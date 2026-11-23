// The emulator tab beside the chat.
import { Codicon, host, jsx, jsxs, useEffect, useQuery, useRef, useState, useValue } from '#sdk'
import { callBackend } from '#app/backend.js'
import { DEMO_GAME, DEMO_ID, ID } from '#app/ids.js'
import { RPC_PLAYER } from '#app/rpc.js'
import { readSideBuildStatus } from '#app/player/build-status.js'
import { EmulatorBar } from '#pages/emulator/emulator-bar.js'
import { usePlayerBridge } from '#shared/player/bridge.js'
import { annotateGame, askAboutGame } from '#app/player/capture.js'
import { claimLive, LIVE_PLAYER, releaseLive } from '#shared/player/live.js'
import { playableSha, PlayerAway, PlayerNotice, PlayerStage } from '#app/player/stage.js'
import { PageStyle } from '#app/style.js'
import { ALWAYS_VISIBLE, BUILD_TICK, PRESENTED, sideKey, sideSurface, sideTabs } from './state.js'

/** Open (or bring forward) the emulator tab for one game, beside the chat. */
export function openSideEmulator(ctx, game) {
  if (!game || typeof host.openWorkspace !== 'function') {
    return false
  }

  const key = sideKey(game.id)
  const surface = sideSurface(game.id)

  claimLive(surface)

  try {
    const close = host.openWorkspace(key, {
      dock: { pane: 'workspace', pos: 'right' },
      minWidth: '22rem',
      title: `Emulator · ${game.title}`,
      render: () => jsx(SideEmulator, { ctx, initialGame: game, paneId: `plugin-workspace:${key}` }),
      onClose: () => {
        sideTabs.delete(game.id)
        releaseLive(surface)
      }
    })

    sideTabs.set(game.id, typeof close === 'function' ? close : () => {})

    return true
  } catch (error) {
    releaseLive(surface)
    console.warn('[hermretro] the emulator could not open beside the chat:', String(error?.message ?? error))

    return false
  }
}

/** The emulator tab beside the chat: the Emulator page's bar and player, sized to the tab. */
function SideEmulator({ ctx, initialGame, paneId }) {
  const gameId = initialGame.id
  const demo = gameId === DEMO_ID
  const surface = sideSurface(gameId)
  const owner = useValue(LIVE_PLAYER)
  const tick = useValue(BUILD_TICK)
  const [paneShown] = useState(() => (typeof host.paneVisibility === 'function' ? host.paneVisibility(paneId) : ALWAYS_VISIBLE))
  const shown = useValue(paneShown) !== false
  const live = owner === surface
  const checking = live && shown && !demo

  // Nobody is playing (the Studio page was left, another tab closed): a visible tab takes the game.
  useEffect(() => {
    if (owner === null && shown) {
      claimLive(surface)
    }
  }, [owner, shown])

  useEffect(() => () => releaseLive(surface), [])

  const buildStatus = useQuery({
    queryKey: [ID, 'gameBuildStatus', 'side', gameId],
    queryFn: () => readSideBuildStatus(gameId),
    enabled: checking,
    refetchInterval: checking ? 5_000 : false,
    staleTime: 2_000,
    retry: false
  })
  const lastCheck = useRef({ checking, tick })

  useEffect(() => {
    const previous = lastCheck.current

    lastCheck.current = { checking, tick }

    if (checking && (!previous.checking || tick !== previous.tick)) {
      void buildStatus.refetch?.({ cancelRefetch: previous.checking })
    }
  }, [checking, tick])

  const game = demo
    ? DEMO_GAME
    : buildStatus.data?.game ?? (buildStatus.data?.code === 'NO_GAME' ? { id: gameId, title: initialGame.title } : initialGame)
  const [reload, setReload] = useState(0)
  const [dismissed, setDismissed] = useState(null)
  const [capturesOpen, setCapturesOpen] = useState(false)
  // The agent's latest presentation of this game: a new one loads the newest build directly (it is
  // an explicit "try this now") and shows its note until the user dismisses it.
  const presentation = useValue(PRESENTED)[gameId] ?? null
  const seenSeq = useRef(presentation?.seq ?? 0)
  const [noteHidden, setNoteHidden] = useState(null)

  useEffect(() => {
    const seq = presentation?.seq ?? 0

    if (seq !== seenSeq.current) {
      seenSeq.current = seq
      setDismissed(null)
      setReload(value => value + 1)
    }
  }, [presentation?.seq])

  const note = presentation?.note && noteHidden !== presentation.seq ? presentation.note : null
  const player = useQuery({
    queryKey: [ID, 'player', 'side', gameId, reload],
    queryFn: async () => (await callBackend(RPC_PLAYER, { id: gameId }, 30_000)).data,
    enabled: live,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false
  })
  const frameRef = useRef(null)
  const stageRef = useRef(null)
  const scopeRef = useRef(null)
  const loadedSha = player.data?.url ? (player.data.romSha256 ?? null) : null
  const currentSha = buildStatus.isError ? null : playableSha(buildStatus.data?.game)
  const rebuilt = Boolean(live && loadedSha && currentSha && loadedSha !== currentSha && dismissed !== currentSha)
  const bridge = usePlayerBridge({ ctx, frameRef, onAnnotate: data => annotateGame(ctx, game, data), scopeRef, visible: live && shown })
  const hardwareOn = Boolean(buildStatus.data?.device?.hardwareEnabled)

  return jsxs('div', {
    className: 'cs-page cs-side',
    'data-page': 'emulator',
    ref: scopeRef,
    children: [
      jsx(PageStyle, {}, 'style'),
      ...(live
        ? [
            jsx(EmulatorBar, {
              capturesOpen,
              ctx,
              focused: bridge.focused,
              game,
              hardwareOn,
              onAsk: () => askAboutGame(ctx, game, bridge.snap),
              onFull: () => void stageRef.current?.requestFullscreen?.()?.catch?.(() => {}),
              onLater: () => setDismissed(currentSha),
              onReload: () => setReload(value => value + 1),
              onToggleCaptures: () => setCapturesOpen(open => !open),
              player,
              rebuilt
            }, 'bar'),
            note
              ? jsxs('div', {
                  className: 'cs-side-note',
                  role: 'note',
                  children: [
                    jsx(Codicon, { name: 'comment', size: 14 }),
                    jsx('span', { className: 'cs-side-note-text', children: note }),
                    jsx('button', {
                      'aria-label': 'Dismiss note',
                      className: 'cs-side-note-x',
                      onClick: () => setNoteHidden(presentation.seq),
                      title: 'Dismiss',
                      type: 'button',
                      children: jsx(Codicon, { name: 'close', size: 12 })
                    })
                  ]
                }, 'note')
              : null,
            jsx(PlayerNotice, { game, onRefresh: () => setReload(value => value + 1), player, refreshing: player.isFetching }, 'notice'),
            jsx(PlayerStage, { ctx, frameKey: `${gameId}:${reload}`, frameRef, game, player, stageRef, visible: true }, 'player')
          ]
        : [jsx(PlayerAway, { onBring: () => claimLive(surface), where: 'Playing in hermretro' }, 'away')])
    ]
  })
}
