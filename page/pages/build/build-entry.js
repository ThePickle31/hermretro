// Build's own Page: the Build page, or what it needs first when there is no hermretro profile. Its own file (not
// index.js) so a tab can import it (python tools/retrodev new tab build <id> --from-page).
import { jsx } from '#sdk'
import { studioTarget } from '#app/routing.js'
import { BuildPage } from './build-page.js'
import { StudioNeeded } from './studio-needed.js'

export function Build({ shell }) {
  // Build chats run only in the hermretro profile: without it there is nothing to fall back to.
  return studioTarget()
    ? jsx(BuildPage, { ctx: shell.ctx, games: shell.gameList, loaded: Boolean(shell.games.data), onLibraryChanged: shell.gamesChanged, onPlay: shell.play, pendingGames: shell.games.data?.pending ?? [] }, 'build')
    : jsx(StudioNeeded, { status: shell.status }, 'studio-needed')
}
