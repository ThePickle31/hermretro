// Gateway events folded into a conversation.
import { reportOf } from './report.js'
import { stepArgs, stepInfo, toolFailed, withInfo } from './steps.js'
import { unwrapCalls } from './tool-results.js'

const lastItem = chat => chat.items[chat.items.length - 1]

/** Close the assistant text that is streaming, so what follows starts a new block. */
export function sealText(chat) {
  const last = lastItem(chat)

  return last?.kind === 'assistant' && last.open
    ? { ...chat, items: [...chat.items.slice(0, -1), { ...last, open: false }] }
    : chat
}

function appendText(chat, text) {
  const last = lastItem(chat)

  if (last?.kind === 'assistant' && last.open) {
    return { ...chat, items: [...chat.items.slice(0, -1), { ...last, text: last.text + text }] }
  }

  return { ...chat, items: [...chat.items, { kind: 'assistant', open: true, text }] }
}

/** Update the pending occurrence of a call in the current turn, including any wrapped steps. */
function updateTool(chat, id, change) {
  if (!id) {
    return chat
  }

  const matches = tool => tool.callId === id && tool.state === 'running' && tool.turn === (chat.turn ?? null)

  for (let index = chat.items.length - 1; index >= 0; index--) {
    const item = chat.items[index]

    if ((item.kind === 'user' && !item.followup) || item.kind === 'end') {
      break
    }

    if (item.kind === 'tools' && item.tools.some(matches)) {
      const items = [...chat.items]

      items[index] = { ...item, tools: item.tools.map(tool => matches(tool) ? change(tool) : tool) }

      return { ...chat, items }
    }
  }

  return chat
}

/** Record that something happened (for "last update" and the quiet / stuck states), at most twice a
 *  second so a stream of tokens does not re-render the page for this alone. */
function touched(chat, now = Date.now()) {
  return now - (chat.lastEventAt ?? 0) > 500 ? { ...chat, lastEventAt: now } : chat
}

function withActivity(chat, activity) {
  return chat.activity === activity ? chat : { ...chat, activity }
}

/** The end of a turn, as an item: the transcript closes the turn's "Worked for…" with it. */
export function endTurn(chat, status, now = Date.now()) {
  const items = sealText(chat).items.map(item =>
    item.kind === 'tools' && item.tools.some(tool => tool.state === 'running')
      ? { ...item, tools: item.tools.map(tool => (tool.state === 'running' ? { ...tool, state: status === 'interrupted' ? 'stopped' : 'done' } : tool)) }
      : item
  )

  return {
    ...chat,
    items: [...items, { kind: 'end', status, at: now, startedAt: chat.turnStartedAt ?? null }],
    busy: false,
    waiting: false,
    turnText: 0,
    activity: null,
    turnStartedAt: null,
    lastCompleteAt: now,
    lastEventAt: now
  }
}

/** Turns the gateway lost when it restarted mid-turn (`pending` rows fenced "unknown"). Each one
 *  pauses the conversation: messages after it wait until it is dropped (`prompt.resolve_unknown`). */
export function lostTurns(pending) {
  return Array.isArray(pending)
    ? pending.filter(row => row?.status === 'unknown' && typeof row.admission_id === 'string').map(row => ({ id: row.admission_id }))
    : []
}

/** One gateway event into the conversation it belongs to. Pure (apart from the clock), so the tests can
 *  drive it. */
export function reduceChat(chat, event) {
  const payload = event.payload ?? {}

  // Frames are numbered per session and per gateway run (`replay_epoch`): a restarted gateway counts
  // from 1 again, so a new epoch resets the watermark instead of dropping everything as seen.
  const epoch = event.replay_epoch ?? payload.replay_epoch

  if (typeof epoch === 'string' && epoch !== chat.epoch) {
    chat = { ...chat, epoch, seq: null, segments: {} }
  }

  if (typeof event.seq === 'number') {
    if (typeof chat.seq === 'number' && event.seq <= chat.seq) {
      return chat
    }

    chat = { ...chat, seq: event.seq }
  }

  const now = Date.now()

  if (event.type?.startsWith('tool.') && payload.turn_id && chat.turn && (
    payload.turn_id !== chat.turn || (!chat.busy && lastItem(chat)?.kind === 'end')
  )) {
    return chat
  }

  switch (event.type) {
    case 'message.start': {
      // A queued message's turn starts: it joins the conversation.
      const [next, ...rest] = !chat.busy || lastItem(chat)?.kind === 'end' ? (chat.queued ?? []) : []

      if (next) {
        chat = { ...sealText(chat), items: [...sealText(chat).items, { ...next, at: now }], queued: rest }
      }

      return {
        ...sealText(chat),
        busy: true,
        turn: payload.turn_id ?? null,
        turnText: 0,
        segments: {},
        activity: 'thinking',
        turnStartedAt: chat.busy && chat.turnStartedAt ? chat.turnStartedAt : now,
        lastEventAt: now
      }
    }

    case 'message.delta': {
      if (payload.text == null) {
        return sealText(chat)
      }

      let text = String(payload.text)

      // `offset` counts the segment's UTF-16 units already sent: drop what was applied before.
      if (typeof payload.offset === 'number') {
        const key = `${payload.turn_id ?? ''}:${payload.segment ?? 0}`
        const applied = chat.segments?.[key] ?? 0

        if (payload.offset + text.length <= applied) {
          return chat
        }

        text = payload.offset < applied ? text.slice(applied - payload.offset) : text
        chat = { ...chat, segments: { ...chat.segments, [key]: payload.offset + payload.text.length } }
      }

      return text ? touched(withActivity({ ...appendText(chat, text), turnText: (chat.turnText ?? 0) + text.length }, 'writing'), now) : chat
    }

    case 'reasoning.delta':
    case 'thinking.delta':
      return chat.busy ? touched(withActivity(chat, 'thinking'), now) : chat

    case 'status.update': {
      const kind = String(payload.kind ?? '')

      if (/compress|compact/.test(kind) && chat.busy) {
        return touched(withActivity(chat, 'compacting'), now)
      }

      return chat.activity === 'compacting' && kind === 'ready' ? withActivity(chat, 'thinking') : chat
    }

    case 'message.interim':
      return payload.already_streamed || !payload.text
        ? sealText(chat)
        : { ...sealText(chat), items: [...sealText(chat).items, { kind: 'assistant', open: false, text: String(payload.text) }], turnText: (chat.turnText ?? 0) + 1 }

    case 'tool.generating':
      return chat.busy ? touched(withActivity(chat, 'preparing'), now) : chat

    case 'tool.start': {
      if (payload.tool_id != null && updateTool(chat, payload.tool_id, tool => tool) !== chat) {
        return chat
      }

      const sealed = sealText(chat)
      // Hermes runs deferred tools through `tool_call`: the step is the call inside it.
      const tools = unwrapCalls(payload.tool_id ?? `t${now}`, String(payload.name ?? ''), payload.args).map(call => ({
        id: call.id,
        callId: payload.tool_id,
        turn: chat.turn ?? null,
        name: call.name,
        args: stepArgs(call.args),
        report: reportOf(call.name, call.args),
        preview: payload.preview ?? payload.context ?? null,
        state: 'running',
        startedAt: now
      }))
      const last = lastItem(sealed)
      const items =
        last?.kind === 'tools'
          ? [...sealed.items.slice(0, -1), { ...last, tools: [...last.tools, ...tools] }]
          : [...sealed.items, { kind: 'tools', tools }]

      return { ...sealed, items, activity: 'tool', lastEventAt: now }
    }

    case 'tool.progress': {
      const progress = { percent: typeof payload.percent === 'number' ? payload.percent : null, message: payload.message ?? null }

      return touched(updateTool(chat, payload.tool_id, tool => ({ ...tool, progress })), now)
    }

    case 'tool.complete': {
      const calls = unwrapCalls(payload.tool_id || `t${now}`, String(payload.name ?? ''), payload.args)
      const done = tool => ({
        ...tool,
        args: tool.args ?? stepArgs(payload.args),
        report: tool.report ?? reportOf(tool.name, calls[0]?.args),
        state: toolFailed(payload) ? 'failed' : 'done',
        summary: payload.summary ?? null,
        finishedAt: now,
        duration: typeof payload.duration_s === 'number' ? payload.duration_s : tool.startedAt ? (now - tool.startedAt) / 1000 : null,
        image: typeof payload.image_path === 'string' ? payload.image_path : null,
        info: stepInfo(tool.name, payload.result, tool.id === payload.tool_id || (!payload.tool_id && calls.length === 1)),
        progress: null
      })
      const updated = updateTool(chat, payload.tool_id, done)
      // A completion whose start was never seen (opened mid-turn) still shows up.
      const next = updated !== chat
        ? updated
        : {
            ...sealText(chat),
            items: [
              ...sealText(chat).items,
              { kind: 'tools', tools: calls.map(call => done({ id: call.id, name: call.name, args: stepArgs(call.args), report: reportOf(call.name, call.args) })) }
            ]
          }

      return { ...next, activity: chat.busy ? 'thinking' : chat.activity, lastEventAt: now }
    }

    case 'message.complete': {
      // A turn ends once: a repeat (a second listener, a replay) changes nothing.
      if (!chat.busy && lastItem(chat)?.kind === 'end') {
        return chat
      }

      let next = sealText(chat)
      const text = typeof payload.text === 'string' ? payload.text : ''

      // Nothing streamed this turn (a provider without streaming): show the final reply.
      if (text && !payload.response_reused && !(chat.turnText > 0)) {
        next = { ...next, items: [...next.items, { kind: 'assistant', open: false, text }] }
      }

      const failure = payload.error ?? payload.failure_reason ?? (payload.status === 'error' ? 'The turn failed.' : null)

      if (failure) {
        next = { ...next, items: [...next.items, { kind: 'error', text: String(failure) }] }
      }

      return endTurn(next, payload.status === 'interrupted' ? 'interrupted' : failure ? 'error' : 'complete', now)
    }

    case 'approval.request':
    case 'clarify.request': {
      // Keyed by request id, so the open-requests poll does not add the same card again.
      const requestId = payload.request_id ?? payload.prompt_id ?? null

      if (requestId && chat.items.some(item => item.requestId === requestId)) {
        return chat
      }

      return {
        ...sealText(chat),
        waiting: true,
        lastEventAt: now,
        items: [...sealText(chat).items, { kind: event.type === 'approval.request' ? 'approval' : 'clarify', payload, requestId }]
      }
    }

    case 'approval.settled':
    case 'clarify.settled': {
      const requestId = payload.request_id ?? payload.prompt_id ?? null
      const items = chat.items.map(item =>
        requestId && item.requestId === requestId && !item.answered ? { ...item, answered: 'answered' } : item
      )

      return { ...chat, items, waiting: items.some(item => item.requestId && !item.answered) }
    }

    case 'session.info': {
      const next = withInfo(chat, payload)

      if (!Array.isArray(payload.pending)) {
        return next
      }

      const lost = lostTurns(payload.pending)
      const known = next.lost ?? []
      const changed = lost.length !== known.length || lost.some((turn, index) => turn.id !== known[index].id)
      const out = changed ? { ...next, lost } : next

      // Paused on a lost turn: nothing runs until it is dropped, so the page is not working.
      return lost.length && out.busy && payload.running === false
        ? { ...out, busy: false, waiting: false, activity: null, turnStartedAt: null }
        : out
    }

    case 'error': {
      // An error frame ends the turn: nothing more comes for it.
      const next = { ...sealText(chat), items: [...sealText(chat).items, { kind: 'error', text: String(payload.message ?? 'Something went wrong.') }] }

      return chat.busy ? endTurn(next, 'error', now) : { ...next, busy: false, waiting: false }
    }

    default:
      return chat
  }
}
