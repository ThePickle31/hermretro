// The right column of the model panel (Effort as a list) and the bar along its bottom (Standard / Fast for
// ChatGPT or Codex Subscription models with fast mode; Manage providers, or the held-pick note).
import { Codicon, jsx, jsxs } from '#sdk'
import { AGENT } from '#app/ids.js'
import { EFFORTS, modelName } from './model-names.js'

const FAST_HINT = 'Quicker replies. Uses more of your plan'
const ARROWS = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 }

/** A radio group's keys: one Tab stop (the picked choice, else the first), arrows pick and focus the next one. */
function radioProps(keys, current, index, pick, disabled) {
  return {
    'data-key': keys[index],
    tabIndex: (keys.includes(current) ? keys[index] === current : index === 0) ? 0 : -1,
    onKeyDown: event => {
      const step = ARROWS[event.key]

      if (!step || disabled) {
        return
      }

      event.preventDefault()

      const from = keys.includes(current) ? keys.indexOf(current) : index
      const next = keys[(from + step + keys.length) % keys.length]

      pick(next)
      event.currentTarget.parentElement?.querySelector(`[data-key="${next}"]`)?.focus?.()
    }
  }
}

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
        children: levels.map(([key, label, hint], index) =>
          jsxs(
            'button',
            {
              ...radioProps(levels.map(([level]) => level), shown.effort, index, next => next !== shown.effort && onEffort(next), disabled || fixed),
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
            ].map(([key, on, label, title], index) =>
              jsx(
                'button',
                {
                  ...radioProps(['normal', 'fast'], fast ? 'fast' : 'normal', index, next => (next === 'fast') !== fast && onFast(next === 'fast'), disabled),
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
