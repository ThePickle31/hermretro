// The page's toolchain install when something goes wrong: every state ends in an action (no download list, a
// profile name someone else owns, no space, a failed verification, a profile that never answers, cancel, an
// install interrupted by a restart), and the progress says its stage and time in words a screen reader gets.
// Run alone: node tests/page/page-setup-recovery.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, root, render, shows, hides, heading, click, settle, button, check, answered, status, doctor, manifest, installAnswer }) => {
  const doc = dom.window.document
  const firstRun = (studio = {}) =>
    status({ profile: { name: 'default', is_studio: false, studio: { name: 'hermretro', exists: false, installed: false, ours: false, ...studio } } })
  const onInstallScreen = async ({ statusData = firstRun(), install, doctorData = doctor(['cli']), doctorQuery }) => {
    await act(async () => { root.render(null) })
    scenario.storage = { setup: { onboardStarted: true } }
    scenario.status = answered(statusData); scenario.doctor = doctorQuery ?? answered(doctorData); scenario.install = install
    await render()
  }
  const requests = () => scenario.calls.filter(call => call[0] === 'request').map(call => call[1])

  // 1. No download list: nothing to review, so nothing starts.
  await onInstallScreen({ install: answered({ ok: true, manifest: { items: [], bytes: 0 }, root: '/h/t', install: { state: 'idle' } }) })
  check('without a download list the install cannot start, and the page says why with Check again', () => {
    assert.ok(button('Download and install').disabled)
    shows(/download list could not be read/); assert.ok(button('Check again'))
  })
  scenario.calls.length = 0
  await click('Check again'); await settle()
  check('Check again reads the list again and installs nothing', () => {
    assert.ok(!scenario.paramsByMethod['plugin.hermretro.install'] || scenario.paramsByMethod['plugin.hermretro.install'].action !== 'start')
    assert.ok(!requests().includes('plugin.hermretro.studio_profile'))
  })

  // 2. A profile named hermretro that someone else made: named before any download.
  await onInstallScreen({ statusData: firstRun({ exists: true, conflict: true }), install: installAnswer({ state: 'idle' }) })
  scenario.calls.length = 0
  check('a profile name collision is named and blocks the download', () => {
    shows(/profile named "hermretro" already exists and was not made by hermretro, so nothing was downloaded/)
    assert.ok(button('Download and install').disabled)
  })
  await act(async () => { button('Download and install').click() }); await settle()
  check('pressing the disabled start sends nothing', () => {
    assert.ok(!requests().includes('plugin.hermretro.install') && !requests().includes('plugin.hermretro.studio_profile'))
  })

  // 3. Not enough disk space where the tools go.
  await onInstallScreen({ install: answered({ ok: true, manifest, root: '/h/t', space: { enough: false, free_bytes: 400_000_000, needed_bytes: 2_300_000_000 }, install: { state: 'idle' } }) })
  check('too little free space is said before the download, with the sizes', () => {
    shows(/Not enough free disk space: the game tools need about 2\.3 GB and 400 MB is free/)
    assert.ok(button('Download and install').disabled)
  })

  // 4. Running: stage, elapsed time, an accessible progress bar and Cancel.
  const running = { state: 'running', run_id: 'run-1', started_at: 1, fraction: 0.04, downloaded_bytes: 5_000_000, current: 'cli', elapsed_seconds: 151, quiet_seconds: 200,
    run: { components: { gbdk: { state: 'done', checks: [] }, cli: { state: 'running', checks: [] } } } }
  await onInstallScreen({ install: installAnswer(running) })
  check('progress says the stage and time in words, and a long quiet spell is explained', () => {
    shows(/4% · Installing GB Studio and its packages · 2:31/)
    const bar = doc.querySelector('[role="progressbar"]')
    assert.equal(bar.getAttribute('aria-label'), 'Game tools install')
    assert.equal(bar.getAttribute('aria-valuetext'), '4%, Installing GB Studio and its packages')
    assert.equal(doc.querySelector('.cs-sr[aria-live="polite"]').textContent, 'Installing GB Studio and its packages')
    shows(/Still working: nothing new on disk for 3:20/)
    assert.ok(button('Cancel'))
  })
  check('the whole onboarding screen is no longer one live region that reads every tick', () => {
    assert.ok(!doc.querySelector('.cs-onb[aria-live]'))
  })
  scenario.byMethod['plugin.hermretro.install'] = () => ({ ok: true, manifest, install: { ...running, cancelling: true } })
  scenario.calls.length = 0
  await click('Cancel'); await settle()
  check('Cancel asks the backend to cancel (it never kills anything itself)', () => {
    assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.install'], { action: 'cancel', run_id: 'run-1' })
  })
  delete scenario.byMethod['plugin.hermretro.install']
  scenario.install = installAnswer({ ...running, cancelling: true }); await render()
  check('while it winds down the page says it is stopping safely, with no second Cancel', () => {
    shows(/Stopping safely/); assert.ok(!button('Cancel'))
  })
  scenario.install = installAnswer({ state: 'cancelled', started_at: 1, finished_at: 9, code: 'CANCELLED', error: 'The install was cancelled.', hint: 'Finished parts are kept. Install again whenever you like.' })
  await render()
  check('a cancelled install keeps its parts and offers Install again', () => {
    shows(/The install was cancelled/); shows(/Finished parts are kept/); assert.ok(button('Install again'))
  })

  // 5. A reload after the broker ended mid-install: the journal's answer.
  await onInstallScreen({ install: installAnswer({ state: 'interrupted', started_at: 1, code: 'INTERRUPTED', error: "The install stopped when hermretro's background process ended (for example when Hermes quit).", hint: 'Finished parts are kept. Install again to continue.' }) })
  check('an interrupted install shows what happened and how to go on, not a fresh review', () => {
    assert.equal(heading(), "One part didn't finish")
    shows(/background process ended/); shows(/Install again to continue/); assert.ok(button('Try again'))
  })
  await onInstallScreen({ install: installAnswer({ state: 'failed', started_at: 1, code: 'NETWORK', error: 'cli: ENOTFOUND registry.npmjs.org', hint: 'A download source could not be reached. Check the internet connection' }) })
  check('a network failure is named with its next step', () => { shows(/A download source could not be reached/) })

  // 6. The install finished but the tools still do not verify.
  await onInstallScreen({ install: installAnswer({ state: 'done', started_at: 1, finished_at: 2, fraction: 1 }), doctorData: doctor(['cli']) })
  check('a finished install whose check still fails says so: Check again and Retry install, never an endless check', () => {
    hides('Checking the installed tools'); shows(/The install finished, but the tools check still reports missing: cli/)
    assert.ok(button('Check again') && button('Retry install'))
  })
  scenario.doctor = { isError: true, isFetching: false, error: new Error('toolchain_doctor timed out') }
  await render()
  check('a check that itself fails offers Check again, not a reinstall', () => {
    shows(/the tools check failed: toolchain_doctor timed out/); assert.ok(button('Check again')); assert.ok(!button('Retry install'))
  })

  // 7. Tools verified, profile made, but its route never answers: Repair in onboarding too.
  await onInstallScreen({ statusData: firstRun({ exists: true, installed: true, ours: true }), install: installAnswer({ state: 'done', started_at: 1, finished_at: 2, fraction: 1 }), doctorData: doctor([]) })
  check('waiting for the profile offers Repair the profile', () => {
    shows(/Waiting for Hermes to start the hermretro profile/); assert.ok(button('Repair the profile'))
  })
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => ({ ok: true, profile: 'hermretro' })
  scenario.calls.length = 0
  await click('Repair the profile'); await settle()
  check('Repair finishes the existing profile again, without creating a second one', () => {
    assert.ok(requests().includes('plugin.hermretro.studio_profile'))
    assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.studio_profile'], { create: false })
  })
  delete scenario.byMethod['plugin.hermretro.studio_profile']

  // 8. A reload near the end: the first install status already says done, and the tools check on screen was
  //    answered just before the finish (react-query's dataUpdatedAt, in ms; finished_at in s).
  const finishedAt = Date.now() / 1000
  let doctorChecks = 0
  const doctorAt = (at, missing = ['cli']) => ({ ...answered(doctor(missing)), dataUpdatedAt: at, errorUpdatedAt: 0, refetch: async () => { doctorChecks += 1 } })
  await onInstallScreen({ install: installAnswer({ state: 'done', run_id: 'run-a', started_at: finishedAt - 300, finished_at: finishedAt, fraction: 1 }), doctorQuery: doctorAt(finishedAt * 1000 - 4_000) })
  await settle()
  check('a done install first seen after a check from before its finish checks the tools once more', () => {
    assert.equal(doctorChecks, 1)
    shows(/Checking the installed tools/)
  })
  await render(); await render(); await settle()
  check('and only once for that run, never a repeated poll', () => { assert.equal(doctorChecks, 1) })
  scenario.doctor = doctorAt(finishedAt * 1000 + 2_000); await render(); await settle()
  check('the check after the finish decides it: missing tools are said, not an endless check', () => {
    hides('Checking the installed tools'); shows(/The install finished, but the tools check still reports missing: cli/)
    assert.equal(doctorChecks, 1)
  })
  await onInstallScreen({ install: installAnswer({ state: 'done', run_id: 'run-b', started_at: finishedAt - 300, finished_at: finishedAt, fraction: 1 }), doctorQuery: doctorAt(finishedAt * 1000 + 1_000) })
  await settle()
  check('a check already answered after the finish is not repeated', () => { assert.equal(doctorChecks, 1) })

  // 9. Cancel names the run on screen, and a cancel that fails is said while the install keeps running.
  await onInstallScreen({ install: installAnswer({ ...running, run_id: 'run-c' }) })
  scenario.byMethod['plugin.hermretro.install'] = () => ({ ok: false, code: 'CANCEL_UNSUPPORTED', manifest, error: 'This install is run by an older hermretro background process that cannot cancel it, so it is still running.' })
  await click('Cancel'); await settle()
  check('Cancel sends the run it means', () => {
    assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.install'], { action: 'cancel', run_id: 'run-c' })
  })
  delete scenario.byMethod['plugin.hermretro.install']
  await render()
  check('a cancel the backend could not do is shown while the install runs', () => {
    shows(/older hermretro background process that cannot cancel it/); shows(/Installing GB Studio/)
  })

  // 10. Finished parts make a smaller install likely but not certain: a warning, not a promise.
  await onInstallScreen({ install: answered({ ok: true, manifest, root: '/h/t', space: { enough: true, free_bytes: 900_000_000, needed_bytes: 500_000_000, estimate: 'reuse', warning: 'Finished parts are reused, so this may fit, but a full install needs about 2.3 GB and less is free.' }, install: { state: 'idle' } }) })
  check('an uncertain fit is a warning and the install can still start', () => {
    shows(/this may fit, but a full install needs about 2\.3 GB/); assert.ok(!button('Download and install').disabled)
  })
  await act(async () => { root.unmount() })
})
