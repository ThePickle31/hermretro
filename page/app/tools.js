// The agent tools whose calls the page reacts to.
// Opens only when the agent presents the game (`chromatic_present_game`), in a workspace tab docked
// right of the chat (`host.openWorkspace`). Builds open nothing: an open tab shows the rebuilt banner,
// and presenting again loads the newest build there directly, with the agent's note above the player.
// One game runs at a time: whichever surface opened last owns the live player.
export const PRESENT_TOOL = 'chromatic_present_game'
export const ROM_BUILD_TOOL = 'chromatic_rom_build'
export const BUILD_TOOLS = new Set([ROM_BUILD_TOOL, 'chromatic_web_preview'])
export const REPORT_TOOL = 'chromatic_build_report'
