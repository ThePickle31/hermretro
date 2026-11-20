// The SDK stand-in's react-query surface (tests/page/sdk-stub.mjs): the query client's cache, and per-key answers.
// Run alone: node tests/page/sdk-stub.test.mjs
import assert from 'node:assert/strict'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

registerAliases() // the stand-in imports react, found through the aliases' package lookup

const { scenario, useQuery, useQueryClient } = await import('./sdk-stub.mjs')
const { jsx } = await import('react/jsx-runtime')
const { renderToStaticMarkup } = await import('react-dom/server')

test('setQueryData and getQueryData share one cache, keyed by the whole query key', () => {
  const client = useQueryClient()

  assert.equal(client.getQueryData(['hermretro', 'games']), undefined)
  assert.deepEqual(client.setQueryData(['hermretro', 'games'], { games: [] }), { games: [] })
  assert.deepEqual(useQueryClient().getQueryData(['hermretro', 'games']), { games: [] }, 'another client sees it')
  client.setQueryData(['hermretro', 'games'], old => ({ games: [...old.games, 'a'] }))
  assert.deepEqual(client.getQueryData(['hermretro', 'games']), { games: ['a'] }, 'an updater gets the old value')
  assert.equal(client.getQueryData(['hermretro']), undefined, 'a shorter key is another entry')
  assert.equal(scenario.queryData.size, 1, 'a test can read the cache as scenario.queryData')
})

test('a function answer is called with the whole query key, so two cards of one per-game query differ', () => {
  const said = { aaa111aaa111: 'Comet Drift: 2 captures', bbb222bbb222: 'Frog Post: none yet' }
  scenario.captures = queryKey => ({ isPending: false, data: said[queryKey[2]] })
  // As the page asks for one game's captures (page/pages/emulator/emulator-bar.js).
  const Card = ({ id }) => jsx('p', { children: useQuery({ queryKey: ['hermretro', 'captures', id] }).data })
  const page = renderToStaticMarkup(jsx('div', { children: [jsx(Card, { id: 'aaa111aaa111' }, 'a'), jsx(Card, { id: 'bbb222bbb222' }, 'b')] }))

  assert.equal(page, '<div><p>Comet Drift: 2 captures</p><p>Frog Post: none yet</p></div>')
  assert.deepEqual(scenario.queries.map(query => query.queryKey[2]), ['aaa111aaa111', 'bbb222bbb222'])
  scenario.captures = { isPending: false, data: 'one answer' }
  assert.equal(useQuery({ queryKey: ['hermretro', 'captures', 'any'] }).data, 'one answer', 'a plain value still answers every key')
  delete scenario.captures
  assert.equal(useQuery({ queryKey: ['hermretro', 'captures', 'any'] }).isPending, true, 'unset: pending')
})
