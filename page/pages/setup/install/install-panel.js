// The install view: what gets downloaded, progress, log and actions.
import { jsx, jsxs } from '#sdk'
import { nodeState } from '#app/backend.js'
import { formatBytes, shortPath } from '#app/format.js'
import { Glyph } from '#shared/ui/glyph.js'
import { Working } from '#shared/ui/working.js'
import { InstallActions, InstallError, InstallProgress } from './install-actions.js'
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
export function InstallPanel({ ctx, status, install, step, profileStep, doctor }) {
  const installer = useInstaller({ ctx, doctor, install, status, toolchainDone: step.state === 'done' })
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
