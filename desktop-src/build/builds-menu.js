// The Build header: where the game stands, and its builds.
import { Button, Codicon, jsx, jsxs, Tip, useEffect, useRef, useState } from '../sdk.js'
import { callStudio } from '../core/backend.js'
import { AGENT } from '../core/ids.js'
import { RPC_BUILDS } from '../core/rpc.js'
import { timeOfDay } from '../core/time.js'
import { Elapsed } from '../ui/elapsed.js'

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

/** The snapshot the backend kept for a build: one taken while its turn ran (latest wins). */
function snapshotFor(build, snapshots) {
  if (!build.endAt || !Array.isArray(snapshots)) {
    return null
  }

  const from = (build.startAt ?? build.endAt - 3_600_000) - 2_000
  const to = build.endAt + 5_000
  let found = null

  for (const snap of snapshots) {
    const times = [snap.at, ...(Array.isArray(snap.builds) ? snap.builds : [])].filter(value => typeof value === 'number')

    for (const time of times) {
      if (time >= from && time <= to && (!found || time > found.time)) {
        found = { id: String(snap.id), time }
      }
    }
  }

  return found?.id ?? null
}

/** Builds ▾: every build of this conversation, newest first; Show scrolls to its card, Restore puts its
 *  files back (the backend saves the current ones first) and asks the agent to build it again. */
export function BuildsMenu({ builds, busy, game, onShow, onRestore }) {
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

    callStudio(RPC_BUILDS, { game: game.id }, 20_000)
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
  }, [open, game.id])

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
                            confirm === build.key
                              ? jsxs('span', {
                                  className: 'cs-b-brow-acts',
                                  children: [
                                    jsx(Button, {
                                      disabled: working,
                                      onClick: async () => {
                                        setWorking(true)
                                        const done = await onRestore(build, snapshot)

                                        setWorking(false)

                                        if (done) {
                                          setOpen(false)
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
                                          label: busy ? `Wait until ${AGENT} finishes` : snapshot ? `Put the game back to build #${build.n}` : snapshots === null ? 'Looking for this build\u2019s files…' : 'This build\u2019s files were not kept',
                                          children: jsx('span', {
                                            style: { display: 'inline-flex' },
                                            children: jsx(Button, { disabled: busy || !snapshot, onClick: () => setConfirm(build.key), size: 'sm', variant: 'outline', children: 'Restore' })
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
                children: confirm ? 'The game as it is now is saved first, then HermRetro builds the restored files as a new build.' : 'Restore makes a new build from an earlier one. Nothing is deleted.'
              })
            ]
          })
        : null
    ]
  })
}
