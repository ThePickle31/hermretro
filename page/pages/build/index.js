// Build: the front door of the page (its descriptor; fields in app/registry.js), and what the Emulator page
// asks of it (is a session one of Build's conversations, which game is shown here, tool results unwrapped).
import { jsx } from '#sdk'
import { studioTarget } from '#app/routing.js'
import { ASSETS_CSS } from './assets/assets.css.js'
import { BUILD_RESPONSIVE_CSS } from './build-responsive.css.js'
import { BUILD_CSS } from './build.css.js'
import { BuildPage } from './build-page.js'
import { watchBuildChats } from './chat/events.js'
import { injectBuildDraft, notePresented } from './chat/store.js'
import { COMPOSER_CSS } from './composer/composer.css.js'
import { MENTIONS_CSS } from './composer/mentions.css.js'
import { MODEL_PICKER_CSS } from './composer/model-picker.css.js'
import { HEADER_CSS } from './header.css.js'
import { NEW_GAME_CSS } from './new-game.css.js'
import { INLINE_PLAYER_CSS } from './player/inline-player.css.js'
import { StudioNeeded } from './studio-needed.js'
import { BUILD_CARD_CSS } from './transcript/build-card.css.js'
import { CARDS_CSS } from './transcript/cards.css.js'
import { TRANSCRIPT_CSS } from './transcript/transcript.css.js'
import { WORKED_MODE_CSS } from './transcript/worked-mode.css.js'
import { WORKED_CSS } from './transcript/worked.css.js'
import { VIEWER_CSS } from './viewer/viewer.css.js'

export { buildShowing, isBuildSession } from './chat/store.js'
export { toolResultObject, unwrapCalls } from './chat/tool-results.js'

function Build({ shell }) {
  // Build chats run only in the hermretro profile: without it there is nothing to fall back to.
  return studioTarget()
    ? jsx(BuildPage, { ctx: shell.ctx, games: shell.gameList, loaded: Boolean(shell.games.data), onLibraryChanged: shell.gamesChanged, onPlay: shell.play, pendingGames: shell.games.data?.pending ?? [] }, 'build')
    : jsx(StudioNeeded, { status: shell.status }, 'studio-needed')
}

/** Make cover art on the Games shelf: open that game here with the request in its message box, not sent. */
function coverRequested({ game, prompt }, ctx) {
  try {
    ctx.storage.set('buildSelected', game.id)
  } catch {
    // this visit only
  }

  const own = game.session && game.session.thisProfile !== false && game.session.exists !== false

  injectBuildDraft(own ? game.session.storedId : '', prompt)
}

export const BUILD_PAGE = {
  id: 'build',
  label: 'Build',
  Page: Build,
  pad: 'build',
  css: [
    BUILD_CSS,
    NEW_GAME_CSS,
    TRANSCRIPT_CSS,
    WORKED_CSS,
    ASSETS_CSS,
    VIEWER_CSS,
    INLINE_PLAYER_CSS,
    CARDS_CSS,
    COMPOSER_CSS,
    MODEL_PICKER_CSS,
    BUILD_CARD_CSS,
    HEADER_CSS,
    WORKED_MODE_CSS,
    MENTIONS_CSS,
    BUILD_RESPONSIVE_CSS
  ],
  // After every other page's rules: the inline player overrides the Emulator page's stage rules.
  cssLast: true,
  register: watchBuildChats,
  listens: {
    'games.coverRequested': coverRequested,
    'emulator.presented': presentation => notePresented(presentation)
  }
}
