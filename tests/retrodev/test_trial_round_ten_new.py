"""Friction the tenth round of fresh-agent trials found in `new`: rpc chose callStudioOnly by the feature instead of
what the handler reads; contribution and tab named no page test to put their checks in; event said nothing about
changing a payload later; a library --project tool had no way to seed a game's last build in its test; the
reference did not say how tools.py splits. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_ten_new
"""

import re
import subprocess
import sys
import textwrap

from retrodev import scaffold_page_tests

from tests.retrodev.fixture import git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase

load_tests = parallel
HARNESS = "  ctx = { os: { writeClipboard: async () => true, openExternal: async () => true } }\n  const pageTab = 1\n"
STUB = "  notify: notice => scenario.notices.push(notice),\n"


def label_of(door: str) -> str:
    found = scaffold_page_tests.LABEL.search(door)
    assert found, door
    return found.group(2)


def joined(out) -> str:
    return " ".join(out["next"])


class Rpc(ScaffoldCase):
    def test_what_the_handler_reads_decides_the_call(self):
        self.new("feature", "rdprobe")
        steps = joined(self.new("rpc", "rdprobe", "rdprobe_peek"))
        self.assertIn(
            "if the handler reads or binds a profile's Build conversations or its plugin data folder "
            "(host._data_dir(): snapshots, asset versions); otherwise callStudio",
            steps,
        )
        self.assertIn("what the handler reads decides, not the feature", steps)
        self.assertNotIn("usually do", steps, "the default for history and assets only")
        self.assertIn("callStudioOnly", retrodev_docs("REFERENCE.md"))
        self.assertIn("chosen by what the handler reads, not by the feature", retrodev_docs("REFERENCE.md"))


class Contribution(ScaffoldCase):
    def probe_host(self) -> None:
        self.new("page", "rdprobe-host")
        self.new("slot", "rdprobe-host", "extra", "--doc", "Buttons at the end. Props: { ctx }")
        write(
            self.tree,
            "page/pages/rdprobe-host/extra-menu.js",
            "export const Menu = () => jsx('div', { className: 'cs-rdextra', children: "
            "jsx(Slot, { name: 'rdprobe-host.extra', props: {} }) })\n",
        )
        label = label_of(self.read("page/pages/rdprobe-host/index.js"))
        opening = "  const openExtra = async () => {\n    await click(dom.querySelector('.cs-rdextra'))\n  }\n"
        write(self.tree, "tests/page/page-rdprobe-host.test.mjs", f"await tab('{label}')\n{opening}")
        write(self.tree, "tests/page/page-other.test.mjs", f"await tab('{label}')\n")
        write(self.tree, "tests/page/harness.mjs", HARNESS)
        write(self.tree, "tests/page/sdk-stub.mjs", STUB)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "probe host")

    def test_the_next_steps_name_the_host_page_s_scenario_test_its_helper_and_the_doubles(self):
        self.probe_host()
        steps = joined(self.new("contribution", "home", "rdprobe-host.extra", "RdprobeItem"))
        self.assertIn("test what RdprobeItem does in the host page's scenario test tests/page/page-rdprobe-host", steps)
        self.assertIn("then openExtra shows `rdprobe-host.extra`", steps)
        self.assertIn("ctx.os (writeClipboard, openExternal: tests/page/harness.mjs)", steps)
        self.assertIn("scenario.notices (what notify() showed: tests/page/sdk-stub.mjs)", steps)
        self.assertIn("(also opening Rdprobe host: tests/page/page-other.test.mjs)", steps)

    def test_a_host_no_test_opens_says_so(self):
        self.new("page", "rdprobe-lone")
        self.new("slot", "rdprobe-lone", "extra", "--doc", "Buttons. Props: { ctx }")
        steps = joined(self.new("contribution", "home", "rdprobe-lone.extra", "RdprobeLoner"))
        self.assertIn("no tests/page/*.test.mjs opens it yet", steps)

    def test_games_card_menu_points_at_page_games_and_open_game_menu(self):
        # The case the trial hit, on the real files (read from the tree, as new reads them).
        for path in [*ROOT.glob("page/pages/games/**/*.js"), *ROOT.glob("page/pages/games/*.md")]:
            write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        for name in ("page-games.test.mjs", "harness.mjs", "sdk-stub.mjs"):
            write(self.tree, f"tests/page/{name}", (ROOT / "tests/page" / name).read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "games")
        steps = joined(self.new("contribution", "home", "games.cardMenu", "RdprobeCopy"))
        self.assertIn("tests/page/page-games.test.mjs: it opens Games with tab('Games'), then openGameMenu", steps)
        self.assertIn("writeClipboard", steps)
        self.assertIn("scenario.notices", steps)


class Tab(ScaffoldCase):
    def test_the_next_steps_name_the_test_that_renders_the_page_s_checks(self):
        self.new("page", "rdprobe-tabbed")
        label = label_of(self.read("page/pages/rdprobe-tabbed/index.js"))
        write(self.tree, "tests/page/page-rdprobe-tabbed.test.mjs", f"await tab('{label}')\n")
        write(self.tree, "tests/page/harness.mjs", HARNESS)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "probe test")
        steps = joined(self.new("tab", "rdprobe-tabbed", "extra"))
        self.assertIn(  # round 15: the page's own files, or a new one for the tab
            "add a check to the existing tests/page/page-rdprobe-tabbed*.test.mjs that covers this tab "
            "(tests/page/page-rdprobe-tabbed.test.mjs), or a new tests/page/page-rdprobe-tabbed-extra.test.mjs",
            steps,
        )
        self.assertIn(f"tab('{label}') opens the page, then pageTab('Extra') opens the tab", steps)
        self.new("page", "rdprobe-untested")
        steps = joined(self.new("tab", "rdprobe-untested", "extra"))
        self.assertIn("the tab's checks: add tests/page/page-rdprobe-untested-extra.test.mjs", steps)


class Event(ScaffoldCase):
    def test_the_next_steps_and_the_reference_say_how_to_change_a_payload_later(self):
        steps = joined(self.new("event", "history", "rdprobe_moved", "--payload", "game=<id>"))
        self.assertIn(  # round 12: the steps point to the reference's list, which names the callers and tests too
            "changing history.rdprobe_moved's payload later: tools/retrodev/REFERENCE.md \"Changing an event's "
            "payload or name\" lists every place (backend/history/emits.py's function rdprobe_moved, its callers: "
            "grep -rn 'rdprobe_moved(' backend/history; the EVENTS entry in backend/history/__init__.py, its "
            "docs/dev/CONTRACT.md row, tests/backend/history/test_event_rdprobe_moved.py",
            steps,
        )
        self.assertIn("### Changing an event's payload or name", retrodev_docs("REFERENCE.md"))


SEEDED = """
import sys, time, unittest
sys.path.insert(0, {root!r})
from backend import library
from backend.hermes import host
from tests.support import isolated_home


class Seed(unittest.TestCase):
    def test_seed(self):
        home = isolated_home(self)
        project = home.base / "game"
        project.mkdir()
        {seed}
        root = str(project)
        self.assertEqual({read}["sha256"], "abc")


result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Seed))
sys.exit(0 if result.wasSuccessful() else 1)
"""


class Tool(ScaffoldCase):
    def test_a_library_project_tool_says_how_to_seed_the_last_build_and_that_call_works(self):
        for name in ("__init__.py", "tool_args.py"):
            write(self.tree, f"backend/library/{name}", (ROOT / f"backend/library/{name}").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "tool_args")
        steps = joined(self.new("tool", "library", "rdprobe_built"))
        seed = re.search(r"host\._registry\(\)\.upsert\(str\(project\), build=\{[^}]*\}\)", steps)
        read = re.search(r"host\._registry\(\)\.get\(library\.game_id\(root\)\)\[\"lastBuild\"\]", steps)
        self.assertIsNotNone(seed, steps)
        self.assertIsNotNone(read, steps)
        script = SEEDED.format(root=str(ROOT), seed=seed and seed.group(0), read=read and read.group(0))
        done = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(script)], cwd=ROOT, capture_output=True, text=True, timeout=120
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_the_reference_says_how_tools_py_splits(self):
        text = retrodev_docs("REFERENCE.md")
        self.assertIn("when `tools.py` is over 400 lines", text)
        self.assertIn(
            "Splitting `tools.py` by hand works the same way: each module has its own `TOOLS`, `tools.py` aggregates "
            "them",
            text,
        )
        self.assertIn("tests patch names on the new module", text)
