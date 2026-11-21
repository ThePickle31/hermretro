// Under the New Game box: says so when the hermretro profile has no signed-in model provider, and where to fix it.
// It reads the same `model.options` answer as the model picker (same query key, so no second request), which lists
// providers without calling a model: nothing is billed to find out.
import { Button, Codicon, host, jsx, jsxs, useQuery, useValue } from '#sdk'
import { chatRequest } from '#pages/build/chat/store.js'
import { AGENT, ID, STUDIO_PROFILE } from '#app/ids.js'
import { studioTarget } from '#app/routing.js'

export const PROVIDERS_HREF = '/settings?tab=providers'

/** True when Hermes answered with a provider list and none of it is signed in with a model; false while unknown. */
export function noProviderReady(data) {
  return Boolean(data && Array.isArray(data.providers) && !data.providers.some(item => item?.authenticated && Array.isArray(item.models) && item.models.length))
}

function activeProfile() {
  try {
    return host.state.profile?.get?.() ?? null
  } catch {
    return null
  }
}

export function ProviderNotice() {
  const gateway = useValue(host.state.gateway)
  const options = useQuery({
    queryKey: [ID, 'models', 'profile'],
    queryFn: () => chatRequest('model.options', {}, 30_000),
    enabled: gateway === 'open',
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1
  })

  if (!noProviderReady(options.data)) {
    return null
  }

  // Settings edit the profile the app is on unless "Applies to" says otherwise.
  const routed = Boolean(studioTarget()?.profile)
  const other = routed ? activeProfile() : null

  return jsxs('div', {
    className: 'cs-b-provider',
    role: 'status',
    children: [
      jsx(Codicon, { name: 'warning', size: 14 }),
      jsxs('span', {
        className: 'cs-grow',
        children: [
          jsx('b', { children: `No model provider is signed in for the ${STUDIO_PROFILE} profile yet.` }),
          ` ${AGENT} needs one to answer. Your idea stays here until you send it.`,
          routed
            ? ` Settings change the${other ? ` \u201c${other}\u201d` : ''} profile Hermes is on: under Settings \u203a Providers, choose ${STUDIO_PROFILE} in \u201cApplies to\u201d first.`
            : ''
        ]
      }),
      jsxs(Button, {
        onClick: () => host.navigate?.(PROVIDERS_HREF),
        size: 'sm',
        variant: 'outline',
        children: [jsx(Codicon, { name: 'settings-gear', size: 14 }), 'Open provider settings']
      })
    ]
  })
}
