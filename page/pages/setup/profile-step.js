// Setup step: the dedicated hermretro profile.
import { Button, host, jsx, jsxs, useState } from '#sdk'
import { createStudioProfileOnce, signInToClaude } from './install/installer.js'
import { Facts, Lede, Small } from '#shared/ui/text.js'
import { Working } from '#shared/ui/working.js'
import { useUpdating } from '#app/update/lock.js'

const PROFILE_FACTS = [
  [
    'Sign-in',
    'It uses the sign-ins, keys and model choices of the profile the plugin is installed in, and follows later changes there. Some accounts may not carry over: Build says so if no model provider is ready there, and where to connect one.'
  ],
  ['Skills', 'hermretro and its six skills are turned on there, with a game-developer persona.'],
  ['Tools', 'Text-to-speech, app connections, computer use and scheduled jobs are turned off there. Everything else keeps the Hermes defaults.'],
  ['Approvals', 'Kept on (smart mode), so installing device software and anything that touches your Chromatic goes through an approval check.']
]

export function ProfileBody({ status }) {
  const profile = status.data?.profile
  const [working, setWorking] = useState(false)
  const [failure, setFailure] = useState(null)
  const updating = useUpdating()

  if (!status.data?.ok || !profile) {
    return jsx(Small, { children: 'Checked once the plugin is on.' })
  }

  if (profile.is_studio) {
    return jsxs('div', {
      className: 'cs-content',
      children: [
        jsx(Lede, { children: `hermretro has its own profile, "${profile.name}". Its chats open there.` }),
        jsx(ClaudeSignIn, { login: profile.studio?.claude_login, status })
      ]
    })
  }

  const create = async () => {
    if (working) {
      return
    }

    setWorking(true)
    setFailure(null)

    try {
      await createStudioProfileOnce(profile)
      host.notify({ kind: 'success', message: 'hermretro profile created' })
      status.refetch?.()
    } catch (error) {
      setFailure(String(error?.message ?? error))
    } finally {
      setWorking(false)
    }
  }

  const starting = profile.studio?.installed && !working

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          'hermretro works in its own Hermes profile, so it has exactly the tools and skills game development needs, and your other chats stay as they are.'
      }),
      jsx(Facts, { rows: PROFILE_FACTS }),
      starting
        ? jsxs('div', {
            className: 'cs-col',
            children: [
              jsx(Working, { children: 'The profile is created. Waiting for Hermes to start it…' }),
              jsx('div', {
                children: jsx(Button, { disabled: working || updating, onClick: create, size: 'sm', variant: 'ghost', children: 'Set it up again' })
              })
            ]
          })
        : working
          ? jsx(Working, { children: 'Creating the profile…' })
          : jsxs('div', {
              className: 'cs-actions',
              children: [
                jsx(Button, { disabled: updating, onClick: create, size: 'sm', variant: 'default', children: 'Create the hermretro profile' }),
                jsx('span', { className: 'cs-faint', children: `The "${profile.name}" profile, where the plugin is installed, is not changed.` })
              ]
            }),
      profile.studio?.installed ? jsx(ClaudeSignIn, { login: profile.studio.claude_login, status }) : null,
      failure ? jsx('p', { className: 'cs-error', children: failure }) : null
    ]
  })
}

/** The studio profile uses Claude through DirectSDK and has no Claude login it can use: sign it in, in the browser. */
function ClaudeSignIn({ login, status }) {
  const [working, setWorking] = useState(false)
  const [failure, setFailure] = useState(null)

  if (!login || login.signed_in) {
    return null
  }

  const signIn = async () => {
    setWorking(true)
    setFailure(null)

    try {
      await signInToClaude()
      host.notify({ kind: 'success', message: 'Signed in to Claude' })
      status.refetch?.()
    } catch (error) {
      setFailure(String(error?.message ?? error))
    } finally {
      setWorking(false)
    }
  }

  return jsxs('div', {
    className: 'cs-col',
    children: [
      working
        ? jsx(Working, { children: 'Waiting for the Claude sign-in in your browser…' })
        : jsx('div', { children: jsx(Button, { onClick: signIn, size: 'sm', variant: 'default', children: 'Sign in to Claude' }) }),
      failure ? jsx('p', { className: 'cs-error', children: failure }) : null
    ]
  })
}
