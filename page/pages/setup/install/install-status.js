// The page's confirmed toolchain install status and reconciliation after a lost start acknowledgement.
import { useEffect, useQuery, useQueryClient, useRef, useState } from '#sdk'
import { callBackend, describeRequestError } from '#app/backend.js'
import { ID } from '#app/ids.js'
import { RPC_INSTALL } from '#app/rpc.js'
import { isUpdating } from '#app/update/lock.js'

const INSTALL_QUERY = [ID, 'install']
const START_ACTION = 'start_fenced'
const START_TIMEOUT_MS = 60_000
const INSTALL_STATES = new Set(['idle', 'running', 'done', 'failed', 'cancelled', 'interrupted'])
export const INSTALL_STATUS_UNKNOWN = 'The install status could not be confirmed.'

export function confirmedInstall(data, starting = false) {
  const install = data?.install

  return data?.ok === true && INSTALL_STATES.has(install?.state) && (!starting || install.state !== 'idle') &&
    (!(starting || install.state === 'running') || (typeof install.run_id === 'string' && Boolean(install.run_id.trim())))
}

async function fetchInstall(queryClient) {
  const checkedAt = performance.now()
  const askedAt = Date.now()
  let answer

  try {
    const { data } = await callBackend(RPC_INSTALL, { action: 'status' }, 30_000)

    if (confirmedInstall(data)) {
      return { ...data, checkedAt, askedAt }
    }

    answer = data
  } catch (error) {
    const { message, notLoaded } = describeRequestError(error)

    answer = { error: message, unsupported: notLoaded }
  }

  const previous = queryClient.getQueryData(INSTALL_QUERY)

  return { ...previous, ...answer, ok: false, install: previous?.install, unsupported: Boolean(answer?.unsupported), error: answer?.error || INSTALL_STATUS_UNKNOWN }
}

function resolvesStart(attempt, data) {
  return confirmedInstall(data) && data.checkedAt > attempt.after && data.askedAt >= attempt.expiresAt
}

export function useInstall({ enabled, polling }) {
  const queryClient = useQueryClient()
  const startInFlight = useRef(false)
  const uncertain = useRef(null)
  const [starting, setStarting] = useState(false)
  const [unconfirmed, setUnconfirmed] = useState(null)
  const query = useQuery({
    queryKey: INSTALL_QUERY,
    queryFn: () => fetchInstall(queryClient),
    enabled,
    refetchInterval: enabled ? arg => {
      const data = arg?.state ? arg.state.data : arg

      if (unconfirmed || data?.ok === false || data?.install?.state === 'running') {
        return 1_500
      }

      return polling ? 5_000 : false
    } : false,
    staleTime: 1_000,
    retry: false
  })

  const confirmed = !query.isError && confirmedInstall(query.data)
  const resolved = confirmed && unconfirmed && resolvesStart(unconfirmed, query.data)
  const statusError = query.isError ? describeRequestError(query.error).message : query.data?.error
  const unavailable = (resolved ? null : unconfirmed?.error) || (!confirmed && (statusError || (query.data && INSTALL_STATUS_UNKNOWN))) || null

  useEffect(() => {
    if (resolved && uncertain.current === unconfirmed) {
      uncertain.current = null
      setUnconfirmed(null)
    }
  }, [resolved, unconfirmed])

  const start = async () => {
    if (!enabled || !confirmed || startInFlight.current || uncertain.current || isUpdating() || query.data.install.state === 'running') {
      return null
    }

    startInFlight.current = true
    setStarting(true)

    const expiresAt = Date.now() + START_TIMEOUT_MS

    try {
      let answer

      try {
        const result = await callBackend(RPC_INSTALL, { action: START_ACTION, expires_at: expiresAt }, START_TIMEOUT_MS)

        answer = result.data
      } catch (error) {
        answer = { error: describeRequestError(error).message }
      }

      const admissionEnd = answer?.start_expires_at
      const fenced = Number.isFinite(admissionEnd) && admissionEnd > 0 && admissionEnd <= expiresAt
      const accepted = fenced && confirmedInstall(answer, true)
      // Gateways from before start_fenced reject this action without a code.
      const denied = answer?.ok === false &&
        ((typeof answer.code === 'string' && Boolean(answer.code) && answer.code !== 'UNAVAILABLE') ||
          answer.error === `Unknown action '${START_ACTION}'.`)

      if (!accepted && !denied) {
        const attempt = { after: performance.now(), expiresAt: fenced ? admissionEnd : expiresAt, error: answer?.error || INSTALL_STATUS_UNKNOWN }

        uncertain.current = attempt
        setUnconfirmed(attempt)
        answer = { ...answer, ok: false, code: 'UNAVAILABLE', error: attempt.error }
      }

      if (accepted) {
        // A poll begun before the acknowledgement must not overwrite the confirmed run.
        await queryClient.cancelQueries({ queryKey: INSTALL_QUERY })
        queryClient.setQueryData(INSTALL_QUERY, answer)
      }

      if (!denied) {
        void query.refetch?.()
      }

      return answer
    } finally {
      startInFlight.current = false
      setStarting(false)
    }
  }

  // Read directly so the mutation can't reuse a cached or in-flight poll from before the user asked.
  const confirmIdle = async () => {
    const data = await fetchInstall(queryClient)

    if (startInFlight.current || data.install?.state === 'running') {
      return 'The game tools are being installed.'
    }

    const pending = uncertain.current

    return pending && !resolvesStart(pending, data) ? pending.error : (confirmedInstall(data) ? null : data.error)
  }

  return { ...query, confirmed, start, starting, unavailable, confirmIdle, updateBlock: unavailable || (!confirmed ? INSTALL_STATUS_UNKNOWN : null) }
}
