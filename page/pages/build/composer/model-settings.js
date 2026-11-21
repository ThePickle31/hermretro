// The right column of the model panel (Effort as a list) and the bar along its bottom (Standard / Fast for
// ChatGPT or Codex Subscription models with fast mode; Manage providers, or the held-pick note).
import { Codicon, jsx, jsxs } from '#sdk'
import { AGENT } from '#app/ids.js'
import { EFFORTS, modelName } from './model-names.js'

const FAST_HINT = 'Quicker replies. Uses more of your plan'

/** `shown` is what the conversation runs on (`model`, `effort`). `narrow` drops the note under the levels. */
export function EffortColumn({ caps, shown, disabled, narrow, onEffort }) {
  const fixed = caps ? caps.reasoning === false : false
  const levels = EFFORTS.filter(([key]) => key !== 'none' || caps?.can_disable_reasoning !== false)
  const picked = EFFORTS.find(([key]) => key === shown.effort)

  return jsxs('div', {
    className: 'cs-b-mp-effort',
    children: [
      jsxs('div', {
        className: 'cs-b-mp-ehead',
        children: [
          jsx('span', { children: 'Effort' }),
          shown.model ? jsx('span', { className: 'cs-b-mp-emodel', title: shown.model, children: modelName(shown.model).name }) : null
        ]
      }),
      jsx('div', {
        'aria-label': 'Effort',
        className: 'cs-b-mp-levels',
        role: 'radiogroup',
        children: levels.map(([key, label, hint]) =>
          jsxs(
            'button',
            {
              'aria-checked': shown.effort === key,
              disabled: disabled || fixed,
              onClick: () => key !== shown.effort && onEffort(key),
              role: 'radio',
              title: hint,
              type: 'button',
              children: [label, shown.effort === key ? jsx(Codicon, { name: 'check', size: 12 }, 'check') : null]
            },
            key
          )
        )
      }),
      narrow
        ? null
        : jsxs('div', {
            className: 'cs-b-mp-enote',
            children: fixed
              ? [jsx('b', { children: 'Fixed' }, 'b'), 'This model has a fixed effort']
              : picked
                ? [jsx('b', { children: picked[1] }, 'b'), picked[2]]
                : [jsx('b', { children: 'Default' }, 'b'), 'The model\u2019s own effort']
          })
    ]
  })
}

/** Standard / Fast when `speed` (a Codex model with fast mode), and on the right the held note or Manage providers. */
export function SpeedBar({ speed, fast, held, narrow, disabled, onFast, onManage }) {
  return jsxs('div', {
    className: 'cs-b-mp-bar',
    children: [
      speed
        ? jsx('div', {
            'aria-label': 'Speed',
            className: 'cs-b-seg cs-b-mp-speed',
            role: 'radiogroup',
            children: [
              ['normal', false, 'Standard', 'Standard speed'],
              ['fast', true, [jsx(Codicon, { name: 'zap', size: 11 }, 'zap'), 'Fast'], FAST_HINT]
            ].map(([key, on, label, title]) =>
              jsx(
                'button',
                {
                  'aria-checked': fast === on,
                  className: on ? 'cs-b-mp-fast' : undefined,
                  disabled,
                  onClick: () => on !== fast && onFast(on),
                  role: 'radio',
                  title,
                  type: 'button',
                  children: label
                },
                key
              )
            )
          })
        : null,
      jsx('span', { className: 'cs-grow' }),
      held
        ? jsx('span', { className: 'cs-b-mp-held', children: narrow ? 'Switches after this turn' : `Switches when ${AGENT} finishes this turn` })
        : jsxs('button', {
            className: 'cs-b-mp-manage',
            onClick: onManage,
            type: 'button',
            children: [narrow ? 'Providers' : 'Manage providers', jsx(Codicon, { name: 'chevron-right', size: 11 }, 'go')]
          })
    ]
  })
}
