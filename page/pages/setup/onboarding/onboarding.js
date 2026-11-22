// First-run onboarding: welcome, install, Chromatic or not, first game.
import { Button, Codicon, host, jsx, jsxs, useEffect, useRef, useState } from '#sdk'
import { describeRequestError } from '#app/backend.js'
import { emit } from '#app/events.js'
import { formatBytes } from '#app/format.js'
import { InstallActions, InstallError, InstallProgress } from '#pages/setup/install/install-actions.js'
import { DownloadTable, InstallFacts, InstallLog, profileRowState } from '#pages/setup/install/install-panel.js'
import { useInstaller } from '#pages/setup/install/installer.js'
import { Art } from '#shared/ui/art.js'
import { Lede } from '#shared/ui/text.js'
import { Working } from '#shared/ui/working.js'

// The backend runs the engine's own toolchain_prepare in the broker and reports per-component
// progress (RPC `install`). The page lists every download before anything starts.
export const ONBOARD_STAGES = [
  ['install', 'Install'],
  ['chromatic', 'Your hardware'],
  ['make', 'First game']
]

// A new user sees only this until the game tools are installed and they have chosen how to play:
// Welcome → what gets downloaded / installing → "Do you have a Chromatic?" → "What do you want to make?".
/** `end`: what the shell puts at the header's right (the update chip, so a broken install can still be updated). */
export function OnboardHeader({ stage, end = null }) {
  const index = ONBOARD_STAGES.findIndex(([id]) => id === stage)

  return jsxs('header', {
    className: 'cs-top',
    children: [
      jsxs('span', { className: 'cs-brand', style: { cursor: 'default' }, children: ['herm', jsx('span', { children: 'retro' })] }),
      index >= 0
        ? jsxs('div', {
            'aria-label': `Setup, step ${index + 1} of ${ONBOARD_STAGES.length}: ${ONBOARD_STAGES[index][1]}`,
            className: 'cs-onb-steps',
            role: 'img',
            children: [
              ...ONBOARD_STAGES.map(([id], position) => jsx('i', { className: position < index ? 'done' : position === index ? 'cur' : '' }, id)),
              jsx('span', { children: `${index + 1} / ${ONBOARD_STAGES.length} · ${ONBOARD_STAGES[index][1]}` })
            ]
          })
        : jsx('span', { className: 'cs-onb-steps', children: jsx('span', { children: 'First-time setup' }) }),
      end ? jsx('div', { className: 'cs-top-end', children: end }) : null
    ]
  })
}

function OnboardWelcome({ manifest, onStart }) {
  return jsxs('div', {
    className: 'cs-onb-hero',
    children: [
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 24 },
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [jsx('span', { className: 'cs-accent', children: '● Welcome' }), jsx('span', { children: 'First-time setup · a few minutes' })]
          }),
          jsxs('h1', { className: 'cs-word', children: ['Make a game.', jsx('br', {}), jsx('span', { className: 'cs-accent', children: 'Play it tonight.' })] }),
          jsx(Lede, {
            children:
              "hermretro turns a chat with Hermes into a real Game Boy Color game. Before your first game it needs the tools that build and playtest ROMs. Everything goes into the plugin's own folder."
          }),
          jsxs('div', {
            className: 'cs-actions',
            style: { gap: 16 },
            children: [
              jsxs(Button, { onClick: onStart, size: 'lg', variant: 'default', children: ['Get started', jsx(Codicon, { name: 'arrow-right', size: 14 })] }),
              manifest
                ? jsx('span', { className: 'cs-faint cs-mono', children: `${formatBytes(manifest.bytes, { approx: true })} download · ${formatBytes(manifest.disk_bytes, { approx: true })} on disk` })
                : null
            ]
          })
        ]
      }),
      jsx(Art, {})
    ]
  })
}

/** While the tools install: the bundled demo, only when asked for, in its own tab beside the chat (the Emulator page
 *  opens it on `setup.demoRequested`). It needs neither the tools being installed nor a model. */
function TryDemo() {
  if (typeof host.openWorkspace !== 'function') {
    return null
  }

  return jsxs('div', {
    className: 'cs-row',
    children: [
      jsxs(Button, {
        onClick: () => emit('setup.demoRequested', {}),
        size: 'sm',
        variant: 'ghost',
        children: [jsx(Codicon, { name: 'play', size: 14 }), 'Try the demo while you wait']
      }),
      jsx('span', { className: 'cs-faint', children: "ModRetro's Hello Color example opens beside the chat. The install keeps going." })
    ]
  })
}

function OnboardInstall({ ctx, status, install, toolchainDone, profileStep, doctor }) {
  const installer = useInstaller({ ctx, doctor, install, status, toolchainDone })
  const data = install.data
  const { phase } = installer
  const title =
    phase === 'failed'
      ? ['One part ', jsx('span', { className: 'cs-bad', children: "didn't finish" }, 'a')]
      : phase === 'review'
        ? ["Here's what gets ", jsx('span', { className: 'cs-accent', children: 'downloaded' }, 'a')]
        : ['Setting up the ', jsx('span', { className: 'cs-accent', children: 'studio' }, 'a')]
  const lede =
    phase === 'failed'
      ? 'Nothing is broken, and the parts that finished are kept. Try again, or ask Hermes to look at the error.'
      : phase === 'review'
        ? "Every file is pinned to an exact version and checked against its SHA-256 before it is used. Nothing is installed system-wide: it all goes into hermretro's folder in your Hermes home, where your games live too."
        : 'You can leave this page: the install keeps running, and this page moves on when the tools are verified.'

  return jsxs('div', {
    className: 'cs-onb-split',
    children: [
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 22 },
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [
              jsx('span', { className: phase === 'failed' ? 'cs-bad' : 'cs-accent', children: 'Step 1 of 3' }),
              jsx('span', { children: { review: 'Install', running: 'Installing', failed: 'Stopped', done: 'Installed' }[phase] })
            ]
          }),
          jsx('h2', { className: 'cs-word cs-title', children: title }),
          jsx(Lede, { children: lede }),
          jsx(InstallFacts, { manifest: data?.manifest, root: data?.root, status }),
          jsx(InstallProgress, { elsewhere: installer.elsewhere, install: data?.install, phase, verifying: installer.verifying }),
          ...InstallError({ installer }),
          jsx(InstallActions, { installer }),
          phase === 'running' ? jsx(TryDemo, {}) : null
        ]
      }),
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 18 },
        children: [
          data?.manifest
            ? jsx(DownloadTable, { install: data.install, manifest: data.manifest, phase, profileRow: profileRowState(installer, profileStep, status) })
            : install.isError && !installer.unsupported
              ? jsx('p', { className: 'cs-error', children: describeRequestError(install.error).message })
              : installer.unsupported
                ? null
                : jsx(Working, { quiet: true, children: 'Reading the download list…' }),
          jsx(InstallLog, { install: data?.install, phase }),
          data?.manifest && !data.manifest.exact
            ? jsx('span', { className: 'cs-faint', children: `Sizes were measured on ${data.manifest.measured_on} and are approximate here.` })
            : null
        ]
      })
    ]
  })
}

function OnboardChromatic({ onEmulator, onDevice }) {
  const card = ({ tag, tone, title, text, onClick, art, primary }) =>
    jsxs('button', {
      className: primary ? 'cs-hwcard primary' : 'cs-hwcard',
      onClick,
      type: 'button',
      children: [
        art,
        jsxs('span', {
          className: 'cs-col',
          style: { gap: 8 },
          children: [
            jsx('span', { className: `cs-tag ${tone}`, style: { alignSelf: 'flex-start' }, children: tag }),
            jsx('span', { className: 'cs-word t', children: title }),
            jsx('span', { className: 'cs-small', children: text })
          ]
        })
      ]
    })

  return jsxs('div', {
    className: 'cs-col',
    style: { gap: 28 },
    children: [
      jsxs('p', { className: 'cs-eyebrow', children: [jsx('span', { className: 'cs-accent', children: 'Step 2 of 3' }), jsx('span', { children: 'Your hardware' })] }),
      jsxs('h2', { className: 'cs-word cs-onb-title', children: ['Do you have a ', jsx('span', { className: 'cs-accent', children: 'Chromatic?' })] }),
      jsx(Lede, {
        children:
          'A Chromatic is optional: every game plays in the emulator here, with sound. With a ModRetro Chromatic you can also stream games to it and write them to a cartridge, now or any time later from Setup.'
      }),
      jsxs('div', {
        className: 'cs-hwcards',
        children: [
          card({
            art: jsx('span', { 'aria-hidden': true, className: 'cs-hwart screen', children: jsx(Codicon, { name: 'play', size: 22 }) }),
            onClick: onEmulator,
            primary: true,
            tag: 'Ready now',
            text: 'Make and play games in the emulator. You can add a Chromatic later from Setup.',
            title: 'Start making games',
            tone: 'good'
          }),
          card({
            art: jsx('span', { 'aria-hidden': true, className: 'cs-hwart device' }),
            onClick: onDevice,
            tag: 'Optional · 4 more steps',
            text: "Update its firmware, turn on Developer Mode and install ModRetro's device software. Each step asks first, and you can stop and come back.",
            title: 'Set up my Chromatic',
            tone: 'quiet'
          })
        ]
      })
    ]
  })
}

const IDEAS = [
  ['Tiny platformer', 'a tiny platformer where a frog hops across lily pads to reach home'],
  ['Top-down adventure', 'a top-down adventure where a gardener collects three seeds to open a gate'],
  ['Puzzle game', 'a short puzzle game about pushing crates onto switches'],
  ['Spooky story', 'a spooky little story game set in an abandoned lighthouse']
]

/** The last screen: the idea goes on to Build's New Game box (`setup.firstIdea`), never sent from here. Every way
 *  out (Build it, Plan first, Skip, Set up my Chromatic) takes what was typed along. */
function OnboardMake({ onDone, onDevice }) {
  const [idea, setIdea] = useState('')

  const handOff = plan => {
    if (idea.trim() || plan) {
      emit('setup.firstIdea', { idea: idea.trim(), plan })
    }
  }
  const go = plan => {
    handOff(plan)
    onDone()
  }

  return jsxs('div', {
    className: 'cs-onb-hero',
    children: [
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 22 },
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [jsx('span', { className: 'cs-good', children: '● Studio ready' }), jsx('span', { children: 'Step 3 of 3' })]
          }),
          jsxs('h2', { className: 'cs-word cs-onb-title', children: ['What do you', jsx('br', {}), 'want to ', jsx('span', { className: 'cs-accent', children: 'make?' })] }),
          jsxs('div', {
            className: 'cs-idea',
            children: [
              jsx('textarea', {
                'aria-label': 'Your game idea',
                onChange: event => setIdea(event.target.value),
                onKeyDown: event => {
                  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault()
                    go(false)
                  }
                },
                placeholder: 'A frog who delivers mail across a flooded town…',
                rows: 3,
                value: idea
              }),
              jsxs('div', {
                className: 'cs-row',
                style: { justifyContent: 'space-between' },
                children: [
                  jsx('span', { className: 'cs-faint', children: 'It goes into the New Game box on Build. Nothing is sent until you press send there.' }),
                  jsxs('div', {
                    className: 'cs-row',
                    style: { gap: 8 },
                    children: [
                      jsx(Button, { onClick: () => go(true), size: 'sm', variant: 'outline', children: 'Plan it first' }),
                      jsxs(Button, {
                        onClick: () => go(false),
                        size: 'sm',
                        variant: 'default',
                        children: ['Continue in Build', jsx(Codicon, { name: 'arrow-right', size: 14 })]
                      })
                    ]
                  })
                ]
              })
            ]
          }),
          jsx('div', {
            'aria-label': 'Ideas',
            className: 'cs-ideas',
            role: 'group',
            children: IDEAS.map(([label, text]) => jsx('button', { onClick: () => setIdea(text), type: 'button', children: label }, label))
          }),
          jsxs('div', {
            className: 'cs-row',
            style: { gap: 8 },
            children: [
              jsx(Button, { onClick: () => go(false), size: 'sm', variant: 'ghost', children: 'Skip, take me to the studio' }),
              onDevice
                ? jsx(Button, {
                    onClick: () => {
                      handOff(false)
                      onDevice()
                    },
                    size: 'sm',
                    variant: 'ghost',
                    children: 'Set up my Chromatic first'
                  })
                : null
            ]
          })
        ]
      }),
      jsx(Art, {})
    ]
  })
}

export function Onboarding({ ctx, screen, status, install, steps, update, onFinish, onDevice, doctor }) {
  const toolchain = steps.find(step => step.id === 'toolchain')
  const profileStep = steps.find(step => step.id === 'profile')
  let body

  if (screen === 'checking') {
    body = jsx(Working, { children: 'Checking what is already installed…' })
  } else if (screen === 'welcome') {
    body = jsx(OnboardWelcome, { manifest: install.data?.manifest, onStart: () => update({ onboardStarted: true }) })
  } else if (screen === 'install') {
    body = jsx(OnboardInstall, { ctx, doctor, install, profileStep, status, toolchainDone: toolchain?.state === 'done' })
  } else if (screen === 'chromatic') {
    body = jsx(OnboardChromatic, { onDevice, onEmulator: () => update({ hardwareSkipped: true, hardwareWanted: false }) })
  } else {
    body = jsx(OnboardMake, { onDevice, onDone: onFinish })
  }

  // A new screen moves focus to its heading (announced once); the section is not a live region, or every
  // progress tick would be read out.
  const section = useRef(null)
  const shown = useRef(screen)

  useEffect(() => {
    if (shown.current === screen) {
      return
    }

    shown.current = screen
    const title = section.current?.querySelector('h1, h2')

    if (title) {
      title.tabIndex = -1
      title.focus?.({ preventScroll: true })
    }
  }, [screen])

  return jsx('section', { className: 'cs-onb', 'data-screen': screen, ref: section, children: body })
}
