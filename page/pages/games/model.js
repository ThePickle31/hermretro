// What the page knows about a library game: labels, states and the prompts about it.
import { formatBytes } from '#app/format.js'
import { gameLabel } from '#app/game-prompts.js'
import { ago } from '#shared/ui/time.js'

const KIND_LABELS = { gbstudio: 'GB Studio', gbdk: 'GBDK' }
export const GAME_STATES = {
  ready: ['good', 'Ready'],
  changed: ['warn', 'Changed since last build'],
  failed: ['bad', 'Build failed'],
  unbuilt: ['quiet', 'Not built yet'],
  romChanged: ['bad', 'ROM changed']
}

export function gameMeta(game, { kind = true, now = Date.now() } = {}) {
  return [
    kind ? KIND_LABELS[game.kind] ?? game.kind ?? null : null,
    game.rom?.size ? formatBytes(game.rom.size, { unit: 'KB' }) : null,
    game.rom?.builtAt ? `built ${ago(game.rom.builtAt, now)}` : 'never built'
  ].filter(Boolean)
}


export function installPrompt(game) {
  const install = game.install
  const rom = game.rom

  if (!install || !rom?.sha256) {
    return `Flash the built ROM of ${gameLabel(game)} to the connected Chromatic cartridge, then guide me through manual boot, gameplay, and audio checks.`
  }

  // An installed game's ROM came from someone else: the chat is told what proves it is theirs to flash, and only what
  // the library verified for this very ROM. Without that, it is told where the game came from and asks for evidence.
  const which = `${rom.path} (${rom.size} bytes, SHA-256 ${rom.sha256})`
  const from = `${install.source} at commit ${install.commit}`
  const built = install.testBuild
  const proof =
    install.mode === 'game' && install.romSha256 === rom.sha256
      ? `It was installed from ${from}: its author published this SHA-256 as romSha256 in game.json, and hermretro checked the ROM against it when it installed the game.`
      : install.mode === 'game+source' && built?.sha256 === rom.sha256 && built.commit === install.commit
        ? `It was built on this computer from the source installed from ${from}${built.matches === true ? ', and it is the ROM the game was installed with, its author\u2019s romSha256' : ''}.`
        : `It came from ${from}; hermretro has no proof that this ROM is its author\u2019s.`
  return `Flash the ROM of ${gameLabel(game)}, ${which}, to the connected Chromatic cartridge, then guide me through manual boot, gameplay, and audio checks. ${proof}`
}

export function fixPrompt(game) {
  return `The last build of ${gameLabel(game)} failed${game.error ? `:\n${game.error}\n` : '. '}Find the cause, fix it, rebuild, and show me the result.`
}
