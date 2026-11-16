// What the page shows when no profile answers for hermretro.
import { Button, Codicon, host, jsx, jsxs } from '../sdk.js'
import { describeRequestError } from '../core/backend.js'
import { ENABLE_COMMAND, PLUGINS_HREF } from '../core/ids.js'
import { CommandLine } from '../ui/links.js'
import { Lede } from '../ui/text.js'
import { Working } from '../ui/working.js'

/** Shown instead of the setup steps while the plugin's backend cannot be reached. Normally
 *  never seen: switching the plugin on in Capabilities turns on the page and the backend. */
export function NotRunning({ backend, status, gateway }) {
  let title = 'Checking hermretro…'
  let body = jsx(Working, { children: 'Asking the plugin for its status.' })

  if (backend === 'offline') {
    title = 'Waiting for Hermes'
    body = jsx(Working, { children: `The connection to Hermes is ${gateway || 'idle'}. This page continues by itself.` })
  } else if (backend === 'error') {
    title = 'hermretro reported a problem'
    body = jsx('pre', { className: 'cs-error', children: status.data?.error || 'Unknown error' })
  } else if (backend === 'failed') {
    title = 'Could not read hermretro\'s status'
    body = jsxs('div', {
      className: 'cs-content',
      children: [
        jsx(Lede, { children: 'The plugin is on, but its status request failed. Press Refresh; if this stays, report the message below.' }),
        jsx('pre', { className: 'cs-error', children: describeRequestError(status.error).message || 'Unknown error' })
      ]
    })
  } else if (backend === 'unavailable') {
    const { message, notLoaded } = describeRequestError(status.error)

    title = 'hermretro is not switched on in any profile'
    body = jsxs('div', {
      className: 'cs-content',
      children: [
        jsx(Lede, {
          children:
            'This page is visible, but the part of the plugin that does the work is off. Switch hermretro on in Capabilities → Plugins for the profile you want to use it in. This page continues by itself once it is on.'
        }),
        jsx('div', {
          className: 'cs-actions',
          children: jsxs(Button, {
            onClick: () => host.navigate(PLUGINS_HREF),
            size: 'sm',
            variant: 'default',
            children: [jsx(Codicon, { name: 'extensions', size: 14 }), 'Open Capabilities → Plugins']
          })
        }),
        jsxs('div', {
          className: 'cs-col',
          style: { gap: 6 },
          children: [jsx('span', { className: 'cs-faint', children: 'Or, from a terminal:' }), jsx(CommandLine, { command: ENABLE_COMMAND })]
        }),
        !notLoaded && message ? jsx('span', { className: 'cs-faint', children: `Details: ${message}` }) : null
      ]
    })
  }

  return jsx('section', {
    'aria-live': 'polite',
    className: 'cs-stage',
    style: { maxWidth: 860 },
    children: jsxs('div', {
      className: 'cs-stage',
      style: { display: 'contents' },
      children: [
        jsxs('div', {
          className: 'cs-stage-head',
          children: [jsx('p', { className: 'cs-eyebrow', children: 'Status' }), jsx('h2', { className: 'cs-word cs-title', children: title })]
        }),
        body
      ]
    })
  })
}
