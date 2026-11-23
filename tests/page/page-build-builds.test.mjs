// The Builds menu rejects time-only snapshots, even if exactly one occurrence falls inside the turn.
// Run alone: node tests/page/page-build-builds.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ buildScenario, scenario, page, click, settle, key, mount, check, answered }) => {
  buildScenario({ selected: 'fff666fff666' })
  scenario.games = answered({ games: [{ id: 'fff666fff666', title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio',
    state: 'ready', rom: null, webExport: true, thumb: null, chat: null, error: null, session: { storedId: 'st-frog' } }],
  device: { hardwareEnabled: false, skipped: true } })
  const callOf = (id, name) => ({ id, function: { name, arguments: '{}' } })
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, running: false, messages: params.omit_messages ? [] : [
    { role: 'user', content: 'make the frog jump', timestamp: 1000 },
    { role: 'assistant', content: '', timestamp: 1001, tool_calls: [callOf('b1', 'chromatic_rom_build')] },
    { role: 'tool', tool_call_id: 'b1', content: JSON.stringify({ ok: true }), timestamp: 1020 },
    { role: 'assistant', content: 'It jumps.', timestamp: 1030 },
    { role: 'user', content: 'make it jump higher', timestamp: 2000 },
    { role: 'assistant', content: '', timestamp: 2001, tool_calls: [callOf('b2', 'chromatic_rom_build')] },
    { role: 'tool', tool_call_id: 'b2', content: JSON.stringify({ ok: true }), timestamp: 2020 },
    { role: 'assistant', content: 'Higher now.', timestamp: 2030 }] })
  const asked = []
  let snapshots = []
  scenario.byMethod['plugin.hermretro.builds'] = params => { asked.push(params); return { ok: true, builds: snapshots } }
  const view = await mount(page)
  await settle(100)
  const openMenu = async () => {
    await click('Builds', view.node.querySelector('.cs-b-head'))
    await settle(30)
    const rows = [...view.node.querySelectorAll('.cs-b-brow')]
    const restore = rows[1] && [...rows[1].querySelectorAll('button')].find(node => node.textContent === 'Restore')
    await key('keydown', 'Escape')
    return { rows: rows.map(node => node.textContent), restore }
  }

  // The sole occurrence could be from a concurrent chat that built the same game.
  snapshots = [{ id: 'snap-1', at: 1_010_000, builds: [1_010_000], reason: 'build' }]
  const kept = await openMenu()
  check('the Builds menu asks plugin.hermretro.builds for this game and lists the builds newest first', () => {
    assert.deepEqual(asked.at(-1), { game: 'fff666fff666', stored: 'st-frog' })
    assert.equal(kept.rows.length, 2); assert.match(kept.rows[0], /#2make it jump higher/); assert.match(kept.rows[1], /#1make the frog jump/)
  })
  check('a lone time-only occurrence inside the turn cannot identify build #1', () => {
    assert.ok(kept.restore, 'build #1 has a Restore button'); assert.equal(kept.restore.disabled, true)
  })
  snapshots = [{ id: 'snap-1', at: 1010, builds: [1010], reason: 'build' }]
  const lost = await openMenu()
  check('a snapshot from outside the build\u2019s turn matches nothing, so Restore stays disabled', () => {
    assert.ok(lost.restore); assert.equal(lost.restore.disabled, true)
  })
  snapshots = [{ id: 'backup', at: 1_010_000, builds: [], reason: 'before-restore' }]
  const backup = await openMenu()
  check('the time a restore backup was made does not match a build', () => {
    assert.equal(backup.restore.disabled, true)
  })
  snapshots = [
    { id: 'snap-1', at: 1_010_000, builds: [1_010_000], reason: 'build' },
    { id: 'snap-2', at: 1_012_000, builds: [1_012_000], reason: 'build' }
  ]
  const ambiguous = await openMenu()
  check('two historical build occurrences in the same turn disable Restore', () => {
    assert.equal(ambiguous.restore.disabled, true)
  })
  snapshots = [{ id: 'snap-1', at: 1_030_001, builds: [1_030_001], reason: 'build' }]
  const adjacent = await openMenu()
  check('an occurrence just after the turn is outside the legacy window', () => {
    assert.equal(adjacent.restore.disabled, true)
  })
  await view.close()

  // While hermretro updates, Restore (which restores files and sends a build request) and the chat box start nothing.
  snapshots = [{ id: 'snap-1', buildRefs: ['first'], buildCalls: [{ id: 'b1', ref: 'first' }], reason: 'build' }]
  scenario.status = answered({ ...scenario.status.data, plugin: { version: '1.2.3', installed_in: { profile: 'default', linked: false } } })
  scenario['plugin-update'] = answered({ target: { route: null, profile: 'default' }, row: { name: 'hermretro', update_available: true, update_target: 'abc' } })
  scenario['update-busy'] = answered([])
  scenario.byMethod['session.active_list'] = () => ({ sessions: [] })
  let finish
  scenario.byMethod['plugins.manage'] = params => (params.action === 'update' ? new Promise(resolve => { finish = resolve }) : { ok: true })
  const updating = await mount(page)
  await settle(100)
  await click('Update ready', updating.node); await click('Update now', updating.node); await settle(40)
  await click('Builds', updating.node.querySelector('.cs-b-head')); await settle(30)
  check('while updating, the Builds menu cannot restore a build', () => {
    const buttons = [...updating.node.querySelectorAll('.cs-b-brow button')].filter(node => node.textContent === 'Restore')
    assert.ok(buttons.length, 'Restore buttons are shown'); assert.ok(buttons.every(node => node.disabled), 'every Restore is disabled')
  })
  check('while updating, the chat box sends nothing', () => {
    assert.equal(updating.node.querySelector('.cs-b-chat textarea')?.disabled, true)
  })
  await key('keydown', 'Escape')
  await settle(10)
  finish({ ok: true, unchanged: true }); await settle(40)
  await updating.close()
})
