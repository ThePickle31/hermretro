// The install view: what gets downloaded, progress, log and actions.
import { Button, Codicon, jsx, jsxs } from '#sdk'
import { nodeState } from '#app/backend.js'
import { formatBytes, shortPath } from '#app/format.js'
import { Glyph } from '#shared/ui/glyph.js'
import { AsyncButton } from '#shared/ui/page.js'
import { Small } from '#shared/ui/text.js'
import { Working } from '#shared/ui/working.js'
import { useInstaller } from './installer.js'

const ROW_LABEL = { done: 'verified', running: 'installing', failed: 'failed', pending: '' }

/** The download list: what, which version, from where, how big, and why. Doubles as live progress. */
export function DownloadTable({ manifest, install, phase, profileRow }) {
  const components = install?.run?.components ?? {}
  const current = install?.current
  const rows = (manifest?.items ?? []).map(item => {
    const component = components[item.component]
    const state = phase === 'done' || install?.state === 'done' ? 'done' : component?.state ?? (phase === 'review' ? null : 'pending')

    return { ...item, state, running: state === 'running' && current === item.component }
  })

  const row = item =>
    jsxs(
      'tr',
      {
        'data-state': item.state ?? undefined,
        children: [
          item.state ? jsx('td', { className: 'g', children: jsx(Glyph, { state: { done: 'done', running: 'checking', failed: 'error', pending: 'waiting' }[item.state] }) }) : null,
          jsxs('td', { className: 'n', children: [item.name, jsx('span', { className: 'p', children: item.purpose })] }),
          jsx('td', { className: 'v', children: item.version }),
          jsx('td', { className: 's', children: item.source }),
          jsx('td', {
            className: `z ${item.state ?? ''}`,
            children: item.state && item.state !== 'pending' ? ROW_LABEL[item.state] : item.bytes ? formatBytes(item.bytes, { approx: item.approx }) : 'no download'
          })
        ]
      },
      item.id
    )

  const live = phase !== 'review'

  return jsxs('table', {
    className: 'cs-dl',
    children: [
      jsx('thead', {
        children: jsxs('tr', {
          children: [
            live ? jsx('th', { className: 'g' }) : null,
            jsx('th', { children: 'Component' }),
            jsx('th', { children: 'Version' }),
            jsx('th', { className: 's', children: 'From' }),
            jsx('th', { className: 'z', children: live ? 'Status' : 'Download' })
          ]
        })
      }),
      jsx('tbody', {
        children: [
          profileRow
            ? row({
                id: 'profile',
                name: 'Your hermretro profile',
                purpose: 'A Hermes profile with just the game tools and skills',
                version: '',
                source: 'this computer',
                bytes: 0,
                state: live ? profileRow : null
              })
            : null,
          ...rows.map(item => row({ ...item, state: live ? item.state : null }))
        ]
      })
    ]
  })
}

/** Checksums proven so far, and what is being installed now. */
export function InstallLog({ install, phase }) {
  const components = install?.run?.components ?? {}
  const lines = []

  for (const id of ['gbdk', 'cli', 'uv', 'emulator']) {
    const component = components[id]

    for (const check of component?.checks ?? []) {
      lines.push(
        jsxs('div', {
          children: [
            jsx('span', { className: 'ok', children: '✓ ' }),
            `${check.file}  sha256 ${String(check.sha256).slice(0, 8)}…  ${check.reused ? 'verified (cached)' : 'verified'}`
          ]
        }, `${id}:${check.file}`)
      )
    }

    if (component?.state === 'done' && !component.checks?.length) {
      lines.push(jsxs('div', { children: [jsx('span', { className: 'ok', children: '✓ ' }), `${id} ${component.version ?? ''} already installed, checked`] }, `${id}:reused`))
    }

    if (component?.state === 'failed') {
      lines.push(jsxs('div', { className: 'bad', children: ['✗ ', `${id}: ${component.error ?? 'failed'}`] }, `${id}:failed`))
    }
  }

  if (phase === 'running' && install?.current) {
    const label = (install.current === 'cli' ? 'GB Studio and its packages' : { gbdk: 'GBDK', uv: 'uv', emulator: 'Python, PyBoy and Pillow' }[install.current]) ?? install.current

    lines.push(jsxs('div', { className: 'w', children: [jsx('span', { className: 'run', children: '↓ ' }), `Installing ${label}…`] }, 'now'))
  }

  return lines.length ? jsx('div', { 'aria-live': 'polite', className: 'cs-log', role: 'log', children: lines }) : null
}

export function InstallFacts({ manifest, status, root }) {
  const node = nodeState(status.data?.node)

  return jsxs('dl', {
    className: 'cs-onb-facts',
    children: [
      jsx('dt', { children: 'Download' }),
      jsx('dd', { children: formatBytes(manifest?.bytes ?? 0, { approx: true }) }),
      jsx('dt', { children: 'On disk' }),
      jsx('dd', { children: formatBytes(manifest?.disk_bytes ?? 0, { approx: true }) }),
      jsx('dt', { children: 'Installs to' }),
      jsx('dd', { className: 'path', title: root ?? '', children: shortPath(root) ?? "the plugin's deps folder" }),
      jsx('dt', { children: 'Already here' }),
      jsx('dd', { className: node.ok ? 'good' : 'bad', children: node.ok ? `Node.js ${node.version} (from Hermes)` : 'Node.js not found' })
    ]
  })
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

  return jsxs('div', {
    className: 'cs-col',
    style: { gap: 8 },
    children: [
      jsxs('div', {
        className: 'cs-row cs-mono',
        style: { justifyContent: 'space-between', fontSize: 11.5 },
        children: [
          jsx('span', { children: verifying ? 'Checking the installed tools…' : `${Math.round(fraction * 100)}%` }),
          jsx('span', { className: 'cs-faint', children: downloaded > 0 ? `${formatBytes(downloaded)} downloaded` : install?.seeded ? 'Using files already on this computer' : '' })
        ]
      }),
      jsx('div', { className: 'cs-progress', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': Math.round(fraction * 100), children: jsx('b', { style: { width: `${fraction * 100}%` } }) })
    ]
  })
}

/** The buttons under an install: start, retry, ask Hermes. */
export function InstallActions({ installer, compact = false }) {
  const { phase, start, starting, ask, node, unsupported } = installer

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
    return jsx(Small, {
      tone: 'warn',
      children: node.version
        ? `Found Node.js ${node.version}, which is too old (hermretro needs ${node.required} or newer). Update Hermes, then come back.`
        : `Node.js was not found. Hermes normally installs it; run "hermes update", restart Hermes, then come back.`
    })
  }

  if (phase === 'done' && installer.needsProfile) {
    return installer.profileWork.state === 'running'
      ? jsx(Working, { children: 'Creating the hermretro profile…' })
      : jsx('div', {
          className: 'cs-actions',
          children: jsx(Button, { onClick: installer.makeProfile, size: compact ? 'sm' : 'lg', variant: 'default', children: 'Create the hermretro profile' })
        })
  }

  if (phase === 'done' && installer.profileWork.state !== 'failed') {
    return jsx(Working, { quiet: true, children: 'Tools verified. Waiting for Hermes to start the hermretro profile…' })
  }

  if (phase === 'review') {
    return jsx('div', {
      className: 'cs-actions',
      children: jsxs(Button, {
        disabled: starting,
        onClick: () => void start(),
        size: compact ? 'sm' : 'lg',
        variant: 'default',
        children: [jsx(Codicon, { name: 'cloud-download', size: 14 }), 'Download and install']
      })
    })
  }

  if (phase === 'failed') {
    return jsxs('div', {
      className: 'cs-actions',
      children: [
        jsxs(Button, {
          disabled: starting,
          onClick: () => void start(),
          size: compact ? 'sm' : 'lg',
          variant: 'default',
          children: [jsx(Codicon, { name: 'refresh', size: 14 }), 'Try again']
        }),
        jsx(AsyncButton, { icon: 'comment-discussion', run: ask, title: 'Opens a chat with the error in it, not sent', children: 'Ask Hermes to fix it' })
      ]
    })
  }

  return null
}

export function InstallError({ installer }) {
  const { failure, phase, profileWork } = installer

  return [
    phase === 'failed' && failure ? jsx('p', { className: 'cs-error', children: failure }, 'error') : null,
    profileWork.state === 'failed'
      ? jsx('p', { className: 'cs-error', children: `The hermretro profile could not be created: ${profileWork.error}` }, 'profile')
      : null
  ]
}

export function profileRowState(installer, profileStep, status) {
  const profile = status.data?.profile

  if (!profile) {
    return null // a backend that predates the studio profile
  }

  if (profileStep?.state === 'done') {
    return 'done'
  }

  if (installer.profileWork.state === 'failed') {
    return 'failed'
  }

  // Being made, or made and waiting for Hermes to start it.
  return installer.profileWork.state !== 'idle' || profile.studio?.installed ? 'running' : 'pending'
}

/** The toolchain step on the Setup page (repairs after onboarding): the same install, compact. */
export function InstallPanel({ ctx, status, install, step, profileStep }) {
  const installer = useInstaller({ ctx, install, status, toolchainDone: step.state === 'done' })
  const data = install.data

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(InstallFacts, { manifest: data?.manifest, root: data?.root, status }),
      jsx(InstallProgress, { elsewhere: installer.elsewhere, install: data?.install, phase: installer.phase, verifying: installer.verifying }),
      data?.manifest
        ? jsx(DownloadTable, { install: data.install, manifest: data.manifest, phase: installer.phase, profileRow: profileRowState(installer, profileStep, status) })
        : install.isError
          ? null
          : jsx(Working, { quiet: true, children: 'Reading the download list…' }),
      jsx(InstallLog, { install: data?.install, phase: installer.phase }),
      ...InstallError({ installer }),
      jsx(InstallActions, { compact: true, installer })
    ]
  })
}
