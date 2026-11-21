// The Games page (Shelf).
import { Button, Codicon, jsx, jsxs, Tip } from '#sdk'
import { studioError } from '#app/backend.js'
import { emit } from '#app/events.js'
import { sendToGameChat } from '#app/chat-insert.js'
import { Art } from '#shared/ui/art.js'
import { AsyncButton, PageHead } from '#shared/ui/page.js'
import { GamesFolder } from './games-folder.js'
import { Lede, Small } from '#shared/ui/text.js'
import { Working } from '#shared/ui/working.js'
import { COVER_PROMPT, GameCard } from './game-card.js'
import { installPrompt } from './model.js'

function DeviceStrip({ hardwareOn, onSetUpDevice }) {
  return hardwareOn
    ? jsxs('div', {
        className: 'cs-dev on',
        children: [
          jsx('span', { className: 'dot' }),
          jsx('span', { className: 'nm', children: 'Chromatic hardware tools are on' }),
          jsx(Small, { children: "Install puts the flash prompt in the game's chat. Hermes asks before it writes the cartridge, unless Approvals are off." })
        ]
      })
    : jsxs('div', {
        className: 'cs-dev',
        children: [
          jsx('span', { className: 'dot' }),
          jsx('span', { className: 'nm', children: 'Playing in the emulator.' }),
          jsx(Small, { children: 'Set up a Chromatic to install games on a real cartridge.' }),
          jsx('span', { className: 'cs-grow' }),
          jsx(Button, { onClick: onSetUpDevice, size: 'sm', variant: 'outline', children: 'Set up my Chromatic' })
        ]
      })
}

export function InstallButton({ ctx, game, hardwareOn, label = 'Install' }) {
  return jsx(AsyncButton, {
    disabled: !hardwareOn || !game.rom,
    icon: 'desktop-download',
    run: () => sendToGameChat(ctx, game, installPrompt(game)),
    title: !hardwareOn ? 'Needs your Chromatic' : !game.rom ? 'Build it first' : "Puts the flash prompt in this game's chat; Hermes asks before writing",
    variant: 'outline',
    children: label
  })
}

/** The hardware state as one chip beside New game (A1); the empty library keeps the full strip. */
function DeviceChip({ hardwareOn, onSetUpDevice }) {
  return hardwareOn
    ? jsx(Tip, {
        label: "Install puts the flash prompt in the game's chat. Hermes asks before it writes the cartridge, unless Approvals are off.",
        children: jsxs('span', { className: 'cs-hwchip on', children: [jsx('i', {}), 'Chromatic tools on'] })
      })
    : jsx(Tip, {
        label: 'Set up a Chromatic to install games on a real cartridge.',
        children: jsxs('button', { className: 'cs-hwchip', onClick: onSetUpDevice, type: 'button', children: [jsx('i', {}), 'Emulator only · Set up my Chromatic'] })
      })
}

export function GamesPage({ ctx, games, hardwareOn, onPlay, onNewGame, onSetUpDevice, onMakeCover }) {
  const list = games.data?.games
  const folder = jsx(GamesFolder, { ctx, path: games.data?.gamesDir }, 'folder')
  const newGame = jsxs(Button, { onClick: onNewGame, size: 'sm', variant: 'default', children: [jsx(Codicon, { name: 'add', size: 14 }), 'New game'] })

  if (games.isError || (games.data && !Array.isArray(list))) {
    return [
      jsx(PageHead, { title: 'Your games' }, 'head'),
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 12, maxWidth: '72ch' },
        children: [
          jsx(Lede, { children: games.isError ? studioError(games.error, 'list your games') : games.data?.error || 'The games list could not be read.' }),
          jsx('div', { children: newGame })
        ]
      }, 'err')
    ]
  }

  if (!list) {
    return [jsx(PageHead, { title: 'Your games' }, 'head'), jsx(Working, { quiet: true, children: 'Reading your games…' }, 'wait')]
  }

  if (!list.length) {
    return [
      jsx(DeviceStrip, { hardwareOn, onSetUpDevice }, 'dev'),
      jsxs(
        'div',
        {
          className: 'cs-empty',
          children: [
            jsxs('div', {
              className: 'cs-col',
              children: [
                jsx('h2', { className: 'cs-word cs-title', children: 'No games yet' }),
                jsx(Lede, {
                  children: 'Games you make with Hermes land here, ready to play in the emulator or install on your Chromatic.'
                }),
                jsx('div', {
                  className: 'cs-actions',
                  children: jsx(Button, { onClick: onNewGame, size: 'sm', variant: 'default', children: 'Create a new game' })
                }),
                jsx('p', { className: 'cs-faint', children: 'Already have a GB Studio project? Ask Hermes to select it and it shows up here.' }),
                folder
              ]
            }),
            jsx(Art, {})
          ]
        },
        'empty'
      )
    ]
  }

  return [
    jsx(PageHead, { title: 'Your games', children: [jsx(DeviceChip, { hardwareOn, onSetUpDevice }, 'hw'), jsx('span', { style: { display: 'contents' }, children: newGame }, 'new')] }, 'head'),
    jsxs(
      'div',
      {
        className: 'cs-shelf',
        children: [
          ...list.map(game => jsx(GameCard, { ctx, game, hardwareOn, onMakeCover, onPlay }, game.id)),
          jsxs(
            'article',
            {
              className: 'cs-gcard',
              children: [
                jsx('button', {
                  'aria-label': 'New game',
                  className: 'cs-cart ghost',
                  onClick: onNewGame,
                  type: 'button',
                  children: jsx('span', {
                    className: 'slot',
                    children: jsxs('span', {
                      className: 'cs-col',
                      style: { alignItems: 'center', gap: 8 },
                      children: [jsx(Codicon, { name: 'add', size: 26 }), jsx('span', { className: 'cs-eyebrow', children: 'New game' })]
                    })
                  })
                }),
                jsxs('div', {
                  className: 'info',
                  children: [
                    jsx('h3', { style: { color: 'var(--ui-text-tertiary)' }, children: 'Blank cartridge' }),
                    jsx('p', { className: 'cs-gtag none', children: 'Make a new game with Hermes' })
                  ]
                })
              ]
            },
            'new'
          )
        ]
      },
      'shelf'
    ),
    folder
  ]
}

/** The page's own Page: the shelf, fed from the shell. */
export function Games({ shell }) {
  return jsx(GamesPage, {
    ctx: shell.ctx,
    games: shell.games,
    hardwareOn: shell.hardwareOn,
    // Make cover art: the request goes into that game's Build conversation (Build listens), not sent.
    onMakeCover: game => {
      emit('games.coverRequested', { game, prompt: COVER_PROMPT })
      shell.go('build')
    },
    onNewGame: () => {
      emit('games.newGameRequested')
      shell.go('build')
    },
    onPlay: shell.play,
    onSetUpDevice: shell.setUpDevice
  })
}
