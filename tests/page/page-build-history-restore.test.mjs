// Exact Build history matching and the outcomes of restoring an older build.
// Run alone: node tests/page/page-build-history-restore.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ buildScenario, scenario, page, click, settle, mount, check, answered }) => {
  const game = 'fff666fff666'
  buildScenario({ selected: game })
  scenario.games = answered({ games: [{ id: game, title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio',
    state: 'ready', rom: null, webExport: true, thumb: null, chat: null, error: null, session: { storedId: 'st-frog' } }],
  device: { hardwareEnabled: false, skipped: true } })
  const turn = (id, at, title) => [
    { role: 'user', content: title, timestamp: at },
    { role: 'assistant', content: '', timestamp: at + 1,
      tool_calls: [{ id, function: { name: 'chromatic_rom_build', arguments: '{}' } }] },
    { role: 'tool', tool_call_id: id, content: JSON.stringify({ structuredContent: { success: true }, buildRef: id }), timestamp: at + 2 },
    { role: 'assistant', content: 'Built.', timestamp: at + 3 }
  ]
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, running: false, messages: params.omit_messages ? [] : [
    { role: 'user', text: 'make the frog jump', timestamp: 1000 },
    { role: 'tool', name: 'tool_call', tool_call_id: 'first', timestamp: 1002,
      args: { calls: [{ name: 'chromatic_rom_build', arguments: {} }] } },
    { role: 'assistant', text: 'Done.', timestamp: 1003 },
    ...turn('missing', 2000, 'make it jump higher'),
    { role: 'user', text: 'build again', timestamp: 2500 },
    { role: 'tool', name: 'tool_call', tool_call_id: 'first', timestamp: 2502,
      args: { calls: [{ name: 'chromatic_rom_build', arguments: {} }] } },
    ...turn('latest', 3000, 'make it jump even higher')
  ] })
  scenario.byMethod['plugin.hermretro.builds'] = { ok: true, builds: [
    { id: '42', at: 42, builds: [], buildRefs: ['first'], buildCalls: [{ id: 'first', ref: 'first', timestamp: 1002 }], reason: 'before-restore' },
    { id: '43', at: 43, builds: [1_001_500, 2_001_500], reason: 'build' }
  ] }
  const asks = []
  let restoreResult = { ok: false, code: 'BACKUP_FAILED', error: 'The project could not be backed up.' }
  scenario.byMethod['plugin.hermretro.build_restore'] = params => {
    asks.push(params)
    return restoreResult
  }
  const prompts = []
  let rejectSubmit = true
  scenario.byMethod['prompt.submit'] = params => {
    prompts.push(params)
    if (rejectSubmit) throw new Error('Rebuild admission failed')
    return { status: 'queued' }
  }

  const view = await mount(page)
  await settle(100)
  const open = async () => {
    if (!view.node.querySelector('.cs-b-builds')) {
      await click('Builds', view.node.querySelector('.cs-b-head'))
      await settle(25)
    }
    return [...view.node.querySelectorAll('.cs-b-brow')]
  }
  const confirm = async row => {
    if (!row.textContent.includes('Restore #1')) await click('Restore', row)
    await click('Restore #1', row)
    await settle(25)
  }
  const [, reused, missing, first] = await open()
  check('an exact snapshot works outside the old time window and a missing reference never falls back', () => {
    assert.equal([...first.querySelectorAll('button')].find(button => button.textContent === 'Restore')?.disabled, false)
    assert.equal([...missing.querySelectorAll('button')].find(button => button.textContent === 'Restore')?.disabled, true)
    assert.equal([...reused.querySelectorAll('button')].find(button => button.textContent === 'Restore')?.disabled, true)
  })
  await confirm(first)
  check('preflight failure reports the restore error and sends no rebuild', () => {
    assert.deepEqual(asks, [{ game, id: '42', buildRef: 'first' }])
    assert.deepEqual(prompts, [])
    assert.match(scenario.notices.at(-1).message, /Could not restore build #1.*could not be backed up/)
  })

  restoreResult = { ok: false, code: 'PARTIAL', restored: '42', backup: '50', changed: 1, removed: 0,
    problems: ['assets/frog.png: a link is in the way'] }
  await confirm((await open()).at(-1))
  check('an incomplete restore reports the backup and first problem and sends no rebuild', () => {
    assert.equal(asks.length, 2)
    assert.deepEqual(prompts, [])
    assert.match(scenario.notices.at(-1).message, /Restore of build #1 was incomplete.*previous files were saved.*assets\/frog.png/)
  })

  restoreResult = { ok: true, restored: '42', backup: '51', changed: 1, removed: 0 }
  await confirm((await open()).at(-1))
  check('after a complete restore a rejected rebuild is reported separately', () => {
    assert.equal(asks.length, 3)
    assert.equal(prompts.length, 1)
    assert.match(prompts[0].text, /I restored the game to build #1.*Please build it again/)
    assert.match(scenario.notices.at(-1).message, /Build #1 was restored.*rebuild request could not be confirmed/)
    assert.equal(view.node.querySelector('.cs-b-builds'), null)
  })

  rejectSubmit = false
  const notices = scenario.notices.length
  await confirm((await open()).at(-1))
  check('a complete restore submits an accepted rebuild without reporting an error', () => {
    assert.equal(asks.length, 4)
    assert.equal(prompts.length, 2)
    assert.equal(scenario.notices.length, notices)
  })
  await view.close()
})
