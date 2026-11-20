// Whether hermretro is being updated right now, for anything that starts work in the hermretro profile (the Build
// page's sends, New Game, Restore): nothing new starts while the update swaps and reloads the plugin.
const lock = { active: false }

export function isUpdating() {
  return lock.active
}

/** Set by the update while it runs (app/update/use-update.js). */
export function setUpdating(active) {
  lock.active = Boolean(active)
}

export const UPDATING_MESSAGE = 'hermretro is updating. You can start again in a moment.'
