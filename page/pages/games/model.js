// What the page knows about a library game: labels, states and the prompts about it.
import { gameLabel } from '#app/game-prompts.js'
import { ago } from '#app/time.js'
import { FLASH_PROMPT } from '#pages/prompts/library.js'

const KIND_LABELS = { gbstudio: 'GB Studio', gbdk: 'GBDK' }
export const GAME_STATES = {
  ready: ['good', 'Ready'],
  changed: ['warn', 'Changed since last build'],
  failed: ['bad', 'Build failed'],
  unbuilt: ['quiet', 'Not built yet']
}

export function gameMeta(game, { kind = true, now = Date.now() } = {}) {
  return [
    kind ? KIND_LABELS[game.kind] ?? game.kind ?? null : null,
    game.rom?.size ? `${Math.max(1, Math.round(game.rom.size / 1024))} KB` : null,
    game.rom?.builtAt ? `built ${ago(game.rom.builtAt, now)}` : 'never built'
  ].filter(Boolean)
}

/** The game to show first: the most recently built one that the player can run. */
export function latestGame(games) {
  const list = [...(games ?? [])].sort((a, b) => (b.rom?.builtAt ?? 0) - (a.rom?.builtAt ?? 0))

  return list.find(game => game.webExport) ?? list[0] ?? null
}


export function installPrompt(game) {
  return FLASH_PROMPT.replace('my built homebrew ROM', `the built ROM of ${gameLabel(game)}`)
}

export function fixPrompt(game) {
  return `The last build of ${gameLabel(game)} failed${game.error ? `:\n${game.error}\n` : '. '}Find the cause, fix it, rebuild, and show me the result.`
}
