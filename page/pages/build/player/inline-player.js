// The game inside the build card that last built it (contract: docs/dev/STUDIO-PAGES.md "The game,
// in the conversation"). The ModRetro player runs in its frame with its own controls hidden; this
// draws them: one bar, the game at a whole-number scale (bare screen or the Chromatic around it), and
// the play-test panel beside it (or under it in a narrow chat, or folded to a tab).
import { jsx, jsxs, useEffect, useLayoutEffect, useMemo, useQuery, useRef, useState, useValue } from '#sdk'
import { callStudio } from '#app/backend.js'
import { ID } from '#app/ids.js'
import { RPC_PLAYER } from '#app/rpc.js'
import { usePlayerBridge } from '#shared/player/bridge.js'
import { claimLive, LIVE_PLAYER, releaseLive } from '#shared/player/live.js'
import { CMD } from '#shared/player/protocol.js'
import { PlayerAway, PlayerNotice, PlayerStage, playableSha } from '#shared/player/stage.js'
import { AnnotateBar, AnnotatePanel } from './annotate-panel.js'
import { sendMarks, useAnnotate } from './annotate.js'
import { BarButton, ControlBar } from './control-bar.js'
import { FoldedPanel, KeyHints, PlaytestPanel } from './playtest-panel.js'
import { usePlayerPrefs } from './prefs.js'
import { askAboutMoment, reportCheck } from './report-flow.js'
import { playerSize } from './scale.js'
import { usePlaytest } from './use-playtest.js'

const PANEL_WIDTH = 300
const FOLD_WIDTH = 34
const STAGE_PAD = 16
/** Below this width the panel goes under the game as tabs. */
const NARROW = 760
/** The game may use this share of the window's height. */
const HEIGHT_SHARE = 0.74

/** The element's width and the window's height, kept current. */
function useRoom(ref) {
  const [room, setRoom] = useState({ width: 0, height: typeof window === 'undefined' ? 800 : window.innerHeight })

  useLayoutEffect(() => {
    const element = ref.current

    if (!element) {
      return undefined
    }

    const measure = () => setRoom({ width: element.clientWidth, height: window.innerHeight })
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null

    observer?.observe(element)
    window.addEventListener('resize', measure)
    measure()

    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [])

  return room
}

/** True while `ref`'s element is the full-screen element. */
function useFullScreen(ref) {
  const [full, setFull] = useState(false)

  useEffect(() => {
    const change = () => setFull(Boolean(ref.current) && document.fullscreenElement === ref.current)

    document.addEventListener('fullscreenchange', change)

    return () => document.removeEventListener('fullscreenchange', change)
  }, [])

  return full
}

const accentOf = element => (element ? getComputedStyle(element).getPropertyValue('--ui-accent').trim() : '')

export function InlinePlayer({ ctx, game, stored, note, report, build, onClose }) {
  const surface = `build:${game.id}`
  const owner = useValue(LIVE_PLAYER)
  const live = owner === surface

  // Opening it is the user's (or the agent's) explicit "play now": it takes the game from the Emulator
  // page, not from a tab beside the chat, which offers "Bring it here" instead.
  useEffect(() => {
    if (owner === null || owner === 'page') {
      claimLive(surface)
    }
  }, [owner, surface])

  useEffect(() => () => releaseLive(surface), [surface])

  const sha = playableSha(game)
  const [reload, setReload] = useState(0)
  const [prefs, setPrefs] = usePlayerPrefs(ctx)
  const player = useQuery({
    queryKey: [ID, 'player', 'build', game.id, sha, reload],
    queryFn: () => callStudio(RPC_PLAYER, { id: game.id }, 30_000),
    enabled: live,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false
  })

  const rootRef = useRef(null)
  const frameRef = useRef(null)
  const screenRef = useRef(null)
  const frameKey = `${game.id}:${sha}:${reload}`
  // A new frame (rebuilt game, Refresh, or the game coming back from the tab beside the chat) starts over.
  const frameId = live && player.data?.url ? `${frameKey}:${player.data.url}` : null
  const bridge = usePlayerBridge({ ctx, frameKey: frameId, frameRef, scopeRef: rootRef, visible: live })
  const annotate = useAnnotate(bridge)
  const playtest = usePlaytest(ctx, game.id, build?.n ?? null, report)
  const [panelOpen, setPanelOpen] = useState(() => playtest.counts.left > 0 || (prefs.panel && !playtest.counts.complete))
  const [sending, setSending] = useState(false)
  const room = useRoom(rootRef)
  const full = useFullScreen(screenRef)
  const narrow = room.width > 0 && room.width < NARROW
  const showPanel = annotate.active || panelOpen
  const complete = playtest.counts.complete

  // Ticking the last check folds the panel; the game takes the room.
  useEffect(() => {
    if (complete) {
      setPanelOpen(false)
    }
  }, [complete])

  // While annotating, Esc on the page ends it too (inside the frame the engine handles it).
  useEffect(() => {
    if (!annotate.active) {
      return undefined
    }

    const escape = event => {
      if (event.key === 'Escape' && !event.target?.closest?.('textarea, input')) {
        annotate.cancel()
      }
    }

    window.addEventListener('keydown', escape)

    return () => window.removeEventListener('keydown', escape)
  }, [annotate.active])

  // Each frame loads in the view chosen when it loads; later changes go through commands, so the game
  // keeps running.
  const query = useMemo(() => `view=${prefs.view}&color=${prefs.finish}`, [frameId])
  const ready = Boolean(player.data?.url) && bridge.frame.ready
  const sync = () => {
    bridge.send(CMD.THEME, { css: `:root{--hr-accent:${accentOf(rootRef.current) || '#3d7bff'}}` })
    bridge.send(CMD.VIEW, { view: prefs.view })
    bridge.send(CMD.FINISH, { id: prefs.finish })
  }

  useEffect(() => {
    if (ready) {
      sync()
    }
  }, [ready, prefs.view, prefs.finish])

  const side = narrow ? 0 : showPanel ? PANEL_WIDTH : FOLD_WIDTH
  const box = full
    ? { width: screen.width, height: screen.height }
    : { width: Math.max(160, room.width - side - 2 * STAGE_PAD), height: Math.max(144, Math.round(room.height * HEIGHT_SHARE)) }
  const size = playerSize(prefs.view, prefs.scale, box)
  const togglePanel = () => {
    setPanelOpen(!panelOpen)
    setPrefs({ panel: !panelOpen })
  }
  const actions = {
    onAsk: () => void askAboutMoment({ bridge, game, stored }),
    onAnnotate: annotate.start,
    onShot: () => bridge.press('screenshot')
  }
  const done = async () => {
    setSending(true)

    try {
      await sendMarks({ bridge, build: build?.n ?? null, game, notes: annotate.notes, stored })
    } finally {
      setSending(false)
    }
  }

  const panel = annotate.active
    ? jsx(AnnotatePanel, { annotate, layout: narrow ? 'tabs' : 'side' })
    : panelOpen
      ? jsx(PlaytestPanel, {
          ...actions,
          build: build?.n ?? null,
          layout: narrow ? 'tabs' : 'side',
          note,
          onWrong: item => void reportCheck({ bridge, game, item, playtest, stored }),
          playtest,
          ready
        })
      : narrow
        ? null
        : jsx(FoldedPanel, { counts: playtest.counts, onOpen: togglePanel })

  const bar = annotate.active
    ? jsx(AnnotateBar, { busy: sending, count: annotate.marks.length, onCancel: annotate.cancel, onDone: () => void done(), title: game.title })
    : jsx(ControlBar, {
        ...actions,
        fits: size.fits,
        frame: bridge.frame,
        hint: bridge.focused ? 'keys go to the game' : 'click the game to play',
        onClose,
        onFull: () => void screenRef.current?.requestFullscreen?.()?.catch?.(() => {}),
        onMore: id => (id === 'restart' ? bridge.press('restart') : bridge.press('record-video')),
        panelToggle: jsx(BarButton, { icon: 'checklist', label: 'Play-test panel', onClick: togglePanel, pressed: panelOpen, text: 'Play-test' }),
        prefs,
        ready,
        setPrefs,
        title: game.title
      })

  const stage = live
    ? jsxs('div', {
        className: 'cs-ip-stage',
        children: [
          jsx(PlayerNotice, { game, onRefresh: () => setReload(value => value + 1), player, refreshing: player.isFetching }),
          // The screen element goes full screen; the game inside it keeps a whole-number size.
          jsx('div', {
            className: 'cs-ip-screen',
            'data-view': prefs.view,
            ref: screenRef,
            children: jsx('div', {
              className: 'cs-ip-fit',
              style: { width: `${size.width}px`, height: `${size.height}px` },
              children: jsx(PlayerStage, { ctx, frameKey, frameRef, game, player, query, visible: true })
            })
          })
        ]
      })
    : jsx(PlayerAway, { onBring: () => claimLive(surface), where: 'Playing beside the chat' })

  return jsxs('div', {
    'aria-label': `Play ${game.title}`,
    className: narrow ? 'cs-ip narrow' : 'cs-ip',
    ref: rootRef,
    children: [
      bar,
      jsxs('div', { className: 'cs-ip-body', children: [stage, narrow ? null : panel] }),
      narrow ? panel : null,
      showPanel ? null : jsx(KeyHints, {})
    ]
  })
}
