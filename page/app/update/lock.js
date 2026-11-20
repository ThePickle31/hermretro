// Whether hermretro is being updated right now. Everything that starts work (a Build turn, Continue after a lost turn,
// New Game, Restore, the toolchain install, removing the tools, setting up the hermretro profile) checks it in its
// handler and greys its control out (useUpdating): nothing new starts while the update swaps and reloads the plugin.
import { atom, useValue } from '#sdk'

export const UPDATE_LOCK = atom(false)

export function isUpdating() {
  return Boolean(UPDATE_LOCK.get())
}

/** For a control's `disabled`: re-renders when an update starts or ends. */
export function useUpdating() {
  return Boolean(useValue(UPDATE_LOCK))
}

/** Set by the update while it runs (app/update/use-update.js). */
export function setUpdating(active) {
  UPDATE_LOCK.set(Boolean(active))
}

export const UPDATING_MESSAGE = 'hermretro is updating. You can start again in a moment.'
