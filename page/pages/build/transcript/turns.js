// A conversation as turns, and the numbered builds among them.
import { replyAssets } from './reply.js'
import { assetKind, BUILD_STEPS, HIDDEN_STEPS, shortTool, stepImages, stepWords } from './step-words.js'

/** The flat transcript as turns: each user message and everything until the next one. */
export function deriveTurns(items) {
  const turns = []
  let current = null

  items.forEach((item, index) => {
    // A turn nobody typed here (started in the full chat, or an automation) follows the last one's end.
    if (item.kind === 'user' || !current || (current.ended && item.kind !== 'end')) {
      current = { key: `t${index}`, user: item.kind === 'user' ? item : null, items: item.kind === 'user' ? [] : [item], ended: false }
      turns.push(current)
    } else {
      current.items.push(item)
    }

    if (item.kind === 'end') {
      current.ended = true
    }
  })

  return turns
}

/** One turn, as the reply shows it: the words before its first step, the steps (with the words between
 *  them as notes), the words after its last step, and what needs the user. */
export function turnParts(turn, root) {
  const tokens = []
  const prompts = []
  const errors = []
  let end = null
  let report = null
  let reportAt = null
  const hasCard = turn.items.some(item => item.kind === 'clarify')

  for (const item of turn.items) {
    if (item.kind === 'assistant' && item.text.trim()) {
      tokens.push({ type: 'text', item })
    } else if (item.kind === 'tools') {
      for (const tool of item.tools) {
        const short = shortTool(tool.name)

        // The build card's words: the last report the turn made.
        const reported = short === 'build_report' && tool.state !== 'failed' ? (tool.info?.report ?? tool.report) : null

        if (reported) {
          report = reported
          reportAt = tool.info?.reportedAt ?? tool.finishedAt ?? tool.startedAt ?? null
        }

        if (!HIDDEN_STEPS.has(short) && !(short === 'clarify' && hasCard)) {
          tokens.push({ type: 'step', tool })
        }
      }
    } else if (item.kind === 'clarify' || item.kind === 'approval') {
      if (item.answered) {
        tokens.push({ type: 'asked', item })
      } else {
        prompts.push(item)
      }
    } else if (item.kind === 'error') {
      errors.push(item)
    } else if (item.kind === 'end') {
      end = item
    }
  }

  const first = tokens.findIndex(token => token.type !== 'text')
  const last = tokens.length - 1 - [...tokens].reverse().findIndex(token => token.type !== 'text')
  const intro = first === -1 ? tokens : tokens.slice(0, first)
  const outro = first === -1 ? [] : tokens.slice(last + 1)
  const entries = first === -1 ? [] : tokens.slice(first, last + 1).map(token => (token.type === 'text' ? { type: 'note', item: token.item } : token))
  const steps = entries.filter(entry => entry.type === 'step').map(entry => entry.tool)
  const assets = []

  for (const tool of steps) {
    for (const path of stepImages(tool, root)) {
      const known = assets.findIndex(asset => asset.path === path)
      // Only looked at (never written) by every step of the turn that touched it.
      const looked = LOOK_STEPS.test(shortTool(tool.name)) && (known === -1 || assets[known].looked)

      if (known !== -1) {
        assets.splice(known, 1)
      }

      assets.push({ path, version: tool.id, kind: assetKind(path), step: stepWords(tool)[1], at: tool.startedAt ?? null, looked })
    }
  }

  const builds = steps.filter(tool => BUILD_STEPS.has(shortTool(tool.name)))
  const lastBuild = builds[builds.length - 1] ?? null
  const presented = [...steps].reverse().find(tool => shortTool(tool.name) === 'present_game' && tool.state === 'done') ?? null

  return {
    intro: intro.map(token => token.item),
    outro: outro.map(token => token.item),
    entries,
    steps,
    prompts,
    errors,
    end,
    assets,
    built: builds.some(tool => tool.state === 'done'),
    buildFailed: lastBuild?.state === 'failed' ? (lastBuild.info?.error ?? 'The build failed.') : null,
    buildState: turnBuildState(turn),
    report,
    reportAt,
    note: presented?.info?.note ?? null,
    running: steps.find(tool => tool.state === 'running') ?? null
  }
}

// The steps that make a numbered build (a present or a player refresh alone does not).
const COMPILE_STEPS = new Set(['rom_build', 'web_build'])

/** How a turn's builds went, cheaply: null (it did not build), 'built' or 'failed' (its last compile). */
function turnBuildState(turn) {
  let state = null

  for (const item of turn.items) {
    if (item.kind === 'tools') {
      for (const tool of item.tools) {
        if (COMPILE_STEPS.has(shortTool(tool.name)) && (tool.state === 'done' || tool.state === 'failed')) {
          state = tool.state === 'done' ? 'built' : 'failed'
        }
      }
    }
  }

  return state
}

/** The conversation's builds in order, numbered from 1: one per turn that compiled the game, with the
 *  card's title (the report's, else the message that asked for it) and when it ran. */
export function buildHistory(turns) {
  const builds = []

  turns.forEach((turn, index) => {
    const state = turnBuildState(turn)

    if (!state) {
      return
    }

    let report = null
    let endAt = null
    let startAt = turn.user?.at ?? null
    let thumb = null

    for (const item of turn.items) {
      if (item.kind === 'end') {
        endAt = item.at ?? endAt
        startAt = startAt ?? item.startedAt ?? null
      } else if (item.kind === 'tools') {
        for (const tool of item.tools) {
          if (shortTool(tool.name) === 'build_report' && tool.state !== 'failed') {
            report = tool.info?.report ?? tool.report ?? report
          }

          for (const path of tool.state === 'failed' ? [] : (tool.info?.images ?? [])) {
            if (assetKind(path) === 'Playtest frame') {
              thumb = { path, version: tool.id, kind: 'Playtest frame' }
            }
          }

          startAt = startAt ?? tool.startedAt ?? null
        }
      }
    }

    const asked = String(turn.user?.text ?? '').trim().split('\n')[0]

    builds.push({
      n: builds.length + 1,
      key: turn.key,
      index,
      state,
      title: report?.title ?? (asked ? (asked.length > 48 ? `${asked.slice(0, 47)}…` : asked) : `Build ${builds.length + 1}`),
      startAt,
      endAt,
      thumb
    })
  })

  return builds
}

/** Whether a turn built the game (cheap: the transcript asks it of every turn): a build step finished, and its
 *  last compile did not fail (a retry that stopped leaves the earlier turn's build the one that plays). */
export function turnBuilt(turn) {
  return (
    turnBuildState(turn) !== 'failed' &&
    turn.items.some(item => item.kind === 'tools' && item.tools.some(tool => tool.state === 'done' && BUILD_STEPS.has(shortTool(tool.name))))
  )
}

// Steps that only look at a picture (it is shown under the step, but the turn did not make it).
const LOOK_STEPS = /^(vision_analyze|read_file|search_files|browser_exec|.+_inspect|.+_analyze|graphics_analyze_scene)$/

/** What a turn made, for the folded line and the Assets panel: the pictures its steps wrote and its
 *  replies delivered, without ones it only looked at and without playtest frames. */
export function madeAssets(parts, root) {
  const made = parts.assets.filter(asset => !asset.looked && asset.kind !== 'Playtest frame')

  for (const asset of replyAssets([...parts.intro, ...parts.outro], root)) {
    if (asset.kind !== 'Playtest frame' && !made.some(entry => entry.path === asset.path)) {
      made.push(asset)
    }
  }

  return made
}
