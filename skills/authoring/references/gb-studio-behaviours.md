# GB Studio behaviours

How GB Studio's compiler and engine behave in ways that build without an error but show up only in play. The
[event cookbook](event-cookbook.md) already follows these. `chromatic_rom_build` warns about the ones marked
*(build warning)*.

## Graphics

- **Sprite palettes show three colours.** GB Studio compiles a sprite palette as `[c0, c0, c1, c3]`: hardware
  entry 0 is transparent, so the colours on screen are the palette's entries 0, 1 and 3, and entry 2 never shows.
  Give `chromatic_palette_create` three colours for a sprite palette (lightest, middle, darkest).
- **LOGO scenes cannot show text** *(build warning)*. Text in a `LOGO` scene (`EVENT_TEXT`, `EVENT_MENU`,
  `EVENT_CHOICE`, `EVENT_TEXT_DRAW`) draws with glitches. Use `LOGO` for a still picture only; a title or ending with
  words is a `TOPDOWN` scene with the player hidden (`EVENT_ACTOR_HIDE` with `actorId: "player"`).
- **Actor sprites draw over a right-hand menu** *(build warning)*. A text box, a choice and an `EVENT_MENU` with
  `layout: "dialogue"` span the screen's width, and the engine hides sprites below their top edge. An `EVENT_MENU`
  with `layout: "menu"` (or no `layout`: the compiler's default) takes the right half, and on Game Boy Color actors
  and the player under it show through. Put `EVENT_HIDE_SPRITES` before the menu, on every path that reaches it,
  and `EVENT_SHOW_SPRITES` after it; a hide in another branch, a thread or a button script does not count. The
  build warns for actors placed under such a menu, and for the player's start or landing tile, in a scene no larger
  than the screen; in a scrolling scene, check the frame. In a scene with parallax the engine never hides sprites
  under the window, so full-width boxes show them too: hide the sprites there as well.
- **The overlay stays across scenes.** `EVENT_OVERLAY_SHOW` (a HUD, a black screen) stays on after a scene change
  until `EVENT_OVERLAY_HIDE`. A text box or menu uses the same window and leaves it closed, so draw a HUD again after
  one.
- **Text tiles are reused in a ring.** Every `EVENT_TEXT_DRAW`, text box and menu draws its letters into new tiles
  from one ring, 116 tiles when the game runs in colour and 52 in a mono game (up to one tile per character), and
  when the ring is full GB Studio starts again from its first tile, whatever still shows it. Text left on screen is overwritten once
  that much newer text has been drawn: a HUD whose parts are redrawn separately turns to garbage (`SS 5`). Keep all
  text that stays up together in one draw and redraw it whole (the
  [event cookbook's HUD](event-cookbook.md#hud-text-on-the-overlay) does).

## Scripts

- **A scene's start script runs locked.** The scene's `script` runs to its end before the player can move or other
  scripts run, so an endless `EVENT_LOOP` there freezes the game. Loop in a thread (`EVENT_THREAD_START`) or in an
  actor's `updateScript`, and wait in every pass (`EVENT_WAIT`): a loop that never waits stops everything else.
- **A sound that waits before the first wait leaves the scene blank.** GB Studio fades a scene in just before the
  first event of its start script that waits on screen (`EVENT_WAIT`, text, a move, a fade) and runs everything
  before it on a blank screen. `EVENT_SOUND_PLAY_EFFECT` with `wait: true` is not such an event, so a jingle of
  waiting sounds at the top of a title or ending script keeps the screen white until it ends. Put an `EVENT_FADE_IN`
  or `EVENT_WAIT` first, or play the sounds with `wait: false`.
- **`$0$` is not global variable 0** *(build warning)*. The compiler drops one leading zero from a text token's
  number: `$00$` prints global variable 0, `$01$` and `$1$` both print variable 1, `$12$` variable 12. `$0$` becomes
  an empty name, which GB Studio fills with the script's default variable: the local `L0` in a scene, actor or
  trigger script, the parameter `V0` in a custom script. `$L0$` is a local, `$T0$` a temporary.
- **Button scripts fire on press only.** `EVENT_SET_INPUT_SCRIPT` runs once per press. For something that lasts while
  a button is held, check `EVENT_IF_INPUT` every frame in a thread.
- **Deprecated events** *(build warning)*. Most still build, but GB Studio is removing them: `EVENT_IF_VALUE`,
  `EVENT_IF_TRUE`, `EVENT_IF_FALSE`, `EVENT_IF_VALUE_COMPARE` and `EVENT_IF_EXPRESSION` become `EVENT_IF` with a
  condition; `EVENT_SET_TRUE` and `EVENT_SET_FALSE` become `EVENT_SET_VALUE`. Convert the args, not only the
  command: `EVENT_IF_TRUE` is true only above 0, while a variable alone as an `EVENT_IF` condition is true for
  anything but 0. `EVENT_WEAPON_ATTACK` no longer builds at all. `chromatic_event_describe` gives each replacement
  and its conversion, and the build warning repeats it, for events in custom scripts and prefabs too.

## Movement and collisions

- **Moving a walking top-down player can overshoot.** A hit script runs a frame after the touch, while a
  grid-moving player may be between cells. `EVENT_ACTOR_SET_POSITION` moves the player but keeps its movement state:
  on a tile-aligned destination the move resets on the next update, but on an unaligned one the move can carry on
  from the new spot (stopping a cell further on) or be clamped. Respawn by switching to the same scene at the respawn
  tile (`chromatic_script_transition`), which starts the player still.
- **Check the collision box.** GB Studio 4.3.2 gives a new 16 × 16 sprite a 16 × 16 box, but sprites from older or
  migrated projects often have a 16 × 8 box at their bottom, so on a 16 px top-down grid only the lower half of a cell
  touches. hermretro's imports give top-down sprites the full 16 × 16 cell on a 16 px grid; check other sprites with
  `chromatic_sprite_inspect` and set the box with `chromatic_sprite_edit`.
- **Collision groups.** Touching an actor in collision group 1, 2 or 3 runs the scene's `playerHit1Script`,
  `playerHit2Script` or `playerHit3Script` and the actor's own `script`, then the player cannot be hit for 20
  frames. Such an actor cannot be talked to with A; in a top-down scene an actor without a group runs its `script` when
  the player faces it and presses A.
- **Projectile hits.** A projectile hits actors whose group is in its `collisionMask` and runs the hit actor's
  `hit1Script`, `hit2Script` or `hit3Script` for the projectile's own `collisionGroup` (1, 2, 3), never its
  `script`; an actor with no group is never hit. A projectile whose mask includes `player` and hits the player runs
  the scene's `playerHit1Script` to `playerHit3Script` for its group instead. While the hit script runs, more hits on
  the same actor are ignored (the projectile still vanishes unless `destroyOnHit` is false). Recipes:
  [shooting](event-cookbook.md#shooting).
- **Script keys.** The script tools accept any `scriptKey` that ends in `Script`, but GB Studio compiles only these:
  an actor's `script`, `startScript`, `updateScript`, `hit1Script`, `hit2Script`, `hit3Script`; a scene's `script`,
  `playerHit1Script`, `playerHit2Script`, `playerHit3Script`; a trigger's `script` (on enter) and `leaveScript`.
  Events under any other key never run.
- **Actors off screen are inactive.** The engine stops each actor that is more than about 48 px (three 16 px cells)
  outside the screen: its `updateScript` ends, and it touches nothing and cannot be hit. It starts again, with its
  `updateScript` from the top, when scrolling brings its position back near the screen, so in a scrolling scene
  enemies wake as they come into view. A hit script already running carries on. The player and an actor with
  `persistent: true` (`chromatic_actor_update` `properties`) stay active off screen.

## Dialogue

- **The first A finishes the typing, the second closes the box.** While a text box is still typing, A shows the
  rest of the page at once; the next A closes it (or turns the page). A playtest that presses A once while the text
  types leaves the box open: press A, step a few frames, press A again, and check the frame.
