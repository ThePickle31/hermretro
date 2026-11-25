"""Where an installed game comes from: a link the user pastes, turned into a git URL, an optional branch and an optional
subfolder, and the git commands that fetch it. Standard library only; the only network access is ``git`` itself.

The rules follow Hermes's own install from git (its helpers are not part of the plugin API, so they are written again
here): git never prompts and never reads the user's git configuration, hooks or credential helpers; every step has a
timeout; a clone is anonymous first, and only a refused one is retried with a GitHub token (``GITHUB_TOKEN``,
``GH_TOKEN`` or ``gh auth token``) sent as a one-shot header in git's environment, never in the URL or a file; and
every URL that is recorded or shown has its credentials, query and fragment removed.

    owner/repo  owner/repo/sub/dir  owner/repo#sub/dir              GitHub shorthand
    https://github.com/owner/repo[.git][/tree/<branch>[/<path>]]    a GitHub page or clone URL
    https://host/path.git  ssh://…  git@host:path.git  file://…     any other git URL; ``#sub/dir`` names a subfolder
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

# Each git step's limit, in seconds (a clone of a game is small: its ROM, its card and, with the source, its project).
CLONE_TIMEOUT = 300
QUICK_TIMEOUT = 60
_SCHEMES = ("https://", "http://", "ssh://", "git@", "file://")
_GITHUB = "https://github.com/"
_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
# What git prints when a remote wants credentials it was not given (a private repository; GitHub answers a private
# repository it will not show with "not found").
_AUTH_REFUSED = re.compile(
    r"could not read (username|password)|authentication failed|terminal prompts disabled|"
    r"repository '[^']*' not found|requested url returned error: 40[134]",
    re.I,
)


class SourceError(Exception):
    """A link that cannot be installed from, or a git step that failed: ``code`` and a sentence for the user."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Source:
    """A resolved link: the URL git clones (credentials and all, as the user gave it), the branch (None: the default
    branch) and the subfolder that holds the game (None: the repository's root)."""

    url: str
    ref: str | None = None
    subdir: str | None = None

    @property
    def public_url(self) -> str:
        return scrub(self.url)

    @property
    def canonical(self) -> str:
        """The one spelling of where the game comes from: the same repository and folder always give the same
        string, whatever link was pasted (a game's install record compares it)."""
        url = self.public_url
        if url.startswith(_GITHUB):
            url = url.lower()
        if url.endswith(".git"):
            url = url[: -len(".git")]
        return url.rstrip("/") + (f"#{self.subdir}" if self.subdir else "")

    def record(self) -> dict:
        return {"url": self.public_url, "ref": self.ref, "subdir": self.subdir}


def resolve(link: str) -> Source:
    """The ``Source`` a pasted link names. Raises ``SourceError(BAD_LINK)`` for anything else."""
    text = (link or "").strip()
    if not text or any(char.isspace() or ord(char) < 32 for char in text):
        raise SourceError("BAD_LINK", "Paste a GitHub link, owner/repo, or a git URL.")
    if text.startswith(_SCHEMES):
        source = _resolve_url(text)
    else:
        source = _resolve_shorthand(text)
    if source.subdir is not None:
        _check_subdir(source.subdir)
    if source.ref is not None and (source.ref.startswith("-") or ".." in source.ref or not source.ref.strip()):
        raise SourceError("BAD_LINK", f"{source.ref!r} is not a branch name.")
    return source


def _resolve_shorthand(text: str) -> Source:
    path, _, fragment = text.partition("#")
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) < 2 or not all(_NAME.match(part) for part in parts[:2]):
        raise SourceError("BAD_LINK", f"{text!r} is not a GitHub owner/repo or a git URL.")
    subdir = "/".join([*parts[2:], *[part for part in fragment.split("/") if part]]) or None
    return Source(f"{_GITHUB}{parts[0]}/{parts[1].removesuffix('.git')}.git", None, subdir)


def _resolve_url(text: str) -> Source:
    if text.startswith(_GITHUB) or text.startswith("https://www.github.com/"):
        parsed = urllib.parse.urlsplit(text)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2 or not all(_NAME.match(part) for part in parts[:2]):
            raise SourceError("BAD_LINK", f"{text!r} does not name a GitHub repository.")
        owner, repo = parts[0], parts[1].removesuffix(".git")
        ref, subdir = None, None
        if len(parts) > 2:
            if parts[2] != "tree" or len(parts) < 4:
                raise SourceError("BAD_LINK", "Link to the repository or one of its folders (…/tree/<branch>/…).")
            ref = urllib.parse.unquote(parts[3])
            subdir = "/".join(urllib.parse.unquote(part) for part in parts[4:]) or None
        if parsed.fragment:
            subdir = parsed.fragment.strip("/") or subdir
        return Source(f"{_GITHUB}{owner}/{repo}.git", ref, subdir)
    url, _, fragment = text.partition("#")
    if not url.startswith(("git@", "file://")):
        parsed = urllib.parse.urlsplit(url)
        if not parsed.hostname:
            raise SourceError("BAD_LINK", f"{text!r} is not a git URL.")
    return Source(url, None, fragment.strip("/") or None)


def _check_subdir(subdir: str) -> None:
    parts = subdir.replace("\\", "/").split("/")
    if subdir.startswith(("/", "\\")) or any(part in ("", ".", "..") for part in parts) or "\0" in subdir:
        raise SourceError("BAD_LINK", f"The folder {subdir!r} must be a plain path inside the repository.")


def scrub(url: str) -> str:
    """``url`` without credentials, query or fragment (an ``http(s)`` URL; others are returned as they are)."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return url.partition("#")[0]
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def within(root: Path, subdir: str | None) -> Path:
    """The folder ``subdir`` names inside the checkout ``root``; refused when it escapes it (``..``, an absolute path, a
    link), is missing or is not a folder."""
    root = Path(root).resolve()
    if not subdir:
        return root
    _check_subdir(subdir)
    candidate = root / subdir
    resolved = candidate.resolve()
    if any(Path(root, *subdir.split("/")[: index + 1]).is_symlink() for index in range(len(subdir.split("/")))):
        raise SourceError("BAD_FOLDER", f"The folder {subdir!r} is a link; it must be a real folder.")
    if resolved != root and root not in resolved.parents:
        raise SourceError("BAD_FOLDER", f"The folder {subdir!r} is outside the repository.")
    if not resolved.is_dir():
        raise SourceError("BAD_FOLDER", f"The repository has no folder {subdir!r}.")
    return resolved


# -- running git ----------------------------------------------------------------------------------


def git_environment(extra: dict | None = None) -> dict:
    """The environment for every git command here: no prompts (terminal, credential manager, ssh), and none of the
    user's git configuration (global or system), so a repository cannot run hooks, filters or helpers."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GIT_SSH_COMMAND": os.environ.get("GIT_SSH_COMMAND") or "ssh -o BatchMode=yes",
            "GIT_LFS_SKIP_SMUDGE": "1",
        }
    )
    environment.update(extra or {})
    return environment


# Configuration every command runs with, whatever the repository's own says.
_SAFE_CONFIG = (
    "-c", "core.hooksPath=" + os.devnull,
    "-c", "core.fsmonitor=false",
    "-c", "credential.helper=",
    "-c", "protocol.ext.allow=never",
    "-c", "submodule.recurse=false",
    "-c", "advice.detachedHead=false",
)  # fmt: skip


def run_git(args: list[str], *, cwd: Path | None = None, timeout: int = QUICK_TIMEOUT, url: str = "") -> str:
    """Run one git command and return its output. ``url`` names the remote a network command talks to: refused
    anonymously, it is tried once more with a GitHub token when it is a GitHub URL and one is available. Raises
    ``SourceError`` (``NO_GIT``, ``TIMEOUT``, ``GIT``) with git's message, any credential removed."""
    git = shutil.which("git")
    if git is None:
        raise SourceError("NO_GIT", "git is not installed; install it to install games from a link.")
    github = bool(url) and scrub(url).lower().startswith(_GITHUB)
    error = ""
    for attempt in range(2 if github else 1):
        extra = {}
        if attempt:  # refused anonymously: the user's own GitHub token, when there is one
            header = _token_header()
            if header is None:
                break
            extra = {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": f"http.{_GITHUB}.extraheader",
                "GIT_CONFIG_VALUE_0": header,
            }
        try:
            result = subprocess.run(
                [git, *_SAFE_CONFIG, *args],
                cwd=str(cwd) if cwd else None,
                env=git_environment(extra),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise SourceError(
                "TIMEOUT", f"git took longer than {timeout} seconds; check the connection and retry."
            ) from exc
        except OSError as exc:
            raise SourceError("NO_GIT", f"git could not run: {exc}.") from exc
        if result.returncode == 0:
            return result.stdout
        error = _clean_error(result.stderr or result.stdout, url)
        if not _AUTH_REFUSED.search(error):
            break
    raise SourceError("GIT", error or "git failed.")


def _clean_error(text: str, url: str) -> str:
    text = text.strip()
    if url and scrub(url) != url:
        text = text.replace(url, scrub(url))
    text = re.sub(r"(https?://)[^/@\s]+@", r"\1", text)
    return text[-800:]


def _token_header() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or _gh_token()
    if not token:
        return None
    pair = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return f"AUTHORIZATION: basic {pair}"


def _gh_token() -> str | None:
    gh = shutil.which("gh")
    if gh is None:
        return None
    try:
        result = subprocess.run(
            [gh, "auth", "token"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip()
    return token if result.returncode == 0 and token and " " not in token else None


def clone(source: Source, destination: Path) -> str:
    """Shallow-clone ``source`` (its branch, else the default branch) into ``destination`` (which must not exist) and
    return the commit checked out."""
    args = ["clone", "--depth", "1", "--no-tags", "--single-branch"]
    if source.ref:
        args += ["--branch", source.ref]
    run_git([*args, "--", source.url, str(destination)], timeout=CLONE_TIMEOUT, url=source.url)
    return head(destination)


def head(checkout: Path) -> str:
    commit = run_git(["rev-parse", "HEAD"], cwd=checkout).strip()
    if not _COMMIT.match(commit):
        raise SourceError("GIT", "git did not report the commit it checked out.")
    return commit


def remote_commit(source: Source) -> str:
    """The commit the source's branch (else its default branch) is at now, read without cloning (``ls-remote``)."""
    output = run_git(["ls-remote", "--", source.url, source.ref or "HEAD"], timeout=QUICK_TIMEOUT, url=source.url)
    wanted = {"HEAD"} if not source.ref else {f"refs/heads/{source.ref}", source.ref}
    for line in output.splitlines():
        commit, _, name = line.partition("\t")
        if name.strip() in wanted and _COMMIT.match(commit.strip()):
            return commit.strip()
    raise SourceError("NO_BRANCH", f"The repository has no branch {source.ref or 'HEAD'}.")


def is_commit(value) -> bool:
    return isinstance(value, str) and bool(_COMMIT.match(value))
