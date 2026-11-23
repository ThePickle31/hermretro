// The page's confirmed toolchain install status and reconciliation after a lost start acknowledgement.
import { useEffect, useQuery, useQueryClient, useRef, useState } from '#sdk'
import { callBackend, describeRequestError } from '#app/backend.js'
import { ID } from '#app/ids.js'
import { RPC_INSTALL } from '#app/rpc.js'
import { isUpdating } from '#app/update/lock.js'

const INSTALL_QUERY = [ID, 'install']
const PENDING_START = 'installStartPending'
const START_ACTION = 'start_admitted'
const START_TIMEOUT_MS = 60_000
const INSTALL_STATES = new Set(['idle', 'running', 'done', 'failed', 'cancelled', 'interrupted'])
export const INSTALL_STATUS_UNKNOWN = 'The install status could not be confirmed.'
const INSTALL_BUSY = 'The game tools are being installed.'

export function confirmedInstall(data, starting = false) {
  const install = data?.install

  return data?.ok === true && INSTALL_STATES.has(install?.state) && (!starting || install.state !== 'idle') &&
    (!(starting || install.state === 'running') || (typeof install.run_id === 'string' && Boolean(install.run_id.trim())))
}

function pendingStart(ctx) {
  return ctx.storage.get(PENDING_START, null)
}

function installBusy(data) {
  return data?.install?.state === 'running' || data?.install?.elsewhere === true
}

async function fetchInstall(queryClient, attempt, retireLegacy = false) {
  let answer

  try {
    const params = { action: 'status' }

    if (attempt) {
      params.admission = attempt.admission
    }

    if (retireLegacy) {
      params.retire_legacy = true
    }

    const { data } = await callBackend(RPC_INSTALL, params, 30_000)

    if (confirmedInstall(data)) {
      return data
    }

    answer = data
  } catch (error) {
    const { message, notLoaded } = describeRequestError(error)

    answer = { error: message, unsupported: notLoaded }
  }

  const previous = queryClient.getQueryData(INSTALL_QUERY)

  return { ...previous, ...answer, ok: false, install: previous?.install, code: answer?.code, expired_admission: answer?.expired_admission, unsupported: Boolean(answer?.unsupported), error: answer?.error || INSTALL_STATUS_UNKNOWN }
}

function expired(attempt, data) {
  return attempt && data?.expired_admission === attempt.admission
}

export function useInstall({ ctx, enabled, polling }) {
  const queryClient = useQueryClient()
  const preparing = useRef(false)
  const [submission, setSubmission] = useState(null)
  const attempt = pendingStart(ctx)
  const query = useQuery({
    queryKey: INSTALL_QUERY,
    queryFn: () => fetchInstall(queryClient, pendingStart(ctx)),
    enabled,
    refetchInterval: enabled ? arg => {
      const data = arg?.state ? arg.state.data : arg

      if (pendingStart(ctx) || data?.ok === false || installBusy(data)) {
        return 1_500
      }

      return polling ? 5_000 : false
    } : false,
    staleTime: 1_000,
    retry: false
  })

  const confirmed = !query.isError && confirmedInstall(query.data)
  const legacy = !query.isError && query.data?.code === 'BROKER_LEGACY' && !installBusy(query.data)
  const pending = attempt && !expired(attempt, query.data)
  const starting = submission === true || (Boolean(pending) && submission === attempt.admission)
  const statusError = query.isError ? describeRequestError(query.error).message : query.data?.error
  const unavailable = (pending && (attempt.error || INSTALL_STATUS_UNKNOWN)) || (!confirmed && (statusError || (query.data && INSTALL_STATUS_UNKNOWN))) || null
  const canStart = !pending && !installBusy(query.data) && (confirmed || legacy)

  useEffect(() => {
    if (expired(attempt, query.data) && pendingStart(ctx)?.admission === attempt.admission) {
      ctx.storage.set(PENDING_START, null)
    }
  }, [ctx, attempt?.admission, query.data?.expired_admission])

  const start = async () => {
    if (!enabled || !canStart || preparing.current || pendingStart(ctx) || isUpdating()) {
      return null
    }

    preparing.current = true
    setSubmission(true)
    let admission = null

    try {
      const { data } = await callBackend(RPC_INSTALL, { action: 'prepare_start' }, 30_000)

      if (data?.ok !== true || !Number.isFinite(data.admission) || data.admission <= 0) {
        return { ok: false, error: data?.error || INSTALL_STATUS_UNKNOWN }
      }

      // While the grant was requested, another mount may have submitted a Start or begun an update.
      if (pendingStart(ctx) || isUpdating()) {
        return null
      }

      // A remount or a lost request reply must still leave the grant for status to reconcile.
      ctx.storage.set(PENDING_START, { admission: data.admission })
      if (pendingStart(ctx)?.admission !== data.admission) {
        return { ok: false, error: INSTALL_STATUS_UNKNOWN }
      }

      admission = data.admission
    } catch (error) {
      return { ok: false, error: describeRequestError(error).message || INSTALL_STATUS_UNKNOWN }
    } finally {
      preparing.current = false
      setSubmission(admission)
    }

    try {
      let answer

      try {
        const result = await callBackend(RPC_INSTALL, { action: START_ACTION, admission }, START_TIMEOUT_MS)

        answer = result.data
      } catch (error) {
        answer = { error: describeRequestError(error).message }
      }

      const accepted = answer?.admission === admission && confirmedInstall(answer, true)
      const denied = answer?.ok === false && ((answer.admission === admission &&
        typeof answer.code === 'string' && Boolean(answer.code) && answer.code !== 'UNAVAILABLE') ||
        answer.error === `Unknown action '${START_ACTION}'.`)

      if (pendingStart(ctx)?.admission !== admission) {
        return null // A fresh status has already reconciled this attempt.
      }

      if (accepted) {
        // A poll begun before the acknowledgement must not overwrite the confirmed run.
        await queryClient.cancelQueries({ queryKey: INSTALL_QUERY })
        if (pendingStart(ctx)?.admission !== admission) {
          return null
        }

        queryClient.setQueryData(INSTALL_QUERY, answer)
      }

      if (accepted || denied) {
        ctx.storage.set(PENDING_START, null)
      } else {
        const error = answer?.error || INSTALL_STATUS_UNKNOWN

        ctx.storage.set(PENDING_START, { admission, error })
        answer = { ...answer, ok: false, code: 'UNAVAILABLE', error }
      }

      void query.refetch?.()

      return answer
    } finally {
      setSubmission(current => current === admission ? null : current)
    }
  }

  // The mutation needs its own read, including any pending Start saved before this page mounted.
  const confirmIdle = async () => {
    const before = pendingStart(ctx)
    const data = await fetchInstall(queryClient, before, true)
    const current = pendingStart(ctx)

    if (preparing.current || installBusy(data)) {
      return INSTALL_BUSY
    }

    if ((before && !expired(before, data)) || (current && !expired(current, data))) {
      return current?.error || before?.error || INSTALL_STATUS_UNKNOWN
    }

    return confirmedInstall(data) ? null : data.error
  }

  return { ...query, canStart, start, starting, unavailable, confirmIdle, updateBlock: legacy && !pending ? null : unavailable || (!confirmed ? INSTALL_STATUS_UNKNOWN : null) }
}
