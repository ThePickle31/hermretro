// The page's stylesheet.
import { jsx } from '../sdk.js'
import { ASSETS_CSS } from '../build-assets/assets.css.js'
import { COMPOSER_CSS } from '../build-composer/composer.css.js'
import { MENTIONS_CSS } from '../build-composer/mentions.css.js'
import { MODEL_PICKER_CSS } from '../build-composer/model-picker.css.js'
import { INLINE_PLAYER_CSS } from '../build-player/inline-player.css.js'
import { BUILD_CARD_CSS } from '../build-transcript/build-card.css.js'
import { CARDS_CSS } from '../build-transcript/cards.css.js'
import { TRANSCRIPT_CSS } from '../build-transcript/transcript.css.js'
import { WORKED_MODE_CSS } from '../build-transcript/worked-mode.css.js'
import { WORKED_CSS } from '../build-transcript/worked.css.js'
import { VIEWER_CSS } from '../build-viewer/viewer.css.js'
import { BUILD_RESPONSIVE_CSS } from '../build/build-responsive.css.js'
import { BUILD_CSS } from '../build/build.css.js'
import { HEADER_CSS } from '../build/header.css.js'
import { NEW_GAME_CSS } from '../build/new-game.css.js'
import { EMULATOR_CSS } from '../emulator/emulator.css.js'
import { GAMES_CSS } from '../games/games.css.js'
import { HOME_CSS } from '../home/home.css.js'
import { ONBOARDING_CSS } from '../onboarding/onboarding.css.js'
import { PROMPTS_CSS } from '../prompts/prompts.css.js'
import { SETUP_CSS } from '../setup/setup.css.js'
import { SHELL_CSS } from '../shell/shell.css.js'
import { FLYER_CSS } from '../ui/flyer.css.js'
import { BASE_CSS } from './base.css.js'
import { RESPONSIVE_CSS } from './responsive.css.js'

// One chunk per area, beside that area's code. The order here is the cascade order.
const CSS = [
  BASE_CSS,
  SHELL_CSS,
  SETUP_CSS,
  ONBOARDING_CSS,
  FLYER_CSS,
  HOME_CSS,
  PROMPTS_CSS,
  GAMES_CSS,
  EMULATOR_CSS,
  RESPONSIVE_CSS,
  BUILD_CSS,
  NEW_GAME_CSS,
  TRANSCRIPT_CSS,
  WORKED_CSS,
  ASSETS_CSS,
  VIEWER_CSS,
  INLINE_PLAYER_CSS,
  CARDS_CSS,
  COMPOSER_CSS,
  MODEL_PICKER_CSS,
  BUILD_CARD_CSS,
  HEADER_CSS,
  WORKED_MODE_CSS,
  MENTIONS_CSS,
  BUILD_RESPONSIVE_CSS
].join('')

export function PageStyle() {
  return jsx('style', { children: CSS })
}
