"""The loopback player server: the assembled frame page, engine files, captures and headers."""

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from backend.player import server as player_server  # noqa: E402 - the repository root goes on sys.path first
from backend.library import rpcs as library_rpcs  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
INDEX = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="css/style.css" />
    <title>Test Game</title>
  </head>
  <body>
    <div id="game"><canvas id="mainCanvas" width="256" height="224"></canvas></div>
    <script src="js/binjgb.js"></script>
    <script src="js/script.js"></script>
    <script src="js/debugger.js"></script>
</body>
</html>
"""


def make_export(base: Path) -> Path:
    root = base / "test-game"
    web = root / "build" / "web"
    for folder in ("js", "css", "rom"):
        (web / folder).mkdir(parents=True)
    (root / "test-game.gbsproj").write_text(json.dumps({"name": "Test Game"}))
    (web / "index.html").write_text(INDEX)
    (web / "gbstudio.json").write_text(json.dumps({"rom": "rom/test.gbc", "project": {"name": "Test Game"}}))
    (web / "rom" / "test.gbc").write_bytes(bytes(range(256)) * 4)
    (web / "js" / "binjgb.wasm").write_bytes(b"\0asm\1\0\0\0")
    (web / "js" / "script.js").write_text("// game")
    (web / "css" / "style.css").write_text("body{}")
    (web / ".codex-web-build.json").write_text(json.dumps({"sourceRevision": "rev-123"}))
    return root


def fetch(url, method="GET", data=None, headers=None):
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.headers, error.read()


def multipart(fields):
    boundary = "----cs" + uuid.uuid4().hex
    body = b""
    for name, value, filename, kind in fields:
        disposition = f'form-data; name="{name}"' + (f'; filename="{filename}"' if filename else "")
        body += f"--{boundary}\r\nContent-Disposition: {disposition}\r\n".encode()
        body += (f"Content-Type: {kind}\r\n" if kind else "").encode() + b"\r\n" + value + b"\r\n"
    return body + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


class LoopbackStart(unittest.TestCase):
    def test_the_server_starts_without_looking_its_address_up(self):
        # HTTPServer.server_bind calls socket.getfqdn("127.0.0.1"), a reverse DNS lookup that took about 35 s on
        # GitHub's Apple Silicon runners: a Mac's first "show the game" waited on it.
        with mock.patch("socket.getfqdn", side_effect=AssertionError("the player server looked its address up")):
            server = player_server.PlayerServer(lambda _identifier: None)
        self.addCleanup(server.close)
        status, _headers, _body = fetch(server.base("missing") + "index.html")
        self.assertEqual(status, 404)


class PlayerServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = make_export(Path(cls.tmp.name))
        cls.gid = games.game_id(cls.root)
        cls.server = player_server.get_server(lambda i: cls.root if i == cls.gid else None)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def url(self, rel):
        return self.server.base(self.gid) + rel

    def index(self):
        status, headers, body = fetch(self.server.url(self.gid))
        self.assertEqual(status, 200)
        html = body.decode()
        context = json.loads(re.search(r'id="codex-web-annotations-context">(.*?)</script>', html).group(1))
        return html, context

    def assert_common_headers(self, headers):
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_url_shape(self):
        self.assertRegex(self.server.url(self.gid), rf"^http://127\.0\.0\.1:\d+/[0-9a-f]{{64}}/{self.gid}/index\.html$")

    def test_frame_page_has_shim_first_bootstrap_before_script_and_bridge_last(self):
        html, context = self.index()
        head = html.index("<head>")
        self.assertLess(html.index("document.oai"), html.index('<meta charset'))
        self.assertGreater(html.index("document.oai"), head)
        # The shim keeps the handheld's finish in memory, under the player's key, Midnight by default.
        self.assertIn('installStorage(params, "hermes-midnight", "codex-gb-studio:device-color:v1")', html)
        self.assertNotIn("__COLOR_KEY__", html)
        # The handheld fills the frame: sized by the frame's height (850:1440 device) and capped by its width,
        # instead of the engine's fixed 420 px.
        self.assertIn("min(calc((100svh - 136px)*850/1440),calc(100vw - 112px))", html)
        boot = html.index("installInputOwner")
        self.assertLess(html.index('src="js/binjgb.js"'), boot)
        self.assertLess(boot, html.index('src="js/script.js"'))
        self.assertIn(f"./codex-annotations/binjgb-{context['runtimeSha256']}.wasm", html)
        self.assertLess(html.index('src="./codex-annotations/bridge.js"'), html.rindex("</body>"))
        rom = (self.root / "build/web/rom/test.gbc").read_bytes()
        self.assertEqual(context["romSha256"], hashlib.sha256(rom).hexdigest())
        self.assertEqual(context["romPath"], "rom/test.gbc")
        self.assertEqual(context["sourceRevision"], "rev-123")
        self.assertRegex(context["captures"]["generation"], r"^[a-f0-9]{32}$")

    def test_engine_modules_wasm_and_device_art(self):
        status, headers, body = fetch(self.url("codex-annotations/bridge.js"))
        self.assertEqual((status, headers["Content-Type"]), (200, "text/javascript; charset=utf-8"))
        self.assert_common_headers(headers)
        status, _headers, body = fetch(self.url("codex-annotations/view.js"))
        self.assertEqual(status, 200)
        text = body.decode()
        self.assertLess(text.index('id: "hermes-midnight"'), text.index('id: "codex"'))
        for finish in (
            "Hermes Edition · Midnight",
            "Hermes Edition · Nous Blue",
            "Hermes Edition · White",
            "Hermes Edition · Clear Blue",
        ):
            self.assertIn(finish, text)
        status, headers, body = fetch(self.url("codex-annotations/chromatic-hermes-midnight.webp"))
        self.assertEqual((status, headers["Content-Type"], body[:4], body[8:12]), (200, "image/webp", b"RIFF", b"WEBP"))
        status, headers, body = fetch(self.url("js/binjgb.wasm"))
        self.assertEqual((status, headers["Content-Type"]), (200, "application/wasm"))
        self.assert_common_headers(headers)
        wasm_sha = hashlib.sha256(body).hexdigest()
        self.assertEqual(fetch(self.url(f"codex-annotations/binjgb-{wasm_sha}.wasm"))[0], 200)
        self.assertEqual(fetch(self.url(f"codex-annotations/binjgb-{'0' * 64}.wasm"))[0], 404)

    def test_paths_stay_inside_the_export(self):
        for rel in (
            "../../../etc/passwd",
            "js/../../../test-game.gbsproj",
            ".codex-web-build.json",
            "%2e%2e/%2e%2e/test-game.gbsproj",
            "codex-annotations/../index.html",
            "nothing.js",
        ):
            self.assertIn(fetch(self.url(rel))[0], (400, 404), rel)
        self.assertEqual(fetch(self.url("css/style.css"))[0], 200)
        port_url = self.server.url(self.gid)
        self.assertEqual(fetch(port_url.replace(self.server.token, "f" * 64))[0], 404)
        self.assertEqual(fetch(port_url.replace(self.gid, "000000000000"))[0], 404)
        self.assertEqual(fetch(port_url, headers={"Host": "evil.example"})[0], 403)

    def test_capture_round_trip_matches_what_the_player_checks(self):
        _html, context = self.index()
        media = PNG + b"\r\n--tail\r\n\x00\xff"
        body, kind = multipart(
            [
                ("kind", b"screenshot", None, None),
                ("metadata", json.dumps({"width": 160}).encode(), None, None),
                ("media", media, "screenshot.png", "image/png"),
            ]
        )
        headers = {"Content-Type": kind, "x-codex-preview-capture": context["captures"]["generation"]}
        status, response_headers, raw = fetch(self.url("codex-captures"), "POST", body, headers)
        self.assertEqual(status, 200, raw)
        self.assert_common_headers(response_headers)
        receipt = json.loads(raw)
        self.assertRegex(receipt["id"], r"^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$")
        self.assertEqual(
            (receipt["kind"], receipt["bytes"], receipt["sha256"]),
            ("screenshot", len(media), hashlib.sha256(media).hexdigest()),
        )
        self.assertEqual(receipt["url"], f"./codex-captures/{receipt['id']}/media")
        self.assertEqual(receipt["metadataUrl"], f"./codex-captures/{receipt['id']}/metadata")
        self.assertRegex(Path(receipt["path"]).name, r"^\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d-\d{3}Z-screenshot\.png$")
        self.assertEqual(Path(receipt["path"]).parent, self.root / "captures")
        self.assertEqual(Path(receipt["path"]).read_bytes(), media)
        self.assertEqual(receipt["metadataPath"], receipt["path"] + ".json")
        status, headers, raw = fetch(self.url(receipt["url"][2:]))
        self.assertEqual((status, headers["Content-Type"], raw), (200, "image/png", media))
        status, _headers, raw = fetch(self.url(receipt["metadataUrl"][2:]))
        self.assertEqual(json.loads(raw)["metadata"], {"width": 160})
        listed = player_server.list_captures(self.root, self.gid)
        self.assertIn(receipt["id"], [c["id"] for c in listed])
        stale = {**headers, "Content-Type": kind, "x-codex-preview-capture": "0" * 32}
        self.assertEqual(fetch(self.url("codex-captures"), "POST", body, stale)[0], 409)

    def test_states_device_and_preflight(self):
        status, headers, raw = fetch(self.url("codex-states"))
        self.assertEqual((status, json.loads(raw)), (200, {"states": []}))
        status, headers, raw = fetch(
            self.url("codex-device"),
            "POST",
            json.dumps({"action": "observe", "generation": "g"}).encode(),
            {"Content-Type": "application/json"},
        )
        answer = json.loads(raw)
        self.assertEqual((answer["available"], answer["devices"], answer["generation"]), (False, [], "g"))
        status, headers, _raw = fetch(
            self.url("codex-captures"),
            "OPTIONS",
            None,
            {
                "Origin": "null",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-codex-preview-capture",
            },
        )
        self.assertEqual(status, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("POST", headers["Access-Control-Allow-Methods"])
        self.assertEqual(headers["Access-Control-Allow-Headers"], "x-codex-preview-capture")


class Pieces(unittest.TestCase):
    def test_frame_shim_is_valid_javascript_with_its_placeholders_filled(self):
        shim = player_server.frame_shim()
        self.assertNotIn("__DEFAULT_COLOR__", shim)
        self.assertNotIn("__COLOR_KEY__", shim)
        self.assertNotIn("</script", shim)
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not installed")
        check = subprocess.run(
            [node, "--check", str(paths.PLUGIN_ROOT / "player" / "frame-shim.js")], capture_output=True, text=True
        )
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_view_without_its_anchor_is_served_unpatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            view = Path(tmp) / "view.js"
            view.write_text("export const COLORS = [];\n")
            with self.assertLogs(player_server.logger, "WARNING"):
                self.assertEqual(player_server.patched_view(view), b"export const COLORS = [];\n")

    def test_an_export_without_the_official_player_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_export(Path(tmp))
            (root / "build/web/index.html").write_text("<html><body></body></html>")
            build = player_server.game_build(root)
            with self.assertRaises(player_server.PlayerError):
                player_server.frame_document(root, build, "0" * 32)


class PlayerRpcs(unittest.TestCase):
    def setUp(self):
        base = isolated_home(self).base  # resolved (macOS: /var is a link to /private/var)
        patch = mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None))
        patch.start()
        self.addCleanup(patch.stop)
        self.root = make_export(base)
        self.gid = games.Registry(paths.library_dir()).upsert(str(self.root))["id"]
        self.ctx = mock.Mock()

    def test_player_rpc_returns_a_working_url(self):
        answer = library_rpcs.rpc_player(self.ctx)({"id": self.gid})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(answer["title"], "Test Game")
        self.assertEqual(fetch(answer["url"])[0], 200)
        rom = (self.root / "build/web/rom/test.gbc").read_bytes()
        self.assertEqual(answer["romSha256"], hashlib.sha256(rom).hexdigest())

    def test_player_rpc_explains_a_missing_web_build(self):
        (self.root / "build/web/js/binjgb.wasm").unlink()
        answer = library_rpcs.rpc_player(self.ctx)({"id": self.gid})
        self.assertFalse(answer["ok"])
        self.assertIn("chat", answer["error"])
        self.assertFalse(library_rpcs.rpc_player(self.ctx)({"id": "nope"})["ok"])

    def test_capture_image_then_captures_lists_it_with_a_loopback_url(self):
        saved = library_rpcs.rpc_capture_image(self.ctx)(
            {"id": self.gid, "png": "data:image/png;base64," + base64.b64encode(PNG).decode()}
        )
        self.assertTrue(saved["ok"], saved)
        self.assertEqual(Path(saved["path"]).parent, self.root / "captures")
        listed = library_rpcs.rpc_captures(self.ctx)({"id": self.gid})["captures"]
        self.assertEqual([c["path"] for c in listed], [saved["path"]])
        self.assertEqual(listed[0]["kind"], "annotation")
        self.assertRegex(
            listed[0]["url"],
            rf"^http://127\.0\.0\.1:\d+/[0-9a-f]{{64}}/{self.gid}/codex-captures/"
            r"[0-9a-f-]{36}/media$",
        )
        status, _headers, body = fetch(listed[0]["url"])
        self.assertEqual((status, body), (200, PNG))
        self.assertFalse(library_rpcs.rpc_capture_image(self.ctx)({"id": self.gid, "png": "data:text/plain,hi"})["ok"])

    def test_captures_list_the_newest_first(self):
        # The sidecar's createdAt decides the order, not the file name or the folder's order.
        folder = player_server.captures_dir(self.root, self.gid)
        folder.mkdir()
        for name, created in (
            ("b.png", "2026-01-02T00:00:00.000Z"),
            ("a.png", "2026-03-01T00:00:00.000Z"),
            ("c.png", "2026-02-01T00:00:00.000Z"),
        ):
            (folder / name).write_bytes(PNG)
            (folder / f"{name}.json").write_text(json.dumps({"kind": "screenshot", "createdAt": created}))
        listed = library_rpcs.rpc_captures(self.ctx)({"id": self.gid})["captures"]
        self.assertEqual([Path(c["path"]).name for c in listed], ["a.png", "c.png", "b.png"])
        self.assertEqual(listed[0]["createdAt"], "2026-03-01T00:00:00.000Z")


class DemoCartridge(unittest.TestCase):
    """The built-in demo: the bundled player plus the engine's hello-color ROM, with no project."""

    def setUp(self):
        self.base = isolated_home(self).base
        patch = mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None))
        patch.start()
        self.addCleanup(patch.stop)
        self.ctx = mock.Mock()
        self.ctx.get_config.return_value = False

    def test_player_rpc_opens_the_demo_by_id_and_without_one(self):
        rom = paths.ENGINE_ROOT / "examples/hello-color/hello-color.gbc"
        for params in ({"id": "demo"}, {}, None):
            answer = library_rpcs.rpc_player(self.ctx)(params)
            self.assertTrue(answer["ok"], answer)
            self.assertEqual((answer["title"], answer["demo"]), ("Hello Color", True))
            self.assertRegex(answer["url"], r"^http://127\.0\.0\.1:\d+/[0-9a-f]{64}/demo/index\.html$")
            self.assertEqual(answer["romSha256"], hashlib.sha256(rom.read_bytes()).hexdigest())

    def test_demo_serves_index_runtime_and_rom_to_any_origin(self):
        url = library_rpcs.rpc_player(self.ctx)({"id": "demo"})["url"]
        base = url[: -len("index.html")]
        status, headers, body = fetch(url)
        self.assertEqual((status, headers["Access-Control-Allow-Origin"]), (200, "*"))
        html = body.decode()
        self.assertIn("<title>Hello Color</title>", html)
        self.assertNotIn("___", html)
        self.assertLess(html.index("codex-gb-studio:device-color:v1"), html.index("js/script.js"))
        context = json.loads(re.search(r'id="codex-web-annotations-context">(.*?)</script>', html).group(1))
        self.assertEqual(context["romPath"], "rom/hello-color.gbc")
        wasm = (paths.PLUGIN_ROOT / "player/web/js/binjgb.wasm").read_bytes()
        self.assertEqual(context["runtimeSha256"], hashlib.sha256(wasm).hexdigest())
        for rel, kind, expected in (
            ("js/binjgb.wasm", "application/wasm", wasm),
            (f"codex-annotations/binjgb-{context['runtimeSha256']}.wasm", "application/wasm", wasm),
            (
                "rom/hello-color.gbc",
                "application/octet-stream",
                (paths.ENGINE_ROOT / "examples/hello-color/hello-color.gbc").read_bytes(),
            ),
        ):
            status, headers, body = fetch(base + rel)
            self.assertEqual(
                (status, headers["Content-Type"], headers["Access-Control-Allow-Origin"]), (200, kind, "*"), rel
            )
            self.assertEqual(body, expected, rel)
        status, _headers, body = fetch(base + "gbstudio.json")
        config = json.loads(body)
        self.assertEqual((status, config["rom"]), (200, "rom/hello-color.gbc"))
        self.assertEqual(config["customControls"]["start"], ["Enter"])
        self.assertEqual(fetch(base + "../demo/index.html")[0] in (400, 404), True)

    def test_demo_captures_go_to_the_library_folder(self):
        png = "data:image/png;base64," + base64.b64encode(PNG).decode()
        saved = library_rpcs.rpc_capture_image(self.ctx)({"id": "demo", "png": png})
        self.assertTrue(saved["ok"], saved)
        self.assertEqual(Path(saved["path"]).parent, paths.library_dir() / "captures" / "demo")
        listed = library_rpcs.rpc_captures(self.ctx)({"id": "demo"})["captures"]
        self.assertEqual([c["path"] for c in listed], [saved["path"]])
        self.assertEqual(fetch(listed[0]["url"])[2], PNG)

    def test_games_reports_the_demo_beside_but_not_inside_the_library(self):
        answer = library_rpcs.rpc_games(self.ctx)({})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(answer["games"], [])
        self.assertEqual(
            answer["demo"], {"id": "demo", "title": "Hello Color", "kind": "gbdk", "note": "ModRetro example"}
        )
        self.assertNotIn("url", answer["demo"])

    def test_a_user_game_without_a_web_export_still_errors(self):
        root = make_export(self.base)
        (root / "build/web/index.html").unlink()
        gid = games.Registry(paths.library_dir()).upsert(str(root))["id"]
        answer = library_rpcs.rpc_player(self.ctx)({"id": gid})
        self.assertFalse(answer["ok"])
        self.assertIn("no playable build", answer["error"])


if __name__ == "__main__":
    unittest.main()
