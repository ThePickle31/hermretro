// Setup keeps confirmed install progress through an unavailable status and resolves a timed-out start by polling.
// Run alone: node tests/page/page-setup-install-status.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, render, click, button, check, shows, hides, answered, status, doctor, installAnswer }) => {
  const idle = installAnswer({ state: 'idle' }).data
  const running = installAnswer({ state: 'running', run_id: 'run-a', fraction: 0.42, current: 'cli' }).data
  const statusError = 'Broker did not answer install_status before its deadline'
  const startError = 'Install start was unconfirmed. Broker did not answer install_start before its deadline'
  const unavailable = { ...idle, ok: false, install: undefined, code: 'UNAVAILABLE', error: statusError }
  const cacheKey = JSON.stringify(['hermretro', 'install'])
  const starts = []
  const cancels = []
  let reply = unavailable
  let startReply = () => ({ ok: false, code: 'UNAVAILABLE', error: startError, start_expires_at: Date.now() - 1 })
  scenario.byMethod['plugin.hermretro.install'] = params => {
    switch (params.action) {
      case 'start_fenced':
        starts.push(params)

        return startReply(params)
      case 'cancel':
        cancels.push(params.run_id)

        return { ok: true }
      default:
        return typeof reply === 'function' ? reply() : reply
    }
  }
  const publish = data => {
    // The SDK stub's useQuery reads its result separately from the cache behind useQueryClient.
    scenario.queryData.set(cacheKey, data)
    scenario.install = { ...answered(data), refetch }

    return scenario.install
  }
  const refetch = async () => publish(await scenario.fns.install())
  const poll = async answer => {
    reply = answer
    await refetch()
    await render()
  }

  scenario.storage = { setup: { onboarded: true }, page: 'setup' }
  scenario.status = answered(status({ plugin: { installed_in: { profile: 'default' } }, restart_needed: true }))
  scenario.doctor = answered(doctor(['cli']))
  scenario['plugin-update'] = answered({
    target: { route: null, profile: 'default' },
    row: { name: 'hermretro', update_available: true }
  })
  await render()
  check('before the first install status, Start and Reload are blocked', () => {
    assert.equal(button('Download and install')?.disabled, true)
    assert.equal(button('Reload')?.disabled, true)
  })
  const toggleChip = () => act(async () => {
    dom.window.document.querySelector('.cs-upd-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  })
  await toggleChip()
  check('before the first install status, Update is blocked', () => {
    assert.equal(button('Update now')?.disabled, true)
  })
  await toggleChip()
  await poll(() => { throw new Error('Gateway request rejected') })
  check('a rejected initial status leaves Start and Reload blocked', () => {
    shows('Gateway request rejected')
    assert.equal(button('Download and install')?.disabled, true)
    assert.equal(button('Reload')?.disabled, true)
  })
  await poll(unavailable)
  check('an unavailable first status shows its error and blocks install, update and reload', () => {
    shows(statusError)
    assert.equal(button('Download and install')?.disabled, true)
    assert.ok(button('Check again'))
    assert.equal(button('Reload')?.disabled, true)
  })
  await toggleChip()
  check('Update now stays disabled while the status is unknown', () => {
    assert.equal(button('Update now')?.disabled, true)
  })
  await toggleChip()

  await poll(idle)
  check('a confirmed idle status clears the first error and allows start and reload', () => {
    hides(statusError)
    assert.equal(button('Download and install')?.disabled, false)
    assert.equal(button('Reload')?.disabled, false)
  })
  let answerOldPoll
  reply = new Promise(resolve => { answerOldPoll = resolve })
  const oldPoll = scenario.fns.install()
  reply = unavailable
  await click('Download and install')
  await render()
  check('a timed-out start polls for its outcome and offers no retry while status is unavailable', () => {
    assert.equal(starts.length, 1)
    shows(startError)
    assert.equal(button('Download and install')?.disabled, true)
    assert.equal(button('Reload')?.disabled, true)
    assert.ok(!button('Try again'))
  })
  answerOldPoll(idle)
  publish(await oldPoll)
  await render()
  check('a pre-start status arriving late cannot resolve the unconfirmed start', () => {
    shows(startError)
    assert.equal(button('Download and install')?.disabled, true)
    assert.equal(button('Reload')?.disabled, true)
  })

  await poll(running)
  check('a fresh status can confirm that the install started despite losing the acknowledgement', () => {
    hides(startError)
    shows('42%')
    assert.ok(button('Cancel'))
  })
  await poll({ ok: true, install: { state: 'running' }, error: statusError })
  check('an invalid success cannot replace confirmed progress', () => {
    shows('42%')
    assert.ok(button('Cancel'))
    assert.equal(button('Reload')?.disabled, true)
  })
  await poll(unavailable)
  check('a later status timeout keeps the active run, progress, cancel and reload guard', () => {
    shows(statusError)
    shows('42%')
    assert.ok(button('Cancel'))
    assert.ok(!button('Download and install'))
    assert.equal(button('Reload')?.disabled, true)
  })
  await click('Cancel')
  check('a malformed Cancel acknowledgement leaves progress and reports failure for the same run', () => {
    assert.deepEqual(cancels, ['run-a'])
    shows('42%')
    shows('The install status could not be confirmed.')
  })

  await poll(installAnswer({ state: 'cancelled', run_id: 'run-a' }).data)
  check('a confirmed terminal status clears the guard and offers another install', () => {
    hides(statusError)
    assert.equal(button('Install again')?.disabled, false)
    assert.equal(button('Reload')?.disabled, false)
  })

  await poll(idle)
  startReply = () => ({ ok: false, code: 'NO_SPACE', error: 'Out of room' })
  await click('Download and install')
  check('an explicit Start denial is shown without treating the install as unconfirmed', () => {
    shows('Out of room')
    assert.equal(button('Reload')?.disabled, false)
  })

  // A mixed-version or malformed reply does not prove the broker's shorter window, even if it claims success.
  startReply = () => ({ ok: true, install: { state: 'done', run_id: 'old-run' } })
  await click('Try again')
  await poll(idle)
  check('a fresh idle during the original start window cannot authorize another mutation', () => {
    shows('The install status could not be confirmed.')
    assert.equal(button('Download and install')?.disabled, true)
    assert.equal(button('Reload')?.disabled, true)
  })
  const originalNow = Date.now
  Date.now = () => starts.at(-1).expires_at + 1
  try {
    await poll(idle)
    check('a confirmed idle after admission expiry allows Start and Reload again', () => {
      assert.equal(button('Download and install')?.disabled, false)
      assert.equal(button('Reload')?.disabled, false)
    })
  } finally {
    Date.now = originalNow
  }

  const mutations = []
  scenario.byMethod['session.active_list'] = () => ({ sessions: [] })
  scenario.byMethod['plugins.manage'] = params => { mutations.push(params.action); return { ok: true } }
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => { mutations.push('studio_profile'); return { ok: true } }
  reply = () => { throw new Error('Fresh status was rejected') }
  await toggleChip()
  await click('Update now')
  check('Update checks live status even if a cached idle enables the button', () => {
    shows('Fresh status was rejected')
    assert.deepEqual(mutations, [])
  })

  reply = { ok: true }
  await click('Reload')
  check('Reload refuses a malformed live status even with a cached idle', () => {
    shows('Reload did not finish: The install status could not be confirmed.')
    assert.deepEqual(mutations, [])
  })
})
