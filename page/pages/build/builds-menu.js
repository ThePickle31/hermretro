// The Build header: where the game stands, and its builds.
import { Button, Codicon, jsx, jsxs, Tip, useEffect, useRef, useState } from '#sdk'
import { callStudioOnly } from '#app/backend.js'
import { AGENT } from '#app/ids.js'
import { RPC_BUILDS } from '#app/rpc.js'
import { timeOfDay } from '#shared/ui/time.js'
import { Elapsed } from '#shared/ui/elapsed.js'

/** One pill beside the title: working, the build you would play, edits since it, or a failed build. */
export function BuildPill({ builds, chat, game }) {
  const last = builds[builds.length - 1] ?? null
  const good = [...builds].reverse().find(build => build.state === 'built') ?? null
  let tone = 'quiet'
  let label

  if (chat?.busy) {
    return jsxs('span', {
      className: 'cs-b-pill busy',
      children: [jsx('i', { className: 'cs-b-spin' }), 'Working · ', jsx(Elapsed, { since: chat.turnStartedAt ?? Date.now() })]
    })
  }

  if (!game) {
    label = 'Setting up'
  } else if (last?.state === 'failed') {
    tone = 'bad'
    label = `Build #${last.n} didn\u2019t finish`
  } else if (game.state === 'changed') {
    tone = 'warn'
    label = good ? `Edited since build #${good.n}` : 'Edited since the last build'
  } else if (good) {
    tone = 'good'
    label = `Build #${good.n} · up to date`
  } else if (game.state === 'ready') {
    tone = 'good'
    label = 'Built · up to date'
  } else if (game.state === 'failed') {
    tone = 'bad'
    label = 'The last build failed'
  } else {
    label = 'No builds yet'
  }

  return jsxs('span', { className: `cs-b-pill ${tone}`, children: [tone === 'quiet' ? null : jsx('i', { className: 'cs-b-pill-dot' }), label] })
}

/** A ROM build's reference can come directly from the result or its exact stored result row. */
function snapshotFor(build, snapshots) {
  if (!Array.isArray(snapshots)) {
    return null
  }

  const matches = snapshots.flatMap(snap => {
    const refs = Array.isArray(snap.buildRefs) ? snap.buildRefs : []
    const calls = Array.isArray(snap.buildCalls) ? snap.buildCalls : []
    const candidates = build.buildRef
      ? [build.buildRef]
      : calls.filter(call => build.resultCall && build.resultCall.id === call.id && build.resultCall.timestamp === call.timestamp).map(call => call.ref)

    return candidates.filter(ref => refs.includes(ref)).map(buildRef => ({ id: String(snap.id), buildRef }))
  })

  return matches.length === 1 ? matches[0] : null
}

/** Builds ▾: every build of this conversation, newest first; Show scrolls to its card, Restore puts its
 *  files back (the backend saves the current ones first) and asks the agent to build it again. */
export function BuildsMenu({ builds, busy, game, stored, onShow, onRestore }) {
  const [open, setOpen] = useState(false)
  const [snapshots, setSnapshots] = useState(null)
  const [confirm, setConfirm] = useState(null)
  const [working, setWorking] = useState(false)
  const wrap = useRef(null)

  useEffect(() => {
    if (!open) {
      setConfirm(null)

      return undefined
    }

    let live = true

    setSnapshots(null)
    callStudioOnly(RPC_BUILDS, { game: game.id, stored }, 20_000)
      .then(answer => live && setSnapshots(answer?.ok && Array.isArray(answer.builds) ? answer.builds : false))
      .catch(() => live && setSnapshots(false))

    const onDown = event => {
      if (wrap.current && !wrap.current.contains(event.target)) {
        setOpen(false)
      }
    }
    const onKey = event => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    window.addEventListener('mousedown', onDown)
    window.addEventListener('keydown', onKey)

    return () => {
      live = false
      window.removeEventListener('mousedown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [open, game.id, stored, builds])

  const newest = builds[builds.length - 1] ?? null
  const playingBuild = [...builds].reverse().find(build => build.state === 'built') ?? null
  const rows = [...builds].reverse()

  return jsxs('div', {
    className: 'cs-b-swwrap',
    ref: wrap,
    children: [
      jsxs(Button, {
        'aria-expanded': open,
        'aria-haspopup': 'menu',
        onClick: () => setOpen(!open),
        size: 'sm',
        variant: open ? 'secondary' : 'ghost',
        children: [jsx(Codicon, { name: 'history', size: 13 }), jsx('span', { className: 'cs-lbl', children: 'Builds' }), builds.length ? jsx('span', { className: 'cs-faint', children: builds.length }) : null, jsx(Codicon, { name: 'chevron-down', size: 11 })]
      }),
      open
        ? jsxs('div', {
            className: 'cs-b-sw-pop cs-b-builds',
            role: 'menu',
            children: [
              jsx('span', { className: 'cs-eyebrow', children: 'Builds' }),
              rows.length
                ? jsx('div', {
                    className: 'cs-b-sw-list',
                    children: rows.map(build => {
                      const current = build === newest
                      const playing = build === playingBuild
                      const snapshot = snapshotFor(build, snapshots)
                      // Restoring the build you already play changes nothing, unless the game was edited since.
                      const restorable = build.state === 'built' && !(playing && current && game.state !== 'changed')
                      const sameSnapshot = snapshot?.id === confirm?.id && snapshot?.buildRef === confirm?.buildRef

                      return jsxs(
                        'div',
                        {
                          className: current ? 'cs-b-brow on' : 'cs-b-brow',
                          children: [
                            jsx('span', { className: `cs-b-bn${build.state === 'failed' ? ' bad' : current ? '' : ' old'}`, children: `#${build.n}` }),
                            jsxs('span', {
                              className: 'cs-col cs-grow',
                              children: [
                                jsx('b', { children: build.title }),
                                jsx('small', {
                                  children: [build.endAt ? timeOfDay(build.endAt) : null, build.state === 'failed' ? 'didn\u2019t finish' : playing ? (game.state === 'changed' ? 'playing now · edited since' : 'playing now') : null]
                                    .filter(Boolean)
                                    .join(' · ')
                                })
                              ]
                            }),
                            confirm?.key === build.key
                              ? jsxs('span', {
                                  className: 'cs-b-brow-acts',
                                  children: [
                                    jsx(Button, {
                                      disabled: working || busy || !sameSnapshot || !restorable,
                                      onClick: async () => {
                                        setWorking(true)
                                        try {
                                          if (await onRestore(build, snapshot)) {
                                            setOpen(false)
                                          }
                                        } finally {
                                          setWorking(false)
                                        }
                                      },
                                      size: 'sm',
                                      children: working ? 'Restoring…' : `Restore #${build.n}`
                                    }),
                                    jsx(Button, { disabled: working, onClick: () => setConfirm(null), size: 'sm', variant: 'ghost', children: 'Cancel' })
                                  ]
                                })
                              : jsxs('span', {
                                  className: 'cs-b-brow-acts',
                                  children: [
                                    jsx(Button, {
                                      onClick: () => {
                                        setOpen(false)
                                        onShow(build.key)
                                      },
                                      size: 'sm',
                                      variant: 'ghost',
                                      children: 'Show'
                                    }),
                                    restorable
                                      ? jsx(Tip, {
                                          label: busy ? `Wait until ${AGENT} finishes` : snapshot ? `Put the game back to build #${build.n}` : snapshots === null ? 'Looking for this build\u2019s files…' : snapshots === false ? 'Could not load saved builds' : 'No saved files match this build',
                                          children: jsx('span', {
                                            style: { display: 'inline-flex' },
                                            children: jsx(Button, { disabled: busy || working || !snapshot, onClick: () => setConfirm({ key: build.key, ...snapshot }), size: 'sm', variant: 'outline', children: 'Restore' })
                                          })
                                        })
                                      : null
                                  ]
                                })
                          ]
                        },
                        build.key
                      )
                    })
                  })
                : jsx('p', { className: 'cs-b-sw-empty cs-small cs-faint', children: `No builds in this conversation yet. ${AGENT} builds the game after each change.` }),
              jsx('p', {
                className: 'cs-b-sw-foot',
                children: confirm ? 'The game as it is now is saved first, then HermRetro builds the restored files as a new build.' : 'Restore puts back the files from an earlier build.'
              })
            ]
          })
        : null
    ]
  })
}
