"""The factory reset's backend half: each part deletes only what it names, and the RPC stops the broker first."""

import json
import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library.games import VERSION  # noqa: E402 - the repository root goes on sys.path first
from backend.setup import reset, reset_rpcs, studio_profile  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import FakeBrokerClient, isolated_home  # noqa: E402 - the repository root goes on sys.path first


def write(path: Path, size: int = 10) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


CAPTURES_DEMO = Path("captures") / "demo" / "shot.png"


class Reset(unittest.TestCase):
    def setUp(self):
        self.places = isolated_home(self)
        home, self.data = self.places.home, self.places.data
        self.cache = home / ".cache"
        self.deps = mock.patch.object(paths, "DEPS_ROOT", self.cache)
        self.deps.start()
        self.addCleanup(self.deps.stop)
        # The unit tests run without Hermes: the studio profile is a folder of the test's own (no chats unless made).
        self.studio = self.places.base / "studio"
        self.enterContext(mock.patch.object(studio_profile, "studio_dir", lambda: self.studio))
        self.games = home / "games"
        self.frog = self.games / "Frog"
        write(self.frog / "frog.gbsproj", 100)
        write(self.frog / "captures" / "shot.png", 7)
        write(self.games / ".hermretro-installs" / "a.lock", 1)
        self.elsewhere = self.places.base / "mine" / "Owl"
        write(self.elsewhere / "owl.gbsproj", 5)
        write(self.elsewhere / "captures" / "clip.webm", 3)
        library = home / "library"
        library.mkdir(parents=True)
        games = {
            "aaaaaaaaaaaa": {"id": "aaaaaaaaaaaa", "projectRoot": str(self.frog)},
            "bbbbbbbbbbbb": {"id": "bbbbbbbbbbbb", "projectRoot": str(self.elsewhere)},
        }
        (library / "games.json").write_text(json.dumps({"version": VERSION, "games": games}))
        write(library / "thumbs" / "aaaaaaaaaaaa.png", 4)
        write(self.data / "snapshots" / "aaaaaaaaaaaa" / "1" / "f", 30)
        write(self.data / "asset-versions" / "a" / "v1.png", 6)
        write(self.data / "frames" / "f.png", 8)
        write(self.cache / "toolchain" / "bin" / "gbdk", 1000)
        self.run_dir = self.places.runtime
        write(self.run_dir / "trace.jsonl", 9)
        write(self.run_dir / "broker.stderr.log", 9)
        write(self.run_dir / "broker.stderr.log.1", 5)
        write(self.run_dir / "broker.token", 1)

    def test_the_plan_says_what_each_part_holds(self):
        parts = reset.plan(self.data)["parts"]
        self.assertEqual(parts["games"]["count"], 2)
        self.assertGreaterEqual(parts["games"]["bytes"], 100)
        self.assertEqual(parts["history"]["bytes"], 30 + 6)  # build snapshots and kept image versions
        self.assertGreaterEqual(parts["toolchain"]["bytes"], 1000)
        self.assertFalse(parts["toolchain"]["custom"])
        self.assertEqual(parts["logs"]["bytes"], 9 + 9 + 5 + 8 + 7)  # a folder of the user's own keeps its captures

    def test_games_empty_the_games_folder_and_library_and_leave_a_folder_of_the_users_own(
        self,
    ):
        answer = reset.clear("games", self.data, [])
        self.assertTrue(answer["ok"])
        self.assertEqual(list(self.games.iterdir()), [])
        self.assertEqual(list((self.places.home / "library").iterdir()), [])
        self.assertTrue(
            (self.data / "asset-versions").exists(),
            "kept image versions belong to Build history",
        )
        self.assertTrue((self.elsewhere / "owl.gbsproj").is_file())
        self.assertTrue((self.data / "snapshots").is_dir())
        self.assertTrue((self.cache / "toolchain").is_dir())

    def test_a_games_folder_the_user_configured_loses_only_hermretros_games(self):
        write(self.games / "notes.txt", 2)
        with mock.patch.dict(os.environ, {"HERMRETRO_GAMES_DIR": str(self.games)}):
            reset.clear("games", self.data, [])
        self.assertEqual(sorted(p.name for p in self.games.iterdir()), ["notes.txt"])

    def test_a_library_folder_the_user_configured_keeps_its_other_files(self):
        library = self.places.home / "library"
        write(library / "notes.txt", 2)
        with mock.patch.dict(os.environ, {"HERMRETRO_LIBRARY_DIR": str(library)}):
            reset.clear("games", self.data, [])
        self.assertEqual(sorted(p.name for p in library.iterdir()), ["notes.txt"])

    def test_a_game_folder_a_link_now_stands_in_for_is_never_followed(self):
        target = self.places.base / "precious"
        write(target / "captures" / "keep.png", 3)
        moved = self.places.base / "moved"
        os.replace(self.frog, moved)
        self.frog.symlink_to(target)
        with mock.patch.dict(os.environ, {"HERMRETRO_GAMES_DIR": str(self.games)}):
            reset.clear("logs", self.data, [])
            reset.clear("games", self.data, [])
        self.assertTrue((target / "captures" / "keep.png").is_file())

    def test_what_could_not_be_deleted_is_said(self):
        with mock.patch.object(reset, "_remove"):
            answer = reset.clear("history", self.data, [])
        self.assertEqual(
            (answer["ok"], answer["code"], answer["removed_bytes"]),
            (False, "PARTLY_REMOVED", 0),
        )

    def test_history_and_logs_delete_only_their_own(self):
        reset.clear("history", self.data, [])
        self.assertFalse((self.data / "snapshots").exists())
        self.assertFalse((self.data / "asset-versions").exists())
        reset.clear("logs", self.data, [])
        self.assertFalse((self.run_dir / "trace.jsonl").exists())
        self.assertFalse((self.run_dir / "broker.stderr.log.1").exists())
        self.assertFalse((self.data / "frames").exists())
        self.assertFalse((self.frog / "captures").exists())
        self.assertTrue((self.elsewhere / "captures" / "clip.webm").is_file())
        self.assertTrue((self.run_dir / "broker.token").is_file())
        self.assertTrue((self.frog / "frog.gbsproj").is_file())

    def _chats(self, rows):
        self.studio.mkdir()
        with sqlite3.connect(self.studio / "state.db") as db:
            db.execute("CREATE TABLE sessions (id TEXT, parent_session_id TEXT, model_config TEXT)")
            db.executemany(
                "INSERT INTO sessions VALUES (?, ?, ?)",
                [(*row, "{}")[:3] if len(row) == 2 else row for row in rows],
            )

    def test_chats_are_deleted_with_hermes_own_command_forks_too_and_any_left_are_said(
        self,
    ):
        # "a" has a delegate (deleted with it) and a fork, which becomes a chat of its own once "a" is gone.
        self._chats(
            [
                ("a", None),
                ("b", None),
                ("a-sub", "a"),
                ("a-fork", "a", '{"_branched_from": "a"}'),
            ]
        )
        library = self.places.home / "library" / "games.json"
        games = json.loads(library.read_text())
        games["games"]["aaaaaaaaaaaa"]["chat"] = {"sessionId": "b"}
        games["games"]["bbbbbbbbbbbb"]["session"] = {"storedId": "a"}
        library.write_text(json.dumps(games))
        ran = []

        def hermes(home, *arguments):
            ran.append(arguments[2])
            if arguments[2] == "b":
                return  # refused
            with sqlite3.connect(home / "state.db") as db:
                db.execute(
                    "DELETE FROM sessions WHERE id = ? OR id = ?",
                    (arguments[2], f"{arguments[2]}-sub"),
                )
                db.execute(
                    "UPDATE sessions SET parent_session_id = NULL WHERE parent_session_id = ?",
                    (arguments[2],),
                )

        with (
            mock.patch.object(studio_profile, "studio_is_ours", lambda: True),
            mock.patch.object(studio_profile, "run_hermes", hermes),
        ):
            self.assertEqual(
                reset.plan(self.data)["parts"]["chats"]["count"],
                3,
                "a fork is a chat of its own",
            )
            answer = reset.clear("chats", self.data, [])
        self.assertEqual(ran[:2], ["a", "b"])
        self.assertIn("a-fork", ran[2:])  # the next round
        self.assertEqual(
            (answer["ok"], answer["code"], answer["partly"]),
            (False, "CHATS_LEFT", True),
        )
        games = json.loads(library.read_text())["games"]
        self.assertEqual(games["aaaaaaaaaaaa"]["chat"], {"sessionId": "b"}, "a chat still there keeps its link")
        self.assertNotIn("session", games["bbbbbbbbbbbb"], "one that went lets go")

    def test_links_let_every_game_go_of_its_chats_after_the_profile_went(self):
        library = self.places.home / "library" / "games.json"
        games = json.loads(library.read_text())
        games["games"]["aaaaaaaaaaaa"]["chat"] = {"sessionId": "x"}
        library.write_text(json.dumps(games))
        self.assertTrue(reset.clear("links", self.data, [])["ok"])
        self.assertNotIn("chat", json.loads(library.read_text())["games"]["aaaaaaaaaaaa"])

    def test_a_linked_session_database_is_another_profiles_and_never_touched(self):
        other = self.places.base / "other"
        other.mkdir()
        with sqlite3.connect(other / "state.db") as db:
            db.execute("CREATE TABLE sessions (id TEXT, parent_session_id TEXT)")
            db.execute("INSERT INTO sessions VALUES ('x', NULL)")
        self.studio.mkdir()
        (self.studio / "state.db").symlink_to(other / "state.db")
        with (
            mock.patch.object(studio_profile, "studio_is_ours", lambda: True),
            mock.patch.object(studio_profile, "run_hermes") as ran,
        ):
            answer = reset.clear("chats", self.data, [])
        self.assertEqual(answer["code"], "CHATS_UNREADABLE")
        ran.assert_not_called()

    def test_a_long_chain_of_forks_goes_in_one_reset(self):
        chain = [("c0", None, "{}")] + [(f"c{i}", f"c{i - 1}", '{"_branched_from": "x"}') for i in range(1, 8)]
        self._chats(chain)

        def hermes(home, *arguments):
            with sqlite3.connect(home / "state.db") as db:
                db.execute("DELETE FROM sessions WHERE id = ?", (arguments[2],))
                db.execute(
                    "UPDATE sessions SET parent_session_id = NULL WHERE parent_session_id = ?",
                    (arguments[2],),
                )

        with (
            mock.patch.object(studio_profile, "studio_is_ours", lambda: True),
            mock.patch.object(studio_profile, "run_hermes", hermes),
        ):
            library = self.places.home / "library" / "games.json"
            games = json.loads(library.read_text())
            games["games"]["aaaaaaaaaaaa"].update(chat={"sessionId": "c0"}, session={"storedId": "c0", "plan": True})
            games["pending"] = {"c7": {"storedId": "c7"}}
            library.write_text(json.dumps(games))
            self.assertTrue(reset.clear("chats", self.data, [])["ok"])
        after = json.loads(library.read_text())
        frog = after["games"]["aaaaaaaaaaaa"]
        self.assertNotIn("chat", frog, "no game points at a deleted chat")
        self.assertNotIn("session", frog)
        self.assertTrue(frog["initialPlan"], "a first plan still owed stays owed")
        self.assertEqual(after["pending"], {})

    def test_a_hermretro_profile_hermretro_did_not_make_keeps_its_chats(self):
        self._chats([("a", None)])
        with mock.patch.object(studio_profile, "run_hermes") as ran:
            self.assertEqual(
                reset.plan(self.data)["parts"]["profile"],
                {"ours": False, "holds": False},
            )
            answer = reset.clear("chats", self.data, [])
        self.assertEqual(answer["code"], "NOT_OURS")
        ran.assert_not_called()

    def test_a_linked_library_folder_is_never_followed(self):
        library = self.places.home / "library"
        target = self.places.base / "elsewhere-library"
        os.replace(library, target)
        library.symlink_to(target)
        write(target / CAPTURES_DEMO, 4)
        reset.clear("games", self.data, [])
        reset.clear("logs", self.data, [])
        self.assertTrue((target / "games.json").is_file())
        self.assertTrue((target / CAPTURES_DEMO).is_file())

    def test_logs_take_only_the_demo_captures_from_the_library(self):
        library = self.places.home / "library"
        write(library / CAPTURES_DEMO, 4)
        write(library / "captures" / "mine.txt", 1)
        reset.clear("logs", self.data, [])
        self.assertFalse((library / CAPTURES_DEMO).exists())
        self.assertTrue((library / "captures" / "mine.txt").is_file())

    def test_a_linked_games_list_never_says_what_to_delete(self):
        library = self.places.home / "library"
        other = self.places.base / "other-library"
        other.mkdir()
        os.replace(library / "games.json", other / "games.json")
        (library / "games.json").symlink_to(other / "games.json")
        with mock.patch.dict(os.environ, {"HERMRETRO_GAMES_DIR": str(self.games)}):
            answer = reset.clear("games", self.data, [])
        self.assertEqual(answer["code"], "LIBRARY_UNREADABLE")
        self.assertTrue((self.frog / "frog.gbsproj").is_file())

    def test_the_library_stays_while_a_game_folder_could_not_be_deleted(self):
        real = reset._remove

        def stubborn(place):
            if place != self.frog:
                real(place)

        with (
            mock.patch.dict(os.environ, {"HERMRETRO_GAMES_DIR": str(self.games)}),
            mock.patch.object(reset, "_remove", stubborn),
        ):
            answer = reset.clear("games", self.data, [])
        self.assertEqual(answer["code"], "PARTLY_REMOVED")
        self.assertTrue(
            (self.places.home / "library" / "games.json").is_file(),
            "so a retry still finds the game",
        )

    def test_a_studio_profile_holding_the_games_says_so(self):
        with mock.patch.dict(os.environ, {"HERMRETRO_GAMES_DIR": str(self.studio / "games")}):
            self.assertTrue(reset.plan(self.data)["parts"]["profile"]["holds"])

    def test_a_library_game_inside_the_studio_profile_says_it_holds_games(self):
        games = json.loads((self.places.home / "library" / "games.json").read_text())
        games["games"]["cccccccccccc"] = {
            "id": "cccccccccccc",
            "projectRoot": str(self.studio / "workspace" / "Cat"),
        }
        (self.places.home / "library" / "games.json").write_text(json.dumps(games))
        self.assertTrue(reset.plan(self.data)["parts"]["profile"]["holds"])

    def test_settings_never_go_through_a_linked_config(self):
        home = self.places.base / "linked-home"
        home.mkdir()
        (home / "config.yaml").symlink_to(self.places.base / "someone-elses.yaml")
        set_here = {"plugins": {"entries": {"hermretro": {"settings": {"hardware_enabled": True}}}}}
        with (
            mock.patch.object(reset.hermes_api, "read_profile_config", lambda _home: set_here),
            mock.patch.object(reset.hermes_api, "write_profile_config_key") as written,
        ):
            answer = reset.clear("settings", self.data, [home])
            self.assertEqual((answer["code"], answer["partly"]), ("CONFIG_LINKED", False))
            written.assert_not_called()
            plain = self.places.base / "plain-home"
            plain.mkdir()
            answer = reset.clear("settings", self.data, [home, plain])
        self.assertTrue(answer["partly"], "the other profile's settings did go")

    def test_a_linked_captures_folder_in_the_library_is_never_followed(self):
        library = self.places.home / "library"
        elsewhere = self.places.base / "elsewhere-captures"
        write(elsewhere / "demo" / "shot.png", 4)
        (library / "captures").symlink_to(elsewhere)
        reset.clear("logs", self.data, [])
        self.assertTrue((elsewhere / "demo" / "shot.png").is_file())

    def test_the_toolchain_says_when_it_went_in_part(self):
        partial = {
            "ok": False,
            "code": "PARTLY_REMOVED",
            "removed_bytes": 10,
            "left_bytes": 5,
        }
        with mock.patch.object(reset.downloads, "remove_downloads", lambda: partial):
            self.assertTrue(reset.clear("toolchain", self.data, [])["partly"])

    def test_games_leave_the_demo_captures_to_logs(self):
        write(self.places.home / "library" / CAPTURES_DEMO, 4)
        reset.clear("games", self.data, [])
        self.assertTrue((self.places.home / "library" / CAPTURES_DEMO).is_file())

    def test_settings_go_back_to_their_defaults_only_where_they_were_set(self):
        set_here = {"plugins": {"entries": {"hermretro": {"settings": {"hardware_enabled": True}}}}}
        configs = {Path("/a"): set_here, Path("/b"): {}}
        with (
            mock.patch.object(reset.hermes_api, "read_profile_config", lambda home: configs[home]),
            mock.patch.object(reset.hermes_api, "write_profile_config_key") as written,
        ):
            reset.clear("settings", self.data, [Path("/a"), Path("/b")])
        written.assert_called_once_with(Path("/a"), "plugins.entries.hermretro.settings", {})

    def test_settings_in_the_older_place_hermes_still_reads_go_too(self):
        older = {"plugins": {"entries": {"hermretro": {"config": {"hardware_enabled": True}}}}}
        with (
            mock.patch.object(reset.hermes_api, "read_profile_config", lambda home: older),
            mock.patch.object(reset.hermes_api, "write_profile_config_key") as written,
        ):
            reset.clear("settings", self.data, [Path("/a")])
        written.assert_called_once_with(Path("/a"), "plugins.entries.hermretro.config", {})

    def test_the_rpc_stops_the_broker_with_its_idle_workers_and_refuses_a_busy_one(
        self,
    ):
        rpc = reset_rpcs.rpc_reset(None)
        self.assertEqual(rpc({"part": "everything"})["code"], "UNKNOWN_PART")
        busy = FakeBrokerClient({"ok": False, "denied": {"code": "BUSY"}})
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (busy, None)):
            answer = rpc({"part": "history"})
        self.assertEqual((answer["ok"], answer["code"]), (False, "BUSY"))
        self.assertEqual(busy.asked, [{"op": "shutdown", "replace": True}])
        self.assertTrue((self.data / "snapshots").is_dir())
        idle = FakeBrokerClient({"ok": True})
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (idle, None)):
            self.assertTrue(rpc({"part": "stop"})["ok"])
            self.assertTrue(rpc({"part": "history"})["ok"])
        self.assertFalse((self.data / "snapshots").exists())


if __name__ == "__main__":
    unittest.main()
