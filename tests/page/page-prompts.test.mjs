// The Prompts page's Reader, opened from the Games shelf's blank cartridge (starting state: games-fixture.mjs).
// Run alone: node tests/page/page-prompts.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { gamesStudio } from './games-fixture.mjs'
import { runScenario } from './harness.mjs'

await runScenario(async helpers => {
  const { dom, plugin, scenario, text, click, tab, currentTab, settle, button, typeInto, key, check } = helpers
  const { games, studio } = await gamesStudio(helpers)
  await tab('Games')

  // Prompts: the Reader.
  await click('New game', dom.window.document.querySelector('.cs-shelf'))
  check('the blank cartridge opens the Create a new game prompt', () => {
    assert.equal(currentTab(), 'Prompts'); assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Create a new game')
  })
  check('the Reader lists the prompts grouped Plan / Create / Play / Polish / On your Chromatic', () => {
    const groups = [...dom.window.document.querySelectorAll('.cs-rgrp > span:first-child')].map(node => node.textContent)
    assert.deepEqual(groups, ['Plan', 'Create', 'Play', 'Polish', 'On your Chromatic'])
    assert.equal(dom.window.document.querySelectorAll('.cs-ritem').length, 11)
  })
  const area = () => dom.window.document.querySelector('.cs-rdetail textarea')
  check('{folder}/{name} become inputs; the folder defaults to the plugin games folder', () => {
    assert.equal(dom.window.document.getElementById('cs-f-folder').value, '/home/u/.hermes/hermretro/games')
    assert.equal(dom.window.document.getElementById('cs-f-name').value, 'MoonGarden')
    assert.match(area().value, /new GB Studio project at \/home\/u\/\.hermes\/hermretro\/games\/MoonGarden\. Make a small exploration game/)
  })
  await typeInto(dom.window.document.getElementById('cs-f-name'), 'StarFarm')
  check('editing the name rewrites the prompt', () => {
    assert.match(area().value, /\/home\/u\/\.hermes\/hermretro\/games\/StarFarm\./)
  })
  await typeInto(area(), 'My own words')
  check('the prompt text is editable and can be reset', () => { assert.equal(area().value, 'My own words'); assert.ok(button('Reset text')) })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Start a new chat')
  await settle()
  check('Start a new chat opens a new chat and puts the edited text in its composer', () => {
    assert.deepEqual(scenario.calls[0], ['newChat', null]); assert.deepEqual(scenario.inserted.at(-1), ['new', 'My own words'])
  })
  await click('Reset text')
  check('Reset text restores the prompt', () => { assert.match(area().value, /StarFarm/) })
  scenario.calls.length = 0
  await click('Add to current chat')
  await settle()
  check('Add to current chat goes to the composer the user is in first', () => { assert.deepEqual(scenario.calls[0], ['insert', null]) })
  await key('keydown', 'ArrowDown', dom.window.document.body)
  check('↓ moves to the next prompt', () => { assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Remix an example') })
  await typeInto(dom.window.document.querySelector('.cs-search input'), 'palette')
  check('search filters the list', () => {
    assert.deepEqual([...dom.window.document.querySelectorAll('.cs-ritem')].map(node => node.textContent), ['Update the palette'])
    assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Update the palette')
  })
  await studio.close()
})
