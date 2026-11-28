// engine/src/build.js: what a build reads is a .gbsproj inside the project's folder, however the path is written.
import assert from "node:assert/strict";
import { mkdtemp, realpath, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { resolveProjectBuildInput } from "../../engine/src/build.js";
import { copyStarter } from "./support.mjs";

test("the project file inside the folder resolves to its real path", async (t) => {
  const project = await copyStarter(t);
  const root = path.dirname(project);
  assert.equal(await resolveProjectBuildInput(root, "project.gbsproj"), await realpath(project));
  assert.equal(await resolveProjectBuildInput(root, "./assets/../project.gbsproj"), await realpath(project));
});

test("a path out of the folder, written or through a link, is refused", async (t) => {
  const project = await copyStarter(t);
  const root = path.dirname(project);
  const outside = await mkdtemp(path.join(tmpdir(), "hermretro-engine-outside-"));
  t.after(() => rm(outside, { recursive: true, force: true }));
  await writeFile(path.join(outside, "other.gbsproj"), "{}");
  await assert.rejects(resolveProjectBuildInput(root, "../other.gbsproj"), /escapes the project root/);
  await assert.rejects(resolveProjectBuildInput(root, path.join(outside, "other.gbsproj")), /escapes the project root/);
  await symlink(path.join(outside, "other.gbsproj"), path.join(root, "linked.gbsproj"));
  await assert.rejects(resolveProjectBuildInput(root, "linked.gbsproj"), /resolves outside the project root/);
});

test("a file that is not a .gbsproj, or a path with a NUL, is refused", async (t) => {
  const project = await copyStarter(t);
  const root = path.dirname(project);
  await assert.rejects(resolveProjectBuildInput(root, "README.md"), /must be a \.gbsproj file/);
  await assert.rejects(resolveProjectBuildInput(root, "project.gbsproj\0"), TypeError);
});
