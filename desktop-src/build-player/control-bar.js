// The inline player's one bar: what is playing, then scale (or the Chromatic finish), the Chromatic
// and Play-test toggles, Annotate, sound, pause, screenshot, more, full screen and close. Every
// control the ModRetro player draws around the game lives here instead.
import { Codicon, jsx, jsxs } from '../sdk.js'
import { AGENT } from '../core/ids.js'
import { moveFocus } from './arrow-keys.js'
import { BarMenu } from './menu.js'
import { FINISHES } from './prefs.js'
import { SCALES } from './scale.js'

const scaleLabel = scale => (scale === 'fit' ? 'Fit' : `${scale}\u00d7`)

export function BarButton({ icon, label, text = null, onClick, pressed, disabled = false, primary = false }) {
  return jsxs('button', {
    'aria-label': label,
    'aria-pressed': pressed,
    className: `cs-ip-btn${primary ? ' primary' : ''}`,
    disabled,
    onClick,
    title: label,
    type: 'button',
    children: [jsx(Codicon, { name: icon, size: 14 }), text ? jsx('span', { className: 'cs-ip-lbl', children: text }) : null]
  })
}

function ScalePicker({ scale, fits, onScale }) {
  // One tab stop for the group; the arrows pick (radio buttons).
  const pick = event => {
    const target = moveFocus(event, event.currentTarget, '[role=radio]')

    if (target) {
      onScale(SCALES[Number(target.dataset.index)])
    }
  }

  return jsx('span', {
    'aria-label': 'Size',
    className: 'cs-ip-seg',
    onKeyDown: pick,
    role: 'radiogroup',
    children: SCALES.map((entry, index) =>
      jsx(
        'button',
        {
          'aria-checked': entry === scale,
          'data-index': index,
          disabled: !fits.includes(entry),
          onClick: () => onScale(entry),
          role: 'radio',
          tabIndex: entry === scale ? 0 : -1,
          title: entry === 'fit' ? 'As big as fits, in whole steps' : `${entry} times the Game Boy screen`,
          type: 'button',
          children: scaleLabel(entry)
        },
        String(entry)
      )
    )
  })
}

export function ControlBar({ title, hint, prefs, setPrefs, fits, frame, ready, panelToggle, onAnnotate, onShot, onMore, onFull, onClose }) {
  const finish = FINISHES.find(entry => entry.id === prefs.finish) ?? FINISHES[0]

  return jsxs('div', {
    className: 'cs-ip-bar',
    children: [
      jsx('span', { className: ready && !frame.paused ? 'cs-b-live on' : 'cs-b-live' }),
      jsx('b', { className: 'cs-ip-title', children: `Playing ${title}` }),
      jsx('span', { className: 'cs-faint cs-ip-hint', children: hint }),
      jsx('span', { className: 'cs-grow' }),
      prefs.view === 'device'
        ? jsx(BarMenu, {
            icon: 'symbol-color',
            items: FINISHES.map(entry => ({ id: entry.id, label: entry.name, swatch: entry.swatch, checked: entry.id === finish.id })),
            label: 'Chromatic finish',
            onPick: id => setPrefs({ finish: id }),
            text: finish.name
          })
        : jsx(ScalePicker, { fits, onScale: scale => setPrefs({ scale }), scale: prefs.scale }),
      jsx(BarButton, { icon: 'device-mobile', label: 'Show the Chromatic around the game', onClick: () => setPrefs({ view: prefs.view === 'device' ? 'screen' : 'device' }), pressed: prefs.view === 'device', text: 'Chromatic' }),
      panelToggle,
      jsx('span', { className: 'cs-ip-sep' }),
      jsx(BarButton, { disabled: !ready, icon: 'inspect', label: `Annotate: point at things in the game for ${AGENT}`, onClick: onAnnotate, text: 'Annotate' }),
      jsx(BarButton, { disabled: !ready, icon: frame.muted ? 'mute' : 'unmute', label: frame.muted ? 'Turn the sound on' : 'Mute', onClick: () => frame.press('sound') }),
      jsx(BarButton, { disabled: !ready, icon: frame.paused ? 'play' : 'debug-pause', label: frame.paused ? 'Resume' : 'Pause', onClick: () => frame.press('play') }),
      jsx(BarButton, { disabled: !ready, icon: 'device-camera', label: "Screenshot into the game's captures", onClick: onShot }),
      jsx(BarMenu, {
        disabled: !ready,
        icon: 'ellipsis',
        items: [
          { id: 'restart', icon: 'debug-restart', label: 'Restart the game' },
          { id: 'record', icon: frame.recording ? 'debug-stop' : 'record', label: frame.recording ? 'Stop recording' : 'Record a video' }
        ],
        label: 'More',
        onPick: onMore
      }),
      jsx(BarButton, { disabled: !ready, icon: 'screen-full', label: 'Full screen', onClick: onFull }),
      jsx(BarButton, { icon: 'close', label: 'Close the game', onClick: onClose })
    ]
  })
}
