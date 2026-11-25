// The setup steps and their state, derived from the backend's status and doctor answers.
import { useState } from '#sdk'
import { nodeState } from '#app/backend.js'

// One step per page. The page shown is always the first step that is not complete
// yet, so finishing a step (detected from the backend) moves the page on by itself.
export const HARDWARE_STEPS = ['firmware', 'devmode', 'devicecli', 'hardware']
// Node.js is not a step: Hermes installs its own, which the backend finds. A missing one blocks the
// toolchain step instead.
const STEP_ORDER = ['profile', 'toolchain', ...HARDWARE_STEPS]

const STEP_TITLES = {
  profile: 'Create the hermretro profile',
  toolchain: 'Install the game toolchain',
  firmware: 'Update your Chromatic',
  devmode: 'Activate Developer Mode',
  devicecli: "Install ModRetro's device software",
  hardware: 'Turn on hardware tools'
}

// Steps done outside Hermes cannot be detected; the user confirms them.
export const MANUAL_STEPS = { firmware: 'firmwareDone', devmode: 'devmodeDone' }

export function useSetupMemory(ctx) {
  const [memory, setMemory] = useState(() => {
    try {
      return { ...(ctx.storage.get('setup', {}) ?? {}) }
    } catch {
      return {}
    }
  })

  const update = patch =>
    setMemory(previous => {
      const next = { ...previous, ...patch }

      try {
        ctx.storage.set('setup', next)
      } catch {
        // not persisted; still applies for this visit
      }

      return next
    })

  return [memory, update]
}

/** The studio profile only exists before onboarding for someone who set up with the older Setup page;
 *  count that as an existing setup once the tools have been checked at all. */
export function toolchainStateKnown(status, doctor) {
  return Boolean(status.data?.ok) && (Boolean(doctor.data) || doctor.isError)
}

export function toolchainState(data, doctor) {
  const report = doctor.data
  const engine = data.engine ?? {}

  if (doctor.isError || (report && !report.ok)) {
    return 'error'
  }

  if (!report) {
    return 'checking'
  }

  return (report.missing_required ?? []).length || !engine.present || engine.verified === false ? 'todo' : 'done'
}

export function computeSteps({ backend, status, doctor, memory }) {
  const data = backend === 'ok' ? status.data : null
  const cli = data?.deps?.device_cli

  const states = {
    // A backend that says nothing about profiles predates this step and cannot make one. A studio profile with no
    // Claude login its provider can use is not done: the step offers the sign-in.
    profile: !data
      ? 'waiting'
      : !data.profile || (data.profile.is_studio && data.profile.studio?.claude_login?.signed_in !== false)
        ? 'done'
        : 'todo',
    toolchain: !data ? 'waiting' : nodeState(data.node).ok ? toolchainState(data, doctor) : 'blocked',
    firmware: memory.firmwareDone ? 'done' : 'todo',
    devmode: memory.devmodeDone ? 'done' : 'todo',
    devicecli: !cli
      ? 'waiting'
      : cli.state === 'installed' || cli.state === 'bundled'
        ? 'done'
        : cli.state === 'unsupported'
          ? 'blocked'
          : 'todo',
    hardware: !data ? 'waiting' : data.hardware_enabled ? 'done' : 'todo'
  }

  return STEP_ORDER.map(id => {
    const hardware = HARDWARE_STEPS.includes(id)
    const state = hardware && memory.hardwareSkipped && states[id] !== 'done' ? 'skipped' : states[id]

    return {
      id,
      title: STEP_TITLES[id],
      hardware,
      manual: id in MANUAL_STEPS,
      state,
      complete: state === 'done' || state === 'skipped'
    }
  })
}

export const STEP_SHORT = {
  profile: 'Studio profile',
  toolchain: 'Game toolchain',
  firmware: 'Firmware',
  devmode: 'Developer Mode',
  devicecli: 'Device software',
  hardware: 'Hardware tools'
}
