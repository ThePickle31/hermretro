// Emulator: the front door of the page (its descriptor; fields in app/registry.js). The player itself is the
// shell's (it stays loaded while other pages are shown); this page adds the bar above it, the notice, the row
// under it, and the emulator tab beside the chat that opens when the agent presents a game.
import { jsx } from '#sdk'
import { SideEmulatorRow } from './beside-chat/row.js'
import { watchBuilds } from './beside-chat/present.js'
import { Emulator } from './emulator-page.js'
import { EMULATOR_CSS } from './emulator.css.js'

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
    'emulator.barActions':
      "Buttons in the bar above the player, after the keyboard light, for the user's own game (not the demo). Rendered on the Emulator page and in the emulator tab beside the chat. Props: { ctx, game, hardwareOn }, plus go(pageId) on the Emulator page only (beside the chat there is no shell: check go before using it)."
  }
}
