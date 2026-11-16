// A prompt with its actions (use in chat, copy).
import { Button, Codicon, CopyButton, jsx, jsxs, useState } from '../sdk.js'
import { sendPromptToChat } from '../core/chat-insert.js'

function PromptActions({ ctx, prompt, primaryLabel = 'Use in chat', primaryVariant = 'secondary' }) {
  const [pending, setPending] = useState(false)

  const run = async () => {
    if (pending) {
      return
    }

    setPending(true)

    try {
      await sendPromptToChat(ctx, prompt)
    } finally {
      setPending(false)
    }
  }

  return jsxs('div', {
    className: 'cs-actions',
    children: [
      jsxs(Button, {
        disabled: pending,
        onClick: () => void run(),
        size: 'sm',
        variant: primaryVariant,
        children: [jsx(Codicon, { name: pending ? 'loading' : 'comment-discussion', size: 14, spinning: pending }), primaryLabel]
      }),
      jsx(CopyButton, { buttonSize: 'sm', buttonVariant: 'outline', label: 'Copy', text: prompt })
    ]
  })
}

/** A prompt shown in full, with the buttons that use it. */
export function PromptBlock({ ctx, prompt, label }) {
  return jsxs('div', {
    className: 'cs-col',
    style: { gap: 10 },
    children: [jsx('p', { className: 'cs-prompt', children: prompt }), jsx(PromptActions, { ctx, primaryLabel: label, primaryVariant: 'default', prompt })]
  })
}
