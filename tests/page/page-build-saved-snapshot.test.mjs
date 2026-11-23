// Saved snapshots and backups are available even if the old conversation is no longer bound.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ buildScenario, scenario, page, click, settle, mount, check, answered }) => {
  const game = 'fff666fff666'
  const savedAt = Date.UTC(2025, 4, 4, 12, 32, 10)
  const snapshot = String(savedAt)
  const backupAt = savedAt + 1000
  const backup = String(backupAt)
  buildScenario({ selected: game })
  scenario.games = answered({ games: [{ id: game, title: 'Frog Post', projectRoot: '/home/u/games/FrogPost',
    kind: 'gbstudio', state: 'changed', rom: null, webExport: false, thumb: null, session: null }] })
  const calls = []
  scenario.byMethod['plugin.hermretro.builds'] = params => {
    calls.push(['builds', params])
    return { ok: true, builds: [
      { id: backup, at: backupAt, reason: 'before-restore', builds: [] },
      { id: snapshot, at: savedAt, reason: 'build', builds: [savedAt + 500] }
    ] }
  }
  scenario.byMethod['plugin.hermretro.build_restore'] = params => {
    calls.push(['restore', params])
    return { ok: true, restored: snapshot, backup: '52', changed: 2, removed: 1 }
  }
  scenario.byMethod['session.create'] = params => {
    calls.push(['create', params])
    return { session_id: 'rt-frog', stored_session_id: 'st-frog', info: { model: params.model, provider: params.provider }, messages: [] }
  }
  scenario.byMethod['plugin.hermretro.build'] = params => {
    calls.push(['bind', params])
    return { ok: true }
  }
  scenario.byMethod['prompt.submit'] = params => {
    calls.push(['submit', params])
    return { status: 'queued' }
  }

  const view = await mount(page)
  await settle(100)
  await click('Builds', view.node.querySelector('.cs-b-head'))
  await settle(25)
  const [backupRow, row] = view.node.querySelectorAll('.cs-b-brow')
  const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' })
  const date = dateFormat.format(savedAt)
  check('an unbound game still lists its saved legacy build by the snapshot date', () => {
    assert.deepEqual(calls, [['builds', { game, stored: null }]])
    assert.equal(row.querySelector('small').textContent, date)
    assert.equal(row.querySelector('button').disabled, false)
  })
  check('an unbound game lists its before-restore backup by date and ID', () => {
    assert.equal(backupRow.querySelector('small').textContent, `${dateFormat.format(backupAt)} · ${backup}`)
    assert.equal(backupRow.querySelector('button').disabled, false)
  })

  await click('Restore', row)
  check('selecting the snapshot alone does not change project files or start a chat', () => {
    assert.deepEqual(calls.map(([step]) => step), ['builds'])
  })

  await click('Restore snapshot', row)
  await settle(25)
  check('a successful restore creates and binds a conversation for the rebuild', () => {
    const operations = calls.filter(([step]) => step !== 'builds')
    assert.deepEqual(operations.map(([step]) => step), ['restore', 'create', 'bind', 'submit'])
    assert.deepEqual(operations[0][1], { game, id: snapshot })
    assert.deepEqual(operations[2][1], { action: 'bind', game, stored: 'st-frog' })
    assert.equal(operations[3][1].session_id, 'rt-frog')
    assert.ok(operations[3][1].text.includes(`saved snapshot from ${date} (snapshot ${snapshot})`))
  })
  await view.close()
})
