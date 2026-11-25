"""Where an installed game comes from (backend/library/install_source.py): links, subfolders, and git that never
prompts, never reads the user's git configuration and never keeps a credential.

Run alone: python -m unittest tests.backend.library.test_install_source
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import install_source  # noqa: E402 - the repository root goes on sys.path first
from backend.library.install_source import Source, SourceError, resolve  # noqa: E402
from tests.support import isolated_home, make_game_repo  # noqa: E402 - the repository root goes on sys.path first

GH = "https://github.com/"


class Links(unittest.TestCase):
    def test_every_spelling_of_a_link(self):
        table = {
            "owner/repo": Source(GH + "owner/repo.git"),
            "owner/repo.git": Source(GH + "owner/repo.git"),
            "owner/repo/games/space": Source(GH + "owner/repo.git", None, "games/space"),
            "owner/repo#games/space": Source(GH + "owner/repo.git", None, "games/space"),
            "https://github.com/owner/repo": Source(GH + "owner/repo.git"),
            "https://github.com/owner/repo.git": Source(GH + "owner/repo.git"),
            "https://github.com/owner/repo/": Source(GH + "owner/repo.git"),
            "https://github.com/owner/repo/tree/dev": Source(GH + "owner/repo.git", "dev"),
            "https://github.com/owner/repo/tree/main/games/space": Source(GH + "owner/repo.git", "main", "games/space"),
            "https://gitlab.example/me/game.git": Source("https://gitlab.example/me/game.git"),
            "https://gitlab.example/me/game.git#space": Source("https://gitlab.example/me/game.git", None, "space"),
            "git@github.com:owner/repo.git": Source("git@github.com:owner/repo.git"),
            "ssh://git@host/owner/repo.git": Source("ssh://git@host/owner/repo.git"),
            "file:///srv/games/space": Source("file:///srv/games/space"),
        }
        for link, expected in table.items():
            with self.subTest(link):
                self.assertEqual(resolve(link), expected)

    def test_links_that_are_refused(self):
        for link in (
            "",
            "repo",
            "owner/repo/../../etc",
            "owner/repo#a/../b",
            "https://github.com/owner",
            "https://github.com/owner/repo/blob/main/game.json",
            "https://github.com/owner/repo/tree/-x",
            "owner/repo with space",
            "https:///nohost",
        ):
            with self.subTest(link), self.assertRaises(SourceError):
                resolve(link)

    def test_one_canonical_spelling_and_no_credentials(self):
        spellings = ["owner/Repo", "https://github.com/owner/repo.git", "https://github.com/Owner/repo/"]
        self.assertEqual({resolve(link).canonical for link in spellings}, {GH + "owner/repo"})
        secret = resolve("https://user:s3cret@gitlab.example/me/game.git?x=1#space")
        self.assertEqual(secret.canonical, "https://gitlab.example/me/game#space")
        self.assertNotIn("s3cret", str(secret.record()))
        self.assertEqual(
            install_source.scrub("https://tok@github.com:8443/o/r.git?t=1"), "https://github.com:8443/o/r.git"
        )


class Git(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)

    def test_git_never_prompts_or_reads_the_users_configuration(self):
        with mock.patch.dict(os.environ, {"GIT_DIR": "/elsewhere", "GIT_CONFIG_GLOBAL": "/home/u/.gitconfig"}):
            environment = install_source.git_environment()
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertNotIn("GIT_DIR", environment)
        self.assertIn("BatchMode=yes", environment["GIT_SSH_COMMAND"])

    def test_clone_and_remote_commit(self):
        repo, link = make_game_repo(self.home.base)
        commit = install_source.clone(resolve(link), self.home.base / "clone")
        self.assertEqual(commit, install_source.remote_commit(resolve(link)))
        self.assertTrue((self.home.base / "clone" / "game.json").is_file())
        with self.assertRaises(SourceError) as missing:
            install_source.remote_commit(Source(link, "nope"))
        self.assertEqual(missing.exception.code, "NO_BRANCH")

    def test_a_refused_github_clone_retries_once_with_the_users_token(self):
        calls = []

        def run(command, **kwargs):
            calls.append(kwargs["env"])
            return mock.Mock(
                returncode=128, stdout="", stderr="fatal: could not read Username for 'https://github.com'"
            )

        with (
            mock.patch.object(install_source.subprocess, "run", side_effect=run),
            mock.patch.dict(os.environ, {"GITHUB_TOKEN": "tok123"}),
            self.assertRaises(SourceError),
        ):
            install_source.run_git(["ls-remote", GH + "o/r.git"], url=GH + "o/r.git")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("GIT_CONFIG_COUNT", calls[0])
        self.assertTrue(calls[1]["GIT_CONFIG_VALUE_0"].startswith("AUTHORIZATION: basic "))
        self.assertNotIn("tok123", calls[1]["GIT_CONFIG_VALUE_0"])  # encoded, and only in the environment

    def test_other_failures_are_not_retried_and_hide_credentials(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return mock.Mock(returncode=128, stdout="", stderr="fatal: unable to access 'https://me:pw@host/r.git'")

        with (
            mock.patch.object(install_source.subprocess, "run", side_effect=run),
            self.assertRaises(SourceError) as error,
        ):
            install_source.run_git(["ls-remote", "https://me:pw@host/r.git"], url="https://me:pw@host/r.git")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("pw", error.exception.message)

    def test_a_subfolder_stays_inside_the_checkout(self):
        root = self.home.base / "checkout"
        (root / "games" / "space").mkdir(parents=True)
        (root / "outside").symlink_to(self.home.base)
        self.assertEqual(install_source.within(root, "games/space"), (root / "games" / "space").resolve())
        for subdir in ("outside", "missing", "../x"):
            with self.subTest(subdir), self.assertRaises(SourceError):
                install_source.within(root, subdir)


if __name__ == "__main__":
    unittest.main()
