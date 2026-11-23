// A redirected prompt stays inside the live build turn, even before its submission reply.
import assert from 'node:assert/strict'
import { runScenario } from './harness.mjs'

await runScenario(async ({ act, answered, buildScenario, check, click, emit, mount, page, scenario, settle, typeInto }) => {
  const game = 'fff666fff666'
  const runtime = 'rt-frog'
  const ref = 'f'.repeat(32)
  buildScenario({ selected: game })
  scenario.games = answered({ games: [{
    id: game, title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio',
    state: 'changed', session: { storedId: 'st-frog' }
  }], device: { hardwareEnabled: false, skipped: true } })
  scenario.byMethod['session.resume'] = { session_id: runtime, running: false, messages: [] }
  scenario.byMethod['plugin.hermretro.builds'] = { ok: true, builds: [{ id: '10', buildRefs: [ref], reason: 'build' }] }
  scenario.byMethod['prompt.submit'] = { status: 'streaming' }
  const view = await mount(page)
  await settle()
  const send = async text => {
    await typeInto(view.node.querySelector('textarea[aria-label="Message Hermes"]'), text)
    await click('Send', view.node.querySelector('.cs-b-comp'))
  }
  const frame = (type, payload = {}) => act(async () => emit({ type, session_id: runtime, payload: { ...payload, turn_id: 'build-turn' } }))
  const call = { tool_id: 'rom', name: 'tool_call', args: { calls: [{ name: 'chromatic_rom_build', arguments: {} }] } }

  await send('Build the pond')
  await frame('message.start')
  await frame('tool.start', call)
  let finishSubmit
  scenario.byMethod['prompt.submit'] = () => new Promise(resolve => { finishSubmit = resolve })
  await send('Make the water darker')
  check('the optimistic follow-up stays visible in the active turn', () => {
    assert.equal(view.node.querySelectorAll('.cs-b-turn').length, 1)
    assert.deepEqual([...view.node.querySelectorAll('.cs-b-turn .cs-b-user')].map(node => node.textContent), [
      'Build the pond', 'Make the water darker'
    ])
  })
  await frame('tool.complete', { ...call, result: { buildRef: ref } })
  await frame('message.complete', { text: 'The pond is built.' })
  await act(async () => finishSubmit({ status: 'redirected' }))
  await settle()
  await click('Builds', view.node.querySelector('.cs-b-head'))
  await settle()
  check('one completed ROM step is attributed to the original request and keeps its exact snapshot', () => {
    const [row, ...other] = view.node.querySelectorAll('.cs-b-brow')
    assert.equal(other.length, 0)
    assert.match(row.textContent, /#1Build the pond/)
    assert.equal([...row.querySelectorAll('button')].find(button => button.textContent === 'Restore').disabled, false)
    assert.match(view.node.querySelector('.cs-b-wk-head').textContent, /1 step/)
  })
  await view.close()
})
