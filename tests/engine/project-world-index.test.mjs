// engine/src/project-world-index.js: what a project's events mean can change with its plugins/ files, so every
// change to them moves the semantic generation an edit checks against, and putting the old bytes back moves it
// again: an edit prepared before is stale either way, never current again. Each step asks for the full rescan
// (strongRefresh) rather than waiting on the folder watcher, whose events reach macOS later than Linux.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { ProjectWorldIndex } from "../../engine/src/project-world-index.js";
import { copyStarter } from "./support.mjs";

test("editing a plugin file and putting it back leaves the earlier semantic generation stale", async (t) => {
  const project = await copyStarter(t);
  const index = new ProjectWorldIndex(project, 1, {});
  t.after(() => index.dispose());
  await index.ensureFresh();
  const first = index.semanticGeneration;
  const plugin = path.join(path.dirname(project), "plugins", "README.md");
  const original = await readFile(plugin, "utf8");

  await writeFile(plugin, `${original}\nedited\n`);
  await index.strongRefresh();
  const edited = index.semanticGeneration;
  assert.ok(edited > first, `the edit moves it (${first} to ${edited})`);

  await writeFile(plugin, original);
  await index.strongRefresh();
  assert.ok(index.semanticGeneration > edited, `putting it back moves it again (${edited} to ${index.semanticGeneration})`);
  assert.notEqual(index.semanticGeneration, first, "the same bytes again are not the first generation again");
});

test("a file outside plugins/ that no event reads leaves the semantic generation where it was", async (t) => {
  const project = await copyStarter(t);
  const index = new ProjectWorldIndex(project, 1, {});
  t.after(() => index.dispose());
  await index.ensureFresh();
  const first = index.semanticGeneration;
  await writeFile(path.join(path.dirname(project), "README.md"), "a note\n");
  await index.strongRefresh();
  assert.equal(index.semanticGeneration, first);
});
