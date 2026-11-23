// ModRetro's real player in a sandboxed frame, and what is shown when it cannot run.
import { Button, Codicon, jsx, jsxs, SandboxedFrame } from '#sdk'
import { describeRequestError, studioError } from '#app/backend.js'
import { sendToGameChat } from '#app/chat-insert.js'
import { buildPrompt } from '#app/game-prompts.js'
import { DEMO_ID } from '#app/ids.js'
import { AsyncButton } from '#shared/ui/page.js'
import { Lede } from '#shared/ui/text.js'
import { Working } from '#shared/ui/working.js'

/** The ROM the player would load now: the web export's own (its ROM is a separate compilation, not the
 *  native build's bytes), else the last build for a backend that predates `web`. */
export function playableSha(game) {
  return game?.web === undefined ? game?.rom?.sha256 ?? null : game.web?.sha256 ?? null
}

/** Why the player RPC failed, worded for the person looking at the page; null while it has not. */
function playerFailure(game, player) {
  if (player?.isError) {
    return describeRequestError(player.error).notLoaded
      ? 'This profile is running an older copy of the hermretro backend. Reload the plugin (Capabilities › Plugins, switch it off and on) and press Refresh.'
      : studioError(player.error, 'run the player')
  }

  // A user's game without a web build keeps its own message (with "Build it in chat") in the stage.
  return game?.id === DEMO_ID && player?.data?.error ? String(player.data.error) : null
}

export function PlayerNotice({ game, gameError, player, onRefresh, refreshing }) {
  const reason = gameError || playerFailure(game, player)

  if (!reason) {
    return null
  }

  return jsxs('div', {
    className: 'cs-rp-note',
    role: 'alert',
    children: [
      jsxs('div', { children: [jsx('b', { children: 'The player could not start' }), jsx('span', { children: reason })] }),
      jsxs(Button, { disabled: refreshing, onClick: onRefresh, size: 'sm', variant: 'outline', children: [jsx(Codicon, { name: 'refresh', size: 14 }), 'Refresh'] })
    ]
  })
}

/** `query` (e.g. `view=screen&color=hermes-midnight`) is added to the player's URL when the frame loads. */
export function PlayerStage({ game, gameError, player, visible, frameRef, stageRef, frameKey, onLoad, ctx, query = '' }) {
  let inner = null

  if (game) {
    const data = player?.data

    if (playerFailure(game, player)) {
      inner = jsx('div', { 'aria-hidden': true, className: 'cs-rp-void' })
    } else if (data?.error) {
      inner = jsxs('div', {
        className: 'cs-rp-msg',
        children: [
          jsx('p', { className: 'cs-eyebrow', children: 'The player could not start' }),
          jsx(Lede, { children: data.error }),
          jsx(AsyncButton, { icon: 'comment-discussion', run: () => sendToGameChat(ctx, game, buildPrompt(game)), variant: 'default', children: 'Build it in chat' })
        ]
      })
    } else if (data?.url) {
      inner = jsx(
        SandboxedFrame,
        { onLoad, ref: frameRef, sandbox: 'allow-scripts allow-downloads', src: query ? `${data.url}?${query}` : data.url, title: `${game.title} in ModRetro's Chromatic player` },
        frameKey
      )
    } else {
      inner = jsx('div', { className: 'cs-rp-msg', children: jsx(Working, { children: `Starting the player for ${game.title}…` }) })
    }
  } else if (!gameError) {
    inner = jsx('div', { className: 'cs-rp-msg', children: jsx(Working, { quiet: true, children: 'Reading your games…' }) })
  }

  return jsx('div', { 'aria-hidden': visible ? undefined : true, className: visible ? 'cs-rp-stage' : 'cs-rp-stage off', ref: stageRef, children: inner })
}

/** Where the live player is, shown by the surface that does not have it. */
export function PlayerAway({ where, onBring }) {
  return jsx('div', {
    className: 'cs-rp-stage',
    children: jsxs('div', {
      className: 'cs-rp-msg cs-rp-away',
      children: [
        jsx('p', { className: 'cs-eyebrow', children: where }),
        jsx(Lede, { children: 'The game runs in one place at a time. Bringing it here starts it again from the title screen.' }),
        jsxs(Button, { onClick: onBring, size: 'sm', variant: 'default', children: [jsx(Codicon, { name: 'arrow-swap', size: 14 }), 'Bring it here'] })
      ]
    })
  })
}
