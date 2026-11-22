// Names every part of the page shares: the plugin id, its route, the studio profile, links.
export const ID = 'hermretro'
export const ROUTE = '/hermretro'

// The built-in demo cartridge (ModRetro's hello-color example in GB Studio's player). The Emulator
// page plays it whenever the library has nothing playable, so the real player is always on screen.
export const DEMO_ID = 'demo'
export const DEMO_GAME = { id: DEMO_ID, title: 'Hello Color', kind: 'gbdk', note: 'ModRetro example' }

// hermretro works in its own Hermes profile; the first setup step creates it.
export const STUDIO_PROFILE = 'hermretro'
export const ENABLE_COMMAND = `hermes plugins enable ${ID}`

// The agent half's `config_schema` form lives under Settings ▸ Plugins keyed by
// the agent plugin key (`?agent=`). `pluginSettingsHref()` builds `?plugin=`,
// which addresses pages a DESKTOP half registers — this desktop half registers
// none, so the agent route is the right deep link (it also resolves when the
// form is folded under a desktop entry as "Agent settings"). `&profile=` is Settings' own scope hand-off (the
// Capabilities gear's): the form edits the hermretro profile, where the hardware tools are, even while the app is on
// another profile. A Hermes without it ignores the parameter and edits the profile the app is on.
export const AGENT_SETTINGS_HREF = `/settings?tab=plugins&agent=${ID}&profile=${STUDIO_PROFILE}`
export const PLUGINS_HREF = `/capabilities?tab=plugins&plugin=${ID}`

// A chat with the agent, one game per conversation. Each reply folds its steps into "Worked for…"
// (open while it works), shows the art it makes as it lands, and ends with the game to play right in
// the conversation once the agent has finished.
export const AGENT = 'HermRetro'
