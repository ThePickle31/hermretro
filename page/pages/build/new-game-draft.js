// The New Game box's draft: the idea and the chosen way to start (Build it / Plan first), kept until the game is
// started, so leaving the Build page, a reload or onboarding's handoff never loses what the user wrote.
import { atom } from '#sdk'

// { idea, plan, seq }: seq changes on every handoff, so an open New Game screen takes it in.
export const NEW_GAME_DRAFT = atom({ idea: '', plan: false, seq: 0 })

const KEY = 'buildNewGame'
let storage = null

const clean = value => ({
  idea: typeof value?.idea === 'string' ? value.idea : '',
  plan: value?.plan === true,
  seq: Number.isFinite(value?.seq) ? value.seq : 0
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
      NEW_GAME_DRAFT.set({ ...clean(saved), seq: NEW_GAME_DRAFT.get().seq })
    }
  } catch {
    // nothing saved
  }
}

/** The user typed or picked a way to start. */
export function editNewGameDraft(change) {
  const next = { ...NEW_GAME_DRAFT.get(), ...change }

  NEW_GAME_DRAFT.set(next)
  save(next)
}

/** The game was started: the next New Game starts empty. */
export function clearNewGameDraft() {
  editNewGameDraft({ idea: '', plan: false })
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

  const next = { idea: merged, plan: plan === true, seq: current.seq + 1 }

  NEW_GAME_DRAFT.set(next)
  save(next)
}
