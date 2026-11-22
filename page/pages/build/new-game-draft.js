// The New Game box's draft: the idea and the chosen way to start (Build it / Plan first), kept until the game is
// started, so leaving the Build page, a reload or onboarding's handoff never loses what the user wrote.
import { atom } from '#sdk'

// { idea, plan, seq, rev }: seq changes on every handoff, so an open New Game screen takes it in; rev on every change,
// so a start clears only the draft it sent.
export const NEW_GAME_DRAFT = atom({ idea: '', plan: false, seq: 0, rev: 0 })
// A start in flight, kept outside the screen: leaving Build and coming back must not start the same game twice.
export const NEW_GAME_STARTING = atom(false)

const KEY = 'buildNewGame'
let storage = null

const clean = value => ({
  idea: typeof value?.idea === 'string' ? value.idea : '',
  plan: value?.plan === true,
  seq: Number.isFinite(value?.seq) ? value.seq : 0,
  rev: Number.isFinite(value?.rev) ? value.rev : 0
})

function save(draft) {
  try {
    storage?.set(KEY, draft.idea || draft.plan ? { idea: draft.idea, plan: draft.plan } : null)
  } catch {
    // this visit only
  }
}

/** With the plugin (build/index.js `register`): the draft left on an earlier visit. */
export function restoreNewGameDraft(ctx) {
  storage = ctx?.storage ?? null

  try {
    const saved = storage?.get(KEY, null)

    if (saved && typeof saved === 'object') {
      NEW_GAME_DRAFT.set({ ...clean(saved), seq: NEW_GAME_DRAFT.get().seq, rev: NEW_GAME_DRAFT.get().rev })
    }
  } catch {
    // nothing saved
  }
}

/** The user typed or picked a way to start. */
export function editNewGameDraft(change) {
  const current = NEW_GAME_DRAFT.get()
  const next = { ...current, ...change, rev: current.rev + 1 }

  NEW_GAME_DRAFT.set(next)
  save(next)
}

/** The game started from the draft at revision ``rev``: the next New Game starts empty, unless the draft changed since
 *  (a newer idea is kept). */
export function clearNewGameDraft(rev) {
  if (NEW_GAME_DRAFT.get().rev === rev) {
    editNewGameDraft({ idea: '', plan: false })
  }
}

/** Onboarding's first idea (`setup.firstIdea`): New Game opens with it in the box, not sent. What the user already
 *  wrote there is kept, with the new idea after it (once: an idea already in the box is not added again). */
export function takeFirstIdea({ idea = '', plan = false } = {}, ctx) {
  const words = String(idea ?? '').trim()
  const current = NEW_GAME_DRAFT.get()
  const kept = current.idea.trim()
  const merged = !words || kept.includes(words) ? current.idea : kept ? `${kept}\n\n${words}` : words

  storage ??= ctx?.storage ?? null

  try {
    ctx?.storage?.set('buildSelected', 'new')
  } catch {
    // this visit only
  }

  const next = { idea: merged, plan: plan === true, seq: current.seq + 1, rev: current.rev + 1 }

  NEW_GAME_DRAFT.set(next)
  save(next)
}
