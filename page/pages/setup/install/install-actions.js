// The install's progress, its error and next step, and its buttons. Every state ends in something to press.
import { Button, Codicon, jsx, jsxs, useEffect, useRef, useState } from '#sdk'
import { formatBytes } from '#app/format.js'
import { AsyncButton } from '#shared/ui/page.js'
import { Small } from '#shared/ui/text.js'
import { Working } from '#shared/ui/working.js'

const STAGE = { gbdk: 'GBDK', cli: 'GB Studio and its packages', uv: 'uv', emulator: 'Python, PyBoy and Pillow' }
// No new files for this long: say it is still working (GB Studio compiles for minutes at one percentage).
const QUIET_NOTE_SECONDS = 90

function clock(seconds) {
  const total = Math.max(0, Math.round(seconds ?? 0))
  const minutes = Math.floor(total / 60)

  return `${minutes}:${String(total % 60).padStart(2, '0')}`
}

/** What the install is doing now, in words: the component being installed, or the step around it. */
export function stageText(install, verifying) {
  if (verifying) {
    return 'Checking the installed tools'
  }

  if (install?.cancelling) {
    return 'Stopping safely'
  }

  return install?.current ? `Installing ${STAGE[install.current] ?? install.current}` : 'Preparing the install'
}

/** Announces a new stage once to screen readers, never every tick of the counter. */
function StageAnnouncer({ text }) {
  const [spoken, setSpoken] = useState(text)
  const last = useRef(text)

  useEffect(() => {
    if (last.current !== text) {
      last.current = text
      setSpoken(text)
    }
  }, [text])

  return jsx('span', { 'aria-live': 'polite', className: 'cs-sr', role: 'status', children: spoken })
}

export function InstallProgress({ install, phase, verifying, elsewhere }) {
  if (phase !== 'running') {
    return null
  }

  if (elsewhere && install?.state !== 'running') {
    return jsx(Working, { children: 'The tools are being installed from a chat. This page moves on when they are verified.' })
  }

  const fraction = Math.max(0.02, Math.min(1, install?.fraction ?? 0))
  const downloaded = install?.downloaded_bytes ?? 0
  const percent = Math.round(fraction * 100)
  const stage = stageText(install, verifying)
  const quiet = !verifying && install?.state === 'running' && (install?.quiet_seconds ?? 0) >= QUIET_NOTE_SECONDS

  return jsxs('div', {
    className: 'cs-col',
    style: { gap: 8 },
    children: [
      jsxs('div', {
        className: 'cs-row cs-mono',
        style: { justifyContent: 'space-between', fontSize: 11.5 },
        children: [
          jsx('span', {
            'aria-hidden': true,
            children: verifying ? 'Checking the installed tools…' : `${percent}% · ${stage}${install?.elapsed_seconds != null ? ` · ${clock(install.elapsed_seconds)}` : ''}`
          }),
          jsx('span', { className: 'cs-faint', children: downloaded > 0 ? `${formatBytes(downloaded)} downloaded` : install?.seeded ? 'Using files already on this computer' : '' })
        ]
      }),
      jsx('div', {
        'aria-label': 'Game tools install',
        'aria-valuemax': 100,
        'aria-valuemin': 0,
        'aria-valuenow': percent,
        'aria-valuetext': verifying ? stage : `${percent}%, ${stage}`,
        className: 'cs-progress',
        role: 'progressbar',
        children: jsx('b', { style: { width: `${fraction * 100}%` } })
      }),
      jsx(StageAnnouncer, { text: stage }),
      quiet
        ? jsx(Small, {
            children: `Still working: nothing new on disk for ${clock(install.quiet_seconds)}. Building GB Studio can stay at one percentage for several minutes.`
          })
        : null
    ]
  })
}

const recheckButton = (installer, label = 'Check again') => jsx(AsyncButton, { icon: 'refresh', run: installer.recheck, variant: 'default', children: label }, 'recheck')

/** The buttons under an install: start, cancel, retry, check again, repair, ask Hermes. */
export function InstallActions({ installer, compact = false }) {
  const { phase, start, starting, ask, node, unsupported } = installer
  const size = compact ? 'sm' : 'lg'

  if (unsupported) {
    return jsxs('div', {
      className: 'cs-col',
      style: { gap: 10 },
      children: [
        jsx(Small, { tone: 'warn', children: 'This hermretro backend cannot install from the page yet. Update the plugin, or let Hermes do it in a chat.' }),
        jsx('div', { className: 'cs-actions', children: jsx(AsyncButton, { icon: 'comment-discussion', run: ask, variant: 'default', children: 'Set up in chat' }) })
      ]
    })
  }

  if (!node.ok) {
    return jsxs('div', {
      className: 'cs-col',
      style: { gap: 10 },
      children: [
        jsx(Small, {
          tone: 'warn',
          children: node.version
            ? `Found Node.js ${node.version}, which is too old (hermretro needs ${node.required} or newer). Update Hermes, then check again.`
            : `Node.js was not found. Hermes normally installs it; run "hermes update", restart Hermes, then check again.`
        }),
        jsx('div', { className: 'cs-actions', children: recheckButton(installer) })
      ]
    })
  }

  if (phase === 'done' && installer.needsProfile) {
    return installer.profileWork.state === 'running'
      ? jsx(Working, { children: 'Creating the hermretro profile…' })
      : jsx('div', {
          className: 'cs-actions',
          children: jsx(Button, { disabled: installer.updating || installer.conflict, onClick: installer.makeProfile, size, variant: 'default', children: 'Create the hermretro profile' })
        })
  }

  if (phase === 'done' && installer.profileWork.state !== 'failed') {
    // Made, but its route has not answered: usually Hermes is still starting it. A profile whose plugin was
    // turned off never answers, so Repair stays offered.
    return jsxs('div', {
      className: 'cs-col',
      style: { gap: 10 },
      children: [
        jsx(Working, { quiet: true, children: installer.profileWork.state === 'running' ? 'Repairing the hermretro profile…' : 'Tools verified. Waiting for Hermes to start the hermretro profile…' }),
        jsx('div', {
          className: 'cs-actions',
          children: jsx(AsyncButton, { disabled: installer.updating || installer.profileWork.state === 'running', icon: 'tools', run: installer.repairProfile, children: 'Repair the profile' })
        })
      ]
    })
  }

  if (phase === 'done') {
    return jsx('div', {
      className: 'cs-actions',
      children: jsx(AsyncButton, { disabled: installer.updating, icon: 'tools', run: installer.repairProfile, variant: 'default', children: 'Repair the profile' })
    })
  }

  if (phase === 'running') {
    if (installer.elsewhere && installer.state !== 'running') {
      return jsx('div', { className: 'cs-actions', children: recheckButton(installer) })
    }

    if (installer.state !== 'running' || installer.verifying) {
      return null
    }

    return installer.cancelling
      ? jsx(Working, { quiet: true, children: 'Stopping safely: waiting for the installer to finish its current step…' })
      : jsx('div', {
          className: 'cs-actions',
          children: jsx(AsyncButton, { icon: 'debug-stop', run: installer.cancel, title: 'Stops after the current step; finished parts are kept', children: 'Cancel' })
        })
  }

  if (phase === 'review') {
    const blocked = installer.unavailable || !installer.manifestReady || installer.conflict || installer.noSpace

    return jsxs('div', {
      className: 'cs-actions',
      children: [
        jsxs(Button, {
          disabled: starting || installer.updating || blocked,
          onClick: () => void start(),
          size,
          variant: 'default',
          children: [jsx(Codicon, { name: 'cloud-download', size: 14 }), 'Download and install']
        }),
        blocked ? recheckButton(installer) : null
      ]
    })
  }

  if (phase === 'failed' && installer.unavailable) {
    return jsx('div', { className: 'cs-actions', children: recheckButton(installer) })
  }

  if (phase === 'failed' && installer.unverified) {
    return jsxs('div', {
      className: 'cs-actions',
      children: [
        recheckButton(installer),
        installer.missing.length
          ? jsxs(Button, {
              disabled: starting || installer.updating,
              onClick: () => void start(),
              size,
              variant: 'outline',
              children: [jsx(Codicon, { name: 'refresh', size: 14 }), 'Retry install']
            })
          : null,
        jsx(AsyncButton, { icon: 'comment-discussion', run: ask, title: 'Opens a chat with the error in it, not sent', children: 'Ask Hermes to fix it' })
      ]
    })
  }

  if (phase === 'failed') {
    return jsxs('div', {
      className: 'cs-actions',
      children: [
        jsxs(Button, {
          disabled: starting || installer.updating || !installer.manifestReady || installer.conflict || installer.noSpace,
          onClick: () => void start(),
          size,
          variant: 'default',
          children: [jsx(Codicon, { name: 'refresh', size: 14 }), installer.state === 'cancelled' ? 'Install again' : 'Try again']
        }),
        jsx(AsyncButton, { icon: 'comment-discussion', run: ask, title: 'Opens a chat with the error in it, not sent', children: 'Ask Hermes to fix it' })
      ]
    })
  }

  return null
}

/** Why the install cannot go on, and the one next step: before it starts, when it stops, when it does not verify. */
export function InstallError({ installer }) {
  const { failure, phase, profileWork, hint } = installer
  const profileName = installer.profile?.studio?.name ?? 'hermretro'
  const doctor = installer.doctor
  const before = phase === 'review' || phase === 'failed'
  const note = (key, text, tone = 'cs-error') => jsx('p', { className: tone, children: text }, key)

  return [
    installer.conflict && phase !== 'running'
      ? note('conflict', `A Hermes profile named "${profileName}" already exists and was not made by hermretro, so nothing was downloaded. Rename or remove that profile in Hermes, then check again.`)
      : null,
    before && !installer.manifestReady && !installer.unsupported
      ? note('manifest', 'The download list could not be read, so nothing can be reviewed or installed yet. Check again; if it stays empty, update or reinstall hermretro.')
      : null,
    before && installer.noSpace
      ? note('space', `Not enough free disk space: the game tools need about ${formatBytes(installer.data?.space?.needed_bytes)} and ${formatBytes(installer.data?.space?.free_bytes)} is free. Free some space, then check again.`)
      : null,
    before && !installer.noSpace && installer.spaceWarning ? note('space-warning', installer.spaceWarning, 'cs-small') : null,
    installer.unavailable ? note('status', installer.unavailable) : null,
    phase === 'running' && installer.cancelError ? note('cancel', installer.cancelError) : null,
    phase === 'review' && installer.elsewhereEnded
      ? note('elsewhere', 'The install that was running in a chat stopped before the tools were ready. Install them here instead.', 'cs-small')
      : null,
    phase === 'failed' && installer.unverified
      ? note(
          'unverified',
          doctor?.isError || doctor?.data?.ok === false
            ? `The install finished, but the tools check failed: ${doctor?.data?.error || String(doctor?.error?.message ?? doctor?.error ?? 'unknown error')}`
            : `The install finished, but the tools check still reports missing: ${installer.missing.join(', ') || 'unknown'}.`
        )
      : null,
    phase === 'failed' && !installer.unverified && failure ? note('error', failure) : null,
    phase === 'failed' && !installer.unverified && hint ? note('hint', hint, 'cs-small') : null,
    profileWork.state === 'failed' ? note('profile', `The hermretro profile could not be created: ${profileWork.error}`) : null
  ]
}
