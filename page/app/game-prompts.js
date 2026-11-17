// Prompts about one game that several features put into its chat.

/** A game as prompts name it: its title, and its folder when known. */
export const gameLabel = game => `"${game.title}"${game.projectRoot ? ` (${game.projectRoot})` : ''}`

export function buildPrompt(game) {
  return `Build ${gameLabel(game)} and its playable web player, so I can play it on the Emulator page of hermretro.`
}
