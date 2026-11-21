// Shell fixtures for tests that render a page's own Page from page/ sources (slots.test.mjs's HOSTS, and any
// test like it), and the one way to find that Page once a page has tabs.
// The real shell is built in page/app/studio-page.js; slots.test.mjs checks pageShell() against it (the same
// fields, each with the same kind of value), so a field the shell gains or a page starts reading shows up as a
// failure, not as an undefined prop.
//   import { pageShell, ownPage } from './shells.mjs'
//   render(jsx(ownPage(pageOf('games')), { shell: pageShell({ games: answered({ games: [game] }) }) }))

/** A query result as the shell holds it (the stub's useQuery answer): `{ data, isFetching, isPending }`. */
export const answered = data => ({ data, isFetching: false, isPending: false })

const noop = () => {}

/** The page's own Page: `Page`, or its first tab's `Page` once the page is made of tabs. */
export function ownPage(page) {
  return page.Page ?? page.tabs[0].Page
}

/**
 * Every field of the real shell (page/app/studio-page.js), with the real shapes, as a page gets it on a ready studio:
 * status, doctor, games and install are queries `{ data, ... }`; backend ('ok' when running) and gateway are
 * strings; viaProfile is the profile the page's queries go to, or null when it is the app's; memory is the setup
 * memory object `{}`; steps is the list of setup steps `[]` (`{ id, complete, hardware? }`) and gameList the games;
 * auto and shown are a step or null, autoId the next step's id (or 'ready' / 'not-running' / 'choice'), choosing a
 * boolean; pluginUpdate is the update state (app/update/use-update.js, nothing ready); player is the shell's one player (`{ game, query, ... }`); go, play, setUpDevice and the
 * other functions are actions. `overrides` replaces any of them.
 */
export function pageShell(overrides = {}) {
  return {
    ctx: { storage: { get: (key, fallback) => fallback, set: noop }, os: {} },
    page: 'games',
    go: noop,
    refresh: noop,
    refreshing: false,
    backend: 'ok',
    doctor: answered({ ok: true, missing_required: [], components: [] }),
    gateway: 'open',
    status: answered({ ok: true, hardware_enabled: false, profile: { name: 'hermretro', is_studio: true } }),
    viaProfile: null,
    steps: [],
    memory: {},
    update: noop,
    auto: null,
    autoId: 'ready',
    choosing: false,
    shown: null,
    pick: noop,
    unpin: noop,
    install: { isFetching: false, isPending: true },
    pluginUpdate: { visible: false, ready: false, checked: false, linked: false, phase: 'idle', step: 0, error: null, review: null,
      version: null, open: false, setOpen: noop, start: noop, agree: noop, cancel: noop, later: noop, whatsNew: noop, openPlugins: noop },
    hardwareOn: false,
    emulatorOnly: false,
    setUpDevice: noop,
    games: answered({ games: [], device: { hardwareEnabled: false } }),
    gameList: [],
    gamesChanged: noop,
    play: noop,
    player: {
      game: null,
      query: answered(null),
      focused: false,
      rebuilt: false,
      capturesOpen: false,
      ask: noop,
      fullScreen: noop,
      later: noop,
      reload: noop,
      refresh: noop,
      toggleCaptures: noop
    },
    ...overrides
  }
}

/** The kind of value a shell field holds, for comparing a fixture with the real shell. */
export function shapeOf(value) {
  if (Array.isArray(value)) return 'list'
  if (typeof value === 'function') return 'action'
  if (value && typeof value === 'object') return 'data' in value || 'isFetching' in value || 'isError' in value ? 'query' : 'object'
  return value === null ? 'empty' : typeof value
}
