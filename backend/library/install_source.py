"""Where an installed game comes from: a link the user pastes, turned into a git URL, a branch and an optional
subfolder. Standard library only; nothing here runs git (``install_git.py`` does).

    owner/repo  owner/repo/sub/dir  owner/repo#sub/dir                 GitHub shorthand
    https://github.com/owner/repo[.git][/tree/<branch>[/<path>]]       a GitHub page or clone URL
    git@host:owner/repo.git  ssh://[user@]host[:port]/path.git         SSH, any host; ``#sub/dir`` names a subfolder
    file:///path/to/repo                                               a local repository, only where allowed

Only these transports are installed from (``check_transport``, run again on a source read back from an install
record): HTTPS to github.com, SSH, and ``file://`` when the caller allows local sources (tests, a folder of the
user's own). A link carrying credentials (a password or token in the URL, a query string) is refused rather than
scrubbed: a secret pasted into a link would otherwise reach git and its error messages. ``…/tree/<rest>`` names a
branch and a folder at once (``feature/demo`` may be either); ``install_git.settle`` decides against the
repository's own branches and tags, the longest that matches winning.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field, replace
from pathlib import Path

GITHUB = "https://github.com/"
_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
# user@host:path, git's "SCP-like" SSH syntax.
_SCP = re.compile(r"^(?P<user>[A-Za-z0-9._-]+)@(?P<host>[A-Za-z0-9.-]+):(?P<path>[A-Za-z0-9._~/-]+)$")
_HOST = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$")


class SourceError(Exception):
    """A link that cannot be installed from, or a git step that failed: ``code`` and a sentence for the user."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Source:
    """A resolved link: the URL git clones, the branch (None until ``settle`` reads the default branch), the
    subfolder that holds the game (None: the repository's root) and, for a ``…/tree/<rest>`` link not yet settled,
    that ``rest``."""

    url: str
    ref: str | None = None
    subdir: str | None = None
    tree: str | None = field(default=None, compare=False)

    @property
    def canonical(self) -> str:
        """Which game this is, whatever link was pasted: the repository and the folder in it, without the branch,
        user names or ``.git`` (two installs with this the same are the same game from the same place)."""
        url = self.url
        if url.startswith(GITHUB):
            url = url.lower()
        match = _SCP.match(url)
        if match:
            url = f"ssh://{match['host']}/{match['path'].lstrip('/')}"
        elif url.startswith("ssh://"):
            parsed = urllib.parse.urlsplit(url)
            port = f":{parsed.port}" if parsed.port else ""
            url = f"ssh://{parsed.hostname}{port}{parsed.path}"
        url = url.removesuffix("/").removesuffix(".git")
        return url + (f"#{self.subdir}" if self.subdir else "")

    def record(self) -> dict:
        """What an install record keeps: enough to fetch the same branch again (``from_record``)."""
        return {"canonical": self.canonical, "url": self.url, "ref": self.ref, "subdir": self.subdir}

    def with_ref(self, ref: str, subdir: str | None) -> Source:
        return replace(self, ref=ref, subdir=subdir, tree=None)


def resolve(link, *, allow_local: bool = False) -> Source:
    """The ``Source`` a pasted link (or a ``Source.record()`` dict, as ``inspect`` returns it) names. Raises
    ``SourceError(BAD_LINK)`` for anything else."""
    if isinstance(link, Source):
        check_transport(link.url, allow_local=allow_local)
        return link
    if isinstance(link, dict):
        return from_record(link, allow_local=allow_local)
    text = link.strip() if isinstance(link, str) else ""
    if not text or any(char.isspace() or ord(char) < 32 for char in text):
        raise SourceError("BAD_LINK", "Paste a GitHub link, owner/repo, or a git URL.")
    try:
        if text.startswith("https://") or text.startswith("http://"):
            source = _resolve_https(text)
        elif text.startswith(("ssh://", "file://")) or _SCP.match(text.partition("#")[0]):
            url, _, fragment = text.partition("#")
            source = Source(url, None, _subdir(fragment))
        else:
            source = _resolve_shorthand(text)
    except ValueError as error:  # urllib's own refusals (a bad port, a bad IPv6 host)
        raise SourceError("BAD_LINK", f"{text!r} is not a link to install from ({error}).") from error
    check_transport(source.url, allow_local=allow_local)
    return source


def from_record(record: dict, *, allow_local: bool = False) -> Source:
    """A source read back from an install record (or an inspect answer), checked like a pasted link."""
    url, ref, subdir = (record.get(key) for key in ("url", "ref", "subdir"))
    if (
        not isinstance(url, str)
        or not (ref is None or isinstance(ref, str))
        or not (subdir is None or isinstance(subdir, str))
    ):
        raise SourceError("BAD_LINK", "The game's recorded source is damaged; install it again from its link.")
    check_transport(url, allow_local=allow_local)
    if ref is not None:
        _check_ref(ref)
    return Source(url, ref, _subdir(subdir or ""))


def check_transport(url: str, *, allow_local: bool = False) -> None:
    """Refuse every URL but HTTPS to github.com, SSH and (``allow_local``) ``file://``, and any with credentials."""
    try:
        if url.startswith(GITHUB):
            parsed = urllib.parse.urlsplit(url)
            if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port:
                raise SourceError("BAD_LINK", "Paste the link without a name, password, token or query in it.")
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) != 2 or not all(_NAME.match(part) for part in parts) or parts[0].startswith("-"):
                raise SourceError("BAD_LINK", f"{url!r} is not a GitHub repository.")
            return
        if url.startswith("ssh://"):
            parsed = urllib.parse.urlsplit(url)
            _ = parsed.port  # raises ValueError for a bad one
            if parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
                raise SourceError("BAD_LINK", "An SSH link names a host and a path, with no password or query.")
            if not _HOST.match(parsed.hostname) or not parsed.path.strip("/") or parsed.path.startswith("//-"):
                raise SourceError("BAD_LINK", f"{url!r} is not an SSH repository link.")
            return
        match = _SCP.match(url)
        if match:
            if match["path"].startswith("-") or match["host"].startswith("-") or not _HOST.match(match["host"]):
                raise SourceError("BAD_LINK", f"{url!r} is not an SSH repository link.")
            return
        if url.startswith("file://") and allow_local:
            parsed = urllib.parse.urlsplit(url)
            if parsed.netloc not in ("", "localhost") or parsed.query or parsed.fragment or not parsed.path:
                raise SourceError("BAD_LINK", f"{url!r} is not a local repository.")
            return
    except ValueError as error:
        raise SourceError("BAD_LINK", f"{url!r} is not a link to install from ({error}).") from error
    raise SourceError("BAD_LINK", "Install from a GitHub link (https://github.com/…) or an SSH git URL.")


def _resolve_shorthand(text: str) -> Source:
    path, _, fragment = text.partition("#")
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) < 2 or not all(_NAME.match(part) and not part.startswith("-") for part in parts[:2]):
        raise SourceError("BAD_LINK", f"{text!r} is not a GitHub owner/repo or a git URL.")
    subdir = "/".join([*parts[2:], *[part for part in fragment.split("/") if part]])
    return Source(f"{GITHUB}{parts[0]}/{parts[1].removesuffix('.git')}.git", None, _subdir(subdir))


def _resolve_https(text: str) -> Source:
    parsed = urllib.parse.urlsplit(text)
    if parsed.username or parsed.password or parsed.query:
        raise SourceError("BAD_LINK", "Paste the link without a name, password, token or query in it.")
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() not in ("github.com", "www.github.com")
        or parsed.port
    ):
        raise SourceError("BAD_LINK", "Install from a GitHub link (https://github.com/…) or an SSH git URL.")
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 2 or not all(_NAME.match(part) and not part.startswith("-") for part in parts[:2]):
        raise SourceError("BAD_LINK", f"{text!r} does not name a GitHub repository.")
    url = f"{GITHUB}{parts[0]}/{parts[1].removesuffix('.git')}.git"
    if len(parts) == 2:
        return Source(url, None, _subdir(parsed.fragment))
    if parts[2] != "tree" or len(parts) < 4:
        raise SourceError("BAD_LINK", "Link to the repository or one of its folders (…/tree/<branch>/…).")
    rest = "/".join(parts[3:])
    _check_ref(parts[3])
    _subdir(rest)
    return Source(url, None, None, tree=rest)


def _check_ref(ref: str) -> None:
    if (
        not ref
        or ref.startswith("-")
        or ".." in ref
        or ref.endswith((".lock", "/"))
        or any(c in ref for c in "~^:?*[\\ ")
    ):
        raise SourceError("BAD_LINK", f"{ref!r} is not a branch name.")


def _subdir(text: str) -> str | None:
    """A subfolder path as a plain relative path (None for none); refused when it could leave the repository."""
    text = (text or "").replace("\\", "/").strip("/")
    if not text:
        return None
    parts = text.split("/")
    if any(part in ("", ".", "..") for part in parts) or "\0" in text:
        raise SourceError("BAD_LINK", f"The folder {text!r} must be a plain path inside the repository.")
    return text


def within(root: Path, subdir: str | None) -> Path:
    """The folder ``subdir`` names inside the checkout ``root``; refused when it escapes it (``..``, a link), is
    missing or is not a folder."""
    root = Path(root).resolve()
    subdir = _subdir(subdir or "")
    if not subdir:
        return root
    current = root
    for part in subdir.split("/"):
        current = current / part
        if current.is_symlink():
            raise SourceError("BAD_FOLDER", f"The folder {subdir!r} is a link; it must be a real folder.")
    resolved = current.resolve()
    if resolved != root and root not in resolved.parents:
        raise SourceError("BAD_FOLDER", f"The folder {subdir!r} is outside the repository.")
    if not resolved.is_dir():
        raise SourceError("BAD_FOLDER", f"The repository has no folder {subdir!r}.")
    return resolved
