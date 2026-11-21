"""Unit tests for schema conversion and result encoding. Run: python -m unittest discover -s tests -t ."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from backend.hermes import contracts  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import results  # noqa: E402 - the repository root goes on sys.path first

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes").decode()


class ContractTests(unittest.TestCase):
    def test_every_pinned_tool_becomes_one_prefixed_schema(self):
        pinned = contracts.pinned_tools()
        schemas = contracts.hermes_schemas()
        self.assertEqual(len(schemas), len(pinned))
        self.assertEqual([s["name"] for s in schemas], ["chromatic_" + t["name"] for t in pinned])
        self.assertEqual(len({s["name"] for s in schemas}), len(pinned))

    def test_schemas_carry_no_references_and_keep_required_fields(self):
        for tool, schema in zip(contracts.pinned_tools(), contracts.hermes_schemas(), strict=True):
            text = json.dumps(schema)
            self.assertNotIn("$ref", text, schema["name"])
            self.assertNotIn("$schema", text, schema["name"])
            required = tool["inputSchema"].get("required")
            if tool["name"] in contracts.CREATORS:  # Hermes fills the destination: the Studio games folder
                required = [key for key in required if key != "destinationPath"]
            self.assertEqual(schema["parameters"].get("required"), required)
            # hermretro's own argument (the broker strips it before the engine): project_select only.
            extra = ["continueInThisChat"] if tool["name"] == "project_select" else []
            self.assertEqual(
                sorted(schema["parameters"].get("properties", {})),
                sorted([*tool["inputSchema"].get("properties", {}), *extra]),
            )

    def test_reference_is_inlined_with_local_description_kept(self):
        build = next(s for s in contracts.hermes_schemas() if s["name"] == "chromatic_rom_build")
        source = build["parameters"]["properties"]["sourcePath"]
        self.assertEqual(source["type"], "string")
        self.assertEqual(source["maxLength"], 4096)
        self.assertIn("Standalone .c source", source["description"])

    def test_web_preview_description_points_at_the_studio_emulator(self):
        schemas = {s["name"]: s["description"] for s in contracts.hermes_schemas()}
        preview = schemas["chromatic_web_preview"]
        self.assertIn("call chromatic_present_game instead", preview)
        self.assertIn("only if the user says they cannot see that emulator", preview)
        self.assertNotIn("Codex", preview)
        # The physical feed has no Studio surface: it keeps the in-app browser wording.
        self.assertIn("desktop_preview tool", schemas["chromatic_device_capture"])
        self.assertNotIn("Codex", schemas["chromatic_device_capture"])

    def test_manifest_lists_exactly_the_registered_tools(self):
        manifest = (paths.PLUGIN_ROOT / "plugin.yaml").read_text()
        declared = [
            line.strip()[2:]
            for line in manifest.split("provides_tools:")[1].splitlines()
            if line.strip().startswith("- ")
        ]
        engine = [s["name"] for s in contracts.hermes_schemas()]
        # plugin-owned tools first, then the engine's in pinned order (the set itself is checked by test_lockstep)
        self.assertEqual(declared[-len(engine) :], engine)
        self.assertEqual(len(set(declared)), len(declared))

    def test_bundled_engine_matches_its_manifest(self):
        check = paths.verify_engine()
        self.assertTrue(check["verified"], check)
        self.assertEqual(check["version"], paths.ENGINE_VERSION)

    def test_the_broker_fingerprint_covers_sub_packages_but_not_caches(self):
        # A running broker is retired when any backend source changes, including future sub-packages.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for rel in ("broker.py", "host/rpc.py", "host/__pycache__/rpc.cpython-314.py", "notes.txt"):
                (folder / rel).parent.mkdir(parents=True, exist_ok=True)
                (folder / rel).write_text("# x\n")
            self.assertEqual([rel for rel, _path in paths.backend_sources(folder)], ["broker.py", "host/rpc.py"])
        every = [rel for rel, _path in paths.backend_sources(paths.BACKEND_ROOT)]
        self.assertEqual(paths.BACKEND_ROOT, paths.PLUGIN_ROOT / "backend")
        self.assertIn("system/paths.py", every)
        self.assertIn("broker/__main__.py", every)

    def test_the_linux_capture_ffmpeg_builds_are_not_shipped(self):
        # LGPL builds from a source that is not public: left out, and the engine still verifies without them.
        for rel in paths.CAPTURE_FFMPEG:
            self.assertFalse((paths.ENGINE_ROOT / rel).exists(), rel)
            self.assertIn(rel, paths._recorded(), "still recorded, so a copy that has them is checked")


class ResultTests(unittest.TestCase):
    def test_denial_is_reported_as_not_dispatched(self):
        out = json.loads(
            results.encode(
                {"ok": False, "dispatched": False, "denied": {"code": "HARDWARE_DISABLED", "message": "off"}},
                "t",
                None,
                False,
            )
        )
        self.assertEqual(out, {"error": "off", "code": "HARDWARE_DISABLED", "dispatched": False})

    def test_unknown_outcome_warns_against_repeating(self):
        out = json.loads(
            results.encode(
                {"ok": False, "dispatched": True, "outcome": "unknown", "error": "timeout"}, "t", None, False
            )
        )
        self.assertEqual(out["code"], "OUTCOME_UNKNOWN")
        self.assertTrue(out["dispatched"])
        self.assertIn("do not simply repeat", out["guidance"])

    def test_structured_content_and_engine_error_are_preserved(self):
        raw = {
            "content": [{"type": "text", "text": "{...}"}],
            "isError": True,
            "structuredContent": {"error": "Project variables changed", "code": "STALE_RESOURCE"},
        }
        out = json.loads(results.encode({"ok": True, "result": raw}, "t", None, False))
        self.assertTrue(out["isError"])
        self.assertEqual(out["code"], "STALE_RESOURCE")
        self.assertEqual(out["structuredContent"], raw["structuredContent"])

    def test_images_are_saved_content_addressed_and_attached_unchanged(self):
        raw = {
            "content": [
                {"type": "text", "text": "Completed (frame: 150)."},
                {"type": "image", "mimeType": "image/png", "data": PNG},
            ],
            "structuredContent": {"frame": 150},
        }
        with tempfile.TemporaryDirectory() as tmp:
            envelope = results.encode({"ok": True, "result": raw, "notice": "worker restarted"}, "t", Path(tmp), True)
            self.assertTrue(envelope["_multimodal"])
            text = json.loads(envelope["content"][0]["text"])
            digest = hashlib.sha256(base64.b64decode(PNG)).hexdigest()
            self.assertEqual(text["images"][0]["sha256"], digest)
            saved = Path(text["images"][0]["file"].removeprefix("MEDIA:"))
            self.assertEqual(saved.read_bytes(), base64.b64decode(PNG))
            self.assertEqual(envelope["content"][1]["image_url"]["url"], "data:image/png;base64," + PNG)
            self.assertEqual(text["notice"], "worker restarted")
            self.assertEqual(text["structuredContent"], {"frame": 150})

    def test_a_build_with_a_ready_player_opens_nothing_and_points_at_present_game(self):
        response = {
            "ok": True,
            "result": {
                "content": [{"type": "text", "text": "Completed."}],
                "structuredContent": {"success": True, "outputPath": "/g/build/game.gb"},
            },
            "player": {"ready": True, "url": "http://127.0.0.1:4000/secret/", "first": True},
            # An older host still adding the Studio address: it is no longer passed on.
            "studio": {"gameId": "abcdefabcdef", "playerUrl": "http://127.0.0.1:5000/tok/abcdefabcdef/index.html"},
        }
        payload = json.loads(results.encode(response, "chromatic_rom_build", None, False))
        for gone in ("studio", "studioPlayerUrl", "studioGameId"):
            self.assertNotIn(gone, payload)
        self.assertNotIn("127.0.0.1", json.dumps(payload))  # neither the engine's nor the Studio's address
        self.assertTrue(payload["player"]["ready"])
        step = payload["nextStep"]
        for needed in (
            "chromatic_present_game",
            "Do not use desktop_preview",
            "cannot see the emulator",
            "studio.playerUrl",
            "Install on Chromatic",
        ):
            self.assertIn(needed, step)
        self.assertNotIn("by itself", step)
        self.assertNotIn("without being asked", step)
        self.assertEqual(payload["structuredContent"]["outputPath"], "/g/build/game.gb")

    def test_an_opened_web_preview_also_points_at_present_game(self):
        preview = {"ok": True, "result": {"content": [], "structuredContent": {"success": True, "url": "http://e/"}}}
        payload = json.loads(results.encode(preview, "chromatic_web_preview", None, False))
        self.assertIn("call chromatic_present_game", payload["nextStep"])
        self.assertNotIn("studioPlayerUrl", payload)

    def test_the_prompt_section_describes_presenting_not_auto_open(self):
        from backend.hermes import host as hermes_host

        section = hermes_host.SYSTEM_PROMPT_SECTION
        self.assertLessEqual(len(section), 2000)
        self.assertIn("chromatic_present_game", section)
        self.assertIn("Nothing opens for the user after a build", section)
        self.assertNotIn("by itself", section)

    def test_a_player_that_could_not_be_refreshed_is_reported_not_hidden(self):
        response = {
            "ok": True,
            "result": {"content": [], "structuredContent": {"success": True}},
            "player": {"ready": False, "error": "export failed"},
        }
        payload = json.loads(results.encode(response, "chromatic_rom_build", None, False))
        self.assertEqual(payload["player"], {"ready": False, "error": "export failed"})
        self.assertNotIn("nextStep", payload)

    def test_images_fall_back_to_files_when_the_route_takes_no_images(self):
        raw = {"content": [{"type": "image", "mimeType": "image/png", "data": PNG}]}
        with tempfile.TemporaryDirectory() as tmp:
            out = results.encode({"ok": True, "result": raw}, "t", Path(tmp), False)
            self.assertIsInstance(out, str)
            self.assertIn("saved to the listed files", json.loads(out)["imageDelivery"])


if __name__ == "__main__":
    unittest.main()
