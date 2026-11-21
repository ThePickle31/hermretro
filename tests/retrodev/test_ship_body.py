"""The trial rounds' regressions for this area (Fixes, RoundEight, RoundFive, RoundFour, RoundNine, RoundSeven, RoundSix, RoundTen, RoundTwo), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_ship_body
"""

import io
import re
import shlex
from pathlib import Path
import retrodev
from retrodev import checks, config, gates, output, release_publish, repo, state
from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write
from retrodev.gates import agent_hint
from tests.retrodev.fixture import FILLED_PLAN
from tests.retrodev.fixture import retrodev_docs
from retrodev import ship
from types import SimpleNamespace

load_tests = parallel

ROOT = Path(retrodev.__file__).resolve().parents[2]

APOSTROPHE = "Fix the game's title"

SECTIONS = ["Why", "What changed", "How verified", "Risk and rollback", "Not done"]

NOT_GITHUB = "none of the git remotes configured for this repository point to a known GitHub host"


def line_with(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


TITLE = "Make the goalie work"

LONG = "Show how many builds each game of the library has had, newest first, on the Home page's shelf and in Game"


def titled(topic: str, title: str) -> str:
    return FILLED_PLAN.format(topic=topic).replace("\n\n## Goal", f"\n\nTitle: {title}\n\n## Goal")


def line_with_RoundEight(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundFour(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


def line_with_RoundSeven(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundSix(out: str, start: str) -> str:
    return next((line for line in out.splitlines() if line.startswith(start)), "")


def line_with_RoundTen(text: str, start: str) -> str:
    return next((line for line in text.splitlines() if line.startswith(start)), "")


def line_with_RoundTwo(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


class FlowFixes(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def ready(self, name="docs/tidy"):
        tree = self.worktree(name)
        self.commit(tree, "docs/guide.md", "# Guide, better\n", "Improve the guide")
        self.passed(tree, name)
        return tree, str(write(self.base, "body.md", GOOD_BODY))

    def test_printed_commands_survive_a_quote_in_the_title(self):
        tree, body = self.ready()
        code, data = self.run_cli("ship", "--title", APOSTROPHE, "--body", body, "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        code, out = self.run_cli("ship", "--title", APOSTROPHE, "--body", body, "--dry-run", cwd=tree)
        self.assertEqual(shlex.split(line_with(out, "gh pr")), data["gh"])
        self.assertEqual(shlex.split(line_with(out, "git push")), data["push"])
        record = state.load_branch(self.main, "docs/tidy")
        record.update(
            pr={"number": 5, "url": "u", "title": APOSTROPHE}, pushed="0" * 40, body=str(self.base / "a b.md")
        )
        state.save_branch(self.main, record)
        code, out = self.run_cli("status", cwd=tree)
        words = shlex.split(line_with(out, "next:").removeprefix("next: ").split(" (")[0])
        body_words = ["--title", APOSTROPHE, "--body", str(self.base / "a b.md")]
        self.assertEqual(words[3:], [*body_words, "--dry-run"], out)  # the last ship was a dry run: it stays one
        step = {"run": ["gh", "release", "create", "v1", "--title", "it's"], "env": {"X": "a b"}}
        self.assertEqual(shlex.split(release_publish.shown(step)), ["X=a b", *step["run"]])

    def test_ship_without_a_body_writes_the_skeleton_in_the_main_checkout_and_stops(self):
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        tree = self.worktree("feat/goalie")
        self.commit(tree, "docs/guide.md", "# Goal\n")
        self.passed(tree, "feat/goalie")
        code, out = self.run_cli("ship", "--title", APOSTROPHE, cwd=tree)
        self.assertEqual(code, 1, out)
        path = self.main / "notes" / "pr" / "goalie.md"
        self.assertFalse((tree / "notes").exists(), "never in the worktree: gc would keep it")
        text = path.read_text()
        self.assertIn("## Why\nMake goalie work.\n", text)
        self.assertIn(
            "Made by an agent (Hermes) for the owner.", text
        )  # no GitHub remote: the owner (round ten: agent named)
        fix = line_with(out, "FIX:").strip()  # the body gate's FIX (every gate runs and prints its own)
        self.assertTrue(fix.startswith(f"FIX: fill in {path}, then python tools/retrodev ship --title"), fix)
        self.assertEqual(shlex.split(fix.split(", then ")[1])[-2:], ["--body", str(path)])
        self.assertEqual(self.run_cli("ship", "--title", "T", "--new-body", cwd=tree)[0], 1)
        self.assertEqual(path.read_text(), text, "an existing body is never overwritten")
        path.write_text(GOOD_BODY)  # filled in: --body defaults to it
        code, data = self.run_cli("ship", "--title", "Tidy", "--dry-run", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertIn(str(path), data["gh"])

    def test_the_skeleton_s_attribution_fills_no_section(self):
        # Under the template's last heading the attribution once counted as that section's content.
        self.new_plan("credit")
        self.run_cli("plan", "approve", "credit", "--words", "start")
        tree = self.worktree("feat/credit")
        self.commit(tree, "docs/guide.md", "# Credit\n")
        path = self.main / "notes" / "pr" / "credit.md"
        real = (ROOT / ".github/pull_request_template.md").read_text()  # the real one has a '## Made by'
        made_by = re.search(r"^## Made by[ \t]*\n(?:[ \t]*<!--.*?-->[ \t]*\n)*", real, flags=re.M | re.S)
        self.assertIsNotNone(made_by, "the real template asks who made the change under '## Made by'")
        without = real[: made_by.start()].rstrip("\n") + "\n"  # an older template, with no '## Made by'
        for template in (None, without, real):  # none (the policy's sections), one without '## Made by', the real one
            if template is not None:
                self.commit(tree, ".github/pull_request_template.md", template, "Template")
            self.passed(tree, "feat/credit")
            path.unlink(missing_ok=True)
            self.assertEqual(self.run_cli("ship", "--title", "Credit", cwd=tree)[0], 1)
            text = path.read_text()
            self.assertEqual(text.count("Made by an agent (Hermes) for the owner."), 1, text)
            if template == real:
                # flipped (round seven): the line replaces the template's comment instead of following it
                self.assertIn("## Made by\nMade by an agent (Hermes) for the owner.\n", text)
                self.assertNotIn(made_by.group(0), text)
                self.assertNotIn("\n---\n", text)
            else:
                self.assertTrue(text.endswith("\n---\n\nMade by an agent (Hermes) for the owner.\n"), text)
            text = text.replace("## Not done\nNothing else.\n", "## Not done\n")  # the plan's Not in scope, out again
            filled = re.sub(
                r"^## (Why|What changed|How verified|Risk and rollback)\n", r"\g<0>Filled.\n", text, flags=re.M
            )
            path.write_text(filled)
            code, data = self.run_cli("ship", "--title", "Credit", "--dry-run", cwd=tree, as_json=True)
            self.assertEqual(code, 1, (template, data))
            gate = next(gate for gate in data["gates"] if gate["name"] == "body")
            self.assertEqual(
                gate["message"].split(" (")[0], "section '## Not done' is empty", (template, gate["message"])
            )
            path.write_text(re.sub(r"^## Not done\n", "## Not done\nNothing.\n", filled, flags=re.M))
            code, data = self.run_cli("ship", "--title", "Credit", "--dry-run", cwd=tree, as_json=True)
            self.assertEqual(code, 0, (template, data))
        self.assertIn(
            "section '## Not done' is empty",
            "; ".join(gates.body_problems(GOOD_BODY.replace("Nothing.\n", ""), SECTIONS)),
        )
        self.assertEqual(gates.body_problems(GOOD_BODY, SECTIONS), [])

    def test_no_github_remote_is_a_note_not_gh_s_error(self):
        tree, body = self.ready()
        self.gh.answers[("pr", "list")] = (1, "", NOT_GITHUB)
        self.gh.answers[("pr", "checks")] = (1, "", NOT_GITHUB)
        code, out = self.run_cli("ship", "--title", "Tidy", "--body", body, "--dry-run", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("note: no GitHub remote; the open pull request lookup was skipped", out)
        self.assertNotIn(NOT_GITHUB, out)
        record = state.load_branch(self.main, "docs/tidy")
        record["pr"] = {"number": 5, "url": "u"}
        state.save_branch(self.main, record)
        for command in ("status", "report"):
            code, out = self.run_cli(command, cwd=tree)
            self.assertIn("note: no GitHub remote", out, command)
            self.assertNotIn(NOT_GITHUB, out, command)

    def test_a_branch_that_changes_no_file_is_refused(self):  # review 1, 3
        tree, body = self.ready()
        git(tree, "revert", "--no-edit", "HEAD")
        self.passed(tree, "docs/tidy")

        def refused(where: str) -> None:
            code, data = self.run_cli("ship", "--title", "Tidy", "--body", body, "--dry-run", cwd=tree, as_json=True)
            self.assertEqual(code, 1, (where, data))
            gate = next(gate for gate in data["gates"] if gate["name"] == "has commits")
            self.assertIn("nothing to ship: the branch changes no file", gate["message"], where)
            self.assertIn("no change since it left", gate["message"], where)

        refused("before dev moved")
        self.on_dev("docs/unrelated.md", "# Unrelated\n")  # the tip now differs from the merge base
        git(tree, "fetch", "-q", "origin")  # a dry-run ship itself does not fetch: the cached ref moves here
        refused("after dev moved")


class TitleAndBody(RepoCase):
    def test_check_names_a_missing_body_and_check_status_and_ship_suggest_the_plan_s_title(self):
        tree = self.worktree("fix/nobody")
        path = self.main / "notes/plans/nobody.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            FILLED_PLAN.format(topic="nobody").replace("\n\n## Goal", "\n\nTitle: Nobody gets a body\n\n## Goal")
        )
        body = self.main / "notes/pr/nobody.md"
        self.run_cli("plan", "approve", "nobody", "--words", "start")
        body.unlink(missing_ok=True)  # start writes it; a branch made by hand has none
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            out.strip().splitlines()[-1],
            f"next: fill in the pull request body (missing: {body}; ship writes it from the template), then python "
            "tools/retrodev ship --title 'Nobody gets a body'" + agent_hint(None),
        )
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("ship --title 'Nobody gets a body'", out)
        _code, out = self.run_cli("ship", "--dry-run", cwd=tree)
        self.assertIn("--title 'Nobody gets a body'", out)


class Status(RepoCase):
    def test_ship_without_a_title_still_runs_and_reports_every_gate(self):
        tree = self.worktree("feat/goalie")
        write(tree, "docs/loose.md", "# uncommitted\n")
        code, out = self.run_cli("ship", cwd=tree)
        self.assertEqual(code, 3, out)  # the plan gate needs the owner: the strictest code among the refusals
        refused = [line.strip().split(":")[0] for line in out.splitlines() if line.strip().startswith("NO  ")]
        for gate in ("NO  title", "NO  body"):
            self.assertIn(gate, refused, out)
        self.assertGreaterEqual(len(refused), 4, out)  # the plan, the commit and the checks too
        self.assertIn("FIX: python tools/retrodev ship --title", out)


class Ship(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def feat(self, topic="goalie"):
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        tree = self.worktree(f"feat/{topic}")
        record = state.load_branch(self.main, f"feat/{topic}")
        state.save_branch(self.main, {**record, "plan": topic})
        self.commit(tree, "docs/guide.md", f"# {topic}\n")
        self.passed(tree, f"feat/{topic}")
        return tree

    def test_a_dry_run_s_body_fix_and_status_keep_dry_run(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY.replace("Because.", ""))
        code, out = self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertTrue(
            line_with_RoundFour(out, "FIX: fill in").endswith(" --dry-run"), line_with_RoundFour(out, "FIX: fill in")
        )
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn(" --dry-run (fill in every section", line_with_RoundFour(out, "next:"))
        body.write_text(GOOD_BODY)
        self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn(" --dry-run (ship --dry-run passed at ", line_with_RoundFour(out, "next:"))
        self.assertIn("without --dry-run the same command pushes", line_with_RoundFour(out, "next:"))

    def test_after_a_real_ship_status_names_a_real_ship(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY.replace("Because.", ""))
        self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        code, out = self.run_cli("ship", "--title", TITLE, "--body", str(body), cwd=tree)  # the body gate stops it
        self.assertEqual(code, 1, out)
        self.assertFalse(line_with_RoundFour(out, "FIX: fill in").endswith("--dry-run"))
        _code, out = self.run_cli("status", cwd=tree)
        self.assertNotIn("--dry-run", line_with_RoundFour(out, "next:"))

    def test_a_dry_run_after_the_pull_request_stays_a_dry_run_in_status(self):  # review round 1, finding 0
        tree = self.feat()
        body = write(self.base, "custom.md", GOOD_BODY)
        self.gh.answers[("pr", "create")] = (0, "https://github.com/o/r/pull/7\n", "")
        code, out = self.run_cli("ship", "--title", TITLE, "--body", str(body), cwd=tree)
        self.assertEqual(code, 0, out)
        self.commit(tree, "docs/guide.md", "# goalie, again\n")
        self.passed(tree, "feat/goalie")
        self.gh.answers[("pr", "list")] = (0, '[{"number": 7, "url": "u", "baseRefName": "dev"}]', "")
        self.gh.answers[("pr", "edit")] = (0, "", "")
        code, out = self.run_cli("ship", "--dry-run", cwd=tree)
        self.assertEqual(code, 0, out)
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn(" --dry-run", line_with_RoundFour(out, "next:"))
        self.assertIn("the last ship was a dry run", line_with_RoundFour(out, "next:"))
        self.run_cli("ship", cwd=tree)  # a real ship: status names a real one again
        self.commit(tree, "docs/guide.md", "# goalie, once more\n")
        self.passed(tree, "feat/goalie")
        _code, out = self.run_cli("status", cwd=tree)
        self.assertNotIn("--dry-run", line_with_RoundFour(out, "next:"))

    def test_a_first_dry_run_without_a_title_keeps_dry_run_in_its_fix_and_in_status(self):  # review round 2, 0
        tree = self.feat()
        plan = self.main / "notes" / "plans" / "goalie.md"
        plan.write_text(plan.read_text().replace("# Plan: goalie", "# Plan: Keep the goalie in goal"))
        write(self.main, "notes/pr/goalie.md", GOOD_BODY)  # the default body, filled in already
        code, out = self.run_cli("ship", "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("FIX: python tools/retrodev ship --title 'Keep the goalie in goal' --dry-run", out)
        _code, out = self.run_cli("status", cwd=tree)
        self.assertTrue(
            line_with_RoundFour(out, "next:").split(" (")[0].endswith(" --dry-run"), line_with_RoundFour(out, "next:")
        )
        self.assertEqual(self.gh.calls, [])
        self.assertIsNone(git(self.origin, "rev-parse", "-q", "--verify", "feat/goalie", check=False).strip() or None)


class Title(RepoCase):
    def test_check_status_and_ship_say_why_they_skip_the_plan_s_title(self):
        tree = self.worktree("feat/longer")
        path = self.main / "notes/plans/longer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(titled("longer", "Show every build"))
        self.assertEqual(self.run_cli("plan", "approve", "longer", "--words", "start")[0], 0)
        path.write_text(titled("longer", LONG))  # edited after the approval
        self.commit(tree, "docs/guide.md", "# longer\n")
        why = "the plan's title is 105 characters; the limit is 100"
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn(why, out.strip().splitlines()[-1])
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn(why, out)
        code, out = self.run_cli("ship", "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn(why, out)


class MadeBy(RepoCase):
    def test_start_and_check_say_how_to_name_the_agent(self):
        self.commit(
            self.main, ".github/pull_request_template.md", (ROOT / ".github/pull_request_template.md").read_text()
        )
        git(self.main, "push", "-q", "origin", "dev")
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        code, out = self.run_cli("start", "feat/goalie", "--no-setup")
        self.assertEqual(code, 0, out)
        self.assertIn("RETRODEV_AGENT='<agent, model>'", out)
        tree = self.base / "hermretro-wt" / "goalie"
        self.commit(tree, "docs/guide.md", "# goalie\n")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("RETRODEV_AGENT='<agent, model>'", out.strip().splitlines()[-1])
        body = self.main / "notes/pr/goalie.md"
        body.write_text(
            body.read_text().replace("Made by an agent (Hermes) for the owner.", "Made by an agent (Codex) for x.")
        )
        _code, out = self.run_cli("check", cwd=tree)
        self.assertNotIn("RETRODEV_AGENT", out.strip().splitlines()[-1], "a named agent needs no hint")


class Body(RepoCase):
    def started(self) -> Path:
        self.commit(
            self.main, ".github/pull_request_template.md", (ROOT / ".github/pull_request_template.md").read_text()
        )
        git(self.main, "push", "-q", "origin", "dev")
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        code, out = self.run_cli("start", "feat/goalie")
        self.assertEqual(code, 0, out)
        return self.base / "hermretro-wt" / "goalie"

    def test_the_made_by_line_replaces_the_template_s_comment_and_names_no_owner_without_github(self):
        self.started()
        body = (self.main / "notes/pr/goalie.md").read_text()
        self.assertTrue(body.endswith("## Made by\nMade by an agent (Hermes) for the owner.\n"), body)
        self.assertNotIn("A person: your name", body)
        github = SimpleNamespace(remote="gh", top=self.main)
        git(self.main, "remote", "add", "gh", "git@github.com:someone/hermretro.git")
        self.assertEqual(ship.made_by(github), "Made by an agent (Hermes) for @someone.")
        readme = retrodev_docs()
        self.assertIn("`Made by an agent (Hermes) for the owner.`", readme)
        self.assertIn("add the model, and name your agent if it is not Hermes", readme)

    def test_check_names_the_sections_still_to_fill_in(self):
        tree = self.started()
        self.commit(tree, "docs/guide.md", "# goalie\n")
        path = self.main / "notes/pr/goalie.md"
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            out.strip().splitlines()[-1],
            f"next: fill in How verified, Risk and rollback in {path}, then python tools/retrodev ship --title "
            "'<one plain sentence>'" + agent_hint(None),
        )
        path.write_text(path.read_text().replace("## Risk and rollback\n", "## Risk and rollback\nLow.\n"))
        _code, out = self.run_cli("check", cwd=tree)
        self.assertTrue(out.strip().splitlines()[-1].startswith(f"next: fill in How verified in {path}, then"), out)


class BodyRoundSix(RepoCase):
    def started(self, topic: str = "goalie") -> Path:
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        code, out = self.run_cli("start", f"feat/{topic}")
        self.assertEqual(code, 0, out)
        return self.base / "hermretro-wt" / topic

    def test_the_first_dry_run_checks_that_body_and_still_refuses_what_the_plan_did_not_fill(self):
        tree = self.started()
        self.commit(tree, "docs/guide.md", "# goalie\n")
        self.run_cli("check", cwd=tree)
        code, out = self.run_cli("ship", "--title", "Keep the goalie in goal", "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        refused = line_with_RoundSix(out, "  NO  body")
        self.assertIn("'## How verified' is empty", refused)
        self.assertIn("'## Risk and rollback' is empty", refused)
        self.assertNotIn("'## What changed' is empty", refused)
        self.assertNotIn("written now", refused, "the body was there before the first ship")
        self.assertNotIn("wrote ", out)

    def test_check_after_a_refused_dry_run_keeps_the_dry_run_in_its_ship(self):
        tree = self.started()
        self.commit(tree, "docs/guide.md", "# goalie\n")
        code, out = self.run_cli("ship", "--title", "Keep the goalie in goal", "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        path = self.main / "notes" / "pr" / "goalie.md"
        self.assertEqual(
            out.strip().splitlines()[-1],
            f"next: fill in How verified, Risk and rollback in {path}, then python tools/retrodev ship --title 'Keep the "
            "goalie in goal' --dry-run" + agent_hint(None),
        )


class MadeByRoundTen(RepoCase):
    def test_the_written_line_names_the_agent_and_agrees_with_the_hint(self):
        self.commit(
            self.main, ".github/pull_request_template.md", (ROOT / ".github/pull_request_template.md").read_text()
        )
        git(self.main, "push", "-q", "origin", "dev")
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        code, out = self.run_cli("start", "feat/goalie", "--no-setup")
        self.assertEqual(code, 0, out)
        body = (self.main / "notes/pr/goalie.md").read_text()
        self.assertTrue(body.endswith("## Made by\nMade by an agent (Hermes) for the owner.\n"), body)
        self.assertIn("names no agent but Hermes", out)  # the hint says what the line says
        ctx = SimpleNamespace(remote="origin", top=self.main)  # no GitHub remote
        named = gates.made_by(ctx, env={"RETRODEV_AGENT": "Hermes, claude-opus-5-5"})
        self.assertEqual(named, "Made by an agent (Hermes, claude-opus-5-5) for the owner.")
        filled = GOOD_BODY.replace("Made by an agent (Hermes) for the owner.", named)
        self.assertEqual(gates.body_problems(filled, ["Why", "What changed", "How verified", "Not done"]), [])
        self.assertEqual(gates.agent_hint(filled, env={}), "")
        self.assertEqual(gates.agent_hint(None, env={"RETRODEV_AGENT": "Codex"}), "")
        older = gates.agent_hint("Made by an agent for the owner.", env={})  # a body an older retrodev wrote
        self.assertIn("names no agent:", older)


class Flow(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def feat(self, topic="goalie"):
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        tree = self.worktree(f"feat/{topic}")
        record = state.load_branch(self.main, f"feat/{topic}")
        state.save_branch(self.main, {**record, "plan": topic})
        self.commit(tree, "docs/guide.md", f"# {topic}\n")
        self.passed(tree, f"feat/{topic}")
        return tree

    def test_a_dry_run_writes_the_skeleton_and_its_fix_names_the_real_title(self):
        tree = self.feat()
        code, out = self.run_cli("ship", "--title", TITLE, "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        path = self.main / "notes" / "pr" / "goalie.md"
        self.assertIn("## Why\nMake goalie work.\n", path.read_text(), "the plan's Goal is the Why")
        self.assertIn(f"NO  body: fill in {path}", out)
        fix = line_with_RoundTwo(out, "FIX: fill in")
        self.assertNotIn("--title ...", out)
        self.assertEqual(
            shlex.split(fix.split(", then ")[1]),
            [*["python", "tools/retrodev", "ship"], "--title", TITLE, "--body", str(path), "--dry-run"],  # still one
        )
        self.assertIsNone(git(self.origin, "rev-parse", "-q", "--verify", "feat/goalie", check=False).strip() or None)

    def test_without_a_plan_the_why_is_a_visible_placeholder(self):
        tree = self.worktree("docs/tidy")  # --no-plan: the record names no plan
        self.commit(tree, "docs/guide.md", "# Tidier\n")
        self.passed(tree, "docs/tidy")
        code, out = self.run_cli("ship", "--title", "Tidy the guide", "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        text = (self.main / "notes" / "pr" / "tidy.md").read_text()
        self.assertIn("## Why\n<!-- no plan: say why -->\n", text)
        self.assertNotIn("the plan's Goal is its Why", out)
        self.assertIn("no plan Goal: write the Why", out)

    def test_the_first_real_ship_records_the_title_before_it_stops_and_reads_a_goals_heading(self):
        tree = self.feat("keeper")
        plan = self.main / "notes" / "plans" / "keeper.md"
        plan.write_text(plan.read_text().replace("## Goal\n", "## Goals\n"))
        code, out = self.run_cli("ship", "--title", TITLE, cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("## Why\nMake keeper work.\n", (self.main / "notes" / "pr" / "keeper.md").read_text())
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn(f"--title '{TITLE}' --body", line_with_RoundTwo(out, "next:"), "the title given, not the plan's")

    def test_a_bare_ship_uses_the_recorded_title_and_body_and_refuses_with_neither(self):
        tree = self.feat()
        code, out = self.run_cli("ship", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("FIX: python tools/retrodev ship --title", out)
        self.assertEqual(self.gh.calls, [])
        plan = self.main / "notes" / "plans" / "goalie.md"
        plan.write_text(plan.read_text().replace("# Plan: goalie", "# Plan: Keep the goalie in goal"))
        _code, out = self.run_cli("ship", cwd=tree)
        self.assertIn("FIX: python tools/retrodev ship --title 'Keep the goalie in goal'", out, "the plan's title")
        body = write(self.base, "custom.md", GOOD_BODY)
        self.gh.answers[("pr", "create")] = (0, "https://github.com/o/r/pull/7\n", "")
        code, out = self.run_cli("ship", "--title", TITLE, "--body", str(body), cwd=tree)
        self.assertEqual(code, 0, out)
        self.commit(tree, "docs/guide.md", "# goalie, again\n")
        self.passed(tree, "feat/goalie")
        self.gh.answers[("pr", "list")] = (0, '[{"number": 7, "url": "u", "baseRefName": "dev"}]', "")
        self.gh.answers[("pr", "edit")] = (0, "", "")
        code, out = self.run_cli("ship", cwd=tree)
        self.assertEqual(code, 0, out)
        edit = self.gh.called("pr", "edit")[0]
        self.assertEqual(edit[edit.index("--title") + 1], TITLE)
        self.assertEqual(edit[edit.index("--body-file") + 1], str(body))

    def test_github_community_files_are_documentation_not_ci(self):
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()))
        for name in ("CONTRIBUTING", "SECURITY", "CODE_OF_CONDUCT"):
            self.assertEqual(ship.labels(ctx, [f".github/{name}.md"]), ["documentation"], name)
        self.assertEqual(ship.labels(ctx, [".github/workflows/ci.yml"]), ["ci"])
        self.assertEqual(ship.labels(ctx, [".github/actions/hermes/action.yml"]), ["ci"])
