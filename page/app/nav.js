// The header: wordmark and the one segmented control.
import { Codicon, jsx, jsxs, Tip } from '#sdk'
import { UpdateChip } from './update/chip.js'

/** Wordmark, one segmented control (always in the same place) and the update chip (only while an update is ready or
 *  running). `pages` are the registry's, in nav order; `nav` ({ page, setupPending, playing }) is what
 *  their badges read; `update` is shell.pluginUpdate. */
export function StudioNav({ pages, nav, onGo, viaProfile = null, update = null }) {
  const page = nav.page

  return jsxs('header', {
    className: 'cs-top',
    children: [
      jsxs('div', {
        className: 'cs-top-start',
        children: [
          jsxs('button', {
            'aria-label': 'hermretro: Build',
            className: 'cs-brand',
            onClick: () => onGo('build'),
            type: 'button',
            children: ['herm', jsx('span', { children: 'retro' })]
          }),
          // The profile the studio works in, when it is not the one the app is on: a quiet chip, the
          // explanation in its tooltip.
          viaProfile
            ? jsx(Tip, {
                label: `Showing the "${viaProfile}" profile, where hermretro is switched on.`,
                children: jsxs('span', {
                  'aria-label': `Showing the "${viaProfile}" profile, where hermretro is switched on.`,
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
      jsx('div', {
        className: 'cs-top-end',
        children: update ? jsx(UpdateChip, { update }) : null
      })
    ]
  })
}
