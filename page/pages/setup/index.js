// Setup: the front door of the page (its descriptor; fields in app/registry.js), and the setup state the
// shell and other pages read (steps, first-run onboarding, the toolchain install, the studio profile).
import { jsx } from '#sdk'
import { ONBOARDING_CSS } from './onboarding/onboarding.css.js'
import { SETUP_CSS } from './setup.css.js'
import { SetupPage } from './setup-page.js'

export { createStudioProfileOnce } from './install/installer.js'
export { useInstall } from './install/install-status.js'
export { ONBOARD_STAGES, OnboardHeader, Onboarding } from './onboarding/onboarding.js'
export { computeSteps, STEP_SHORT, toolchainState, toolchainStateKnown, useSetupMemory } from './steps.js'

/** The dot on the Setup segment while setup is not finished. */
function SetupBadge({ nav }) {
  return nav.setupPending ? jsx('i', { 'aria-label': 'setup is not finished', className: 'pip', role: 'img' }) : null
}

export const SETUP_PAGE = {
  id: 'setup',
  label: 'Setup',
  Page: SetupPage,
  Badge: SetupBadge,
  css: [SETUP_CSS, ONBOARDING_CSS],
  events: {
    'setup.firstIdea':
      "Onboarding's last screen handed its idea on: { idea, plan }. Build opens New Game with the idea in its box and Build it (plan false) or Plan first (plan true) chosen, not sent.",
    'setup.demoRequested': 'Try the demo was picked during setup: {}. The Emulator page opens the bundled demo beside the chat; it needs neither the toolchain nor a model.'
  }
}
