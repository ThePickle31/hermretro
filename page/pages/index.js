// The registry: every page, one line each, in nav order. A page describes itself in its own index.js
// (fields in app/registry.js); adding a page is its folder plus one line here.
import { BUILD_PAGE } from './build/index.js'
import { SETUP_PAGE } from './setup/index.js'
import { PROMPTS_PAGE } from './prompts/index.js'
import { GAMES_PAGE } from './games/index.js'
import { EMULATOR_PAGE } from './emulator/index.js'

export const PAGES = [BUILD_PAGE, SETUP_PAGE, PROMPTS_PAGE, GAMES_PAGE, EMULATOR_PAGE]

// What the shell itself uses from a page beyond its descriptor, each from that page's front door:
// first-run onboarding and the setup steps (every page shows their state), the newest game (the player's
// default and where new games go).
export {
  computeSteps,
  ONBOARD_STAGES,
  OnboardHeader,
  Onboarding,
  STEP_SHORT,
  toolchainStateKnown,
  useInstall,
  useSetupMemory
} from './setup/index.js'
export { latestGame } from './games/index.js'
