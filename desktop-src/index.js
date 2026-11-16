/**
 * hermretro — Hermes Desktop half: the entry module.
 *
 * One full page (`/hermretro`) with a sidebar nav row and a ⌘K command.
 * One segmented control in its header switches between the pages
 * (docs/dev/STUDIO-PAGES.md is the contract with the backend):
 *   Home      hero, then Continue (last game or setup) / Start something / Studio.
 *   Build     one game, one conversation with the agent; the game plays inside the reply.
 *   Setup     the wizard driven by the `status` / `doctor` RPCs (game steps, then a
 *             choice between the emulator and a physical Chromatic, whose steps are
 *             optional), beside the flying Chromatic.
 *   Prompts   the Reader: prompt list, editable prompt, New chat / Add / Copy.
 *   Games     the shelf of real cartridges, from the `games` RPC.
 *   Emulator  ModRetro's real player in a SandboxedFrame (`player` RPC), kept
 *             loaded while other pages are shown.
 * Prompts only ever go into a chat composer; nothing is sent. The plugin adds no panes beside the chat
 * (the agent's work and the game live on the Build page).
 * When the agent presents a game (`chromatic_present_game`) the emulator opens in a workspace tab
 * right of the chat (`host.openWorkspace`, driven by `tool.complete` gateway events; builds open
 * nothing); one game runs at a time, in whichever of the page and the tab opened it last.
 *
 * This folder is the source: one small module per feature, in one level of folders. tools/bundle.mjs
 * bundles it into desktop/plugin.js, the plain ESM file the app loads; never edit that file.
 * UI is jsx()/jsxs() calls, and only sdk.js imports `@hermes/plugin-sdk`, `react` and
 * `react/jsx-runtime`. Runtime plugins are not scanned by the app's Tailwind build, so the page
 * carries its own scoped stylesheet (styles/, classes `cs-*`); every colour is a theme variable
 * (`var(--ui-*)`), so light, dark and every skin repaint it.
 * The artwork is the PNGs in art/, embedded as data URLs by the bundler.
 * Look at it with tests/desktop/preview/build.mjs (light and dark).
 */

import { host, jsx, PALETTE_AREA, ROUTES_AREA, SIDEBAR_NAV_AREA } from './sdk.js'
import { watchBuildChats } from './build-chat/events.js'
import { ID, ROUTE } from './core/ids.js'
import { StudioPage } from './shell/studio-page.js'
import { watchBuilds } from './side-emulator/present.js'

export default {
  id: ID,
  name: 'hermretro',
  register(ctx) {
    watchBuilds(ctx)
    watchBuildChats(ctx)
    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: ROUTE },
        render: () => jsx(StudioPage, { ctx })
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        order: 60,
        data: { codicon: 'game', label: 'hermretro', path: ROUTE }
      },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: {
          id: `${ID}.open`,
          label: 'hermretro: Open',
          keywords: ['chromatic', 'modretro', 'game boy', 'gbc', 'gb studio', 'rom', 'cartridge'],
          run: () => host.navigate(ROUTE)
        }
      }
    ])
  }
}
