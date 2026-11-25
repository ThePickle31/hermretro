// A build shown or reported before it passed its checks says so on its card and in Builds, with why.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'
import { frogPost, resumeConversation, toolCall } from './frog-post-fixture.mjs'

const NOT_RUN = 'T1 has no result on this ROM.'
const NOT_CURRENT = 'Game files changed after the playable copy was made, so it is not the current game.'

await runScenario(async ({ answered, buildScenario, check, click, mount, page, scenario, settle }) => {
  const frog = frogPost()
  buildScenario({ selected: frog.id })
  scenario.games = answered({ games: [{ ...frog, session: { storedId: 'st-unfinished' } }], device: { hardwareEnabled: false, skipped: true } })
  const report = {
    title: 'Lamp in the dark', summary: 'The lamp lights.', tested: ['Lamp lights'],
    checks: [{ id: 'T1', text: 'The lamp lights', result: 'not run' }], difficulty: 'Easy.'
  }
  const shown = { ok: true, studio: { gameId: frog.id, note: null }, message: 'Shown.', unfinished: { request: 'Show me now', notVerified: [NOT_RUN], notCurrent: NOT_CURRENT } }
  scenario.byMethod['session.resume'] = resumeConversation(() => [
    { role: 'user', content: 'make a lamp', timestamp: 1000 },
    { role: 'assistant', content: '', timestamp: 1001, tool_calls: [toolCall('b1', 'chromatic_rom_build'), toolCall('r1', 'chromatic_build_report', report)] },
    { role: 'tool', tool_call_id: 'b1', content: JSON.stringify({ ok: true }), timestamp: 1010 },
    { role: 'tool', tool_call_id: 'r1', content: JSON.stringify({ ok: true, report }), timestamp: 1011 },
    { role: 'assistant', content: 'Done.', timestamp: 1012 },
    { role: 'user', content: 'show me now', timestamp: 2000 },
    { role: 'assistant', content: '', timestamp: 2001, tool_calls: [
      toolCall('b2', 'chromatic_rom_build'), toolCall('p2', 'chromatic_present_game', { unfinished: 'Show me now' }),
      toolCall('r2', 'chromatic_build_report', { ...report, unfinished: 'Show me now' })] },
    { role: 'tool', tool_call_id: 'b2', content: JSON.stringify({ ok: true }), timestamp: 2010 },
    { role: 'tool', tool_call_id: 'p2', content: JSON.stringify(shown), timestamp: 2011 },
    { role: 'tool', tool_call_id: 'r2', content: JSON.stringify({ ok: true, report: { ...report, unfinished: 'Show me now', notVerified: [NOT_RUN] } }), timestamp: 2012 },
    { role: 'assistant', content: 'Here it is, unfinished.', timestamp: 2013 }])
  const view = await mount(page)
  await settle(100)
  const card = n => view.node.querySelector(`.cs-b-bc[data-build="${n}"]`)
  check('the unfinished build says so on its card', () => {
    assert.equal(card(2).querySelector('.cs-b-bc-unfinished').textContent, 'Unfinished')
  })
  await click('Details', card(2))
  check('its details give the reason, why the copy is not current and what was not verified, once each', () => {
    const why = [...card(2).querySelectorAll('.cs-b-bc-unfinished-why p')].map(node => node.textContent)
    assert.deepEqual(why, ['Show me now', NOT_CURRENT, NOT_RUN])
  })
  await click('Builds', view.node.querySelector('.cs-b-head'))
  await settle()
  check('Builds marks the unfinished build', () => {
    const rows = [...view.node.querySelectorAll('.cs-b-brow')].map(node => node.textContent)
    assert.match(rows[0], /#2.*unfinished/)
    assert.doesNotMatch(rows[1], /unfinished/)
  })
  await view.close()
})
