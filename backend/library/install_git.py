"""The git steps of an install: fetch a game bounded before anything is checked out, list its tree, check it out,
and read a repository's branches. Standard library only; ``git`` is the only network access.

The rules follow Hermes's own install from git (its helpers are not plugin API, so they are written again here): git
never prompts and never reads the user's git configuration, hooks or credential helpers; every step has a timeout and
its output is capped; a clone is anonymous first, and only one GitHub refused is retried with the user's GitHub token
(``GITHUB_TOKEN``, ``GH_TOKEN`` or ``gh auth token --hostname github.com``), sent as a one-shot header in git's
environment (never in its arguments, the URL or a file) with redirects off.

A fetch is shallow and partial (``--filter=blob:limit``: no file over the per-file limit is downloaded) and checks
nothing out. ``tree`` lists what the commit holds (modes, sizes) so a link, a submodule, a file too large, too many
files or two paths that are the same on a case-insensitive disk are refused before any file is written.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from .install_source import GITHUB, Source, SourceError

CLONE_TIMEOUT = 300
QUICK_TIMEOUT = 60
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TREE_ENTRIES = 20_000
_COMMIT_CHARS = frozenset("0123456789abcdef")
# What git prints when a remote wants credentials it was not given (GitHub answers a private repository it will not
# show with "not found").
_AUTH_REFUSED = (
    "could not read username",
    "could not read password",
    "authentication failed",
    "terminal prompts disabled",
    "repository not found",
    "returned error: 401",
    "returned error: 403",
    "returned error: 404",
)
# Configuration every command runs with, whatever the repository's own says.
_SAFE_CONFIG = (
    "-c", "core.hooksPath=" + os.devnull,
    "-c", "core.fsmonitor=false",
    "-c", "core.symlinks=false",
    "-c", "credential.helper=",
    "-c", "protocol.ext.allow=never",
    "-c", "submodule.recurse=false",
    "-c", "advice.detachedHead=false",
)  # fmt: skip


def is_commit(value) -> bool:
    return isinstance(value, str) and len(value) == 40 and set(value) <= _COMMIT_CHARS


def git_environment(extra: dict | None = None) -> dict:
    """The environment for every git command here: no prompts (terminal, credential manager, ssh), none of the
    user's git configuration (global or system) or ``GIT_*`` settings, no lazy fetch of a filtered file."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_NO_LAZY_FETCH": "1",
            # A local (file://) remote serves the partial fetch too.
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "uploadpack.allowFilter",
            "GIT_CONFIG_VALUE_0": "true",
        }
    )
    for key, value in (extra or {}).items():
        index = int(environment["GIT_CONFIG_COUNT"])
        environment.update({f"GIT_CONFIG_KEY_{index}": key, f"GIT_CONFIG_VALUE_{index}": value})
        environment["GIT_CONFIG_COUNT"] = str(index + 1)
    return environment


def run_git(args: list[str], *, cwd: Path, timeout: int = QUICK_TIMEOUT, url: str = "") -> str:
    """Run one git command in ``cwd`` and return its output (at most ``MAX_OUTPUT_BYTES``). ``url`` names the remote a
    network command talks to: refused anonymously, a GitHub URL is tried once more with the user's GitHub token.
    Raises ``SourceError`` (``NO_GIT``, ``TIMEOUT``, ``OUTPUT``, ``GIT``)."""
    git = shutil.which("git")
    if git is None:
        raise SourceError("NO_GIT", "git is not installed; install it to install games from a link.")
    error = ""
    for attempt in range(2 if url.startswith(GITHUB) else 1):
        extra = {}
        if attempt:
            token = _github_token()
            if token is None:
                break
            pair = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            extra = {f"http.{GITHUB}.extraheader": f"AUTHORIZATION: basic {pair}", "http.followRedirects": "false"}
        code, output, message = _run([git, *_SAFE_CONFIG, *args], cwd, git_environment(extra), timeout)
        if code == 0:
            return output
        error = message
        if not any(sign in error.lower() for sign in _AUTH_REFUSED):
            break
    raise SourceError("GIT", error or "git failed.")


def _run(command: list[str], cwd: Path, environment: dict, timeout: int) -> tuple[int, str, str]:
    """``(exit code, output, error text)``; the output is read from a file so a huge one is never held whole."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise SourceError(
                "TIMEOUT", f"git took longer than {timeout} seconds; check the connection and retry."
            ) from exc
        except OSError as exc:
            raise SourceError("NO_GIT", f"git could not run: {exc}.") from exc
        out.seek(0)
        data = out.read(MAX_OUTPUT_BYTES + 1)
        if len(data) > MAX_OUTPUT_BYTES:
            raise SourceError("OUTPUT", "The repository is too large to install from.")
        err.seek(max(0, err.seek(0, os.SEEK_END) - 4000))
        message = err.read().decode("utf-8", "replace").strip()
    return completed.returncode, data.decode("utf-8", "replace"), message


def _github_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip() or None
    gh = shutil.which("gh")
    if gh is None:
        return None
    try:
        result = subprocess.run(
            [gh, "auth", "token", "--hostname", "github.com"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip()
    return token if result.returncode == 0 and token and len(token) < 512 and " " not in token else None


# -- fetching ---------------------------------------------------------------------------------------


def fetch(source: Source, destination: Path) -> str:
    """Fetch ``source``'s branch into ``destination`` (which must not exist): one commit, files over the per-file
    limit left out, nothing checked out. Returns the commit."""
    if not source.ref:
        raise SourceError("NO_BRANCH", "The source has no branch yet.")
    run_git(
        [
            "clone",
            "--depth",
            "1",
            "--no-tags",
            "--single-branch",
            "--no-checkout",
            "--no-local",
            f"--filter=blob:limit={MAX_FILE_BYTES}",
            "--branch",
            source.ref,
            "--",
            source.url,
            str(destination),
        ],  # fmt: skip
        cwd=destination.parent,
        timeout=CLONE_TIMEOUT,
        url=source.url,
    )
    commit = run_git(["rev-parse", "HEAD"], cwd=destination).strip()
    if not is_commit(commit):
        raise SourceError("GIT", "git did not report the commit it fetched.")
    return commit


def tree(checkout: Path, subdir: str | None) -> list[dict]:
    """Every entry of the fetched commit under ``subdir``: ``{path, mode, kind, size}`` (``size`` None for a file
    the fetch left out because it is over the per-file limit), ``path`` relative to ``subdir``."""
    prefix = f"{subdir}/" if subdir else ""
    listing = run_git(["ls-tree", "-r", "-z", "--full-tree", "HEAD"], cwd=checkout).split("\0")
    sizes = {}
    for line in run_git(
        ["cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)", "--batch-all-objects"], cwd=checkout
    ).splitlines():
        name, kind, size = (line.split(" ") + ["", ""])[:3]
        if kind == "blob" and size.isdigit():
            sizes[name] = int(size)
    entries = []
    for item in listing:
        if not item:
            continue
        meta, _, path = item.partition("\t")
        mode, kind, name = (meta.split(" ") + ["", ""])[:3]
        if not path.startswith(prefix):
            continue
        entries.append({"path": path[len(prefix) :], "mode": mode, "kind": kind, "size": sizes.get(name)})
        if len(entries) > MAX_TREE_ENTRIES:
            break
    return entries


def tree_problems(entries: list[dict], *, max_files: int, max_total: int) -> list[dict]:
    """What makes a fetched tree unsafe to check out: links, submodules, files over the limit, too many files or
    bytes, and paths that are one path on a case-insensitive or Unicode-normalising disk (macOS)."""
    problems, seen, total = [], {}, 0
    if len(entries) > max_files:
        problems.append(_finding("TOO_MANY", "", f"The game has more than {max_files} files."))
    for entry in entries:
        path = entry["path"]
        if entry["mode"] == "120000":
            problems.append(_finding("LINK", path, f"{path} is a link; a game holds only plain files."))
        elif entry["mode"] == "160000" or entry["kind"] == "commit":
            problems.append(_finding("SUBMODULE", path, f"{path} is another repository; a game holds only its files."))
        elif entry["size"] is None or entry["size"] > MAX_FILE_BYTES:
            problems.append(_finding("TOO_BIG", path, f"{path} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB."))
        else:
            total += entry["size"]
        parts = path.split("/")
        for depth in range(1, len(parts) + 1):
            spelled = "/".join(parts[:depth])
            key = unicodedata.normalize("NFC", spelled).casefold()
            other = seen.setdefault(key, spelled)
            if other != spelled:
                problems.append(_finding("COLLISION", spelled, f"{spelled} and {other} are the same path on a Mac."))
                break
    if total > max_total:
        problems.append(_finding("TOO_BIG", "", f"The game is larger than {max_total // (1024 * 1024)} MB."))
    return problems


def checkout(checkout_root: Path, subdir: str | None) -> None:
    """Write the fetched commit's files under ``subdir`` (all of them without one) into the checkout."""
    pathspec = f":(literal){subdir}" if subdir else "."
    run_git(["checkout", "-q", "HEAD", "--", pathspec], cwd=checkout_root, timeout=CLONE_TIMEOUT)


# -- branches -------------------------------------------------------------------------------------


def settle(source: Source) -> Source:
    """The source with its branch known: the default branch when none was named, and for a ``…/tree/<rest>`` link
    the longest of the repository's branches and tags that ``rest`` starts with (the rest is the folder)."""
    if source.ref and not source.tree:
        return source
    with tempfile.TemporaryDirectory(prefix="hermretro-refs-") as outside:  # never inside someone's checkout
        if source.tree is None:
            output = run_git(["ls-remote", "--symref", "--", source.url, "HEAD"], cwd=Path(outside), url=source.url)
            for line in output.splitlines():
                if line.startswith("ref: refs/heads/") and line.endswith("\tHEAD"):
                    return source.with_ref(line[len("ref: refs/heads/") : -len("\tHEAD")], source.subdir)
            raise SourceError("NO_BRANCH", "The repository has no default branch.")
        output = run_git(["ls-remote", "--heads", "--tags", "--", source.url], cwd=Path(outside), url=source.url)
    names = set()
    for line in output.splitlines():
        name = line.partition("\t")[2].strip().removesuffix("^{}")
        for prefix in ("refs/heads/", "refs/tags/"):
            if name.startswith(prefix):
                names.add(name[len(prefix) :])
    matches = [name for name in names if source.tree == name or source.tree.startswith(name + "/")]
    if not matches:
        raise SourceError("NO_BRANCH", f"The repository has no branch for {source.tree!r}.")
    ref = max(matches, key=len)
    return source.with_ref(ref, source.tree[len(ref) + 1 :] or None)


def remote_commit(source: Source) -> str:
    """The commit the source's branch is at now, read without cloning (``ls-remote``, outside any checkout)."""
    with tempfile.TemporaryDirectory(prefix="hermretro-refs-") as outside:
        output = run_git(
            ["ls-remote", "--", source.url, f"refs/heads/{source.ref}", f"refs/tags/{source.ref}"],
            cwd=Path(outside),
            url=source.url,
        )
    found = {}
    for line in output.splitlines():
        commit, _, name = line.partition("\t")
        if is_commit(commit.strip()):
            found[name.strip()] = commit.strip()
    tag = f"refs/tags/{source.ref}"
    for name in (f"refs/heads/{source.ref}", tag + "^{}", tag):  # a branch, else an annotated tag's commit
        if name in found:
            return found[name]
    raise SourceError("NO_BRANCH", f"The repository has no branch {source.ref}.")


def _finding(code: str, path: str, message: str) -> dict:
    return {"code": code, "path": path, "message": message}
