// Build's own Page: the Build page, or what it needs first when there is no hermretro profile. Its own file (not
// index.js) so a tab can import it.
import { jsx } from '#sdk'
import { studioTarget } from '#app/routing.js'
import { BuildPage } from './build-page.js'
import { StudioNeeded } from './studio-needed.js'

export function Build({ shell }) {
  // Build chats run only in the hermretro profile: without it there is nothing to fall back to.
  if (!studioTarget()) {
    return jsx(StudioNeeded, { status: shell.status }, 'studio-needed')
  }
  return jsx(BuildPage, {
    ctx: shell.ctx,
    games: shell.gameList,
    loaded: Boolean(shell.games.data) && !shell.games.isError,
    libraryError: shell.libraryError,
    localPending: shell.buildPending,
    changePending: shell.changeBuildPending,
    onLibraryChanged: shell.gamesChanged,
    onSelect: shell.selectBuild,
    pendingGames: shell.games.data?.pending ?? [],
    playerVisit: shell.buildPlayer,
    selection: shell.buildSelection,
    unavailable: shell.games.data?.unavailable,
    updating: shell.pluginUpdate?.phase === 'updating'
  }, 'build')
}
