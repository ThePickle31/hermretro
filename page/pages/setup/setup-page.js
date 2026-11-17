// The Setup page: the step rail, the step shown (or the hardware choice, or setup complete) and the flyer.
import { jsx, jsxs } from '#sdk'
import { Flyer } from '#shared/ui/art.js'
import { HardwareChoice } from './hardware-steps.js'
import { SetupComplete } from './setup-complete.js'
import { SetupWizard, StepRail } from './wizard.js'

export function SetupPage({ shell }) {
  const { autoId, backend, choosing, ctx, doctor, gateway, install, memory, pick, shown, status, steps, update } = shell

  return jsxs('div', {
    className: 'cs-setup',
    children: [
      jsx(StepRail, { autoId, onPick: pick, shownId: shown?.id ?? null, skipped: Boolean(memory.hardwareSkipped), steps }, 'rail'),
      shown
        ? jsx(SetupWizard, { autoId, backend, ctx, doctor, gateway, install, onContinue: shell.unpin, onPick: pick, shown, status, steps, update }, 'wizard')
        : choosing
          ? jsx(HardwareChoice, { steps, update }, 'choice')
          : jsx(
              SetupComplete,
              {
                doctor,
                emulatorOnly: shell.emulatorOnly,
                onGo: shell.go,
                onRecheck: shell.refresh,
                onSetUpDevice: shell.setUpDevice,
                rechecking: shell.refreshing,
                status,
                steps
              },
              'complete'
            ),
      jsx(Flyer, {}, 'flyer')
    ]
  })
}
