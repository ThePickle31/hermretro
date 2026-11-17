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
import { BUILD_CHATS, BUILD_PRESENTED, BUILD_VIEWING, chatRequest, patchChat } from './chat/store.js'
import { BuildComposer } from './composer/composer.js'
import { ChatModelPicker, DraftModelPicker, useDraftPick } from './composer/model-picker.js'
import { InlinePlayer } from './player/inline-player.js'
import { PlayCard } from './player/play-card.js'
import { rootOf } from './transcript/groups.js'
import { BuildStatus } from './transcript/status.js'
import { Transcript } from './transcript/transcript.js'
import { buildHistory, deriveTurns } from './transcript/turns.js'
import { callStudioOnly, describeRequestError } from '#app/backend.js'
import { AGENT } from '#app/ids.js'
import { RPC_BUILD_RESTORE } from '#app/rpc.js'
import { playableSha } from '#app/player/stage.js'
import { buildRpc, newGamePrompt } from './binding.js'
import { BuildPill, BuildsMenu } from './builds-menu.js'
import { BuildNewGame } from './new-game.js'
import { BuildSwitcher, switcherEntries } from './switcher.js'

export function BuildPage({ ctx, games, pendingGames, loaded = true, onPlay, onLibraryChanged }) {
  const chats = useValue(BUILD_CHATS)
  // The model and effort a new conversation starts on (New Game, a game with no conversation yet).
  const [draftPick, setDraftPick] = useDraftPick(ctx)
  // Bindings made this visit, until the library answers with them (and the only record on an older backend).
  // released: game id → the stored id it let go of with Stop editing, until the library stops listing it.
  const [local, setLocal] = useState({ bound: {}, pending: [], released: {} })
  const [selected, setSelected] = useState(() => {
    try {
      return ctx.storage.get('buildSelected', 'new') || 'new'
    } catch {
      return 'new'
    }
  })

  const select = key => {
    setSelected(key)

    try {
      ctx.storage.set('buildSelected', key)
    } catch {
      // this visit only
    }
  }

  const rail = useMemo(
    () =>
      games.map(game => {
        const session = game.session && local.released[game.id] !== game.session.storedId ? game.session : null

        return { ...game, session, title: game.displayTitle || game.title, buildSession: session?.storedId ?? local.bound[game.id] ?? null }
      }),
    [games, local.bound, local.released]
  )
  const pending = useMemo(
    () =>
      [
        ...(Array.isArray(pendingGames) ? pendingGames : []),
        ...local.pending.filter(item => !(pendingGames ?? []).some(known => known.storedId === item.storedId))
      ].filter(item => !rail.some(game => game.buildSession === item.storedId)),
    [pendingGames, local.pending, rail]
  )

  // A New Game conversation becomes its game's once the library shows the game it made.
  useEffect(() => {
    if (!selected.startsWith('pending:')) {
      return
    }

    const stored = selected.slice('pending:'.length)
    const made = rail.find(game => game.buildSession === stored)

    if (made) {
      select(made.id)
    }
  }, [games, selected])

  // While a New Game conversation has not made its game yet, look at the library after each turn.
  useEffect(() => {
    if (pending.some(item => chats[item.storedId]?.busy === false)) {
      onLibraryChanged()
    }
  }, [pending.map(item => chats[item.storedId]?.busy).join(',')])

  const game = rail.find(item => item.id === selected) ?? null
  const pendingItem = selected.startsWith('pending:') ? (pending.find(item => `pending:${item.storedId}` === selected) ?? null) : null

  // A remembered selection that is gone (game removed, New Game discarded elsewhere) falls back to New game.
  useEffect(() => {
    const madeGame = selected.startsWith('pending:') && rail.some(item => item.buildSession === selected.slice(8))

    if (loaded && selected !== 'new' && !game && !pendingItem && !madeGame && !(selected.startsWith('pending:') && chats[selected.slice(8)]?.busy)) {
      select('new')
    }
  }, [loaded, selected, Boolean(game), Boolean(pendingItem)])

  // Presentations of the game shown here play in this conversation, not in a tab beside the chat.
  useEffect(() => {
    BUILD_VIEWING.set(game?.id ?? null)

    return () => BUILD_VIEWING.set(null)
  }, [game?.id])

  // A conversation in another Hermes profile is not opened (or replaced) from here.
  const elsewhere = Boolean(game?.session && game.session.thisProfile === false)
  const stored = elsewhere ? null : (game?.buildSession ?? pendingItem?.storedId ?? null)
  const chat = stored ? chats[stored] : null

  useEffect(() => {
    if (!stored || chat?.runtime || chat?.opening || chat?.failure) {
      return
    }

    // The library already knows this profile has no such session: no resume needed to say so.
    if (game?.session?.storedId === stored && game.session.exists === false) {
      patchChat(stored, current => (current.missing ? current : { ...current, missing: true }))
    } else {
      void openBuildChat(stored)
    }
  }, [stored, chat?.runtime])

  // A reply that finished while the user looked at this conversation is read.
  useEffect(() => {
    if (stored && chat && !chat.busy && (chat.lastCompleteAt ?? 0) > (chat.seenAt ?? 0)) {
      patchChat(stored, current => ({ ...current, seenAt: Date.now() }))
    }
  }, [stored, chat?.lastCompleteAt, chat?.busy])

  // The game plays in the conversation once the agent is done: it opens by itself when the agent handed it
  // over this turn (chromatic_present_game), and stays open until the user closes it.
  const [playerFor, setPlayerFor] = useState(null)
  const presented = useValue(BUILD_PRESENTED)[game?.id ?? ''] ?? null
  const seenPresent = useRef(presented?.seq ?? 0)
  const openWhenDone = useRef(false)

  useEffect(() => {
    const seq = presented?.seq ?? 0

    if (seq !== seenPresent.current) {
      seenPresent.current = seq
      openWhenDone.current = true
    }
  }, [presented?.seq])

  useEffect(() => {
    if (game && openWhenDone.current && !chat?.busy && !chat?.opening) {
      openWhenDone.current = false
      setPlayerFor(game.id)
    }
  }, [chat?.busy, chat?.opening, presented?.seq, game?.id])

  useEffect(() => {
    openWhenDone.current = false
  }, [game?.id])

  const startGame = async ({ idea, name, plan }) => {
    let id = null

    try {
      id = await createBuildChat(name.trim() || 'New game', draftPick)
      // The backend tells the agent each turn that this is a New Game conversation (and how to start), so
      // the idea is sent as the user wrote it. An older backend gets the instructions in the message.
      const recorded = await buildRpc({ action: 'start', stored: id, name: name.trim() || null, plan })

      setLocal(current => ({ ...current, pending: [...current.pending, { storedId: id, name: name.trim() || null }] }))
      select(`pending:${id}`)
      await sendBuildChat(id, recorded ? idea.trim() : newGamePrompt({ idea, name, plan }), idea.trim())
      onLibraryChanged()
    } catch (error) {
      host.notify({ kind: 'error', message: `Could not start the conversation: ${describeRequestError(error).message}` })

      if (id) {
        void buildRpc({ action: 'cancel', stored: id }).catch(() => {})
      }
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

    setLocal(current => ({ ...current, pending: current.pending.filter(entry => entry.storedId !== item.storedId) }))
    select('new')
    onLibraryChanged()
  }

  // Set when the user starts over after the game's conversation was removed from Hermes.
  const [forgotten, setForgotten] = useState({})
  const fresh = Boolean(game && !elsewhere && (!stored || forgotten[game.id]))
  const shownStored = fresh ? null : stored
  const shownChat = shownStored ? chat : null
  const shownItems = shownChat?.items ?? null
  const shownRoot = useMemo(() => rootOf(game, shownItems ?? []), [game?.projectRoot, shownItems])
  // A turn to scroll to (the Builds menu's Show).
  const [focusTurn, setFocusTurn] = useState(null)

  // The conversation's builds, worked out between turns (never while a reply streams).
  const settledItems = useRef(null)

  if (!shownChat?.busy) {
    settledItems.current = shownItems
  }

  const builds = useMemo(() => buildHistory(deriveTurns(settledItems.current ?? [])), [settledItems.current])

  // A game with no conversation opens a blank one; the session is made on the first message and bound to
  // the game (replacing a removed one), so the agent is told which game it works on and finds it selected.
  const send = async (text, attachments = [], shown = text) => {
    if (!fresh) {
      if (stored) {
        await sendBuildChat(stored, text, shown, attachments)
      }

      return
    }

    let target
    let recorded

    try {
      target = await createBuildChat(game.title, draftPick)
      recorded = await buildRpc({ action: 'bind', game: game.id, stored: target, replace: Boolean(stored || game.session) })
      setLocal(current => ({ ...current, bound: { ...current.bound, [game.id]: target } }))
      setForgotten(current => ({ ...current, [game.id]: false }))
      onLibraryChanged()
    } catch (error) {
      host.notify({ kind: 'error', message: `Could not start the conversation: ${describeRequestError(error).message}` })

      return
    }

    // An older backend cannot tell the agent which game this is: say it in the first message.
    await sendBuildChat(
      target,
      recorded ? text : `Work on my existing hermretro game "${game.title}" at ${game.projectRoot} (select that project first). ${text}`,
      shown,
      attachments
    )
  }

  const startOver = () => {
    if (game) {
      setForgotten(current => ({ ...current, [game.id]: true }))
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
    setForgotten(current => ({ ...current, [target.id]: false }))

    if (selected === target.id) {
      select('new')
    }

    onLibraryChanged()
  }

  // Restore: the backend saves the game as it is now, puts that build's files back, and the agent is
  // asked to build it again, which makes it the newest build.
  const restoreBuild = async (build, snapshot) => {
    if (!game || !shownStored) {
      return false
    }

    try {
      const answer = await callStudioOnly(RPC_BUILD_RESTORE, { game: game.id, id: snapshot }, 60_000)

      if (!answer?.ok) {
        throw new Error(answer?.error ?? 'The build could not be restored.')
      }
    } catch (error) {
      host.notify({ kind: 'error', message: `Could not restore build #${build.n}: ${describeRequestError(error).message}` })

      return false
    }

    onLibraryChanged()
    await send(
      `I restored the game to build #${build.n} ("${build.title}") from the hermretro Builds menu: its files are back as they were then (the version before this is saved). Please build it again and check that it still works.`,
      [],
      `Restore build #${build.n} \u00b7 ${build.title}`
    )

    return true
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

  const title = game?.title ?? pendingItem?.name ?? 'New game'
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
            game && (builds.length || shownStored)
              ? jsx(BuildsMenu, {
                  builds,
                  busy: Boolean(shownChat?.busy),
                  game,
                  onRestore: restoreBuild,
                  onShow: key => setFocusTurn(current => ({ key, seq: (current?.seq ?? 0) + 1 }))
                })
              : null,
            pendingItem && !shownChat?.busy
              ? jsx(Button, { onClick: () => void discard(pendingItem), size: 'sm', variant: 'ghost', children: 'Discard' })
              : null
          ]
        })

  const jumpToQuestion = () => document.querySelector?.('.cs-b-card[data-prompt="open"]')?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
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

  let body

  if (elsewhere) {
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
        game ? jsx(Button, { onClick: startOver, size: 'sm', children: 'Start a new conversation' }) : null
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
                children: playerFor === game.id
                  ? jsx(InlinePlayer, { ctx, game, note: null, onClose: () => setPlayerFor(null), stored: shownStored }, `player:${game.id}`)
                  : jsx(PlayCard, { game, onPlay: () => setPlayerFor(game.id), state: 'ready' })
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
      onClosePlayer: () => setPlayerFor(null),
      onPlay: () => game && setPlayerFor(game.id),
      onSend: (text, shown, attachments) => void send(text, attachments ?? [], shown ?? text),
      focusTurn,
      playerOpen: Boolean(game && playerFor === game.id),
      stored: shownStored
    }, shownStored ?? 'none')
  }

  const main =
    selected === 'new'
      ? jsxs('div', {
          className: 'cs-b-chat',
          children: [header, jsx(BuildNewGame, { onStart: startGame, picker: jsx(DraftModelPicker, { ctx, onPick: setDraftPick, pick: draftPick, up: false }) })]
        })
      : jsxs('div', {
          className: 'cs-b-chat',
          children: [
            header,
            body,
            jsx(BuildComposer, {
              busy: Boolean(shownChat?.busy),
              game,
              disabled: Boolean(elsewhere || shownChat?.opening || shownChat?.missing || shownChat?.failure || (!fresh && !shownChat?.runtime)),
              onSend: (text, attachments) => void send(text, attachments),
              onStop: () => void stopBuildChat(shownStored),
              picker: elsewhere || shownChat?.missing
                ? null
                : fresh
                  ? jsx(DraftModelPicker, { ctx, onPick: setDraftPick, pick: draftPick })
                  : shownStored
                    ? jsx(ChatModelPicker, { chat: shownChat, disabled: !shownChat?.runtime, stored: shownStored })
                    : null,
              placeholder: shownChat?.busy ? `Reply to ${AGENT}…` : `Tell ${AGENT} what to change in ${title}…`,
              status: shownChat ? jsx(BuildStatus, { chat: { ...shownChat, stored: shownStored }, onJump: jumpToQuestion, onStop: () => void stopBuildChat(shownStored) }) : null,
              stored: shownStored
            })
          ]
        })

  return jsx('div', { className: 'cs-b', children: main })
}
