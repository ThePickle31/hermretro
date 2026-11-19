// Prompts: the front door of the page (its descriptor; fields in app/registry.js) and the prompt library
// other pages put into chats.
import { PROMPTS_CSS } from './prompts.css.js'
import { Prompts } from './prompts-page.js'

export { ALL_PROMPTS, DEVICE_CLI_PROMPT, FLASH_PROMPT, NEW_GAME_PROMPT, promptById, SETUP_PROMPT } from './library.js'

export const PROMPTS_PAGE = {
  id: 'prompts',
  label: 'Prompts',
  Page: Prompts,
  css: [PROMPTS_CSS]
}
