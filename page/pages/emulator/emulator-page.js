// The Emulator page's own Page: the bar above the shell's player and the notice under it. Its own file (not
// index.js) so a tab can import it (python tools/retrodev new tab emulator <id> --from-page).
import { jsx } from '#sdk'
import { PlayerNotice } from '#app/player/stage.js'
import { EmulatorBar } from './emulator-bar.js'

export function Emulator({ shell }) {
  const { ctx, go, hardwareOn, player } = shell

  // Always the player: the user's game, or the demo cartridge when there is nothing of theirs to play.
  return [
    jsx(
      EmulatorBar,
      {
        capturesOpen: player.capturesOpen,
        ctx,
        focused: player.focused,
        game: player.game,
        go,
        hardwareOn,
        onAsk: player.ask,
        onFull: player.fullScreen,
        onLater: player.later,
        onReload: player.reload,
        onToggleCaptures: player.toggleCaptures,
        player: player.query,
        rebuilt: player.rebuilt
      },
      'bar'
    ),
    jsx(PlayerNotice, { game: player.game, onRefresh: player.refresh, player: player.query, refreshing: player.query.isFetching }, 'notice')
  ]
}
