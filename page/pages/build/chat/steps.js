// A tool call as a step of the conversation.
import { PRESENT_TOOL, REPORT_TOOL } from '#app/tools.js'
import { normalizeReport } from './report.js'
import { toolResultObject } from './tool-results.js'

export function toolFailed(payload) {
  const result = toolResultObject(payload?.result)

  return Boolean(payload?.error || result?.ok === false || result?.isError === true || (result && typeof result.error === 'string' && result.error))
}

// Argument keys worth keeping on a step (labels, details, image paths). Bulky ones (file bodies, code,
// patches) are dropped: a long conversation holds hundreds of steps.
const STEP_ARG_KEYS = ['name', 'file_path', 'path', 'command', 'image_url', 'assetPath', 'outputPath', 'kind', 'query', 'url', 'question', 'questions', 'goal', 'sceneId', 'note']

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
export function stepInfo(name, result) {
  const parsed = toolResultObject(result)

  if (!parsed || typeof parsed !== 'object') {
    return null
  }

  const content = parsed.structuredContent && typeof parsed.structuredContent === 'object' ? parsed.structuredContent : {}
  const text = value => (typeof value === 'string' && value ? value : null)
  const images = (Array.isArray(parsed.images) ? parsed.images : [])
    .map(image => (typeof image?.file === 'string' ? image.file.replace(/^MEDIA:/, '') : null))
    .filter(Boolean)
    .slice(0, 8)

  return {
    error: text(parsed.error) ? String(parsed.error).slice(0, 400) : null,
    projectRoot: text(content.projectRoot),
    assetPath: text(content.assetPath),
    outputPath: text(content.outputPath) ?? (text(content.path) && /\.(png|gif)$/i.test(content.path) ? content.path : null),
    images,
    note: String(name ?? '') === PRESENT_TOOL && parsed.ok === true ? text(parsed.studio?.note) : null,
    report: String(name ?? '') === REPORT_TOOL && parsed.ok === true ? normalizeReport(parsed.report) : null
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
