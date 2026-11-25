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
| Jump with A held | rises 66 px (just over 8 tiles), top after 33 frames, back to the same height after 52 frames |
| Jump with A tapped | rises 20 px (2.5 tiles), back down after 20 frames |
| Jump length, same height | about 80 px (10 tiles) at full walking speed, about 130 px (16 tiles) at full running speed |

A field's units: velocities (`plat_*_vel`) are 128ths of a subpixel per frame, so 4096 is 1 px per frame;
`plat_jump_vel` 16384 starts a jump at 4 px per frame, and gravity (`plat_grav` 1792, or `plat_hold_grav` 512 while
A is held) slows it each frame. Change one, and the jump changes with it: measure it again on a build before
placing gaps and hazards against it.

## Top-down grid

- **The grid.** The player moves one cell per press and stops on whole cells: 8 px by default, 16 px with
  `{"id": "topdown_grid", "value": 16}`. On the 16 px grid the player's cells are at even tile x and odd tile y
  (GB Studio snaps the start there), so put actors and items at even x and odd y too, and build walls
  and triggers from 2 × 2-tile blocks starting at even x and even y. A patrolling actor moves 2 tiles per cell.
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
  second; it goes from 0 to 128 (4 px per frame). Crossing a scene takes (scene length in px − 160) ÷ (speed ÷ 32)
  frames for a horizontal scroll, with 144 in place of 160 for a vertical one.
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
- **Enemies wake as they scroll in.** Actors more than about 48 px off screen are inactive: their `updateScript`
  starts when they come near the screen and stops once they fall behind it (see
  [actors off screen](gb-studio-behaviours.md#movement-and-collisions)). Place enemies along the level where they
  should appear; shooting and hits are in the [event cookbook](event-cookbook.md#shooting).
