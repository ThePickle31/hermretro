// The Setup page once every step is done.
import { Button, Codicon, jsx, jsxs } from '#sdk'
import { Facts, Lede } from '#shared/ui/text.js'

/** Everything is verified (or the Chromatic part was skipped). */
/** The hermretro row: the installed version and whether Hermes has a newer one (the header chip runs the update). */
function versionFact(data, update) {
  const version = data.plugin?.version ?? '?'

  if (!update) {
    return version
  }

  if (update.ready && update.phase === 'idle') {
    return jsxs('span', {
      className: 'cs-note',
      children: [
        `${version} · a new version is ready`,
        jsx(Button, { onClick: update.start, size: 'sm', variant: 'default', children: 'Update' }),
        jsxs(Button, { onClick: update.whatsNew, size: 'sm', variant: 'link', children: ["What's new", jsx(Codicon, { name: 'link-external', size: 12 })] })
      ]
    })
  }

  if (update.phase === 'updating') {
    return `${version} · updating…`
  }

  return update.linked ? `${version} · a linked checkout: update it with git` : update.checked ? `${version} · up to date` : version
}

export function SetupComplete({ steps, status, doctor, emulatorOnly, onRecheck, rechecking, onSetUpDevice, onGo, pluginUpdate = null }) {
  const data = status.data ?? {}
  const report = doctor.data?.ok ? doctor.data : null
  const tools = (report?.components ?? [])
    .filter(component => component.status === 'ready' && !component.optional && component.id !== 'node' && component.id !== 'runtime')
    .map(component => `${component.label ?? component.id} ${component.detected ?? ''}`.trim())
  const cli = data.deps?.device_cli

  return jsxs('section', {
    'aria-live': 'polite',
    className: 'cs-stage',
    children: [
      jsxs('div', {
        className: 'cs-stage-head',
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [
              jsx('span', { className: 'cs-accent', children: '●' }),
              emulatorOnly ? `Steps 1–2 done · emulator only` : `All ${steps.length} steps done`
            ]
          }),
          jsx('h2', { className: 'cs-word cs-title', children: 'Setup is complete' })
        ]
      }),
      jsx(Lede, {
        children: emulatorOnly
          ? 'Everything the emulator needs is installed and verified. A Chromatic is optional: set it up any time to stream games to it and write cartridges. Open any step to review it.'
          : 'Everything is installed and verified, including your Chromatic. Open any step to review it.'
      }),
      jsx(Facts, {
        rows: [
          ['hermretro', versionFact(data, pluginUpdate)],
          ['Profile', data.profile?.name ?? data.via_profile ?? 'this profile'],
          ['Toolchain', [tools.join(' · '), data.engine?.version ? `engine ${data.engine.version}` : ''].filter(Boolean).join(' · ') || 'Ready'],
          [
            'Chromatic',
            data.hardware_enabled
              ? `Device software${cli?.version ? ` ${cli.version}` : ''} · hardware tools on`
              : 'Not set up: streaming and flashing are off'
          ]
        ]
      }),
      jsxs('div', {
        className: 'cs-actions',
        children: [
          jsx(Button, { onClick: () => onGo('home'), size: 'sm', variant: 'default', children: 'Go to the studio' }),
          jsxs(Button, {
            disabled: rechecking,
            onClick: onRecheck,
            size: 'sm',
            variant: 'ghost',
            children: [jsx(Codicon, { name: 'refresh', size: 14, spinning: rechecking }), 'Check everything again']
          }),
          emulatorOnly ? jsx(Button, { onClick: onSetUpDevice, size: 'sm', variant: 'outline', children: 'Set up my Chromatic' }) : null
        ]
      })
    ]
  })
}
