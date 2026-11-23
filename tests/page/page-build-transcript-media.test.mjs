// Build transcript, tool steps, result cards, reply pictures, suggestions and @ mentions.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'
import { frogPost, frogSprite, lamplight, reportedRobinBuild, robinBuildReport, resumeConversation, toolCall } from './frog-post-fixture.mjs'

await runScenario(async ({ answered, buildScenario, button, check, click, key, mount, page, scenario, settle, typeInto }) => {
  const frog = frogPost()
  const otherGame = lamplight()
  buildScenario({ selected: frog.id })
  const showConversation = storedId => {
    scenario.games = answered({ games: [{ ...frog, session: { storedId } }, otherGame], device: { hardwareEnabled: false, skipped: true } })
  }
  showConversation('st-long')
  const submits = []
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }

  const assetRoots = new Set()
  scenario.byMethod['plugin.hermretro.asset'] = params => {
    assetRoots.add(params.root)
    if (params.path.startsWith(otherGame.projectRoot + '/')) {
      return { ok: false, code: 'OTHER_GAME', error: 'That image belongs to another game.' }
    }
    return frogSprite(params.path)
  }
  // A long turn: Simple shows five plain groups, Technical every step, and reply pictures are small cards.
  const report = robinBuildReport()
  scenario.byMethod['session.resume'] = resumeConversation(() => [
    { role: 'user', content: 'make a bird game', timestamp: 2000 },
    { role: 'assistant', content: 'Planning.', timestamp: 2001, tool_calls: [
      toolCall('p1', 'skill_view', { name: 'hermretro:authoring' }), toolCall('p2', 'skill_view', { name: 'hermretro:pixel-art' }), toolCall('p3', 'chromatic_project_inspect'), toolCall('p4', 'chromatic_project_inventory'),
      toolCall('a1', 'chromatic_asset_import', { assetPath: 'assets/sprites/bird.png' }), toolCall('a2', 'chromatic_sprite_edit'), toolCall('a3', 'terminal', { command: 'python draw.py' }),
      toolCall('w1', 'chromatic_scene_update'), toolCall('w2', 'chromatic_actor_update'),
      toolCall('b1', 'chromatic_rom_build'), toolCall('b2', 'chromatic_emulator_step'), toolCall('r1', 'chromatic_build_report', report)] },
    ...['p1', 'p2', 'p3', 'p4', 'a1', 'a2', 'a3', 'w1', 'w2', 'b1', 'b2', 'r1'].map((id, index) => ({
      role: 'tool', tool_call_id: id, timestamp: 2002 + index,
      ...(id === 'b1' ? { content: JSON.stringify({ structuredContent: { success: true } }) } : {})
    })),
    { role: 'assistant', content: 'Here they are:\n\nMEDIA:/home/u/games/FrogPost/assets/sprites/bird.png\nMEDIA:/home/u/games/FrogPost/cover.png\nMEDIA:/home/u/games/Lamplight/cover.png\n\nWant it to flap all the time?', timestamp: 2100 },
    { role: 'user', content: 'add music', timestamp: 3000 },
    // As the gateway resumes it: the build went through Hermes's tool_call door, and its result row has no name.
    { role: 'assistant', content: '', timestamp: 3001, tool_calls: [toolCall('m1', 'tool_call', { calls: [{ name: 'chromatic_rom_build', arguments: {} }] })] },
    // The engine's own shape for a build that ran and stopped: success false, the reason in a diagnostic.
    { role: 'tool', tool_call_id: 'm1', content: JSON.stringify({ result: 'Operation failed (diagnostics: 1).', structuredContent: { success: false, diagnostics: [{ severity: 'error', code: 'BANK_FULL', message: 'The song is 2.4 KB too big for the cartridge.' }] } }), timestamp: 3050 },
    { role: 'assistant', content: 'The music did not fit.', timestamp: 3060 }])
  const transcript = await mount(page)
  await settle(100)
  check('only the current build mounts its conversation and the previous build starts folded', () => {
    assert.equal(transcript.node.querySelector('.cs-b-history-row').getAttribute('aria-expanded'), 'false')
    assert.equal(transcript.node.querySelectorAll('.cs-b-turn-body').length, 1)
  })
  await click('Builds', transcript.node.querySelector('.cs-b-head'))
  await settle()
  await click('Show', transcript.node.querySelectorAll('.cs-b-brow')[1])
  await settle()
  check('Show opens the chosen build at its conversation', () => {
    assert.equal(transcript.node.querySelector('.cs-b-history-row').getAttribute('aria-expanded'), 'true')
  })
  check('the report becomes build card #1: title, summary, what changed, and a footer with what was tested', () => {
    const card = transcript.node.querySelector('.cs-b-bc[data-build="1"]')
    assert.ok(card); assert.match(card.querySelector('.cs-b-bc-title').textContent, /Robin in the sky/)
    assert.match(card.querySelector('.cs-b-bc-sum').textContent, /little red robin/)
    assert.ok(!card.querySelector('.cs-b-bc-changes'))
    assert.match(card.querySelector('.cs-b-bc-foot').textContent, /✓ 2 play-tested.*○ 1 not tested.*⚠ 1 note/)
    assert.ok(!/chromatic_build_report|Using build report/.test(transcript.node.textContent), 'the report is not a step')
  })
  check('the reply leads its build result, and its pictures are small cards in one row', () => {
    const turn = transcript.node.querySelectorAll('.cs-b-turn')[0]
    const order = [...turn.querySelector('.cs-b-her').children].map(node => node.className.split(' ')[0])
    assert.ok(order.lastIndexOf('cs-b-agent') < order.indexOf('cs-b-bc'), 'reply before the result')
    const cards = turn.querySelectorAll('.cs-b-rimgs .cs-b-rchip')
    assert.equal(cards.length, 1, 'the separate cover stays in the reply')
    assert.ok(turn.querySelector('.cs-b-ba-side.now'), 'the matching sprite stays in its result')
  })
  check('every picture is asked for as Frog Post\u2019s, so the backend can refuse another game\u2019s', () => {
    assert.deepEqual([...assetRoots], [frog.projectRoot])
  })
  check('another game\u2019s picture in the reply stays an inert line the app does not open', () => {
    const turn = transcript.node.querySelectorAll('.cs-b-turn')[0]
    const inert = [...turn.querySelectorAll('[data-markdown][data-inert]')].map(node => node.textContent)
    assert.deepEqual(inert, ['MEDIA:/home/u/games/Lamplight/cover.png'])
  })
  await click('Details', transcript.node.querySelector('.cs-b-bc[data-build="1"]'))
  check('Details lists what was play-tested, not tested and the notes', () => {
    assert.deepEqual([...transcript.node.querySelectorAll('.cs-b-bc-details .cs-b-bc-changes li')].map(node => node.textContent), ['+Robin sprite, 3 views', '~Camera follows the player'])
    const details = transcript.node.querySelector('.cs-b-bc-details').textContent
    assert.match(details, /Play-tested.*Robin faces where it flies.*Not tested.*Sound.*You might notice.*only flaps while moving/)
  })
  check('a failed compile is build #2 that didn\u2019t finish, with what went wrong, and the pill says so', () => {
    const card = transcript.node.querySelector('.cs-b-bc[data-build="2"]')
    assert.ok(card); assert.ok(card.classList.contains('bad'))
    assert.match(card.textContent, /#2The build didn’t finish/); assert.match(card.textContent, /2\.4 KB too big/)
    assert.ok(button('Ask HermRetro to fix it'))
    assert.match(transcript.node.querySelector('.cs-b-pill').textContent, /Build #2 didn’t finish/)
    assert.match(transcript.node.querySelectorAll('.cs-b-turn')[1].textContent, /1 step(?!s)/, 'the result row is the build step, not another one')
  })
  check('next-step chips show only under the newest reply', () => {
    assert.equal(transcript.node.querySelectorAll('.cs-b-next-steps').length, 0, 'the last turn reported nothing to suggest')
  })
  await click('11 steps', transcript.node.querySelector('.cs-b-turn'))
  check('Simple shows the turn as five plain groups, folded, each with its step count', () => {
    const heads = [...transcript.node.querySelectorAll('.cs-b-ph-head')].map(node => node.textContent)
    assert.deepEqual(heads.map(text => text.replace(/\d+ steps?.*/, '').trim()), ['Planned it', 'Drew the art', 'Set up the level', 'Built it', 'Play-tested it'])
    assert.match(heads[1], /3 steps/, 'a command joins the group it was helping')
    assert.equal(transcript.node.querySelectorAll('.cs-b-ph-body').length, 0, 'a finished turn starts with every group folded')
  })
  await click('Planned it', transcript.node)
  check('a group of only glances says so instead of listing them', () => {
    const body = transcript.node.querySelector('.cs-b-ph-body')
    assert.equal(body.querySelectorAll('.cs-b-tool').length, 0); assert.match(body.textContent, /Technical shows them/)
  })
  await click('Technical', transcript.node.querySelector('.cs-b-wk-mode'))
  check('Technical lists every step with its detail, for every turn', () => {
    assert.equal(transcript.node.querySelector('.cs-b-turn .cs-b-wk-inner').querySelectorAll('.cs-b-tool').length, 11)
    assert.match(transcript.node.querySelector('.cs-b-turn .cs-b-wk-inner').textContent, /python draw\.py/)
  })
  await click('Simple', transcript.node.querySelector('.cs-b-wk-mode'))
  await click('Builds', transcript.node.querySelector('.cs-b-head'))
  await settle(30)
  await key('keydown', 'Escape')
  await transcript.close()
  // On a conversation whose newest turn reported suggestions, try those chips and the @ picker.
  showConversation('st-long2')
  scenario.byMethod['session.resume'] = resumeConversation(() => reportedRobinBuild('Want it to flap all the time?', report))
  const gamePictures = []
  scenario.byMethod['plugin.hermretro.assets'] = params => {
    gamePictures.push(params.game)
    return { ok: true, assets: [
      { path: '/home/u/games/FrogPost/cover.png', name: 'Cover', file: 'cover.png', kind: 'cover', modifiedAt: 5 },
      { path: '/home/u/games/FrogPost/assets/sprites/bird.png', name: 'Robin', file: 'bird.png', kind: 'sprite', modifiedAt: 5 },
      { path: '/home/u/games/FrogPost/assets/backgrounds/sky.png', name: 'Open Sky', file: 'sky.png', kind: 'background', modifiedAt: 5 }] }
  }
  const composer = await mount(page)
  await settle(100)
  check('the newest reply ends with its suggestions as chips', () => {
    assert.deepEqual([...composer.node.querySelectorAll('.cs-b-next-steps button')].map(node => node.textContent), ['Flap while idle', 'Fly faster'])
  })
  await click('Fly faster', composer.node.querySelector('.cs-b-next-steps'))
  await settle()
  check('a suggestion fills the message box and is not sent', () => {
    assert.equal(composer.node.querySelector('textarea[aria-label="Message Hermes"]').value, 'Fly faster')
  })
  const messageBox = composer.node.querySelector('textarea[aria-label="Message Hermes"]')
  await typeInto(messageBox, 'make @')
  await settle(50)
  check('typing @ lists the game\u2019s pictures', () => {
    assert.deepEqual(gamePictures.slice(-1), ['fff666fff666'])
    assert.deepEqual([...composer.node.querySelectorAll('.cs-b-mention-row b')].map(node => node.textContent), ['Cover', 'Robin', 'Open Sky'])
  })
  await typeInto(messageBox, 'make @rob')
  await settle(20)
  check('what follows @ filters the list', () => {
    assert.deepEqual([...composer.node.querySelectorAll('.cs-b-mention-row b')].map(node => node.textContent), ['Robin'])
  })
  await key('keydown', 'Enter', messageBox)
  await settle()
  check('Enter picks it: the @word leaves the text and the picture is attached as a mention', () => {
    assert.ok(!composer.node.querySelector('.cs-b-mention'))
    assert.equal(messageBox.value, 'make ')
    assert.match(composer.node.querySelector('.cs-b-comp .cs-b-chip.mention').textContent, /@Robin/)
  })
  await typeInto(messageBox, 'make it chubbier')
  await click('Send', composer.node.querySelector('.cs-b-comp'))
  await settle()
  check('the message names the file for the agent and shows the mention in the bubble', () => {
    assert.match(submits.at(-1).text, /^About \/home\/u\/games\/FrogPost\/assets\/sprites\/bird\.png:\nmake it chubbier$/)
    assert.match([...composer.node.querySelectorAll('.cs-b-user')].at(-1).textContent, /@Robin/)
  })
  await composer.close()
})
