// One cartridge on the Games shelf, with its actions.
import { Codicon, host, jsx, jsxs, Tip, useEffect, useRef, useState } from '#sdk'
import { openGameChat, sendToGameChat } from '#app/chat-insert.js'
import { buildPrompt } from '#app/game-prompts.js'
import { AGENT } from '#app/ids.js'
import { Slot } from '#app/slots.js'
import { Cartridge } from './cartridge.js'
import { fixPrompt, gameMeta, installPrompt } from './model.js'

export const COVER_PROMPT =
  'Make this game\u2019s card: draw a 160x144 pixel-art cover in the game\u2019s own palette and write its tagline, description and genres, with chromatic_game_info.'

const GAME_STATUS = {
  ready: ['good', 'Ready'],
  changed: ['warn', 'Changed'],
  failed: ['bad', 'Build failed'],
  unbuilt: ['quiet', 'Not built']
}

/** The one action a game needs next: Play, or Build & play / Fix in chat / Build in chat. */
function primaryAction(ctx, game, onPlay) {
  if (game.state === 'failed') {
    return { icon: 'tools', label: 'Fix in chat', tone: 'outline', title: 'Puts the build error in its chat, not sent', run: () => sendToGameChat(ctx, game, fixPrompt(game)) }
  }

  if (game.state === 'unbuilt') {
    return { icon: 'play', label: 'Build in chat', title: 'Puts a build prompt in its chat, not sent', run: () => sendToGameChat(ctx, game, buildPrompt(game)) }
  }

  if (game.state === 'changed') {
    return { icon: 'play', label: 'Build & play', title: `Edited since its last build: puts a build prompt in its chat, not sent. ${AGENT} shows it beside the chat when it is built.`, run: () => sendToGameChat(ctx, game, buildPrompt(game)) }
  }

  return { icon: 'play', label: 'Play', title: `Play ${game.displayTitle || game.title} on the Emulator page`, run: () => onPlay(game.id) }
}

async function revealGame(ctx, game) {
  const path = game.projectRoot
  const shown = await ctx.os?.revealPath?.(path).catch(() => false)

  if (!shown) {
    const copied = await ctx.os?.writeClipboard?.(path).catch(() => false)

    host.notify({ kind: 'info', message: copied ? 'The game is on the computer running Hermes. Its folder path is copied.' : path })
  }
}

/** A1 "split Play": the game's next action and, behind the arrow, everything else it can do. */
function GameActions({ ctx, game, hardwareOn, onPlay, onMakeCover }) {
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState(false)
  const wrap = useRef(null)
  const title = game.displayTitle || game.title
  const action = primaryAction(ctx, game, onPlay)
  const built = game.state !== 'failed' && game.state !== 'unbuilt'
  const card = game.card ?? null

  useEffect(() => {
    if (!open) {
      return undefined
    }

    const items = () => [...(wrap.current?.querySelectorAll?.('.cs-gmenu button:not(:disabled)') ?? [])]
    const onDown = event => {
      if (wrap.current && !wrap.current.contains(event.target)) {
        setOpen(false)
      }
    }
    const onKey = event => {
      if (event.key === 'Escape') {
        setOpen(false)
        wrap.current?.querySelector('.cs-split .caret')?.focus?.()
      } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        const list = items()
        const at = list.indexOf(document.activeElement)

        event.preventDefault()
        list[(at + (event.key === 'ArrowDown' ? 1 : list.length - 1)) % list.length]?.focus?.()
      }
    }

    items()[0]?.focus?.()
    window.addEventListener('mousedown', onDown)
    window.addEventListener('keydown', onKey)

    return () => {
      window.removeEventListener('mousedown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  const run = async fn => {
    setOpen(false)
    setPending(true)

    try {
      await fn()
    } finally {
      setPending(false)
    }
  }

  const item = (icon, label, fn, { disabled = false, why } = {}) =>
    jsxs(
      'button',
      {
        disabled,
        onClick: () => void run(fn),
        role: 'menuitem',
        title: why,
        type: 'button',
        children: [jsx(Codicon, { name: icon, size: 13 }), jsx('span', { children: label }), why && disabled ? jsx('em', { children: why }) : null]
      },
      label
    )

  const rows = [
    game.state === 'changed' && game.webExport ? item('play', 'Play last build', () => onPlay(game.id)) : null,
    built
      ? item('desktop-download', 'Install on Chromatic', () => sendToGameChat(ctx, game, installPrompt(game)), {
          disabled: !hardwareOn || !game.rom,
          why: !hardwareOn ? 'Needs your Chromatic' : !game.rom ? 'Build it first' : "Puts the flash prompt in its chat; Hermes asks before writing"
        })
      : null,
    item('comment-discussion', 'Open its chat', () => openGameChat(game), { disabled: !game.chat && !game.session, why: game.chat ? game.chat.title || undefined : game.session ? undefined : 'No chat recorded' }),
    !card?.complete && onMakeCover ? item('sparkle', game.cover ? 'Finish card' : 'Make cover art', () => onMakeCover(game)) : null,
    game.projectRoot ? item('folder-opened', 'Show in folder', () => revealGame(ctx, game)) : null,
    // What other pages add to this menu (games/index.js declares the slot).
    jsx(Slot, { name: 'games.cardMenu', props: { ctx, game, hardwareOn, item } }, 'more')
  ].filter(Boolean)

  return jsxs('div', {
    className: 'cs-split',
    ref: wrap,
    children: [
      jsx(Tip, {
        label: action.title,
        children: jsxs('button', {
          className: `main ${action.tone ?? 'solid'}`,
          disabled: pending,
          onClick: () => void run(action.run),
          type: 'button',
          children: [jsx(Codicon, { name: action.icon, size: 13 }), action.label]
        })
      }),
      jsx('button', {
        'aria-expanded': open,
        'aria-haspopup': 'menu',
        'aria-label': `More for ${title}`,
        className: `caret ${action.tone ?? 'solid'}`,
        onClick: () => setOpen(!open),
        type: 'button',
        children: jsx(Codicon, { name: 'chevron-down', size: 12 })
      }),
      open ? jsx('div', { 'aria-label': `${title} actions`, className: 'cs-gmenu', role: 'menu', children: rows }) : null
    ]
  })
}

/** What is wrong with the game folder's layout (`layout` in the games RPC), when anything is. */
function LayoutTag({ layout }) {
  const findings = [...(layout?.problems ?? []), ...(layout?.warnings ?? [])]

  if (!findings.length) {
    return null
  }

  return jsxs('span', { className: `cs-gst ${layout.problems?.length ? 'bad' : 'warn'}`, title: findings.map(item => item.path || item.code).join('\n'), children: [jsx('i', {}), 'Layout'] })
}

export function GameCard({ ctx, game, hardwareOn, onPlay, onMakeCover }) {
  const title = game.displayTitle || game.title
  const card = game.card ?? null
  const playable = game.state !== 'unbuilt' && game.state !== 'failed'
  const [tone, status] = GAME_STATUS[game.state] ?? GAME_STATUS.unbuilt
  const meta = gameMeta(game, { kind: false })
  const built = meta[meta.length - 1]

  return jsxs('article', {
    className: 'cs-gcard',
    children: [
      jsx(Cartridge, {
        disabled: !playable,
        game,
        label: playable ? `Play ${title}` : title,
        note: playable ? 'Title screen after first play' : 'No build yet',
        onClick: () => onPlay(game.id),
        play: playable,
        title
      }),
      jsxs('div', {
        className: 'info',
        children: [
          jsx('h3', { title, children: title }),
          game.state === 'failed' && game.error
            ? jsx('p', { className: 'cs-gtag bad', title: game.error, children: game.error })
            : card?.tagline
              ? jsx('p', { className: 'cs-gtag', title: [card.description || card.tagline, card.genres?.length ? card.genres.join(' · ') : null].filter(Boolean).join('\n'), children: card.tagline })
              : jsx('p', { className: 'cs-gtag none', children: 'No description yet' }),
          jsxs('div', {
            className: 'cs-gline',
            title: meta.join(' · '),
            children: [jsxs('span', { className: `cs-gst ${tone}`, children: [jsx('i', {}), status] }), jsx('span', { children: built }), jsx(LayoutTag, { layout: game.layout })]
          })
        ]
      }),
      jsx(GameActions, { ctx, game, hardwareOn, onMakeCover, onPlay })
    ]
  })
}
