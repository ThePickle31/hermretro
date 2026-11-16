"""The shipped skills: ModRetro's Codex skills tailored to Hermes and to this plugin.

Checks that the text uses the Hermes tool names, has no leftover Codex host wording, and that every
relative link (including its #anchor) resolves inside skills/.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
NAMES = ("setup", "game-planning", "authoring", "pixel-art", "rom-debugging", "deployment")

# Mentions of Codex that deliberately name ModRetro's Codex product or keep a real path/URL.
CODEX_ALLOWED = (
    re.compile(r"https://github\.com/OpenAI-Partners/ModRetro-Chromatic-Plugin-for-Codex/\S*"),
    re.compile(r"ModRetro's Codex plugin"),
    re.compile(r"~/\.codex-gb-studio/chromatic"),
)


def markdown_files():
    return sorted(SKILLS.rglob("*.md"))


def plugin_tools() -> set[str]:
    text = (ROOT / "plugin.yaml").read_text()
    block = text.split("provides_tools:", 1)[1]
    return set(re.findall(r"^\s+-\s+(chromatic_\w+)\s*$", block, re.M))


def engine_tools(plugin: set[str]) -> set[str]:
    own = {"chromatic_studio_device_cli", "chromatic_present_game", "chromatic_game_info", "chromatic_build_report"}
    return {name[len("chromatic_"):] for name in plugin - own}


def fenced(lines):
    inside = False
    for line in lines:
        if line.lstrip().startswith("```"):
            inside = not inside
            yield line, True
        else:
            yield line, inside


def slug(heading: str) -> str:
    text = re.sub(r"[`*_]|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", heading.strip().lower())
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(path: Path) -> set[str]:
    found, counts = set(), {}
    for line, inside in fenced(path.read_text().splitlines()):
        m = None if inside else re.match(r"#{1,6} (.+)$", line)
        if m:
            base = slug(m.group(1))
            n = counts.get(base, 0)
            counts[base] = n + 1
            found.add(base if n == 0 else f"{base}-{n}")
    return found


class SkillsTest(unittest.TestCase):
    def test_six_skills_with_matching_names(self):
        dirs = sorted(p.name for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())
        self.assertEqual(dirs, sorted(NAMES))
        for name in NAMES:
            head = (SKILLS / name / "SKILL.md").read_text().split("\n---\n", 1)[0]
            self.assertIn(f"\nname: {name}\n", head + "\n")
            self.assertRegex(head, r"\ndescription: \S")

    def test_every_chromatic_tool_named_exists(self):
        tools = plugin_tools()
        self.assertTrue(tools)  # the full set is checked against registration by test_lockstep
        for path in markdown_files():
            for name in re.findall(r"\bchromatic_[a-z0-9_]*[a-z0-9]\b", path.read_text()):
                if name == "chromatic_emulator":  # the `chromatic_emulator_*` family
                    continue
                self.assertIn(name, tools, f"{path.relative_to(ROOT)} names unknown tool {name}")

    def test_no_bare_engine_tool_calls(self):
        names = engine_tools(plugin_tools())
        multi = {n for n in names if "_" in n}
        single = names - multi
        problems = []
        for path in markdown_files():
            for number, (line, inside) in enumerate(fenced(path.read_text().splitlines()), 1):
                where = f"{path.relative_to(ROOT)}:{number}"
                if inside:
                    m = re.match(r"\s*([a-z][a-z0-9_]*)( \{|$)", line)
                    if m and m.group(1) in names:
                        problems.append(where)
                    continue
                for span in re.findall(r"`([^`]+)`", line):
                    m = re.match(r"([a-z][a-z0-9_]*)(.*)$", span)
                    if not m:
                        continue
                    name, rest = m.groups()
                    if name in multi and (rest == "" or rest[0] in " .'"):
                        problems.append(f"{where} `{span}`")
                    elif name in single and rest.startswith(" {"):
                        problems.append(f"{where} `{span}`")
                    elif name.endswith("_") and rest == "*" and not name.startswith("chromatic_"):
                        problems.append(f"{where} `{span}`")
        self.assertEqual(problems, [])

    def test_no_codex_host_wording(self):
        problems = []
        for path in SKILLS.rglob("*"):
            if not path.is_file() or path.suffix not in (".md", ".mjs"):
                continue
            for number, line in enumerate(path.read_text().splitlines(), 1):
                for allowed in CODEX_ALLOWED:
                    line = allowed.sub("", line)
                if re.search(r"codex", line, re.I) and not (path.suffix == ".mjs" and "imagegen" in line):
                    problems.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:80]}")
        self.assertEqual(problems, [])
        for path in markdown_files():
            self.assertNotIn("built-in browser", path.read_text(), path)
            self.assertNotIn("modretro-chromatic-", path.read_text(), path)

    def test_relative_links_resolve(self):
        problems = []
        for path in markdown_files():
            for line, inside in fenced(path.read_text().splitlines()):
                if inside:
                    continue
                for target in re.findall(r"\]\(([^)\s]+)\)", line):
                    if re.match(r"[a-z][a-z0-9+.-]*:", target):
                        continue
                    file_part, _, anchor = target.partition("#")
                    resolved = (path.parent / file_part).resolve() if file_part else path
                    where = f"{path.relative_to(ROOT)} -> {target}"
                    if not resolved.is_file() or SKILLS.resolve() not in resolved.parents:
                        problems.append(where)
                    elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
                        problems.append(where + " (anchor)")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
