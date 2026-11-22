// The status line above the message box.
import { Button, jsx, jsxs } from '#sdk'
import { openInFullChat } from '#pages/build/chat/actions.js'
import { AGENT } from '#app/ids.js'
import { clock, useNow } from '#shared/ui/time.js'
import { stepWords } from './step-words.js'

/** What the agent is doing, in words, above the message box. It says so honestly when nothing has come
 *  in for a while, and when the connection is the problem. */
export function BuildStatus({ chat, onStop }) {
  const now = useNow(Boolean(chat?.busy))

  if (!chat?.busy) {
    return null
  }

  const quietFor = now - (chat.lastEventAt ?? now)
  const running = [...chat.items].reverse().find(item => item.kind === 'tools' && item.tools.some(tool => tool.state === 'running'))
  const tool = running ? [...running.tools].reverse().find(entry => entry.state === 'running') : null
  const waiting = chat.waiting || chat.items.some(item => (item.kind === 'clarify' || item.kind === 'approval') && !item.answered)
  const slow = tool && /rom_build|web_build|toolchain_prepare|emulator_step|flash/.test(tool.name)
  let tone = ''
  let headline
  let detail = null

  if (waiting) {
    tone = 'wait'
    headline = `${AGENT} is waiting for your answer` // the question is in the message box below
  } else if ((chat.unreachable ?? 0) >= 3) {
    tone = 'warn'
    headline = 'Reconnecting to Hermes…'
    detail = 'The work carries on; this page catches up when it reconnects.'
  } else {
    headline = tool
      ? `${AGENT} is ${stepWords(tool)[0].replace(/^./, letter => letter.toLowerCase())}`
      : chat.activity === 'writing'
        ? `${AGENT} is writing`
        : chat.activity === 'compacting'
          ? `${AGENT} is tidying up the conversation`
          : chat.activity === 'preparing'
            ? `${AGENT} is getting the next step ready`
            : `${AGENT} is thinking`

    // Builds and installs can run for minutes without a word: give them longer before saying so.
    if (quietFor >= (slow ? 600_000 : 180_000)) {
      tone = 'stuck'
      headline = `${AGENT} has been quiet for ${Math.floor(quietFor / 60_000)} minutes`
      detail = 'It may be stuck. Look in the full chat, or stop it.'
    } else if (quietFor >= 45_000) {
      detail = slow ? `Nothing new for ${Math.round(quietFor / 1000)}s. That is normal for this step.` : `Nothing new for ${Math.round(quietFor / 1000)}s. Still working.`
    } else {
      detail = quietFor < 3_000 ? 'just now' : `last update ${Math.round(quietFor / 1000)}s ago`
    }
  }

  return jsxs('div', {
    'aria-live': 'polite',
    className: `cs-b-status ${tone}`,
    role: 'status',
    children: [
      jsx('span', { className: tone === 'wait' ? 'cs-b-pulse wait' : tone === 'stuck' || tone === 'warn' ? 'cs-b-pulse off' : 'cs-b-pulse' }),
      jsx('b', { children: headline }),
      detail ? jsx('span', { className: 'cs-faint', children: detail }) : null,
      jsx('span', { className: 'cs-grow' }),
      chat.turnStartedAt ? jsx('span', { className: 'cs-b-dur', children: clock(now - chat.turnStartedAt) }) : null,
      tone === 'stuck' && chat.stored ? jsx(Button, { onClick: () => openInFullChat(chat.stored), size: 'sm', variant: 'ghost', children: 'Open full chat' }) : null,
      tone === 'stuck' ? jsx(Button, { onClick: onStop, size: 'sm', variant: 'outline', children: 'Stop' }) : null
    ]
  })
}
