// Setup: the front door of the page (its descriptor; fields in app/registry.js), and the setup state the
// shell and other pages read (steps, first-run onboarding, the toolchain install, the studio profile).
import { jsx } from '#sdk'
import { ONBOARDING_CSS } from './onboarding/onboarding.css.js'
import { SETUP_CSS } from './setup.css.js'
import { SetupPage } from './setup-page.js'

export { createStudioProfileOnce, useInstall } from './install/installer.js'
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
  css: [SETUP_CSS, ONBOARDING_CSS]
}
