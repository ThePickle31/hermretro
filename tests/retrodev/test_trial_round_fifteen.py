"""Friction the fifteenth round of fresh-agent trials found: a printed command with a title holding an apostrophe
showed shlex's '"'"' form; `new tab` sent Build's tab to a `### Build` subsection under `## Pages` that does not
exist, kept a `none (...)` Tabs line's parenthetical, and pointed at an unrelated sibling test (the New Game
shelf's); `new listener` put its placeholder on a long wrapped line with the host.logger instruction as docstring
prose; `new event` did not say the broker never emits; takeover's plan approve step lacked RETRODEV_AGENT; the
body warning took 'documents `tools/x`' for a claim. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_fifteen
"""

import io
import shlex
from pathlib import Path

from retrodev import body_names, config, gates, output, scaffold, scaffold_readme, ship

from tests.repo.test_placeholders import left_in
from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]
PAGES_DOC = (ROOT / "docs/dev/STUDIO-PAGES.md").read_text(encoding="utf-8")


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


class Quoting(RepoCase):
    def test_a_title_with_an_apostrophe_is_double_quoted_and_still_one_word(self):
        title = "Fix the player's frame"
        said = ship.command(title)
        self.assertEqual(said, "python tools/retrodev ship --title \"Fix the player's frame\"")
        self.assertNotIn("'\"'\"'", said)
        self.assertEqual(shlex.split(said)[-1], title)

    def test_a_word_double_quotes_would_expand_keeps_shlex_quoting(self):
        for title in ("It's $HOME", 'Say "it\'s"', "It's `x`", "It's a\\b", "It's done!"):
            with self.subTest(title=title):
                said = output.cmd("ship", "--title", title)
                self.assertFalse(said.endswith(f'"{title}"'), said)
                self.assertEqual(shlex.split(said)[-1], title)
        self.assertEqual(output.cmd("a b", "plain"), "'a b' plain")  # no apostrophe: unchanged


class TabDesignHeading(ScaffoldCase):
    def test_the_hint_names_the_page_s_real_heading(self):
        self.assertEqual(
            scaffold_readme.design_heading(PAGES_DOC, "Build"),
            "its `### Page` subsection under `## Build: one game, one conversation` of docs/dev/STUDIO-PAGES.md",
        )
        self.assertEqual(
            scaffold_readme.design_heading(PAGES_DOC, "Home"),
            "its `### Home` subsection under `## Pages` of docs/dev/STUDIO-PAGES.md",
        )
        self.assertIn("it has none yet: add one", scaffold_readme.design_heading(PAGES_DOC, "Rdprobe"))
        self.assertEqual(
            scaffold_readme.design_heading("## Rdpage tools\n\nText.\n", "Rdpage"),
            "its `## Rdpage tools` section of docs/dev/STUDIO-PAGES.md",
        )

    def test_new_tab_says_it(self):
        write(self.tree, "docs/dev/STUDIO-PAGES.md", PAGES_DOC)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "the pages doc")
        said = " ".join(self.new("tab", "home", "extra")["next"])
        self.assertIn("as a bullet in its `### Home` subsection under `## Pages` of docs/dev/STUDIO-PAGES.md", said)
        self.assertNotIn("`### <Page>`", said)


class TabsNoneLine(ScaffoldCase):
    def test_a_none_line_s_parenthetical_goes_with_it(self):
        line = "**Tabs:** none (its areas are subfolders, not tabs)."
        self.assertEqual(
            scaffold.readme_item(line, "Tabs:", "`main` (`main/index.js`)"), "**Tabs:** `main` (`main/index.js`)."
        )
        readme = self.read("page/pages/home/README.md")
        self.assertIn("**Tabs:** none.", readme)
        write(self.tree, "page/pages/home/README.md", readme.replace("**Tabs:** none.", line))
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "a none with a reason")
        self.new("tab", "home", "main", "--from-page")
        self.new("tab", "home", "history")
        tabs = next(row for row in self.read("page/pages/home/README.md").splitlines() if "**Tabs:**" in row)
        self.assertEqual(tabs, "**Tabs:** `main` (`main/index.js`), `history` (`history/index.js`).")


class TabTests(ScaffoldCase):
    def test_the_step_names_the_page_s_own_files_or_a_new_one_for_the_tab(self):
        write(self.tree, "tests/page/page-home-shelf.test.mjs", "await tab('Home')\n")
        write(self.tree, "tests/page/page-home.test.mjs", "await tab('Home')\n")
        write(self.tree, "tests/page/page-homely.test.mjs", "await tab('Home')\n")  # another page's
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "home tests")
        said = " ".join(self.new("tab", "home", "extra")["next"])
        self.assertIn(
            "the tab's checks: add a check to the existing tests/page/page-home*.test.mjs that covers this tab "
            "(tests/page/page-home-shelf.test.mjs, tests/page/page-home.test.mjs), or a new "
            "tests/page/page-home-extra.test.mjs (tests/page/*.test.mjs are picked up automatically; name a new one "
            "on the **Tests:** line of page/pages/home/README.md)",
            said,
        )
        self.assertNotIn("page-homely", said)
        self.assertNotIn("the page's checks are in", said)


class ListenerStub(ScaffoldCase):
    def test_the_placeholder_has_a_line_of_its_own_and_host_logger_is_a_step(self):
        write(self.tree, "backend/library/__init__.py", (ROOT / "backend/library/__init__.py").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "library")
        out = self.new("listener", "history", "library.build_reported")
        source = self.read("backend/history/listeners.py")
        lines = source.splitlines()
        self.assertIn("    say what this listener does.", lines)
        self.assertEqual([line for line in lines if left_in(line)], ["    say what this listener does."])
        self.assertNotIn("host.logger", source)
        self.assertTrue(all(len(line) <= 120 for line in lines))
        self.assertIn("log with host.logger (from ..hermes import host)", " ".join(out["next"]))


class EventBroker(ScaffoldCase):
    def test_the_steps_say_the_broker_never_emits(self):
        said = " ".join(self.new("event", "history", "rdprobe_moved", "--payload", "game=<id>")["next"])
        self.assertIn(
            "the broker process never emits (backend/system/events.py): call it from Hermes-side code (an RPC, tool "
            "or hook) that sees it happen",
            said,
        )
        reference = retrodev_docs("REFERENCE.md")
        self.assertIn("--when 'Setup finished installing the toolchain'", reference)
        self.assertIn("### Changing an event's payload or name", reference)
        self.assertIn("`git mv tests/backend/<feature>/test_event_<old>.py", reference)


class TakeoverAgent(RepoCase):
    def test_the_plan_approve_step_names_the_agent_while_it_is_unset(self):
        self.assertEqual(gates.agent_prefix({}), "RETRODEV_AGENT='<agent, model>' ")
        self.assertEqual(gates.agent_prefix({"RETRODEV_AGENT": "Hermes, a model"}), "")
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        approve = next(step for step in steps(out) if "plan approve" in step)
        self.assertIn(f"when they say start: {gates.agent_prefix()}python tools/retrodev plan approve", approve)
        note = next(part for part in retrodev_docs("README.md").split("\n\n") if part.startswith("`RETRODEV_AGENT="))
        self.assertIn("`takeover`", note)
        self.assertIn("`plan approve`", note)


class BodyCitations(RepoCase):
    def setUp(self):
        super().setUp()
        self.tree = self.worktree("docs/debug")
        self.commit(self.tree, "docs/dev/DEBUGGING.md", "# Debugging\n")
        self.ctx = config.Context.make(self.tree, output.Out(stream=io.StringIO()))

    def warning(self, what: str) -> str:
        return body_names.warning(self.ctx, GOOD_BODY.replace("Things.", what)) or ""

    def test_a_cited_tool_is_quiet_and_a_claimed_change_still_warns(self):
        for said in (
            "- `docs/dev/DEBUGGING.md` documents `tools/debug/gateway_rpc.mjs`.",
            "- A section that describes `tools/debug/gateway_rpc.mjs`.",
            "- The guide explains `tools/debug/gateway_rpc.mjs`.",
            "- Says how to use `tools/debug/gateway_rpc.mjs`.",
            "- Says how to run `tools/debug/gateway_rpc.mjs`.",
        ):
            with self.subTest(said=said):
                self.assertEqual(self.warning(said), "")
        self.assertIn("`tools/x.py`", self.warning("- Changed `tools/x.py`."))
        self.assertIn("`tools/x.py`", self.warning("- Documents the gateway; changed `tools/x.py`."))


class QuickPath(RepoCase):
    def test_start_branches_from_the_fetched_origin_dev(self):
        self.assertIn("it fetches and branches from `origin/dev`", retrodev_docs("README.md"))
