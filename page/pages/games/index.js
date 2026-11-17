// Games: the front door of the page (its descriptor; fields in app/registry.js), what other pages use from
// the library model, and the Install button it puts into the Emulator page's bar.
import { jsx } from '#sdk'
import { emit } from '#app/events.js'
import { COVER_PROMPT } from './game-card.js'
import { GAMES_CSS } from './games.css.js'
import { GamesPage, InstallButton } from './games-page.js'

export { GAME_STATES, gameMeta, latestGame } from './model.js'
export { StateTag } from './state-tag.js'

function Games({ shell }) {
  return jsx(GamesPage, {
    ctx: shell.ctx,
    games: shell.games,
    hardwareOn: shell.hardwareOn,
    // Make cover art: the request goes into that game's Build conversation (Build listens), not sent.
    onMakeCover: game => {
      emit('games.coverRequested', { game, prompt: COVER_PROMPT })
      shell.go('build')
    },
    onOpenPrompt: shell.openPrompt,
    onPlay: shell.play,
    onSetUpDevice: shell.setUpDevice
  })
}

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
