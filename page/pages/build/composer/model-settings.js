// The Effort row of the model panel, and beside it (ChatGPT or Codex Subscription models with fast mode) Speed.
import { Codicon, jsx, jsxs } from '#sdk'
import { EFFORTS } from './model-names.js'

const FAST_HINT = 'Quicker, uses more of your plan'

/** `shown` is what the conversation runs on (`effort`, `fast`); `speed` says the model has fast mode; `beside` puts
 *  Speed on the Effort line (the wide panel), else on its own line under it with a short hint. */
export function ModelSettings({ caps, shown, speed, beside, disabled, onEffort, onFast }) {
  const fixedEffort = caps ? caps.reasoning === false : false
  const efforts = EFFORTS.filter(([key]) => key !== 'none' || caps?.can_disable_reasoning !== false)
  const effortGroup = jsxs('div', {
    className: 'cs-b-mp-group cs-b-mp-effortgroup',
    children: [
      jsxs('div', {
        className: 'cs-row',
        children: [
          jsx('span', { className: 'cs-eyebrow', children: 'Effort' }),
          jsx('span', { className: 'cs-grow' }),
          jsx('span', { className: 'cs-faint', children: fixedEffort ? 'This model has a fixed effort' : (EFFORTS.find(([key]) => key === shown.effort)?.[2] ?? 'The model\u2019s default') })
        ]
      }),
      jsx('div', {
        'aria-label': 'Effort',
        className: 'cs-b-seg',
        role: 'radiogroup',
        children: efforts.map(([key, label]) =>
          jsx(
            'button',
            {
              'aria-checked': shown.effort === key,
              disabled: disabled || fixedEffort,
              onClick: () => key !== shown.effort && onEffort(key),
              role: 'radio',
              type: 'button',
              children: label
            },
            key
          )
        )
      })
    ]
  })
  const speedGroup = speed
    ? jsxs('div', {
        className: 'cs-b-mp-group cs-b-mp-speed',
        children: [
          jsxs('div', {
            className: 'cs-row',
            children: [
              jsx('span', { className: 'cs-eyebrow', children: 'Speed' }),
              beside ? null : jsx('span', { className: 'cs-grow' }),
              beside ? null : jsx('span', { className: 'cs-faint', children: shown.fast ? FAST_HINT : 'Standard speed' })
            ]
          }),
          jsx('div', {
            'aria-label': 'Speed',
            className: 'cs-b-seg',
            role: 'radiogroup',
            children: [
              ['normal', false, 'Normal', 'Standard speed'],
              ['fast', true, jsxs('span', { className: 'cs-b-mp-fastlabel', children: [jsx(Codicon, { name: 'zap', size: 11 }), 'Fast'] }), FAST_HINT]
            ].map(([key, on, label, title]) =>
              jsx(
                'button',
                {
                  'aria-checked': shown.fast === on,
                  className: on ? 'cs-b-mp-fast' : undefined,
                  disabled,
                  onClick: () => on !== shown.fast && onFast(on, { model: shown.model, provider: shown.provider }),
                  role: 'radio',
                  title,
                  type: 'button',
                  children: label
                },
                key
              )
            )
          })
        ]
      })
    : null
  return jsxs('div', {
    className: `cs-b-mp-effort${speed && beside ? ' beside' : ''}`,
    children: [effortGroup, speedGroup]
  })
}
