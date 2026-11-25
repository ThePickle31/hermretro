// Read GB Studio's own event definitions (src/lib/events/event*.js) and print the engine's event catalog as JSON.
// Run through tools/engine/event_catalog.py, which finds the toolchain's GB Studio and writes or verifies the
// committed catalog: node tools/engine/event_catalog.mjs <gb-studio folder>
//
// Each definition is a CommonJS module that needs only GB Studio's l10n helper (answered from src/lang/en.json)
// and, in one file, a scriptValue type guard its compile function uses (never called here).

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import vm from "node:vm";

// GB Studio marks events deprecated without naming what replaces them. Every deprecated event is listed here, with
// its replacement or null, so a GB Studio update that deprecates another one stops the generator until it is added.
export const REPLACEMENTS = {
  EVENT_ACTOR_INVOKE: null,
  EVENT_ACTOR_MOVE_TO_VALUE: "EVENT_ACTOR_MOVE_TO",
  EVENT_ACTOR_SET_ANIMATE: null,
  EVENT_ACTOR_SET_FRAME_TO_VALUE: "EVENT_ACTOR_SET_FRAME",
  EVENT_ACTOR_SET_POSITION_TO_VALUE: "EVENT_ACTOR_SET_POSITION",
  EVENT_DEFINE_LABEL: "EVENT_LOOP_WHILE",
  EVENT_GOTO_LABEL: "EVENT_LOOP_WHILE",
  EVENT_IF_EXPRESSION: "EVENT_IF",
  EVENT_IF_FALSE: "EVENT_IF",
  EVENT_IF_TRUE: "EVENT_IF",
  EVENT_IF_VALUE: "EVENT_IF",
  EVENT_IF_VALUE_COMPARE: "EVENT_IF",
  EVENT_SET_FALSE: "EVENT_SET_VALUE",
  EVENT_SET_TRUE: "EVENT_SET_VALUE",
  EVENT_WEAPON_ATTACK: "EVENT_LAUNCH_PROJECTILE",
};

// Field types that only arrange the editor and are never stored in an event's args.
const LAYOUT_TYPES = new Set(["addEventButton", "break", "collapsable", "presets", "tabs"]);
// soundType asks for the kind of the chosen sound asset, which an example never satisfies.
const CONDITION_OPERATORS = ["in", "eq", "ne", "gt", "gte", "lt", "lte", "set", "soundType"];

function loadStrings(root) {
  return JSON.parse(readFileSync(path.join(root, "src", "lang", "en.json"), "utf8"));
}

function loadDefinition(file, strings) {
  const l10n = (key, params = {}) => {
    let text = typeof strings[key] === "string" ? strings[key] : key;
    for (const [name, value] of Object.entries(params)) text = text.replaceAll(`{${name}}`, String(value ?? ""));
    return text;
  };
  const modules = {
    "../helpers/l10n": { default: l10n },
    "shared/lib/scriptValue/types": { isConstScriptValue: () => false },
  };
  const module = { exports: {} };
  const require = (name) => {
    if (!(name in modules)) throw new Error(`${path.basename(file)} requires ${name}, which the catalog cannot load`);
    return modules[name];
  };
  vm.runInNewContext(readFileSync(file, "utf8"), { module, exports: module.exports, require }, { filename: file });
  return module.exports;
}

function plain(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function sceneTypesOf(conditions) {
  const types = conditions.flatMap((condition) => condition.sceneType ?? []);
  return types.length > 0 ? types.map((type) => type.toUpperCase()) : undefined;
}

// The conditions on other args that decide whether GB Studio shows (and compiles) a field.
function whenOf(conditions) {
  const when = new Map();
  for (const condition of conditions) {
    if (typeof condition.key !== "string" || condition.key.startsWith("__")) continue;
    const kept = { key: condition.key };
    for (const operator of CONDITION_OPERATORS) {
      if (operator in condition) kept[operator] = plain(condition[operator]);
    }
    when.set(JSON.stringify(kept), kept);
  }
  return when.size > 0 ? [...when.values()] : undefined;
}

function optionsOf(field) {
  if (Array.isArray(field.options)) return field.options.map((option) => (Array.isArray(option) ? option[0] : option));
  if (field.values && typeof field.values === "object") return Object.keys(field.values);
  return undefined;
}

function describeField(field, conditions) {
  const record = { key: field.key, type: field.type };
  if (field.defaultValue !== undefined) record.default = placeholder(plain(field.defaultValue));
  const options = optionsOf(field);
  if (options) record.options = options;
  for (const bound of ["min", "max"]) {
    if (typeof field[bound] === "number") record[bound] = field[bound];
  }
  if (field.multiple) record.multiple = true;
  if (field.optional) record.optional = true;
  const text = field.description || field.label;
  if (typeof text === "string" && text) record.description = text;
  const when = whenOf(conditions);
  if (when) record.when = when;
  const sceneTypes = sceneTypesOf(conditions);
  if (sceneTypes) record.sceneTypes = sceneTypes;
  return record;
}

// Walk a definition's fields: args, child branches (fields of type events) and scene-type warnings. A group's or
// collapsible section's conditions apply to the fields inside it.
function collect(fields, found, inherited = []) {
  for (const field of fields ?? []) {
    const conditions = [...inherited, ...(field.conditions ?? [])];
    if (Array.isArray(field.fields)) collect(field.fields, found, conditions);
    if (!field.key && field.labelVariant === "warning" && typeof field.label === "string") {
      const sceneTypes = sceneTypesOf(conditions);
      const when = whenOf(conditions);
      found.warnings.push({ ...(sceneTypes ? { sceneTypes } : {}), ...(when ? { when } : {}), message: field.label });
      continue;
    }
    if (typeof field.key !== "string" || field.key.startsWith("__") || LAYOUT_TYPES.has(field.type)) continue;
    if (field.type === "events") {
      if (!found.branches.some((branch) => branch.key === field.key)) found.branches.push({ key: field.key, when: whenOf(conditions) });
      continue;
    }
    const known = found.fields.find((record) => record.key === field.key);
    if (known) showAlso(known, describeField(field, conditions));
    else found.fields.push(describeField(field, conditions));
    // A coordinate or duration names the arg that holds its units (tiles or pixels, time or frames).
    if (typeof field.unitsField === "string" && !found.fields.some((record) => record.key === field.unitsField)) {
      const units = { key: field.unitsField, type: "units" };
      if (field.unitsDefault !== undefined) units.default = field.unitsDefault;
      if (Array.isArray(field.unitsAllowed)) units.options = [...field.unitsAllowed];
      const when = whenOf(conditions.filter((condition) => condition.key !== field.unitsField));
      if (when) units.when = when;
      found.fields.push(units);
    }
  }
}

// A key GB Studio declares more than once (a menu's options) is shown when any of its declarations' conditions hold:
// "when" (all must hold) becomes "whenAny" (one list of them must).
function showAlso(known, repeated) {
  const alternatives = known.whenAny ?? [known.when ?? []];
  const added = repeated.when ?? [];
  delete known.when;
  if (alternatives.length === 0 || added.length === 0 || alternatives.some((when) => when.length === 0)) {
    delete known.whenAny;
    return;
  }
  known.whenAny = [...alternatives, added];
}

function shown(field, defaults) {
  const alternatives = field.whenAny ?? [field.when ?? []];
  return alternatives.some((when) => when.every((condition) => holds(condition, defaults)));
}

function holds(condition, args) {
  const value = args[condition.key];
  if ("soundType" in condition) return false;
  // JSON keeps GB Studio's undefined ("not set yet") as null.
  if ("in" in condition && !condition.in.some((option) => option === value || (option === null && value === undefined))) return false;
  if ("eq" in condition && value !== condition.eq) return false;
  if ("ne" in condition && value === condition.ne) return false;
  if ("gt" in condition && !(value > condition.gt)) return false;
  if ("gte" in condition && !(value >= condition.gte)) return false;
  if ("lt" in condition && !(value < condition.lt)) return false;
  if ("lte" in condition && !(value <= condition.lte)) return false;
  if ("set" in condition && Boolean(value) !== condition.set) return false;
  return true;
}

// GB Studio's editor fills a LAST_<KIND> default with the resource last picked; the catalog names the kind instead.
function placeholder(value) {
  if (typeof value === "string") {
    const kind = /^LAST_([A-Z_]+)$/.exec(value)?.[1];
    return kind ? `<${kind.toLowerCase().replaceAll("_", " ")}>` : value;
  }
  if (Array.isArray(value)) return value.map(placeholder);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, placeholder(item)]));
  return value;
}

// The event GB Studio's editor adds: every field it shows for the defaults, set to its default.
function exampleOf(id, found) {
  const defaults = Object.fromEntries(found.fields.map((field) => [field.key, field.default]));
  const args = {};
  for (const field of found.fields) {
    if (field.default === undefined || field.sceneTypes || !shown(field, defaults)) continue;
    args[field.key] = field.default;
  }
  const example = { command: id, args };
  const branches = found.branches.filter((branch) => shown(branch, defaults));
  if (branches.length > 0) example.children = Object.fromEntries(branches.map((branch) => [branch.key, []]));
  return example;
}

export function buildCatalog(root) {
  const strings = loadStrings(root);
  const folder = path.join(root, "src", "lib", "events");
  const files = readdirSync(folder).filter((name) => /^event[A-Z]\w*\.js$/.test(name)).sort();
  const events = {};
  for (const name of files) {
    const definition = loadDefinition(path.join(folder, name), strings);
    const id = definition.id;
    if (typeof id !== "string" || !/^EVENT_[A-Z0-9_]+$/.test(id)) throw new Error(`${name} has no event id`);
    if (events[id]) throw new Error(`${name} repeats event id ${id}`);
    const found = { fields: [], branches: [], warnings: [] };
    collect(definition.fields, found);
    const entry = { name: typeof strings[id] === "string" ? strings[id] : id };
    if (typeof definition.description === "string" && definition.description) entry.summary = definition.description;
    entry.groups = (definition.groups ?? []).map((group) => strings[group] ?? group);
    if (Array.isArray(definition.sceneTypes)) entry.sceneTypes = definition.sceneTypes.map((type) => type.toUpperCase());
    if (definition.deprecated) {
      if (!(id in REPLACEMENTS)) throw new Error(`${id} is deprecated: add it to REPLACEMENTS in tools/engine/event_catalog.mjs`);
      entry.deprecated = true;
      if (REPLACEMENTS[id]) entry.replacement = REPLACEMENTS[id];
    }
    if (found.warnings.length > 0) entry.warnings = found.warnings;
    entry.fields = found.fields;
    if (found.branches.length > 0) entry.branches = found.branches.map((branch) => branch.key);
    entry.example = exampleOf(id, found);
    events[id] = entry;
  }
  for (const [id, replacement] of Object.entries(REPLACEMENTS)) {
    if (!events[id]?.deprecated) throw new Error(`REPLACEMENTS names ${id}, which GB Studio no longer deprecates`);
    if (replacement && (!events[replacement] || events[replacement].deprecated)) {
      throw new Error(`${id}'s replacement ${replacement} is not a current GB Studio event`);
    }
  }
  const version = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8")).version;
  return { gbStudioVersion: version, events: Object.fromEntries(Object.keys(events).sort().map((id) => [id, events[id]])) };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  if (process.argv.length !== 3) {
    process.stderr.write("usage: node tools/engine/event_catalog.mjs <gb-studio folder>\n");
    process.exit(2);
  }
  try {
    process.stdout.write(`${JSON.stringify(buildCatalog(path.resolve(process.argv[2])), null, 1)}\n`);
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exit(1);
  }
}
