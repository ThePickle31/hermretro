"""Pointers into a document land on a real heading.

Two kinds are checked across the committed documents and source comments: markdown links to an anchor
(``[x](#anchor)``, ``[x](other.md#anchor)``), whose anchor must be one of that file's heading slugs (GitHub's
rule), and a quoted section name after a document's name (``the README, "Install"``, ``ARCHITECTURE.md "The agent
half"``, ``the README's 'Install' section``), which must be one of that document's headings. A renamed heading
otherwise leaves readers (and agents) looking for a section that is not there.

Run alone: python -m unittest tests.repo.test_doc_links
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.repo.test_layout import files  # noqa: E402 - the repository root goes on the path first

SKIPPED = ("engine/", "tools/npm/", "desktop/", "player/")  # vendored or generated
SELF = "tests/repo/test_doc_links.py"  # its examples of broken pointers
SOURCES = (".md", ".py", ".js", ".mjs")
FENCE = re.compile(r"^(```|~~~).*?^\1", re.M | re.S)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.M)
ANCHOR_LINK = re.compile(r"\]\(([^()\s]*?)#([^()\s]+)\)")
QUOTE = r"(?:\"([^\"\n]{2,80})\"|'([^'\n]{2,80})'|“([^”\n]{2,80})”)"
# <document>, "Name" · <document> "Name" · <document>'s "Name" section (the possessive only with "section").
SECTION = re.compile(r"\b(README|[\w./-]+\.md)(?:,? " + QUOTE + r"|'s " + QUOTE + r" section)")


CODE_SPAN = re.compile(r"(`+)(.+?)\1")
EMPHASIS_UNDERSCORE = re.compile(r"(?<![^\W_])_+|_+(?![^\W_])")  # a run of _ not inside a word


def heading_text(raw: str) -> str:
    """The heading as rendered: a link's text, emphasis markers dropped, a code span's text kept literally
    (underscores included, as in an identifier)."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    parts = []
    for index, piece in enumerate(CODE_SPAN.split(text)):
        if index % 3 == 2:
            parts.append(piece)  # a code span's content
        elif index % 3 == 0:
            parts.append(EMPHASIS_UNDERSCORE.sub("", piece.replace("*", "")))
    return "".join(parts).strip()


def headings(text: str) -> list[str]:
    return [heading_text(found) for found in HEADING.findall(FENCE.sub("", text))]


def slugs(text: str) -> set[str]:
    """GitHub's anchors: lower case, punctuation dropped, spaces to hyphens, a -N suffix for a repeat."""
    seen: dict[str, int] = {}
    result = set()
    for heading in headings(text):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if not count else f"{slug}-{count}")
    return result


def resolve(name: str, source: str, tracked: set[str]) -> str | None:
    """The tracked document a pointer names: the README beside the source (else the root one), a path from the
    root or from the source's folder, or the one tracked file with that name."""
    folder = Path(source).parent
    if name == "README":
        beside = (folder / "README.md").as_posix()
        return beside if beside in tracked else "README.md"
    for candidate in (name, (folder / name).as_posix()):
        if candidate in tracked:
            return candidate
    named = [path for path in tracked if path.endswith("/" + name.split("/")[-1]) or path == name]
    return named[0] if len(named) == 1 else None


def broken(text: str, source: str, read, tracked: set[str]) -> list[str]:
    found = []
    if source.endswith(".md"):
        for target, anchor in ANCHOR_LINK.findall(FENCE.sub("", text)):
            if target.startswith(("http://", "https://")):
                continue
            path = (Path(source).parent / target).as_posix() if target else source
            path = Path(path).as_posix()
            normalised = "/".join(_normalise(path.split("/")))
            if normalised not in tracked:
                continue  # a missing file is another test's concern
            if anchor not in slugs(read(normalised)):
                found.append(f"{source}: #{anchor} is not a heading of {normalised}")
    for match in SECTION.finditer(text):
        name = next(group for group in match.groups()[1:] if group)
        document = resolve(match.group(1), source, tracked)
        if document is None or not document.endswith(".md"):
            continue
        if name.lower() not in (heading.lower() for heading in headings(read(document))):
            found.append(f'{source}: "{name}" is not a heading of {document}')
    return found


def _normalise(parts: list[str]) -> list[str]:
    out: list[str] = []
    for part in parts:
        if part == "..":
            out = out[:-1]
        elif part not in ("", "."):
            out.append(part)
    return out


class DocLinks(unittest.TestCase):
    def test_every_pointer_lands_on_a_heading(self):
        tracked = set(files())

        def read(name: str) -> str:
            return (ROOT / name).read_text(encoding="utf-8")

        found = []
        for name in sorted(tracked):
            if name.endswith(SOURCES) and not name.startswith(SKIPPED) and name != SELF and (ROOT / name).is_file():
                found += broken(read(name), name, read, tracked)
        self.assertEqual(
            found,
            [],
            "\n  ".join(["", *found])
            + "\nFIX: point at the heading as it is now written (or add the heading); for an anchor, the heading's "
            "slug: lower case, punctuation dropped, spaces to hyphens",
        )

    def test_the_rule_catches_a_renamed_heading(self):
        docs = {"README.md": "# Tool\n## Install\nFor development, link it.\n", "docs/A.md": "## Mine `x`\n"}
        tracked = set(docs) | {".github/CONTRIBUTING.md"}

        def check(text: str, source: str = ".github/CONTRIBUTING.md") -> list[str]:
            return broken(text, source, docs.__getitem__, tracked)

        self.assertEqual(len(check('See the README, "Develop".')), 1)
        self.assertEqual(len(check("See the README's 'Develop' section.")), 1)
        self.assertEqual(check('See the README, "Install", and the README\'s "Install" section.'), [])
        self.assertEqual(len(check("[here](../README.md#develop)")), 1)
        self.assertEqual(check("[here](../README.md#install) [mine](../docs/A.md#mine-x)"), [])
        self.assertEqual(len(check("[top](#nowhere)", "docs/A.md")), 1)

    def test_anchors_keep_underscores(self):
        """GitHub keeps underscores (in code spans and identifiers) in a heading's anchor and its text."""
        docs = {"docs/C.md": "### `asset_info` RPC\n### `studio_profile` — no params\n## *Bold* and __strong__\n"}
        tracked = set(docs) | {"docs/B.md"}

        def check(text: str) -> list[str]:
            return broken(text, "docs/B.md", docs.__getitem__, tracked)

        self.assertEqual(
            check("[a](C.md#asset_info-rpc) [s](C.md#studio_profile--no-params) [b](C.md#bold-and-strong)"), []
        )
        self.assertEqual(check("See C.md \"asset_info RPC\"."), [])
        self.assertEqual(len(check("[a](C.md#assetinfo-rpc)")), 1)
        self.assertEqual(len(check("See C.md \"assetinfo RPC\".")), 1)
        contract = (ROOT / "docs/dev/CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("studio_profile--no-params", slugs(contract))
        self.assertNotIn("studioprofile--no-params", slugs(contract))


if __name__ == "__main__":
    unittest.main()
