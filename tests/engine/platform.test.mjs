// engine/src/platform.js: containment and path safety by each system's own rules, Windows' included (the engine
// keeps its Windows support), whatever system the test runs on.
import assert from "node:assert/strict";
import test from "node:test";

import { assertSafePlatformPath, isPathWithinRoot } from "../../engine/src/platform.js";

test("a path is within its root only when it resolves inside it (POSIX)", () => {
  for (const inside of ["/games/a", "/games/a/b.gbsproj", "/games/a/./b/../c"]) {
    assert.equal(isPathWithinRoot("/games/a", inside, "linux"), true, inside);
  }
  for (const outside of ["/games/ab", "/games/a/../b", "/etc/passwd", "../b"]) {
    assert.equal(isPathWithinRoot("/games/a", outside, "linux"), false, outside);
  }
  assert.equal(isPathWithinRoot("relative/root", "relative/root/x", "darwin"), false, "a relative root contains nothing");
});

test("on Windows, containment ignores case and either separator", () => {
  assert.equal(isPathWithinRoot("C:\\Games\\A", "c:/games/a/b.gbsproj", "win32"), true);
  assert.equal(isPathWithinRoot("C:\\Games\\A", "C:\\Games\\AB", "win32"), false);
  assert.equal(isPathWithinRoot("C:\\Games\\A", "D:\\Games\\A", "win32"), false);
});

test("Windows paths that name devices, streams, shares or reserved names are refused", () => {
  for (const unsafe of ["\\\\server\\share\\x", "C:relative", "C:\\a\\file.txt:stream", "C:\\a\\CON", "C:\\a\\b.", "C:\\a\\b?"]) {
    assert.throws(() => assertSafePlatformPath(unsafe, "win32"), TypeError, unsafe);
  }
  assert.doesNotThrow(() => assertSafePlatformPath("C:\\Games\\a\\b.gbsproj", "win32"));
  assert.doesNotThrow(() => assertSafePlatformPath("odd:name?", "linux"), "other systems allow what Windows reserves");
  assert.throws(() => assertSafePlatformPath("a\0b", "linux"), TypeError);
});
