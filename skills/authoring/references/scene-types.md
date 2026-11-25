# Scene types

How GB Studio 4.3.2's `PLATFORM`, `TOPDOWN` and `SHMUP` scenes move the player, so a plan and a level fit them
without a test build. Their settings are engine fields: read them with `chromatic_engine_field_inspect` (it lists only
the project's overrides; anything not listed has GB Studio's default, given here) and change them with
`chromatic_engine_field_update`. Positions inside the engine are in subpixels: 32 to a pixel, 256 to a tile.

## Platformer

GB Studio's default jump and run, worked out from its platformer code at the default field values:

| Move | Default |
| --- | --- |
| Walk | 1.56 px per frame at full speed, reached after about 40 frames (`plat_walk_vel` 6400, `plat_walk_acc` 152) |
| Run (hold B) | 2.56 px per frame, reached after about 45 frames (`plat_run_vel` 10496, `plat_run_acc` 228) |
| Jump with A held | rises 66 px (just over 8 tiles), top after 32 frames, back to the same height after 50 frames |
| Jump with A tapped | rises 16 px (2 tiles), back down after 18 frames |
| Jump length, same height | about 80 px (10 tiles) at full walking speed, about 130 px (16 tiles) at full running speed |

Frames here are frames in the air. A tap is A pressed for one frame and let go before the jump's first frame in
the air; held for that frame too, the jump rises 20 px over 20 frames, and letting go later gives a height between
that and 66 px.

A field's units: velocities (`plat_*_vel`) are 128ths of a subpixel per frame, so 4096 is 1 px per frame;
`plat_jump_vel` 16384 starts a jump at 4 px per frame, and gravity (`plat_grav` 1792, or `plat_hold_grav` 512 while
A is held) slows it each frame. Change one, and the jump changes with it: measure it again on a build before
placing gaps and hazards against it.

## Top-down grid

- **The grid.** A tap moves the player one cell; holding a direction starts another step at each cell, and the
  player always stops on a whole cell. Cells are 8 px by default, 16 px with
  `chromatic_engine_field_update {"updates":[{"id":"topdown_grid","value":16}]}`. On the 16 px grid the player's
  cells are at even tile x and odd tile y (GB Studio snaps the start there), so put actors and items at even x and
  odd y too, and build walls and triggers from 2 × 2-tile blocks starting at even x and even y. A patrolling actor
  moves 2 tiles per cell.
- **Actors block the player.** Every actor with collisions on (not pinned, not disabled with
  `EVENT_ACTOR_COLLISIONS_DISABLE`) stops the player in front of it. Walking into an actor in a collision group
  counts as touching it (its hit scripts run) and the player stays where it is; to take a pickup the player walks
  into it, then on into the cell once its script has disabled its collisions.
- **Touches are checked on cells.** The engine checks whether the player overlaps an actor only while the player
  stands on a cell (every frame) and as it starts a move, not while it is between cells. A moving enemy passes
  through the player; the hit comes when the player is standing or about to step.
- **The player's box in corridors.** On the 8 px grid a 16 × 16 box needs passages 2 tiles wide and 2 tiles high,
  and the player gets through only when lined up with them exactly, one press at a time. For a maze, use the 16 px
  grid with 2 × 2-tile walls; or, on the 8 px grid, give the player a 16 × 8 box at its feet
  (`chromatic_sprite_edit` `boundsX` 0, `boundsY` 0, `boundsWidth` 16, `boundsHeight` 8), so passages left and
  right need only 1 tile of height, and keep up-and-down passages 2 tiles wide.

## Shoot-'em-up

- **Direction.** The scene scrolls the way the player faces when it starts: the project's `startDirection` for the
  first scene, or the `direction` of the `chromatic_script_transition` that enters it: facing right, the screen
  travels right through the scene; left, up and down likewise. Place the player at the end the screen starts from.
- **Speed.** `shooter_scroll_speed` is in subpixels per frame: 32 (the default) is 1 px per frame, 60 px a
  second; it goes from 0 to 128 (4 px per frame), and at 0 the screen does not scroll. Crossing a scene from one end
  takes about (scene length in px − 160) ÷ (speed ÷ 32) frames for a horizontal scroll, with 144 in place of 160
  for a vertical one; a player placed partway along starts the screen there, so count only the distance left.
- **The end.** Scrolling stops for good when the far edge of the scene reaches the edge of the screen. Nothing else
  happens there: put the boss, a trigger or a timed scene switch at that end.
- **Movement** (`SHOOTER_MOVEMENT_TYPE`). GB Studio's default, `MOVEMENT_TYPE_FREE`, moves the player in all eight
  directions and keeps it inside the screen along the scroll. With `MOVEMENT_TYPE_LOCK_PERPENDICULAR` the player
  moves only across the scroll (up and down in a horizontal shooter, left and right in a vertical one) and the
  screen carries it along. Walls stop the player's own moves but not the scroll, so leave a way past every wall the
  scroll brings at the player. Projects made from the starter template set `MOVEMENT_TYPE_LOCK_PERPENDICULAR`: check
  the field before planning controls.
- **Across the scroll** the scene's edges stop the player, and the screen follows it once it is more than 16 px
  from the middle. A horizontal shooter whose scene is 18 tiles high (the screen) never scrolls up or down.
- **Triggers** (`SHOOTER_TRIGGER_ACTIVATION`) run when the player touches them (`ON_PLAYER_COLLISION`, the
  default) or as they scroll onto the screen (`ON_SCREEN_ENTER`), which suits starting a wave or a boss.
- **Hurting walls** (`SHOOTER_WALL_COLLISION_GROUP`): `COLLISION_GROUP_1` to `_3` makes touching a wall run the
  scene's `playerHit1Script` to `playerHit3Script`, as an actor in that group does.
- **Enemies wake as they scroll in.** An actor's `updateScript` starts as its tile column (or row) scrolls in, a
  tile or so ahead of the screen's edge, and stops once it is about 48 px behind the screen (see
  [actors off screen](gb-studio-behaviours.md#movement-and-collisions)). Place enemies along the level where they
  should appear.

## Shooting

Enemies go in collision group 2, so touching one runs the scene's `playerHit2Script` like a
[hazard](event-cookbook.md#hazard). The player's shots are projectiles in group 1 that hit only actors in group 2
(`collisionMask`); the scene's start script fires one each time A is pressed (fire the way the level scrolls):

```json
[
  {"command": "EVENT_SET_INPUT_SCRIPT", "args": {"input": ["a"], "override": true}, "children": {"true": [
    {"command": "EVENT_LAUNCH_PROJECTILE", "args": {"spriteSheetId": "<shot sprite id>", "spriteStateId": "", "actorId": "player", "x": 0, "y": 0, "directionType": "direction", "direction": "right", "speed": 3, "animSpeed": 15, "lifeTime": 1, "initialOffset": 0, "loopAnim": true, "destroyOnHit": true, "collisionGroup": "1", "collisionMask": ["2"]}}
  ]}}
]
```

A shot in group 1 runs the enemy's `hit1Script` (group 2 runs `hit2Script`, group 3 `hit3Script`), not its
`script`. This enemy `hit1Script` removes the enemy, counts it in variable 0 and redraws the
[HUD](event-cookbook.md#hud-text-on-the-overlay) (script target
`{"sceneId": "<scene id>", "actorId": "<enemy id>", "scriptKey": "hit1Script"}`):

```json
[
  {"command": "EVENT_ACTOR_DEACTIVATE", "args": {"actorId": "$self$"}},
  {"command": "EVENT_INC_VALUE", "args": {"variable": "0"}},
  {"command": "EVENT_OVERLAY_SHOW", "args": {"color": "white", "x": 0, "y": 17}},
  {"command": "EVENT_TEXT_DRAW", "args": {"text": "COINS $00$ LIVES $01$", "x": 1, "y": 0, "location": "overlay"}}
]
```

`EVENT_ACTOR_DEACTIVATE` stops the enemy's `updateScript` and keeps it gone until the scene is entered again; the
hit script itself runs on to its end. Hiding it with collisions off would leave its `updateScript` firing.

An enemy fires back from its `updateScript`. Its shots hit only the player, and a shot in group 3 runs the scene's
`playerHit3Script`:

```json
[
  {"command": "EVENT_LAUNCH_PROJECTILE", "args": {"spriteSheetId": "<shot sprite id>", "spriteStateId": "", "actorId": "$self$", "x": 0, "y": 0, "directionType": "target", "targetActorId": "player", "speed": 2, "animSpeed": 15, "lifeTime": 2, "initialOffset": 0, "loopAnim": true, "destroyOnHit": true, "collisionGroup": "3", "collisionMask": ["player"]}},
  {"command": "EVENT_WAIT", "args": {"time": {"type": "number", "value": 1.5}, "units": "time"}}
]
```

Projectile `speed` is in pixels per frame and `lifeTime` in seconds (at most 4). A shot that hits the player runs
the hit script even during the 20 frames after a touch. Which actor a shot hits, and when a second shot is ignored:
[projectile hits](gb-studio-behaviours.md#movement-and-collisions).
