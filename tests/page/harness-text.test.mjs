// The page tests' text assertions (harness.mjs): a failure shows the part of the page near the closest match.
// Run alone: node tests/page/harness-text.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'

import path from 'node:path'

import { assertHides, assertShows, modulesFrom, nearest, selectedPageTab, tabButton } from './harness.mjs'

const page = 'x'.repeat(50_000) + ' Node.js 26.13.0 (from Hermes) ' + 'y'.repeat(50_000)

test('the closest match is the longest leading part of a string or a RegExp the page has', () => {
  assert.deepEqual(nearest(page, 'Node.js 26.13.0 (from Python)'), { at: 50_001, matched: 'Node.js 26.13.0 (from ' })
  assert.equal(nearest(page, /Node\.js 26\.13\.0 \(from Python\)/).matched, 'Node.js 26.13.0 (from ')
  assert.equal(nearest(page, 'Nothing like it').matched, '')
})

test('a failure shows about 300 characters around the closest match, not the whole page', () => {
  const failure = (fn) => { try { fn() } catch (error) { return error.message } assert.fail('it passed') }
  for (const message of [
    failure(() => assertShows(page, /from Python/, 'the source')),
    failure(() => assertShows(page, 'Nothing like it')),
    failure(() => assertHides(page, 'from Hermes'))
  ]) {
    assert.ok(message.length < 500, `${message.length} chars`)
  }
  assert.match(failure(() => assertShows(page, /from Python/, 'the source')), /^the source: .*closest: "from " at 50018[^]*\(from Hermes\)/)
})

test('a passing assertion says nothing', () => {
  assertShows(page, /from Hermes/)
  assertShows(page, 'Node.js 26.13.0')
  assertHides(page, 'from Python')
  assertHides(page, /Step \d of/)
})

test('a relative node_modules argument is made absolute (the temp folder links to it); none means look it up', () => {
  assert.equal(modulesFrom(['node', 'page-a.test.mjs', 'tools/npm/node_modules']), path.resolve('tools/npm/node_modules'))
  assert.equal(modulesFrom(['node', 'page-a.test.mjs', '/abs/node_modules']), '/abs/node_modules')
  assert.equal(modulesFrom(['node', 'page-a.test.mjs']), null)
})

test('pageTab looks only in a page\'s own tab bar (.cs-tabs), by its exact label', () => {
  const button = label => ({ textContent: label })
  const document = { querySelectorAll: selector => (selector === '.cs-tabs button' ? [button('One'), button('Two')] : [button('Two')]) }
  assert.equal(tabButton(document, 'Two').textContent, 'Two')
  assert.equal(tabButton(document, 'Tw'), null)
})

test('selectedPageTab (currentPageTab in a scenario) reads the selected tab of a page\'s own tab bar in the given scope, else null', () => {
  const asked = []
  const scope = label => ({ querySelector: selector => { asked.push(selector); return label === null ? null : { textContent: label } } })
  assert.equal(selectedPageTab(scope('Two')), 'Two')
  assert.equal(selectedPageTab(scope(null)), null)
  assert.equal(selectedPageTab(null), null)
  assert.deepEqual([...new Set(asked)], ['.cs-tabs [role="tab"][aria-selected="true"]'])
})
