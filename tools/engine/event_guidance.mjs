// What GB Studio's event definitions do not say, written by hand for the event catalog (event_catalog.mjs checks each
// table against the definitions every time it writes the catalog, so a GB Studio update that changes an event stops it).

// GB Studio marks events deprecated without naming what replaces them or how. Every deprecated event is listed, with
// its replacement (or none) and how to convert one, so a GB Studio update that deprecates another stops the generator.
const variable = (name) => `{"type":"variable","value":<${name}>}`;
const ifCondition = (condition, caveat) =>
  `EVENT_IF with condition ${condition} and the same true and false branches.${caveat ? ` ${caveat}` : ""}`;
const labels =
  "Labels have no current event: rewrite the jump as structure. A backward EVENT_GOTO_LABEL that repeats events " +
  "becomes an EVENT_LOOP_WHILE around them, with the condition that kept it jumping as the loop's condition; a " +
  "forward one that skips events becomes an EVENT_IF whose false branch holds the skipped events. Remove both events " +
  "of the pair.";

export const DEPRECATIONS = {
  EVENT_ACTOR_INVOKE: {
    migration:
      "Move the actor's interact script into a custom script and call it with EVENT_CALL_CUSTOM_EVENT from the actor " +
      "and from here.",
  },
  EVENT_ACTOR_MOVE_TO_VALUE: {
    replacement: "EVENT_ACTOR_MOVE_TO",
    migration:
      `Keep actorId; x becomes ${variable("vectorX")}, y ${variable("vectorY")}, units "tiles". The old event moves ` +
      'horizontally first and through walls and actors: set moveType "horizontal" and collideWith [] to keep that ' +
      '(the editor\'s default collideWith ["walls"] stops at walls).',
  },
  EVENT_ACTOR_SET_ANIMATE: {
    migration: "It compiles to nothing in this GB Studio: remove it.",
  },
  EVENT_ACTOR_SET_FRAME_TO_VALUE: {
    replacement: "EVENT_ACTOR_SET_FRAME",
    migration: `Keep actorId; frame becomes ${variable("variable")}.`,
  },
  EVENT_ACTOR_SET_POSITION_TO_VALUE: {
    replacement: "EVENT_ACTOR_SET_POSITION",
    migration: `Keep actorId; x becomes ${variable("vectorX")}, y ${variable("vectorY")}, units "tiles".`,
  },
  EVENT_DEFINE_LABEL: { replacement: "EVENT_LOOP_WHILE", migration: labels },
  EVENT_GOTO_LABEL: { replacement: "EVENT_LOOP_WHILE", migration: labels },
  EVENT_IF_EXPRESSION: {
    replacement: "EVENT_IF",
    migration: ifCondition(
      '{"type":"gt","valueA":{"type":"expression","value":<expression>},"valueB":{"type":"number","value":0}}',
      "The old event is true only above 0; an expression alone as the condition is true for anything but 0, so a " +
        "negative result would take the other branch.",
    ),
  },
  EVENT_IF_FALSE: {
    replacement: "EVENT_IF",
    migration: ifCondition(
      `{"type":"lte","valueA":${variable("variable")},"valueB":{"type":"number","value":0}}`,
      "The old event takes its true branch at 0 or below.",
    ),
  },
  EVENT_IF_TRUE: {
    replacement: "EVENT_IF",
    migration: ifCondition(
      `{"type":"gt","valueA":${variable("variable")},"valueB":{"type":"number","value":0}}`,
      "The old event takes its true branch only above 0; a variable alone as the condition is true for anything " +
        "but 0, so a negative value would take the other branch.",
    ),
  },
  EVENT_IF_VALUE: {
    replacement: "EVENT_IF",
    migration: ifCondition(
      `{"type":<op>,"valueA":${variable("variable")},"valueB":{"type":"number","value":<comparator>}}`,
      "operator ==, !=, <, >, <=, >= becomes type eq, ne, lt, gt, lte, gte.",
    ),
  },
  EVENT_IF_VALUE_COMPARE: {
    replacement: "EVENT_IF",
    migration: ifCondition(
      `{"type":<op>,"valueA":${variable("vectorX")},"valueB":${variable("vectorY")}}`,
      "operator ==, !=, <, >, <=, >= becomes type eq, ne, lt, gt, lte, gte.",
    ),
  },
  EVENT_SET_FALSE: {
    replacement: "EVENT_SET_VALUE",
    migration: 'Keep variable; value becomes {"type":"number","value":0}.',
  },
  EVENT_SET_TRUE: {
    replacement: "EVENT_SET_VALUE",
    migration: 'Keep variable; value becomes {"type":"number","value":1}.',
  },
  EVENT_WEAPON_ATTACK: {
    replacement: "EVENT_LAUNCH_PROJECTILE",
    migration:
      "Keep spriteSheetId, actorId, collisionGroup and collisionMask; offset becomes initialOffset; set " +
      'directionType "actor" with otherActorId the same actor, so it launches the way the source faces. The old ' +
      "attack had no speed or lifetime: choose speed and lifeTime (a short lifeTime for a swing) and check the frame.",
  },
};

const wait = { command: "EVENT_WAIT", args: { frames: { type: "number", value: 1 }, units: "frames" } };

// Examples for events whose editor default does nothing useful or freezes the game, and what an event needs first.
// An example is one event, or a list of events with this one among them when it only works with others.
export const EXAMPLES = {
  EVENT_CALL_CUSTOM_EVENT: {
    requires:
      "A custom script in the project: its id from project_inventory's scripts. Give one " +
      '"$variable[V<n>]$" arg per variable parameter the script declares (a variable id; a ScriptValue for a ' +
      'parameter taken by value) and one "$actor[<n>]$" arg per actor parameter (an actor id, "player" or "$self$"). ' +
      "Without the script GB Studio compiles nothing for the call.",
    example: {
      command: "EVENT_CALL_CUSTOM_EVENT",
      args: { customEventId: "<custom script>", "$variable[V0]$": "<variable>", "$actor[0]$": "player" },
    },
  },
  EVENT_DEFINE_LABEL: {
    example: [
      { command: "EVENT_GOTO_LABEL", args: { label: "skip" } },
      { command: "EVENT_TEXT", args: { text: "Never shown." } },
      { command: "EVENT_DEFINE_LABEL", args: { label: "skip" } },
    ],
  },
  EVENT_GOTO_LABEL: {
    requires: "An EVENT_DEFINE_LABEL with the same label in the same script.",
    example: [
      { command: "EVENT_GOTO_LABEL", args: { label: "skip" } },
      { command: "EVENT_TEXT", args: { text: "Never shown." } },
      { command: "EVENT_DEFINE_LABEL", args: { label: "skip" } },
    ],
  },
  EVENT_LOOP: {
    requires:
      "It never ends: run it in a thread (EVENT_THREAD_START) or an actor's updateScript, and give its body an " +
      "EVENT_WAIT so the game keeps running.",
    example: { command: "EVENT_LOOP", args: {}, children: { true: [wait] } },
  },
  EVENT_LOOP_WHILE: {
    requires: "The body must change what the condition reads, and wait a frame, or the game freezes.",
    example: {
      command: "EVENT_LOOP_WHILE",
      args: {
        condition: {
          type: "lt",
          valueA: { type: "variable", value: "<variable>" },
          valueB: { type: "number", value: 10 },
        },
      },
      children: { true: [{ command: "EVENT_INC_VALUE", args: { variable: "<variable>" } }, wait] },
    },
  },
};

// GB Studio's form for these field types replaces the definition's default with its own shape before it stores the
// event; the catalog gives that shape (a data table's definition default is an older array the compiler cannot read).
export const EDITOR_DEFAULTS = {
  dataTable: { variables: ["0"], rows: [{ label: "", values: [{ type: "number", value: 0 }] }] },
};
