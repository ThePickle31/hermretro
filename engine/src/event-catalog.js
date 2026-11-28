import path from "node:path";
import { readdirSync, readFileSync, realpathSync, statSync } from "node:fs";
import { SCRIPT_KEYS, MAXIMUM_EVENT_DEPTH, isObject } from "./native-script-events.js";
import { GameStudioProjectError } from "./project.js";
import { supplementalResources } from "./world-script-graph.js";
import { engineUrl } from "./engine-root.js";

// "../src/" reaches the catalog from this module and from the bundle in dist/ alike.
const EVENT_CATALOG_URL = engineUrl("src/gb-studio-events.json");
const EVENT_LIST_LIMIT = 40;
const EVENT_UNCATEGORIZED = "Uncategorized";
const EVENT_FIELD_TYPES = {
  value:
    'A typed ScriptValue object, never a bare number or string: {"type":"number","value":3}, {"type":"variable","value":"<variable id>"}, {"type":"direction","value":"up"}, {"type":"expression","value":"$00$ + 1"}, or an operator such as {"type":"add","valueA":{...},"valueB":{...}} (eq, ne, lt, lte, gt, gte, and, or, not, add, sub, mul, div, mod, min, max, rnd). A condition is true for any value but 0.',
  constvalue: 'A constant ScriptValue: {"type":"number","value":3}.',
  union: 'A {"type":<one of types>,"value":...} object.',
  variable:
    'A variable id string: a global variable\'s id ("0", "12"; variable_inspect lists them), "L0"… for the actor\'s or trigger\'s locals, "T0"/"T1" for temporaries, "V0"…"V9" for a custom script\'s parameters.',
  actor: 'An actor id, "player", or "$self$" (the actor whose script runs).',
  number: "A plain number.",
  checkbox: "true or false.",
  select: "One of options.",
  togglebuttons: "One of options; with multiple:true an array of them (e.g. [0, 2]), never a single value.",
  units: "One of options: the units of this event's coordinate, distance or time args.",
  textarea:
    "A string. A field with multiple:true also takes an array of strings, one per text box. $00$ prints global variable 0 and $12$ variable 12; $L0$ a local, $T0$ a temporary, $V0$ a custom script's parameter. GB Studio drops one leading zero, so $1$ and $01$ both print variable 1 but $0$ prints the script's default variable (local L0, or V0 in a custom script), not global 0.",
  text: "A string.",
  direction:
    'A plain string: "up", "down", "left" or "right" ("" keeps the current direction); with multiple:true an array of them.',
  scene: "A scene id (project_inventory).",
  sprite: "A sprite asset id (project_inventory).",
  avatar:
    'An avatar asset id (project_inventory, type avatar: a 16 × 16 image under assets/avatars, not a sprite), or "" for none.',
  music: "A music asset id.",
  soundEffect: '"beep", "crash", "tone", or a sound asset id.',
  input: 'An array of buttons: "a", "b", "start", "select", "up", "down", "left", "right".',
  collisionMask:
    'A collision group from options ("player", "1", "2", "3"): one string such as "3", or with multiple:true an array such as ["1"].',
  dataTable:
    '{"variables":[<variable id per column>],"rows":[{"label":"","values":[{"type":"number","value":0}, …one per column]}]}: the index variable picks a row (from 0) and each column\'s value goes into that column\'s variable.',
  palette: "A palette id (palette_inspect).",
  engineField: "An engine field key (engine_field_inspect).",
  customEvent: "A custom script id (project_inventory's scripts).",
};
const EVENT_NOTES = {
  EVENT_SWITCH_SCENE: "Create it with script_transition, which checks the destination scene and landing tile.",
};
let eventCatalogCache;
export function eventCatalog() {
  eventCatalogCache ??= JSON.parse(readFileSync(EVENT_CATALOG_URL, "utf8"));
  return eventCatalogCache;
}
// Commands GB Studio's compiler handles itself, without an event definition.
export const COMPILER_EVENT_COMMANDS = new Set([
  "EVENT_END",
  "INTERNAL_SET_CONTEXT",
  "INTERNAL_IF_PARAM",
  "INTERNAL_SET_SPRITE_MODE",
]);
const PLUGIN_EVENT_DIRECTORY = /^events$/i;
const PLUGIN_EVENT_FILE = /^event.*\.js$/i;
// GB Studio loads a plugin's events from plugins/*/**/events/event*.js and registers the id each one's code returns
// when run, which reading the source cannot tell. A project with any such file (looked for more widely than GB Studio
// does: hidden folders, symbolic links, any letter case) keeps every command on write; its build reports one GB Studio
// has no compiler for. That includes an event GB Studio cannot compile, which a plugin may register again with a
// compile that works: if none does, its build stops with SCRIPT_EVENT_COMPILE_FAILED naming the replacement.
function projectHasPluginEvents(projectRoot) {
  const visited = new Set();
  const visit = (directory) => {
    let real;
    let entries;
    try {
      real = realpathSync(directory);
      if (visited.has(real)) return false;
      visited.add(real);
      entries = readdirSync(directory, { withFileTypes: true });
    } catch {
      return false;
    }
    const events = PLUGIN_EVENT_DIRECTORY.test(path.basename(directory));
    for (const entry of entries) {
      const child = path.join(directory, entry.name);
      if (events && PLUGIN_EVENT_FILE.test(entry.name)) return true;
      let folder = entry.isDirectory();
      if (entry.isSymbolicLink()) {
        try {
          folder = statSync(child).isDirectory();
        } catch {
          folder = false;
        }
      }
      if (folder && visit(child)) return true;
    }
    return false;
  };
  return visit(path.join(projectRoot, "plugins"));
}
// Why GB Studio cannot build a script event, or undefined when it can: a command it has no event for (it builds the
// game without it) or an event whose compile helper its compiler no longer has (the build fails), unless GB Studio's
// legacy migration converts it in this project. A project with plugin events keeps every command.
export function unbuildableEventMessage(command, where, project = {}) {
  const entry =
    typeof command === "string" && Object.hasOwn(eventCatalog().events, command)
      ? eventCatalog().events[command]
      : undefined;
  if ((entry && !entry.unavailable) || COMPILER_EVENT_COMMANDS.has(command)) return undefined;
  if (legacyMigrationConverts(command, project.legacyDescriptor)) return undefined;
  if (typeof command === "string" && project.projectRoot !== undefined && projectHasPluginEvents(project.projectRoot))
    return undefined;
  return entry
    ? unavailableEventMessage(command, where)
    : `${unknownEventMessage(command, where)} GB Studio would build the game without it.`;
}
function editDistance(left, right) {
  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let row = 1; row <= left.length; row += 1) {
    const current = [row];
    for (let column = 1; column <= right.length; column += 1) {
      current[column] = Math.min(
        previous[column] + 1,
        current[column - 1] + 1,
        previous[column - 1] + (left[row - 1] === right[column - 1] ? 0 : 1),
      );
    }
    previous = current;
  }
  return previous[right.length];
}
// The current events closest to an unknown command: the most shared words, then the fewest edits.
function nearestEvents(command, limit = 3) {
  const words = (value) =>
    value
      .toLowerCase()
      .replace(/^event_/, "")
      .split("_")
      .filter(Boolean);
  const wanted = new Set(words(command));
  return Object.entries(eventCatalog().events)
    .filter(([, entry]) => !entry.deprecated && !entry.unavailable)
    .map(([id]) => ({
      id,
      shared: words(id).filter((word) => wanted.has(word)).length,
      distance: editDistance(command.toUpperCase(), id),
    }))
    .sort(
      (left, right) => right.shared - left.shared || left.distance - right.distance || left.id.localeCompare(right.id),
    )
    .slice(0, limit)
    .map(({ id }) => id);
}
export function unknownEventMessage(command, where) {
  if (typeof command !== "string" || command.length === 0) return `${where} has no command.`;
  return `${where} uses ${command}, which is not a GB Studio ${eventCatalog().gbStudioVersion} event or one of the project's plugin events. Nearest events: ${nearestEvents(command).join(", ")} (event_describe describes them).`;
}
// GB Studio's legacy migration (migrateLegacyProjectVersions.ts) turns EVENT_WEAPON_ATTACK into EVENT_LAUNCH_PROJECTILE
// when it loads a single-file project from before 2.0.0 r14, so such a project builds it. As in its migrateProject,
// versions 1.x reach 2.0.0 r2, and every 2.0.0 release from r1 to r13 passes the r13 to r14 step.
function legacyMigrationConverts(command, descriptor) {
  if (command !== "EVENT_WEAPON_ATTACK" || !isObject(descriptor) || descriptor._resourceType === "project")
    return false;
  const version = descriptor._version === "1" ? "1.0.0" : descriptor._version || "1.0.0";
  if (["1.0.0", "1.1.0", "1.2.0"].includes(version)) return true;
  const release = descriptor._release || "1";
  return version === "2.0.0" && typeof release === "string" && /^(?:[1-9]|1[0-3])$/.test(release);
}
// How to replace an event GB Studio deprecates, or undefined for one it does not.
export function deprecatedEventGuidance(command) {
  const entry = Object.hasOwn(eventCatalog().events, command) ? eventCatalog().events[command] : undefined;
  if (!entry?.deprecated) return undefined;
  return entry.replacement
    ? `Use ${entry.replacement} instead (event_describe describes it): ${entry.migration}`
    : entry.migration;
}
// For an event GB Studio lists but cannot compile (always one it deprecates): why, and how to replace it.
export function unavailableEventMessage(command, where) {
  const entry = Object.hasOwn(eventCatalog().events, command) ? eventCatalog().events[command] : undefined;
  if (!entry?.unavailable) return undefined;
  return `${where} uses ${command}. ${entry.unavailable} ${deprecatedEventGuidance(command)}`;
}
function eventCategories(entry) {
  return entry.groups.length > 0 ? entry.groups : [EVENT_UNCATEGORIZED];
}
function eventSummaryLine(entry) {
  const summary = entry.summary ?? entry.name;
  const sentence = /^.*?[.!?](?=\s|$)/.exec(summary)?.[0] ?? summary;
  return sentence.length > 140 ? `${sentence.slice(0, 139)}…` : sentence;
}
function eventListing(id, entry) {
  return {
    event: id,
    name: entry.name,
    summary: eventSummaryLine(entry),
    ...(entry.deprecated ? { deprecated: true, ...(entry.replacement ? { replacement: entry.replacement } : {}) } : {}),
    ...(entry.unavailable ? { unavailable: true } : {}),
  };
}
function searchWords(text) {
  return text
    .toLowerCase()
    .split(/[^a-z0-9$]+/)
    .filter(Boolean);
}
function eventSearchWords(id, entry) {
  return searchWords(
    [id, entry.name, entry.summary ?? "", ...eventCategories(entry), ...entry.fields.map((field) => field.key)].join(
      " ",
    ),
  );
}
function compactEvent(id, entry) {
  const field = ({ description, when, whenAny, sceneTypes, ...kept }) => kept;
  return {
    event: id,
    name: entry.name,
    ...(entry.deprecated
      ? {
          deprecated: true,
          ...(entry.replacement ? { replacement: entry.replacement } : {}),
          migration: entry.migration,
        }
      : {}),
    ...(entry.unavailable ? { unavailable: entry.unavailable } : {}),
    ...(entry.requires ? { requires: entry.requires } : {}),
    fields: entry.fields.map(field),
    ...(entry.branches ? { branches: entry.branches.map((branch) => branch.key) } : {}),
    example: entry.example,
  };
}
export function describeEvents(input) {
  const { gbStudioVersion, events } = eventCatalog();
  if (input.events !== undefined) {
    if (
      input.query !== undefined ||
      input.category !== undefined ||
      input.includeDeprecated !== undefined ||
      input.cursor !== undefined
    ) {
      throw new GameStudioProjectError(
        "INVALID_INPUT",
        "Give events to describe them, or query/category/includeDeprecated/cursor to list; not both.",
      );
    }
    const unknown = input.events.filter((id) => !Object.hasOwn(events, id.toUpperCase()));
    if (unknown.length > 0) {
      const words = unknown
        .flatMap((id) =>
          id
            .toLowerCase()
            .replace(/^event_/, "")
            .split("_"),
        )
        .filter((word) => word.length > 1);
      const near = Object.keys(events)
        .filter((id) => words.some((word) => id.toLowerCase().includes(word)))
        .slice(0, 12);
      throw new GameStudioProjectError(
        "EVENT_NOT_FOUND",
        `GB Studio ${gbStudioVersion} has no event ${unknown.join(", ")}${near.length > 0 ? `; similar: ${near.join(", ")}` : ""}. Search with query.`,
      );
    }
    const compact = input.detail === "compact";
    const described = [...new Set(input.events.map((id) => id.toUpperCase()))].map((id) => {
      if (compact) return compactEvent(id, events[id]);
      const { groups, ...entry } = events[id];
      return {
        event: id,
        ...entry,
        categories: eventCategories({ groups }),
        ...(EVENT_NOTES[id] ? { note: EVENT_NOTES[id] } : {}),
      };
    });
    const types = new Set(described.flatMap((entry) => entry.fields.map((field) => field.type)));
    return {
      gbStudioVersion,
      events: described,
      fieldTypes: Object.fromEntries(
        [...types]
          .filter((type) => Object.hasOwn(EVENT_FIELD_TYPES, type))
          .map((type) => [type, EVENT_FIELD_TYPES[type]]),
      ),
      ...(described.some((entry) => entry.branches)
        ? {
            branches:
              "Each branch is an array of events under the event's children, e.g. children.true; a branch with when is compiled only when its conditions hold.",
          }
        : {}),
      ...(compact
        ? {}
        : {
            conditions:
              'A field or branch with when is used only when every condition holds (whenAny: when one list holds in full). Each condition names an arg (key) and a test (eq, ne, in, gt, gte, lt, lte, set), or where the script is: parallaxEnabled (the scene has parallax), entityType/entityTypeNot (the script belongs to "scene", "actor", "trigger" or "customEvent").',
          }),
      ids: "Omit event ids: script_edit, scene_apply and dialogue_update give every event, nested ones included, a unique id.",
    };
  }
  if (
    input.query === undefined &&
    input.category === undefined &&
    input.includeDeprecated === undefined &&
    input.cursor === undefined
  ) {
    const counts = new Map();
    for (const entry of Object.values(events)) {
      if (entry.deprecated) continue;
      for (const group of eventCategories(entry)) counts.set(group, (counts.get(group) ?? 0) + 1);
    }
    return {
      gbStudioVersion,
      eventCount: Object.keys(events).length,
      deprecatedCount: Object.values(events).filter((entry) => entry.deprecated).length,
      categories: [...counts]
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([name, count]) => ({ name, count })),
      nextStep: "List with category, query or includeDeprecated, then describe up to 5 events by name.",
    };
  }
  const category = input.category?.toLowerCase();
  const words = searchWords(input.query ?? "");
  const matches = [];
  let deprecatedHidden = 0;
  for (const [id, entry] of Object.entries(events)) {
    if (category !== undefined && !eventCategories(entry).some((group) => group.toLowerCase() === category)) continue;
    const text = eventSearchWords(id, entry);
    if (!words.every((word) => text.some((candidate) => candidate.startsWith(word)))) continue;
    if (entry.deprecated && input.includeDeprecated !== true && id !== input.query?.toUpperCase()) {
      deprecatedHidden += 1;
      continue;
    }
    const title = searchWords(`${id} ${entry.name}`);
    matches.push({ id, entry, score: words.filter((word) => title.includes(word)).length, length: title.length });
  }
  matches.sort(
    (left, right) => right.score - left.score || left.length - right.length || left.id.localeCompare(right.id),
  );
  if (
    matches.length === 0 &&
    category !== undefined &&
    !Object.values(events).some((entry) => eventCategories(entry).some((group) => group.toLowerCase() === category))
  ) {
    throw new GameStudioProjectError(
      "INVALID_INPUT",
      `No category ${input.category}; call event_describe with no arguments to list them.`,
    );
  }
  const start = Number(input.cursor ?? 0);
  const end = start + EVENT_LIST_LIMIT;
  return {
    matches: matches.slice(start, end).map(({ id, entry }) => eventListing(id, entry)),
    total: matches.length,
    ...(end < matches.length
      ? { nextCursor: String(end), nextStep: "Call again with the same arguments and this cursor for the rest." }
      : {}),
    ...(deprecatedHidden > 0 ? { deprecatedHidden } : {}),
  };
}
const MENU_RIGHT_COLUMN = 10;
const SCREEN_TILES_WIDE = 20;
const SCREEN_TILES_HIGH = 18;
const TILE_PIXELS = 8;
const AUTHORING_WARNINGS_PER_CODE = 3;
const AUTHORING_EVENT_BUDGET = 100_000;
const AUTHORING_SCRIPT_CALL_DEPTH = 16;
const ZERO_TOKEN = /\$0\$/;
// Scripts these events start run later, beside the one that starts them: they begin with sprites in an unknown state
// and what they hide is not hidden for the events after them.
const DEFERRED_SCRIPT_EVENTS = new Set([
  "EVENT_THREAD_START",
  "EVENT_SET_INPUT_SCRIPT",
  "EVENT_SET_TIMER_SCRIPT",
  "EVENT_SET_MUSIC_ROUTINE",
  "EVENT_SET_ADVENTURE_CALLBACK_SCRIPT",
  "EVENT_SET_PLATFORMER_CALLBACK_SCRIPT",
  "EVENT_SAVE_DATA",
]);
function catalogHolds(condition, args) {
  if ("parallaxEnabled" in condition || "entityType" in condition || "entityTypeNot" in condition) return true;
  const value = args[condition.key];
  if ("soundType" in condition) return true;
  if ("in" in condition && !condition.in.some((option) => option === value || (option === null && value === undefined)))
    return false;
  if ("eq" in condition && value !== condition.eq) return false;
  if ("ne" in condition && value === condition.ne) return false;
  if ("gt" in condition && !(value > condition.gt)) return false;
  if ("gte" in condition && !(value >= condition.gte)) return false;
  if ("lt" in condition && !(value < condition.lt)) return false;
  if ("lte" in condition && !(value <= condition.lte)) return false;
  if ("set" in condition && Boolean(value) !== condition.set) return false;
  return true;
}
function catalogShown(record, args) {
  return (record.whenAny ?? [record.when ?? []]).some((alternative) =>
    alternative.every((condition) => catalogHolds(condition, args)),
  );
}
function textArgValues(value) {
  return typeof value === "string"
    ? [value]
    : Array.isArray(value)
      ? value.filter((item) => typeof item === "string")
      : [];
}
function tilePosition(resource) {
  const scale = resource.coordinateType === "pixels" ? TILE_PIXELS : 1;
  const x = Number(resource.x) / scale;
  const y = Number(resource.y) / scale;
  return Number.isFinite(x) && Number.isFinite(y) ? { x: Math.floor(x), y: Math.floor(y) } : undefined;
}
// A 16 px sprite at tile (x, y) covers x..x+1 and y-1..y; the menu covers columns 10-19 from row 18 - items - 2 down.
function underMenu(position, items) {
  return position.x + 1 >= MENU_RIGHT_COLUMN && position.y >= SCREEN_TILES_HIGH - items - 2;
}
function scriptOwnerName(kind, resource) {
  return `${kind} ${resource.name || resource.id}`;
}
// Where the player stands when a scene starts: the project's start position and every scene switch's landing tile.
function playerPositions(inventory, owners, scripts) {
  const positions = new Map();
  const add = (sceneId, x, y) => {
    if (typeof sceneId !== "string" || !Number.isFinite(x) || !Number.isFinite(y)) return;
    positions.set(sceneId, [...(positions.get(sceneId) ?? []), { x, y }]);
  };
  const settings = inventory.settings ?? {};
  add(settings.startSceneId, Number(settings.startX), Number(settings.startY));
  const numberOf = (value) =>
    isObject(value) && value.type === "number" ? Number(value.value) : typeof value === "number" ? value : NaN;
  const walk = (events, depth) => {
    if (!Array.isArray(events) || depth > MAXIMUM_EVENT_DEPTH) return;
    for (const event of events) {
      if (!isObject(event)) continue;
      if (event.command === "EVENT_SWITCH_SCENE" && isObject(event.args))
        add(event.args.sceneId, numberOf(event.args.x), numberOf(event.args.y));
      if (isObject(event.children)) for (const branch of Object.values(event.children)) walk(branch, depth + 1);
    }
  };
  for (const owner of owners)
    for (const [key, events] of Object.entries(owner.resource)) if (SCRIPT_KEYS.test(key)) walk(events, 0);
  for (const script of scripts.values()) walk(script.resource.script, 0);
  return positions;
}
export function authoringWarnings(inventory, shared = {}) {
  const { events: catalog } = eventCatalog();
  const settings = inventory.settings ?? {};
  const colorProject = settings.colorMode === "color" || settings.colorMode === "mixed";
  const scripts = shared.scripts ?? new Map();
  const prefabs = shared.prefabs ?? new Map();
  const found = new Map();
  const deprecated = new Map();
  let budget = AUTHORING_EVENT_BUDGET;
  const owners = [];
  for (const scene of inventory.scenes ?? []) {
    const sceneName = scene.name || scene.id;
    const place = {
      scene,
      sceneType: String(scene.type || settings.defaultSceneTypeId || "TOPDOWN").toUpperCase(),
      fixedCamera: Number(scene.width) <= SCREEN_TILES_WIDE && Number(scene.height) <= SCREEN_TILES_HIGH,
      callStack: [],
      inScript: false,
    };
    owners.push({
      place: { ...place, where: `scene ${sceneName}`, resourcePath: scene.resourcePath },
      resource: scene,
    });
    for (const [kind, resources, prefabType] of [
      ["actor", scene.actors ?? [], "actorPrefab"],
      ["trigger", scene.triggers ?? [], "triggerPrefab"],
    ]) {
      for (const resource of resources) {
        const prefab = prefabs.get(resource.prefabId);
        const inherited = prefab?.type === prefabType ? prefab : undefined;
        const where = `${scriptOwnerName(kind, resource)}${inherited ? ` (prefab ${inherited.resource.name || inherited.id})` : ""} in scene ${sceneName}`;
        owners.push({
          place: {
            ...place,
            where,
            resourcePath: inherited?.resourcePath ?? resource.resourcePath,
            ...(inherited && isObject(resource.prefabScriptOverrides)
              ? { overrides: resource.prefabScriptOverrides }
              : {}),
          },
          resource: inherited?.resource ?? resource,
        });
      }
    }
  }
  const players = playerPositions(inventory, owners, scripts);
  function warn(place, event, code, message, suggestedAction) {
    const key = `${code}\0${place.resourcePath}\0${event.id ?? place.where}\0${place.scene.id}`;
    if (!found.has(key))
      found.set(key, {
        severity: "warning",
        code,
        message,
        suggestedAction,
        event: event.command,
        resourcePath: place.resourcePath,
      });
  }
  function check(place, event, args, entry, hidden) {
    if (place.sceneType === "LOGO" && entry.warnings?.some((warning) => warning.sceneTypes?.includes("LOGO"))) {
      warn(
        place,
        event,
        "TEXT_IN_LOGO_SCENE",
        `${event.command} in ${place.where} shows text in a LOGO scene, which GB Studio draws with glitches.`,
        "Give the scene another type (scene_update type TOPDOWN), or show the text in a scene that is not LOGO.",
      );
    }
    // The text the compiler prints: no comment, no menu option past the menu's items.
    const texts =
      event.command === "EVENT_COMMENT"
        ? []
        : entry.fields.filter((field) => field.type === "textarea" && catalogShown(field, args));
    if (texts.some((field) => textArgValues(args[field.key]).some((text) => ZERO_TOKEN.test(text)))) {
      warn(
        place,
        event,
        "TEXT_VARIABLE_TOKEN",
        `${event.command} in ${place.where} prints $0$, which GB Studio reads as ${place.inScript ? "the custom script's parameter V0" : "the local variable L0"}, not global variable 0.`,
        "Write $00$ for global variable 0: GB Studio drops one leading zero, so $01$ and $1$ both print variable 1.",
      );
    }
    if (entry.deprecated) {
      const uses = deprecated.get(event.command) ?? {
        authored: new Set(),
        where: place.where,
        resourcePath: place.resourcePath,
        entry,
      };
      uses.authored.add(`${place.resourcePath}\0${event.id ?? uses.authored.size}`);
      deprecated.set(event.command, uses);
    }
    // GB Studio's compiler draws a menu without a layout as the right-hand menu.
    if (
      event.command === "EVENT_MENU" &&
      (args.layout ?? "menu") === "menu" &&
      colorProject &&
      place.fixedCamera &&
      !hidden
    ) {
      const items = Math.min(8, Math.max(0, Number(args.items) || 0));
      const covered = (place.scene.actors ?? [])
        .filter((actor) => {
          const position = tilePosition(actor);
          return position && underMenu(position, items);
        })
        .map((actor) => actor.name || actor.id);
      if ((players.get(place.scene.id) ?? []).some((position) => underMenu(position, items)))
        covered.unshift("the player");
      if (covered.length > 0) {
        warn(
          place,
          event,
          "ACTORS_OVER_MENU",
          `The menu in ${place.where} opens over ${covered.slice(0, 4).join(", ")}${covered.length > 4 ? ` and ${covered.length - 4} more` : ""}; on Game Boy Color, actor sprites draw over a menu with layout menu.`,
          "Put EVENT_HIDE_SPRITES before the menu on every path to it and EVENT_SHOW_SPRITES after it, or use layout dialogue (full width, which hides the sprites below it).",
        );
      }
    }
  }
  // The branches the compiler builds: those it declares for these args (a switch's first `choices` cases, no false
  // branch when __disableElse), or every branch of an event the catalog does not know.
  function compiledBranches(entry, args, children) {
    return Object.entries(children).filter(([key, events]) => {
      if (!Array.isArray(events)) return false;
      if (!entry) return true;
      const branch = entry.branches?.find((candidate) => candidate.key === key);
      return branch !== undefined && catalogShown(branch, args);
    });
  }
  function callScript(place, args, hidden, depth) {
    const script = scripts.get(args.customEventId);
    if (!script || place.callStack.includes(script.id) || place.callStack.length >= AUTHORING_SCRIPT_CALL_DEPTH)
      return hidden;
    const name = script.resource.name || script.id;
    return visit(
      {
        ...place,
        where: `custom script ${name} (called from ${place.where})`,
        resourcePath: script.resourcePath,
        callStack: [...place.callStack, script.id],
        overrides: undefined,
        inScript: true,
      },
      script.resource.script,
      hidden,
      depth + 1,
    );
  }
  // Whether sprites are hidden after this event on every path through it, given that they were before it (hidden).
  function after(place, event, args, entry, hidden, depth) {
    if (event.command === "EVENT_HIDE_SPRITES") return true;
    if (event.command === "EVENT_SHOW_SPRITES") return false;
    if (event.command === "EVENT_CALL_CUSTOM_EVENT") return callScript(place, args, hidden, depth);
    const branches = compiledBranches(entry, args, isObject(event.children) ? event.children : {});
    if (branches.length === 0) return hidden;
    if (DEFERRED_SCRIPT_EVENTS.has(event.command)) {
      for (const [, events] of branches) visit(place, events, false, depth + 1);
      return hidden;
    }
    const ends = branches.map(([, events]) => visit(place, events, hidden, depth + 1));
    if (event.command === "EVENT_GROUP") return ends[0];
    // An if or a switch with its false branch runs exactly one branch.
    if (branches.some(([key]) => key === "false")) return ends.every(Boolean);
    // A loop or a rate limit runs its body any number of times: a later pass starts where the first one ended.
    branches.forEach(([, events], index) => {
      if (hidden && !ends[index]) visit(place, events, false, depth + 1);
    });
    return hidden && ends.every(Boolean);
  }
  function visit(place, events, hidden, depth) {
    if (!Array.isArray(events) || depth > MAXIMUM_EVENT_DEPTH) return hidden;
    for (const event of events) {
      if (--budget < 0) return hidden;
      if (!isObject(event) || typeof event.command !== "string") continue;
      let args = isObject(event.args) ? event.args : {};
      const override = place.overrides?.[event.id];
      if (isObject(override) && isObject(override.args)) args = { ...args, ...override.args };
      if (args.__comment) continue;
      const entry = catalog[event.command];
      if (entry) check(place, event, args, entry, hidden);
      hidden = after(place, event, args, entry, hidden, depth);
    }
    return hidden;
  }
  for (const { place, resource } of owners) {
    for (const [key, events] of Object.entries(resource)) {
      if (SCRIPT_KEYS.test(key)) visit(place, events, false, 0);
    }
  }
  for (const [command, uses] of deprecated) {
    found.set(`DEPRECATED_EVENT\0${command}`, {
      severity: "warning",
      code: "DEPRECATED_EVENT",
      message: `${command} is deprecated in GB Studio (${uses.authored.size} in the project, first in ${uses.where}).`,
      suggestedAction: uses.entry.replacement
        ? `Replace it with ${uses.entry.replacement}: ${uses.entry.migration}`
        : uses.entry.migration,
      event: command,
      resourcePath: uses.resourcePath,
    });
  }
  return capAuthoringWarnings([...found.values()]);
}
// A few warnings of each kind and one line for the rest, so a pattern repeated across a project names its places
// without filling the build's diagnostics.
function capAuthoringWarnings(warnings) {
  const byCode = new Map();
  for (const warning of warnings) byCode.set(warning.code, [...(byCode.get(warning.code) ?? []), warning]);
  return [...byCode.values()].flatMap((same) => {
    if (same.length <= AUTHORING_WARNINGS_PER_CODE) return same;
    const kept = same.slice(0, AUTHORING_WARNINGS_PER_CODE - 1);
    const rest = same.slice(kept.length);
    const places = [...new Set(rest.map((warning) => warning.resourcePath))];
    return [
      ...kept,
      {
        severity: "warning",
        code: same[0].code,
        message: `${rest.length} more ${same[0].code} warnings, in ${places.slice(0, 5).join(", ")}${places.length > 5 ? ` and ${places.length - 5} more files` : ""}.`,
        suggestedAction: same[0].suggestedAction,
      },
    ];
  });
}
export async function authoringScripts(inventory) {
  const supplemental = await supplementalResources(inventory.projectRoot, {});
  const scripts = new Map(
    supplemental.filter((resource) => resource.type === "script").map((resource) => [resource.id, resource]),
  );
  if (inventory.format === "legacy") {
    for (const script of Array.isArray(inventory.descriptor?.customEvents) ? inventory.descriptor.customEvents : []) {
      if (isObject(script) && typeof script.id === "string" && script.id && !scripts.has(script.id))
        scripts.set(script.id, {
          type: "script",
          id: script.id,
          resourcePath: path.basename(inventory.projectPath),
          resource: script,
        });
    }
  }
  const prefabs = new Map(
    supplemental
      .filter((resource) => resource.type === "actorPrefab" || resource.type === "triggerPrefab")
      .map((resource) => [resource.id, resource]),
  );
  return { scripts, prefabs };
}
