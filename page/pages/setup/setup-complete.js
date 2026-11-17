// The Setup page once every step is done.
import { Button, Codicon, jsx, jsxs } from '#sdk'
import { Facts, Lede } from '#shared/ui/text.js'

/** Everything is verified (or the Chromatic part was skipped). */
export function SetupComplete({ steps, status, doctor, emulatorOnly, onRecheck, rechecking, onSetUpDevice, onGo }) {
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
