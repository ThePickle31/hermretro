// Games: the front door of the page (its descriptor; fields in app/registry.js), what other pages use from
// the library model, and the Install button it puts into the Emulator page's bar.
import { GAMES_CSS } from './games.css.js'
import { Games, InstallButton } from './games-page.js'

export { GAME_STATES, gameMeta, latestGame } from './model.js'
export { StateTag } from './state-tag.js'

export const GAMES_PAGE = {
  id: 'games',
  label: 'Games',
  Page: Games,
  css: [GAMES_CSS],
  events: {
    'games.coverRequested': 'Make cover art (or Finish card) was picked for a game: { game, prompt }. The game opens on Build with the prompt in its message box, not sent.'
  },
  slots: {
    'games.cardMenu':
      "Extra items at the end of a game's arrow menu on the shelf. Props: { ctx, game, hardwareOn, item(icon, label, run, { disabled, why }) }; return item(...) for a menu button."
  },
  contributes: {
    'emulator.barActions': [InstallButton]
  }
}
