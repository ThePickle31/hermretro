// The page: which screen is shown, and the data every screen shares (`shell`, handed to each page's Page).
// The pages themselves come from the registry (app/registry.js, page/pages/index.js).
import {
  Button,
  Codicon,
  host,
  jsx,
  jsxs,
  ScrollArea,
  useEffect,
  useQuery,
  useQueryClient,
  useRef,
  useState,
  useValue
} from '#sdk'
import { ART_DATA } from '#shared/art/index.js'
import { callStudio, describeRequestError, useBackend } from './backend.js'
import { DEMO_GAME, DEMO_ID, ID } from './ids.js'
import { forgetRoute, routing } from './routing.js'
import { RPC_GAME_THUMB, RPC_GAMES, RPC_PLAYER } from './rpc.js'
import {
  computeSteps,
  latestGame,
  ONBOARD_STAGES,
  OnboardHeader,
  Onboarding,
  STEP_SHORT,
  toolchainStateKnown,
  useInstall,
  useSetupMemory
} from '#pages/index.js'
import { usePlayerBridge } from '#shared/player/bridge.js'
import { annotateGame, askAboutGame } from './player/capture.js'
import { shrinkFrame } from '#shared/player/frame-image.js'
import { claimLive, LIVE_PLAYER, releaseLive } from '#shared/player/live.js'
import { playableSha, PlayerAway, PlayerStage } from './player/stage.js'
import { PageStyle } from './style.js'
import { Footer } from '#shared/ui/page.js'
import { StudioNav } from './nav.js'
import { NotRunning } from './not-running.js'
import { PageView } from './page-view.js'
import { NAV_PAGES, pageById } from './registry.js'
import { UpdateChip } from './update/chip.js'
import { usePluginUpdate } from './update/use-update.js'

export function StudioPage({ ctx }) {
  const queryClient = useQueryClient()
  const [memory, update] = useSetupMemory(ctx)
  const [page, setPage] = useState(() => {
    try {
      const stored = ctx.storage.get('page', 'home')

      return pageById(stored) ? stored : 'home'
    } catch {
      return 'home'
    }
  })
  // Step the user chose to look at; null follows the first incomplete step.
  const [pinned, setPinned] = useState(null)
  const [promptId, setPromptId] = useState('new-game')
  const [polling, setPolling] = useState({ fast: true, pollDoctor: false })
  const { backend, doctor, gateway, status } = useBackend(polling)
  const refreshing = status.isFetching || doctor.isFetching

  const running = backend === 'ok'
  const steps = computeSteps({ backend, doctor, memory, status })
  const auto = running ? (steps.find(step => !step.complete) ?? null) : null
  // The game steps are done and the Chromatic ones are next: ask whether there is a Chromatic
  // before showing them, so people without one go straight to making games.
  const choosing = Boolean(auto?.hardware) && !memory.hardwareWanted && !memory.hardwareSkipped
  const autoId = !running ? 'not-running' : !auto ? 'ready' : choosing ? 'choice' : auto.id
  const pinnedStep = running ? (steps.find(step => step.id === pinned) ?? null) : null
  const shown = pinnedStep ?? (choosing ? null : auto)
  const viaProfile = running ? (status.data.via_profile ?? null) : null
  // The app itself is on the hermretro profile: Build chats and prompts use its own connection.
  // Only an answer changes it: one failed poll must not swap a running Build chat for the repair panel.
  if (running) {
    routing.ambientStudio = !viaProfile && Boolean(status.data.profile?.is_studio)
  }
  const pluginUpdate = usePluginUpdate({ ctx, running, status })
  const hardwareOn = Boolean(status.data?.hardware_enabled)
  const emulatorOnly = Boolean(memory.hardwareSkipped) && !hardwareOn
  const gameReady = running && steps.filter(step => !step.hardware).every(step => step.complete)

  // Initial answers have arrived; only changes after this are worth announcing.
  const settled = running && (Boolean(doctor.data) || doctor.isError)
  const lastAuto = useRef(autoId)
  const wasSettled = useRef(false)
  const stepsRef = useRef(steps)

  stepsRef.current = steps

  // A step was completed: leave any reviewed page and move on to the next one.
  useEffect(() => {
    const before = lastAuto.current

    lastAuto.current = autoId

    if (before === autoId) {
      return
    }

    setPinned(null)

    const finished = stepsRef.current.find(step => step.id === before)

    if (wasSettled.current && finished?.state === 'done') {
      host.notify({ kind: 'success', message: `${finished.title}: done` })
    }
  }, [autoId])

  useEffect(() => {
    wasSettled.current = settled
  }, [settled])

  // First-run onboarding: until the game tools are in and the user has chosen how to play, the page
  // shows only the guided setup. A setup finished before onboarding existed skips it.
  const priorSetup = Boolean(memory.hardwareSkipped || memory.hardwareWanted || memory.firmwareDone || memory.devmodeDone)
  const legacyReady =
    settled && !memory.onboardStarted && (gameReady || priorSetup || Boolean(status.data?.profile?.is_studio && toolchainStateKnown(status, doctor)))
  const onboarding = running && !memory.onboarded && !legacyReady
  const onboardScreen = !onboarding
    ? null
    : !settled
      ? 'checking'
      : !memory.onboardStarted
        ? 'welcome'
        : !gameReady
          ? 'install'
          : !memory.hardwareSkipped && !memory.hardwareWanted
            ? 'chromatic'
            : 'make'

  useEffect(() => {
    if (legacyReady && !memory.onboarded) {
      update({ onboarded: true })
    }
  }, [legacyReady, memory.onboarded])

  const toolchainStep = steps.find(step => step.id === 'toolchain')
  const wantInstall = running && (onboarding || page === 'setup' || toolchainStep?.state === 'todo')
  const install = useInstall({ enabled: wantInstall })
  const installState = install.data?.install?.state ?? null
  const lastInstall = useRef(installState)

  // The page's install finished: read the tools again so the step can verify.
  useEffect(() => {
    const before = lastInstall.current

    lastInstall.current = installState

    if (before === 'running' && installState === 'done') {
      void doctor.refetch?.()
    }
  }, [installState])

  const finishOnboarding = () => {
    update({ onboarded: true })
    go('home')
  }

  useEffect(() => {
    const toolchainOpen = toolchainStep && toolchainStep.state !== 'done' && toolchainStep.state !== 'checking'
    const next = {
      fast: autoId !== 'ready',
      pollDoctor: Boolean(toolchainOpen) && installState !== 'running' && (autoId === 'toolchain' || onboardScreen === 'install')
    }

    setPolling(current => (current.fast === next.fast && current.pollDoctor === next.pollDoctor ? current : next))
  }, [autoId, toolchainStep?.state, installState, onboardScreen])

  const go = id => {
    setPage(id)

    try {
      ctx.storage.set('page', id)
    } catch {
      // remembered for this visit only
    }
  }

  const refresh = () => {
    routing.scannedAt = 0 // look through the profiles again
    forgetRoute() // and forget a profile that may have been removed or stopped
    void queryClient.invalidateQueries({ queryKey: [ID] })
  }

  const pick = id => setPinned(id === autoId ? null : id)
  const setUpDevice = () => {
    update({ hardwareSkipped: false, hardwareWanted: true, onboarded: true })
    setPinned(null)
    go('setup')
  }
  const openPrompt = id => {
    setPromptId(id)
    go('prompts')
  }

  // ── games and the player ──
  const onEmulator = page === 'emulator'
  const games = useQuery({
    queryKey: [ID, 'games', viaProfile],
    queryFn: () => callStudio(RPC_GAMES),
    enabled: running,
    // While the player is on screen, a rebuild in chat is noticed within seconds.
    refetchInterval: onEmulator ? 5_000 : 30_000,
    staleTime: 2_000,
    retry: false
  })
  const gameList = Array.isArray(games.data?.games) ? games.data.games : []
  const [emu, setEmu] = useState({ id: null, reload: 0 })
  const [emuOpened, setEmuOpened] = useState(false)
  const [dismissed, setDismissed] = useState(null)
  const [capturesOpen, setCapturesOpen] = useState(false)
  const demo = { ...DEMO_GAME, ...(games.data?.demo && typeof games.data.demo === 'object' ? games.data.demo : {}), id: DEMO_ID }
  // A game picked on the shelf plays even without a web build (its error says how to build it); left
  // to itself the page plays the newest playable game, else the demo cartridge. While the library is
  // still loading nothing is chosen, so the frame does not load the demo and then switch.
  const libraryKnown = Boolean(games.data) || games.isError
  const game =
    emu.id === DEMO_ID
      ? demo
      : (gameList.find(item => item.id === emu.id) ?? (libraryKnown ? (latestGame(gameList.filter(item => item.webExport)) ?? demo) : null))

  useEffect(() => {
    if (onEmulator && game) {
      setEmuOpened(true)
    }
  }, [onEmulator, game?.id])

  // One game runs at a time. Visiting the Emulator page never takes the game from a tab beside the
  // chat (that would restart a game the user is playing); the page offers "Bring it here" instead and
  // only plays when nothing else does.
  const liveOwner = useValue(LIVE_PLAYER)
  const pageLive = liveOwner === 'page'

  useEffect(() => {
    if (onEmulator && running && liveOwner === null) {
      claimLive('page')
    }
  }, [onEmulator, running, liveOwner])

  useEffect(() => () => releaseLive('page'), [])

  const player = useQuery({
    queryKey: [ID, 'player', game?.id ?? null, emu.reload],
    queryFn: () => callStudio(RPC_PLAYER, { id: game.id }, 30_000),
    enabled: running && emuOpened && Boolean(game) && pageLive,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false
  })
  const frameRef = useRef(null)
  const stageRef = useRef(null)
  const loadedSha = player.data?.url ? (player.data.romSha256 ?? null) : null
  const currentSha = playableSha(game)
  const rebuilt = Boolean(pageLive && loadedSha && currentSha && loadedSha !== currentSha && dismissed !== currentSha)
  const thumbTried = useRef(new Set())

  const bridge = usePlayerBridge({ ctx, frameRef, onAnnotate: data => annotateGame(ctx, game, data), visible: onEmulator && running && pageLive })
  const ask = () => askAboutGame(ctx, game, bridge.snap)

  // After a game first loads, keep its title screen for the shelf (when it has none yet).
  const onFrameLoad = () => {
    const target = game

    if (!target || target.id === DEMO_ID || target.thumb || thumbTried.current.has(target.id)) {
      return
    }

    thumbTried.current.add(target.id)

    const attempt = async remaining => {
      const png = await shrinkFrame(await bridge.snap())

      if (!png) {
        if (remaining > 0) {
          ctx.setTimeout(() => void attempt(remaining - 1), 5_000)
        }

        return
      }

      try {
        await callStudio(RPC_GAME_THUMB, { id: target.id, png })
        void queryClient.invalidateQueries({ queryKey: [ID, 'games'] })
      } catch (error) {
        console.warn('[hermretro] title screen not saved:', describeRequestError(error).message)
      }
    }

    ctx.setTimeout(() => void attempt(3), 3_000)
  }

  const play = id => {
    setEmu(current => ({ id, reload: current.reload }))
    go('emulator')
  }

  // ── what every page gets ──
  const currentPage = pageById(page) ?? NAV_PAGES[0]
  const shell = {
    ctx,
    page,
    go,
    refresh,
    refreshing,
    backend,
    doctor,
    gateway,
    status,
    // the profile the page's own queries go to when it is not the app's (null when it is the app's)
    viaProfile,
    // setup: the steps, where the user is in them, and first-run memory
    steps,
    memory,
    update,
    auto,
    autoId,
    choosing,
    shown,
    pick,
    unpin: () => setPinned(null),
    install,
    // Hermes's update of hermretro: the header chip, and the version row on the Setup page
    pluginUpdate,
    gameReady,
    hardwareOn,
    emulatorOnly,
    setUpDevice,
    // games and prompts
    games,
    gameList,
    gamesChanged: () => void queryClient.invalidateQueries({ queryKey: [ID, 'games'] }),
    play,
    openPrompt,
    promptId,
    setPromptId,
    // New games go in the plugin's games folder (the backend reports it); an older backend without it falls
    // back to the folder of the latest game.
    newGameFolder: (() => {
      if (typeof games.data?.gamesDir === 'string' && games.data.gamesDir) {
        return games.data.gamesDir
      }

      const root = latestGame(gameList)?.projectRoot

      return root ? root.replace(/[\\/][^\\/]+[\\/]?$/, '') || null : null
    })(),
    profileLabel: routing.profile ?? status.data?.profile?.name ?? 'this profile',
    // the one player, kept by the shell so it survives page switches (the Emulator page shows it)
    player: {
      game,
      query: player,
      focused: bridge.focused,
      rebuilt,
      capturesOpen,
      ask,
      fullScreen: () => void stageRef.current?.requestFullscreen?.()?.catch?.(() => {}),
      later: () => setDismissed(currentSha),
      reload: () => setEmu(current => ({ id: game.id, reload: current.reload + 1 })),
      refresh: () => {
        refresh()
        setEmu(current => ({ id: current.id, reload: current.reload + 1 }))
      },
      toggleCaptures: () => setCapturesOpen(open => !open)
    }
  }

  // ── body ──
  let body

  if (!running) {
    body = [jsx(NotRunning, { backend, gateway, status }, 'off')]
  } else if (onboardScreen) {
    body = [
      jsx(
        Onboarding,
        { ctx, install, onDevice: setUpDevice, onFinish: finishOnboarding, screen: onboardScreen, status, steps, update },
        'onboarding'
      )
    ]
  } else {
    body = [jsx(PageView, { page: currentPage, shell }, currentPage.id)]
  }

  // The page's own padding ('flush' or 'build', each without the footer), only once it is shown.
  const pad = running && !onboardScreen ? (currentPage.pad ?? null) : null
  // After onboarding a broken game step is a banner, not the onboarding again.
  const broken = running && settled && !onboardScreen && page !== 'setup' ? steps.find(step => !step.hardware && !step.complete) : null
  // The player stays mounted (hidden and paused) while another page is shown, so the game is not reloaded.
  // Beside the chat instead: the Emulator page says so; other pages drop the hidden frame.
  const stage =
    running && !onboardScreen && (emuOpened || onEmulator)
      ? pageLive
        ? jsx(PlayerStage, { ctx, frameKey: `${game?.id ?? 'none'}:${emu.reload}`, frameRef, game, onLoad: onFrameLoad, player, stageRef, visible: onEmulator }, 'player')
        : onEmulator
          ? jsx(PlayerAway, { onBring: () => claimLive('page'), where: 'Playing beside the chat' }, 'player')
          : null
      : null

  return jsx(ScrollArea, {
    className: 'h-full',
    style: { height: '100%' },
    children: jsxs('div', {
      className: 'cs-page',
      'data-page': page,
      style: {
        '--cs-hermes': `url("${ART_DATA.hermes}")`,
        '--cs-cart': `url("${ART_DATA.cart}")`,
        '--cs-fly-body': `url("${ART_DATA.chromBody}")`,
        '--cs-fly-wing': `url("${ART_DATA.chromWing}")`
      },
      children: [
        jsx(PageStyle, {}, 'style'),
        onboardScreen
          ? jsx(
              OnboardHeader,
              {
                end: pluginUpdate.visible ? jsx(UpdateChip, { update: pluginUpdate }) : null,
                stage: ONBOARD_STAGES.some(([id]) => id === onboardScreen) ? onboardScreen : null
              },
              'nav'
            )
          : jsx(
              StudioNav,
              {
                nav: { page, playing: Boolean(stage && game && player.data?.url), setupPending: running && Boolean(auto) },
                onGo: go,
                onRefresh: refresh,
                pages: NAV_PAGES,
                refreshing,
                update: pluginUpdate,
                viaProfile
              },
              'nav'
            ),
        jsxs(
          'div',
          {
            className: pad ? `cs-pad ${pad}` : 'cs-pad',
            children: [
              // Hermes kept running the old code after an update (the Update button reloads it; a terminal update does not).
              running && status.data?.restart_needed && pluginUpdate.phase !== 'restart'
                ? jsxs(
                    'div',
                    {
                      className: 'cs-repair',
                      role: 'status',
                      children: [
                        jsx(Codicon, { name: 'refresh', size: 14 }),
                        jsx('span', { children: 'hermretro was updated, but Hermes is still running the old version. Quit and reopen Hermes to finish.' })
                      ]
                    },
                    'restart'
                  )
                : null,
              broken
                ? jsxs(
                    'div',
                    {
                      className: 'cs-repair',
                      role: 'status',
                      children: [
                        jsx(Codicon, { name: 'warning', size: 14 }),
                        jsx('span', { children: `${STEP_SHORT[broken.id]} needs attention: ${broken.title.toLowerCase()} again to keep building games.` }),
                        jsx(Button, { onClick: () => go('setup'), size: 'sm', variant: 'outline', children: 'Repair' })
                      ]
                    },
                    'repair'
                  )
                : null,
              ...body,
              stage,
              pad && currentPage.BelowPlayer ? jsx(currentPage.BelowPlayer, { shell }, 'side') : null,
              pad ? null : jsx(Footer, { ctx }, 'foot')
            ]
          },
          'pad'
        )
      ]
    })
  })
}
