// tools/debug/gateway_rpc.mjs without a gateway: one JSON line naming what hermes said, exit 1 (not a Node stack).
// Uses a stub `hermes` on PATH, so it needs no Hermes. Run alone: node tests/page/gateway-rpc.test.mjs
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

test('gateway_rpc.mjs reports a missing gateway as JSON and exits 1', () => {
  const bin = mkdtempSync(path.join(os.tmpdir(), 'gateway-rpc-'))
  try {
    const stub = path.join(bin, 'hermes')
    writeFileSync(stub, '#!/bin/sh\necho "Error: no gateway runs for $2" >&2\nexit 1\n')
    chmodSync(stub, 0o755)
    const run = spawnSync(process.execPath, [path.join(root, 'tools/debug/gateway_rpc.mjs'), 'nobody', 'plugin.hermretro.status'], {
      encoding: 'utf8', env: { ...process.env, PATH: `${bin}${path.delimiter}${process.env.PATH}` }
    })
    assert.equal(run.status, 1, run.stderr)
    assert.deepEqual(JSON.parse(run.stdout), { profile: 'nobody', error: 'no gateway: Error: no gateway runs for nobody' })
    assert.equal(run.stderr, '', 'no Node stack')
  } finally {
    rmSync(bin, { recursive: true, force: true })
  }
})
