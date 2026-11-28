// engine/src/project-snapshot.js: a project's revision, which every edit names to prove it read the latest project
// (scene-batch.test.mjs), stays put while nothing authored changes and moves when anything does.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { loadProjectSnapshot, projectRevision } from "../../engine/src/project-snapshot.js";
import { copyStarter } from "./support.mjs";

test("the revision is the same on every read of an unchanged project", async (t) => {
  const project = await copyStarter(t);
  const first = await projectRevision(project);
  assert.match(first, /^[0-9a-f]{64}$/);
  assert.equal(await projectRevision(project), first);
  assert.equal((await loadProjectSnapshot(project)).revision, first);
});

test("the revision moves when an authored file changes, and again when it is put back", async (t) => {
  const project = await copyStarter(t);
  const settings = path.join(path.dirname(project), "project", "settings.gbsres");
  const original = await readFile(settings, "utf8");
  const before = await projectRevision(project);
  await writeFile(settings, JSON.stringify({ ...JSON.parse(original), hermretroTest: true }, null, 2));
  const changed = await projectRevision(project);
  assert.notEqual(changed, before);
  await writeFile(settings, original);
  assert.equal(await projectRevision(project), before, "the same files give the same revision");
});
