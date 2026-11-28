// engine/src/scene-batch.js: a scene batch applies all of its operations or none, against the revision it names.
import assert from "node:assert/strict";
import test from "node:test";

import { applySceneBatch } from "../../engine/src/scene-batch.js";
import { loadProjectSnapshot } from "../../engine/src/project-snapshot.js";
import { copyStarter, projectFiles } from "./support.mjs";

async function starterScene(t) {
  const project = await copyStarter(t);
  const snapshot = await loadProjectSnapshot(project);
  const [sceneId] = snapshot.scenesById.keys();
  return { project, sceneId, revision: snapshot.revision };
}

test("a batch whose later operation fails leaves every file as it was", async (t) => {
  const { project, sceneId } = await starterScene(t);
  const before = await projectFiles(project);
  await assert.rejects(
    applySceneBatch(project, {
      sceneId,
      operations: [
        { type: "actor.create", name: "Kept Out", x: 2, y: 2 },
        { type: "actor.update", actorId: "no-such-actor", x: 3 },
      ],
    }),
    { code: "ACTOR_NOT_FOUND" },
  );
  assert.deepEqual(await projectFiles(project), before);
});

test("a batch against a stale revision writes nothing", async (t) => {
  const { project, sceneId } = await starterScene(t);
  const before = await projectFiles(project);
  await assert.rejects(
    applySceneBatch(project, {
      sceneId,
      expectedRevision: "0".repeat(64),
      operations: [{ type: "actor.create", name: "Too Late", x: 2, y: 2 }],
    }),
    { code: "STALE_PROJECT_REVISION" },
  );
  assert.deepEqual(await projectFiles(project), before);
});

test("a batch that succeeds writes its actor and moves the revision", async (t) => {
  const { project, sceneId, revision } = await starterScene(t);
  const before = await projectFiles(project);
  const result = await applySceneBatch(project, {
    sceneId,
    expectedRevision: revision,
    operations: [{ type: "actor.create", name: "Written", x: 2, y: 2 }],
  });
  const after = await projectFiles(project);
  const added = [...after.keys()].filter((name) => !before.has(name));
  assert.equal(added.length, 1, `one new file, not ${added.join(", ")}`);
  assert.match(JSON.stringify(JSON.parse(after.get(added[0]))), /"name":"Written"/);
  assert.notEqual((await loadProjectSnapshot(project)).revision, revision);
  assert.ok(result);
});
