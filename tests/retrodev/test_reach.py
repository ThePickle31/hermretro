"""try (a pull request's full checks in a throwaway checkout), mac (a fake ssh) and preview (a fake build).

Run alone: python -m unittest tests.retrodev.test_reach
"""

import io
import re
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from retrodev import config, mac, output, preview, trial

from tests.retrodev.fixture import RepoCase, git, parallel, write

load_tests = parallel


class Try(RepoCase):
    def setUp(self):
        super().setUp()
        self.fakes["tmp_root"] = self.base
        self.baseline = git(self.main, "rev-parse", "HEAD").strip()
        git(self.main, "tag", "v0.0.1", self.baseline)
        git(self.main, "push", "-q", "origin", "HEAD:refs/heads/main", "refs/tags/v0.0.1")
        self.tree = self.worktree("feat/thing")
        self.commit(self.tree, "backend/library/core.py", "VALUE = 2\n", "Change the value")
        git(self.tree, "push", "-q", "origin", "HEAD:refs/pull/7/head")  # what GitHub keeps for pull request 7
        self.head = git(self.tree, "rev-parse", "HEAD").strip()

    def worktrees(self) -> list[str]:
        return [
            line
            for line in git(self.main, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
        ]

    def test_try_runs_the_full_checks_in_a_throwaway_checkout_and_removes_it(self):
        before = self.worktrees()
        code, data = self.run_cli("try", "7", as_json=True)
        self.assertEqual(code, 0, data)
        assert isinstance(data, dict)
        self.assertEqual(data["head"], self.head)
        self.assertTrue(data["path"].startswith(str(self.base / "rd-try7-")), "outside the repository, short")
        names = [entry.get("names") or entry.get("script") for entry in self.check_log()]
        self.assertIn(["lint"], names)  # --full: lint first, then scaffold beside the others
        self.assertIn(["bundle", "page", "scaffold", "scan", "unit"], [sorted(entry) for entry in names])
        self.assertIn(["acceptance"], names)
        scaffold = [entry.get("mode") for entry in self.check_log() if "scaffold" in entry.get("names", [])]
        self.assertEqual(scaffold, ["nested"], "try runs scaffold nested, whatever the pull request changed")
        installs = [(e["script"], e["head"]) for e in self.check_log() if "script" in e]
        self.assertEqual(installs, [([], self.head), (["--update-from", self.baseline], self.head)])
        self.assertEqual([row["name"] for row in data["checks"]], list(trial.REQUIRED))
        self.assertEqual(list(self.base.glob("rd-try7-*")), [])
        self.assertEqual(self.worktrees(), before)

    def test_a_pr_cannot_drop_a_required_check_from_its_policy(self):
        policy = "tools/retrodev/policy.toml"
        before = (self.tree / policy).read_text()
        body = re.sub(r"(?m)^clean_install = \[.*\]\n", "", before, count=1)
        self.assertNotEqual(before, body)
        self.commit(self.tree, policy, body, "Drop the clean install inputs")
        git(self.tree, "push", "-q", "origin", "HEAD:refs/pull/8/head")
        code, data = self.run_cli("try", "8", "--no-setup", as_json=True)
        self.assertEqual(code, 1, data)
        assert isinstance(data, dict)
        self.assertIn("unverified: required check configuration is missing: clean_install", data["error"]["message"])
        self.assertEqual(self.check_log(), [])

    def test_a_stale_clone_cannot_test_against_an_old_release(self):
        other = self.base / "publisher"
        git(self.base, "clone", "-q", "-b", "main", str(self.origin), str(other))
        self.commit(other, "docs/guide.md", "# New release\n")
        newer = git(other, "rev-parse", "HEAD").strip()
        git(other, "tag", "v0.0.2", newer)
        git(other, "push", "-q", "origin", "main", "refs/tags/v0.0.2", "HEAD:refs/pull/8/head")
        self.assertEqual(git(self.main, "rev-parse", "origin/main").strip(), self.baseline)
        self.assertEqual(git(self.main, "tag", "--list", "v0.0.2").strip(), "")
        code, data = self.run_cli("try", "7", "--no-setup", as_json=True)
        self.assertEqual(code, 1, data)
        assert isinstance(data, dict)
        self.assertIn("unverified: latest release v0.0.2 is not an ancestor of PR head", data["error"]["message"])
        self.assertIn("sync and push", data["error"]["fix"])
        self.assertEqual(self.check_log(), [])
        code, data = self.run_cli("try", "8", "--no-setup", as_json=True)
        self.assertEqual(code, 0, data)
        assert isinstance(data, dict)
        self.assertEqual((data["update_tag"], data["update_from"]), ("v0.0.2", newer))
        self.assertIn(["--update-from", newer], [e["script"] for e in self.check_log() if "script" in e])

    def test_a_pull_request_that_moves_an_installed_file_and_changes_a_repository_test_gets_both(self):
        """The two checks a branch heuristic once added: the update from the newest release (a move under
        backend/hermes/) and scaffold nested (a tests/repo/ change). try names every check, so it runs both."""
        tree = self.base / "hermretro-wt" / "thing"
        git(tree, "mv", "backend/hermes/glue.py", "backend/hermes/seam.py")
        self.commit(tree, "tests/repo/test_probe.py", "PROBE = 1\n", "Move the glue, probe the tree")
        git(tree, "push", "-q", "origin", "HEAD:refs/pull/8/head")
        head = git(tree, "rev-parse", "HEAD").strip()
        self.clear_log()
        code, data = self.run_cli("try", "8", "--no-setup", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertIn(["--update-from", self.baseline], [e["script"] for e in self.check_log() if "script" in e])
        self.assertEqual({e["head"] for e in self.check_log() if "script" in e}, {head})
        scaffold = [entry.get("mode") for entry in self.check_log() if "scaffold" in entry.get("names", [])]
        self.assertEqual(scaffold, ["nested"])

    def test_keep_leaves_it_and_a_failure_still_removes_it(self):
        code, data = self.run_cli("try", "7", "--keep", "--no-setup", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertTrue((self.base / data["path"]).is_dir())
        self.fail_checks("unit")
        code, data = self.run_cli("try", "7", "--no-setup", as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("failed its full checks", data["error"]["message"])
        self.assertEqual(len(list(self.base.glob("rd-try7-*"))), 1, "only the kept one")

    def test_a_skipped_check_is_unverified_not_a_full_pass(self):
        """Without the toolchain acceptance prints a skipped row and exits 0 (check's policy may skip it): try
        must not call that a pass of the full checks."""
        self.skip_checks("acceptance")
        code, data = self.run_cli("try", "7", "--no-setup", as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("unverified", data["error"]["message"])
        self.assertIn("acceptance skipped", data["error"]["message"])
        self.assertEqual(data["skipped"], ["acceptance"])
        self.assertEqual(list(self.base.glob("rd-try7-*")), [], "the checkout is still removed")
        code, out = self.run_cli("try", "7", "--no-setup")
        self.assertNotIn("passed the full checks", out)

    def test_an_unknown_pull_request_says_how_to_check(self):
        code, data = self.run_cli("try", "99", as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("gh pr view 99", data["error"]["fix"])


class FakeSSH:
    def __init__(self, up: bool = True, code: int = 0, rows: tuple = ("     ok  unit         1.0 s  fine",)):
        self.up, self.code, self.calls, self.rows = up, code, [], rows

    def __call__(self, args, say):
        self.calls.append(list(args))
        if args[-1] == "true":
            return 0 if self.up else 255
        for row in self.rows:
            say(row)
        return self.code


class Mac(RepoCase):
    def test_no_mac_configured_is_fine(self):
        self.fakes["ssh"] = ssh = FakeSSH()
        code, out = self.run_cli("mac")
        self.assertEqual(code, 0, out)
        self.assertIn("no mac configured; CI's macOS runners cover it", out)
        self.assertEqual(ssh.calls, [])

    def test_an_unreachable_mac_waits(self):
        self.fakes["ssh"] = ssh = FakeSSH(up=False)
        self.run_cli("config", "set", "mac_host", "mbp")
        code, data = self.run_cli("mac", as_json=True)
        self.assertEqual(code, 2, data)
        self.assertIn("unreachable; CI covers macOS", data["error"]["message"])
        self.assertEqual(ssh.calls, [["-o", "ConnectTimeout=3", "-o", "BatchMode=yes", "mbp", "true"]])

    def test_the_mac_checks_out_this_commit_and_runs_the_checks(self):
        self.fakes["ssh"] = ssh = FakeSSH()
        tree = self.worktree("feat/thing")
        self.commit(tree, "docs/guide.md", "# Guide 2\n")
        code, data = self.run_cli("mac", "--host", "mbp", cwd=tree, as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("is not on origin", data["error"]["message"])
        git(tree, "push", "-q", "origin", "feat/thing")
        code, out = self.run_cli("mac", "--host", "mbp", "--", "unit", "page", cwd=tree)
        self.assertEqual(code, 0, out)
        sha = git(tree, "rev-parse", "HEAD").strip()
        host, command = ssh.calls[-1]
        self.assertEqual(host, "mbp")
        self.assertTrue(command.startswith("cd ~/Projects/hermretro && git fetch --quiet origin && "), command)
        self.assertIn(f'git worktree add --quiet --detach "$tree" {sha} && ', command)
        self.assertIn('(cd "$tree" && python3 tools/check.py --strict unit page)', command)
        self.assertTrue(
            command.endswith('rm -rf "$tmp"; git worktree prune; exit $code'),
            command,
        )
        for never in ("checkout", "reset", "stash", "clean"):
            self.assertNotIn(never, command, "the clone's own checkout is never switched or reset")
        self.assertIn("ok  unit", out)
        ssh.code = 1
        self.assertEqual(self.run_cli("mac", "--host", "mbp", cwd=tree)[0], 1)

    def test_the_mac_script_tests_the_pushed_commit_not_the_clones_local_changes(self):
        """The script itself, run by a local shell against a clone with uncommitted changes (the mac stand-in)."""
        clone = self.base / "macclone"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(clone))
        broken = "import sys\nprint('the local change ran')\nsys.exit(7)\n"
        write(clone, "tools/check.py", broken)  # a local edit on the mac that must neither run nor be lost
        tree = self.worktree("feat/thing")
        self.commit(tree, "docs/guide.md", "# Guide 2\n")
        git(tree, "push", "-q", "origin", "feat/thing")
        sha = git(tree, "rev-parse", "HEAD").strip()
        (self.base / "mactmp").mkdir()
        self.fakes["mac_tmp"] = self.base / "mactmp"
        lines = []

        def local_ssh(args, say):
            if args[-1] == "true":
                return 0
            done = subprocess.run(["sh", "-c", args[-1]], text=True, capture_output=True)
            for line in (done.stdout + done.stderr).splitlines():
                say(line)
                lines.append(line)
            return done.returncode

        self.fakes["ssh"] = local_ssh
        self.run_cli("config", "set", "mac_repo", str(clone), cwd=tree)
        code, out = self.run_cli("mac", "--host", "mbp", "--", "unit", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("the local change ran", "\n".join(lines))
        self.assertEqual(self.check_log()[-1]["names"], ["--strict", "unit"], "the committed check.py ran")
        self.assertEqual((clone / "tools/check.py").read_text(), broken, "the local change is kept")
        self.assertEqual(git(clone, "rev-parse", "HEAD").strip(), git(clone, "rev-parse", "origin/dev").strip())
        self.assertNotEqual(sha, git(clone, "rev-parse", "HEAD").strip(), "the clone's checkout did not move")
        self.assertEqual(len(git(clone, "worktree", "list").splitlines()), 1, "the temp worktree is gone")
        self.assertEqual(list((self.base / "mactmp").iterdir()), [])

    def test_a_skipped_check_that_exits_zero_is_unverified_not_passed(self):
        """An older check.py (or one that ignores --strict) skips acceptance without the toolchain and exits 0."""
        skipped = "skipped  acceptance   0.0 s  the toolchain is not installed (python tools/ci/prepare_toolchain.py)"
        self.fakes["ssh"] = ssh = FakeSSH(rows=("     ok  unit         1.0 s  fine", skipped))
        tree = self.worktree("feat/thing")
        git(tree, "push", "-q", "origin", "feat/thing")
        code, data = self.run_cli("mac", "--host", "mbp", "--", "acceptance", cwd=tree, as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("unverified on mbp", data["error"]["message"])
        self.assertIn("skipped there (acceptance), so not passed", data["error"]["message"])
        self.assertEqual(data["skipped"], ["acceptance"])
        self.assertIn("python3 tools/check.py --strict acceptance", ssh.calls[-1][1])
        code, out = self.run_cli("mac", "--host", "mbp", "--", "acceptance", cwd=tree)
        self.assertNotIn("passed on mbp", out)

    def test_doctor_reports_the_mac_as_optional(self):
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()), fakes={"ssh": FakeSSH(up=False)})
        self.assertIn("no mac configured", mac.doctor_item(ctx)["detail"])
        ctx.local["mac_host"] = "mbp"
        item = mac.doctor_item(ctx)
        self.assertEqual(
            (item["ok"], item["optional"], item["detail"]), (True, True, "mbp unreachable; CI covers macOS")
        )

    def test_a_home_relative_repo_is_expanded_on_the_mac(self):
        self.assertEqual(mac.remote_path("~/Projects/my games"), "~/'Projects/my games'")
        self.assertEqual(mac.remote_path("/srv/x"), "/srv/x")


class Preview(RepoCase):
    def test_the_page_choices_it_prints_are_the_nav_s_pages_in_order(self):  # review 2, 0: Home was removed
        index = (Path(__file__).resolve().parents[2] / "page" / "pages" / "index.js").read_text()
        pages = re.findall(r"^import \{ \w+_PAGE \} from '\./([a-z-]+)/index\.js'", index, re.M)
        self.assertEqual(list(preview.PAGES), pages[: len(preview.PAGES)])  # a page added later (new page) may follow

    def desktop(self):
        folder = self.base / "desktop"
        write(folder, "package.json", "{}")
        write(folder, "dist/assets/main-abc.css", "body{}")
        return folder

    def test_preview_builds_into_the_state_folder_and_prints_the_path(self):
        calls = []

        def build(command, cwd):
            calls.append(command)
            write(self.base / command[2], "index.html", "<html>preview</html>")  # command[2] is absolute
            return 0, "", ""

        self.fakes["preview_run"] = build
        code, data = self.run_cli("preview", "--desktop", str(self.desktop()), as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(calls[0][:2], ["node", "tests/page/preview/build.mjs"])
        self.assertEqual(data["path"], str(self.main / ".git" / "retrodev" / "preview" / "index.html"))

    def test_a_missing_desktop_or_a_stale_bundle_says_what_to_do(self):
        code, data = self.run_cli("preview", "--desktop", str(self.base / "nowhere"), as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("npm run build", data["error"]["fix"])
        self.fakes["preview_run"] = lambda command, cwd: (1, "", "page/x.js changed\nRun: node tools/bundle/bundle.mjs")
        code, data = self.run_cli("preview", "--desktop", str(self.desktop()), as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("node tools/bundle/bundle.mjs", data["error"]["fix"])

    def test_serving_with_a_symlinked_hermes_source_serves_the_stylesheet_the_build_links(self):
        source = self.base / "hermes-agent"
        write(source, "apps/desktop/package.json", "{}")
        write(source, "apps/desktop/dist/assets/main-abc.css", "body{}")
        link = self.base / "linked-hermes"
        link.symlink_to(source, target_is_directory=True)

        def build(command, cwd):  # like build.mjs: the stylesheet linked by its absolute path in <desktop>/dist/assets
            css = f"{command[3]}/dist/assets/main-abc.css"
            write(Path(command[2]), "index.html", f'<link rel="stylesheet" href="{css}">')
            return 0, "", ""

        got = {}

        def serve(server):
            threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True).start()
            index = self.main / ".git" / "retrodev" / "preview" / "index.html"
            href = index.read_text().split('href="')[1].split('"')[0]
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}{href}"
                with urllib.request.urlopen(url, timeout=5) as answer:
                    got["css"] = answer.read().decode()
            except urllib.error.HTTPError as error:
                got["css"] = f"HTTP {error.code}"
                error.close()
            finally:
                server.shutdown()

        self.fakes.update(preview_run=build, preview_serve=serve, hermes_source=link)
        code, data = self.run_cli("preview", "--serve", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(got["css"], "body{}")
        self.assertEqual(data["desktop"], str(source / "apps" / "desktop"))

    def test_the_server_is_loopback_and_serves_the_preview_and_the_desktop_stylesheets_only(self):
        out = self.base / "out"
        write(out, "index.html", "<html>preview</html>")
        assets = self.desktop() / "dist" / "assets"
        server = preview.make_server(out, assets)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True).start()
        self.addCleanup(server.shutdown)
        host, port = server.server_address[:2]
        self.assertEqual(host, "127.0.0.1")
        # HTTPServer looks 127.0.0.1 up in DNS (socket.getfqdn), about 35 s on a Mac: started in its own process with
        # the lookup made to fail, the server still starts (a patch here would reach every thread of the pool).
        probe = (
            "import socket, sys\n"
            "def refuse(*_a): raise SystemExit('the preview server looked its address up')\n"
            "socket.getfqdn = refuse\n"
            "from retrodev import preview\n"
            "server = preview.make_server(*map(__import__('pathlib').Path, sys.argv[1:]))\n"
            "server.server_close()\n"
        )
        tools = str(Path(preview.__file__).resolve().parents[1])
        started = subprocess.run(
            [sys.executable, "-c", probe, str(out), str(assets)], cwd=tools, capture_output=True, text=True, timeout=60
        )
        self.assertEqual(started.returncode, 0, started.stderr)

        def get(path):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as answer:
                return answer.read().decode()

        self.assertIn("preview", get("/index.html"))
        self.assertEqual(get(str(assets / "main-abc.css")), "body{}")
        for outside in (str(self.base / "desktop" / "package.json"), "/../../etc/hostname"):
            with self.assertRaises(urllib.error.HTTPError, msg=outside) as caught:
                get(outside)
            caught.exception.close()


if __name__ == "__main__":
    unittest.main()
