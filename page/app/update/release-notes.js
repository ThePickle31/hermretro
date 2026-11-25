// What each release changed (the releases RPC's notes), grouped as New and Fixed: the update card and the dialog.
import { jsx, jsxs } from '#sdk'

const GROUPS = [
  ['new', 'New'],
  ['fixed', 'Fixed']
]

function Release({ release, dated }) {
  const groups = GROUPS.map(([kind, label]) => [kind, label, release.notes.filter(note => note.kind === kind)]).filter(([, , notes]) => notes.length)
  const date = release.date ? new Date(release.date).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : ''

  return jsxs('section', {
    className: 'cs-upd-rel',
    children: [
      dated ? jsxs('div', { className: 'cs-upd-relh', children: [jsx('b', { children: `v${release.version}` }), date ? jsx('span', { children: date }) : null] }) : null,
      ...groups.map(([kind, label, notes]) =>
        jsxs(
          'div',
          {
            className: 'cs-upd-grp',
            children: [jsx('span', { className: 'cs-upd-tag', 'data-kind': kind, children: label }), jsx('ul', { children: notes.map((note, i) => jsx('li', { children: note.text }, i)) })]
          },
          kind
        )
      )
    ]
  })
}

/** `releases` newest first; null when there are none with notes. */
export function ReleaseNotes({ releases }) {
  const shown = (releases ?? []).filter(release => release.notes?.length)

  if (!shown.length) {
    return null
  }

  return jsx('div', {
    className: 'cs-upd-notes',
    children: shown.map(release => jsx(Release, { dated: shown.length > 1, release }, release.version))
  })
}
