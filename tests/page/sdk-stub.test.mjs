// The SDK stand-in's react-query surface (tests/page/sdk-stub.mjs): the query client's cache.
// Run alone: node tests/page/sdk-stub.test.mjs
import assert from 'node:assert/strict'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

registerAliases() // the stand-in imports react, found through the aliases' package lookup

const { scenario, useQueryClient } = await import('./sdk-stub.mjs')

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
