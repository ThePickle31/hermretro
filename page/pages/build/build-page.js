// The Build page: one game, one conversation.
import { Button, host, jsx, jsxs, useEffect, useMemo, useRef, useState, useValue } from '#sdk'
import {
  createBuildChat,
  openBuildChat,
  openInFullChat,
  reopenBuildChat,
  sendBuildChat,
  stopBuildChat
} from './chat/actions.js'
import { BUILD_CHATS, BUILD_STARTING, BUILD_VIEWING, chatRequest, patchChat } from './chat/store.js'
import { BuildComposer } from './composer/composer.js'
import { ChatModelPicker, DraftModelPicker, useDraftPick } from './composer/model-picker.js'
import { InlinePlayer } from './player/inline-player.js'
import { PlayCard } from './player/play-card.js'
import { useInlinePlayer } from './player/use-inline-player.js'
import { BuildStatus } from './transcript/status.js'
import { rootOf } from './transcript/groups.js'
import { AssetGame } from './assets/cache.js'
import { Transcript } from './transcript/transcript.js'
import { buildHistory, deriveTurns } from './transcript/turns.js'
import { describeRequestError } from '#app/backend.js'
import { AGENT } from '#app/ids.js'
import { isUpdating, UPDATING_MESSAGE } from '#app/update/lock.js'
import { playableSha } from '#app/player/stage.js'
import { buildRpc, newGamePrompt } from './binding.js'
import { BuildPill, BuildsMenu } from './builds-menu.js'
import { restoreProjectBuild } from './build-restore.js'
import { BuildPromptCard } from './transcript/questions.js'
import { BuildNewGame } from './new-game.js'
import { Background } from '#app/background.js'
import { Working } from '#shared/ui/working.js'
import { BuildSwitcher, switcherEntries } from './switcher.js'
import { CartShelf } from './cart-shelf.js'
import { useBuildSelection, useMissingBuildGame } from './selection.js'

/** `updating`: hermretro is being updated: nothing new is sent until it is done (the update reloads the plugin). */
export function BuildPage({ ctx, games, selection, onSelect, pendingGames, localPending, changePending, loaded, libraryError, unavailable, onLibraryChanged, playerVisit, updating = false }) {
  const chats = useValue(BUILD_CHATS)
  const startingGames = useValue(BUILD_STARTING)
  // Bindings made this visit, until the library answers with them (and the only record on an older backend).
  // released: game id → the stored id it let go of with Stop editing, until the library stops listing it.
  const [local, setLocal] = useState({ bound: {}, released: {} })
  const selected = useBuildSelection(ctx, selection, onSelect)

  const rail = useMemo(
    () =>
      games.map(game => {
        const session = game.session && local.released[game.id] !== game.session.storedId ? game.session : null
        const bound = local.bound[game.id]
        // Keep an accepted replacement visible while the game list still reports the old binding.
        const linked = session?.storedId
        const buildSession = (!linked || linked === bound?.replaces ? bound?.stored : null) ?? linked ?? null

        return { ...game, session, title: game.displayTitle || game.title, buildSession }
      }),
    [games, local.bound, local.released]
  )
  const pending = useMemo(
    () =>
      [
        ...(Array.isArray(pendingGames) ? pendingGames : []),
        ...localPending.filter(item => !(pendingGames ?? []).some(known => known.storedId === item.storedId))
      ].filter(item => !rail.some(game => game.buildSession === item.storedId)),
    [pendingGames, localPending, rail]
  )

  // Render the same conversation even on the first render where its game replaces the pending entry.
  const pendingId = selected.startsWith('pending:') ? selected.slice('pending:'.length) : null
  const made = pendingId ? rail.find(game => game.buildSession === pendingId) : null
  useEffect(() => {
    if (made) {
      onSelect(made.id)
    }
  }, [made?.id])

  // While a New Game conversation has not made its game yet, look at the library after each turn.
  useEffect(() => {
    if (pending.some(item => chats[item.storedId]?.busy === false)) {
      onLibraryChanged()
    }
  }, [pending.map(item => chats[item.storedId]?.busy).join(',')])

  const game = made ?? rail.find(item => item.id === selected) ?? null
  const pendingItem = pending.find(item => item.storedId === pendingId) ?? null
  const missingSelection = selected !== 'new' && !game && !pendingItem
  const missingGame = useMissingBuildGame(loaded && missingSelection && !pendingId ? selected : null, unavailable)
  const removed = loaded && missingSelection && (pendingId ? !chats[pendingId]?.busy : missingGame.removed)
  const waitingForSelection = missingSelection && (!loaded || !pendingId)

  // A remembered selection that is gone (game removed, New Game discarded elsewhere) falls back to New game.
  useEffect(() => {
    if (removed) {
      select('new')
    }
  }, [removed, selected])

  // Presentations of the game shown here play in this conversation, not in a tab beside the chat.
  useEffect(() => {
    BUILD_VIEWING.set(game?.id ?? null)

    return () => BUILD_VIEWING.set(null)
  }, [game?.id])

  // A conversation in another Hermes profile is not opened (or replaced) from here.
  const elsewhere = Boolean(game?.session && game.session.thisProfile === false)
  const stored = elsewhere ? null : (game?.buildSession ?? pendingItem?.storedId ?? null)
  const chat = stored ? chats[stored] : null
  // A restart is permission to replace one missing conversation, not whatever is bound later.
  const [restartIds, setRestartIds] = useState({})
  const replaces = game && stored && restartIds[game.id] === stored ? stored : null
  const fresh = Boolean(game && !elsewhere && (!stored || replaces))
  useEffect(() => {
    setRestartIds(current => {
      const kept = Object.entries(current).filter(([id, expected]) => rail.some(item => item.id === id && item.buildSession === expected))

      return kept.length === Object.keys(current).length ? current : Object.fromEntries(kept)
    })
  }, [rail])
  const [draftPick, setDraftPick, draftOptions] = useDraftPick(ctx, selected === 'new' || fresh)
  const startingGame = startingGames.has(game?.id)

  useEffect(() => {
    if (!stored || chat?.runtime || chat?.opening || chat?.failure) {
      return
    }

    // The library already knows this profile has no such session: no resume needed to say so.
    if (game?.session?.storedId === stored && game.session.exists === false) {
      patchChat(stored, current => (current.missing ? current : { ...current, missing: true }))
    } else {
      void openBuildChat(stored, game?.id)
    }
  }, [stored, chat?.runtime])

  // A reply that finished while the user looked at this conversation is read.
  useEffect(() => {
    if (stored && chat && !chat.busy && (chat.lastCompleteAt ?? 0) > (chat.seenAt ?? 0)) {
      patchChat(stored, current => ({ ...current, seenAt: Date.now() }))
    }
  }, [stored, chat?.lastCompleteAt, chat?.busy])

  const { markPresentationsSeen, onClosePlayer, onPlay, playerOpen } = useInlinePlayer(playerVisit, game?.id, chat)
  const select = key => {
    if (key !== selected) {
      markPresentationsSeen()
      onSelect(key)
    }
  }

  // Nothing that starts work in the hermretro profile runs while hermretro is updating (the update reloads it).
  const refuseWhileUpdating = () => {
    if (!isUpdating()) {
      return false
    }

    host.notify({ kind: 'warning', message: UPDATING_MESSAGE })

    return true
  }

  // True once the conversation holds the idea (New Game then clears its kept draft); false leaves the draft as it is.
  const startGame = async ({ idea, name, plan }) => {
    if (refuseWhileUpdating()) {
      return false
    }

    markPresentationsSeen()
    let id = null

    try {
      id = await createBuildChat(name.trim() || 'New game', draftPick)
      // The backend tells the agent each turn that this is a New Game conversation (and how to start), so
      // the idea is sent as the user wrote it. An older backend gets the instructions in the message.
      const recorded = await buildRpc({ action: 'start', stored: id, name: name.trim() || null, plan })

      // Only a first message Hermes accepted starts the game: otherwise New Game keeps the idea to send again.
      const first = recorded ? idea.trim() : newGamePrompt({ idea, name, plan })

      if (!(await sendBuildChat(id, first, idea.trim(), [], { mustLand: true }))) {
        void buildRpc({ action: 'cancel', stored: id }).catch(() => {})

        if (!isUpdating()) {
          host.notify({ kind: 'error', message: 'Could not start the conversation: Hermes did not take the first message.' })
        }

        return false
      }

      const created = { storedId: id, name: name.trim() || null, createdAt: Date.now() / 1000 }

      changePending(current => [...current, created])
      onSelect(`pending:${id}`)
      onLibraryChanged()

      return true
    } catch (error) {
      host.notify({ kind: 'error', message: `Could not start the conversation: ${describeRequestError(error).message}` })

      if (id) {
        void buildRpc({ action: 'cancel', stored: id }).catch(() => {})
      }

      return false
    }
  }

  // A New Game conversation that has not made its game can be let go: it leaves the rail (the hidden
  // session stays in Hermes, reachable from Open in full chat before discarding).
  const discard = async item => {
    try {
      await buildRpc({ action: 'cancel', stored: item.storedId })
    } catch (error) {
      host.notify({ kind: 'error', message: `Could not discard it: ${describeRequestError(error).message}` })

      return
    }

    changePending(current => current.filter(entry => entry.storedId !== item.storedId))
    select('new')
    onLibraryChanged()
  }

  const shownStored = fresh ? null : stored
  const shownChat = shownStored ? chat : null
  const shownItems = shownChat?.items ?? null
  const binding = local.bound[game?.id]
  // Keep a first edit's composer until handoff; a pending New Game uses its stored ID throughout.
  const composerKey = binding && binding.stored === stored ? (binding.replaces ?? game.id) : (stored ?? game?.id ?? '')
  // A turn to scroll to (the Builds menu's Show).
  const [focusTurn, setFocusTurn] = useState(null)
  // The New Game shelf's All games tile opens the switcher: { view, seq }, a new seq each time.
  const [switcherRequest, setSwitcherRequest] = useState(null)

  // The conversation's builds, worked out between turns (never while a reply streams).
  const settledItems = useRef(null)

  if (!shownChat?.busy) {
    settledItems.current = shownItems
  }

  const builds = useMemo(() => buildHistory(deriveTurns(settledItems.current ?? [])), [settledItems.current])

  // A game with no conversation opens a blank one; the session is made on the first message and bound to
  // the game (replacing a removed one), so the agent is told which game it works on and finds it selected.
  const send = async (text, attachments = [], shown = text, options) => {
    if (refuseWhileUpdating()) {
      return false
    }

    if (!fresh) {
      return stored ? sendBuildChat(stored, text, shown, attachments, options) : false
    }

    const { id, title, projectRoot } = game
    // Check the shared atom directly, including two sends before React renders the disabled composer.
    if (BUILD_STARTING.get().has(id)) {
      return false
    }
    BUILD_STARTING.set(new Set([...BUILD_STARTING.get(), id]))
    try {
      const target = await createBuildChat(title, draftPick)

      if (refuseWhileUpdating()) {
        return false
      }
      const recorded = await buildRpc({ action: 'bind', game: id, stored: target, ...(replaces ? { replace: replaces } : {}) })

      setLocal(current => ({ ...current, bound: { ...current.bound, [id]: { stored: target, replaces: stored } } }))
      onLibraryChanged()
      // An older backend cannot tell the agent which game this is: say it in the first message.
      return await sendBuildChat(
        target,
        recorded ? text : `Work on my existing hermretro game "${title}" at ${projectRoot} (select that project first). ${text}`,
        shown,
        attachments,
        options
      )
    } catch (error) {
      host.notify({ kind: 'error', message: `Could not start the conversation: ${describeRequestError(error).message}` })
      return false
    } finally {
      BUILD_STARTING.set(new Set([...BUILD_STARTING.get()].filter(gameId => gameId !== id)))
    }
  }

  const startOver = () => {
    if (game && stored && chat?.missing && !BUILD_STARTING.get().has(game.id)) {
      setRestartIds(current => ({ ...current, [game.id]: stored }))
    }
  }

  // Stop editing: the game leaves Editing now and is back under Edit a game. Its conversation is kept
  // and shown in the Hermes sidebar again, so it is not lost; the next edit starts a new one.
  const stopEditing = async target => {
    const storedId = target?.buildSession

    if (!storedId) {
      return
    }

    try {
      await buildRpc({ action: 'unbind', game: target.id, stored: storedId })
    } catch (error) {
      host.notify({ kind: 'error', message: `Could not stop editing ${target.title}: ${describeRequestError(error).message}` })

      return
    }

    void chatRequest('session.set_hidden', { session_id: storedId, hidden: false }).catch(error =>
      console.warn('[hermretro] could not show the old conversation in the sidebar:', describeRequestError(error).message)
    )
    setLocal(current => {
      const bound = { ...current.bound }

      delete bound[target.id]

      return { ...current, bound, released: { ...current.released, [target.id]: storedId } }
    })

    if (selected === target.id) {
      select('new')
    }

    onLibraryChanged()
  }

  // Per conversation: working, waiting, unread. Kept as the same object while those stay the same, so
  // a streaming reply does not re-render the switcher on every frame.
  const statesRef = useRef({ key: '', value: {} })
  const states = useMemo(() => {
    const result = {}

    for (const [key, value] of Object.entries(chats)) {
      result[key] = {
        busy: Boolean(value?.busy),
        waiting: Boolean(value?.items?.some(item => (item.kind === 'clarify' || item.kind === 'approval') && !item.answered)),
        unread: key !== stored && (value?.lastCompleteAt ?? 0) > (value?.seenAt ?? 0)
      }
    }

    const key = JSON.stringify(result)

    if (key !== statesRef.current.key) {
      statesRef.current = { key, value: result }
    }

    return statesRef.current.value
  }, [chats, stored])

  const title = game?.title ?? pendingItem?.name ?? (waitingForSelection ? 'Build' : 'New game')
  const entries = useMemo(() => switcherEntries(rail, pending, states, selected), [rail, pending, states, selected])
  // Edit a game: the library games with no conversation (the rest are already in the menu).
  const library = useMemo(() => rail.filter(item => !item.buildSession && item.id !== selected), [rail, selected])

  // Ctrl+1…9 switches to the game in that place of the menu (Hermes binds no Ctrl+digit).
  useEffect(() => {
    const onKey = event => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey || !/^[1-9]$/.test(event.key)) {
        return
      }

      const entry = entries[Number(event.key) - 1]

      if (entry) {
        event.preventDefault()
        select(entry.key)
      }
    }

    window.addEventListener('keydown', onKey)

    return () => window.removeEventListener('keydown', onKey)
  }, [entries])

  const switcher = jsx(BuildSwitcher, {
    entries,
    library,
    onRequestSeen: () => setSwitcherRequest(null),
    request: switcherRequest,
    onDiscard: item => discard(item),
    onOpenChat: openInFullChat,
    onSelect: select,
    onStop: stopEditing,
    selected,
    title
  })
  const header =
    selected === 'new'
      ? jsx('header', { className: 'cs-b-head', children: switcher })
      : jsxs('header', {
          className: 'cs-b-head',
          children: [
            switcher,
            jsx(BuildPill, { builds, chat: shownChat, game }),
            jsx('span', { className: 'cs-grow' }),
            game && !elsewhere
              ? jsx(BuildsMenu, {
                  builds,
                  busy: Boolean(shownChat?.busy || shownChat?.opening || shownChat?.missing || shownChat?.failure || startingGame || updating),
                  game,
                  stored: shownStored,
                  onRestore: (snapshot, target, title) => !refuseWhileUpdating() && restoreProjectBuild(
                    game.id, snapshot, target, title, (text, shown) => send(text, [], shown, { mustLand: true }), onLibraryChanged
                  ),
                  onShow: key => setFocusTurn({ key, stored: shownStored })
                }, game.id)
              : null,
            pendingItem && !shownChat?.busy
              ? jsx(Button, { onClick: () => void discard(pendingItem), size: 'sm', variant: 'ghost', children: 'Discard' })
              : null
          ]
        })

  // An open question or approval is asked in the message box (one at a time, the oldest first); only while a turn
  // runs: one its turn ended without settling has expired and must not hold the box.
  const openPrompt = shownChat?.busy ? (shownChat.items?.find(item => (item.kind === 'clarify' || item.kind === 'approval') && !item.answered) ?? null) : null
  const playable = Boolean(game && game.webExport && playableSha(game))
  const emptyState = jsx('div', {
    className: 'cs-b-hello',
    children: jsxs('div', {
      className: 'cs-col',
      children: [
        jsx('p', { className: 'cs-small', children: chat?.opening ? 'Opening the conversation…' : `Tell ${AGENT} what to make or change in ${title}.` }),
        chat?.opening ? jsx('div', { className: 'cs-b-skel', children: [jsx('i', {}, 'a'), jsx('i', {}, 'b'), jsx('i', {}, 'c')] }) : null
      ]
    })
  })

  const selectionError = libraryError || missingGame.error
  const libraryNotice = selectionError ? jsx('p', { className: 'cs-error cs-b-library-error', role: 'alert', children: selectionError }, 'library-error') : null
  let body

  if (waitingForSelection) {
    body = selectionError ? null : jsx('div', {
      className: 'cs-b-empty',
      children: jsx(Working, { quiet: true, children: 'Reading your games…' })
    })
  } else if (elsewhere) {
    body = jsx('div', {
      className: 'cs-b-empty',
      children: jsx('p', {
        className: 'cs-small',
        children: `This game\u2019s conversation is in the ${game.session.profileName ? `\u201c${game.session.profileName}\u201d` : 'other'} Hermes profile. Switch to that profile to keep working on it here.`
      })
    })
  } else if (shownChat?.missing) {
    body = jsxs('div', {
      className: 'cs-b-empty',
      children: [
        jsx('p', { className: 'cs-small', children: 'This game\u2019s conversation was removed from Hermes. The game itself is fine.' }),
        game ? jsx(Button, { disabled: startingGame, onClick: startOver, size: 'sm', children: 'Start a new conversation' }) : null
      ]
    })
  } else if (shownChat?.failure) {
    body = jsxs('div', {
      className: 'cs-b-empty',
      children: [
        jsx('p', { className: 'cs-error', children: `Could not open this conversation: ${shownChat.failure}` }),
        jsx(Button, { onClick: () => void reopenBuildChat(shownStored), size: 'sm', variant: 'outline', children: 'Try again' })
      ]
    })
  } else if (!shownChat?.items?.length && !shownChat?.busy) {
    // Nothing said yet: a playable game can still be played right here.
    body = jsx('div', {
      className: 'cs-b-tx',
      children: jsxs('div', {
        className: 'cs-b-col',
        children: [
          emptyState,
          playable && !chat?.opening
            ? jsx('div', {
                className: 'cs-b-her',
                children: playerOpen
                  ? jsx(InlinePlayer, { ctx, game, note: null, onClose: onClosePlayer, stored: shownStored }, `player:${game.id}`)
                  : jsx(PlayCard, { game, onPlay, state: 'ready' })
              })
            : null
        ]
      })
    })
  } else {
    body = jsx(Transcript, {
      chat: shownChat,
      ctx,
      empty: emptyState,
      game,
      onClosePlayer,
      onPlay,
      onSend: (text, shown, attachments) => void send(text, attachments ?? [], shown ?? text),
      focusTurn: focusTurn?.stored === shownStored ? focusTurn : null,
      onFocusHandled: setFocusTurn,
      playerOpen,
      stored: shownStored
    }, shownStored ?? 'none')
  }

  const main =
    selected === 'new'
      ? jsxs('div', {
          className: 'cs-b-chat cs-b-attract',
          children: [
            jsx(Background, { id: 'platformer' }, 'level'),
            header,
            libraryNotice,
            jsx(BuildNewGame, { onStart: startGame, updating, picker: jsx(DraftModelPicker, { ctx, onPick: setDraftPick, options: draftOptions, pick: draftPick, up: false }) }, 'new'),
            jsx(CartShelf, { entries, onAll: view => setSwitcherRequest(current => ({ view, seq: (current?.seq ?? 0) + 1 })), onSelect: select, others: library }, 'shelf')
          ]
        })
      : jsxs('div', {
          className: 'cs-b-chat',
          children: [
            header,
            libraryNotice,
            body,
            !waitingForSelection && jsx(BuildComposer, {
              busy: Boolean(shownChat?.busy),
              game,
              fresh,
              disabled: Boolean(updating || startingGame || elsewhere || shownChat?.opening || shownChat?.missing || shownChat?.failure || (!fresh && !shownChat?.runtime)),
              onSend: send,
              onStop: () => void stopBuildChat(shownStored),
              picker: elsewhere || shownChat?.missing
                ? null
                : fresh
                  ? jsx(DraftModelPicker, { ctx, disabled: startingGame || updating, onPick: setDraftPick, options: draftOptions, pick: draftPick })
                  : shownStored
                    ? jsx(ChatModelPicker, { chat: shownChat, ctx, disabled: !shownChat?.runtime, stored: shownStored })
                    : null,
              placeholder: updating
                ? 'hermretro is updating. You can send again in a moment.'
                : startingGame
                  ? 'Starting the conversation…'
                  : shownChat?.busy
                    ? `Reply to ${AGENT}…`
                    : `Tell ${AGENT} what to change in ${title}…`,
              status: shownChat ? jsx(BuildStatus, { chat: { ...shownChat, stored: shownStored }, onStop: () => void stopBuildChat(shownStored) }) : null,
              ask: openPrompt && shownStored ? jsx(BuildPromptCard, { item: openPrompt, stored: shownStored }, openPrompt.requestId ?? 'prompt') : null,
              stored: shownStored
            }, `composer:${composerKey}`)
          ]
        })

  // The game whose images this page shows (the backend answers no other game's).
  return jsx(AssetGame.Provider, { value: rootOf(game, shownChat?.items ?? []), children: jsx('div', { className: 'cs-b', children: main }) })
}
