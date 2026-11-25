// Replace deleted sessions and recover turns interrupted by a restart, including during an update.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'
import { frogPost } from './frog-post-fixture.mjs'

await runScenario(async ({ act, answered, buildScenario, button, check, click, emit, installAnswer, mount, page, scenario, settle, typeInto }) => {
  const frog = frogPost()
  buildScenario({ selected: frog.id })
  const showConversation = storedId => {
    scenario.games = answered({ games: [{ ...frog, session: { storedId } }], device: { hardwareEnabled: false, skipped: true } })
  }
  scenario.install = installAnswer({ state: 'idle' })
  const submits = []
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }
  const buildCalls = []
  scenario.byMethod['plugin.hermretro.build'] = params => { buildCalls.push(params); return { ok: true } }
  const plainResume = params => ({ session_id: `rt-of-${params.session_id}`, messages: [
    { role: 'user', content: 'make the frog jump' }, { role: 'assistant', content: [{ type: 'text', text: 'Added a jump.' }],
      tool_calls: [{ id: 't0', function: { name: 'chromatic_rom_build' } }] },
    { role: 'tool', tool_call_id: 't0', content: '{}' }, { role: 'user', text: 'secret', display_kind: 'hidden' }] })

  // Replace a conversation removed from Hermes when the next message is sent.
  showConversation('st-gone')
  const replacement = { session_id: 'rt-new-1', stored_session_id: 'st-new-1', messages: [] }
  scenario.byMethod['session.create'] = () => replacement
  scenario.byMethod['session.resume'] = params => { if (params.session_id === 'st-gone') throw Object.assign(new Error('session not found'), { code: 4007 }); return plainResume(params) }
  const removed = await mount(page)
  await settle()
  check('a game whose conversation was removed says so and offers a new one', () => {
    assert.match(removed.node.textContent, /conversation was removed from Hermes/)
    assert.ok(button('Start a new conversation'))
  })
  await click('Start a new conversation', removed.node)
  await typeInto(removed.node.querySelector('textarea[aria-label="Message Hermes"]'), 'start again')
  await click('Send', removed.node.querySelector('.cs-b-comp'))
  await settle()
  check('the next message makes a new conversation and replaces the removed one', () => {
    assert.deepEqual(buildCalls.at(-1), { action: 'bind', game: 'fff666fff666', stored: replacement.stored_session_id, replace: 'st-gone' })
    assert.equal(submits.at(-1).text, 'start again')
  })
  await removed.close()
  // A turn Hermes lost when it restarted pauses the conversation: the page says so, and Continue drops it.
  showConversation('st-lost')
  let lostRows = [{ admission_id: 'adm-lost', status: 'unknown', text: 'make a bird', execution_generation: 1 }, { admission_id: 'adm-q', status: 'queued', text: 'continue' }]
  let lostRunning = false
  const resolved = []
  scenario.byMethod['session.resume'] = params => ({ ...plainResume(params), running: lostRunning, pending: lostRows })
  scenario.byMethod['prompt.resolve_unknown'] = params => { resolved.push(params); lostRows = lostRows.filter(row => row.admission_id !== params.admission_id); return { status: 'terminal', outcome: 'interrupted' } }
  const interrupted = await mount(page)
  await settle()
  check('a conversation paused on a lost turn says so, with the message that waits behind it', () => {
    assert.match(interrupted.node.querySelector('.cs-b-card.warn')?.textContent ?? '', /HermRetro stopped partway through.*Continue to send your waiting message/)
    assert.match(interrupted.node.querySelector('.cs-b-user.queued')?.textContent ?? '', /Waiting · sent when you continue.*continue/)
  })
  const submitsBefore = submits.length
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { status: 'queued' } }
  await typeInto(interrupted.node.querySelector('textarea[aria-label="Message Hermes"]'), 'and add clouds')
  await click('Send', interrupted.node.querySelector('.cs-b-comp'))
  await settle()
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }
  check('a message sent while paused waits too, and the page does not claim to be working', () => {
    assert.deepEqual([...interrupted.node.querySelectorAll('.cs-b-user.queued')].map(node => node.lastChild.textContent), ['continue', 'and add clouds'])
    assert.ok(!interrupted.node.querySelector('.cs-b-comp button[aria-label="Stop"]'))
  })
  // While hermretro updates, Continue (which would release the waiting messages) starts nothing.
  scenario.status = answered({ ...scenario.status.data, plugin: { version: '1.2.3', installed_in: { profile: 'default', linked: false } } })
  scenario['plugin-update'] = answered({ target: { route: null, profile: 'default' }, row: { name: 'hermretro', update_available: true, update_target: 'abc' } })
  scenario['update-busy'] = answered([])
  scenario.byMethod['plugin.hermretro.install'] = () => scenario.install.data
  scenario.byMethod['session.active_list'] = () => ({ sessions: [] })
  let finishUpdate
  scenario.byMethod['plugins.manage'] = params => (params.action === 'update' ? new Promise(resolve => { finishUpdate = resolve }) : { ok: true })
  await interrupted.rerender()
  await click('Update ready', interrupted.node); await click('Update', interrupted.node.ownerDocument.querySelector('.cs-upd-dlg')); await settle()
  const lostContinue = () => [...interrupted.node.querySelector('.cs-b-card.warn').querySelectorAll('button')].find(node => node.textContent === 'Continue')
  const submitsUpdating = submits.length
  check('while hermretro updates, Continue is disabled', () => { assert.equal(lostContinue().disabled, true) })
  lostContinue().click(); await settle()
  check('and pressing it releases nothing: no lost turn dropped, no message sent', () => {
    assert.deepEqual(resolved, []); assert.equal(submits.length, submitsUpdating)
  })
  await act(async () => { finishUpdate({ ok: true, unchanged: true }) }); await settle()
  // Continue pressed first; an update starts while its session.resume is still on the way: when that answer
  // arrives, nothing is released.
  const normalResume = scenario.byMethod['session.resume']
  let releaseResume = null
  scenario.byMethod['session.resume'] = params => (params.omit_messages && !releaseResume
    ? new Promise(resolve => { releaseResume = () => resolve(normalResume(params)) })
    : normalResume(params))
  await click('Continue', interrupted.node.querySelector('.cs-b-card.warn')); await settle()
  await click('Update ready', interrupted.node); await click('Update', interrupted.node.ownerDocument.querySelector('.cs-upd-dlg')); await settle()
  check('the resume is still on the way when the update starts', () => { assert.ok(releaseResume, 'session.resume is pending') })
  await act(async () => { releaseResume() }); await settle()
  check('a Continue pressed before an update releases nothing once the update has started', () => {
    assert.deepEqual(resolved, []); assert.equal(submits.length, submitsUpdating)
    assert.ok(interrupted.node.querySelector('.cs-b-card.warn'), 'the conversation stays paused')
  })
  await act(async () => { finishUpdate({ ok: true, unchanged: true }) }); await settle()
  scenario.byMethod['session.resume'] = normalResume
  scenario['plugin-update'] = undefined
  await interrupted.rerender()
  await click('Continue', interrupted.node.querySelector('.cs-b-card.warn'))
  await settle()
  check('Continue drops the lost turn (not run again) and sends nothing new when messages wait', () => {
    assert.deepEqual(resolved, [{ session_id: 'rt-of-st-lost', admission_id: 'adm-lost' }])
    assert.equal(submits.length, submitsBefore + 1)
    assert.ok(!interrupted.node.querySelector('.cs-b-card.warn'))
  })
  lostRunning = true // polling can land between any two of these events on a loaded machine
  await act(async () => { emit({ type: 'message.start', session_id: 'rt-of-st-lost', payload: { turn_id: 'L1' } }) })
  await settle()
  check('then the waiting messages run in order', () => {
    assert.equal([...interrupted.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'continue')
    assert.deepEqual([...interrupted.node.querySelectorAll('.cs-b-user.queued')].map(node => node.lastChild.textContent), ['and add clouds'])
  })
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-lost', payload: { text: 'Done.' } }) })
  // Lost again with nothing waiting: Continue asks HermRetro to pick up where it stopped.
  await act(async () => { emit({ type: 'message.start', session_id: 'rt-of-st-lost', payload: { turn_id: 'L2' } }) })
  await settle()
  check('while a turn runs the message box offers Stop', () => { assert.ok(interrupted.node.querySelector('.cs-b-comp button[aria-label="Stop"]')) })
  lostRunning = false
  lostRows = [{ admission_id: 'adm-lost-2', status: 'unknown', text: 'and add clouds', execution_generation: 3 }]
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-lost', payload: { pending: lostRows, running: false } }) })
  await settle()
  check('a turn lost while the page watched stops the working state and shows the card', () => {
    assert.match(interrupted.node.querySelector('.cs-b-card.warn')?.textContent ?? '', /pick up where it stopped/)
    assert.ok(!interrupted.node.querySelector('.cs-b-comp button[aria-label="Stop"]'))
  })
  await click('Continue', interrupted.node.querySelector('.cs-b-card.warn'))
  await settle()
  check('with nothing waiting, Continue drops the lost turn and asks to continue', () => {
    assert.deepEqual(resolved.at(-1), { session_id: 'rt-of-st-lost', admission_id: 'adm-lost-2' })
    assert.match(submits.at(-1).text, /cut off when Hermes restarted\. Continue where you left off/)
    assert.equal([...interrupted.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'Continue')
  })
  await interrupted.close()
})
