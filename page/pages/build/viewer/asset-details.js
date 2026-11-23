// The Details tab beside the picture.
import { Button, Codicon, jsx, jsxs } from '#sdk'
import { AGENT } from '#app/ids.js'
import { timeOfDay } from '#shared/ui/time.js'
import { versionTime } from './version-history.js'

export function AssetDetails({ asset, checks, copyColour, gameColours, info, kind, palette, setGameColours, version, restoreBlocked }) {
  const { currentId, older, restore, restoring, setPicked, shownEntry, shownNumber, versions } = version
  const madeBy = asset.step || asset.at
    ? jsxs('div', {
        className: 'cs-col cs-v-sec',
        children: [
          jsx('span', { className: 'cs-eyebrow', children: asset.step === 'In the reply' ? `Shown by ${AGENT}` : `Made by ${AGENT}` }),
          asset.ask ? jsx('span', { className: 'cs-v-quote', children: `\u201c${asset.ask.length > 140 ? `${asset.ask.slice(0, 140)}…` : asset.ask}\u201d` }) : null,
          jsx('span', { className: 'cs-faint', children: [asset.at ? timeOfDay(asset.at) : '', asset.step && asset.step !== 'In the reply' ? asset.step : ''].filter(Boolean).join(' · ') })
        ]
      })
    : null

  return [
    older
      ? jsxs('div', {
          className: 'cs-v-note',
          children: [
            jsx('span', { children: `This is v${shownNumber} from ${versionTime(shownEntry)}. The game uses v${versions.findIndex(entry => entry.current) + 1}.` }),
            jsxs('div', {
              className: 'cs-row',
              style: { gap: 6 },
              children: [
                jsx(Button, { disabled: restoring || restoreBlocked, onClick: () => void restore(), size: 'sm', children: restoring ? 'Restoring…' : `Restore v${shownNumber}` }),
                jsx(Button, { onClick: () => setPicked(currentId), size: 'sm', variant: 'ghost', children: 'Show the current one' })
              ]
            })
          ]
        }, 'older')
      : null,
    madeBy ? jsx('div', { children: madeBy }, 'made') : null,
    kind === 'sprite' && info?.palette
      ? jsxs('div', {
          className: 'cs-col cs-v-sec',
          children: [
            jsx('span', { className: 'cs-eyebrow', children: 'In-game palette' }),
            jsxs('div', {
              className: 'cs-row',
              style: { gap: 8 },
              children: [
                jsx('div', { className: 'cs-v-pal', children: info.palette.colors.map((color, position) => jsx('button', { onClick: () => void copyColour(color), style: { background: color }, title: `${color}${position === 2 ? ' (not used by sprites)' : ''}`, type: 'button' }, position)) }),
                info.palette.name ? jsx('span', { className: 'cs-tag', children: info.palette.name }) : null
              ]
            }),
            jsxs('label', { className: 'cs-v-toggle', children: [jsx('input', { checked: gameColours, onChange: event => setGameColours(event.target.checked), type: 'checkbox' }), 'Show it in these colours'] })
          ]
        }, 'palette')
      : null,
    palette.length
      ? jsxs('div', {
          className: 'cs-col cs-v-sec',
          children: [
            jsx('span', { className: 'cs-eyebrow', children: `Colours in the file · ${palette.length}${palette.length >= 32 ? '+' : ''}` }),
            jsx('div', { className: 'cs-v-sw', children: palette.map(color => jsx('button', { onClick: () => void copyColour(color), style: { background: color }, title: `${color} · click to copy`, type: 'button' }, color)) })
          ]
        }, 'colours')
      : null,
    checks.length
      ? jsxs('div', {
          className: 'cs-col cs-v-sec',
          children: [
            jsx('span', { className: 'cs-eyebrow', children: 'Checks' }),
            ...checks.map((check, position) => jsxs('span', { className: `cs-v-check${check.ok ? '' : ' bad'}`, children: [jsx(Codicon, { name: check.ok ? 'check' : 'warning', size: 12 }), check.text] }, position))
          ]
        }, 'checks')
      : null,
    kind === 'cover'
      ? jsxs('div', { className: 'cs-col cs-v-sec', children: [jsx('span', { className: 'cs-eyebrow', children: 'Shown on' }), jsx('span', { className: 'cs-v-text', children: 'Its Games page card and the Build page' })] }, 'shown')
      : info?.usedIn
        ? jsxs('div', {
            className: 'cs-col cs-v-sec',
            children: [
              jsx('span', { className: 'cs-eyebrow', children: 'Used in' }),
              ...(info.usedIn.length
                ? info.usedIn.map(use => jsxs('span', { className: 'cs-v-text', children: [jsx('b', { children: use.scene }), ` · ${use.count > 1 ? `${use.count}: ` : ''}${use.as.join(', ')}`] }, use.sceneId))
                : [jsx('span', { className: 'cs-faint', children: 'Not placed in any scene yet' }, 'none')])
            ]
          }, 'used')
        : null,
  ]
}
