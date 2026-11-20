// The shared starting state of the Games, Prompts and Emulator scenarios (page-games, page-prompts, page-emulator,
// page-emulator-side .test.mjs): the studio left as the studio-profile scenarios leave it, a library of four games
// fed by the games RPC, the studio page mounted and Refresh pressed. Each file navigates to its own page from here.
//   const { games, now2, studio } = await gamesStudio(helpers)   // helpers: what runScenario hands the scenario
// Comet Drift and Old Orbit carry a `card` in the real shape (docs/dev/CONTRACT.md, "The game object";
// game_card.public()): Comet Drift's is complete with genres and controls, Old Orbit's is still missing its cover.
// The RPC order (Comet Drift, Robo Run, Ace Arena, Old Orbit), the most recently built order (Comet Drift, Old Orbit,
// then the unbuilt ones) and A-Z (Ace Arena first) all differ, so a test can tell which order a page uses: find a
// game's card by its title, not its position.

/** The four library games the scenarios use (Comet Drift ready with a chat and a full card, Robo Run failed with no
 *  card, Ace Arena never built, Old Orbit older with an unfinished card). */
export function libraryGames(now2) {
  return [
    { id: 'aaa111aaa111', title: 'Comet Drift', projectRoot: '/home/u/ChromaticGames/CometDrift', kind: 'gbstudio', state: 'ready',
      rom: { path: '/home/u/ChromaticGames/CometDrift/build/web/rom/game.gbc', sha256: 'sha-one', size: 262144, builtAt: now2 - 120 },
      webExport: true, thumb: 'data:image/png;base64,AAAA', chat: { sessionId: 'stored-comet', title: 'Comet Drift — first level' }, error: null,
      card: { title: 'Comet Drift', tagline: 'Dodge, boost, survive.', description: 'Steer a comet through an asteroid field.', about: null,
        genres: ['Arcade', 'Shooter'], tags: ['space'], controls: { A: 'Boost', 'D-Pad': 'Steer' },
        complete: true, missing: [], hasCover: true, coverForBuild: 'sha-one' } },
    { id: 'bbb222bbb222', title: 'Robo Run', projectRoot: '/home/u/ChromaticGames/RoboRun', kind: 'gbdk', state: 'failed', rom: null,
      webExport: false, thumb: null, chat: null, error: 'background uses 212 tiles (limit 192)' },
    { id: 'ddd444ddd444', title: 'Ace Arena', projectRoot: '/home/u/ChromaticGames/AceArena', kind: 'gbstudio', state: 'unbuilt', rom: null,
      webExport: false, thumb: null, chat: null, error: null },
    { id: 'ccc333ccc333', title: 'Old Orbit', projectRoot: '/home/u/ChromaticGames/OldOrbit', kind: 'gbstudio', state: 'ready', // built first:
      rom: { path: '/o.gbc', sha256: 'sha-old', size: 1, builtAt: now2 - 900 }, webExport: true, thumb: null, chat: null, error: null, // Home skips it
      card: { title: 'Old Orbit', tagline: null, description: null, about: null, genres: ['Puzzle'], tags: [], controls: {},
        complete: false, missing: ['tagline', 'description', 'cover'], hasCover: false, coverForBuild: null } }
  ]
}

/** Set the scenario up, mount the studio page and press Refresh; returns { games, now2, studio }. */
export async function gamesStudio({ scenario, page, mount, click, answered, doctor, installAnswer, complete }) {
  // Where the studio-profile scenarios leave the app: the active profile has the plugin but is not the studio,
  // a hermretro route is known, and the profile RPCs still answer (Refresh below forgets the route).
  scenario.ambient = { ...complete, profile: { name: 'default', is_studio: false,
    create: { name: 'hermretro', description: 'hermretro', no_skills: true, share_auth: true, no_alias: true },
    studio: { name: 'hermretro', exists: true, installed: false, ours: false } } }
  scenario.routes = [{ profile: 'default', connectionId: 'local' }, { profile: 'hermretro', targetProfile: 'hermretro', connectionId: 'local' }]
  scenario.byProfile = {}
  scenario.byMethod['profiles.create'] = { ok: true, name: 'hermretro' }
  scenario.byMethod['plugin.hermretro.studio_profile'] = { ok: false, code: 'NAME_TAKEN', error: 'A profile named hermretro already exists and was not made by hermretro.' }
  scenario.install = installAnswer({ state: 'idle' })

  // Games, Prompts and the Emulator, fed by the games / player RPCs (docs/dev/STUDIO-PAGES.md).
  scenario.status = answered({ ...complete, hardware_enabled: false }); scenario.doctor = answered(doctor([]))
  scenario.storage = { setup: { hardwareSkipped: true } }
  const now2 = Math.round(Date.now() / 1000)
  const games = libraryGames(now2)
  scenario.games = answered({ games, gamesDir: '/home/u/.hermes/hermretro/games', device: { hardwareEnabled: true, skipped: false } })
  scenario.player = { isPending: true }
  const studio = await mount(page)
  await click('Refresh') // forget the profile route left over from the cases above
  return { games, now2, studio }
}
