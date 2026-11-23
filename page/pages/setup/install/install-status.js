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
  const named = typeof install?.run_id === 'string' && Boolean(install.run_id.trim())

  return data?.ok === true && INSTALL_STATES.has(install?.state) && (!starting || install.state !== 'idle') &&
    (install.worker_left === undefined || typeof install.worker_left === 'boolean') &&
    (starting ? named : install.state !== 'running' || named || (data.legacy_progress === true && !Object.hasOwn(install, 'run_id')))
}

function pendingStart(ctx) {
  return ctx.storage.get(PENDING_START, null)
}

function validAdmission(admission) {
  return typeof admission?.boot_id === 'string' && Boolean(admission.boot_id) &&
    Number.isFinite(admission.deadline) && admission.deadline > 0
}

function sameAdmission(left, right) {
  if (typeof left === 'number') {
    return left === right // The stored format before admissions carried a boot identity.
  }

  return validAdmission(left) && left.boot_id === right?.boot_id && left.deadline === right?.deadline
}

function installBusy(data) {
  return data?.install?.state === 'running' || data?.install?.elsewhere === true || data?.install?.worker_left === true
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

  return {
    ...previous,
    ...answer,
    ok: false,
    install: previous?.install,
    legacy_progress: previous?.legacy_progress,
    code: answer?.code,
    expired_admission: undefined,
    unsupported: Boolean(answer?.unsupported),
    error: answer?.error || INSTALL_STATUS_UNKNOWN
  }
}

function expired(attempt, data) {
  return attempt && data?.ok === true && sameAdmission(attempt.admission, data.expired_admission)
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
  const busy = installBusy(query.data)
  const legacy = !query.isError && query.data?.code === 'BROKER_LEGACY' && !busy
  const pending = attempt && !expired(attempt, query.data)
  const starting = submission === true || (Boolean(pending) && sameAdmission(submission, attempt.admission))
  const statusError = query.isError ? describeRequestError(query.error).message : query.data?.error
  const unavailable = (pending && (attempt.error || INSTALL_STATUS_UNKNOWN)) || (!confirmed && (statusError || (query.data && INSTALL_STATUS_UNKNOWN))) || null
  const canStart = !pending && !busy && (confirmed || legacy)

  useEffect(() => {
    if (expired(attempt, query.data) && sameAdmission(attempt.admission, pendingStart(ctx)?.admission)) {
      ctx.storage.set(PENDING_START, null)
    }
  }, [ctx, attempt, query.data])

  const start = async () => {
    if (!enabled || !canStart || preparing.current || pendingStart(ctx) || isUpdating()) {
      return null
    }

    preparing.current = true
    setSubmission(true)
    let admission = null

    try {
      const { data } = await callBackend(RPC_INSTALL, { action: 'prepare_start' }, 30_000)

      if (data?.ok !== true || !validAdmission(data.admission)) {
        return { ok: false, error: data?.error || INSTALL_STATUS_UNKNOWN }
      }

      // While the grant was requested, another mount may have submitted a Start or begun an update.
      if (pendingStart(ctx) || isUpdating()) {
        return null
      }

      // A remount or a lost request reply must still leave the grant for status to reconcile.
      ctx.storage.set(PENDING_START, { admission: data.admission })
      if (!sameAdmission(data.admission, pendingStart(ctx)?.admission)) {
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

      const accepted = sameAdmission(admission, answer?.admission) && confirmedInstall(answer, true)
      const denied = answer?.ok === false && ((sameAdmission(admission, answer.admission) &&
        typeof answer.code === 'string' && Boolean(answer.code) && answer.code !== 'UNAVAILABLE') ||
        answer.error === `Unknown action '${START_ACTION}'.`)

      if (!sameAdmission(admission, pendingStart(ctx)?.admission)) {
        return null // A fresh status has already reconciled this attempt.
      }

      if (accepted) {
        // A poll begun before the acknowledgement must not overwrite the confirmed run.
        await queryClient.cancelQueries({ queryKey: INSTALL_QUERY })
        if (!sameAdmission(admission, pendingStart(ctx)?.admission)) {
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

  return { ...query, busy, canStart, start, starting, unavailable, confirmIdle, updateBlock: legacy && !pending ? null : unavailable || (!confirmed ? INSTALL_STATUS_UNKNOWN : null) }
}
