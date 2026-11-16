// Messages between the Studio page and the player frame (`desktop-src/frame/`). Every message is a
// plain object whose `cs` field names it. The page sends `{ cs: 'cmd', type: CMD.*, ... }`; the frame
// answers with `{ cs: FROM_FRAME.*, ... }`. Contract: docs/dev/STUDIO-PAGES.md "Page ↔ frame messages".

export const TO_FRAME = 'cmd'

/** Page → frame command types. */
export const CMD = Object.freeze({
  KEY: 'key', // { key, code, down }: a key the page caught while the game is armed
  SNAP: 'snap', // { id }: answer FROM_FRAME.SNAP with the current frame as a PNG data URL
  HOLD: 'hold', // pause the game and its sound while the surface is hidden
  RELEASE: 'release', // undo HOLD
  THEME: 'theme', // { css }: the app's colours for the frame's own UI
  VIEW: 'view', // { view }: one of VIEWS (inline UI only)
  PRESS: 'press', // { action }: press one of the player's own buttons (PRESSABLE)
  FINISH: 'finish', // { id }: show the handheld in this finish (a DEVICE_COLORS id)
  ANNOTATE: 'annotate', // { on }: enter or leave annotate mode
  MARK_COLOR: 'mark-color', // { id, index, value }: preview a colour on a marked object (value null resets it)
  MARK_REMOVE: 'mark-remove', // { id }: drop one mark
  MARKS_TAKE: 'marks-take' // { id }: answer FROM_FRAME.TAKEN with the marks and their close-ups, then leave annotate
})

/** Frame → page message names. */
export const FROM_FRAME = Object.freeze({
  LOG: 'log', // { level, text }
  FOCUS: 'focus', // { value }: the frame's window gained or lost focus
  SNAP: 'snap', // { id, url }
  NOTE: 'annotate', // { target, note, image }: one object and a note, from the in-frame note card
  STATE: 'state', // { ready, paused, muted, annotating, recording }
  MARKS: 'marks', // { marks }: the marked objects while annotating (inline UI)
  TAKEN: 'marks-taken' // { id, image, marks }: the marks with close-ups, answering MARKS_TAKE
})

/** How the frame shows the player. `full` is ModRetro's whole player page (Emulator page, side tab);
 *  `screen` and `device` are the inline player's: the bare game screen or the handheld around it, with
 *  every control drawn by the page instead. */
export const VIEWS = Object.freeze(['full', 'screen', 'device'])

/** The player's own buttons the page may press (their `data-action` in the engine's view). */
export const PRESSABLE = Object.freeze(['play', 'sound', 'restart', 'history', 'screenshot', 'record-video', 'annotate'])

/** Native size of the Game Boy screen. */
export const SCREEN_W = 160
export const SCREEN_H = 144

/** The handheld art (engine view.js `.cgv-handheld`): 850 × 1440, the screen 62.1177% of its width. */
export const DEVICE_RATIO = 850 / 1440
export const DEVICE_SCREEN_SHARE = 0.621177
