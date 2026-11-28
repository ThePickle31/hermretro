import { lstat, unlink } from "node:fs/promises";
import path from "node:path";
import {
  projectRelativePath,
  readProjectJsonWithRevision,
  resolveProjectPath,
  resourceRevision,
  resourceSlug,
  stableResourceId,
  withProjectResourceWriteLock,
  writeProjectJsonAtomic,
} from "./project-files.js";
import { GameStudioProjectError, inventoryProject, resolveNativeAssetIdentity } from "./project.js";
import {
  explicitlyPatchedNativeScriptValues,
  findInvalidNativeScriptEvent,
  withNativeScriptEventIds,
} from "./native-script-events.js";
import { isObject } from "./shared/values.js";
const UNSAFE_KEYS = new Set(["__proto__", "prototype", "constructor"]);
export const IMMUTABLE_KEYS = new Set(["id", "_resourceType", "_index", "symbol", "resourcePath"]);
const DIRECTIONS = new Set(["up", "down", "left", "right"]);
const EMITTED_LABEL_SUFFIXES = {
  scene: ["init", "p_hit1", "p_hit2", "p_hit3", "collisions", "actors", "triggers", "sprites", "projectiles"],
  actor: ["interact", "update", "hit1", "hit2", "hit3"],
  trigger: ["interact"],
  script: [],
};
function emittedLabels(kind, symbol) {
  return [symbol, ...EMITTED_LABEL_SUFFIXES[kind].map((suffix) => `${symbol}_${suffix}`)];
}
function symbolOwners(inventory) {
  const owners = [];
  for (const scene of inventory.scenes) {
    owners.push({ kind: "scene", resource: scene, scene });
    for (const actor of scene.actors ?? []) owners.push({ kind: "actor", resource: actor, scene });
    for (const trigger of scene.triggers ?? []) owners.push({ kind: "trigger", resource: trigger, scene });
  }
  for (const script of inventory.scripts ?? []) owners.push({ kind: "script", resource: script });
  return owners.filter((owner) => typeof owner.resource.symbol === "string" && owner.resource.symbol);
}
export function takenResourceSymbols(inventory, exceptId) {
  const taken = new Set();
  for (const { kind, resource } of symbolOwners(inventory)) {
    if (exceptId !== undefined && resource.id === exceptId) continue;
    for (const label of emittedLabels(kind, resource.symbol)) taken.add(label);
  }
  for (const asset of inventory.assets ?? []) {
    if (typeof asset.symbol === "string" && asset.symbol) taken.add(asset.symbol);
  }
  return taken;
}
function symbolAvailable(kind, symbol, taken) {
  return emittedLabels(kind, symbol).every((label) => !taken.has(label));
}
export function uniqueResourceSymbol(kind, name, taken) {
  const base = `${kind}_${resourceSlug(name, kind)}`;
  let symbol = base;
  for (let suffix = 2; !symbolAvailable(kind, symbol, taken); suffix++) symbol = `${base}_${suffix}`;
  return symbol;
}
export function renamedResourceSymbol(kind, previous, next, taken) {
  const current = typeof next.symbol === "string" ? next.symbol : "";
  const sameSlug =
    resourceSlug(String(next.name), kind) ===
    resourceSlug(typeof previous.name === "string" ? previous.name : "", kind);
  return current && sameSlug && symbolAvailable(kind, current, taken)
    ? current
    : uniqueResourceSymbol(kind, next.name, taken);
}
function describeSymbolOwner({ kind, resource, scene }) {
  const owner = `${kind} ${resource.name || resource.id} (id ${resource.id})`;
  return scene && kind !== "scene" ? `${owner} in scene ${scene.name || scene.id}` : owner;
}
function duplicateSymbolAdvice(owners) {
  const renamable = owners.filter((owner) => owner.kind === "actor" || owner.kind === "trigger");
  if (renamable.length === 0) {
    const scenes = owners.filter((owner) => owner.kind === "scene");
    return `Give ${scenes.length === owners.length ? "all but one scene" : "each scene"} its own symbol (scene_update properties.symbol)`;
  }
  const tools = [...new Set(renamable.map((owner) => `${owner.kind}_update name`))].join(" or ");
  if (renamable.length === owners.length) return `Rename all but one (${tools}) to give each its own symbol`;
  return `Rename the ${[...new Set(renamable.map((owner) => owner.kind))].join(" and ")} (${tools}) so each has its own symbol`;
}
export function duplicateSymbolDiagnostics(inventory) {
  const byLabel = new Map();
  for (const owner of symbolOwners(inventory)) {
    for (const label of emittedLabels(owner.kind, owner.resource.symbol)) {
      const owners = byLabel.get(label) ?? [];
      owners.push(owner);
      byLabel.set(label, owners);
    }
  }
  const reported = new Set();
  const diagnostics = [];
  for (const [label, owners] of byLabel) {
    const ownerKey = owners.map((owner) => owner.resource.id).join("\0");
    if (owners.length < 2 || owners.every((owner) => owner.kind === "script") || reported.has(ownerKey)) continue;
    reported.add(ownerKey);
    const shared = owners.every((owner) => owner.resource.symbol === label);
    const listed = owners
      .map((owner) =>
        owner.resource.symbol === label
          ? describeSymbolOwner(owner)
          : `${describeSymbolOwner(owner)} through symbol ${owner.resource.symbol}`,
      )
      .join(", ");
    diagnostics.push({
      severity: "error",
      code: "DUPLICATE_SYMBOL",
      message: shared
        ? `Symbol ${label} is shared by ${listed}; GB Studio compiles them as one. ${duplicateSymbolAdvice(owners)}`
        : `Compiled name ${label} is used by ${listed}; GB Studio writes one over the other. ${duplicateSymbolAdvice(owners)}`,
      resourcePath: owners[owners.length - 1].resource.resourcePath,
    });
  }
  return diagnostics;
}
export function validateResourceName(value, label) {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new GameStudioProjectError("INVALID_INPUT", `${label} must be a non-empty string`);
  }
  return value.trim();
}
/** Validate arrays too: a forbidden key must never be hidden inside an event. */
export function assertSafeResourceProperties(value, label, root = true) {
  if (Array.isArray(value)) {
    for (const child of value) assertSafeResourceProperties(child, label, false);
    return;
  }
  if (!isObject(value)) return;
  for (const [key, child] of Object.entries(value)) {
    if (UNSAFE_KEYS.has(key) || (root && IMMUTABLE_KEYS.has(key))) {
      throw new GameStudioProjectError("INVALID_PROPERTY", reservedPropertyMessage(label, key));
    }
    assertSafeResourceProperties(child, label, false);
  }
}
export function reservedPropertyMessage(label, key) {
  return key === "symbol"
    ? `${label} cannot set symbol: a symbol follows the name, so rename the resource to change it`
    : `${label} cannot modify reserved property ${key}`;
}
export function mergeResourceObjects(existing, changes) {
  const merged = { ...existing };
  for (const [key, value] of Object.entries(changes)) {
    const previous = merged[key];
    merged[key] = isObject(previous) && isObject(value) ? mergeResourceObjects(previous, value) : value;
  }
  return merged;
}
export function findProjectScene(inventory, sceneId) {
  const scene =
    "scene" in inventory ? inventory.scene(sceneId) : inventory.scenes.find((candidate) => candidate.id === sceneId);
  if (!scene) {
    throw new GameStudioProjectError("SCENE_NOT_FOUND", `No scene with id ${sceneId} exists in this project`);
  }
  return scene;
}
export function findSceneActor(scene, actorId, access) {
  const actor = access ? access.actor(scene.id, actorId) : scene.actors.find((candidate) => candidate.id === actorId);
  if (!actor) {
    throw new GameStudioProjectError("ACTOR_NOT_FOUND", `No actor with id ${actorId} exists in scene ${scene.id}`);
  }
  return actor;
}
/** Match the actual distributed actor shape and existing deterministic dialogue IDs. */
export function createActorResource(input, id, index, symbol) {
  const script = [];
  if (input.dialogue !== undefined) {
    script.push({
      id: stableResourceId(id, "script", "0", "EVENT_TEXT"),
      command: "EVENT_TEXT",
      args: { text: input.dialogue, avatarId: "" },
      __type: "event",
    });
  }
  return {
    _resourceType: "actor",
    id,
    _index: index,
    symbol,
    prefabId: "",
    name: validateResourceName(input.name, "Actor name"),
    coordinateType: "tiles",
    x: input.x ?? 0,
    y: input.y ?? 0,
    frame: 0,
    animate: false,
    spriteSheetId: input.spriteSheetId ?? "",
    paletteId: "",
    direction: input.direction ?? "down",
    moveSpeed: 1,
    animSpeed: 15,
    isPinned: false,
    persistent: false,
    collisionGroup: "",
    collisionExtraFlags: [],
    prefabScriptOverrides: {},
    script,
    startScript: [],
    updateScript: [],
    hit1Script: [],
    hit2Script: [],
    hit3Script: [],
  };
}
export function mergeActorChanges(existing, input) {
  if (input.properties !== undefined) {
    if (!isObject(input.properties)) {
      throw new GameStudioProjectError("INVALID_INPUT", "Actor properties must be a JSON object");
    }
    assertSafeResourceProperties(input.properties, "Actor properties");
  }
  const updates = { ...(input.properties ?? {}) };
  for (const field of ["name", "x", "y", "direction", "spriteSheetId"]) {
    const value = input[field];
    if (value !== undefined) updates[field] = field === "name" ? validateResourceName(value, "Actor name") : value;
  }
  return withNativeScriptEventIds(mergeResourceObjects(existing, updates));
}
// GB Studio never reads an actor's paletteId. One kept from before is left alone; a request that gives one (properties)
// or changes it is refused.
export function assertNoActorPalette(actor, previous, properties) {
  const given = (value) => value !== undefined && value !== "";
  if (given(actor.paletteId) && (actor.paletteId !== previous?.paletteId || given(properties?.paletteId))) {
    throw new GameStudioProjectError(
      "ACTOR_PALETTE_UNSUPPORTED",
      "GB Studio never reads an actor's paletteId, so it would change nothing. In color, each sprite tile's paletteIndex picks one of the scene's eight sprite palette slots: import the sprite with asset_import sprite.paletteIndex (0-7), then put the palette in that slot with palette_assign target sprite. Actors that share one sprite share its slot.",
    );
  }
}
/** Check the merged resource so `properties` cannot bypass coordinate/reference validation. */
export function validateActorResource(inventory, scene, actor, previous, options = {}) {
  validateResourceName(actor.name, "Actor name");
  const direction = actor.direction;
  if (direction !== undefined && (typeof direction !== "string" || !DIRECTIONS.has(direction))) {
    throw new GameStudioProjectError("INVALID_INPUT", "Actor direction must be up, down, left, or right");
  }
  const coordinateType = actor.coordinateType ?? "tiles";
  if (coordinateType !== "tiles" && coordinateType !== "pixels") {
    throw new GameStudioProjectError("INVALID_INPUT", "Actor coordinateType must be tiles or pixels");
  }
  const sceneWidth = scene.width;
  const sceneHeight = scene.height;
  const x = actor.x ?? 0;
  const y = actor.y ?? 0;
  if (!Number.isSafeInteger(x) || !Number.isSafeInteger(y)) {
    throw new GameStudioProjectError("INVALID_INPUT", "Actor x and y must be integer coordinates");
  }
  if (
    typeof sceneWidth !== "number" ||
    !Number.isSafeInteger(sceneWidth) ||
    sceneWidth < 1 ||
    typeof sceneHeight !== "number" ||
    !Number.isSafeInteger(sceneHeight) ||
    sceneHeight < 1
  ) {
    throw new GameStudioProjectError("INVALID_RESOURCE", `Scene ${scene.id} has invalid dimensions`);
  }
  const spriteSheetId = actor.spriteSheetId ?? "";
  if (typeof spriteSheetId !== "string") {
    throw new GameStudioProjectError("INVALID_INPUT", "Actor spriteSheetId must be a string");
  }
  const candidate = spriteSheetId === "" ? undefined : resolveNativeAssetIdentity(inventory, spriteSheetId);
  const sprite = candidate?.type === "sprite" ? candidate : undefined;
  if (spriteSheetId !== "" && !sprite) {
    throw new GameStudioProjectError(
      "SPRITE_NOT_FOUND",
      `Actor ${String(actor.id ?? actor.name)} references missing sprite ${spriteSheetId}`,
    );
  }
  assertNoActorPalette(actor, previous, options.properties);
  const unit = coordinateType === "pixels" ? 8 : 1;
  const boundsWidth =
    typeof sprite?.boundsWidth === "number" && sprite.boundsWidth > 0 ? Math.ceil(sprite.boundsWidth / 8) * unit : unit;
  if (
    typeof x !== "number" ||
    typeof y !== "number" ||
    x < 0 ||
    y < 0 ||
    x + boundsWidth > sceneWidth * unit ||
    y >= sceneHeight * unit
  ) {
    throw new GameStudioProjectError(
      "ACTOR_OUT_OF_BOUNDS",
      `Actor ${String(actor.id ?? actor.name)} lies outside the ${sceneWidth} by ${sceneHeight} scene`,
    );
  }
  for (const key of ["script", "startScript", "updateScript", "hit1Script", "hit2Script", "hit3Script"]) {
    if (actor[key] !== undefined && !Array.isArray(actor[key])) {
      throw new GameStudioProjectError("INVALID_INPUT", `Actor ${key} must be an event array`);
    }
  }
  const invalid = findInvalidNativeScriptEvent(actor, previous, { ...options, projectRoot: inventory.projectRoot });
  if (invalid) throw new GameStudioProjectError("INVALID_EVENT", invalid.message);
}
export async function assertExpectedResourceRevision(root, target, expectedRevision) {
  const actualRevision = await resourceRevision(root, target);
  assertLoadedResourceRevision(root, target, actualRevision, expectedRevision);
  return actualRevision;
}
export function assertLoadedResourceRevision(root, target, actualRevision, expectedRevision) {
  if (expectedRevision !== undefined && actualRevision !== expectedRevision) {
    throw new GameStudioProjectError(
      "REVISION_MISMATCH",
      `Resource changed since the expected revision: ${projectRelativePath(root, target)}`,
      target,
    );
  }
}
export function legacyDescriptorScenes(descriptor, resourcePath) {
  const materialize = (resource) => ({
    ...resource,
    id: typeof resource.id === "string" ? resource.id : "",
    name: typeof resource.name === "string" ? resource.name : "",
    resourcePath,
  });
  return (Array.isArray(descriptor.scenes) ? descriptor.scenes : []).filter(isObject).map((scene) => ({
    ...materialize(scene),
    actors: (Array.isArray(scene.actors) ? scene.actors : []).filter(isObject).map(materialize),
    triggers: (Array.isArray(scene.triggers) ? scene.triggers : []).filter(isObject).map(materialize),
  }));
}
export function findLegacyProjectScene(descriptor, resourcePath, sceneId) {
  const scene = legacyDescriptorScenes(descriptor, resourcePath).find((candidate) => candidate.id === sceneId);
  if (!scene) throw new GameStudioProjectError("SCENE_NOT_FOUND", `Scene ${sceneId} disappeared during update`);
  return scene;
}
export function findLegacySceneCollectionResource(descriptor, sceneId, kind, resourceId) {
  const scene = (Array.isArray(descriptor.scenes) ? descriptor.scenes : []).find(
    (candidate) => isObject(candidate) && candidate.id === sceneId,
  );
  if (!isObject(scene))
    throw new GameStudioProjectError("SCENE_NOT_FOUND", `Scene ${sceneId} disappeared during update`);
  const resource = (Array.isArray(scene[kind]) ? scene[kind] : []).find(
    (candidate) => isObject(candidate) && candidate.id === resourceId,
  );
  if (!isObject(resource)) {
    const name = kind === "actors" ? "actor" : "trigger";
    throw new GameStudioProjectError(
      kind === "actors" ? "ACTOR_NOT_FOUND" : "TRIGGER_NOT_FOUND",
      `No ${name} with id ${resourceId} exists in scene ${sceneId}`,
    );
  }
  return resource;
}
export function assertDistributedOwnerIdentity(resource, kind, resourceId, sceneId) {
  if (resource.id !== resourceId) {
    throw new GameStudioProjectError(
      kind === "actor" ? "ACTOR_NOT_FOUND" : "TRIGGER_NOT_FOUND",
      `No ${kind} with id ${resourceId} exists in scene ${sceneId}`,
    );
  }
}
export function rewriteLegacySceneCollection(inventory, sceneId, kind, transform) {
  const scenes = Array.isArray(inventory.descriptor.scenes) ? inventory.descriptor.scenes : [];
  let found = false;
  const rewritten = scenes.map((entry) => {
    if (!isObject(entry) || entry.id !== sceneId) return entry;
    found = true;
    const resources = Array.isArray(entry[kind]) ? entry[kind].filter(isObject) : [];
    return { ...entry, [kind]: transform(resources) };
  });
  if (!found) {
    throw new GameStudioProjectError("SCENE_NOT_FOUND", `Scene ${sceneId} disappeared during update`);
  }
  return { ...inventory.descriptor, scenes: rewritten };
}
function containsReference(value, targetId, keys) {
  if (Array.isArray(value)) return value.some((child) => containsReference(child, targetId, keys));
  if (!isObject(value)) return false;
  for (const [key, child] of Object.entries(value)) {
    if (keys.has(key)) {
      if (child === targetId) return true;
      if (Array.isArray(child) && child.includes(targetId)) return true;
      if (isObject(child) && (child.id === targetId || child.value === targetId)) return true;
    }
    if (containsReference(child, targetId, keys)) return true;
  }
  return false;
}
/** Never rewrite a different authored script just to make deleting a resource succeed. */
export function assertResourceNotReferenced(inventory, kind, targetId, sceneId) {
  if ("structuralReferences" in inventory) {
    const reference = inventory
      .structuralReferences({ type: kind, id: targetId, sceneId })
      .find((candidate) => candidate.owner.resourceId !== targetId);
    if (reference) {
      throw new GameStudioProjectError(
        "RESOURCE_REFERENCED",
        `Cannot delete ${kind} ${targetId}: resource ${reference.owner.resourceId} still references it`,
        reference.owner.resourcePath,
      );
    }
    return;
  }
  const keys =
    kind === "actor"
      ? new Set(["actorId", "actor", "actorIds", "targetActorId"])
      : new Set(["triggerId", "trigger", "triggerIds", "targetTriggerId"]);
  for (const scene of inventory.scenes) {
    const { actors: _actors, triggers: _triggers, ...sceneFields } = scene;
    const resources = [sceneFields, ...scene.actors, ...scene.triggers];
    for (const resource of resources) {
      if (resource.id === targetId) continue;
      if (containsReference(resource, targetId, keys)) {
        throw new GameStudioProjectError(
          "RESOURCE_REFERENCED",
          `Cannot delete ${kind} ${targetId}: resource ${String(resource.id ?? scene.id)} still references it`,
          typeof resource.resourcePath === "string" ? resource.resourcePath : undefined,
        );
      }
    }
  }
}
export async function removeProjectResource(root, candidate) {
  const absolute = path.isAbsolute(candidate) ? candidate : path.resolve(root, candidate);
  const initial = await lstat(absolute);
  if (initial.isSymbolicLink() || !initial.isFile()) {
    throw new GameStudioProjectError(
      "UNSAFE_SYMLINK",
      `Refusing to delete a symbolic link or non-file native project resource: ${absolute}`,
      absolute,
    );
  }
  const safePath = await resolveProjectPath(root, absolute, { mustExist: true, allowRoot: false });
  const confirmed = await lstat(absolute);
  if (confirmed.isSymbolicLink() || !confirmed.isFile() || safePath !== absolute) {
    throw new GameStudioProjectError(
      "UNSAFE_SYMLINK",
      `Native project resource changed while preparing deletion: ${absolute}`,
      absolute,
    );
  }
  await unlink(safePath);
}
export async function inspectActor(projectPath, input, access) {
  if (access) await access.ensureFresh();
  const inventory = access ? undefined : await inventoryProject(projectPath);
  const context = access ?? inventory;
  const scene = findProjectScene(context, input.sceneId);
  const selected = findSceneActor(scene, input.actorId, access);
  const target = path.resolve(context.projectRoot, selected.resourcePath);
  const format = inventory?.format ?? access.projectInspection().format;
  const loaded = await readProjectJsonWithRevision(context.projectRoot, target);
  if (format === "distributed") assertDistributedOwnerIdentity(loaded.json, "actor", input.actorId, scene.id);
  const actor =
    format === "distributed"
      ? loaded.json
      : (() => {
          const currentScene = findLegacyProjectScene(loaded.json, selected.resourcePath, scene.id);
          const { resourcePath: _resourcePath, ...resource } = findSceneActor(currentScene, input.actorId);
          return resource;
        })();
  return {
    projectPath: context.projectPath,
    projectRoot: context.projectRoot,
    sceneId: scene.id,
    resourcePath: selected.resourcePath,
    actor,
    revision: loaded.revision,
  };
}
export async function updateActor(projectPath, input, access) {
  if (access) await access.ensureFresh();
  const inventory = access ? undefined : await inventoryProject(projectPath);
  const context = access ?? inventory;
  const scene = findProjectScene(context, input.sceneId);
  const selected = findSceneActor(scene, input.actorId, access);
  const target = path.resolve(context.projectRoot, selected.resourcePath);
  const format = inventory?.format ?? access.projectInspection().format;
  return withProjectResourceWriteLock(context.projectRoot, target, async () => {
    const loaded = await readProjectJsonWithRevision(context.projectRoot, target);
    assertLoadedResourceRevision(context.projectRoot, target, loaded.revision, input.expectedRevision);
    if (format === "distributed") assertDistributedOwnerIdentity(loaded.json, "actor", input.actorId, scene.id);
    if (format === "legacy" && access && typeof access.strongRefresh === "function") await access.strongRefresh();
    const ownerScene =
      format === "distributed" ? scene : findLegacyProjectScene(loaded.json, selected.resourcePath, scene.id);
    const original =
      format === "distributed"
        ? loaded.json
        : findLegacySceneCollectionResource(loaded.json, scene.id, "actors", input.actorId);
    let actor = mergeActorChanges(original, input);
    if (actor.name !== original.name)
      actor = {
        ...actor,
        symbol: renamedResourceSymbol(
          "actor",
          original,
          actor,
          takenResourceSymbols(await inventoryProject(projectPath, access), input.actorId),
        ),
      };
    const validationContext = format === "legacy" ? (access ?? (await inventoryProject(projectPath))) : context;
    validateActorResource(validationContext, ownerScene, actor, original, {
      explicitlyPatchedValues: explicitlyPatchedNativeScriptValues(input.properties),
      properties: input.properties,
      legacyDescriptor: format === "legacy" ? loaded.json : undefined,
    });
    const updated =
      format === "distributed"
        ? actor
        : rewriteLegacySceneCollection({ descriptor: loaded.json }, scene.id, "actors", (resources) =>
            resources.map((resource) => (resource.id === input.actorId ? actor : resource)),
          );
    await assertExpectedResourceRevision(context.projectRoot, target, loaded.revision);
    await writeProjectJsonAtomic(context.projectRoot, target, updated);
    const revision = await resourceRevision(context.projectRoot, target);
    if (access) await access.noteCommittedPaths([target]);
    return {
      projectPath: context.projectPath,
      projectRoot: context.projectRoot,
      sceneId: scene.id,
      resourcePath: selected.resourcePath,
      actor,
      revision,
    };
  });
}
export async function deleteActor(projectPath, input, access) {
  if (access && typeof access.ensureFresh === "function") await access.ensureFresh();
  const inventory = access ? undefined : await inventoryProject(projectPath);
  const context = access ?? inventory;
  const scene = findProjectScene(context, input.sceneId);
  const actor = findSceneActor(scene, input.actorId, access);
  const target = path.resolve(context.projectRoot, actor.resourcePath);
  return withProjectResourceWriteLock(context.projectRoot, target, async () => {
    const loaded = await readProjectJsonWithRevision(context.projectRoot, target);
    assertLoadedResourceRevision(context.projectRoot, target, loaded.revision, input.expectedRevision);
    if (access) await access.strongRefresh();
    if (access && !access.coverage.complete) {
      throw new GameStudioProjectError(
        "RESOURCE_REFERENCED",
        `Cannot delete actor ${actor.id}: complete reference coverage could not be verified`,
        actor.resourcePath,
      );
    }
    const format = inventory?.format ?? access.projectInspection().format;
    if (format === "legacy") findLegacySceneCollectionResource(loaded.json, scene.id, "actors", input.actorId);
    else assertDistributedOwnerIdentity(loaded.json, "actor", input.actorId, scene.id);
    const references =
      format === "legacy"
        ? { scenes: legacyDescriptorScenes(loaded.json, actor.resourcePath) }
        : (access ?? (await inventoryProject(projectPath)));
    assertResourceNotReferenced(references, "actor", actor.id, scene.id);
    if (format === "distributed") {
      await assertExpectedResourceRevision(context.projectRoot, target, loaded.revision);
      await removeProjectResource(context.projectRoot, target);
    } else {
      const descriptor = rewriteLegacySceneCollection({ descriptor: loaded.json }, scene.id, "actors", (resources) =>
        resources.filter((resource) => resource.id !== actor.id),
      );
      await assertExpectedResourceRevision(context.projectRoot, target, loaded.revision);
      await writeProjectJsonAtomic(context.projectRoot, target, descriptor);
    }
    if (access) await access.noteCommittedPaths([target]);
    return {
      projectPath: context.projectPath,
      projectRoot: context.projectRoot,
      sceneId: scene.id,
      actorId: actor.id,
      resourcePath: actor.resourcePath,
      deleted: true,
    };
  });
}
