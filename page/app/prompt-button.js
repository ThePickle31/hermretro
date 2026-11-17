// A button that puts a prompt into a chat.
import { jsx } from '#sdk'
import { sendPromptToChat } from './chat-insert.js'
import { AsyncButton } from '#shared/ui/page.js'

/** A plain button that puts a prompt into a chat. */
export function PromptButton({ ctx, label, prompt, variant = 'outline', fresh = false, disabled }) {
  return jsx(AsyncButton, { disabled, icon: 'comment-discussion', run: () => sendPromptToChat(ctx, prompt, { fresh }), title: 'Puts the prompt in a chat, not sent', variant, children: label })
}
