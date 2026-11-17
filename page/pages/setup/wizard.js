// The setup wizard: step rail and the current step.
import { Button, Codicon, jsx, jsxs } from '#sdk'
import { Glyph, INDICATOR } from '#shared/ui/glyph.js'
import { Small } from '#shared/ui/text.js'
import { Working } from '#shared/ui/working.js'
import { DeviceSoftwareBody, DevModeBody, FirmwareBody, HardwareBody } from './hardware-steps.js'
import { ProfileBody } from './profile-step.js'
import { HARDWARE_STEPS, STEP_SHORT } from './steps.js'
import { ToolchainBody } from './toolchain-step.js'

function stepBody(step, props) {
  switch (step.id) {
    case 'profile':
      return jsx(ProfileBody, props)
    case 'toolchain':
      return jsx(ToolchainBody, { ...props, step })
    case 'firmware':
      return jsx(FirmwareBody, { ...props, step })
    case 'devmode':
      return jsx(DevModeBody, { ...props, step })
    case 'devicecli':
      return jsx(DeviceSoftwareBody, { ...props, step })
    default:
      return jsx(HardwareBody, { ...props, step })
  }
}

/** The list of steps beside the page: the game steps, then the optional Chromatic ones. */
export function StepRail({ steps, shownId, autoId, onPick, skipped }) {
  const done = steps.filter(step => step.state === 'done').length
  const item = (step, position) =>
    jsxs(
      'button',
      {
        'aria-current': step.id === shownId ? 'step' : undefined,
        className: 'cs-rail-item',
        'data-auto': step.id === autoId ? '' : undefined,
        'data-state': step.state,
        onClick: () => onPick(step.id),
        type: 'button',
        children: [
          jsx('span', { className: 'n', children: String(position + 1).padStart(2, '0') }),
          jsx('span', { className: 'l', children: STEP_SHORT[step.id] }),
          jsx(Glyph, { state: step.state })
        ]
      },
      step.id
    )

  return jsxs('nav', {
    'aria-label': 'Setup steps',
    className: 'cs-rail',
    children: [
      jsx('span', { className: 'cs-rail-group', children: 'Make games' }),
      ...steps.filter(step => !step.hardware).map(step => item(step, steps.indexOf(step))),
      jsxs('span', { className: 'cs-rail-group second', children: [jsx('span', { children: 'Your Chromatic' }), jsx('span', { children: 'optional' })] }),
      ...steps.filter(step => step.hardware).map(step => item(step, steps.indexOf(step))),
      jsx('div', {
        className: 'cs-meter',
        children: steps.map((step, position) =>
          jsx(
            'button',
            {
              'aria-label': `Step ${position + 1}: ${step.title} (${(INDICATOR[step.state] ?? INDICATOR.waiting).label})`,
              className: step.id === HARDWARE_STEPS[0] ? 'gap' : undefined,
              'data-auto': step.id === autoId ? '' : undefined,
              'data-state': step.state,
              onClick: () => onPick(step.id),
              type: 'button',
              children: jsx('i', {})
            },
            step.id
          )
        )
      }),
      jsx('span', { className: 'cs-faint cs-mono', children: `${done} / ${steps.length} done${skipped ? ' · emulator only' : ''}` })
    ]
  })
}

function StepStage({ step, number, total, children, footer }) {
  const tag =
    step.state === 'done'
      ? jsx('span', { className: 'cs-tag good', children: 'Done' })
      : step.state === 'error'
        ? jsx('span', { className: 'cs-tag bad', children: 'Problem' })
        : step.state === 'skipped'
          ? jsx('span', { className: 'cs-tag quiet', children: 'Skipped' })
          : step.hardware
            ? jsx('span', { className: 'cs-tag quiet', children: 'Only for a physical Chromatic' })
            : null

  return jsxs('section', {
    'aria-live': 'polite',
    className: 'cs-stage',
    children: [
      jsxs('div', {
        className: 'cs-stage-head',
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [
              jsx('span', { className: 'cs-accent', children: `Step ${number} of ${total}` }),
              jsx('span', { children: step.hardware ? 'Your Chromatic' : 'Make games' }),
              tag
            ]
          }),
          jsx('h2', { className: 'cs-word cs-title', children: step.title })
        ]
      }),
      children,
      footer
    ]
  })
}

export function SetupWizard({ ctx, steps, shown, autoId, backend, status, doctor, gateway, install, update, onPick, onContinue }) {
  const position = steps.indexOf(shown)
  const reviewing = shown.id !== autoId
  const waiting = !reviewing && !shown.manual && !shown.complete && shown.state !== 'blocked'
  const left = []
  const right = []

  if (position > 0) {
    left.push(
      jsxs(
        Button,
        {
          onClick: () => onPick(steps[position - 1].id),
          size: 'sm',
          variant: 'ghost',
          children: [jsx(Codicon, { name: 'arrow-left', size: 14 }), 'Back']
        },
        'back'
      )
    )
  }

  if (waiting) {
    left.push(jsx(Working, { quiet: true, children: 'Checking automatically; this page moves on when the step is done.' }, 'waiting'))
  }

  if (shown.hardware && !shown.complete) {
    right.push(
      jsx(Button, { onClick: () => update({ hardwareSkipped: true }), size: 'sm', variant: 'ghost', children: "Skip, I'll use the emulator" }, 'skip')
    )
  }

  if (shown.state === 'skipped') {
    right.push(
      jsx(
        Button,
        { onClick: () => update({ hardwareSkipped: false, hardwareWanted: true }), size: 'sm', variant: 'outline', children: 'Set up my Chromatic' },
        'unskip'
      )
    )
  }

  if (reviewing) {
    right.push(
      jsxs(
        Button,
        { onClick: onContinue, size: 'sm', variant: 'default', children: ['Continue', jsx(Codicon, { name: 'arrow-right', size: 14 })] },
        'continue'
      )
    )
  }

  const footer =
    left.length || right.length
      ? jsxs('div', {
          className: 'cs-stage-foot',
          children: [jsx('div', { className: 'cs-row', style: { flex: '1 1 auto' }, children: left }), jsx('div', { className: 'cs-row', children: right })]
        })
      : null

  return jsx(StepStage, {
    step: shown,
    number: position + 1,
    total: steps.length,
    footer,
    children: jsxs('div', {
      className: 'cs-content',
      children: [
        shown.state === 'skipped'
          ? jsx(Small, { children: 'Skipped: you are using the emulator. Streaming and flashing stay off until your Chromatic is set up.' })
          : null,
        stepBody(shown, { backend, ctx, doctor, gateway, install, status, steps, update })
      ]
    })
  })
}
