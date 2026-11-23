// Run alone: node tests/page/build-call-history.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'
import { registerAliases } from './aliases.mjs'

registerAliases()

const { historyItems } = await import('#pages/build/chat/history.js')
const { reduceChat } = await import('#pages/build/chat/reducer.js')
const { buildHistory, deriveTurns } = await import('#pages/build/transcript/turns.js')

const rom = 'chromatic_rom_build'
const deferred = { name: 'tool_call', args: { calls: [{ name: rom, arguments: {} }] } }
const callId = 'call_rom'
const ref = '01c0e4b921d447b3a7652b216df41ece'
const buildsFor = items => buildHistory(deriveTurns(items))

test('a deferred ROM build keeps the outer call ID through a spilled live completion', () => {
  const payload = { ...deferred, tool_id: callId }
  const initial = reduceChat({ items: [], busy: true }, { type: 'tool.start', payload })
  const preview = '{"buildRef": "' + ref + '", "result": "Compiling'
  const result = ['<persisted-output>', 'Full output saved to: /tmp/call_rom.txt', `Preview (first ${preview.length} chars):`, preview, '...', '</persisted-output>'].join('\n')
  const finished = reduceChat(initial, { type: 'tool.complete', payload: { ...payload, result } })
  const [build] = buildsFor(finished.items)

  assert.equal(finished.items[0].tools.length, 1)
  assert.equal(build.callId, callId)
  assert.equal(build.buildRef, null)
})

test('a direct or deferred live verbose result keeps the exact reference', () => {
  const result = { buildRef: ref, result: 'Warning\n'.repeat(16_000), structuredContent: { success: true } }

  for (const call of [{ name: rom, args: {} }, deferred]) {
    const payload = { ...call, tool_id: callId, result }
    const chat = reduceChat({ items: [] }, { type: 'tool.complete', payload })
    const [build] = buildsFor(chat.items)

    assert.equal(build.callId, callId)
    assert.equal(build.buildRef, ref)
  }
})

test('compact resume retains the raw call ID without requiring an assistant tool call row', () => {
  const buildRow = { role: 'tool', tool_call_id: callId, timestamp: 2, ...deferred }
  const messages = [{ role: 'user', text: 'Build the game', timestamp: 1 }, buildRow]
  const [build] = buildsFor(historyItems(messages))

  assert.equal(build.callId, callId)
  assert.equal(build.buildRef, null)
  assert.equal(buildsFor(historyItems([...messages, { role: 'user', text: 'Again', timestamp: 3 }, { ...buildRow, timestamp: 4 }])).every(row => row.callId === null), true)
})
