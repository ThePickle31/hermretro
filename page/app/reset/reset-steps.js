// The factory reset (Settings → Plugins → hermretro): its parts, the choices that follow from others, and the run.
// The backend deletes hermretro's data one part at a time (`reset`, backend/setup/reset.py, the studio chats with
// Hermes's own command); the studio profile is deleted through Hermes. Then hermretro updates itself. No React here, so the steps
// can be tested on their own.
import { host } from '#sdk'
import { STUDIO_PROFILE } from '#app/ids.js'
import { forgetRoute } from '#app/routing.js'
import { RPC_RESET } from '#app/rpc.js'
import { busyChats, busySentence, requestOn, runUpdate, UPDATE_MARKER, UPDATE_PENDING } from '#app/update/flow.js'

export const RESET_PARTS = [
  { id: 'games', label: 'Games' },
  { id: 'history', label: 'Build history' },
  { id: 'chats', label: 'Studio chats' },
  { id: 'profile', label: 'Studio profile' },
  { id: 'settings', label: 'Plugin settings' },
  { id: 'toolchain', label: 'Toolchain & engine' },
  { id: 'logs', label: 'Logs & captures' }
]

export const DEFAULT_CHOICES = Object.fromEntries(RESET_PARTS.map(part => [part.id, part.id === 'games' ? 'keep' : 'delete']))

/** The Hermes connection a target ({ route, profile }) reaches: its route's, else the one the app is on now. */
export function connectionOf(target) {
  return target?.route?.connectionId || host.activeConnectionId?.() || 'local'
}

/** The profile the app itself is on now (where a target without a route goes). */
export function appProfile() {
  try {
    return host.state.profile?.get?.() ?? null
  } catch {
    return null
  }
}

// What the page remembers across the reload an update ends with, so the settings page that loads says how it went.
export const RESET_MARKER = 'resetDone'

// The backend's parts, in the order they are deleted (the contract's `reset`).
// Logs before Games: a deleted game takes its captures, and its folder is how Logs & captures finds them.
const BACKEND_PARTS = ['history', 'logs', 'games', 'chats', 'settings', 'toolchain']
const PART_TIMEOUT_MS = 600_000
const label = id => RESET_PARTS.find(part => part.id === id)?.label ?? id

/** The choices as they apply: a part that cannot be deleted stays (`locked`: id → why), and a deleted part takes what
 *  lives inside it (Games and the studio profile take build history; the profile takes its chats and its settings). Answers
 *  `{ choices, forced, notes }`: `forced` names why each overridden part is deleted or kept (its choice is locked),
 *  `notes` what a part still free to choose loses anyway. */
export function settleChoices(choices, locked = {}) {
  const settled = { ...choices }
  const forced = {}

  for (const [id, why] of Object.entries(locked)) {
    if (why) {
      settled[id] = 'keep'
      forced[id] = why
    }
  }

  const takes = (owner, part, why) => {
    if (settled[owner] === 'delete' && !forced[part]) {
      settled[part] = 'delete'
      forced[part] = why
    }
  }

  takes('profile', 'chats', 'Deleted with the studio profile')
  takes('profile', 'settings', 'Deleted with the studio profile')
  takes('profile', 'history', 'Deleted with the studio profile')
  takes('games', 'history', 'Deleted with Games')

  // Said, never locked: a deleted game takes the captures in its folder, whatever Logs & captures says; and kept build
  // history loses its numbered builds with the chats they were made in (dated snapshots and backups stay usable).
  const notes = {}

  if (settled.games === 'delete' && settled.logs !== 'delete' && !forced.logs) {
    notes.logs = 'Game captures go with Games'
  }

  if (settled.chats === 'delete' && settled.history !== 'delete' && !forced.history) {
    notes.history = 'Numbered builds go with the chats'
  }

  return { choices: settled, forced, notes }
}

/** The run's steps, in order: stop, the backend's parts, the profile, the update. A deleted profile takes its chats. */
export function resetSteps(choices) {
  const deleted = id => choices[id] === 'delete' && !(id === 'chats' && choices.profile === 'delete')

  return [
    { id: 'stop', label: 'Stopping the studio' },
    ...BACKEND_PARTS.filter(deleted).map(id => ({ id, label: label(id) })),
    ...(deleted('profile') ? [{ id: 'profile', label: label('profile') }] : []),
    { id: 'update', label: 'Updating hermretro' }
  ]
}

async function deleteStudioProfile(studio) {
  if (typeof host.deleteProfile !== 'function') {
    throw new Error('This Hermes cannot delete a profile from a plugin. Update Hermes, then try again.')
  }

  await host.deleteProfile(studio.route ?? STUDIO_PROFILE)
  forgetRoute()
}

/** One backend part: its bytes deleted. A refusal throws, carrying what it deleted before stopping (`removed`). */
async function backendPart(target, part) {
  const answer = await requestOn(target, RPC_RESET, { part }, PART_TIMEOUT_MS)

  if (!answer?.ok) {
    throw Object.assign(new Error(answer?.error || `${label(part)} could not be deleted.`), { removed: Number(answer?.removed_bytes) || 0, partly: Boolean(answer?.partly) })
  }

  return Number(answer.removed_bytes) || 0
}

/** The summary of a reset this page has not shown yet (one that ended with the page reloaded), or null. */
export function pendingReset(ctx) {
  try {
    const summary = ctx.storage.get(RESET_MARKER, null)

    return summary && typeof summary === 'object' ? summary : null
  } catch {
    return null
  }
}

export function forgetReset(ctx) {
  remember(ctx, RESET_MARKER, null)
}

/** Whether an unfinished update's mark is for this install (a mark from before marks named one counts as this). */
function sameInstall(pending, install) {
  return !pending.profile || (pending.profile === install.profile && pending.connectionId === connectionOf(install))
}

function stored(ctx, key) {
  try {
    return ctx.storage.get(key, null)
  } catch {
    return null
  }
}

function remember(ctx, key, value) {
  try {
    ctx.storage.set(key, value)
  } catch {
    // for this visit only
  }
}

/** Run the reset. `target` answers the backend's parts (the hermretro profile when there is one), `studio` is that
 *  profile ({ route, profile }, null when there is none), `install` where Hermes updates hermretro (null for a linked
 *  checkout), `version` the installed version. `onStep(i)` follows `resetSteps(choices)`. Resolves to the summary the
 *  done screen shows, never throws: `{ deleted, kept, failed: { step, error } | null, update, from }`, `update` being
 *  runUpdate's outcome (null when the update did not run). */
export async function runReset({ ctx, choices, here, ambient, target, studio, install, version, onStep = () => {} }) {
  const steps = resetSteps(choices)
  const gone = new Set()
  // What is still there: the parts no finished step deleted (the profile takes its chats and build history).
  const kept = () => RESET_PARTS.filter(part => !gone.has(part.id)).map(part => part.label)
  // `here` and `ambient`: the restart after a reload checks them too.
  const summary = { deleted: 0, kept: kept(), failed: null, update: null, from: version, here, ambient, install }
  const profileGone = choices.profile === 'delete'

  for (const [index, step] of steps.entries()) {
    onStep(index)

    try {
      // A turn under way must not lose its game or its chat: before each step, nothing may be running in the studio
      // (a chat started from elsewhere after the first check is caught at the next step).
      if (step.id !== 'update' && !gone.has('profile')) {
        const building = await busyChats(studio)

        if (building.length) {
          throw new Error(busySentence(building, 'reset hermretro'))
        }
      }

      if (step.id === 'stop') {
        await backendPart(target, 'stop')
      } else if (BACKEND_PARTS.includes(step.id)) {
        summary.deleted += await backendPart(target, step.id)
      } else if (step.id === 'profile') {
        await deleteStudioProfile(studio)
        gone.add('chats').add('history').add('settings')

        // Hermes moves the app off the profile it deleted, to its default one: the restart expects that.
        if (summary.ambient === STUDIO_PROFILE) {
          summary.ambient = 'default'
        }
      } else if (install) {
        // An earlier update that installed but did not finish loading is finished, never read as up to date; one left
        // unfinished on another Hermes is not this one's to finish or to forget.
        const pending = stored(ctx, UPDATE_PENDING)

        if (pending && !sameInstall(pending, install)) {
          throw new Error('Another hermretro update is unfinished. Finish it on the hermretro page first.')
        }

        const mark = error => remember(ctx, UPDATE_PENDING, { at: Date.now(), error, connectionId: connectionOf(install), profile: install.profile })

        // The page the app loads after an update shows the done screen from this.
        remember(ctx, RESET_MARKER, summary)
        summary.update = await runUpdate({
          install,
          resume: Boolean(pending),
          studio: profileGone ? null : studio,
          busy: () => busyChats(profileGone ? null : studio),
          // The stop step was refused while the toolchain installed, and the update lock (held from the start of the
          // reset) keeps Setup from starting one since.
          confirmInstallIdle: async () => null,
          installed: () => mark(null),
          refused: () => remember(ctx, UPDATE_PENDING, null),
          remember: marker => {
            remember(ctx, UPDATE_PENDING, null)
            remember(ctx, UPDATE_MARKER, { ...marker, from: version })
            remember(ctx, RESET_MARKER, { ...summary, update: { kind: 'updated', restart: marker.restart } })
          }
        })

        if (summary.update.kind === 'partial') {
          mark(summary.update.error ?? null)
        }
      }
    } catch (error) {
      summary.failed = { step: step.label, error: String(error?.message ?? error) }
      summary.deleted += error?.removed ?? 0

      // Partly deleted is not kept: the Stopped at line names it.
      if (error?.partly) {
        gone.add(step.id)
        summary.kept = kept()
      }

      break
    }

    if (step.id !== 'stop' && step.id !== 'update') {
      gone.add(step.id)
      summary.kept = kept()
    }
  }

  // Kept until the done screen closes (`forgetReset`): the app may reload this page with the updated copy first.
  if (summary.update) {
    remember(ctx, RESET_MARKER, summary)
  }

  return summary
}
