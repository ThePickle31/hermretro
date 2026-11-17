// Setup steps for a physical Chromatic, and the choice between it and the emulator.
import { Button, Codicon, host, jsx, jsxs } from '#sdk'
import { AGENT_SETTINGS_HREF, LINKS } from '#app/ids.js'
import { DEVICE_CLI_PROMPT } from '#pages/prompts/library.js'
import { Chip } from '#shared/ui/glyph.js'
import { ExternalLink } from '#shared/ui/links.js'
import { PromptBlock } from '#shared/ui/prompt-block.js'
import { Facts, Lede, Small } from '#shared/ui/text.js'
import { MANUAL_STEPS } from './steps.js'

/** Steps done in ModRetro's own app: the user says when they are done. */
function Confirm({ step, update }) {
  return step.state === 'done'
    ? jsx(Button, { onClick: () => update({ [MANUAL_STEPS[step.id]]: false }), size: 'sm', variant: 'ghost', children: 'Mark as not done' })
    : jsxs(Button, {
        onClick: () => update({ [MANUAL_STEPS[step.id]]: true }),
        size: 'sm',
        variant: 'default',
        children: [jsx(Codicon, { name: 'check', size: 14 }), "I've done this"]
      })
}

export function FirmwareBody({ ctx, step, update }) {
  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          "Install the latest firmware with ModRetro's Chromatic Firmware Updater. This happens in ModRetro's app, not in Hermes, so confirm here when it is done."
      }),
      jsxs('div', {
        className: 'cs-actions',
        children: [
          jsx(ExternalLink, { ctx, href: LINKS.firmware, variant: 'outline', children: 'Open the Firmware Updater guide' }),
          jsx(Confirm, { step, update })
        ]
      })
    ]
  })
}

function Keys({ keys }) {
  return jsxs('span', {
    className: 'cs-row',
    style: { gap: 6 },
    children: keys.flatMap((key, index) => [
      index ? jsx('span', { className: 'cs-faint', children: '+' }, `p${index}`) : null,
      jsx('kbd', { className: 'cs-kbd', children: key }, key)
    ])
  })
}

export function DevModeBody({ step, update }) {
  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          "Developer Mode lets this computer write your games to the cartridge. In ModRetro's Chromatic Firmware Updater press"
      }),
      jsxs('div', {
        className: 'cs-row',
        style: { gap: 10 },
        children: [
          jsx(Keys, { keys: ['Ctrl', 'I'] }),
          jsx('span', { className: 'cs-faint', children: 'or, on macOS,' }),
          jsx(Keys, { keys: ['⌘', 'I'] })
        ]
      }),
      jsx(Small, { children: 'then enter the activation code included with the Chromatic: Codex Edition.' }),
      jsxs('div', {
        className: 'cs-warnline',
        children: [
          jsx('span', { children: jsx(Codicon, { name: 'warning', size: 14 }) }),
          jsx('span', { children: "Activation happens only in ModRetro's Updater. Never type the code into a chat." })
        ]
      }),
      jsx('div', { className: 'cs-actions', children: jsx(Confirm, { step, update }) })
    ]
  })
}

export function DeviceSoftwareBody({ ctx, step, status }) {
  const cli = status.data?.deps?.device_cli

  if (!cli) {
    return jsx(Small, {
      children: status.data?.ok ? 'Not reported yet. Start a new chat to finish loading the plugin.' : 'Checked once the plugin is on.'
    })
  }

  if (step.state === 'done') {
    return jsx(Lede, { children: `ModRetro Chromatic CLI${cli.version ? ` ${cli.version}` : ''} is installed in hermretro's folder.` })
  }

  if (cli.state === 'unsupported') {
    return jsx(Small, { tone: 'warn', children: cli.detail || 'ModRetro does not publish its device software for this computer.' })
  }

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          "hermretro talks to the device through ModRetro's own Chromatic CLI. It is ModRetro's software, so it is not included: Hermes downloads it from ModRetro, checks it, and keeps it in hermretro's folder."
      }),
      jsx(Facts, {
        rows: [
          [
            'Source',
            jsxs('span', {
              children: [
                "ModRetro's npm package, checked against pinned hashes. ",
                cli.terms ? jsx(ExternalLink, { ctx, href: cli.terms, children: "ModRetro's terms" }) : null
              ]
            })
          ],
          ['Approval', 'Hermes asks for your approval before downloading, unless Approvals are turned off.']
        ]
      }),
      jsx(PromptBlock, { ctx, label: 'Install in chat', prompt: DEVICE_CLI_PROMPT })
    ]
  })
}

const HARDWARE_ABILITIES = ['Detect the device', 'Stream', 'Flash a cartridge', 'Capture']

export function HardwareBody({ step }) {
  const on = step.state === 'done'

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children: on
          ? 'Hardware tools are on for this profile: device detection, streaming, flashing and capture are available.'
          : 'Device detection, streaming, flashing and capture are off until you allow them. Turn on "Chromatic hardware tools" in the plugin settings; this page continues once it is on.'
      }),
      jsx('div', {
        className: 'cs-row',
        style: { gap: 6 },
        children: HARDWARE_ABILITIES.map(label => jsx(Chip, { tone: on ? 'good' : '', children: label }, label))
      }),
      jsx(Small, {
        children: 'Writing a cartridge, streaming and driver setup ask for your approval first, unless Approvals are turned off in Hermes.'
      }),
      jsx('div', {
        className: 'cs-actions',
        children: jsxs(Button, {
          onClick: () => host.navigate(AGENT_SETTINGS_HREF),
          size: 'sm',
          variant: on ? 'outline' : 'default',
          children: [jsx(Codicon, { name: 'settings-gear', size: 14 }), 'Open plugin settings']
        })
      })
    ]
  })
}

/** Between the game steps and the Chromatic ones: everything needed for the emulator is done,
 *  and a physical Chromatic is optional. */
export function HardwareChoice({ steps, update }) {
  const remaining = steps.filter(step => step.hardware && step.state !== 'done').length

  return jsxs('section', {
    'aria-live': 'polite',
    className: 'cs-stage',
    children: [
      jsxs('div', {
        className: 'cs-stage',
        style: { display: 'contents' },
        children: [
          jsxs('div', {
            className: 'cs-stage-head',
            children: [
              jsxs('p', {
                className: 'cs-eyebrow',
                children: [jsx('span', { className: 'cs-accent', children: 'Steps 1–2 done' }), jsx('span', { children: 'The emulator is ready' })]
              }),
              jsx('h2', { className: 'cs-word cs-title', children: 'Ready to make games' })
            ]
          }),
          jsx(Lede, {
            children:
              'Hermes can now create, build and playtest your games, and you play them on the Emulator page, with sound. A physical Chromatic is optional: set it up now, or any time later.'
          }),
          jsxs('div', {
            className: 'cs-choice',
            children: [
              jsxs('div', {
                children: [
                  jsx('p', { className: 'cs-eyebrow', children: 'Emulator' }),
                  jsx('h3', { children: 'Start making games' }),
                  jsx(Small, { children: 'Build and play everything inside Hermes. Nothing else to install.' }),
                  jsx('div', {
                    className: 'cs-actions',
                    children: jsxs(Button, {
                      onClick: () => update({ hardwareSkipped: true, hardwareWanted: false }),
                      size: 'sm',
                      variant: 'default',
                      children: ['Start making games', jsx(Codicon, { name: 'arrow-right', size: 14 })]
                    })
                  })
                ]
              }),
              jsxs('div', {
                children: [
                  jsx('p', { className: 'cs-eyebrow', children: 'ModRetro Chromatic' }),
                  jsx('h3', { children: 'I have a Chromatic' }),
                  jsx(Small, {
                    children: `${remaining} more ${remaining === 1 ? 'step' : 'steps'} to stream your games to the handheld and write them to a cartridge: firmware, Developer Mode, ModRetro's device software and hardware tools.`
                  }),
                  jsx('div', {
                    className: 'cs-actions',
                    children: jsx(Button, {
                      onClick: () => update({ hardwareSkipped: false, hardwareWanted: true }),
                      size: 'sm',
                      variant: 'outline',
                      children: 'Set up my Chromatic'
                    })
                  })
                ]
              })
            ]
          }),
          jsx('span', { className: 'cs-faint', children: 'You can change this any time: the Chromatic steps stay in the setup list.' })
        ]
      })
    ]
  })
}
