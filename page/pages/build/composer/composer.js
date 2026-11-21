// The message box of a Build conversation.
import { Button, Codicon, jsx, jsxs, Tip, useEffect, useLayoutEffect, useRef, useState, useValue } from '#sdk'
import { attachmentKey, mergeAttachments } from '#pages/build/chat/attachments.js'
import { BUILD_INJECT } from '#pages/build/chat/store.js'
import { AGENT } from '#app/ids.js'
import { AttachmentChip } from './attachment-chip.js'
import { later, MENTION_AT, MentionPicker, useProjectAssets } from './mentions.js'

/** Attach files (an asset, a frame, annotated objects) to the next message of a Build conversation,
 *  with `text` to finish. `attachments`: a list (#pages/build/chat/attachments.js). */
export function attachToBuild(stored, attachments, text = '') {
  const all = BUILD_INJECT.get()
  const current = all[stored]

  BUILD_INJECT.set({ ...all, [stored]: { seq: (current?.seq ?? 0) + 1, text, attach: attachments } })
}

export function BuildComposer({ busy, disabled, placeholder, onSend, onStop, stored = null, status = null, picker = null, game = null, fresh = false }) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState([])
  const [mention, setMention] = useState(null)
  const [pick, setPick] = useState(0)
  const inject = useValue(BUILD_INJECT)[stored ?? ''] ?? null
  const box = useRef(null)
  const assets = useProjectAssets(mention && game ? game.id : null, mention ? 'open' : 'closed')
  const query = (mention?.query ?? '').toLowerCase()
  const matches = Array.isArray(assets)
    ? assets.filter(item => !query || String(item.name).toLowerCase().includes(query) || String(item.file ?? '').toLowerCase().includes(query)).slice(0, 8)
    : assets === false
      ? []
      : null

  // Ask about an asset or a frame (or Make cover art on the Games page) adds it here for the user to finish
  // and send. Each draft is used once, also when it was left before this box was on screen.
  useEffect(() => {
    if (inject && !inject.used) {
      BUILD_INJECT.set({ ...BUILD_INJECT.get(), [stored ?? '']: { ...inject, used: true } })

      if (inject.attach?.length) {
        setAttachments(current => mergeAttachments(current, inject.attach))
      }

      if (inject.text) {
        setText(current => (current.trim() ? `${current.trimEnd()}\n${inject.text}` : inject.text))
      }

      const focus = () => box.current?.focus?.()

      if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(focus)
      } else {
        focus()
      }
    }
  }, [inject?.seq, stored])

  // Grow with the text, up to a limit.
  useLayoutEffect(() => {
    const element = box.current

    if (element) {
      element.style.height = 'auto'
      element.style.height = `${Math.min(element.scrollHeight, 200)}px`
    }
  }, [text])

  // Typing @ (after a space or at the start) opens the asset list; what follows filters it.
  const track = (value, caret) => {
    const found = game ? MENTION_AT.exec(value.slice(0, caret ?? value.length)) : null

    if (found) {
      setMention({ start: (caret ?? value.length) - found[2].length - 1, query: found[2] })
      setPick(0)
    } else {
      setMention(null)
    }
  }

  const choose = item => {
    if (!item || !mention) {
      return
    }

    const element = box.current
    const caret = element?.selectionStart ?? text.length
    const next = `${text.slice(0, mention.start)}${text.slice(caret)}`.replace(/^\s+$/, '')

    setText(next)
    setAttachments(current => mergeAttachments(current, [{ path: item.path, name: item.name }]))
    setMention(null)
    later(() => {
      element?.focus?.()
      element?.setSelectionRange?.(mention.start, mention.start)
    })
  }

  const openPicker = () => {
    const element = box.current
    const caret = element?.selectionStart ?? text.length
    const before = text.slice(0, caret)
    const insert = before && !/\s$/.test(before) ? ' @' : '@'
    const value = `${before}${insert}${text.slice(caret)}`

    setText(value)
    setMention({ start: caret + insert.length - 1, query: '' })
    setPick(0)
    later(() => {
      element?.focus?.()
      element?.setSelectionRange?.(caret + insert.length, caret + insert.length)
    })
  }

  const send = async () => {
    const value = text.trim()

    if ((!value && !attachments.length) || disabled) {
      return
    }

    // A first edit may be refused before the transcript takes over, including retries. Keep its draft until then.
    if (fresh && !(await onSend(value, attachments))) {
      return
    }
    setText('')
    setAttachments([])
    setMention(null)
    if (!fresh) {
      void onSend(value, attachments)
    }
  }

  return jsxs('div', {
    className: 'cs-b-comp',
    children: [
      status,
      mention && game ? jsx(MentionPicker, { index: pick, items: matches, onHover: setPick, onPick: choose, query: mention.query }) : null,
      attachments.length
        ? jsx('div', {
            className: 'cs-b-chips',
            children: attachments.map(item =>
              jsx(AttachmentChip, { item, onRemove: gone => setAttachments(current => current.filter(entry => attachmentKey(entry) !== attachmentKey(gone))) }, attachmentKey(item))
            )
          })
        : null,
      jsx('textarea', {
        'aria-label': 'Message Hermes',
        disabled,
        onBlur: () => setMention(null),
        onChange: event => {
          setText(event.target.value)
          track(event.target.value, event.target.selectionStart)
        },
        onKeyDown: event => {
          if (mention && game) {
            const count = matches?.length ?? 0

            if (event.key === 'Escape') {
              event.preventDefault()
              setMention(null)

              return
            }

            if (count && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
              event.preventDefault()
              setPick(value => (value + (event.key === 'ArrowDown' ? 1 : count - 1)) % count)

              return
            }

            if (count && (event.key === 'Enter' || event.key === 'Tab') && !event.shiftKey) {
              event.preventDefault()
              choose(matches[Math.min(pick, count - 1)])

              return
            }
          }

          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent?.isComposing) {
            event.preventDefault()
            send()
          }
        },
        placeholder,
        ref: box,
        rows: 1,
        value: text
      }),
      jsxs('div', {
        className: 'cs-b-comp-row',
        children: [
          game
            ? jsx(Tip, {
                label: 'Point at a sprite, background or cover',
                children: jsx('span', {
                  style: { display: 'inline-flex' },
                  children: jsxs(Button, { 'aria-label': 'Mention an asset', disabled, onClick: openPicker, size: 'sm', variant: 'ghost', children: ['@', jsx('span', { className: 'cs-lbl', children: 'Asset' })] })
                })
              })
            : null,
          picker,
          jsx('span', { className: 'cs-grow' }),
          busy
            ? jsx(Tip, {
                label: `Stop ${AGENT}`,
                children: jsxs('button', { 'aria-label': 'Stop', className: 'cs-b-stop', onClick: onStop, type: 'button', children: [jsx('i', {}), jsx('span', { className: 'cs-sr', children: 'Stop' })] })
              })
            : null,
          jsx('button', {
            'aria-label': 'Send',
            className: 'cs-b-send',
            disabled: disabled || (!text.trim() && !attachments.length),
            onClick: send,
            type: 'button',
            children: [jsx(Codicon, { name: 'arrow-up', size: 14 }, 'icon'), jsx('span', { className: 'cs-sr', children: 'Send' }, 'label')]
          })
        ]
      })
    ]
  })
}
