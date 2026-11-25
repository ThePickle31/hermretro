// Setup keeps confirmed install progress through an unavailable status and resolves a timed-out start by polling.
// Run alone: node tests/page/page-setup-install-status.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, root, scenario, render, click, button, check, shows, hides, answered, status, doctor, installAnswer }) => {
  const idle = installAnswer({ state: 'idle' }).data
  const running = installAnswer({ state: 'running', run_id: 'run-a', fraction: 0.42, current: 'cli' }).data
  const statusError = 'Broker did not answer install_status before its deadline'
  const startError = 'Install start was unconfirmed. Broker did not answer install_start before its deadline'
  const unavailable = { ...idle, ok: false, install: undefined, code: 'UNAVAILABLE', error: statusError }
  const cacheKey = JSON.stringify(['hermretro', 'install'])
  const starts = []
  const cancels = []
  let reply = unavailable
  let deadline = 100
  let startReply = () => ({ ok: false, code: 'UNAVAILABLE', error: startError })
  scenario.byMethod['plugin.hermretro.install'] = params => {
    switch (params.action) {
      case 'prepare_start':
        deadline += 60

        return { ok: true, admission: { boot_id: 'test-boot', deadline } }
      case 'start_admitted':
        assert.deepEqual(scenario.storage.installStartPending?.admission, params.admission, 'persist before submitting')
        starts.push(params)

        return startReply(params)
      case 'cancel':
        cancels.push(params.run_id)

        return { ok: true }
      default:
        return typeof reply === 'function' ? reply(params) : reply
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
  scenario.status = answered(status({ plugin: { installed_in: { profile: 'default' } } }))
  scenario.doctor = answered(doctor(['cli']))
  scenario['plugin-update'] = answered({
    target: { route: null, profile: 'default' },
    row: { name: 'hermretro', update_available: true }
  })
  await render()
  check('before the first install status, Start is blocked', () => {
    assert.equal(button('Download and install')?.disabled, true)
  })
  // The chip opens the update dialog; its close button puts it away again.
  const scrim = () => dom.window.document.querySelector('.cs-upd-scrim')
  const update = label => [...(scrim()?.querySelectorAll('button') ?? [])].find(node => node.textContent === label)
  const toggleChip = () => act(async () => {
    const target = scrim() ? scrim().querySelector('[aria-label="Close"]') : dom.window.document.querySelector('.cs-upd-chip')
    target.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  })
  await toggleChip()
  check('before the first install status, Update is blocked', () => {
    assert.equal(update('Update')?.disabled, true)
  })
  await toggleChip()
  await poll(() => { throw new Error('Gateway request rejected') })
  check('a rejected initial status leaves Start blocked', () => {
    shows('Gateway request rejected')
    assert.equal(button('Download and install')?.disabled, true)
  })
  await poll(unavailable)
  check('an unavailable first status shows its error and blocks the install', () => {
    shows(statusError)
    assert.equal(button('Download and install')?.disabled, true)
    assert.ok(button('Check again'))
  })
  await toggleChip()
  check('Update stays disabled while the status is unknown', () => {
    assert.equal(update('Update')?.disabled, true)
  })
  await toggleChip()

  await poll(idle)
  check('a confirmed idle status clears the first error and allows Start', () => {
    hides(statusError)
    assert.equal(button('Download and install')?.disabled, false)
  })
  scenario.storage.installStartPending = { admission: 86460 }
  await poll({ ...unavailable, expired_admission: 86460 })
  check('an unavailable status cannot clear a stored admission from before the upgrade', () => {
    assert.equal(scenario.storage.installStartPending?.admission, 86460)
    assert.equal(button('Download and install')?.disabled, true)
  })
  await poll(params => ({ ...idle, expired_admission: params.admission }))
  check('a fresh confirmed status releases a stale numeric admission', () => {
    assert.equal(scenario.storage.installStartPending, null)
    assert.equal(button('Download and install')?.disabled, false)
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
    assert.ok(!button('Try again'))
  })
  answerOldPoll(idle)
  publish(await oldPoll)
  await render()
  check('a pre-start status arriving late cannot resolve the unconfirmed start', () => {
    shows(startError)
    assert.equal(button('Download and install')?.disabled, true)
  })

  await poll(params => ({ ...running, expired_admission: params.admission }))
  check('a fresh status can confirm that the install started despite losing the acknowledgement', () => {
    hides(startError)
    shows('42%')
    assert.ok(button('Cancel'))
  })
  await poll({ ok: true, install: { state: 'running' }, error: statusError })
  check('an invalid success cannot replace confirmed progress', () => {
    shows('42%')
    assert.ok(button('Cancel'))
  })
  await poll(unavailable)
  check('a later status timeout keeps the active run, progress, cancel and update guard', () => {
    shows(statusError)
    shows('42%')
    assert.ok(button('Cancel'))
    assert.ok(!button('Download and install'))
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
  })

  await poll(idle)
  startReply = params => ({ ok: false, admission: params.admission, code: 'NO_SPACE', error: 'Out of room' })
  await click('Download and install')
  check('an explicit Start denial is shown without treating the install as unconfirmed', () => {
    shows('Out of room')
  })

  // Remount before the pending Start replies. Desktop wall time can move either way during reconciliation.
  let completeStart
  startReply = () => new Promise(resolve => { completeStart = resolve })
  await click('Try again')
  await act(async () => { root.render(null) })
  await render()
  const originalNow = Date.now
  try {
    Date.now = () => originalNow() + 86_400_000
    await poll(idle)
    check('the remounted page blocks Start during the outstanding admission even with a fast Desktop clock', () => {
      shows('The install status could not be confirmed.')
      assert.equal(button('Download and install')?.disabled, true)
    })
    await toggleChip()
    check('the persisted attempt also blocks Update while Start is in flight', () => {
      assert.equal(update('Update')?.disabled, true)
    })
    await toggleChip()
    await act(async () => { completeStart({ ok: true, install: { state: 'done', run_id: 'old-run' } }) })
    await poll({ ...idle, expired_admission: { ...starts.at(-1).admission, boot_id: 'other-boot' } })
    check('a malformed Start reply or an older admission cannot unblock the current attempt', () => {
      assert.equal(button('Download and install')?.disabled, true)
    })
    Date.now = () => originalNow() - 86_400_000
    await poll(params => ({ ...idle, expired_admission: { ...params.admission } }))
    check('gateway-confirmed expiry allows Start even with a slow Desktop clock', () => {
      assert.equal(button('Download and install')?.disabled, false)
      assert.equal(scenario.storage.installStartPending, null)
    })
  } finally {
    Date.now = originalNow
  }

  await click('Download and install')
  await poll(params => ({ ...idle, expired_admission: params.admission }))
  check('expiry also releases the original mount while its Start request is still unanswered', () => {
    assert.equal(button('Download and install')?.disabled, false)
  })
  await act(async () => { completeStart({ ...running, admission: starts.at(-1).admission }) })
  check('a late acknowledgement cannot replace the status that reconciled its admission', () => {
    assert.equal(scenario.queryData.get(cacheKey).install.state, 'idle')
  })

  const mutations = []
  scenario.byMethod['session.active_list'] = () => ({ sessions: [] })
  scenario.byMethod['plugins.manage'] = params => { mutations.push(params.action); return { ok: true } }
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => { mutations.push('studio_profile'); return { ok: true } }

  const retained = { ...idle, install: { state: 'failed', elsewhere: false, worker_left: true } }
  await poll(retained)
  await toggleChip()
  check('a failed install with a live worker blocks Start, and Update waits for it', () => {
    assert.equal(button('Try again')?.disabled, true)
    assert.match(scrim().textContent, /The game tools are being installed\. You can update when that finishes/)
  })
  await toggleChip()

  const oldRunning = { ...idle, install: { state: 'running', fraction: 0.42, current: 'cli' }, legacy_progress: true }
  await poll(oldRunning)
  await toggleChip()
  check('a retained unnamed install shows progress and blocks mutations without offering Cancel', () => {
    shows('42%')
    assert.ok(!button('Cancel'))
    assert.ok(!button('Download and install'))
    assert.match(scrim().textContent, /The game tools are being installed\. You can update when that finishes/)
  })
  await toggleChip()

  await poll({ ...idle, install: { state: 'idle', elsewhere: true } })
  await toggleChip()
  check('an install elsewhere makes Update wait in the UI', () => {
    assert.match(scrim().textContent, /The game tools are being installed\. You can update when that finishes/)
  })
  await toggleChip()
  await poll(idle)
  reply = retained
  await toggleChip()
  await click('Update', scrim())
  check('Update checks for a retained installer after the cached status was idle', () => {
    shows('The game tools are being installed.')
    assert.deepEqual(mutations, [])
  })
  reply = () => { throw new Error('Fresh status was rejected') }
  await click('Try again', scrim())
  check('Update checks live status even if a cached idle enables the button', () => {
    shows('Fresh status was rejected')
    assert.deepEqual(mutations, [])
  })

  const reads = []
  const legacy = { ...unavailable, code: 'BROKER_LEGACY', error: 'The old broker could not read its fingerprint.' }
  let legacyBusy = true
  reply = params => {
    reads.push(params)

    return !params.retire_legacy ? legacy : legacyBusy ? { ok: false, code: 'BUSY', error: 'The old broker is running games.' } : idle
  }
  await act(async () => { root.render(null) })
  await poll(reply)
  await toggleChip()
  check('a passive legacy poll offers an action without requesting retirement', () => {
    assert.deepEqual(reads, [{ action: 'status' }])
    assert.equal(update('Update')?.disabled, false)
    assert.equal(button('Download and install')?.disabled, false)
  })
  await click('Update', scrim())
  check('explicit Update checks the legacy broker and honors its busy refusal', () => {
    assert.deepEqual(reads.at(-1), { action: 'status', retire_legacy: true })
    shows('The old broker is running games.')
    assert.deepEqual(mutations, [])
  })
  legacyBusy = false
  await click('Try again', scrim())
  check('Update proceeds after the guarded legacy retirement confirms idle', () => {
    assert.deepEqual(mutations, ['update', 'studio_profile', 'toggle', 'toggle'])
  })
})
