// Shown instead of the Build page while the hermretro profile is missing or broken: Build chats run there
// and nowhere else, so there is nothing to fall back to. Repair re-runs the profile setup.
import { Button, host, jsx, jsxs, useState } from '#sdk'
import { createStudioProfileOnce } from '#pages/setup/install/installer.js'
import { Lede } from '#shared/ui/text.js'
import { Working } from '#shared/ui/working.js'

export function StudioNeeded({ status }) {
  const profile = status.data?.profile
  const [working, setWorking] = useState(false)
  const [failure, setFailure] = useState(null)
  const exists = Boolean(profile?.studio?.exists)
  // Finished but not answering yet: Hermes is still starting it.
  const starting = Boolean(profile?.studio?.installed) && !working

  const repair = async () => {
    if (working || !profile) {
      return
    }

    setWorking(true)
    setFailure(null)

    try {
      await createStudioProfileOnce(profile)
      host.notify({ kind: 'success', message: 'hermretro profile ready' })
      status.refetch?.()
    } catch (error) {
      setFailure(String(error?.message ?? error))
    } finally {
      setWorking(false)
    }
  }

  return jsxs('section', {
    className: 'cs-studio-needed cs-content',
    role: 'status',
    children: [
      jsx('h2', { children: exists ? 'The hermretro profile needs repair' : 'The hermretro profile is not set up' }),
      jsx(Lede, {
        children:
          'Build chats run only in the hermretro profile, where the game-making tools and skills live. ' +
          (exists ? 'It exists but is not answering as it should.' : 'It has not been created yet.')
      }),
      working
        ? jsx(Working, { children: exists ? 'Repairing the profile…' : 'Creating the profile…' })
        : jsxs('div', {
            className: 'cs-col',
            children: [
              // Finished but not answering yet: usually Hermes is still starting it; Repair stays offered,
              // because a profile whose plugin was turned off never answers.
              starting ? jsx(Working, { children: 'The profile is set up. Waiting for Hermes to start it…' }) : null,
              jsx('div', {
                className: 'cs-actions',
                children: jsx(Button, {
                  disabled: !profile,
                  onClick: repair,
                  size: 'sm',
                  variant: starting ? 'ghost' : 'default',
                  children: exists ? 'Repair' : 'Set up the profile'
                })
              })
            ]
          }),
      failure ? jsx('p', { className: 'cs-error', children: failure }) : null
    ]
  })
}
