// The Change tab and its draft.
import { Button, Codicon, jsx, jsxs, useEffect, useRef, useState } from '#sdk'
import { AGENT } from '#app/ids.js'
import { baseName } from '#app/paths.js'
import { stepWords } from '#pages/build/transcript/step-words.js'
import { versionTime } from './version-history.js'

export function ChangeForm({ active, area, asks, chat, image, kind, loaded, name, onArea, onSend, onSent, path, progress, showProgress, shownView, version }) {
  const [request, setRequest] = useState('')
  const [rebuild, setRebuild] = useState(true)
  const input = useRef(null)
  const { older, shownEntry, shownNumber } = version
  const showForm = active && !showProgress

  useEffect(() => {
    if (showForm) {
      input.current?.focus()
    }
  }, [showForm])

  if (!active) {
    return null
  }

  const send = () => {
    const words = request.trim()

    if (!words || !onSend) {
      return
    }

    const notes = []

    if (area && image) {
      notes.push(`Only change the area from (${area.x}, ${area.y}) to (${area.x + area.w - 1}, ${area.y + area.h - 1}), in pixels of the ${image.naturalWidth}×${image.naturalHeight} image. Keep everything outside it exactly as it is.`)
    }

    if (older && shownEntry) {
      notes.push(`Start from version ${shownNumber} (from ${versionTime(shownEntry)}), kept at ${shownEntry.file}. The file in the game is a newer version.`)
    }

    if (rebuild && (kind === 'sprite' || kind === 'background')) {
      notes.push('When it is done, build the game and show it to me with chromatic_present_game.')
    }

    const text = notes.length ? `${words}\n\n${notes.map(note => `- ${note}`).join('\n')}` : words

    onSend(text, area ? `${words} (the marked area)` : words, [{ path, name: loaded?.name ?? baseName(path) }])
    setRequest('')
    onSent()
  }

  return showProgress
    ? [
        jsxs('div', {
          className: 'cs-v-card',
          children: [jsx('span', { className: 'cs-faint', children: 'You asked' }), jsx('span', { className: 'cs-v-text', children: chat?.items?.findLast?.(item => item.kind === 'user')?.text ?? '' })]
        }, 'asked'),
        jsxs('div', {
          className: 'cs-col cs-v-sec',
          children: [
            jsx('span', { className: 'cs-eyebrow', children: 'Progress' }),
            ...(progress.length ? progress : []).map(tool =>
              jsxs('span', {
                className: `cs-v-step ${tool.state}`,
                children: [tool.state === 'running' ? jsx('span', { className: 'cs-b-spin' }) : jsx(Codicon, { name: tool.state === 'failed' ? 'error' : 'check', size: 12 }), stepWords(tool)[tool.state === 'running' ? 0 : 1]]
              }, tool.id)
            ),
            !progress.length ? jsx('span', { className: 'cs-faint', children: 'Starting…' }) : null
          ]
        }, 'progress'),
        jsx('span', { className: 'cs-grow' }, 'grow'),
        jsx('span', { className: 'cs-faint', children: 'You can close this. The new version shows up here and in the chat.' }, 'close')
      ]
    : [
        jsx('textarea', {
          className: 'cs-v-input',
          disabled: !onSend,
          onChange: event => setRequest(event.target.value),
          onKeyDown: event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent?.isComposing) {
              event.preventDefault()
              send()
            }
          },
          placeholder: onSend ? `What should ${AGENT} change in ${name}?` : 'Open this game\u2019s conversation to ask for changes.',
          ref: input,
          rows: 4,
          value: request
        }, 'input'),
        area
          ? jsxs('div', {
              className: 'cs-row cs-v-sec',
              style: { gap: 6 },
              children: [jsx('span', { className: 'cs-v-text', children: `Only the marked area · ${area.w}×${area.h}` }), jsx('span', { className: 'cs-grow' }), jsx(Button, { onClick: () => onArea(null), size: 'sm', variant: 'ghost', children: 'Clear' })]
            }, 'area')
          : shownView === 'Image' || shownView === 'Sheet'
            ? jsx('span', { className: 'cs-faint', children: 'Drag on the picture to change just one area.' }, 'area')
            : null,
        older ? jsx('span', { className: 'cs-faint', children: `It starts from v${shownNumber}, the version shown.` }, 'from') : null,
        kind === 'sprite' || kind === 'background'
          ? jsxs('label', { className: 'cs-v-toggle', children: [jsx('input', { checked: rebuild, onChange: event => setRebuild(event.target.checked), type: 'checkbox' }), 'Build and show the game after'] }, 'rebuild')
          : null,
        jsxs(Button, { disabled: !onSend || !request.trim(), onClick: send, size: 'sm', children: [`Send to ${AGENT}`, jsx('span', { className: 'cs-v-kbd', children: '\u21b5' })] }, 'send'),
        jsx('span', { className: 'cs-grow' }, 'grow'),
        asks.length
          ? jsxs('div', {
              className: 'cs-col cs-v-sec',
              children: [jsx('span', { className: 'cs-eyebrow', children: 'Asked before' }), ...asks.slice(-4).map((ask, position) => jsx('span', { className: 'cs-faint', title: ask, children: `\u201c${ask.length > 80 ? `${ask.slice(0, 80)}…` : ask}\u201d` }, position))]
            }, 'asks')
          : null
      ]

}
