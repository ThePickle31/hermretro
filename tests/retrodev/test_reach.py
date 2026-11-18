"""try (a pull request's full checks in a throwaway checkout), mac (a fake ssh) and preview (a fake build).

Run alone: python -m unittest tests.retrodev.test_reach
"""

import io
import threading
import unittest
import urllib.error
import urllib.request

from retrodev import config, mac, output, preview

from tests.retrodev.fixture import RepoCase, git, parallel, write

load_tests = parallel


class Try(RepoCase):
    def setUp(self):
        super().setUp()
        self.fakes["tmp_root"] = self.base
        tree = self.worktree("feat/thing")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", "Change the value")
        git(tree, "push", "-q", "origin", "HEAD:refs/pull/7/head")  # what GitHub keeps for pull request 7
        self.head = git(tree, "rev-parse", "HEAD").strip()

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
        self.assertEqual(data["head"], self.head)
        self.assertTrue(data["path"].startswith(str(self.base / "rd-try7-")), "outside the repository, short")
        names = [entry.get("names") or entry.get("script") for entry in self.check_log()]
        self.assertIn(["unit", "bundle", "lint", "page", "scan"], names)
        self.assertIn(["acceptance"], names)  # --full
        self.assertEqual([e["head"] for e in self.check_log() if "script" in e], [self.head])
        self.assertEqual(list(self.base.glob("rd-try7-*")), [])
        self.assertEqual(self.worktrees(), before)

    def test_keep_leaves_it_and_a_failure_still_removes_it(self):
        code, data = self.run_cli("try", "7", "--keep", "--no-setup", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertTrue((self.base / data["path"]).is_dir())
        self.fail_checks("unit")
        code, data = self.run_cli("try", "7", "--no-setup", as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("failed its full checks", data["error"]["message"])
        self.assertEqual(len(list(self.base.glob("rd-try7-*"))), 1, "only the kept one")

    def test_an_unknown_pull_request_says_how_to_check(self):
        code, data = self.run_cli("try", "99", as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("gh pr view 99", data["error"]["fix"])


class FakeSSH:
    def __init__(self, up: bool = True, code: int = 0):
        self.up, self.code, self.calls = up, code, []

    def __call__(self, args, say):
        self.calls.append(list(args))
        if args[-1] == "true":
            return 0 if self.up else 255
        say("     ok  unit         1.0 s  fine")
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
        self.assertEqual(
            command,
            f"cd ~/Projects/hermretro && git fetch --quiet origin && git -c advice.detachedHead=false checkout --quiet "
            f"--detach {sha} && python3 tools/check.py unit page",
        )
        self.assertIn("ok  unit", out)
        ssh.code = 1
        self.assertEqual(self.run_cli("mac", "--host", "mbp", cwd=tree)[0], 1)

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
