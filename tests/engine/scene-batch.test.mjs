// engine/src/scene-batch.js: a scene batch applies all of its operations or none, against the revision it names.
import assert from "node:assert/strict";
import { chmod, mkdir, readdir } from "node:fs/promises";
import path from "node:path";
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

test("a write that fails after an earlier one landed rolls the earlier one back", async (t) => {
  // The actor is written under actors/, then the trigger under triggers/, which cannot be written. A process that may
  // write anywhere (root) ignores the folder's mode, so the failure cannot be made there.
  if (process.getuid?.() === 0) return t.skip("root writes into a read-only folder");
  const { project, sceneId } = await starterScene(t);
  const triggers = path.join(path.dirname(project), "project", "scenes", "start", "triggers");
  await mkdir(triggers);
  await chmod(triggers, 0o555); // empty, so the copy's removal still takes it (that needs only its parent's mode)
  const before = await projectFiles(project);
  await assert.rejects(
    applySceneBatch(project, {
      sceneId,
      operations: [
        { type: "actor.create", name: "Rolled Back", x: 2, y: 2 },
        { type: "trigger.create", name: "Unwritable", x: 4, y: 4, width: 2, height: 2 },
      ],
    }),
    { code: "TRANSACTION_COMMIT_FAILED", message: /triggers\/\.unwritable\.gbsres/ },
  );
  // The folder the actor's write made is left, empty: the actor was written before the trigger failed, then removed.
  assert.deepEqual(await readdir(path.join(path.dirname(triggers), "actors")), []);
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
