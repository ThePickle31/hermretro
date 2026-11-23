// A tool call as a step of the conversation.
import { PRESENT_TOOL, REPORT_TOOL, ROM_BUILD_TOOL } from '#app/tools.js'
import { normalizeReport } from './report.js'
import { toolBuildRef, toolResultObject } from './tool-results.js'

export function toolFailed(payload) {
  const result = toolResultObject(payload?.result)

  // An engine operation that ran but did not succeed (a build that stopped) says so in its structured content only.
  return Boolean(
    payload?.error ||
      payload?.is_error === true ||
      result?.ok === false ||
      result?.isError === true ||
      result?.structuredContent?.success === false ||
      (result && typeof result.error === 'string' && result.error)
  )
}

/** Why an engine operation did not succeed: its first error diagnostic, else its summary line (a warning is not
 *  the reason). */
function engineError(parsed, content) {
  if (content.success !== false) {
    return null
  }

  const diagnostics = Array.isArray(content.diagnostics) ? content.diagnostics : []
  const error = diagnostics.find(item => item?.severity === 'error' && typeof item.message === 'string')

  return error?.message ?? (typeof parsed.result === 'string' && parsed.result ? parsed.result : null)
}

// Argument keys worth keeping on a step (labels, details, image paths). Bulky ones (file bodies, code,
// patches) are dropped: a long conversation holds hundreds of steps.
const STEP_ARG_KEYS = ['name', 'file_path', 'path', 'command', 'image_url', 'assetPath', 'outputPath', 'sourcePath', 'kind', 'query', 'url', 'question', 'questions', 'goal', 'sceneId', 'note']

export function stepArgs(args) {
  if (!args || typeof args !== 'object') {
    return null
  }

  const kept = {}

  for (const key of STEP_ARG_KEYS) {
    const value = args[key]

    if (typeof value === 'string') {
      kept[key] = value.length > 400 ? `${value.slice(0, 400)}…` : value
    } else if (key === 'questions' && Array.isArray(value)) {
      kept.questions = value.slice(0, 8).map(question => (typeof question === 'string' ? question : String(question?.question ?? ''))).filter(Boolean)
    }
  }

  return Object.keys(kept).length ? kept : null
}

/** What the page keeps of a finished step's result: its error, the paths it made, a presentation. */
export function stepInfo(name, result, exactCall = true) {
  const value = toolResultObject(result)
  const buildRef = exactCall && name === ROM_BUILD_TOOL ? toolBuildRef(result, value) : null

  if (!value && !buildRef) {
    return null
  }

  const parsed = value ?? {}

  const content = parsed.structuredContent && typeof parsed.structuredContent === 'object' ? parsed.structuredContent : {}
  const text = value => (typeof value === 'string' && value ? value : null)
  const images = (Array.isArray(parsed.images) ? parsed.images : [])
    .map(image => (typeof image?.file === 'string' ? image.file.replace(/^MEDIA:/, '') : null))
    .filter(Boolean)
  const report = String(name ?? '') === REPORT_TOOL && parsed.ok === true ? normalizeReport(parsed.report) : null

  return {
    error: (text(parsed.error) ?? engineError(parsed, content))?.slice(0, 400) ?? null,
    projectRoot: text(content.projectRoot),
    assetPath: text(content.assetPath),
    outputPath: text(content.outputPath) ?? (text(content.path) && /\.(png|gif)$/i.test(content.path) ? content.path : null),
    buildRef,
    images: /(?:^|_)emulator_/.test(String(name)) ? images : images.slice(0, 8),
    note: String(name ?? '') === PRESENT_TOOL && parsed.ok === true ? text(parsed.studio?.note) : null,
    report,
    reportedAt: report && Number.isFinite(parsed.reportedAt) && parsed.reportedAt > 0 ? parsed.reportedAt : null
  }
}

/** The model, provider, effort and fast mode a conversation runs on, from `session.info` (an event, or the `info`
 *  of a create / resume). A field the payload leaves out keeps its last value. */
export function withInfo(chat, info) {
  if (!info || typeof info !== 'object') {
    return chat
  }

  const current = chat.info ?? {}
  const next = {
    model: typeof info.model === 'string' && info.model ? info.model : (current.model ?? null),
    provider: typeof info.provider === 'string' && info.provider ? info.provider : (current.provider ?? null),
    effort: typeof info.reasoning_effort === 'string' ? info.reasoning_effort : (current.effort ?? ''),
    fast: typeof info.fast === 'boolean' ? info.fast : (current.fast ?? false)
  }

  return next.model === current.model && next.provider === current.provider && next.effort === current.effort && next.fast === current.fast
    ? chat
    : { ...chat, info: next }
}
