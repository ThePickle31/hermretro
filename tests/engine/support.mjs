// What the engine's tests share: a private copy of an example project, and a project's files as they are on disk.
import { createHash } from "node:crypto";
import { cp, mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const EXAMPLES = fileURLToPath(new URL("../../engine/examples/", import.meta.url));

/** The starter example copied into a new temporary folder, removed after the test: its project file's path. */
export async function copyStarter(t) {
  const folder = await mkdtemp(path.join(tmpdir(), "hermretro-engine-test-"));
  t.after(() => rm(folder, { recursive: true, force: true }));
  await cp(path.join(EXAMPLES, "starter"), folder, { recursive: true });
  return path.join(folder, "project.gbsproj");
}

/** Every file under the project's folder: its path from there, mapped to its text (or its SHA-256 when binary). */
export async function projectFiles(project) {
  const root = path.dirname(project);
  const files = new Map();
  for (const entry of await readdir(root, { recursive: true, withFileTypes: true })) {
    if (!entry.isFile()) continue;
    const full = path.join(entry.parentPath, entry.name);
    const bytes = await readFile(full);
    const text = bytes.toString("utf8");
    files.set(path.relative(root, full), text.includes("�") ? createHash("sha256").update(bytes).digest("hex") : text);
  }
  return new Map([...files].sort(([a], [b]) => a.localeCompare(b)));
}
