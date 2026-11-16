// The Home page.
import { Button, Codicon, jsx, jsxs, useState } from '../sdk.js'
import { studioError } from '../core/backend.js'
import { openGameChat, sendPromptToChat } from '../core/chat-insert.js'
import { gameMeta, latestGame } from '../games/model.js'
import { StateTag } from '../games/state-tag.js'
import { ALL_PROMPTS, NEW_GAME_PROMPT, promptById } from '../prompts/library.js'
import { STEP_SHORT, toolchainState } from '../setup/steps.js'
import { Art } from '../ui/art.js'
import { AsyncButton } from '../ui/page.js'
import { PromptButton } from '../ui/prompt-button.js'
import { Screen } from '../ui/screen.js'
import { Lede, Small } from '../ui/text.js'
import { Working } from '../ui/working.js'

const QUICK_STARTS = [
  { id: 'start', title: 'Start a new game', text: 'Hermes asks what you want to make, creates it and shows the first frame.' },
  { id: 'remix', title: 'Remix an example', text: 'Start from Wrecklight and make it your own.' },
  { id: 'plan', title: 'Plan a game', text: 'A short interview, then a brief, backlog and test plan.' },
  { id: 'play-game', title: 'Play my game', text: 'Hermes builds the selected game and shows it to you in the emulator beside the chat.' }
]

function SetupBar({ steps, autoId }) {
  return jsx('div', {
    'aria-hidden': true,
    className: 'cs-bar7',
    children: steps.map(step => jsx('i', { className: step.complete ? 'on' : step.id === autoId ? 'cur' : '' }, step.id))
  })
}

function ContinuePanel({ ctx, steps, auto, autoId, choosing, games, onGo, onPlay }) {
  if (auto) {
    // The next step by name; the bar under it shows where it sits (the hero counts the done steps).
    const title = choosing ? 'Emulator or Chromatic?' : `Next: ${STEP_SHORT[auto.id]}`

    return [
      jsx('p', { className: 'cs-eyebrow', children: jsx('span', { className: 'cs-accent', children: 'Continue setup' }) }, 'e'),
      jsx('h3', { className: 'cs-word', style: { fontSize: 'clamp(24px, 2.4cqi, 40px)' }, children: title }, 'h'),
      jsx(SetupBar, { autoId, steps }, 'bar'),
      jsx(
        Small,
        {
          children: choosing
            ? 'The emulator is ready. Choose whether to set up a physical Chromatic too.'
            : auto.hardware
              ? 'Only for a physical Chromatic. You can skip it and use the emulator.'
              : 'The page installs what is missing into hermretro\'s folder, then moves on by itself.'
        },
        's'
      ),
      jsx('div', { className: 'cs-actions', children: jsx(Button, { onClick: () => onGo('setup'), size: 'sm', variant: 'default', children: 'Continue setup' }) }, 'a')
    ]
  }

  const eyebrow = jsx('p', { className: 'cs-eyebrow', children: jsx('span', { className: 'cs-accent', children: 'Continue' }) }, 'e')

  if (games.isError || games.data?.games === undefined) {
    return [
      eyebrow,
      games.isError
        ? jsx(Small, { children: studioError(games.error, 'list your games') }, 'err')
        : jsx(Working, { quiet: true, children: 'Reading your games…' }, 'wait')
    ]
  }

  const game = latestGame(games.data.games)

  if (!game) {
    return [
      eyebrow,
      jsx('h3', { className: 'cs-word', style: { fontSize: 'clamp(24px, 2.4cqi, 40px)' }, children: 'No games yet' }, 'h'),
      jsx(Small, { children: 'Games you make with Hermes land here, ready to play on the Emulator page.' }, 's'),
      jsx('div', { className: 'cs-actions', children: jsx(PromptButton, { ctx, label: 'Start a new game', prompt: NEW_GAME_PROMPT, variant: 'default' }) }, 'a')
    ]
  }

  return [
    eyebrow,
    jsxs(
      'div',
      {
        className: 'cs-cont',
        children: [
          jsx(Screen, { game }),
          jsxs('div', {
            className: 'cs-col',
            style: { gap: 10 },
            children: [
              jsx('h3', { className: 'name', children: game.title }),
              jsxs('div', { className: 'cs-row', style: { gap: 10 }, children: [jsx(StateTag, { game }), jsx('span', { className: 'cs-meta', children: gameMeta(game).join(' · ') })] }),
              game.chat?.title ? jsx('span', { className: 'cs-faint', children: `Chat: ${game.chat.title}` }) : null,
              jsxs('div', {
                className: 'cs-actions',
                children: [
                  game.chat ? jsx(AsyncButton, { icon: 'comment-discussion', run: () => openGameChat(game), title: 'Open the chat this game was made in', variant: 'default', children: 'Open chat' }) : null,
                  jsxs(Button, {
                    disabled: game.state === 'unbuilt',
                    onClick: () => onPlay(game.id),
                    size: 'sm',
                    variant: game.chat ? 'outline' : 'default',
                    children: [jsx(Codicon, { name: 'play', size: 14 }), 'Play']
                  })
                ]
              })
            ]
          })
        ]
      },
      'cont'
    )
  ]
}

export function HomePage({ ctx, steps, auto, autoId, choosing, status, doctor, memory, games, onGo, onPlay, onOpenPrompt, onSetUpDevice }) {
  const ready = !auto
  const hardwareOn = Boolean(status.data?.hardware_enabled)
  const emulatorOnly = Boolean(memory.hardwareSkipped) && !hardwareOn
  // Steps verified done, not skipped ones. The Chromatic steps count only for someone setting one up.
  const counted = steps.filter(step => !step.hardware || memory.hardwareWanted || hardwareOn)
  const done = counted.filter(step => step.state === 'done').length
  const [busy, setBusy] = useState(null)

  const quick = async item => {
    if (item.id === 'remix') {
      onOpenPrompt('remix')

      return
    }

    setBusy(item.id)

    try {
      await sendPromptToChat(ctx, item.id === 'start' ? NEW_GAME_PROMPT : promptById(item.id).text)
    } finally {
      setBusy(null)
    }
  }

  const toolchain = toolchainState(status.data, doctor)
  const gameCount = games.data?.games?.length
  const statRow = (term, tone, value) =>
    jsxs('div', { children: [jsx('dt', { children: term }), jsxs('dd', { title: String(value), children: [jsx('i', { className: tone }), value] })] }, term)

  return jsxs('div', {
    className: 'cs-home',
    children: [
      jsxs('div', {
        className: 'cs-hero',
        children: [
          jsxs('div', {
            className: 'cs-col',
            children: [
              jsxs('p', {
                className: 'cs-eyebrow',
                children: [
                  jsx('span', { className: 'cs-accent', children: '●' }),
                  ready ? (emulatorOnly ? 'Ready to make games in the emulator' : 'Setup is complete') : `Setup: ${done} of ${counted.length} done`
                ]
              }),
              jsxs('h2', {
                className: 'cs-word',
                children: ['Make a game.', jsx('br', {}), jsx('span', { className: 'cs-accent', children: 'Play it tonight.' })]
              }),
              jsx(Lede, {
                children:
                  'Build your game by chatting. Hermes builds and playtests it; you play it on the Emulator page, with sound, or on your Chromatic.'
              }),
              jsxs('div', {
                className: 'cs-actions',
                children: [
                  ready
                    ? jsx(PromptButton, { ctx, fresh: true, label: 'Start a new game', prompt: NEW_GAME_PROMPT, variant: 'default' })
                    : jsx(Button, { onClick: () => onGo('setup'), size: 'sm', variant: 'default', children: 'Continue setup' }),
                  ready && emulatorOnly ? jsx(Small, { children: 'Your Chromatic is not set up, so streaming and flashing are off.' }) : null,
                  ready && emulatorOnly ? jsx(Button, { onClick: onSetUpDevice, size: 'sm', variant: 'outline', children: 'Set up my Chromatic' }) : null
                ]
              })
            ]
          }),
          jsx(Art, {})
        ]
      }),
      jsxs('div', {
        className: 'cs-band',
        children: [
          jsx('section', { children: ContinuePanel({ ctx, auto, autoId, choosing, games, onGo, onPlay, steps }) }),
          jsxs('section', {
            children: [
              jsxs('p', { className: 'cs-eyebrow', children: ['Start something', ready ? null : jsx('span', { className: 'cs-draft', children: 'after setup' })] }),
              jsx('div', {
                className: 'cs-quick',
                children: QUICK_STARTS.map(item =>
                  jsxs(
                    'button',
                    {
                      disabled: !ready || busy !== null,
                      onClick: () => void quick(item),
                      type: 'button',
                      children: [
                        jsx('span', { className: 't', children: item.title }),
                        jsx('span', { className: 'a', children: item.id === 'remix' ? 'Open prompt →' : busy === item.id ? 'Opening…' : 'Use in chat →' }),
                        jsx('span', { className: 'd', children: item.text })
                      ]
                    },
                    item.id
                  )
                )
              }),
              jsx('div', { children: jsx('button', { className: 'cs-link', onClick: () => onGo('prompts'), type: 'button', children: `All ${ALL_PROMPTS.length} prompts →` }) })
            ]
          }),
          jsxs('section', {
            children: [
              jsx('p', { className: 'cs-eyebrow', children: 'Studio' }),
              jsxs('dl', {
                className: 'cs-stat',
                children: [
                  statRow('Setup', ready ? 'good' : 'warn', `${done} of ${counted.length} done`),
                  statRow('Profile', status.data?.profile?.is_studio === false ? 'warn' : 'good', status.data?.profile?.name ?? status.data?.via_profile ?? 'this profile'),
                  statRow('Toolchain', { done: 'good', todo: 'warn', error: 'bad' }[toolchain] ?? '', { done: 'ready', todo: 'missing', error: 'check failed' }[toolchain] ?? 'checking…'),
                  statRow('Chromatic', hardwareOn ? 'good' : '', hardwareOn ? 'on' : emulatorOnly ? 'emulator only' : 'not set up'),
                  statRow('Games', '', gameCount === undefined ? (games.isError ? 'unavailable' : '…') : String(gameCount))
                ]
              }),
              jsxs('div', {
                className: 'cs-row',
                style: { gap: 14 },
                children: [
                  jsx('button', { className: 'cs-link', onClick: () => onGo('setup'), type: 'button', children: 'Setup →' }),
                  jsx('button', { className: 'cs-link', onClick: () => onGo('games'), type: 'button', children: 'Games →' })
                ]
              })
            ]
          })
        ]
      })
    ]
  })
}
