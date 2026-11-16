// The header: wordmark and the one segmented control.
import { Button, Codicon, jsx, jsxs, Tip } from '../sdk.js'

export const PAGES = [
  ['home', 'Home'],
  ['build', 'Build'],
  ['setup', 'Setup'],
  ['prompts', 'Prompts'],
  ['games', 'Games'],
  ['emulator', 'Emulator']
]

/** Wordmark, one segmented control (always in the same place) and Refresh. */
export function StudioNav({ page, onGo, setupPending, playing, onRefresh, refreshing, viaProfile = null }) {
  return jsxs('header', {
    className: 'cs-top',
    children: [
      jsxs('div', {
        className: 'cs-top-start',
        children: [
          jsxs('button', {
            'aria-label': 'hermretro home',
            className: 'cs-brand',
            onClick: () => onGo('home'),
            type: 'button',
            children: ['herm', jsx('span', { children: 'retro' })]
          }),
          // The profile the studio works in, when it is not the one the app is on: a quiet chip, the
          // explanation in its tooltip.
          viaProfile
            ? jsx(Tip, {
                label: `Showing the "${viaProfile}" profile, where hermretro is switched on. Prompts open a chat in that profile.`,
                children: jsxs('span', {
                  'aria-label': `Showing the "${viaProfile}" profile, where hermretro is switched on. Prompts open a chat in that profile.`,
                  className: 'cs-top-profile',
                  children: [jsx(Codicon, { name: 'account', size: 12 }), viaProfile]
                })
              })
            : null
        ]
      }),
      jsx('nav', {
        'aria-label': 'Studio pages',
        className: 'cs-seg',
        children: PAGES.map(([id, label]) =>
          jsxs(
            'button',
            {
              'aria-current': page === id ? 'page' : undefined,
              onClick: () => onGo(id),
              type: 'button',
              children: [
                label,
                id === 'setup' && setupPending ? jsx('i', { 'aria-label': 'setup is not finished', className: 'pip', role: 'img' }) : null,
                id === 'emulator' && playing && page !== 'emulator' ? jsx('i', { 'aria-label': 'a game is loaded', className: 'live', role: 'img' }) : null
              ]
            },
            id
          )
        )
      }),
      jsx('div', {
        className: 'cs-top-end',
        children: jsx(Tip, {
          label: 'Check the setup and reload the studio',
          children: jsx('span', {
            style: { display: 'inline-flex' },
            children: jsxs(Button, {
              'aria-label': 'Refresh',
              disabled: refreshing,
              onClick: onRefresh,
              size: 'sm',
              variant: 'ghost',
              children: [jsx(Codicon, { name: 'refresh', size: 14, spinning: refreshing }), jsx('span', { className: 'cs-lbl', children: 'Refresh' })]
            })
          })
        })
      })
    ]
  })
}
