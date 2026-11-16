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
  deps: { inside_plugin: true, toolchain_root: '~/.hermes/profiles/hermretro/plugins/hermretro/deps/toolchain', device_cli: cli('missing') },
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
    thumb: 'thumbs/comet.png', chat: { sessionId: 'st-comet', title: 'Comet Drift — dodge the comets' }, error: null },
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
const library = (list = GAMES) => answered({ games: list, demo: DEMO, device: { hardwareEnabled: true, skipped: false } })
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
const installed = install => answered({ ok: true, manifest: MANIFEST, root: '~/.hermes/profiles/default/plugins/hermretro/deps/toolchain', install })
const RUNNING = { state: 'running', started_at: 1, fraction: 0.4, downloaded_bytes: 281_000_000, current: 'cli', run: { components: {
  gbdk: { state: 'done', version: '4.5.0', checks: [{ file: 'gbdk-linux64.tar.gz', sha256: 'd7857a5f6d135ee4', reused: false }] },
  cli: { state: 'running', checks: [] } } } }
const FAILED = { state: 'failed', started_at: 1, error: 'cli: yarn install: getaddrinfo ENOTFOUND registry.npmjs.org', run: { components: {
  gbdk: { state: 'done', version: '4.5.0', checks: [{ file: 'gbdk-linux64.tar.gz', sha256: 'd7857a5f6d135ee4', reused: false }] },
  cli: { state: 'failed', error: 'yarn install: getaddrinfo ENOTFOUND registry.npmjs.org', checks: [] } } } }
const firstRun = { profile: { ...{ name: 'default', is_studio: false, create: {}, studio: { exists: false, installed: false } } } }

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
    status: answered(status({ hardware_enabled: true, project: { name: 'MoonGarden', root: '~/games/MoonGarden' }, deps: { inside_plugin: true, device_cli: cli('installed') } })),
    doctor: answered(doctor(true)),
    storage: { onboarded: true, hardwareWanted: true, firmwareDone: true, devmodeDone: true }
  },
  off: { label: 'Plugin off', status: notLoaded, doctor: { isPending: true }, storage: { onboarded: true } },
  studio: {
    label: 'Studio (games)',
    status: answered(status({ hardware_enabled: true, deps: { inside_plugin: true, device_cli: cli('installed') } })),
    doctor: answered(doctor(true)),
    storage: { onboarded: true, hardwareWanted: true, firmwareDone: true, devmodeDone: true },
    games: library(),
    player: playerAt
  },
  emuonly: { label: 'Studio (emulator only)', status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareSkipped: true }, games: library(), player: playerAt },
  rebuilt: {
    label: 'Rebuilt',
    status: answered(status({ hardware_enabled: true, deps: { inside_plugin: true, device_cli: cli('installed') } })),
    doctor: answered(doctor(true)),
    storage: { onboarded: true, hardwareWanted: true, firmwareDone: true, devmodeDone: true },
    games: library([{ ...GAMES[0], rom: { ...GAMES[0].rom, sha256: 'new' } }, ...GAMES.slice(1)]),
    player: playerAt
  },
  empty: { label: 'No games', status: answered(status()), doctor: answered(doctor(true)), storage: { onboarded: true, hardwareSkipped: true }, games: library([]), player: demoPlayer },
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

const registrations = []
const ctx = {
  registerMany: list => registrations.push(...list),
  setTimeout: (fn, ms) => {
    const id = setTimeout(fn, ms)

    return () => clearTimeout(id)
  },
  os: { writeClipboard: async () => true, openExternal: async url => console.log('open', url) },
  storage: { get: (key, fallback) => (key === 'setup' ? { ...chosen.storage } : key === 'page' ? (params.get('p') ?? fallback) : fallback), set: () => {} }
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
