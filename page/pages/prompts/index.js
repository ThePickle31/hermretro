// Prompts: the front door of the page (its descriptor; fields in app/registry.js) and the prompt library
// other pages put into chats.
import { jsx } from '#sdk'
import { PROMPTS_CSS } from './prompts.css.js'
import { PromptsPage } from './prompts-page.js'

export { ALL_PROMPTS, DEVICE_CLI_PROMPT, FLASH_PROMPT, NEW_GAME_PROMPT, promptById, SETUP_PROMPT } from './library.js'

function Prompts({ shell }) {
  return jsx(PromptsPage, {
    ctx: shell.ctx,
    defaultFolder: shell.newGameFolder,
    gameReady: shell.gameReady,
    hardwareOn: shell.hardwareOn,
    onGo: shell.go,
    onSelect: shell.setPromptId,
    onSetUpDevice: shell.setUpDevice,
    profileLabel: shell.profileLabel,
    selected: shell.promptId,
    storage: shell.ctx.storage
  })
}

export const PROMPTS_PAGE = {
  id: 'prompts',
  label: 'Prompts',
  Page: Prompts,
  css: [PROMPTS_CSS]
}
