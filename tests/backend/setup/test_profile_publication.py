"""The publishing step rechecks the profile name and the gateway's lock on disk."""

import fcntl
import unittest
from unittest import mock

from backend.setup import profile_publication as pp
from tests.support import isolated_home


class ProfilePublication(unittest.TestCase):
    def setUp(self):
        self.profiles = isolated_home(self).base / "profiles"
        self.profiles.mkdir()
        self.target = self.profiles / "hermretro"
        self.staging = self.profiles / ".staging"
        self.staging.mkdir()
        (self.staging / "config.yaml").touch()
        self.marker = pp.hermes_api.profile_tombstone(self.target)

    def tombstone(self):
        self.marker.parent.mkdir(exist_ok=True)
        self.marker.write_text("deleted")

    def publish(self, race=None):
        with pp.profiles_directory(self.target) as (target, profiles):
            pp.lock_profiles(profiles)
            deleted = pp.Tombstone(target, profiles)
            expected = pp.creation_candidate(target, profiles, deleted)
            if race:
                race()
            pp.publish(self.staging, target, expected, profiles, deleted)

    def test_an_identity_free_directory_without_a_tombstone_is_left_in_place(self):
        self.target.mkdir()
        mine = self.target / "my-game-notes"
        mine.write_text("keep")
        with self.assertRaises(FileExistsError):
            self.publish()
        self.assertEqual(mine.read_text(), "keep")

    def test_native_identity_markers_take_precedence_over_a_tombstone(self):
        self.tombstone()
        self.target.mkdir()
        for name in ("config.yaml", ".env", "SOUL.md", "profile.yaml", "auth.json", "state.db"):
            with self.subTest(marker=name):
                identity = self.target / name
                identity.symlink_to("missing")
                with self.assertRaises(FileExistsError):
                    self.publish()
                self.assertTrue(identity.is_symlink())
                self.assertTrue(self.marker.is_file())
                identity.unlink()

    def test_a_gateway_holding_the_shell_lock_prevents_recovery(self):
        self.tombstone()
        self.target.mkdir()
        runtime = self.target / "gateway.lock"
        runtime.write_text("owner")
        with runtime.open("r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(FileExistsError):
                self.publish()
            self.assertEqual(runtime.read_text(), "owner")
        self.assertTrue(self.marker.is_file())
        self.assertEqual(list(self.profiles.glob(".hermretro-deleted-*")), [])

    def test_a_replacement_during_the_source_rename_is_restored(self):
        self.tombstone()
        self.target.mkdir()
        moved = self.profiles / "moved"
        real = pp.rename_unoccupied

        def replace_before_move(source, target, **kwargs):
            if not moved.exists():
                self.target.rename(moved)
                self.target.mkdir()
                (self.target / ".env").write_text("somebody else's")
            real(source, target, **kwargs)

        with mock.patch.object(pp, "rename_unoccupied", side_effect=replace_before_move):
            with self.assertRaises(FileExistsError):
                self.publish()
        self.assertEqual((self.target / ".env").read_text(), "somebody else's")
        self.assertTrue(self.marker.is_file())

    def test_a_competing_empty_directory_is_not_replaced_during_publication(self):
        real = pp.rename_unoccupied

        def create_before_publish(source, target, **kwargs):
            self.target.mkdir()
            real(source, target, **kwargs)

        with mock.patch.object(pp, "rename_unoccupied", side_effect=create_before_publish):
            with self.assertRaises(FileExistsError):
                self.publish()
        self.assertEqual(list(self.target.iterdir()), [])
        self.assertTrue(self.staging.is_dir())

    def test_a_new_tombstone_created_during_preparation_is_preserved(self):
        with self.assertRaises(FileExistsError):
            self.publish(race=self.tombstone)
        self.assertTrue(self.marker.is_file())
        self.assertFalse(self.target.exists())
