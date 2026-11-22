// The New Game draft (page/pages/build/new-game-draft.js) and the provider check under it
// (page/pages/build/composer/provider-notice.js), from the sources: what onboarding's handoff keeps and merges.
// Run alone: node tests/page/new-game-draft.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'

import { registerAliases } from './aliases.mjs'

registerAliases()

const { NEW_GAME_DRAFT, clearNewGameDraft, editNewGameDraft, restoreNewGameDraft, takeFirstIdea } = await import('../../page/pages/build/new-game-draft.js')
const { noProviderReady } = await import('../../page/pages/build/composer/provider-notice.js')

const memory = initial => {
  const kept = { ...initial }

  return { kept, storage: { get: (key, fallback) => kept[key] ?? fallback, set: (key, value) => { kept[key] = value } } }
}

test('a draft left on an earlier visit comes back with the plugin', () => {
  const { storage } = memory({ buildNewGame: { idea: 'a moth who collects lamps', plan: true } })

  restoreNewGameDraft({ storage })
  assert.equal(NEW_GAME_DRAFT.get().idea, 'a moth who collects lamps')
  assert.equal(NEW_GAME_DRAFT.get().plan, true)
})

test('the first idea opens New Game with it, keeping what was already typed there', () => {
  const { kept, storage } = memory({ buildSelected: 'game-1' })

  restoreNewGameDraft({ storage })
  editNewGameDraft({ idea: 'my own words', plan: false })
  const before = NEW_GAME_DRAFT.get().seq

  takeFirstIdea({ idea: '  a frog delivering mail  ', plan: true }, { storage })
  assert.equal(kept.buildSelected, 'new', 'Build opens on New Game')
  assert.equal(NEW_GAME_DRAFT.get().idea, 'my own words\n\na frog delivering mail', 'nothing the user wrote is lost')
  assert.equal(NEW_GAME_DRAFT.get().plan, true, 'Plan first stays chosen')
  assert.ok(NEW_GAME_DRAFT.get().seq > before, 'a new handoff, so an open New Game takes it in')
  assert.deepEqual(kept.buildNewGame, { idea: 'my own words\n\na frog delivering mail', plan: true }, 'kept for a reload')

  takeFirstIdea({ idea: 'a frog delivering mail', plan: false }, { storage })
  assert.equal(NEW_GAME_DRAFT.get().idea, 'my own words\n\na frog delivering mail', 'an idea already in the box is not added again')
  assert.equal(NEW_GAME_DRAFT.get().plan, false, 'the latest choice of how to start wins')
})

test('handing over the same idea twice, or none, does not repeat or wipe the draft', () => {
  const { storage } = memory({})

  restoreNewGameDraft({ storage })
  clearNewGameDraft(NEW_GAME_DRAFT.get().rev)
  takeFirstIdea({ idea: 'a lighthouse', plan: false }, { storage })
  takeFirstIdea({ idea: 'a lighthouse', plan: false }, { storage })
  assert.equal(NEW_GAME_DRAFT.get().idea, 'a lighthouse')
  takeFirstIdea({ idea: '', plan: true }, { storage })
  assert.equal(NEW_GAME_DRAFT.get().idea, 'a lighthouse', 'Plan it first with an empty box keeps the draft')
  assert.equal(NEW_GAME_DRAFT.get().plan, true)
})

test('a started game clears the draft, in memory and in storage', () => {
  const { kept, storage } = memory({})

  restoreNewGameDraft({ storage })
  editNewGameDraft({ idea: 'something', plan: true })
  clearNewGameDraft(NEW_GAME_DRAFT.get().rev)
  assert.equal(NEW_GAME_DRAFT.get().idea, '')
  assert.equal(NEW_GAME_DRAFT.get().plan, false)
  assert.equal(kept.buildNewGame, null)
})

test('a start clears only the draft it sent: a newer idea written meanwhile stays', () => {
  const { kept, storage } = memory({})

  restoreNewGameDraft({ storage })
  editNewGameDraft({ idea: 'the idea being sent', plan: false })
  const sent = NEW_GAME_DRAFT.get().rev

  editNewGameDraft({ idea: 'a second idea, written while the first one started' })
  clearNewGameDraft(sent)
  assert.equal(NEW_GAME_DRAFT.get().idea, 'a second idea, written while the first one started')
  assert.deepEqual(kept.buildNewGame, { idea: 'a second idea, written while the first one started', plan: false })
})

test('the provider notice shows only when Hermes listed providers and none is signed in with a model', () => {
  assert.equal(noProviderReady(undefined), false, 'unknown while loading')
  assert.equal(noProviderReady({}), false, 'an older Hermes without a provider list')
  assert.equal(noProviderReady({ providers: [] }), true)
  assert.equal(noProviderReady({ providers: [{ slug: 'anthropic', authenticated: false, models: ['m'] }] }), true)
  assert.equal(noProviderReady({ providers: [{ slug: 'openai-codex', authenticated: true, models: [] }] }), true, 'signed in with no model')
  assert.equal(noProviderReady({ providers: [{ slug: 'openai-codex', authenticated: true, models: ['gpt'] }] }), false)
})
