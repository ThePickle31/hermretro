// Exact Build history matching and the outcomes of restoring an older build.
// Run alone: node tests/page/page-build-history-restore.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ buildScenario, scenario, page, click, settle, mount, check, answered, emit, act }) => {
  const game = 'fff666fff666'
  buildScenario({ selected: game })
  scenario.games = answered({ games: [{ id: game, title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio',
    state: 'changed', rom: null, webExport: true, thumb: null, chat: null, error: null, session: { storedId: 'st-frog' } }],
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
    { id: '46', at: 3_002_500, builds: [], buildRefs: ['latest'], reason: 'build' },
    { id: '45', at: 2_499_000, builds: [], buildRefs: ['new-unrepresented'], reason: 'build' },
    { id: '44', at: 2_001_500, builds: [2_001_500], buildRefs: ['old-unrepresented'], reason: 'build' },
    { id: '43', at: 1_001_500, builds: [1_001_500], reason: 'build' },
    { id: '42', at: 42, builds: [1000], buildRefs: ['first'], buildCalls: [{ id: 'first', ref: 'first', timestamp: 1002 }], reason: 'before-restore' }
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
  const [latest, reused, missing, first, ...saved] = await open()
  check('an exact snapshot works outside the old time window and a missing reference never falls back', () => {
    assert.equal([...latest.querySelectorAll('button')].find(button => button.textContent === 'Restore')?.disabled, false)
    assert.equal([...first.querySelectorAll('button')].find(button => button.textContent === 'Restore')?.disabled, false)
    assert.equal([...missing.querySelectorAll('button')].find(button => button.textContent === 'Restore')?.disabled, true)
    assert.equal([...reused.querySelectorAll('button')].find(button => button.textContent === 'Restore')?.disabled, true)
  })
  check('mixed history lists each unmatched legacy snapshot once and keeps exact matches on numbered rows', () => {
    assert.equal(saved.length, 2)
    assert.ok(saved.every(row => row.querySelector('b').textContent === 'Saved snapshot'))
    assert.ok(saved.every(row => !row.querySelector('.cs-b-bn') && !row.textContent.includes('Show')))
  })
  await confirm(first)
  check('preflight failure reports the restore error and sends no rebuild', () => {
    assert.deepEqual(asks, [{ game, id: '42', buildRef: 'first' }])
    assert.deepEqual(prompts, [])
    assert.match(scenario.notices.at(-1).message, /Could not restore build #1.*could not be backed up/)
  })

  restoreResult = { ok: false, code: 'PARTIAL', restored: '42', backup: '50', changed: 1, removed: 0,
    problems: ['assets/frog.png: unexpected file'] }
  await confirm((await open())[3])
  check('an incomplete restore reports the backup and first problem and sends no rebuild', () => {
    assert.equal(asks.length, 2)
    assert.deepEqual(prompts, [])
    assert.match(scenario.notices.at(-1).message, /Restore of build #1 was incomplete.*previous files were saved \(snapshot 50\).*assets\/frog.png/)
  })

  restoreResult = { ok: true, restored: '42', backup: '51', changed: 1, removed: 0 }
  await confirm((await open())[3])
  check('after a complete restore a rejected rebuild is reported separately', () => {
    assert.equal(asks.length, 3)
    assert.equal(prompts.length, 1)
    assert.match(prompts[0].text, /I restored the game to build #1.*Please build it again/)
    assert.match(scenario.notices.at(-1).message, /Build #1 was restored.*rebuild request could not be confirmed/)
    assert.equal(view.node.querySelector('.cs-b-builds'), null)
  })

  rejectSubmit = false
  const notices = scenario.notices.length
  await confirm((await open())[3])
  check('a complete restore submits an accepted rebuild without reporting an error', () => {
    assert.equal(asks.length, 4)
    assert.equal(prompts.length, 2)
    assert.equal(scenario.notices.length, notices)
  })
  await act(async () => emit({ type: 'message.complete', session_id: 'rt-of-st-frog', payload: { text: 'Rebuilt.' } }))
  await settle(25)
  const legacyRow = (await open()).at(-1)
  const date = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' }).format(1_001_500)
  await click('Restore', legacyRow)
  check('the confirmation identifies the selected legacy snapshot by date without sending anything', () => {
    assert.match(legacyRow.textContent, /Saved snapshot.*Restore snapshot.*Cancel/)
    assert.equal(legacyRow.querySelector('small').textContent, date)
    assert.equal(legacyRow.querySelector('button').getAttribute('aria-label'), `Restore saved snapshot from ${date}`)
    assert.equal(asks.length, 4)
    assert.equal(prompts.length, 2)
  })
  await click('Cancel', legacyRow)
  await click('Restore', legacyRow)
  restoreResult = { ok: true, restored: '43', backup: '52', changed: 2, removed: 1 }
  await click('Restore snapshot', legacyRow)
  await settle(25)
  check('confirming the dated snapshot restores that ID and names the same date in the rebuild', () => {
    assert.deepEqual(asks.at(-1), { game, id: '43' })
    assert.equal(asks.length, 5)
    assert.equal(prompts.length, 3)
    assert.ok(prompts.at(-1).text.includes(`saved snapshot from ${date} (snapshot 43)`))
    assert.doesNotMatch(prompts.at(-1).text, /build #/)
    assert.equal(view.node.querySelector('.cs-b-builds'), null)
  })
  await view.close()
})
