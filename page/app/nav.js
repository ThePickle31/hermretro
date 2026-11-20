// The header: wordmark and the one segmented control.
import { Button, Codicon, jsx, jsxs, Tip } from '#sdk'
import { UpdateChip } from './update/chip.js'

/** Wordmark, one segmented control (always in the same place), the update chip (only while an update is ready or
 *  running) and Refresh. `pages` are the registry's, in nav order; `nav` ({ page, setupPending, playing }) is what
 *  their badges read; `update` is shell.pluginUpdate. */
export function StudioNav({ pages, nav, onGo, onRefresh, refreshing, viaProfile = null, update = null }) {
  const page = nav.page

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
        children: pages.map(({ id, label, Badge }) =>
          jsxs(
            'button',
            {
              'aria-current': page === id ? 'page' : undefined,
              onClick: () => onGo(id),
              type: 'button',
              children: [label, Badge ? jsx(Badge, { nav }) : null]
            },
            id
          )
        )
      }),
      jsxs('div', {
        className: 'cs-top-end',
        children: [
          update ? jsx(UpdateChip, { update }, 'update') : null,
          jsx(Tip, {
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
          }, 'refresh')
        ]
      })
    ]
  })
}
