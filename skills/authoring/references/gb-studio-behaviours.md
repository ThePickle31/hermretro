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
  with `layout: "menu"` takes the right half, and on Game Boy Color actors (and the player) under it show through.
  Put `EVENT_HIDE_SPRITES` before the menu and `EVENT_SHOW_SPRITES` after it. The build warns for actors placed under
  such a menu in a scene no larger than the screen; in a scrolling scene, check the frame.
- **The overlay stays across scenes.** `EVENT_OVERLAY_SHOW` (a HUD, a black screen) stays on after a scene change
  until `EVENT_OVERLAY_HIDE`. A text box or menu uses the same window and leaves it closed, so draw a HUD again after
  one.

## Scripts

- **A scene's start script runs locked.** The scene's `script` runs to its end before the player can move or other
  scripts run, so an endless `EVENT_LOOP` there freezes the game. Loop in a thread (`EVENT_THREAD_START`) or in an
  actor's `updateScript`.
- **Text tokens need two digits** *(build warning)*. `$00$` prints global variable 0, `$12$` variable 12, `$L0$` a
  local, `$T0$` a temporary. `$0$` reads as no variable, and GB Studio prints another one instead. Write global
  variables with two digits or more.
- **Button scripts fire on press only.** `EVENT_SET_INPUT_SCRIPT` runs once per press. For something that lasts while
  a button is held, check `EVENT_IF_INPUT` every frame in a thread.
- **Deprecated events** *(build warning)*. They still build, but GB Studio is removing them: `EVENT_IF_VALUE`,
  `EVENT_IF_TRUE`, `EVENT_IF_FALSE`, `EVENT_IF_VALUE_COMPARE` and `EVENT_IF_EXPRESSION` become `EVENT_IF` with a
  condition; `EVENT_SET_TRUE` and `EVENT_SET_FALSE` become `EVENT_SET_VALUE`. `chromatic_event_describe` names each
  replacement.

## Movement and collisions

- **Moving a walking top-down player overshoots.** A hit script runs a frame after the touch, while a grid-moving
  player is between cells. `EVENT_ACTOR_SET_POSITION` on the player then keeps the move going from the new spot, and
  it stops one cell further on. Respawn by switching to the same scene at the respawn tile
  (`chromatic_script_transition`), which starts the player still.
- **The default collision box is the bottom half.** GB Studio gives a 16 × 16 sprite a 16 × 8 box at its bottom, so
  on a 16 px top-down grid only the lower half of a cell touches. hermretro's imports give top-down sprites the full
  16 × 16 cell on a 16 px grid; check other sprites with `chromatic_sprite_inspect` and set the box with
  `chromatic_sprite_edit`.
- **Collision groups.** Touching an actor in collision group 1, 2 or 3 runs the scene's `playerHit1Script`,
  `playerHit2Script` or `playerHit3Script` and the actor's own `script`, then the player cannot be hit for 20
  frames. Such an actor cannot be talked to with A; in a top-down scene an actor without a group runs its `script` when
  the player faces it and presses A.

## Dialogue

- **The first A finishes the typing, the second closes the box.** While a text box is still typing, A shows the
  rest of the page at once; the next A closes it (or turns the page). A playtest that presses A once while the text
  types leaves the box open: press A, step a few frames, press A again, and check the frame.
