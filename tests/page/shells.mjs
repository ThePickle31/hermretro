// Shell fixtures for tests that render a page's own Page from page/ sources (slots.test.mjs's HOSTS, and any
// test like it), and the one way to find that Page once a page has tabs.
// The real shell is built in page/app/studio-page.js; registry.test.mjs/slots.test.mjs check each fixture here
// against it, so a field Home starts reading shows up as a failure, not as an undefined prop.
//   import { homeShell, ownPage } from './shells.mjs'
//   render(jsx(ownPage(pageOf('home')), { shell: homeShell({ games: answered({ games: [game] }) }) }))

/** A query result as the shell holds it (the stub's useQuery answer): `{ data, isFetching, isPending }`. */
export const answered = data => ({ data, isFetching: false, isPending: false })

const noop = () => {}

/** The page's own Page: `Page`, or its first tab's `Page` once the page is made of tabs. */
export function ownPage(page) {
  return page.Page ?? page.tabs[0].Page
}

/**
 * Every shell field Home reads (Home in page/pages/home/index.js), with the real shapes:
 * status, doctor and games are queries `{ data, ... }`; memory is the setup memory object `{}`; steps is the list
 * of setup steps `[]` (`{ id, complete, hardware? }`); auto is the next step or null, autoId its id (or 'ready' /
 * 'not-running' / 'choice'), choosing a boolean; go, openPrompt, play and setUpDevice are actions.
 * `overrides` replaces any of them.
 */
export function homeShell(overrides = {}) {
  return {
    auto: null,
    autoId: 'ready',
    choosing: false,
    ctx: { storage: { get: (key, fallback) => fallback, set: noop }, os: {} },
    doctor: answered({ ok: true, missing_required: [], components: [] }),
    games: answered({ games: [], device: { hardwareEnabled: false } }),
    memory: {},
    status: answered({ ok: true, hardware_enabled: false, profile: { name: 'hermretro', is_studio: true } }),
    steps: [],
    go: noop,
    openPrompt: noop,
    play: noop,
    setUpDevice: noop,
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
