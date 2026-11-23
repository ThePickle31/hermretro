// "Worked for…": a turn's steps, collapsed, Simple or Technical.
import { atom, Codicon, jsx, jsxs, useState, useValue } from '#sdk'
import { AssetImage, AssetStrip, LatestAsset } from '#pages/build/assets/images.js'
import { spanWords } from '#shared/ui/time.js'
import { Elapsed } from '#shared/ui/elapsed.js'
import { GIST_WORDS, GROUP_MIN_STEPS, groupTitle, MINOR_STEPS, workGroups } from './groups.js'
import { SUGGESTED } from './questions.js'
import { shortTool, stepDetail, stepWords } from './step-words.js'
import { madeAssets } from './turns.js'

function StepRow({ tool, assets, onOpenAsset, freshFrom }) {
  const [running, done] = stepWords(tool)
  const live = tool.state === 'running'
  const detail = stepDetail(tool)
  const percent = typeof tool.progress?.percent === 'number' ? Math.max(0, Math.min(100, tool.progress.percent)) : null

  return jsxs('div', {
    className: 'cs-b-tool',
    'data-state': tool.state,
    children: [
      jsxs('div', {
        className: 'cs-b-tool-line',
        children: [
          jsx('span', {
            className: 'cs-b-ico',
            children: live
              ? jsx('i', { className: 'cs-b-spin' })
              : jsx(Codicon, { name: tool.state === 'failed' ? 'error' : tool.state === 'stopped' ? 'debug-stop' : 'check', size: 12 })
          }),
          jsx('span', { className: live ? 'cs-b-tool-name cs-b-shimmer' : 'cs-b-tool-name', children: live ? running : tool.state === 'failed' ? `${running} failed` : done }),
          detail ? jsx('span', { className: 'cs-b-tool-detail', title: detail, children: detail }) : null,
          jsx('span', { className: 'cs-grow' }),
          live ? null : typeof tool.duration === 'number' && tool.duration >= 1 ? jsx('span', { className: 'cs-b-dur', children: spanWords(tool.duration * 1000) }) : null
        ]
      }),
      percent != null && live ? jsx('div', { className: 'cs-b-bar', children: jsx('i', { style: { width: `${percent}%` } }) }) : null,
      assets.length ? jsx('div', { className: 'cs-b-tool-assets', children: jsx(AssetStrip, { assets, freshFrom, onOpen: onOpenAsset }) }) : null
    ]
  })
}

/** One line of an open "Worked for…": a step with its pictures, a note, or the user's answer. */
function workedEntry(entry, index, assetsByStep, freshFrom, onOpenAsset) {
  if (entry.type === 'step') {
    return jsx(StepRow, { assets: assetsByStep.get(entry.tool.id) ?? [], freshFrom, onOpenAsset, tool: entry.tool }, entry.tool.id ?? `s${index}`)
  }

  if (entry.type === 'asked') {
    const answers = entry.item.answers ?? (entry.item.answered && entry.item.answered !== 'answered' && entry.item.answered !== 'answered elsewhere' ? [entry.item.answered] : [])

    return jsxs(
      'div',
      {
        className: 'cs-b-tool',
        'data-state': 'done',
        children: [
          jsxs('div', {
            className: 'cs-b-tool-line',
            children: [
              jsx('span', { className: 'cs-b-ico', children: jsx(Codicon, { name: 'check', size: 12 }) }),
              jsx('span', { className: 'cs-b-tool-name', children: entry.item.kind === 'approval' ? 'You answered an approval' : 'You answered' })
            ]
          }),
          answers.length ? jsx('div', { className: 'cs-b-chips', children: answers.map((answer, position) => jsx('span', { className: 'cs-b-chip', children: String(answer).replace(SUGGESTED, '') }, position)) }) : null
        ]
      },
      `a${index}`
    )
  }

  return jsx('p', { className: 'cs-b-note', children: entry.item.text }, `n${index}`)
}

/** A few pictures overlapping, as a hint of what a turn or phase made (plain images: the stack sits
 *  inside a button). */
function AssetStack({ assets, max = 4 }) {
  const shown = assets.slice(-max)

  return jsx('span', {
    'aria-hidden': true,
    className: 'cs-b-stack',
    children: shown.map(asset => jsx('span', { className: 'cs-b-stack-i', children: jsx(AssetImage, { asset }) }, `${asset.path}#${asset.version}`))
  })
}

/** A step in the simple view: what it did in plain words, with what it made. */
function SimpleStep({ tool, assets, onOpenAsset, freshFrom }) {
  const [running, done] = stepWords(tool)
  const live = tool.state === 'running'
  const failed = tool.state === 'failed'

  return jsxs('div', {
    className: 'cs-b-tool',
    'data-state': tool.state,
    children: [
      jsxs('div', {
        className: 'cs-b-tool-line',
        children: [
          jsx('span', {
            className: 'cs-b-ico',
            children: live ? jsx('i', { className: 'cs-b-spin' }) : jsx(Codicon, { name: failed ? 'error' : tool.state === 'stopped' ? 'debug-stop' : 'check', size: 12 })
          }),
          jsx('span', { className: live ? 'cs-b-tool-name cs-b-shimmer' : 'cs-b-tool-name', children: live ? `${running}…` : failed ? `${running} failed` : done }),
          failed && tool.info?.error ? jsx('span', { className: 'cs-b-tool-detail', title: tool.info.error, children: tool.info.error }) : null
        ]
      }),
      assets.length ? jsx('div', { className: 'cs-b-tool-assets', children: jsx(AssetStrip, { assets, freshFrom, onOpen: onOpenAsset }) }) : null
    ]
  })
}

/** One of a turn's groups (Planned it, Drew the art…): a line that opens to its steps. The simple view
 *  leaves out glances (reading a guide, inspecting the project) that showed nothing. */
function WorkGroup({ group, live, open, onToggle, assetsByStep, freshFrom, onOpenAsset }) {
  const steps = group.entries.filter(entry => entry.type === 'step').map(entry => entry.tool)
  const running = steps.some(tool => tool.state === 'running')
  const failed = !running && steps.length > 0 && steps[steps.length - 1].state === 'failed'
  const made = steps.flatMap(tool => (assetsByStep.get(tool.id) ?? []).filter(asset => !asset.looked && asset.kind !== 'Playtest frame'))
  const seconds = steps.reduce((sum, tool) => sum + (typeof tool.duration === 'number' ? tool.duration : 0), 0)
  const shown = group.entries.filter(entry => !(entry.type === 'step' && entry.tool.state === 'done' && MINOR_STEPS.test(shortTool(entry.tool.name)) && !assetsByStep.get(entry.tool.id)?.length))
  const icon = running ? jsx('i', { className: 'cs-b-spin' }) : jsx(Codicon, { name: failed ? 'error' : 'check', size: 12 })

  return jsxs('div', {
    className: 'cs-b-ph',
    'data-group': group.kind,
    'data-open': open ? 'true' : 'false',
    'data-state': running ? 'running' : failed ? 'failed' : 'done',
    children: [
      jsxs('button', {
        'aria-expanded': open,
        className: 'cs-b-ph-head',
        onClick: onToggle,
        type: 'button',
        children: [
          jsx('span', { className: 'cs-b-ico', children: icon }),
          jsx('span', { className: running && live ? 'cs-b-ph-name cs-b-shimmer' : 'cs-b-ph-name', children: groupTitle(group, running && live, made.length > 0) }),
          jsx('span', { className: 'cs-grow' }),
          made.length && !open ? jsx(AssetStack, { assets: made, max: 3 }) : null,
          jsx('span', { className: 'cs-b-ph-meta', children: `${steps.length} ${steps.length === 1 ? 'step' : 'steps'}${seconds >= 1 ? ` · ${spanWords(seconds * 1000)}` : ''}` }),
          jsx(Codicon, { name: open ? 'chevron-down' : 'chevron-right', size: 12 })
        ]
      }),
      open
        ? jsx('div', {
            className: 'cs-b-ph-body',
            children: shown.length
              ? shown.map((entry, position) =>
                  entry.type === 'step'
                    ? jsx(SimpleStep, { assets: assetsByStep.get(entry.tool.id) ?? [], freshFrom, onOpenAsset, tool: entry.tool }, entry.tool.id ?? `s${position}`)
                    : workedEntry(entry, `${group.kind}.${position}`, assetsByStep, freshFrom, onOpenAsset)
                )
              : jsx('span', { className: 'cs-faint cs-small', children: 'Only small checks here. Technical shows them.' })
          })
        : null
    ]
  })
}

// Simple (five plain groups) or Technical (every step with its command or detail), for every turn.
const WORKED_MODE = atom('simple')

export function Worked({ parts, live, startedAt, endedAt, status, root, onOpenAsset }) {
  const [open, setOpen] = useState(null)
  const [openGroups, setOpenGroups] = useState({})
  const mode = useValue(WORKED_MODE)
  const shown = open ?? live
  const count = parts.steps.length
  const freshFrom = live ? Date.now() - 4_000 : null
  const icon = live
    ? jsx('i', { className: 'cs-b-spin' })
    : jsx(Codicon, { name: status === 'interrupted' ? 'debug-stop' : status === 'error' ? 'error' : 'check', size: 12 })
  const took = startedAt && endedAt ? spanWords(endedAt - startedAt) : null
  // Short turns stay one plain list; longer ones fold into the fixed groups.
  const { groups: allGroups, last } = workGroups(parts.entries)
  const groups = count >= GROUP_MIN_STEPS ? allGroups : []
  const headline = live
    ? jsxs('span', { className: 'cs-b-shimmer', children: ['Working for ', jsx(Elapsed, { since: startedAt ?? Date.now() })] })
    : status === 'interrupted'
      ? `Stopped${took ? ` after ${took}` : ''}`
      : took
        ? `Worked for ${took}`
        : 'Worked on it'
  const assetsByStep = new Map()

  for (const asset of parts.assets) {
    const list = assetsByStep.get(asset.version) ?? []

    list.push(asset)
    assetsByStep.set(asset.version, list)
  }

  const made = madeAssets(parts, root)
  const latest = live ? parts.assets[parts.assets.length - 1] : null
  // In words, what it did: "drew the art, set up the level, built it".
  const gist = !live && allGroups.length > 1 ? allGroups.filter(group => GIST_WORDS[group.kind]).map(group => GIST_WORDS[group.kind]) : []
  const groupOpen = (group, index) => openGroups[group.kind] ?? (live && group.kind === last)

  return jsxs('div', {
    className: `cs-b-wk${live ? ' live' : ''}`,
    'data-open': shown ? 'true' : 'false',
    children: [
      jsxs('div', {
        className: 'cs-b-wk-row',
        children: [
          jsxs('button', {
            'aria-expanded': shown,
            className: 'cs-b-wk-head',
            onClick: () => setOpen(!shown),
            type: 'button',
            children: [
              jsx('span', { className: `cs-b-ico ${status ?? ''}`, children: icon }),
              jsx('b', { children: headline }),
              gist.length ? jsx('span', { className: 'cs-faint cs-b-gist', children: `· ${gist.join(', ')}` }) : count ? jsx('span', { className: 'cs-faint', children: `· ${count} ${count === 1 ? 'step' : 'steps'}` }) : null,
              jsx(Codicon, { name: shown ? 'chevron-down' : 'chevron-right', size: 12 })
            ]
          }),
          made.length && !shown
            ? jsxs('button', {
                'aria-label': `See the ${made.length === 1 ? 'picture' : `${made.length} pictures`} this made`,
                className: 'cs-b-wk-assets',
                onClick: event => onOpenAsset?.(made[0], event.currentTarget),
                type: 'button',
                children: [jsx(AssetStack, { assets: made }), jsx('span', { children: `${made.length} ${made.length === 1 ? 'asset' : 'assets'}` })]
              })
            : null
        ]
      }),
      jsx('div', {
        className: 'cs-b-wk-body',
        children: jsxs('div', {
          className: `cs-b-wk-inner${mode === 'simple' && groups.length > 1 ? ' phased' : ''}`,
          children: [
            shown && count
              ? jsx('div', {
                  className: 'cs-b-wk-mode',
                  children: jsx('div', {
                    'aria-label': 'How much detail',
                    className: 'cs-v-seg',
                    role: 'tablist',
                    children: [
                      ['simple', 'Simple'],
                      ['technical', 'Technical']
                    ].map(([key, label]) =>
                      jsx('button', { 'aria-selected': mode === key, className: mode === key ? 'on' : '', onClick: () => WORKED_MODE.set(key), role: 'tab', type: 'button', children: label }, key)
                    )
                  })
                }, 'mode')
              : null,
            ...(mode === 'simple' && groups.length > 1
              ? [jsx('div', { className: 'cs-b-phases', children: groups.map((group, index) =>
                  jsx(
                    WorkGroup,
                    {
                      assetsByStep,
                      freshFrom,
                      group,
                      live,
                      onOpenAsset,
                      onToggle: () => setOpenGroups(current => ({ ...current, [group.kind]: !groupOpen(group, index) })),
                      open: groupOpen(group, index)
                    },
                    group.kind
                  )
                ) }, 'groups')]
              : mode === 'simple'
                ? parts.entries.map((entry, index) =>
                    entry.type === 'step'
                      ? jsx(SimpleStep, { assets: assetsByStep.get(entry.tool.id) ?? [], freshFrom, onOpenAsset, tool: entry.tool }, entry.tool.id ?? `s${index}`)
                      : workedEntry(entry, index, assetsByStep, freshFrom, onOpenAsset)
                  )
                : parts.entries.map((entry, index) => workedEntry(entry, index, assetsByStep, freshFrom, onOpenAsset))),
            live && !parts.running && !parts.prompts.length ? jsx('div', { className: 'cs-b-tool cs-b-next', children: jsx('span', { className: 'cs-b-shimmer', children: 'Thinking about the next step…' }) }, 'next') : null,
            latest ? jsx(LatestAsset, { asset: latest, onOpen: onOpenAsset }, 'latest') : null
          ]
        })
      })
    ]
  })
}
