// Renders the real desktop/plugin.js page with canned backend answers, for looking at it.
import { createRoot } from 'react-dom/client'
import { jsx } from 'react/jsx-runtime'
import { preview } from '@hermes/plugin-sdk'
import { THEME_PRESET_PALETTES } from 'hermes-theme-presets'
import plugin from '../../../desktop/plugin.js'

const answered = data => ({ data, isFetching: false, isPending: false })
const cli = state => ({ state, version: state === 'installed' ? '1.2.1' : null, terms: 'https://modretro.com/eula' })
const status = (extra = {}) => ({
  ok: true,
  platform: { system: 'linux', machine: 'x86_64', qualified: true },
  node: { found: true, version: '26.12.1', required: '22', ok: true },
  engine: { present: true, version: '1.0.34', verified: true },
  hardware_enabled: false,
  project: null,
  profile: { name: 'hermretro', is_studio: true, studio: { installed: true } },
  deps: { toolchain_root: '~/.hermes/hermretro/.cache/toolchain', device_cli: cli('missing') },
  ...extra
})
const COMPONENTS = [
  ['cli', 'GB Studio CLI', '4.3.2'],
  ['gbdk', 'GBDK compiler', '4.5.0'],
  ['python', 'Python (emulator)', '3.13'],
  ['pyboy', 'PyBoy emulator', '2.7.0'],
  ['pillow', 'Pillow imaging', '>=11,<13', '12.3.0'],
  ['desktop', 'GB Studio desktop editor', '4.3.2', null, true]
]
const doctor = ready => ({
  ok: true,
  missing_required: ready ? [] : ['cli', 'gbdk', 'python', 'pyboy', 'pillow'],
  components: COMPONENTS.map(([id, label, required, found, optional]) => ({
    id,
    label,
    required,
    optional: Boolean(optional),
    status: ready && !optional ? 'ready' : 'missing',
    detected: ready && !optional ? (found ?? required) : ''
  }))
})
const installer = { name: 'chromatic-dev', is_studio: false, create: {}, studio: { exists: false, installed: false } }
// Example library for the Games / Emulator / Home pages. Title screens are the mockups' real
// captures (copied next to index.html by build.mjs); the player is a static stand-in page.
const t = Math.round(Date.now() / 1000)
const GAMES = [
  { id: 'c0e1a2b3c4d5', title: 'Comet Drift', projectRoot: '/home/you/ChromaticGames/CometDrift', kind: 'gbstudio', state: 'ready', webExport: true,
    rom: { path: '/home/you/ChromaticGames/CometDrift/build/web/rom/game.gbc', sha256: 'aa11', size: 131072, builtAt: t - 7200 },
    thumb: 'thumbs/comet.png', cover: true, chat: { sessionId: 'st-comet', title: 'Comet Drift — dodge the comets' }, error: null,
    card: { title: 'Comet Drift', tagline: 'Dash a tiny ship through falling comets.', description: 'Dodge three waves of comets, dash with B and reach the Asteroid Belt.', genres: ['Arcade', 'Action'], tags: [], controls: {}, complete: true, missing: [], hasCover: true } },
  { id: 's1a2b3c4d5e6', title: 'Chromatic Starter', projectRoot: '/home/you/ChromaticGames/ChromaticStarter', kind: 'gbstudio', state: 'ready', webExport: true,
    rom: { path: '/x/game.gbc', sha256: 'bb22', size: 65536, builtAt: t - 90000 }, thumb: 'thumbs/starter.png', chat: { sessionId: 'st-starter', title: 'Chromatic starter project' }, error: null },
  { id: 'p1a2b3c4d5e6', title: 'Studio Proof', projectRoot: '/home/you/ChromaticGames/StudioProof', kind: 'gbstudio', state: 'changed', webExport: true,
    rom: { path: '/x/game.gbc', sha256: 'cc33', size: 65536, builtAt: t - 260000 }, thumb: 'thumbs/studio.png', chat: null, error: null },
  { id: 'h1a2b3c4d5e6', title: 'Hello Color', projectRoot: '/home/you/ChromaticGames/HelloColor', kind: 'gbdk', state: 'ready', webExport: true,
    rom: { path: '/x/game.gbc', sha256: 'dd44', size: 32768, builtAt: t - 400000 }, thumb: 'thumbs/hello.png', chat: null, error: null },
  { id: 'r1a2b3c4d5e6', title: 'Robo Run', projectRoot: '/home/you/ChromaticGames/RoboRun', kind: 'gbdk', state: 'failed', webExport: false,
    rom: null, thumb: null, chat: { sessionId: 'st-robo', title: 'Robo Run' }, error: 'background uses 212 tiles (limit 192)' }
]
const DEMO = { id: 'demo', title: 'Hello Color', kind: 'gbdk', note: 'ModRetro example' }
const library = (list = GAMES) => answered({ games: list, demo: DEMO, gamesDir: '/home/you/.hermes/hermretro/games', device: { hardwareEnabled: true, skipped: false } })
const playerAt = answered({ url: new URL('player/index.html#comet', location.href).href, romSha256: 'aa11', title: 'Comet Drift' })
// With nothing of the user's to play, the Emulator page loads the built-in demo cartridge.
const demoPlayer = answered({ url: new URL('player/index.html#demo', location.href).href, romSha256: 'demo', title: 'Hello Color', demo: true })
const notLoaded = { isError: true, isFetching: false, error: Object.assign(new Error('unknown method'), { code: -32601 }) }

// What the backend's install RPC reports (sizes as measured on linux-x64).
const MANIFEST = { bytes: 708_271_425, disk_bytes: 2_300_000_000, measured_on: 'linux-x64', exact: true, items: [
  { id: 'gbdk', component: 'gbdk', name: 'GBDK compiler', version: '4.5.0', source: 'github.com/gbdk-2020/gbdk-2020', bytes: 6_870_728, purpose: 'Compiles C for the Game Boy CPU' },
  { id: 'gbstudio', component: 'cli', name: 'GB Studio CLI', version: '4.3.2', source: 'github.com/chrismaltby/gb-studio', bytes: 18_130_254, purpose: 'Builds your game into a ROM' },
  { id: 'gbvm', component: 'cli', name: 'GBVM', version: 'bd6f41c', source: 'github.com/chrismaltby/gbvm', bytes: 3_995_554, purpose: 'The Game Boy engine inside every game' },
  { id: 'packages', component: 'cli', name: 'GB Studio packages', version: 'yarn 4.4.1', source: 'registry.npmjs.org', bytes: 551_000_000, approx: true, purpose: 'The libraries GB Studio needs' },
  { id: 'uv', component: 'uv', name: 'uv', version: '0.12.6', source: 'github.com/astral-sh/uv', bytes: 20_274_889, purpose: 'Installs the Python parts' },
  { id: 'emulator', component: 'emulator', name: 'Python, PyBoy and Pillow', version: '3.13.12 · 2.7.0 · 12.3.0', source: 'python-build-standalone · pypi.org', bytes: 108_000_000, approx: true, purpose: 'The emulator Hermes playtests with' }] }
const installed = install => answered({ ok: true, manifest: MANIFEST, root: '~/.hermes/hermretro/.cache/toolchain', install })
const RUNNING = { state: 'running', started_at: 1, fraction: 0.4, downloaded_bytes: 281_000_000, current: 'cli', run: { components: {
  gbdk: { state: 'done', version: '4.5.0', checks: [{ file: 'gbdk-linux64.tar.gz', sha256: 'd7857a5f6d135ee4', reused: false }] },
  cli: { state: 'running', checks: [] } } } }
const FAILED = { state: 'failed', started_at: 1, error: 'cli: yarn install: getaddrinfo ENOTFOUND registry.npmjs.org', run: { components: {
  gbdk: { state: 'done', version: '4.5.0', checks: [{ file: 'gbdk-linux64.tar.gz', sha256: 'd7857a5f6d135ee4', reused: false }] },
  cli: { state: 'failed', error: 'yarn install: getaddrinfo ENOTFOUND registry.npmjs.org', checks: [] } } } }
const firstRun = { profile: { ...{ name: 'default', is_studio: false, create: {}, studio: { exists: false, installed: false } } } }


// Build: Comet Drift's conversation. Images are drawn here (pixel sprites, a title frame) and served
// the way the backend's asset RPC does.
const ROOT = '/home/you/ChromaticGames/CometDrift'
const sprite = (frames, paint) => {
  const canvas = document.createElement('canvas')
  canvas.width = 16 * frames
  canvas.height = 16
  const c = canvas.getContext('2d')
  for (let f = 0; f < frames; f += 1) paint(c, f * 16, f)
  return canvas.toDataURL('image/png')
}
const px = (c, x, y, color, w = 1, h = 1) => { c.fillStyle = color; c.fillRect(x, y, w, h) }
const ASSETS = {
  [`${ROOT}/assets/sprites/ship.png`]: { name: 'Ship', w: 64, h: 16, url: () => sprite(4, (c, x, f) => {
    px(c, x + 6, 3, '#e8f0ff', 4, 10); px(c, x + 4, 6, '#7fa7ff', 2, 6); px(c, x + 10, 6, '#7fa7ff', 2, 6); px(c, x + 7, 1, '#ffd166', 2, 3)
    px(c, x + 7, 13, f % 2 ? '#ff6b35' : '#ffd166', 2, 2 + (f % 2)) }) },
  [`${ROOT}/assets/sprites/comet.png`]: { name: 'Comet', w: 32, h: 16, url: () => sprite(2, (c, x, f) => {
    px(c, x + 8, 6, '#ffe8a3', 5, 5); px(c, x + 9, 7, '#fff', 2, 2); px(c, x + 3 - f, 4, '#ff9f1c', 5, 2); px(c, x + 1, 9 + f, '#ff6b35', 6, 2) }) },
  [`${ROOT}/assets/backgrounds/asteroid_belt.png`]: { name: 'asteroid_belt.png', w: 160, h: 144, url: () => {
    const canvas = document.createElement('canvas'); canvas.width = 160; canvas.height = 144
    const c = canvas.getContext('2d'); c.fillStyle = '#0b1026'; c.fillRect(0, 0, 160, 144)
    for (let i = 0; i < 60; i += 1) px(c, (i * 53) % 160, (i * 31) % 144, i % 3 ? '#5b6ea8' : '#e8f0ff')
    for (let i = 0; i < 9; i += 1) { px(c, (i * 41) % 150, 20 + (i * 37) % 110, '#6b5a4a', 10, 8); px(c, (i * 41) % 150 + 2, 22 + (i * 37) % 110, '#8a7562', 5, 3) }
    return canvas.toDataURL('image/png') } },
  [`${ROOT}/cover.png`]: { name: 'cover.png', w: 160, h: 144, url: () => {
    const canvas = document.createElement('canvas'); canvas.width = 160; canvas.height = 144
    const c = canvas.getContext('2d'); c.fillStyle = '#0b1026'; c.fillRect(0, 0, 160, 144)
    for (let i = 0; i < 70; i += 1) px(c, (i * 47) % 160, (i * 29) % 144, i % 4 ? '#5b6ea8' : '#e8f0ff')
    px(c, 20, 18, '#ffd166', 120, 22); px(c, 24, 22, '#ff6b35', 112, 14)
    px(c, 74, 80, '#e8f0ff', 12, 30); px(c, 66, 92, '#7fa7ff', 8, 14); px(c, 86, 92, '#7fa7ff', 8, 14); px(c, 77, 110, '#ff6b35', 6, 10)
    return canvas.toDataURL('image/png') } }
}
const assetRpc = params => {
  const known = ASSETS[params?.path]
  if (!known) return { ok: false, code: 'MISSING' }
  known.data ??= known.url()
  // Build cards: the ship was redrawn at now-550 s (a reply from before that asks for the old one).
  if (params?.at && params.path.endsWith('/ship.png') && params.at > (now - 1400) * 1000 && params.at < (now - 550) * 1000) {
    const comet = ASSETS[`${ROOT}/assets/sprites/comet.png`]
    comet.data ??= comet.url()
    return { ...assetRpc({ path: params.path }), earlier: true, versionId: '1000', dataUrl: comet.data, width: 32,
      sprite: { name: 'Ship', frameWidth: 16, frameHeight: 16, animSpeed: 15, canvasWidth: 16, canvasHeight: 16, palette: null, standing: { tiles: frameTiles(0), flip: false } } }
  }
  return { ok: true, path: params.path, name: params.path.split('/').pop(), relative: params.path.slice(ROOT.length + 1), width: known.w, height: known.h,
    versionId: params?.version ?? '2000', dataUrl: known.data, ...(known.w > 16 && known.h === 16 ? { sprite: { name: known.name, frameWidth: 16, frameHeight: 16, animSpeed: 15, canvasWidth: 16, canvasHeight: 16, palette: null,
      standing: { tiles: frameTiles(0), flip: false }, moving: { frames: Array.from({ length: known.w / 16 }, (_, column) => frameTiles(column)), flip: false } } } : {}) }
}
// The viewer's details: versions, a sprite's animations and palette, and the scene that uses it.
const frameTiles = column => [{ x: 0, y: 0, sliceX: column * 16, sliceY: 0 }, { x: 8, y: 0, sliceX: column * 16 + 8, sliceY: 0 }]
const BELT = { id: 'belt', name: 'Asteroid Belt', width: 20, height: 18, background: `${ROOT}/assets/backgrounds/asteroid_belt.png`, actors: [
  { name: 'Player', spriteId: 'ship', sprite: `${ROOT}/assets/sprites/ship.png`, x: 9, y: 14, player: true, canvasWidth: 16, canvasHeight: 16, tiles: frameTiles(0), flip: false, palette: null },
  ...[[3, 4], [14, 6], [7, 9]].map(([x, y], index) => ({ name: `Comet ${index + 1}`, spriteId: 'comet', sprite: `${ROOT}/assets/sprites/comet.png`, x, y, canvasWidth: 16, canvasHeight: 16, tiles: frameTiles(0), flip: false, palette: null }))] }
const assetInfoRpc = params => {
  const known = ASSETS[params?.path]
  if (!known) return { ok: false, code: 'MISSING' }
  const versions = [{ id: '1000', at: Date.now() - 900_000, file: '/kept/1000.png', current: false }, { id: '2000', at: Date.now() - 60_000, file: params.path, current: true }]
  const relative = params.path.slice(ROOT.length + 1)
  if (relative.startsWith('assets/sprites/')) {
    const id = relative.includes('ship') ? 'ship' : 'comet'
    const columns = known.w / 16
    return { ok: true, path: params.path, relative, kind: 'sprite', versions,
      sprite: { name: known.name, id, type: 'fixed_movement', flipLeft: false, states: [''], canvasWidth: 16, canvasHeight: 16, animSpeed: 7, numTiles: columns * 2,
        animations: [{ slot: 0, name: 'Idle', frames: [frameTiles(0)] }, { slot: 4, name: 'Moving', frames: Array.from({ length: columns }, (_, column) => frameTiles(column)) }] },
      palette: { id: 'p', name: 'Hull', colors: ['#E8F0FF', '#7FA7FF', '#3A4A8A', '#101830'] },
      usedIn: [{ scene: 'Asteroid Belt', sceneId: 'belt', as: id === 'ship' ? ['Player'] : ['Comet 1', 'Comet 2', 'Comet 3'], count: id === 'ship' ? 1 : 3 }], scenes: [BELT] }
  }
  if (relative.startsWith('assets/backgrounds/')) {
    return { ok: true, path: params.path, relative, kind: 'background', versions, background: { name: 'Asteroid Belt', autoColor: true },
      usedIn: [{ scene: 'Asteroid Belt', sceneId: 'belt', as: ['Background'], count: 1 }], scenes: [BELT] }
  }
  return { ok: true, path: params.path, relative, kind: relative === 'cover.png' ? 'cover' : 'image', versions }
}
const now = Date.now() / 1000
const call = (id, name, args) => ({ id, function: { name: 'tool_call', arguments: JSON.stringify({ calls: [{ name, arguments: args }] }) } })
const HISTORY = [
  { role: 'user', text: 'Make the ship able to dash with B, and add a second level with faster comets.', timestamp: now - 1500 },
  { role: 'assistant', text: 'Adding a **dash** on B with a short cooldown, then a new *Asteroid Belt* scene where comets spawn twice as often.', timestamp: now - 1496,
    tool_calls: [call('a', 'chromatic_asset_import', { assetPath: 'assets/sprites/ship.png', kind: 'sprite' }), call('b', 'chromatic_scene_create', { name: 'Asteroid Belt' })] },
  { role: 'tool', tool_call_id: 'a', name: 'tool_call', timestamp: now - 1470 }, { role: 'tool', tool_call_id: 'b', name: 'tool_call', timestamp: now - 1440 },
  { role: 'assistant', text: 'The belt needs a darker sky so the comets read.', timestamp: now - 1438,
    tool_calls: [call('c', 'chromatic_asset_import', { assetPath: 'assets/backgrounds/asteroid_belt.png', kind: 'background' }), call('d', 'chromatic_rom_build', {}), call('e', 'chromatic_present_game', {})] },
  { role: 'tool', tool_call_id: 'c', name: 'tool_call', timestamp: now - 1420 }, { role: 'tool', tool_call_id: 'd', name: 'tool_call', timestamp: now - 1458 + 60 },
  { role: 'tool', tool_call_id: 'e', name: 'tool_call', timestamp: now - 1426 + 50 },
  { role: 'assistant', text: `Ready to try:\n\n- **Dash** with B through the first comet wave\n- Fly right into the *Asteroid Belt*\n\nI also drew a cover:\n\nMEDIA:${ROOT}/cover.png\n\nIt uses the game's own colours.`, timestamp: now - 1372 },
  { role: 'user', text: 'The dash feels too short. Double it. And can the comets have a fiery tail?', timestamp: now - 40 }]
// A long turn (11 steps) that folds into phases, with a reply that delivers two pictures.
const PHASED_HISTORY = [
  { role: 'user', text: 'Make a comet dodging game: a little ship, a starfield, comets to avoid.', timestamp: now - 900 },
  { role: 'assistant', text: 'Planning it out first.', timestamp: now - 898, tool_calls: [
    call('p1', 'skill_view', { name: 'hermretro:authoring' }), call('p2', 'skill_view', { name: 'hermretro:pixel-art' }), call('p3', 'chromatic_project_inspect', {}), call('p4', 'chromatic_project_inventory', {}),
    call('a1', 'chromatic_asset_import', { assetPath: 'assets/sprites/ship.png', kind: 'sprite' }), call('a2', 'chromatic_asset_import', { assetPath: 'assets/sprites/comet.png', kind: 'sprite' }),
    call('a3', 'chromatic_asset_import', { assetPath: 'assets/backgrounds/asteroid_belt.png', kind: 'background' }), call('a4', 'terminal', { command: 'python tools/draw_cover.py' }),
    call('w1', 'chromatic_scene_update', {}), call('w2', 'chromatic_actor_update', {}), call('w3', 'chromatic_script_edit', {}),
    call('b1', 'chromatic_rom_build', {}), call('b2', 'chromatic_emulator_step', {}), call('b3', 'chromatic_present_game', {})] },
  ...['p1', 'p2', 'p3', 'p4', 'a1', 'a2', 'a3', 'a4', 'w1', 'w2', 'w3', 'b1', 'b2', 'b3'].map((id, index) => ({ role: 'tool', tool_call_id: id, name: 'tool_call', timestamp: now - 890 + index * 12 })),
  { role: 'assistant', text: `**Comet Drift** is ready to play. You fly a little ship through a starfield and dodge comets.\n\nThe ship and the cover are in the project:\n\nMEDIA:${ROOT}/assets/sprites/ship.png\nMEDIA:${ROOT}/cover.png\n\nPossible next steps: a dash, a second level, music.`, timestamp: now - 700 }]
// Three builds: a report with what changed, an art edit (before / after), and a compile that failed.
const CARDS_HISTORY = [
  { role: 'user', text: 'Make a comet dodging game: a little ship, a starfield, comets to avoid.', timestamp: now - 1500 },
  { role: 'assistant', text: 'Planning it out first.', timestamp: now - 1498, tool_calls: [
    call('c1', 'skill_view', { name: 'hermretro:pixel-art' }), call('c2', 'chromatic_asset_import', { assetPath: 'assets/sprites/ship.png', kind: 'sprite' }),
    call('c3', 'chromatic_asset_import', { assetPath: 'assets/sprites/comet.png', kind: 'sprite' }), call('c4', 'chromatic_asset_import', { assetPath: 'assets/backgrounds/asteroid_belt.png', kind: 'background' }),
    call('c5', 'chromatic_scene_update', {}), call('c6', 'chromatic_actor_update', {}), call('c7', 'chromatic_rom_build', {}), call('c8', 'chromatic_emulator_step', {}), call('c9', 'chromatic_present_game', {}),
    call('c10', 'chromatic_build_report', { title: 'Comet Drift', summary: 'You fly a little ship through a starfield and dodge comets. Move with the D-pad.',
      changes: [{ kind: 'added', text: 'Ship sprite with an engine flicker', asset: 'assets/sprites/ship.png' }, { kind: 'added', text: 'Comets that drift down the screen', asset: 'assets/sprites/comet.png' },
        { kind: 'added', text: 'Asteroid belt background', asset: 'assets/backgrounds/asteroid_belt.png' }],
      tested: ['The ship moves in all 8 directions', 'Comets fall and wrap around', 'The camera stays put'], untested: ['Sound', 'A real Chromatic'],
      notes: ['Comets do not hurt the ship yet'], suggestions: ['Make the comets hurt', 'Add a score', 'Speed up over time'] })] },
  ...['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8', 'c9', 'c10'].map((id, index) => ({ role: 'tool', tool_call_id: id, name: 'tool_call', timestamp: now - 1490 + index * 9 })),
  { role: 'assistant', text: 'One thing you might notice: comets pass right through the ship. Want them to end the run?', timestamp: now - 1380 },
  { role: 'user', text: 'Make the ship chunkier, with a brighter engine.', timestamp: now - 600 },
  { role: 'assistant', text: '', timestamp: now - 598, tool_calls: [call('d1', 'chromatic_asset_import', { assetPath: 'assets/sprites/ship.png', kind: 'sprite' }), call('d2', 'chromatic_rom_build', {}),
    call('d3', 'chromatic_build_report', { title: 'Chunkier ship', summary: 'The ship is wider with a brighter engine. Same size, so it still fits its slot.',
      changes: [{ kind: 'changed', text: 'ship.png: wider hull, brighter engine', asset: 'assets/sprites/ship.png' }], tested: ['All 4 frames updated'], suggestions: ['A bit slimmer', 'Make the engine blue'] })] },
  ...['d1', 'd2', 'd3'].map((id, index) => ({ role: 'tool', tool_call_id: id, name: 'tool_call', timestamp: now - 560 + index * 20 })),
  { role: 'assistant', text: 'Here it is.', timestamp: now - 500 },
  { role: 'user', text: 'Add some calm background music.', timestamp: now - 200 },
  { role: 'assistant', text: '', timestamp: now - 198, tool_calls: [call('e1', 'chromatic_rom_build', {})] },
  { role: 'tool', tool_call_id: 'e1', name: 'tool_call', content: JSON.stringify({ ok: false, error: 'The song needs 9.1 KB but the cartridge bank has 6.7 KB left.' }), timestamp: now - 120 },
  { role: 'assistant', text: 'The music did not fit, so the build stopped. Nothing else changed: you are still playing build #2.', timestamp: now - 110 }]
const SNAPSHOTS = [{ id: String(Math.round((now - 540) * 1000)), at: Math.round((now - 540) * 1000) }, { id: String(Math.round((now - 1430) * 1000)), at: Math.round((now - 1430) * 1000) }]
const ASSET_LIST = [
  { path: `${ROOT}/cover.png`, name: 'Cover', kind: 'cover', modifiedAt: now - 700 },
  { path: `${ROOT}/assets/sprites/ship.png`, name: 'Ship', kind: 'sprite', modifiedAt: now - 800 },
  { path: `${ROOT}/assets/sprites/comet.png`, name: 'Comet', kind: 'sprite', modifiedAt: now - 800 },
  { path: `${ROOT}/assets/backgrounds/asteroid_belt.png`, name: 'Asteroid Belt', kind: 'background', modifiedAt: now - 800 }]
// ?long=1: a long conversation (200 turns of steps and replies), for checking it stays smooth.
const longHistory = () => {
  const rows = []
  for (let turn = 0; turn < 200; turn += 1) {
    const at = now - (200 - turn) * 600
    rows.push({ role: 'user', text: `Change number ${turn}: make the comets a little faster and add a sound when the ship dashes.`, timestamp: at })
    rows.push({ role: 'assistant', text: `Turn ${turn}: making **the comets** faster.\n\n- one\n- two`, timestamp: at + 2,
      tool_calls: Array.from({ length: 6 }, (_, step) => call(`l${turn}-${step}`, step === 5 ? 'chromatic_rom_build' : 'chromatic_scene_update', { name: `scene ${step}` })) })
    for (let step = 0; step < 6; step += 1) rows.push({ role: 'tool', tool_call_id: `l${turn}-${step}`, name: 'tool_call', timestamp: at + 10 + step * 5 })
    rows.push({ role: 'assistant', text: 'Done. Try it now and tell me how the dash feels.', timestamp: at + 60 })
  }
  return rows
}

// The model picker's list, shaped like `model.options` (names from a real install).
const caps = (list, extra = {}) => Object.fromEntries(list.map(model => [model, { reasoning: true, ...extra }]))
const MODEL_OPTIONS = { model: 'claude-opus-5-5[1m]', provider: 'claude-subscription-directsdk-experimental', providers: [
  { slug: 'claude-subscription-directsdk-experimental', name: 'Claude Subscription DirectSDK (Experimental)', authenticated: true, total_models: 7,
    models: ['claude-opus-5-5[1m]', 'claude-sonnet-5-5[1m]', 'claude-haiku-5-5[1m]', 'claude-opus-5[1m]', 'claude-sonnet-5[1m]', 'claude-opus-4-8[1m]', 'claude-haiku-4-5-20251001'],
    capabilities: caps(['claude-opus-5-5[1m]', 'claude-sonnet-5-5[1m]', 'claude-haiku-5-5[1m]', 'claude-opus-5[1m]', 'claude-sonnet-5[1m]', 'claude-opus-4-8[1m]', 'claude-haiku-4-5-20251001']) },
  { slug: 'openai-codex', name: 'ChatGPT or Codex Subscription', authenticated: true, total_models: 17,
    models: ['gpt-6.1-sol', 'gpt-6.1-sol-900k', 'gpt-6-astra', 'gpt-6-astra-900k', 'gpt-6.1-terra', 'gpt-6-sol'], capabilities: caps(['gpt-6.1-sol', 'gpt-6.1-sol-900k', 'gpt-6-astra', 'gpt-6-astra-900k', 'gpt-6.1-terra', 'gpt-6-sol'], { fast: true }) },
  { slug: 'anthropic', name: 'Anthropic', authenticated: true, total_models: 20, models: ['claude-fable-5-2', 'claude-opus-5-5', 'claude-sonnet-5'], capabilities: caps(['claude-fable-5-2', 'claude-opus-5-5', 'claude-sonnet-5']) },
  { slug: 'nous', name: 'Nous Portal', authenticated: true, total_models: 68, models: ['anthropic/claude-fable-5.2', 'anthropic/claude-opus-5.5', 'anthropic/claude-opus-5'], capabilities: caps(['anthropic/claude-fable-5.2', 'anthropic/claude-opus-5.5', 'anthropic/claude-opus-5']) }] }
function buildScenario(label, live, history = HISTORY) {
  const asking = live === 'ask'
  return {
    label,
    status: answered({ ...status(), via_profile: 'hermretro' }), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareSkipped: true }, player: playerAt,
    // Comet Drift has its Build conversation (the backend's binding); a New Game is still being set up.
    games: answered({
      games: GAMES.map((game, index) => (index === 0 ? { ...game, session: { storedId: 'st-comet', thisProfile: true, exists: true } } : game)),
      pending: [{ storedId: 'st-lamp', name: 'Lamplight', exists: true }],
      demo: DEMO, device: { hardwareEnabled: true, skipped: false }
    }),
    extra: { buildSelected: GAMES[0].id },
    rpc: {
      'session.resume': params => (params?.omit_messages
        ? { session_id: 'rt-comet', running: true, open_requests: asking ? [{ id: 'q-1', method: 'clarify', params: { questions: [
            { qid: 'q0', question: 'How should the comet tail look?', choices: ['Short flicker, 2 frames (Recommended)', 'Long trail, 4 frames', 'Sparks that fall off'] }] } }] : [] }
        : { session_id: 'rt-comet', running: false, info: { model: 'claude-opus-5-5[1m]', provider: 'claude-subscription-directsdk-experimental', reasoning_effort: 'high' },
            messages: new URLSearchParams(location.search).get('long') ? longHistory() : history }),
      'plugin.hermretro.asset': assetRpc,
      'plugin.hermretro.asset_info': assetInfoRpc,
      'plugin.hermretro.asset_restore': { ok: true },
      'plugin.hermretro.assets': { ok: true, root: ROOT, assets: ASSET_LIST },
      'plugin.hermretro.builds': { ok: true, builds: SNAPSHOTS },
      'plugin.hermretro.build_restore': { ok: true, restored: SNAPSHOTS[1].id },
      'model.options': MODEL_OPTIONS,
      'config.set': params => ({ key: params?.key, value: params?.value }),
      'prompt.submit': { ok: true }, 'session.interrupt': { ok: true }, 'session.create': { session_id: 'rt-new', stored_session_id: 'st-new' }
    },
    live
  }
}

export const SCENARIOS = {
  welcome: { label: '1 Welcome', status: answered(status(firstRun)), doctor: answered(doctor(false)), install: installed({ state: 'idle' }), storage: {} },
  review: { label: '2 Downloads', status: answered(status(firstRun)), doctor: answered(doctor(false)), install: installed({ state: 'idle' }), storage: { onboardStarted: true } },
  installing: { label: '3 Installing', status: answered(status(firstRun)), doctor: answered(doctor(false)), install: installed(RUNNING), storage: { onboardStarted: true } },
  failed: { label: '3 Failed', status: answered(status()), doctor: answered(doctor(false)), install: installed(FAILED), storage: { onboardStarted: true } },
  hardware: { label: '4 Chromatic?', status: answered(status()), doctor: answered(doctor(true)), install: installed({ state: 'done' }), storage: { onboardStarted: true } },
  make: { label: '5 First game', status: answered(status()), doctor: answered(doctor(true)), install: installed({ state: 'done' }), storage: { onboardStarted: true, hardwareSkipped: true } },
  profile: { label: 'Profile', status: answered(status({ profile: installer })), doctor: answered(doctor(false)), storage: { onboarded: true } },
  toolchain: { label: 'Toolchain', status: answered(status()), doctor: answered(doctor(false)), storage: { onboarded: true } },
  error: { label: 'Toolchain error', status: answered(status()), doctor: answered({ ok: false, error: 'toolchain_doctor did not answer within 30 s' }), storage: { onboarded: true } },
  choice: { label: 'Emulator or Chromatic', status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true } },
  devmode: { label: 'Developer Mode', status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareWanted: true, firmwareDone: true } },
  devicecli: { label: 'Device software', status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareWanted: true, firmwareDone: true, devmodeDone: true } },
  emulator: { label: 'Home (emulator only)', status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareSkipped: true } },
  complete: {
    label: 'Home (complete)',
    status: answered(status({ hardware_enabled: true, project: { name: 'MoonGarden', root: '~/games/MoonGarden' }, deps: { device_cli: cli('installed') } })),
    doctor: answered(doctor(true)),
    storage: { onboarded: true, hardwareWanted: true, firmwareDone: true, devmodeDone: true }
  },
  off: { label: 'Plugin off', status: notLoaded, doctor: { isPending: true }, storage: { onboarded: true } },
  studio: {
    label: 'Studio (games)',
    status: answered(status({ hardware_enabled: true, deps: { device_cli: cli('installed') } })),
    doctor: answered(doctor(true)),
    storage: { onboarded: true, hardwareWanted: true, firmwareDone: true, devmodeDone: true },
    games: library(),
    player: playerAt
  },
  emuonly: { label: 'Studio (emulator only)', status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareSkipped: true }, games: library(), player: playerAt },
  rebuilt: {
    label: 'Rebuilt',
    status: answered(status({ hardware_enabled: true, deps: { device_cli: cli('installed') } })),
    doctor: answered(doctor(true)),
    storage: { onboarded: true, hardwareWanted: true, firmwareDone: true, devmodeDone: true },
    games: library([{ ...GAMES[0], rom: { ...GAMES[0].rom, sha256: 'new' } }, ...GAMES.slice(1)]),
    player: playerAt
  },
  empty: { label: 'No games', status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareSkipped: true }, games: library([]), player: demoPlayer },
  build: buildScenario('Build (working)', 'working'),
  buildplay: buildScenario('Build (ready to play)', 'done'),
  buildask: buildScenario('Build (question)', 'ask'),
  buildphases: buildScenario('Build (phases and assets)', 'done', PHASED_HISTORY),
  buildcards: buildScenario('Build (build cards)', null, CARDS_HISTORY),
  buildnew: {
    label: 'Build (new game)',
    status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareSkipped: true }, games: library(), player: playerAt,
    extra: { buildSelected: 'new' }
  },
  old: { label: 'Old backend', status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareSkipped: true }, games: notLoaded, player: notLoaded }
}

const params = new URLSearchParams(location.search)
const chosen = SCENARIOS[params.get('s')] ?? SCENARIOS.welcome

// The app paints its palette at runtime (themes/context.tsx applyTheme), not from CSS: do the
// same with the default Nous skin, so both modes are the ones users see.
function applyNous(dark) {
  const preset = THEME_PRESET_PALETTES.nous
  const c = dark ? (preset.darkColors ?? preset.colors) : preset.colors
  const midground = c.midground ?? c.ring
  const vars = {
    '--theme-foreground': c.foreground,
    '--theme-primary': c.primary,
    '--theme-secondary': c.secondary,
    '--theme-accent-soft': c.accent,
    '--theme-midground': midground,
    '--theme-warm': c.primary,
    '--theme-background-seed': c.background,
    '--theme-sidebar-seed': c.sidebarBackground ?? c.background,
    '--theme-card-seed': c.card,
    '--theme-elevated-seed': c.popover,
    '--theme-bubble-seed': c.userBubble ?? c.popover,
    '--theme-mix-chrome': dark ? '74%' : '92%',
    '--theme-mix-sidebar': '100%',
    '--theme-mix-card': dark ? '38%' : '22%',
    '--theme-mix-elevated': dark ? '46%' : '28%',
    '--theme-mix-bubble': dark ? '46%' : '0%',
    '--dt-primary-foreground': c.primaryForeground,
    '--dt-border': c.border,
    '--dt-input': c.input,
    '--dt-ring': c.ring,
    '--dt-muted': c.muted
  }
  const root = document.documentElement

  root.classList.toggle('dark', dark)
  root.style.setProperty('color-scheme', dark ? 'dark' : 'light')
  for (const [key, value] of Object.entries(vars)) if (value) root.style.setProperty(key, value)
}

applyNous(params.get('mode') === 'dark')
preview.scenario.status = chosen.status
preview.scenario.doctor = chosen.doctor
preview.scenario.games = chosen.games ?? { isPending: true }
preview.scenario.install = chosen.install ?? installed({ state: 'idle' })
preview.scenario.player = chosen.player ?? { isPending: true }
preview.scenario.captures = answered({ captures: [] })
preview.scenario.models = answered(MODEL_OPTIONS)
if (chosen.rpc) preview.scenario.rpc = { 'plugin.hermretro.games': chosen.games?.data, ...chosen.rpc }

const registrations = []
const ctx = {
  registerMany: list => registrations.push(...list),
  setTimeout: (fn, ms) => {
    const id = setTimeout(fn, ms)

    return () => clearTimeout(id)
  },
  os: { writeClipboard: async () => true, openExternal: async url => console.log('open', url) },
  storage: {
    get: (key, fallback) => (key === 'setup' ? { ...chosen.storage } : key === 'page' ? (params.get('p') ?? fallback) : (chosen.extra?.[key] ?? fallback)),
    set: () => {}
  }
}

plugin.register(ctx)
const page = registrations.find(entry => entry.area === 'routes')
// ?view=side&w=480: the emulator tab beside the chat, opened the way the agent's chromatic_present_game opens it.
// ?player=<url> swaps the stand-in player for a real one (the backend's `player` RPC address).
const realPlayer = params.get('player')

if (realPlayer) {
  preview.scenario.player = answered({ url: realPlayer, romSha256: params.get('sha') ?? 'aa11', title: 'Comet Drift' })
}

if (params.get('view') === 'side' || params.get('view') === 'both') {
  const width = Number(params.get('w')) || 480
  const holder = document.getElementById('page')
  // view=both: the Studio page on the left, then a presentation opens the tab (which takes the live player).
  const left = params.get('view') === 'both' ? '<div id="left" style="flex:1;min-width:0;height:100%"></div>' : '<div style="flex:1;display:grid;place-items:center;color:var(--ui-text-quaternary);font:12px var(--dt-font-sans)">chat</div>'

  holder.style.display = 'flex'
  holder.innerHTML = `${left}<div id="side" style="width:${width}px;flex:none;height:100%;border-left:1px solid var(--ui-stroke-tertiary);background:var(--ui-bg-editor)"></div>`
  preview.scenario.rpc = { 'plugin.hermretro.games': chosen.games?.data ?? library().data }
  preview.onWorkspace = tab => {
    document.title = tab.title
    createRoot(document.getElementById('side')).render(jsx(tab.render, {}))
  }
  const present = () =>
    preview.emit({ type: 'tool.complete', session_id: 'rt-comet', payload: { name: 'chromatic_present_game', args: {}, result: { ok: true, studio: { gameId: GAMES[0].id, playerUrl: 'http://127.0.0.1/', title: GAMES[0].title, note: params.get('note') ?? 'Try the new double jump on the second ledge.', presentedAt: 1 }, message: 'Shown to the user beside the chat.' } } })

  if (params.get('view') === 'both') {
    createRoot(document.getElementById('left')).render(jsx(page.render, {}))
    setTimeout(present, 1500)
  } else {
    present()
  }
} else {
  createRoot(document.getElementById('page')).render(jsx(page.render, {}))

  // Build: the reply to the last message streams in, with steps and the art they make, like a live turn.
  if (chosen.live) {
    const at = (ms, type, payload, seq) => setTimeout(() => preview.emit({ type, session_id: 'rt-comet', seq, payload }), ms)
    const wrap = (name, args) => ({ name: 'tool_call', args: { calls: [{ name, arguments: args }] } })

    at(900, 'message.start', { turn_id: 'T9' }, 100)
    at(1000, 'message.delta', { text: 'Doubling the dash from 8 to 16 frames, then giving the comets ', turn_id: 'T9', segment: 0, offset: 0 }, 101)
    at(1100, 'message.delta', { text: 'a tail.', turn_id: 'T9', segment: 0, offset: 63 }, 102)
    at(1200, 'tool.start', { tool_id: 'x1', ...wrap('chromatic_engine_field_update', { name: 'dash_frames' }) }, 103)
    at(1300, 'tool.complete', { tool_id: 'x1', ...wrap('chromatic_engine_field_update', {}), summary: 'dash_frames 8 → 16', result: { ok: true }, duration_s: 1.4 }, 104)
    if (chosen.live === 'ask') {
      at(1400, 'tool.start', { tool_id: 'x2', name: 'clarify', args: { questions: [{ question: 'How should the comet tail look?' }] } }, 105)
    } else {
      at(1400, 'tool.start', { tool_id: 'x2', ...wrap('chromatic_asset_import', { assetPath: 'assets/sprites/comet.png', kind: 'sprite' }) }, 105)
      at(1500, 'tool.complete', { tool_id: 'x2', ...wrap('chromatic_asset_import', {}), result: { ok: true, structuredContent: { assetPath: 'assets/sprites/comet.png' } }, duration_s: 6 }, 106)
      at(1600, 'tool.start', { tool_id: 'x3', ...wrap('chromatic_rom_build', {}) }, 107)
    }

    // The turn ends: the game opens in the conversation with the agent's note.
    if (chosen.live === 'done') {
      at(1800, 'tool.complete', { tool_id: 'x3', ...wrap('chromatic_rom_build', {}), summary: 'Built the ROM', result: { ok: true }, duration_s: 38 }, 108)
      at(1900, 'tool.complete', { tool_id: 'x4', ...wrap('chromatic_present_game', {}), result: { ok: true, studio: { gameId: GAMES[0].id, title: GAMES[0].title, note: 'Dash is twice as long now: try it on the first comet wave.', presentedAt: 1 } } }, 109)
      at(2000, 'message.delta', { text: 'Ready: the dash is twice as long, and comets now trail fire.', turn_id: 'T9', segment: 1, offset: 0 }, 110)
      at(2100, 'message.complete', { text: '', status: 'complete' }, 111)
    }
  }
}

const bar = document.getElementById('bar')

for (const [id, scenario] of Object.entries(SCENARIOS)) {
  const link = document.createElement('a')

  link.textContent = scenario.label
  link.href = `?s=${id}&mode=${params.get('mode') ?? 'light'}${params.get('p') ? `&p=${params.get('p')}` : ''}`
  if (scenario === chosen) link.setAttribute('aria-current', 'page')
  bar.append(link)
}

const mode = document.createElement('a')

mode.textContent = params.get('mode') === 'dark' ? 'Light' : 'Dark'
mode.href = `?s=${params.get('s') ?? 'toolchain'}&mode=${params.get('mode') === 'dark' ? 'light' : 'dark'}${params.get('p') ? `&p=${params.get('p')}` : ''}`
mode.className = 'mode'
bar.append(mode)
