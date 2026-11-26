// The Install on Chromatic prompt (page/pages/games/model.js installPrompt): an installed game's names its ROM and,
// only when the library verified it for this very ROM, what proves it is the author's; without a browser.
import assert from 'node:assert/strict'
import test from 'node:test'
import { registerAliases } from './aliases.mjs'

registerAliases()
const { installPrompt } = await import('../../page/pages/games/model.js')

const sha = 'ab'.repeat(32)
const other = 'cd'.repeat(32)
const rom = { path: '/games/Comet/build/game.gbc', sha256: sha, size: 65536 }
const install = { source: 'github.com/someone/comet', commit: 'c0ffee', mode: 'game', romSha256: sha }
const game = extra => ({ title: 'Comet', projectRoot: '/games/Comet', rom, ...extra })
const NO_PROOF = /hermretro has no proof that this ROM is its author/

test('a game made here keeps the plain flash prompt', () => {
  assert.match(installPrompt(game({})), /^Flash the built ROM of "Comet"/)
})

test('a game installed without its source names its ROM and the checksum its author published, for that ROM only', () => {
  const prompt = installPrompt(game({ install }))
  assert.match(prompt, /\/games\/Comet\/build\/game\.gbc \(65536 bytes, SHA-256 (?:ab){32}\)/)
  assert.match(prompt, /installed from github\.com\/someone\/comet at commit c0ffee/)
  assert.match(prompt, /published this SHA-256 as romSha256 in game\.json, and hermretro checked the ROM/)
  assert.match(installPrompt(game({ install: { ...install, romSha256: other } })), NO_PROOF)
})

test('a game installed with its source claims a build here only for the exact ROM and commit built', () => {
  const source = { ...install, mode: 'game+source', romSha256: sha }
  assert.match(installPrompt(game({ install: source })), NO_PROOF)
  const built = { ...source, testBuild: { sha256: sha, commit: 'c0ffee', matches: true } }
  assert.match(installPrompt(game({ install: built })), /built on this computer from the source installed from/)
  assert.match(installPrompt(game({ install: built })), /it is the ROM the game was installed with/)
  assert.match(installPrompt(game({ install: { ...source, testBuild: { sha256: other, commit: 'c0ffee', matches: true } } })), NO_PROOF)
  assert.match(installPrompt(game({ install: { ...source, testBuild: { sha256: sha, commit: 'beef', matches: true } } })), NO_PROOF)
})
