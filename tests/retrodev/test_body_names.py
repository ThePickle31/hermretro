"""The trial rounds' regressions for this area (RoundEighteen, RoundEleven, RoundFifteen, RoundFourteen, RoundSeventeen, RoundSixteen, RoundThirteen, RoundTwelve, RoundTwenty), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_body_names
"""

import io
import unittest
from pathlib import Path
from retrodev import body_names, config, output
from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write
from tests.retrodev.fixture import retrodev_docs

load_tests = parallel

README = """# {Label}

**Shows:** the page.

**Tabs:** none.

**Slots:** declares none, contributes none.

**Tests:** `tests/page/page-{page}.test.mjs`.

## Adding a tab here

Make a folder `page/pages/{page}/<tab>/`{taken} with an `index.js` exporting `{{ id, label, Page }}`.
"""


class SyncedTakeoverBodyRoundEighteen(RepoCase):
    def warning(self, tree, what: str) -> str:
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        return body_names.warning(ctx, GOOD_BODY.replace("Things.", what)) or ""

    def test_no_warning_for_what_dev_moved_once_synced_and_still_one_without_a_sync(self):
        self.on_dev("tools/old_helpers.py", "def rdprobe_helper():\n    return 1\n", "A helper")
        git(self.main, "fetch", "-q", "origin")
        synced, plain = self.worktree("fix/taken"), self.worktree("fix/plain")
        for tree in (synced, plain):
            self.commit(tree, "tools/kept.py", "VALUE = 1\n")
        other = self.base / "other"
        git(other, "rm", "-q", "tools/old_helpers.py")
        write(other, "tools/new_helpers.py", "def rdprobe_renamed():\n    return 1\n")
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "Dev moves the helper")
        git(other, "push", "-q", "origin", "dev")
        git(synced, "fetch", "-q", "origin")
        git(synced, "merge", "-q", "--no-edit", "origin/dev")
        said = "- Explained why `tools/old_helpers.py`'s `rdprobe_helper` went away."
        self.assertEqual(self.warning(synced, said), "")
        git(plain, "fetch", "-q", "origin")
        away = self.warning(plain, said)
        self.assertIn("`tools/old_helpers.py`", away)  # its tree still has the helper itself


class BodyNamesRoundEleven(RepoCase):
    def ready(self, said: str) -> Path:
        tree = self.worktree("docs/tidy")
        self.commit(tree, "backend/library/games.py", "def built_rom(root):\n    return root / 'build.gb'\n", "Rom")
        write(self.main, "notes/pr/tidy.md", GOOD_BODY.replace("Things.", said))
        return tree

    def test_ship_warns_about_a_name_the_code_does_not_have(self):
        tree = self.ready("Adds `games.rom_path` (the built ROM) and `new event`.")
        code, out = self.run_cli("ship", "--title", "Tidy", "--dry-run", cwd=tree, as_json=True)
        self.assertIn("body_warning", out, out)
        self.assertIn("`games.rom_path`", out["body_warning"])
        self.assertIn("appear(s) nowhere in the branch's diff or tree", out["body_warning"])
        self.assertNotIn("new event", out["body_warning"])  # a quoted command, not an identifier
        failed = [gate["name"] for gate in out.get("gates", []) if not gate["ok"]]
        self.assertNotIn("body", failed)  # a warning, never a gate
        del code

    def test_a_name_the_branch_has_warns_nothing(self):
        tree = self.ready("Adds `games.built_rom` (the built ROM).")
        _code, out = self.run_cli("ship", "--title", "Tidy", "--dry-run", cwd=tree, as_json=True)
        self.assertNotIn("body_warning", out)

    def test_check_s_last_line_warns_too(self):
        tree = self.ready("Adds `games.rom_path` (the built ROM).")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("`games.rom_path`", out.rstrip().splitlines()[-1])

    def test_only_code_like_names_count(self):
        body = GOOD_BODY.replace("Things.", "`dev`, `new event`, `rom_path`, `useQuery`, `a.b()`, `x/y.py`")
        self.assertEqual(body_names.quoted_identifiers(body), ["rom_path", "useQuery", "a.b()"])
        self.assertIn("warns, never fails", retrodev_docs("REFERENCE.md"))


class BodyCitationsRoundFifteen(RepoCase):
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
        self.commit(self.tree, "tools/kept.py", "VALUE = 1\n")  # round 17: a docs-only branch never warns on code
        self.assertIn("`tools/x.py`", self.warning("- Changed `tools/x.py`."))
        self.assertIn("`tools/x.py`", self.warning("- Documents the gateway; changed `tools/x.py`."))


class BodyBareNamesRoundFourteen(RepoCase):
    def warning(self, what: str) -> str:
        tree = self.worktree("fix/core")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n")
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        return body_names.warning(ctx, GOOD_BODY.replace("Things.", what)) or ""

    def test_bare_names_and_runtime_data_files_are_quiet_and_a_stale_repository_path_still_warns(self):
        said = self.warning(
            "- Changed `backend/library/core.py`; `tools.py` and `glue.py` call it unchanged.\n"
            "- The library reads `games.json` and `library.toml` at run time.\n"
            "- Moved the check into `backend/x/y.py`."
        )
        self.assertNotIn("`tools.py`", said)
        self.assertNotIn("`games.json`", said)
        self.assertNotIn("`library.toml`", said)
        self.assertIn("names the file(s) `backend/x/y.py`, which the", said)

    def test_only_paths_under_the_repository_s_top_folders_count(self):
        self.assertTrue(body_names.is_repo_path("backend/x/y.py"))
        self.assertTrue(body_names.is_repo_path(".github/workflows/ci.yml"))
        self.assertTrue(body_names.is_repo_path("desktop/plugin.js"))  # review 3, 0
        for word in ("games.json", "tools.py", "foo/bar.py", "/abs/path.py", "engine-ish"):
            with self.subTest(word=word):
                self.assertFalse(body_names.is_repo_path(word))

    def test_a_claim_about_an_untouched_bundle_warns_and_a_changed_one_does_not(self):  # review 3, 0
        tree = self.worktree("fix/bundle")
        self.commit(tree, "desktop/plugin.js", "// rebuilt\n")
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        quiet = (
            body_names.warning(ctx, GOOD_BODY.replace("Things.", "- Rebuilt `desktop/plugin.js`; `plugin.js` too."))
            or ""
        )
        self.assertEqual(quiet, "")
        said = body_names.warning(ctx, GOOD_BODY.replace("Things.", "- Rebuilt `desktop/other.js`.")) or ""
        self.assertIn("names the file(s) `desktop/other.js`, which the", said)


class DocsOnlyBodyRoundSeventeen(RepoCase):
    def warning(self, tree, what: str) -> str:
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        return body_names.warning(ctx, GOOD_BODY.replace("Things.", what)) or ""

    def test_a_docs_branch_describes_code_without_a_warning_and_others_still_warn(self):
        said = "- Explained how `tools/retrodev/sync.py` hints and where `backend/library/` keeps games."
        docs = self.worktree("docs/guide")
        self.commit(docs, "docs/dev/DEBUGGING.md", "# Debugging\n")
        self.commit(docs, "backend/library/README.md", "# Library\n")
        self.assertEqual(self.warning(docs, said), "")
        self.assertIn("`docs/dev/TESTING.md`", self.warning(docs, said + " Changed `docs/dev/TESTING.md`."))
        reference = self.worktree("docs/reference")  # review 3, 1: the CLI's own reference is documentation too
        self.commit(reference, "tools/retrodev/REFERENCE.md", "# Reference\n")
        self.assertEqual(self.warning(reference, said), "")
        code = self.worktree("fix/code")
        self.commit(code, "docs/dev/DEBUGGING.md", "# Debugging\n")
        self.commit(code, "tools/kept.py", "VALUE = 1\n")
        self.assertIn("`tools/retrodev/sync.py`", self.warning(code, said))


class BodyDroppedInMergeRoundSixteen(RepoCase):
    def test_a_file_the_branch_s_own_commit_changed_is_quiet_after_a_merge_dropped_it(self):
        tree = self.worktree("fix/notes")
        self.commit(tree, "docs/dev/DEBUGGING.md", "# Debugging\n\nThe same words.\n")
        self.commit(tree, "tools/kept.py", "VALUE = 1\n")
        self.on_dev("docs/dev/DEBUGGING.md", "# Debugging\n\nThe same words.\n", "dev wrote it the same")
        git(tree, "fetch", "-q", "origin")
        git(tree, "merge", "-q", "--no-edit", "origin/dev")
        self.assertNotIn("docs/dev/DEBUGGING.md", git(tree, "diff", "--name-only", "origin/dev...HEAD"))
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        body = GOOD_BODY.replace("Things.", "- Changed `docs/dev/DEBUGGING.md` and `tools/kept.py`.")
        self.assertIsNone(body_names.warning(ctx, body))
        never = GOOD_BODY.replace("Things.", "- Changed `tools/never.py`.")
        self.assertIn("`tools/never.py`", body_names.warning(ctx, never) or "")

    def test_a_rename_dev_also_made_counts_its_old_path_too(self):
        self.on_dev("tools/old_name.py", "VALUE = 1\n", "The file")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/rename")
        git(tree, "mv", "tools/old_name.py", "tools/new_name.py")
        git(tree, "commit", "-q", "-m", "Rename")
        other = self.base / "other"
        git(other, "pull", "-q", "origin", "dev")
        git(other, "mv", "tools/old_name.py", "tools/new_name.py")
        git(other, "commit", "-q", "-m", "dev renames it the same")
        git(other, "push", "-q", "origin", "dev")
        git(tree, "fetch", "-q", "origin")
        git(tree, "merge", "-q", "--no-edit", "origin/dev")
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        body = GOOD_BODY.replace("Things.", "- Renamed `tools/old_name.py` to `tools/new_name.py`.")
        self.assertIsNone(body_names.warning(ctx, body))


class BodyCitedPathsRoundThirteen(RepoCase):
    def warning(self, what: str) -> str:
        if not hasattr(self, "tree"):
            self.tree = self.worktree("fix/core")
            self.commit(self.tree, "backend/library/core.py", "VALUE = 2\n")
        tree = self.tree
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        return body_names.warning(ctx, GOOD_BODY.replace("Things.", what)) or ""

    def test_paths_cited_as_evidence_or_under_engine_do_not_warn(self):
        said = self.warning(
            "- `backend/library/core.py` keeps the value, checked against `backend/hermes/glue.py` and verified in "
            "`tests/backend/library/test_core.py`.\n"
            "- The value comes from `backend/library/names.py` (source: `docs/dev/CONTRACT.md`).\n"
            "- Changed the value to match `engine/modretro-chromatic/tools.json`."
        )
        self.assertEqual(said, "")

    def test_paths_a_sentence_claims_a_change_to_still_warn_and_say_to_ignore_a_cited_one(self):
        said = self.warning(
            "- Added `backend/library/extra.py` for the value.\n"
            "- `backend/hermes/glue.py`: takes the new value.\n"
            "- Things around `backend/library/core.py`."
        )
        self.assertIn("names the file(s) `backend/library/extra.py`, `backend/hermes/glue.py`, which the", said)
        self.assertIn("ignore if the file is only cited", said)

    def test_a_change_from_an_untouched_file_still_warns_and_a_source_it_comes_from_does_not(self):
        for claim in (
            "- Removed the obsolete helper from `backend/hermes/glue.py`.",
            "- Moved the parser from `backend/hermes/glue.py` to `backend/library/core.py`.",
            "- Deleted the old copy from `backend/hermes/glue.py`.",
        ):
            with self.subTest(claim=claim):
                self.assertIn("names the file(s) `backend/hermes/glue.py`, which the", self.warning(claim))
        quiet = (
            "- Changed `backend/library/core.py`: the numbers come from `backend/hermes/glue.py`, taken from "
            "`backend/library/names.py`, read from `docs/dev/CONTRACT.md` and copied from `tools/layout.toml`."
        )
        self.assertEqual(self.warning(quiet), "")

    def test_any_verb_claims_an_untouched_file(self):  # review 2, 0
        for claim in (
            "- Fixed the crash in `backend/hermes/glue.py`.",
            "- Updated `backend/hermes/glue.py` for the value.",
            "- `backend/library/core.py` keeps the value; tidied `backend/hermes/glue.py`.",
        ):
            with self.subTest(claim=claim):
                self.assertIn("names the file(s) `backend/hermes/glue.py`, which the", self.warning(claim))

    def test_a_citation_clause_holds_its_whole_list_until_a_new_change_clause(self):  # review 2, 1
        quiet = (
            "- Changed `backend/library/core.py`, checked against `backend/hermes/glue.py` and "
            "`tests/backend/library/test_core.py`.\n"
            "- Changed `backend/library/core.py`, based on `backend/hermes/glue.py`, `tools/layout.toml` and "
            "`docs/dev/CONTRACT.md` (cited by `backend/library/names.py`)."
        )
        self.assertEqual(self.warning(quiet), "")
        for claim in (
            "- Changed `backend/library/core.py`, checked against `tools/layout.toml`; removed X from "
            "`backend/hermes/glue.py`.",
            "- Checked against `tools/layout.toml` and removed X from `backend/hermes/glue.py`.",
        ):
            with self.subTest(claim=claim):
                said = self.warning(claim)
                self.assertIn("names the file(s) `backend/hermes/glue.py`, which the", said)
                self.assertNotIn("`tools/layout.toml`", said)

    def test_a_hyphenated_modifier_is_no_citation(self):  # review 3, 0
        for claim in (
            "- Fixed per-game handling in `backend/hermes/glue.py`.",
            "- Made a see-through overlay in `backend/hermes/glue.py`.",
        ):
            with self.subTest(claim=claim):
                self.assertIn("names the file(s) `backend/hermes/glue.py`, which the", self.warning(claim))
        self.assertEqual(self.warning("- Changed `backend/library/core.py`, per `backend/hermes/glue.py`."), "")


class BodyPathsRoundTwelve(RepoCase):
    def test_what_changed_naming_a_file_the_branch_did_not_touch_warns(self):
        tree = self.worktree("fix/core")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n")
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        text = GOOD_BODY.replace(
            "Things.", "`backend/library/core.py` and `core.py` change; `backend/hermes/glue.py` and `ship.py` too."
        )
        said = body_names.warning(ctx, text) or ""
        # a bare name (`ship.py`) is no repository path the diff can check (round 14)
        self.assertIn("names the file(s) `backend/hermes/glue.py`, which the branch's diff does not", said)
        self.assertNotIn("`backend/library/core.py`", said)
        self.assertNotIn("`core.py`", said)
        self.assertIsNone(body_names.warning(ctx, GOOD_BODY.replace("Things.", "`backend/library/` changes.")))

    def test_a_renamed_file_counts_at_both_its_paths(self):  # review 1, 1
        self.on_dev("backend/library/old.py", "VALUE = 1\n" * 20)
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/rename")
        git(tree, "mv", "backend/library/old.py", "backend/library/new.py")
        git(tree, "commit", "-q", "-m", "Rename")
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        text = GOOD_BODY.replace("Things.", "Renamed `backend/library/old.py` to `backend/library/new.py`.")
        self.assertIsNone(body_names.warning(ctx, text))


class BodyCitationsRoundTwenty(unittest.TestCase):
    def test_a_path_the_body_calls_unchanged_is_cited_not_claimed(self):
        cases = {
            "The guide `docs/dev/TESTING.md` is unchanged.": [],
            "Left `docs/dev/TESTING.md` untouched; fixed `tools/retrodev/sync.py`.": ["tools/retrodev/sync.py"],
            "No change to `docs/dev/TESTING.md`.": [],
            "`docs/a.md`, `docs/b.md` and `docs/c.md` are unchanged.": [],
            "Fixed `tools/a.py`, `docs/b.md` unchanged.": ["tools/a.py"],  # only the name the words follow
            "Fixed `tools/a.py` so the API stays unchanged.": ["tools/a.py"],  # not next to it
            "Changed `tools/a.py`.": ["tools/a.py"],
        }
        for sentence, claimed in cases.items():
            self.assertEqual(body_names.claimed(sentence), claimed, sentence)
