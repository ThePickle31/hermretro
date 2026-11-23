// The conversation.
import {
  Button,
  Codicon,
  jsx,
  jsxs,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState
} from '#sdk'
import { resumeBuildChat } from '#pages/build/chat/actions.js'
import { useUpdating } from '#app/update/lock.js'
import { InlinePlayer } from '#pages/build/player/inline-player.js'
import { PlayCard } from '#pages/build/player/play-card.js'
import { AssetViewer } from '#pages/build/viewer/asset-viewer.js'
import { AGENT } from '#app/ids.js'
import { playableSha } from '#app/player/stage.js'
import { AssetGame } from '#pages/build/assets/cache.js'
import { sendAssetChange } from '#pages/build/assets/changes.js'
import { TurnMemo } from './turn-view.js'
import { buildHistory, deriveTurns, turnBuilt } from './turns.js'

const TURN_PAGE = 40

export function Transcript({ ctx, chat, stored, game, playerOpen, onPlay, onClosePlayer, onSend, empty, focusTurn = null, onFocusHandled }) {
  const items = chat?.items ?? []
  const turns = useMemo(() => deriveTurns(items), [items])
  // Each turn's build (#n), the same object while it is unchanged so finished turns do not re-render.
  const buildCache = useRef(new Map())
  const builds = useMemo(() => {
    const byIndex = new Map()

    for (const build of buildHistory(turns)) {
      const sig = JSON.stringify(build)
      const known = buildCache.current.get(build.key)
      const kept = known && known.sig === sig ? known.build : build

      buildCache.current.set(build.key, { sig, build: kept })
      byIndex.set(build.index, kept)
    }

    return byIndex
  }, [turns])
  const root = useContext(AssetGame)
  const scroller = useRef(null)
  const stuck = useRef(true)
  const [behind, setBehind] = useState(false)
  const [limit, setLimit] = useState(TURN_PAGE)
  const [viewer, setViewer] = useState(null)
  const [openBuilds, setOpenBuilds] = useState(() => new Set())
  const toggleBuild = useCallback(key => {
    stuck.current = false
    setOpenBuilds(current => {
      const next = new Set(current)

      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }

      return next
    })
  }, [])
  const busy = Boolean(chat?.busy)

  // A new conversation starts at its end, with the page size reset.
  useLayoutEffect(() => {
    stuck.current = true
    setLimit(TURN_PAGE)
    setBehind(false)
    setViewer(null)
  }, [stored])

  // Earlier messages load above what the user is reading: keep their place.
  const keepFromBottom = useRef(null)

  // Follow the conversation while the user is at the bottom; otherwise offer a jump back.
  useLayoutEffect(() => {
    const element = scroller.current

    if (!element) {
      return
    }

    if (keepFromBottom.current != null) {
      element.scrollTop = element.scrollHeight - keepFromBottom.current
      keepFromBottom.current = null
    } else if (stuck.current) {
      element.scrollTop = element.scrollHeight
    } else {
      setBehind(true)
    }
  }, [items, chat?.queued, limit])

  // Pictures and cards that load after a render (a before/after, a thumbnail) grow the conversation:
  // keep the newest message in view while the user is at the bottom.
  useEffect(() => {
    const element = scroller.current
    const column = element?.firstElementChild

    if (!column || typeof ResizeObserver !== 'function') {
      return undefined
    }

    const observer = new ResizeObserver(() => {
      if (stuck.current && keepFromBottom.current == null) {
        element.scrollTop = element.scrollHeight
      }
    })

    observer.observe(column)

    return () => observer.disconnect()
  }, [stored])

  const onScroll = () => {
    const element = scroller.current

    if (!element) {
      return
    }

    const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 64

    stuck.current = atBottom

    if (atBottom && behind) {
      setBehind(false)
    }
  }

  const jump = () => {
    const element = scroller.current

    stuck.current = true
    setBehind(false)
    element?.scrollTo?.({ behavior: 'smooth', top: element.scrollHeight })
  }

  // "Show" in the Builds menu loads earlier messages if needed, then expands and highlights the turn.
  const [highlight, setHighlight] = useState(null)

  useEffect(() => {
    if (!focusTurn) {
      return undefined
    }

    const index = turns.findIndex(turn => turn.key === focusTurn.key)

    if (index === -1) {
      return undefined
    }

    if (index < turns.length - limit) {
      setLimit(turns.length - index)

      return undefined
    }

    if (builds.has(index) && index < turns.length - 1 && !openBuilds.has(focusTurn.key)) {
      stuck.current = false
      setOpenBuilds(current => new Set(current).add(focusTurn.key))

      return undefined
    }

    const node = scroller.current?.querySelector?.(`[data-turn="${focusTurn.key}"]`)

    if (!node) {
      return undefined
    }

    onFocusHandled(null)
    stuck.current = false
    node.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
    setHighlight({ node })

    return undefined
  }, [focusTurn, limit, openBuilds, builds, turns, onFocusHandled])

  useEffect(() => {
    if (!highlight) {
      return undefined
    }
    const { node } = highlight
    node.setAttribute('data-flash', 'true')

    const id = setTimeout(() => node.removeAttribute('data-flash'), 1600)

    return () => {
      clearTimeout(id)
      node.removeAttribute('data-flash')
    }
  }, [highlight])

  const openAsset = useCallback((assets, index, opener) => setViewer({ assets, index, opener }), [])
  const latestBuild = useMemo(() => {
    for (let index = turns.length - 1; index >= 0; index -= 1) {
      if (turnBuilt(turns[index])) {
        return index
      }
    }

    return -1
  }, [turns])
  const first = Math.max(0, turns.length - limit)
  const lastIndex = turns.length - 1
  // The model each turn's message went to before it: a reply names its model when that changed.
  const modelBefore = useMemo(() => {
    const result = []
    let seen = null

    turns.forEach((turn, index) => {
      result[index] = seen

      if (turn.user?.model) {
        seen = { model: turn.user.model, effort: turn.user.effort ?? '' }
      }
    })

    return result
  }, [turns])
  const playableGame = Boolean(game && game.webExport && playableSha(game))

  return jsxs('div', {
    className: 'cs-b-txwrap',
    children: [
      jsx('div', {
        className: 'cs-b-tx',
        onScroll,
        ref: scroller,
        children: jsxs('div', {
          className: 'cs-b-col',
          children: [
            first > 0
              ? jsx('div', { className: 'cs-b-earlier', children: jsx(Button, {
                    onClick: () => {
                      const element = scroller.current

                      keepFromBottom.current = element ? element.scrollHeight - element.scrollTop : null
                      setLimit(value => value + TURN_PAGE)
                    },
                    size: 'sm',
                    variant: 'ghost',
                    children: `Show ${Math.min(first, TURN_PAGE)} earlier messages`
                  }) }, 'earlier')
              : null,
            !turns.length ? empty : null,
            ...turns.slice(first).map((turn, offset) => {
              const index = first + offset

              return jsx(
                TurnMemo,
                {
                  build: builds.get(index) ?? null,
                  chatBusy: busy,
                  ctx,
                  game: index === latestBuild ? game : null,
                  isLast: index === lastIndex,
                  expanded: openBuilds.has(turn.key),
                  onToggleBuild: toggleBuild,
                  latestBuild: index === latestBuild,
                  live: busy && index === lastIndex,
                  turnStartedAt: busy && index === lastIndex ? (chat?.turnStartedAt ?? null) : null,
                  previousModel: modelBefore[index] ?? null,
                  onClosePlayer,
                  onOpenAsset: openAsset,
                  onPlay,
                  onSend,
                  playerOpen: index === latestBuild && playerOpen,
                  root,
                  stored,
                  turn
                },
                turn.key
              )
            }),
            ...(chat?.queued ?? []).map((item, index) =>
              jsxs(
                'div',
                {
                  className: 'cs-b-user queued',
                  children: [
                    jsx('span', { className: 'cs-b-qlabel', children: chat.lost?.length ? 'Waiting · sent when you continue' : `Queued · ${AGENT} reads this when it finishes` }),
                    jsx('span', { children: item.text })
                  ]
                },
                `q${index}`
              )
            ),
            chat?.lost?.length && !busy ? jsx(LostTurnCard, { chat, stored }, 'lost') : null,
            // A playable game whose conversation has not built it (it was built elsewhere): play it here, once the
            // agent is not working.
            latestBuild === -1 && playableGame && turns.length && !busy
              ? jsx('div', {
                  className: 'cs-b-her',
                  children: playerOpen
                    ? jsx(InlinePlayer, { ctx, game, note: null, onClose: onClosePlayer, stored }, `player:${game.id}`)
                    : jsx(PlayCard, { game, onPlay, state: 'ready' })
                })
              : null
          ]
        })
      }),
      behind ? jsxs('button', { className: 'cs-b-jump', onClick: jump, type: 'button', children: [jsx(Codicon, { name: 'arrow-down', size: 12 }), 'Latest'] }) : null,
      viewer
        ? jsx(AssetViewer, {
            assets: viewer.assets,
            chat,
            ctx,
            game,
            index: viewer.index,
            onClose: () => setViewer(null),
            onIndex: index => setViewer(current => ({ ...current, index })),
            onSend: stored ? (...args) => sendAssetChange(stored, ...args) : null,
            opener: viewer.opener,
            root,
            stored,
            turns
          })
        : null
    ]
  })
}

/** A conversation paused because Hermes restarted in the middle of a turn: nothing runs until the user
 *  says to go on. */
function LostTurnCard({ chat, stored }) {
  const waiting = chat.queued?.length ?? 0
  const updating = useUpdating()

  return jsxs('div', {
    className: 'cs-b-card warn',
    children: [
      jsxs('div', { className: 'cs-row', children: [jsx(Codicon, { name: 'debug-pause', size: 14 }), jsx('b', { children: `${AGENT} stopped partway through` })] }),
      jsx('p', {
        className: 'cs-small',
        children: `Hermes restarted while ${AGENT} was working, so its last turn did not finish. What it already made is kept. ${
          waiting ? `Continue to send your ${waiting === 1 ? 'waiting message' : `${waiting} waiting messages`}.` : `Continue to have ${AGENT} pick up where it stopped.`
        }`
      }),
      chat.lostFailure ? jsx('p', { className: 'cs-small', children: chat.lostFailure }) : null,
      jsx('div', {
        className: 'cs-row',
        children: jsx(Button, { disabled: Boolean(chat.resuming || updating), onClick: () => void resumeBuildChat(stored), size: 'sm', children: chat.resuming ? 'Continuing…' : 'Continue' })
      })
    ]
  })
}
