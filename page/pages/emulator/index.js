// Emulator: the front door of the page (its descriptor; fields in app/registry.js). The player itself is the
// shell's (it stays loaded while other pages are shown); this page adds the bar above it, the notice, the row
// under it, and the emulator tab beside the chat that opens when the agent presents a game.
import { jsx } from '#sdk'
import { PlayerNotice } from '#app/player/stage.js'
import { SideEmulatorRow } from './beside-chat/row.js'
import { watchBuilds } from './beside-chat/present.js'
import { EmulatorBar } from './emulator-bar.js'
import { EMULATOR_CSS } from './emulator.css.js'

function Emulator({ shell }) {
  const { ctx, hardwareOn, player } = shell

  // Always the player: the user's game, or the demo cartridge when there is nothing of theirs to play.
  return [
    jsx(
      EmulatorBar,
      {
        capturesOpen: player.capturesOpen,
        ctx,
        focused: player.focused,
        game: player.game,
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

function BelowPlayer({ shell }) {
  return jsx(SideEmulatorRow, { ctx: shell.ctx, game: shell.player.game })
}

/** The live dot on the Emulator segment while a game is loaded and another page is shown. */
function EmulatorBadge({ nav }) {
  return nav.playing && nav.page !== 'emulator' ? jsx('i', { 'aria-label': 'a game is loaded', className: 'live', role: 'img' }) : null
}

export const EMULATOR_PAGE = {
  id: 'emulator',
  label: 'Emulator',
  Page: Emulator,
  Badge: EmulatorBadge,
  pad: 'flush',
  BelowPlayer,
  css: [EMULATOR_CSS],
  register: watchBuilds,
  events: {
    'emulator.presented':
      'The agent presented a game (chromatic_present_game): { gameId, seq, note, t }. seq counts presentations of that game; the Build page plays it in its conversation.'
  },
  slots: {
    'emulator.barActions': "Buttons in the bar above the player, after the keyboard light, for the user's own game (not the demo). Props: { ctx, game, hardwareOn }."
  }
}
