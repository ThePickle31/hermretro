// The Prompts page (Reader).
import { Button, Codicon, CopyButton, jsx, jsxs, useEffect, useRef, useState } from '#sdk'
import { sendPromptToChat } from '#app/chat-insert.js'
import { Art } from '#shared/ui/art.js'
import { AsyncButton, PageHead } from '#shared/ui/page.js'
import { PromptButton } from '#app/prompt-button.js'
import { Small } from '#shared/ui/text.js'
import { ALL_PROMPTS, PROMPT_SECTIONS, promptById } from './library.js'

function fillPrompt(prompt, values) {
  return prompt.text.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? `{${key}}`)
}

function promptFields(prompt) {
  return [...new Set([...prompt.text.matchAll(/\{(\w+)\}/g)].map(match => match[1]))]
}

const WHAT_HAPPENS = {
  device: 'Hermes asks for your approval before it touches the device, unless Approvals are turned off.',
  create: 'Hermes creates the project in that folder, selects it for the chat and builds the first ROM. It then shows up on the Games page.',
  other: 'Works on the game selected in that chat. Start with Create if the chat has none yet.'
}

export function PromptsPage({ ctx, storage, selected, onSelect, gameReady, hardwareOn, profileLabel, defaultFolder, onSetUpDevice, onGo }) {
  const [query, setQuery] = useState('')
  const [edits, setEdits] = useState({})
  const [names, setNames] = useState({})
  const [folder, setFolder] = useState(() => {
    try {
      return storage.get('promptFolder', null)
    } catch {
      return null
    }
  })
  const listRef = useRef(null)

  const needle = query.trim().toLowerCase()
  const matches = prompt => !needle || `${prompt.title} ${prompt.text} ${prompt.section.title}`.toLowerCase().includes(needle)
  const visible = ALL_PROMPTS.filter(matches)
  const prompt = visible.find(item => item.id === selected) ?? visible[0] ?? promptById(selected)
  const locked = Boolean(prompt.hw) && !hardwareOn
  const values = { folder: folder ?? defaultFolder ?? '~', name: names[prompt.id] ?? prompt.defaults?.name ?? 'MyGame' }
  const text = edits[prompt.id] ?? fillPrompt(prompt, values)
  const fields = promptFields(prompt)
  const canChat = gameReady && !locked

  const state = useRef({})

  state.current = { visible, prompt, onSelect }

  // ↑ / ↓ move through the list (not while typing).
  useEffect(() => {
    const onKey = event => {
      if ((event.key !== 'ArrowDown' && event.key !== 'ArrowUp') || event.metaKey || event.ctrlKey || event.altKey) {
        return
      }

      const target = event.target

      if (target && (target.isContentEditable || /^(TEXTAREA|SELECT)$/.test(target.tagName ?? '') || (target.tagName === 'INPUT' && target.type !== 'search'))) {
        return
      }

      const { visible: list, prompt: current, onSelect: select } = state.current
      const index = list.findIndex(item => item.id === current.id)
      const next = list[Math.max(0, Math.min(list.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))]

      if (next) {
        event.preventDefault()
        select(next.id)
        ctx.setTimeout(() => listRef.current?.querySelector?.(`[data-prompt="${next.id}"]`)?.focus?.(), 0)
      }
    }

    window.addEventListener('keydown', onKey)

    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const setField = (key, value) => {
    setEdits(previous => ({ ...previous, [prompt.id]: undefined }))

    if (key === 'folder') {
      setFolder(value)

      try {
        storage.set('promptFolder', value)
      } catch {
        // remembered for this visit only
      }
    } else {
      setNames(previous => ({ ...previous, [prompt.id]: value }))
    }
  }

  const groups = PROMPT_SECTIONS.map(section => ({ section, items: visible.filter(item => item.section === section) })).filter(group => group.items.length)

  return [
    jsx(PageHead, {
      label: `Prompts · ${ALL_PROMPTS.length} ready to use`,
      lede: jsxs('span', {
        children: [
          'Every prompt opens a chat in ',
          jsx('span', { className: 'cs-mono', children: profileLabel }),
          ' with the text in its composer, ready for you to edit and send. Or copy it and paste it anywhere.'
        ]
      }),
      number: '02',
      title: 'Start building'
    }, 'head'),
    jsxs(
      'div',
      {
        className: 'cs-reader',
        children: [
          jsxs('nav', {
            'aria-label': 'Prompts',
            className: 'cs-rlist',
            ref: listRef,
            children: [
              jsxs('label', {
                className: 'cs-search',
                children: [
                  jsx(Codicon, { name: 'search', size: 14 }),
                  jsx('input', { 'aria-label': 'Find a prompt', onChange: event => setQuery(event.target.value), placeholder: 'Find a prompt', type: 'search', value: query })
                ]
              }),
              groups.length
                ? groups.flatMap(({ section, items }, index) => [
                    jsxs('span', { className: index ? 'cs-rgrp' : 'cs-rgrp first', children: [jsx('span', { children: section.title }), jsx('span', { children: items.length })] }, `g-${section.id}`),
                    ...items.map(item =>
                      jsxs(
                        'button',
                        {
                          'aria-current': item.id === prompt.id ? 'true' : undefined,
                          className: item.hw && !hardwareOn ? 'cs-ritem off' : 'cs-ritem',
                          'data-prompt': item.id,
                          onClick: () => onSelect(item.id),
                          type: 'button',
                          children: [jsx('span', { children: item.title }), item.hw && !hardwareOn ? jsx('span', { className: 'cs-tag quiet', children: 'device' }) : null]
                        },
                        item.id
                      )
                    )
                  ])
                : jsx(Small, { children: 'No prompts match.' }),
              jsxs('p', {
                className: 'cs-faint',
                style: { paddingTop: 18 },
                children: [jsx('span', { className: 'cs-key', children: '↑' }), ' ', jsx('span', { className: 'cs-key', children: '↓' }), ' to move through the list']
              })
            ]
          }),
          jsxs('section', {
            'aria-label': prompt.title,
            className: 'cs-rdetail',
            children: [
              jsxs('div', {
                className: 'cs-col',
                style: { gap: 10 },
                children: [
                  jsxs('p', {
                    className: 'cs-eyebrow',
                    children: [
                      jsx('span', { className: 'cs-accent', children: prompt.section.n }),
                      prompt.section.title,
                      jsx('span', { className: 'cs-tag quiet', children: prompt.src === 'modretro' ? 'ModRetro quickstart' : 'Hermes' }),
                      locked ? jsx('span', { className: 'cs-tag warn', children: 'Needs your Chromatic' }) : null
                    ]
                  }),
                  jsx('h3', { className: 'cs-word', style: { fontSize: 'clamp(28px, 3cqi, 52px)' }, children: prompt.title })
                ]
              }),
              fields.length
                ? jsx('div', {
                    className: 'cs-params',
                    children: fields.flatMap(key => [
                      jsx('label', { htmlFor: `cs-f-${key}`, children: key === 'folder' ? 'Parent folder' : 'Project name' }, `l-${key}`),
                      jsx('input', { id: `cs-f-${key}`, onChange: event => setField(key, event.target.value), spellCheck: false, value: values[key] }, `i-${key}`)
                    ])
                  })
                : null,
              jsx('textarea', {
                'aria-label': 'Prompt text',
                onChange: event => setEdits(previous => ({ ...previous, [prompt.id]: event.target.value })),
                spellCheck: false,
                value: text
              }),
              prompt.note ? jsx('p', { className: 'cs-faint', children: prompt.note }) : null,
              jsxs('div', {
                className: 'cs-actions',
                children: [
                  jsx(PromptButton, { ctx, disabled: !canChat, fresh: true, label: 'Start a new chat', prompt: text, variant: 'default' }),
                  jsx(AsyncButton, {
                    disabled: !canChat,
                    icon: 'insert',
                    run: () => sendPromptToChat(ctx, text),
                    title: 'Adds the prompt to the hermretro chat you were last in, else a new one',
                    variant: 'secondary',
                    children: 'Add to current chat'
                  }),
                  jsx(CopyButton, { buttonSize: 'sm', buttonVariant: 'outline', label: 'Copy', text }),
                  jsx('span', { className: 'cs-grow' }),
                  edits[prompt.id] !== undefined
                    ? jsx(Button, { onClick: () => setEdits(previous => ({ ...previous, [prompt.id]: undefined })), size: 'sm', variant: 'ghost', children: 'Reset text' })
                    : null
                ]
              }),
              locked
                ? jsxs('div', {
                    className: 'cs-note',
                    children: [
                      jsx(Small, { children: 'Streaming and flashing need your Chromatic set up. You can still read and copy those prompts.' }),
                      jsx(Button, { onClick: onSetUpDevice, size: 'sm', variant: 'outline', children: 'Set up my Chromatic' })
                    ]
                  })
                : !gameReady
                  ? jsxs('div', {
                      className: 'cs-note',
                      children: [
                        jsx(Small, { children: 'After setup: these prompts need the game toolchain, so the chat buttons turn on once it is installed.' }),
                        jsx(Button, { onClick: () => onGo('setup'), size: 'sm', variant: 'outline', children: 'Continue setup' })
                      ]
                    })
                  : null,
              jsxs('div', {
                className: 'cs-uses',
                children: [
                  jsx('p', { className: 'cs-eyebrow', children: 'What happens' }),
                  jsx(Small, { children: prompt.hw ? WHAT_HAPPENS.device : prompt.section.id === 'create' ? WHAT_HAPPENS.create : WHAT_HAPPENS.other }),
                  jsx('span', { className: 'cs-faint', children: 'Nothing is sent until you press send in the chat.' })
                ]
              })
            ]
          }),
          jsx(Art, {})
        ]
      },
      'reader'
    )
  ]
}

/** The page's own Page: the prompt library, fed from the shell. */
export function Prompts({ shell }) {
  return jsx(PromptsPage, {
    ctx: shell.ctx,
    defaultFolder: shell.newGameFolder,
    gameReady: shell.gameReady,
    hardwareOn: shell.hardwareOn,
    onGo: shell.go,
    onSelect: shell.setPromptId,
    onSetUpDevice: shell.setUpDevice,
    profileLabel: shell.profileLabel,
    selected: shell.promptId,
    storage: shell.ctx.storage
  })
}
