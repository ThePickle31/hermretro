// Setup step: the game toolchain.
import { Button, Codicon, jsx, jsxs } from '../sdk.js'
import { describeRequestError } from '../core/backend.js'
import { InstallPanel } from '../install/install-panel.js'
import { RemoveTools } from './remove-tools.js'
import { Glyph } from '../ui/glyph.js'
import { Lede, Small } from '../ui/text.js'
import { Working } from '../ui/working.js'

const COMPONENT_STATUS = { ready: 'Ready', missing: 'Missing', incompatible: 'Incompatible', unknown: 'Unknown' }

function ComponentRow({ component }) {
  const status = component.optional && component.status !== 'ready' ? 'optional' : (component.status ?? 'unknown')
  const versions = [
    component.required ? `needs ${component.required}` : null,
    component.detected ? `found ${component.detected}` : component.status === 'missing' ? 'not found' : null
  ]
    .filter(Boolean)
    .join(' · ')

  return jsxs('div', {
    className: 'cs-comp',
    children: [
      jsx(Glyph, { state: component.status === 'ready' ? 'done' : component.status === 'incompatible' ? 'error' : 'todo' }),
      jsxs('span', {
        className: 'name',
        children: [component.label ?? component.id, component.optional ? jsx('small', { children: 'optional' }) : null]
      }),
      jsx('span', { className: 'ver', children: versions }),
      jsx('span', { className: `st ${status}`, children: status === 'optional' ? 'Optional' : COMPONENT_STATUS[status] ?? 'Unknown' }),
      component.detail ? jsx('span', { className: 'detail', children: component.detail }) : null
    ]
  })
}

export function ToolchainBody({ ctx, step, status, doctor, install, steps }) {
  if (!status.data?.ok) {
    return jsx(Small, { children: 'Checked once the plugin is on.' })
  }

  const platform = status.data.platform
  const engine = status.data.engine ?? {}
  const deps = status.data.deps ?? {}
  const report = doctor.data

  // The engine has its own row; Node.js comes with Hermes and is not listed.
  const rows = (report?.ok ? (report.components ?? []) : [])
    .filter(component => component.id !== 'node' && component.id !== 'runtime')
    .map(component => jsx(ComponentRow, { component }, component.id ?? component.label))

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          'The compilers and emulator that turn a project into a real Game Boy Color ROM and let Hermes playtest it: GB Studio, GBDK and PyBoy.'
      }),
      step.state === 'error'
        ? jsxs('div', {
            className: 'cs-col',
            style: { gap: 10 },
            children: [
              jsx('p', {
                className: 'cs-error',
                children: `Toolchain check failed: ${report?.error || describeRequestError(doctor.error).message || 'unknown error'}`
              }),
              jsx('div', {
                className: 'cs-actions',
                children: jsxs(Button, {
                  disabled: doctor.isFetching,
                  onClick: () => void doctor.refetch?.(),
                  size: 'sm',
                  variant: 'default',
                  children: [jsx(Codicon, { name: 'refresh', size: 14, spinning: doctor.isFetching }), 'Check again']
                })
              })
            ]
          })
        : null,
      platform && platform.qualified === false
        ? jsx(Small, {
            tone: 'warn',
            children: platform.rosetta
              ? 'Hermes is running under Rosetta (Intel emulation). It works, but builds are slower: install the Apple Silicon version of Hermes.'
              : platform.node_arch && platform.machine && platform.node_arch !== platform.machine
                ? `The Node.js hermretro found is built for ${platform.node_arch}, but this computer is ${platform.machine}. It works, but slower: install the ${platform.machine === 'arm64' ? 'Apple Silicon' : platform.machine} version of Node.js (for example with Homebrew in /opt/homebrew).`
                : `${platform.system ?? 'This system'} ${platform.machine ?? ''} has not been tested yet; some steps may not work.`
          })
        : null,
      (step.state === 'todo' || step.state === 'blocked') && install
        ? jsx(InstallPanel, { ctx, install, profileStep: steps?.find(item => item.id === 'profile'), status, step })
        : null,
      step.state === 'done' || step.state === 'error'
        ? jsx('div', {
            className: 'cs-comps',
            children: [
              jsx(ComponentRow, {
                component: {
                  id: 'engine',
                  label: 'Chromatic engine',
                  status: engine.present ? (engine.verified === false ? 'incompatible' : 'ready') : 'missing',
                  detected: engine.present ? engine.version : '',
                  detail: engine.detail || (engine.present && engine.verified === false ? 'Engine could not be verified.' : '')
                }
              }, 'engine'),
              ...rows
            ]
          })
        : null,
      !report && step.state === 'checking' ? jsx(Working, { quiet: true, children: 'Checking installed tools…' }) : null,
      deps.toolchain_root && step.state === 'done'
        ? jsxs('span', {
            className: 'cs-faint',
            children: [
              'Install folder: ',
              jsx('span', { className: 'cs-mono', children: deps.toolchain_root }),
              deps.toolchain_cache_reused_from ? '. Downloads were reused from an existing ModRetro install on this computer.' : ''
            ]
          })
        : null,
      step.state === 'done' ? jsx(RemoveTools, { doctor, status }) : null
    ]
  })
}
