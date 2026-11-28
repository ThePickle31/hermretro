// engine/src/project-snapshot.js: a project's inventory names what its files hold, and its revision, which every edit
// names to prove it read the latest project (scene-batch.test.mjs), stays put while nothing authored changes and moves
// when anything does.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { inventoryProjectNormalized, loadProjectSnapshot, projectRevision } from "../../engine/src/project-snapshot.js";
import { copyStarter } from "./support.mjs";

async function resource(project, relative) {
  return JSON.parse(await readFile(path.join(path.dirname(project), relative), "utf8"));
}

test("the inventory lists the starter's scene and the background it is drawn on, as their files say", async (t) => {
  const project = await copyStarter(t);
  const scene = await resource(project, "project/scenes/start/scene.gbsres");
  const background = await resource(project, "assets/backgrounds/workshop.png.gbsres");
  const inventory = await inventoryProjectNormalized(project);
  assert.deepEqual(
    inventory.scenes.map(({ id, name, backgroundId }) => ({ id, name, backgroundId })),
    [{ id: scene.id, name: scene.name, backgroundId: background.id }],
  );
  const listed = inventory.assets.find((asset) => asset.id === scene.backgroundId);
  assert.deepEqual(
    { name: listed?.name, type: listed?.type, filename: listed?.filename, resourcePath: listed?.resourcePath },
    { name: background.name, type: "background", filename: "workshop.png", resourcePath: "assets/backgrounds/workshop.png" },
  );
  assert.deepEqual(inventory.diagnostics, []);
  assert.equal(inventory.revision, await projectRevision(project));
});

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
