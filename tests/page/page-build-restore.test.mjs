// The asset viewer's Restore (page/pages/build/viewer/asset-viewer.js): putting a kept version back redraws every
// picture of that file already on screen, not only the viewer's own, even one asked for by another spelling of its path.
// Run alone: node tests/page/page-build-restore.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, buildScenario, dom, scenario, page, click, settle, mount, check, answered }) => {
  buildScenario({ selected: 'fff666fff666' })
  scenario.games = answered({ games: [{ id: 'fff666fff666', title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio',
    state: 'ready', rom: null, webExport: true, thumb: null, chat: null, error: null, session: { storedId: 'st-frog' } }],
  device: { hardwareEnabled: false, skipped: true } })
  const art = '/home/u/games/FrogPost/assets/ui/frame.png'
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, running: false, messages: params.omit_messages ? [] : [
    { role: 'user', content: 'draw a frame', timestamp: 1000 },
    { role: 'assistant', content: '', timestamp: 1001, tool_calls: [{ id: 'i1', function: { name: 'chromatic_asset_import', arguments: JSON.stringify({ assetPath: 'assets/ui/frame.png', kind: 'ui' }) } }] },
    { role: 'tool', tool_call_id: 'i1', content: JSON.stringify({ ok: true }), timestamp: 1010 },
    { role: 'assistant', content: '', timestamp: 1011, tool_calls: [{ id: 'i2', function: { name: 'chromatic_asset_import', arguments: JSON.stringify({ assetPath: 'assets/ui/../ui/frame.png', kind: 'ui' }) } }] },
    { role: 'tool', tool_call_id: 'i2', content: JSON.stringify({ ok: true }), timestamp: 1012 },
    { role: 'assistant', content: 'Drawn.', timestamp: 1020 }] })
  // The file on disk is v2 until v1 is put back.
  const look = { v1: 'data:image/png;base64,djE=', v2: 'data:image/png;base64,djI=' }
  let onDisk = 'v2'
  scenario.byMethod['plugin.hermretro.asset'] = params => {
    const shown = params.version === '1' ? 'v1' : params.version === '2' ? 'v2' : onDisk
    return { ok: true, path: art, name: 'frame.png', relative: 'assets/ui/frame.png', kind: 'ui', width: 16, height: 16, bytes: 4,
      earlier: Boolean(params.version) && shown !== onDisk, versionId: shown === 'v1' ? '1' : '2', dataUrl: look[shown] }
  }
  scenario.byMethod['plugin.hermretro.asset_info'] = params => ({ ok: true, path: params.path, relative: 'assets/ui/frame.png', kind: 'ui',
    versions: [{ id: '1', at: 1_000_000, file: '/kept/1.png', current: onDisk === 'v1' }, { id: '2', at: 1_010_000, file: params.path, current: onDisk === 'v2' }] })
  const restores = []
  scenario.byMethod['plugin.hermretro.asset_restore'] = params => { restores.push(params); onDisk = 'v1'; return { ok: true, path: art, versions: [] } }

  const view = await mount(page)
  await settle(100)
  const stacked = () => [...view.node.querySelectorAll('.cs-b-wk-row .cs-b-stack-i img')].map(node => node.getAttribute('src'))
  check('the turn shows both spellings of the picture it made as the file is now', () => { assert.deepEqual(stacked(), [look.v2, look.v2]) })
  await act(async () => { view.node.querySelector('.cs-b-wk-assets').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle(50)
  await act(async () => { view.node.querySelector('.cs-v button[aria-label="Version 1"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle(30)
  await click('Restore v1', view.node.querySelector('.cs-v'))
  await settle(80)
  check('Restore puts v1 back for this game', () => { assert.deepEqual(restores, [{ path: art, root: '/home/u/games/FrogPost', version: '1' }]) })
  check('the pictures already in the conversation redraw as v1, whichever path they asked for', () => { assert.deepEqual(stacked(), [look.v1, look.v1]) })
  await view.close()
})
