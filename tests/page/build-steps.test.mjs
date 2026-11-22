// The Build page's reading of a step's result (page/pages/build/chat/steps.js): when a step failed, and why.
// Run alone: node tests/page/build-steps.test.mjs
import assert from 'node:assert/strict'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

registerAliases()

const { stepInfo, toolFailed } = await import('#pages/build/chat/steps.js')

// What the engine answers for a build that ran and stopped: no `ok`, no `isError`, `success: false` in its
// structured content, the reason in its diagnostics (seen from a real GB Studio build in the dev sandbox).
const STOPPED = {
  result: 'Operation failed (warnings: 1; diagnostics: 1).',
  structuredContent: {
    success: false,
    builder: 'gb-studio-cli',
    diagnostics: [
      { severity: 'warning', code: 'OLD_ASSET', message: 'An asset was converted again.' },
      { severity: 'error', code: 'BUILD_TIMEOUT', message: 'The compiler exceeded the requested time limit.' }
    ]
  }
}

test('a build the engine says did not succeed is a failed step, live (an object) and from history (JSON text)', () => {
  assert.equal(toolFailed({ result: STOPPED }), true)
  assert.equal(toolFailed({ result: JSON.stringify(STOPPED) }), true)
})

test('its reason is the first error diagnostic, else the summary line', () => {
  assert.equal(stepInfo('chromatic_rom_build', STOPPED).error, 'The compiler exceeded the requested time limit.')
  const bare = { result: 'Operation failed (exit 1).', structuredContent: { success: false } }
  assert.equal(stepInfo('chromatic_rom_build', bare).error, 'Operation failed (exit 1).')
  const warned = { result: 'Operation failed (warnings: 1).', structuredContent: { success: false, diagnostics: [{ severity: 'warning', message: 'An asset was converted again.' }] } }
  assert.equal(stepInfo('chromatic_rom_build', warned).error, 'Operation failed (warnings: 1).', 'a warning is not the reason')
})

test('a build that succeeded, or a result without structured content, is not a failure', () => {
  const built = { result: 'Completed (warnings: 1).', structuredContent: { success: true, diagnostics: [{ severity: 'warning', message: 'x' }] } }
  assert.equal(toolFailed({ result: built }), false)
  assert.equal(stepInfo('chromatic_rom_build', built).error, null)
  assert.equal(toolFailed({ result: { ok: true } }), false)
})

test('the plugin’s own failures still count as before', () => {
  assert.equal(toolFailed({ result: { ok: false, error: 'folder exists' } }), true)
  assert.equal(toolFailed({ result: { isError: true, error: 'no' } }), true)
  assert.equal(toolFailed({ error: 'gateway error' }), true)
})

const { turnBuilt } = await import('#pages/build/transcript/turns.js')
const turnOf = (...tools) => ({ key: 't', user: null, items: [{ kind: 'tools', tools: tools.map(([name, state], index) => ({ id: `s${index}`, name, state })) }] })

test('a turn whose last compile stopped did not build the game, even after an earlier compile in it succeeded', () => {
  assert.equal(turnBuilt(turnOf(['chromatic_rom_build', 'done'])), true)
  assert.equal(turnBuilt(turnOf(['chromatic_rom_build', 'done'], ['chromatic_rom_build', 'failed'])), false)
  assert.equal(turnBuilt(turnOf(['chromatic_rom_build', 'failed'], ['chromatic_rom_build', 'done'])), true)
  assert.equal(turnBuilt(turnOf(['chromatic_present_game', 'done'])), true, 'a presentation alone still plays the build there is')
})
