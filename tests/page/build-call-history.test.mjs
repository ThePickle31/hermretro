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
const secondRef = 'f'.repeat(32)
const buildsFor = items => buildHistory(deriveTurns(items))

test('a deferred ROM build recovers its own reference from a spilled live completion', () => {
  const payload = { ...deferred, tool_id: callId }
  const initial = reduceChat({ items: [], busy: true }, { type: 'tool.start', payload })
  const preview = '{"buildRef": "' + ref + '", "result": "Compiling'
  const result = ['<persisted-output>', 'Full output saved to: /tmp/call_rom.txt', `Preview (first ${preview.length} chars):`, preview, '...', '</persisted-output>'].join('\n')
  const finished = reduceChat(initial, { type: 'tool.complete', payload: { ...payload, result } })
  const [build] = buildsFor(finished.items)

  assert.equal(finished.items[0].tools.length, 1)
  assert.equal(build.resultCall, null)
  assert.equal(build.buildRef, ref)
})

test('a direct or deferred live verbose result keeps the exact reference', () => {
  const result = { buildRef: ref, result: 'Warning\n'.repeat(16_000), structuredContent: { success: true } }

  for (const call of [{ name: rom, args: {} }, deferred]) {
    const payload = { ...call, tool_id: callId, result }
    const chat = reduceChat({ items: [] }, { type: 'tool.complete', payload })
    const [build] = buildsFor(chat.items)

    assert.equal(build.resultCall, null)
    assert.equal(build.buildRef, ref)

    const bounded = JSON.stringify({ output: JSON.stringify(result).slice(0, 32768), truncated: true })
    const truncated = reduceChat({ items: [] }, { type: 'tool.complete', payload: { ...payload, result: bounded } })

    assert.equal(buildsFor(truncated.items)[0].buildRef, ref)
  }
})

test('compact resume retains the exact result timestamp with a reused call ID', () => {
  const buildRow = { role: 'tool', tool_call_id: callId, timestamp: 2, ...deferred }
  const messages = [{ role: 'user', text: 'Build the game', timestamp: 1 }, buildRow]
  const [build] = buildsFor(historyItems(messages))

  assert.deepEqual(build.resultCall, { id: callId, timestamp: 2 })
  assert.equal(build.buildRef, null)
  const reused = [...messages, { role: 'user', text: 'Again', timestamp: 3 }, { ...buildRow, timestamp: 4 }]

  assert.deepEqual(buildsFor(historyItems(reused)).map(row => row.resultCall), [
    { id: callId, timestamp: 2 },
    { id: callId, timestamp: 4 }
  ])
  assert.deepEqual(buildsFor(historyItems([...messages, { ...buildRow, timestamp: 2.125 }]))[0].resultCall, {
    id: callId, timestamp: 2.125
  })
  assert.equal(buildsFor(historyItems([{ ...buildRow, timestamp: null }]))[0].resultCall, null)
})

test('reused live call IDs keep their own completion within and across turns', () => {
  const call = { tool_id: callId, ...deferred }
  const event = (type, payload = {}) => ({ type, payload })
  const payload = (turn, buildRef) => ({ ...call, turn_id: turn, result: { buildRef } })
  const chat = [
    event('message.start', { turn_id: 'first' }),
    event('tool.start', call),
    event('tool.complete', payload('first', ref)),
    event('message.complete'),
    event('message.start', { turn_id: 'second' }),
    event('tool.start', call),
    event('tool.complete', payload('first', ref)),
    event('tool.complete', payload('second', secondRef)),
    event('tool.start', call),
    event('tool.complete', payload('second', 'a'.repeat(32)))
  ].reduce(reduceChat, { items: [] })

  const steps = chat.items.filter(item => item.kind === 'tools').flatMap(item => item.tools)
  assert.deepEqual(steps.map(tool => tool.info?.buildRef), [ref, secondRef, 'a'.repeat(32)])
  assert.deepEqual(buildsFor(chat.items).map(build => build.buildRef), [ref, 'a'.repeat(32)])
})

test('an outer result cannot assign a reference to a wrapped batch', () => {
  const payload = { tool_id: callId, name: 'tool_call', args: { calls: [deferred.args.calls[0], { name: 'read_file' }] } }
  const started = reduceChat({ items: [] }, { type: 'tool.start', payload })
  const completed = reduceChat(started, { type: 'tool.complete', payload: { ...payload, result: { buildRef: ref } } })

  assert.equal(buildsFor(completed.items)[0].buildRef, null)
})

const rawStart = (id, timestamp, calls = deferred.args.calls) => ({
  role: 'assistant',
  tool_calls: [{ id, function: { name: 'tool_call', arguments: JSON.stringify({ calls }) } }],
  timestamp
})
const rawResult = (id, timestamp, body) => ({
  role: 'tool', tool_name: 'tool_call', tool_call_id: id, content: JSON.stringify(body), timestamp
})
const stepsFor = items => items.filter(item => item.kind === 'tools').flatMap(item => item.tools)

test('a raw outer validation error fails the wrapped ROM occurrence with the same ID', () => {
  const failure = { error: 'Required argument project is missing' }
  const items = historyItems([
    { role: 'user', content: 'Build it', timestamp: 1 },
    rawStart(callId, 2), rawResult(callId, 3, { buildRef: ref }),
    rawStart(callId, 4), { ...rawResult(callId, 5, failure), name: 'tool_call' },
    { role: 'user', content: 'Try again', timestamp: 6 },
    rawStart(callId, 7), rawResult(callId, 8, { buildRef: secondRef })
  ])

  assert.deepEqual(stepsFor(items).map(step => [step.name, step.state, step.info?.error]), [
    [rom, 'done', null], [rom, 'failed', failure.error], [rom, 'done', null]
  ])
  assert.equal(new Set(stepsFor(items).map(step => step.id)).size, 3)
  assert.deepEqual(buildsFor(items).map(build => [build.state, build.buildRef, build.resultCall]), [
    ['failed', null, null], ['built', secondRef, { id: callId, timestamp: 8 }]
  ])
})

test('raw batch results keep their outer IDs separate from other calls', () => {
  const calls = [deferred.args.calls[0], { name: 'read_file', arguments: {} }]
  const items = historyItems([
    { role: 'user', content: 'Build it', timestamp: 1 },
    rawStart(callId, 2, calls),
    rawStart(`${callId}:0`, 3),
    rawResult(callId, 4, { error: 'tool_call takes exactly one entry for local tools' }),
    rawResult(`${callId}:0`, 5, { buildRef: ref })
  ])

  assert.deepEqual(stepsFor(items).map(step => [step.name, step.state, step.info?.buildRef]), [
    [rom, 'failed', null], ['read_file', 'failed', null], [rom, 'done', ref]
  ])
  assert.deepEqual(buildsFor(items)[0].resultCall, { id: `${callId}:0`, timestamp: 5 })
})

test('a compact result for a batch member stays within its outer occurrence', () => {
  const calls = [{ name: 'read_file', arguments: {} }, deferred.args.calls[0]]
  const items = historyItems([
    rawStart(callId, 1, calls),
    { ...rawResult(callId, 2, { buildRef: ref }), args: deferred.args },
    { ...rawResult(callId, 3, { ok: true }), args: { calls: [calls[0]] } }
  ])

  assert.deepEqual(stepsFor(items).map(step => step.name), ['read_file', rom])
  assert.equal(buildsFor(items)[0].buildRef, null)
  assert.equal(buildsFor(items)[0].resultCall, null)
})

test('a redirected user row does not end the active tool occurrence or claim its build', () => {
  const call = { ...deferred, tool_id: callId, turn_id: 'active' }
  const started = [
    { type: 'message.start', payload: { turn_id: 'active' } },
    { type: 'tool.start', payload: call }
  ].reduce(reduceChat, { items: [{ kind: 'user', text: 'Build the game' }] })
  const followup = { kind: 'user', text: 'Make it a little faster', followup: true }
  const redirected = { ...started, items: [...started.items, followup] }
  const chat = [
    { type: 'tool.progress', payload: { ...call, percent: 50 } },
    { type: 'tool.complete', payload: { ...call, result: { buildRef: ref } } },
    { type: 'message.complete', payload: { turn_id: 'active', text: 'Built.' } }
  ].reduce(reduceChat, redirected)

  assert.deepEqual(stepsFor(chat.items).map(step => [step.state, step.info?.buildRef]), [['done', ref]])
  assert.deepEqual(buildsFor(chat.items).map(build => [build.title, build.buildRef]), [['Build the game', ref]])
  assert.ok(deriveTurns(chat.items)[0].items.includes(followup))
})

test('a wrapped compact resume row with no outcome evidence is an unknown build', () => {
  const items = historyItems([
    { role: 'user', text: 'Build it', timestamp: 1 },
    { role: 'tool', tool_call_id: callId, timestamp: 2, ...deferred }
  ])

  assert.equal(stepsFor(items)[0].state, 'unknown')
  assert.equal(buildsFor(items)[0].state, 'unknown')
  assert.deepEqual(buildsFor(items)[0].resultCall, { id: callId, timestamp: 2 })
})
