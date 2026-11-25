# Event cookbook

Short working scripts for common mechanics, in the event JSON the script tools take. Insert a list one event at a
time with `chromatic_script_edit` (`action: "insert"`; an event's `children` go in with it) or as `script.edit`
operations in one `chromatic_scene_apply`. Leave out `id`: the engine gives every event, nested ones included, its
own. For any other event, `chromatic_event_describe` lists categories, searches (`{"query":"camera shake"}`) and
describes up to five events (`{"events":["EVENT_IF"]}`) with every arg, its type, default and allowed values, and
an example event to adapt. Use current events: `EVENT_IF` (not `EVENT_IF_VALUE` or `EVENT_IF_TRUE`) and
`EVENT_SET_VALUE` (not `EVENT_SET_TRUE`); `chromatic_rom_build` warns about deprecated ones.

Variables are global ids written as strings: `"0"`, `"1"` and so on. Name them with `chromatic_variable_set` and use
their ids here; these recipes use `"0"` coins, `"1"` lives, `"2"` menu choice, `"3"` and `"6"` thread handles,
`"4"` coin taken, `"5"` and `"7"` counters. A ScriptValue arg (type `value`) is always an object such as
`{"type":"number","value":3}` or `{"type":"variable","value":"0"}`, never a bare number. The
[GB Studio behaviours](gb-studio-behaviours.md) page explains the choices below.

## HUD text on the overlay

Scene `script` (runs when the scene starts). The overlay (GB Studio's window layer) is shown from row 17, one row
at the bottom of the screen, and the text is drawn into it; `$00$` prints variable 0:

```json
[
  {"command": "EVENT_OVERLAY_SHOW", "args": {"color": "white", "x": 0, "y": 17}},
  {"command": "EVENT_TEXT_DRAW", "args": {"text": "COINS $00$ ", "x": 1, "y": 0, "location": "overlay"}},
  {"command": "EVENT_TEXT_DRAW", "args": {"text": "LIVES $01$ ", "x": 11, "y": 0, "location": "overlay"}}
]
```

- Draw the value again whenever it changes (the pickup below does). The trailing space clears a digit when the
  number gets shorter.
- A text box or menu uses the same window: after one, run these three events again.
- The overlay stays up in the next scene: start a scene without a HUD with
  `{"command": "EVENT_OVERLAY_HIDE", "args": {}}`.

## Pickup

Put the coin actor in collision group 1:
`chromatic_actor_update {"sceneId": "<scene id>", "actorId": "<coin id>", "properties": {"collisionGroup": "1"}}`.
Its `script` then runs when the player touches it (an actor in a collision group is touched, not talked to):

```json
[
  {"command": "EVENT_ACTOR_HIDE", "args": {"actorId": "$self$"}},
  {"command": "EVENT_ACTOR_COLLISIONS_DISABLE", "args": {"actorId": "$self$"}},
  {"command": "EVENT_SET_VALUE", "args": {"variable": "4", "value": {"type": "number", "value": 1}}},
  {"command": "EVENT_INC_VALUE", "args": {"variable": "0"}},
  {"command": "EVENT_SOUND_PLAY_EFFECT", "args": {"type": "beep", "priority": "medium", "pitch": 6, "duration": 0.2, "wait": false}},
  {"command": "EVENT_TEXT_DRAW", "args": {"text": "COINS $00$ ", "x": 1, "y": 0, "location": "overlay"}}
]
```

The coin comes back when the scene is entered again. To keep it taken, its `startScript` hides it when its flag is
set (one variable per coin):

```json
[
  {"command": "EVENT_IF", "args": {"condition": {"type": "eq", "valueA": {"type": "variable", "value": "4"}, "valueB": {"type": "number", "value": 1}}}, "children": {"true": [
    {"command": "EVENT_ACTOR_HIDE", "args": {"actorId": "$self$"}},
    {"command": "EVENT_ACTOR_COLLISIONS_DISABLE", "args": {"actorId": "$self$"}}
  ], "false": []}}
]
```

## Hazard

Put the hazard actors in collision group 2. Touching one runs the scene's `playerHit2Script` (script target
`{"sceneId": "<scene id>", "scriptKey": "playerHit2Script"}`) and the hazard's own `script`; the player then cannot
be hit again for 20 frames. Groups 1 and 3 have `playerHit1Script` and `playerHit3Script`. Lives (variable 1) start
at 0 like every variable: set them once before play, as the title menu's START branch below does, and never in this
scene's start script, which runs again on every respawn.

```json
[
  {"command": "EVENT_SOUND_PLAY_EFFECT", "args": {"type": "crash", "priority": "high", "duration": 0.4, "wait": false}},
  {"command": "EVENT_CAMERA_SHAKE", "args": {"time": 0.3, "units": "time", "shakeDirection": "horizontal", "magnitude": {"type": "number", "value": 3}}},
  {"command": "EVENT_DEC_VALUE", "args": {"variable": "1"}},
  {"command": "EVENT_TEXT_DRAW", "args": {"text": "LIVES $01$ ", "x": 11, "y": 0, "location": "overlay"}},
  {"command": "EVENT_IF", "args": {"condition": {"type": "lte", "valueA": {"type": "variable", "value": "1"}, "valueB": {"type": "number", "value": 0}}}, "children": {"true": [], "false": []}}
]
```

Then fill the branches with scene switches (below), into the `EVENT_IF` by its id: `true` to the game-over scene,
`false` back into this same scene at the respawn tile. Switching scene starts the player still on that tile;
`EVENT_ACTOR_SET_POSITION` on a walking top-down player can carry its move on past the tile (see
[GB Studio behaviours](gb-studio-behaviours.md)).

## Gated exit with a counter

Trigger `script` (runs when the player walks onto the trigger). The exit opens with 5 coins:

```json
[
  {"command": "EVENT_IF", "args": {"condition": {"type": "gte", "valueA": {"type": "variable", "value": "0"}, "valueB": {"type": "number", "value": 5}}}, "children": {"true": [], "false": [
    {"command": "EVENT_TEXT", "args": {"text": "The gate needs\n5 coins."}}
  ]}}
]
```

Put the scene switch into the `true` branch with `chromatic_script_transition` and a `branchPath`.

## Menu that stores a choice

Option *n* sets the variable to *n*; B (with `cancelOnB`) or the last option (with `cancelOnLastOption`) sets 0.
`EVENT_SWITCH` then runs one branch per value (`true0` for `value0` and so on, `false` for anything else). On a
title scene, START sets up a new game (3 lives, no coins) before its scene switch goes into `true0`:

```json
[
  {"command": "EVENT_MENU", "args": {"variable": "2", "items": 3, "option1": "START", "option2": "HOW TO", "option3": "CREDITS", "cancelOnLastOption": false, "cancelOnB": false, "layout": "dialogue"}},
  {"command": "EVENT_SWITCH", "args": {"variable": "2", "choices": 3, "value0": {"type": "number", "value": 1}, "value1": {"type": "number", "value": 2}, "value2": {"type": "number", "value": 3}}, "children": {
    "true0": [
      {"command": "EVENT_SET_VALUE", "args": {"variable": "1", "value": {"type": "number", "value": 3}}},
      {"command": "EVENT_SET_VALUE", "args": {"variable": "0", "value": {"type": "number", "value": 0}}}
    ],
    "true1": [{"command": "EVENT_TEXT", "args": {"text": "Take 5 coins\nto the gate."}}],
    "true2": [{"command": "EVENT_TEXT", "args": {"text": "Made with\nGB Studio."}}],
    "false": []
  }}
]
```

`layout: "dialogue"` spans the screen's width. `layout: "menu"` (also what a menu without `layout` gets) takes the
right half, and on Game Boy Color actor sprites draw over it: put `{"command": "EVENT_HIDE_SPRITES", "args": {}}`
before it and `{"command": "EVENT_SHOW_SPRITES", "args": {}}` after it. Text and menus never belong in a `LOGO`
scene.

## Loops in a thread

A scene's start script runs to its end before the scene plays, so an endless loop there freezes the game. Run
repeating work in a thread, and wait in every pass (a loop that never waits stops everything else); its handle goes
in variable 3:

```json
[
  {"command": "EVENT_THREAD_START", "args": {"variable": "3"}, "children": {"true": [
    {"command": "EVENT_LOOP", "args": {}, "children": {"true": [
      {"command": "EVENT_WAIT", "args": {"time": {"type": "number", "value": 1}, "units": "time"}},
      {"command": "EVENT_INC_VALUE", "args": {"variable": "5"}}
    ]}}
  ]}}
]
```

`{"command": "EVENT_THREAD_STOP", "args": {"variable": "3"}}` ends it. A loop that moves one actor belongs in that
actor's `updateScript` instead, which GB Studio runs over and over while the actor is active.

## Held buttons

A button script (`EVENT_SET_INPUT_SCRIPT`) runs once per press, until the scene changes or
`EVENT_REMOVE_INPUT_SCRIPT` removes it:

```json
[
  {"command": "EVENT_SET_INPUT_SCRIPT", "args": {"input": ["b"], "override": true}, "children": {"true": [
    {"command": "EVENT_SOUND_PLAY_EFFECT", "args": {"type": "tone", "priority": "medium", "frequency": 440, "duration": 0.1, "wait": false}}
  ]}}
]
```

To act for as long as a button is held, check it every frame in a thread:

```json
[
  {"command": "EVENT_THREAD_START", "args": {"variable": "6"}, "children": {"true": [
    {"command": "EVENT_LOOP", "args": {}, "children": {"true": [
      {"command": "EVENT_IF_INPUT", "args": {"input": ["a"]}, "children": {"true": [
        {"command": "EVENT_INC_VALUE", "args": {"variable": "7"}}
      ], "false": []}},
      {"command": "EVENT_WAIT", "args": {"frames": {"type": "number", "value": 1}, "units": "frames"}}
    ]}}
  ]}}
]
```

## Sound effects

The presets are `beep` (`pitch` 1–8), `tone` (`frequency` in Hz) and `crash`; `duration` is in seconds. With
`wait: false` the script goes on while the sound plays; `wait: true` pauses it until the sound ends. A new sound
replaces one still playing unless its `priority` is lower (then the new one is dropped), so a sequence waits for
each sound before the next:

```json
[
  {"command": "EVENT_SOUND_PLAY_EFFECT", "args": {"type": "beep", "priority": "medium", "pitch": 4, "duration": 0.25, "wait": true}},
  {"command": "EVENT_SOUND_PLAY_EFFECT", "args": {"type": "tone", "priority": "medium", "frequency": 523, "duration": 0.15, "wait": true}},
  {"command": "EVENT_SOUND_PLAY_EFFECT", "args": {"type": "crash", "priority": "high", "duration": 0.4, "wait": false}}
]
```

## Scene switch

Write scene switches with `chromatic_script_transition`, not by hand: it checks the destination scene and the
landing tile and writes the typed `EVENT_SWITCH_SCENE`. To put one inside a branch, name the branch:

```text
chromatic_script_transition {"target": {"sceneId": "<scene id>", "triggerId": "<trigger id>", "branchPath": [{"eventId": "<EVENT_IF id>", "branch": "true"}]}, "destinationSceneId": "<destination id>", "x": 10, "y": 13, "direction": "up"}
```

`chromatic_script_inspect` returns the `EVENT_IF` id after the insert.
