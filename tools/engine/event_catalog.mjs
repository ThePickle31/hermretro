// Read GB Studio's own event definitions (src/lib/events/event*.js) and print the engine's event catalog as JSON.
// Run through tools/engine/event_catalog.py, which finds the toolchain's GB Studio and writes or verifies the
// committed catalog: node tools/engine/event_catalog.mjs <gb-studio folder>
//
// Each definition is a CommonJS module that needs only GB Studio's l10n helper (answered from src/lang/en.json)
// and, in one file, a scriptValue type guard its compile function uses (never called here). What the definitions do
// not say (replacements, migrations, examples that need other events) is in event_guidance.mjs.

import { readFileSync, readdirSync, realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { DEPRECATIONS, EDITOR_DEFAULTS, EXAMPLES, UNAVAILABLE } from "./event_guidance.mjs";

// Field types that only arrange the editor and are never stored in an event's args.
const LAYOUT_TYPES = new Set(["addEventButton", "break", "collapsable", "presets", "tabs"]);
// Args the editor keeps for itself (its sections, tabs and collapsed panels); the compiler never reads them.
const EDITOR_KEY = /^__(?:section|scriptTabs|collapse)/;
// soundType asks for the kind of the chosen sound asset, which an example never satisfies.
const KEY_OPERATORS = ["in", "eq", "ne", "gt", "gte", "lt", "lte", "set", "soundType"];
// Conditions on where the event is (the scene's parallax, the kind of script that holds it), not on its args.
const PLACE_CONDITIONS = ["parallaxEnabled", "entityType", "entityTypeNot"];
// A custom script call's args name the script's own parameters.
const CALL_BINDING = /^\$(?:actor|variable)\[[^\]]+\]\$$/;

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

function withoutComments(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

// The text of GB Studio's ScriptBuilder, which holds every helper a compile function can take.
function loadScriptBuilder(root) {
  const folder = path.join(root, "src", "lib", "compiler", "scriptBuilder");
  return readdirSync(folder)
    .filter((name) => name.endsWith(".ts"))
    .map((name) => withoutComments(readFileSync(path.join(folder, name), "utf8")))
    .join("\n");
}

// The helpers a compile function takes (`const { a, b } = helpers`) that the ScriptBuilder no longer defines.
function missingHelpers(compile, builder) {
  if (typeof compile !== "function") return [];
  const names = [...withoutComments(compile.toString()).matchAll(/const\s*\{([^}]*)\}\s*=\s*helpers/g)].flatMap((match) =>
    match[1].split(",").map((name) => name.split(":")[0].trim()),
  );
  return names.filter((name) => name && !new RegExp(`\\b${name}\\b`).test(builder));
}

function plain(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

// One condition as the catalog keeps it, or null for one only the editor reads. A shape the catalog does not know
// stops the generator: guessing would document a field as shown when GB Studio hides it.
function conditionOf(condition, where) {
  const unknown = () => new Error(`${where}: condition ${JSON.stringify(condition)} has a shape the catalog does not know`);
  if (typeof condition.key === "string") {
    if (EDITOR_KEY.test(condition.key)) return null;
    const operators = Object.keys(condition).filter((name) => name !== "key");
    if (operators.length === 0 || operators.some((name) => !KEY_OPERATORS.includes(name))) throw unknown();
    return plain(condition);
  }
  const [name, ...rest] = Object.keys(condition);
  if (rest.length > 0 || !PLACE_CONDITIONS.includes(name)) throw unknown();
  const value = condition[name];
  return { [name]: typeof value === "boolean" ? value : [].concat(value) };
}

function unique(items) {
  return [...new Map(items.map((item) => [JSON.stringify(item), item])).values()];
}

// GB Studio's conditions as alternatives (one list must hold in full; `or` makes several) and the scene types they
// name. Scene types are kept apart: they say where an event misbehaves, not which args it reads.
function conditionsOf(conditions, where) {
  let alternatives = [[]];
  const sceneTypes = [];
  for (const condition of conditions) {
    if ("sceneType" in condition) {
      if (Object.keys(condition).length !== 1) throw new Error(`${where}: a sceneType condition with other keys`);
      sceneTypes.push(...[].concat(condition.sceneType).map((type) => type.toUpperCase()));
    } else if ("or" in condition) {
      if (Object.keys(condition).length !== 1 || !Array.isArray(condition.or)) {
        throw new Error(`${where}: condition ${JSON.stringify(condition)} has a shape the catalog does not know`);
      }
      const options = condition.or.flatMap((group) => {
        const inner = conditionsOf(group, where);
        if (inner.sceneTypes) throw new Error(`${where}: a sceneType inside an or condition`);
        return inner.alternatives;
      });
      alternatives = alternatives.flatMap((alternative) => options.map((option) => [...alternative, ...option]));
    } else {
      const kept = conditionOf(condition, where);
      if (kept) alternatives = alternatives.map((alternative) => [...alternative, kept]);
    }
  }
  return { alternatives: unique(alternatives.map(unique)), sceneTypes: sceneTypes.length > 0 ? sceneTypes : undefined };
}

// "when" (every condition holds) for one alternative, "whenAny" (one list of them holds in full) for several.
function shownWhen(alternatives) {
  if (alternatives.some((alternative) => alternative.length === 0)) return {};
  return alternatives.length === 1 ? { when: alternatives[0] } : { whenAny: alternatives };
}

function alternativesOf(record) {
  return record.whenAny ?? [record.when ?? []];
}

function optionsOf(field) {
  if (field.type === "collisionMask") return [...(field.includePlayer ? ["player"] : []), "1", "2", "3"];
  if (Array.isArray(field.options)) return field.options.map((option) => (Array.isArray(option) ? option[0] : option));
  if (field.values && typeof field.values === "object") return Object.keys(field.values);
  return undefined;
}

// A union field stores {type, value}: the default is the value for its default type.
function defaultOf(field, where) {
  if (field.type === "union") {
    const types = Array.isArray(field.types) ? field.types : [];
    if (!types.includes(field.defaultType)) throw new Error(`${where}: union field ${field.key} has no defaultType among its types`);
    const value = field.defaultValue?.[field.defaultType];
    return value === undefined ? undefined : { type: field.defaultType, value: placeholder(plain(value)) };
  }
  if (field.type in EDITOR_DEFAULTS) return plain(EDITOR_DEFAULTS[field.type]);
  return field.defaultValue === undefined ? undefined : placeholder(plain(field.defaultValue));
}

function describeField(field, conditions, where) {
  const record = { key: field.key, type: field.type };
  if (field.type === "union") record.types = [...field.types];
  const value = defaultOf(field, `${where} field ${field.key}`);
  if (value !== undefined) record.default = value;
  const options = optionsOf(field);
  if (options) record.options = options;
  for (const bound of ["min", "max"]) {
    if (typeof field[bound] === "number") record[bound] = field[bound];
  }
  // A collision mask holds one group or several, by the shape of its default.
  if (field.multiple || field.allowMultiple || (field.type === "collisionMask" && Array.isArray(field.defaultValue))) {
    record.multiple = true;
  }
  if (field.optional) record.optional = true;
  const text = field.description || field.label;
  if (typeof text === "string" && text) record.description = text;
  const { alternatives, sceneTypes } = conditionsOf(conditions, `${where} field ${field.key}`);
  Object.assign(record, shownWhen(alternatives));
  if (sceneTypes) record.sceneTypes = sceneTypes;
  return record;
}

// Walk a definition's fields: args, child branches (fields of type events) and warnings. A group's or collapsible
// section's conditions apply to the fields inside it.
function collect(fields, found, where, inherited = []) {
  for (const field of fields ?? []) {
    const conditions = [...inherited, ...(field.conditions ?? [])];
    if (Array.isArray(field.fields)) collect(field.fields, found, where, conditions);
    if (!field.key && field.labelVariant === "warning" && typeof field.label === "string") {
      const { alternatives, sceneTypes } = conditionsOf(conditions, `${where} warning`);
      found.warnings.push({ ...(sceneTypes ? { sceneTypes } : {}), ...shownWhen(alternatives), message: field.label });
      continue;
    }
    if (typeof field.key !== "string" || field.key.startsWith("__") || LAYOUT_TYPES.has(field.type)) continue;
    if (field.type === "events") {
      if (!found.branches.some((branch) => branch.key === field.key)) {
        found.branches.push({ key: field.key, ...shownWhen(conditionsOf(conditions, `${where} branch ${field.key}`).alternatives) });
      }
      continue;
    }
    const known = found.fields.find((record) => record.key === field.key);
    if (known) showAlso(known, describeField(field, conditions, where));
    else found.fields.push(describeField(field, conditions, where));
    // A coordinate or duration names the arg that holds its units (tiles or pixels, time or frames).
    if (typeof field.unitsField === "string" && !found.fields.some((record) => record.key === field.unitsField)) {
      const units = { key: field.unitsField, type: "units" };
      if (field.unitsDefault !== undefined) units.default = field.unitsDefault;
      if (Array.isArray(field.unitsAllowed)) units.options = [...field.unitsAllowed];
      const rest = conditions.filter((condition) => condition.key !== field.unitsField);
      Object.assign(units, shownWhen(conditionsOf(rest, `${where} field ${field.unitsField}`).alternatives));
      found.fields.push(units);
    }
  }
}

// A key GB Studio declares more than once (a menu's options) is shown when any of its declarations' conditions hold.
function showAlso(known, repeated) {
  const alternatives = unique([...alternativesOf(known), ...alternativesOf(repeated)]);
  delete known.when;
  delete known.whenAny;
  Object.assign(known, shownWhen(alternatives));
}

// The editor's "Disable Else" sets __disableElse. An event whose compiler reads it leaves its false branch out (the
// catalog adds the arg); for any other the condition is the editor's alone and is dropped.
function disableElse(found, compile) {
  const records = [...found.fields, ...found.branches, ...found.warnings];
  const names = (alternative) => alternative.some((condition) => condition.key === "__disableElse");
  if (!records.some((record) => alternativesOf(record).some(names))) return;
  if (typeof compile !== "function" || !compile.toString().includes("__disableElse")) {
    for (const record of records) {
      const alternatives = alternativesOf(record).map((alternative) => alternative.filter((condition) => condition.key !== "__disableElse"));
      delete record.when;
      delete record.whenAny;
      Object.assign(record, shownWhen(unique(alternatives)));
    }
    return;
  }
  found.fields.push({
    key: "__disableElse",
    type: "checkbox",
    optional: true,
    description: "true leaves the false branch out (the editor's Disable Else): the compiler ignores children.false.",
  });
}

function shown(record, args) {
  return alternativesOf(record).some((alternative) => alternative.every((condition) => holds(condition, args)));
}

function holds(condition, args) {
  // An example assumes a scene without parallax and fits any kind of script.
  if ("parallaxEnabled" in condition) return condition.parallaxEnabled === false;
  if ("entityType" in condition || "entityTypeNot" in condition) return true;
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

// A hand-written example must use only args and branches GB Studio declares, and name its own event.
function checkExample(id, example, events) {
  const list = Array.isArray(example) ? example : [example];
  if (!list.some((event) => event.command === id)) throw new Error(`${id}'s example in event_guidance.mjs does not use ${id}`);
  const check = (event) => {
    const entry = events[event.command];
    if (!entry) throw new Error(`${id}'s example uses ${event.command}, which GB Studio does not have`);
    for (const key of Object.keys(event.args ?? {})) {
      const binding = event.command === "EVENT_CALL_CUSTOM_EVENT" && CALL_BINDING.test(key);
      if (!binding && !entry.fields.some((field) => field.key === key)) throw new Error(`${id}'s example gives ${event.command} an arg ${key} it does not have`);
    }
    for (const [branch, children] of Object.entries(event.children ?? {})) {
      if (!entry.branches?.some((record) => record.key === branch)) throw new Error(`${id}'s example gives ${event.command} a branch ${branch} it does not have`);
      children.forEach(check);
    }
  };
  list.forEach(check);
}

function checkGuidance(events) {
  for (const [id, deprecation] of Object.entries(DEPRECATIONS)) {
    if (!events[id]?.deprecated) throw new Error(`DEPRECATIONS names ${id}, which GB Studio no longer deprecates`);
    const replacement = deprecation.replacement;
    if (replacement && (!events[replacement] || events[replacement].deprecated)) {
      throw new Error(`${id}'s replacement ${replacement} is not a current GB Studio event`);
    }
  }
  for (const id of UNAVAILABLE) {
    if (!events[id]?.unavailable) throw new Error(`UNAVAILABLE names ${id}, whose helpers GB Studio's compiler has`);
  }
  for (const [id, guidance] of Object.entries(EXAMPLES)) {
    if (!events[id]) throw new Error(`EXAMPLES names ${id}, which GB Studio does not have`);
    checkExample(id, guidance.example, events);
  }
}

export function buildCatalog(root) {
  const strings = loadStrings(root);
  const builder = loadScriptBuilder(root);
  const folder = path.join(root, "src", "lib", "events");
  const files = readdirSync(folder).filter((name) => /^event[A-Z]\w*\.js$/.test(name)).sort();
  const events = {};
  for (const name of files) {
    const definition = loadDefinition(path.join(folder, name), strings);
    const id = definition.id;
    if (typeof id !== "string" || !/^EVENT_[A-Z0-9_]+$/.test(id)) throw new Error(`${name} has no event id`);
    if (events[id]) throw new Error(`${name} repeats event id ${id}`);
    const found = { fields: [], branches: [], warnings: [] };
    collect(definition.fields, found, id);
    disableElse(found, definition.compile);
    const entry = { name: typeof strings[id] === "string" ? strings[id] : id };
    if (typeof definition.description === "string" && definition.description) entry.summary = definition.description;
    entry.groups = (definition.groups ?? []).map((group) => strings[group] ?? group);
    if (Array.isArray(definition.sceneTypes)) entry.sceneTypes = definition.sceneTypes.map((type) => type.toUpperCase());
    if (definition.deprecated) {
      if (!(id in DEPRECATIONS)) throw new Error(`${id} is deprecated: add it to DEPRECATIONS in tools/engine/event_guidance.mjs`);
      const { replacement, migration } = DEPRECATIONS[id];
      Object.assign(entry, { deprecated: true, ...(replacement ? { replacement } : {}), migration });
    }
    const missing = missingHelpers(definition.compile, builder);
    if (missing.length > 0) {
      if (!UNAVAILABLE.includes(id)) {
        throw new Error(`${id} compiles with ${missing.join(", ")}, which GB Studio's ScriptBuilder lacks: add it to UNAVAILABLE in tools/engine/event_guidance.mjs`);
      }
      entry.unavailable = `GB Studio's compiler has no ${missing.join(" or ")}: a script with this event does not build.`;
    }
    if (found.warnings.length > 0) entry.warnings = found.warnings;
    entry.fields = found.fields;
    if (found.branches.length > 0) entry.branches = found.branches;
    if (EXAMPLES[id]?.requires) entry.requires = EXAMPLES[id].requires;
    entry.example = EXAMPLES[id]?.example ?? exampleOf(id, found);
    events[id] = entry;
  }
  checkGuidance(events);
  const version = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8")).version;
  return { gbStudioVersion: version, events: Object.fromEntries(Object.keys(events).sort().map((id) => [id, events[id]])) };
}

// Node runs this file by its real path: compare real paths, or a folder reached through a symlink (macOS's /var and
// /tmp are) would never run it.
if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) {
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
