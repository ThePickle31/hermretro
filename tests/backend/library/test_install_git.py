"""The git steps of an install (backend/library/install_git.py): git that never prompts or reads the user's
configuration, a fetch whose tree is checked before anything is checked out, the token retry, and branches.

Run alone: python -m unittest tests.backend.library.test_install_git
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import install_git  # noqa: E402 - the repository root goes on sys.path first
from backend.library.install_source import Source, SourceError, resolve  # noqa: E402
from tests.support import commit_all, git, isolated_home, make_game_repo  # noqa: E402

GH = "https://github.com/"


def problem_codes(entries, **limits):
    limits = {"max_files": 100, "max_total": 10**9, **limits}
    return sorted({problem["code"] for problem in install_git.tree_problems(entries, **limits)})


def entry(path, mode="100644", size=10, kind="blob"):
    return {"path": path, "mode": mode, "kind": kind, "size": size}


class Environment(unittest.TestCase):
    def test_git_never_prompts_or_reads_the_users_configuration(self):
        with mock.patch.dict(os.environ, {"GIT_DIR": "/elsewhere", "GIT_CONFIG_GLOBAL": "/home/u/.gitconfig"}):
            environment = install_git.git_environment()
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_NO_LAZY_FETCH"], "1")
        self.assertNotIn("GIT_DIR", environment)
        self.assertIn("BatchMode=yes", environment["GIT_SSH_COMMAND"])

    def run_refused(self, stderr, **environment):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs["env"]))
            kwargs["stderr"].write(stderr.encode())
            return mock.Mock(returncode=128)

        with (
            mock.patch.object(install_git.subprocess, "run", side_effect=run),
            mock.patch.object(install_git.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"),
            mock.patch.object(install_git, "_github_token", return_value=environment.get("token")),
            self.assertRaises(SourceError),
        ):
            install_git.run_git(["ls-remote", GH + "o/r.git"], cwd=Path("/"), url=GH + "o/r.git")
        return calls

    def test_a_refused_github_fetch_retries_once_with_the_token_in_the_environment_only(self):
        calls = self.run_refused("fatal: could not read Username for 'https://github.com'", token="tok123")
        self.assertEqual(len(calls), 2)
        (_, first), (argv, second) = calls
        self.assertNotIn("tok123", " ".join(argv))
        values = {
            second[f"GIT_CONFIG_KEY_{i}"]: second[f"GIT_CONFIG_VALUE_{i}"]
            for i in range(int(second["GIT_CONFIG_COUNT"]))
        }
        self.assertTrue(values[f"http.{GH}.extraheader"].startswith("AUTHORIZATION: basic "))
        self.assertEqual(values["http.followRedirects"], "false")
        self.assertNotIn(
            f"http.{GH}.extraheader", {first[f"GIT_CONFIG_KEY_{i}"] for i in range(int(first["GIT_CONFIG_COUNT"]))}
        )

    def test_other_failures_are_not_retried(self):
        self.assertEqual(len(self.run_refused("fatal: unable to connect", token="tok")), 1)
        self.assertEqual(len(self.run_refused("fatal: repository not found")), 1)  # no token to try

    def test_the_token_comes_only_for_github(self):
        with (
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch.object(install_git.shutil, "which", return_value="/usr/bin/gh"),
            mock.patch.object(
                install_git.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="tok\n")
            ) as gh,
        ):
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("GH_TOKEN", None)
            self.assertEqual(install_git._github_token(), "tok")
        self.assertEqual(gh.call_args.args[0][1:], ["auth", "token", "--hostname", "github.com"])

    def test_output_is_capped(self):
        with mock.patch.object(install_git, "MAX_OUTPUT_BYTES", 10), self.assertRaises(SourceError) as refused:
            install_git.run_git(["--version", "--build-options"], cwd=Path("/"))
        self.assertEqual(refused.exception.code, "OUTPUT")


class Tree(unittest.TestCase):
    def test_what_makes_a_tree_unsafe(self):
        self.assertEqual(problem_codes([entry("game.json"), entry("build/game.gbc")]), [])
        self.assertEqual(problem_codes([entry("docs", mode="120000")]), ["LINK"])
        self.assertEqual(problem_codes([entry("vendor", mode="160000", kind="commit", size=None)]), ["SUBMODULE"])
        self.assertEqual(problem_codes([entry("art/huge.bin", size=None)]), ["TOO_BIG"])  # left out by the fetch
        self.assertEqual(problem_codes([entry("a"), entry("b")], max_files=1), ["TOO_MANY"])
        self.assertEqual(problem_codes([entry("a", size=60), entry("b", size=60)], max_total=100), ["TOO_BIG"])
        self.assertEqual(problem_codes([entry("Docs/a"), entry("docs/b")]), ["COLLISION"])
        self.assertEqual(problem_codes([entry("café.png"), entry("café.png")]), ["COLLISION"])


class Fetch(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.repos = self.home.base / "repos"

    def settled(self, link):
        return install_git.settle(resolve(link, allow_local=True))

    def test_the_default_branch_is_named_and_the_fetch_checks_nothing_out(self):
        repo, link = make_game_repo(self.repos)
        source = self.settled(link)
        self.assertEqual(source.ref, "main")
        clone = self.home.base / "clone"
        commit = install_git.fetch(source, clone)
        self.assertEqual(commit, git(repo, "rev-parse", "HEAD"))
        self.assertFalse((clone / "game.json").exists())
        paths = {item["path"] for item in install_git.tree(clone, None)}
        self.assertIn("build/game.gbc", paths)
        install_git.checkout(clone, None)
        self.assertTrue((clone / "game.json").is_file())
        self.assertEqual(install_git.remote_commit(source), commit)

    def test_an_oversized_file_is_seen_before_checkout(self):
        repo, link = make_game_repo(self.repos)
        (repo / "art").mkdir()
        (repo / "art" / "huge.bin").write_bytes(b"\1" * 64 * 1024)
        commit_all(repo, "big")
        clone = self.home.base / "clone"
        with mock.patch.object(install_git, "MAX_FILE_BYTES", 40 * 1024):  # over it: the 64 KiB file, not the ROM
            install_git.fetch(self.settled(link), clone)
            problems = install_git.tree_problems(install_git.tree(clone, None), max_files=100, max_total=10**9)
        self.assertEqual([(p["code"], p["path"]) for p in problems], [("TOO_BIG", "art/huge.bin")])
        self.assertFalse((clone / "art").exists())

    def test_a_tree_link_takes_the_longest_branch_that_matches(self):
        repo, link = make_game_repo(self.repos)
        git(repo, "tag", "feature")  # a tag and a branch whose names "feature/demo/..." could both start
        git(repo, "branch", "feature/demo")
        settled = self.settled(link + "#x")  # a plain link keeps its folder
        self.assertEqual((settled.ref, settled.subdir), ("main", "x"))
        tree_source = Source(link, None, None, tree="feature/demo/games/space")
        self.assertEqual(install_git.settle(tree_source).ref, "feature/demo")
        self.assertEqual(install_git.settle(tree_source).subdir, "games/space")
        self.assertEqual(install_git.settle(Source(link, None, None, tree="feature/other")).ref, "feature")
        with self.assertRaises(SourceError) as missing:
            install_git.settle(Source(link, None, None, tree="nope/x"))
        self.assertEqual(missing.exception.code, "NO_BRANCH")


if __name__ == "__main__":
    unittest.main()
