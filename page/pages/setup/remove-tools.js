// Setup: delete the downloaded tools (about 2.4 GB). Games stay; setup can install them again.
import { Button, host, jsx, jsxs, useState } from '#sdk'
import { callBackend, describeRequestError } from '#app/backend.js'
import { formatBytes } from '#app/format.js'
import { RPC_REMOVE_TOOLS } from '#app/rpc.js'

export function RemoveTools({ status, doctor }) {
  const [state, setState] = useState('idle') // idle · confirm · working
  const [failure, setFailure] = useState(null)

  const remove = async () => {
    setState('working')
    setFailure(null)

    try {
      const { data } = await callBackend(RPC_REMOVE_TOOLS, {}, 120_000)

      if (!data?.ok) {
        throw new Error(data?.error || 'The tools could not be removed.')
      }

      host.notify({ kind: 'success', message: `Downloaded tools removed (${formatBytes(data.removed_bytes, { unit: 'MB' })}). Your games are untouched.` })
      status.refetch?.()
      doctor.refetch?.()
      setState('idle')
    } catch (error) {
      const { message, notLoaded } = describeRequestError(error)

      setFailure(notLoaded ? 'This hermretro backend cannot remove the tools yet. Restart Hermes, then try again.' : message || String(error))
      setState('idle')
    }
  }

  return jsxs('div', {
    className: 'cs-col',
    style: { gap: 8 },
    children: [
      state === 'confirm'
        ? jsxs('div', {
            className: 'cs-actions',
            children: [
              jsx('span', { children: 'Delete the downloaded tools? Your games stay. Building again needs a new install (about a minute).' }),
              jsx(Button, { onClick: () => void remove(), size: 'sm', variant: 'destructive', children: 'Remove' }),
              jsx(Button, { onClick: () => setState('idle'), size: 'sm', variant: 'ghost', children: 'Cancel' })
            ]
          })
        : jsx('div', {
            children: jsx(Button, {
              disabled: state === 'working',
              onClick: () => setState('confirm'),
              size: 'sm',
              variant: 'ghost',
              children: state === 'working' ? 'Removing…' : 'Remove downloaded tools'
            })
          }),
      failure ? jsx('p', { className: 'cs-error', children: failure }) : null
    ]
  })
}
