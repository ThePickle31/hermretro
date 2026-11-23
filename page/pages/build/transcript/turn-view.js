// One turn of the conversation.
import { Button, Codicon, jsx, jsxs, memo, useCallback, useRef } from '#sdk'
import { attachmentKey } from '#pages/build/chat/attachments.js'
import { AttachmentChip } from '#pages/build/composer/attachment-chip.js'
import { effortLabel, modelName } from '#pages/build/composer/model-names.js'
import { InlinePlayer } from '#pages/build/player/inline-player.js'
import { PlayCard, playsBuild } from '#pages/build/player/play-card.js'
import { AGENT } from '#app/ids.js'
import { spanWords } from '#shared/ui/time.js'
import { playableSha } from '#app/player/stage.js'
import { BuildCard, NextSteps, primaryArt } from './build-card.js'
import { FrameReplay } from './frame-replay.js'
import { AgentText, replyAssets } from './reply.js'
import { turnParts } from './turns.js'
import { Worked } from './worked.js'

function UserMessage({ user }) {
  return jsxs('div', {
    className: 'cs-b-user',
    children: [
      user.attachments?.length
        ? jsx('div', { className: 'cs-b-chips', children: user.attachments.map(item => jsx(AttachmentChip, { item }, attachmentKey(item))) })
        : null,
      jsx('span', { children: user.text })
    ]
  })
}

function TurnBody({ turn, live, turnStartedAt = null, previousModel = null, chatBusy, latestBuild, build = null, game, root, ctx, stored, playerOpen, onPlay, onClosePlayer, onOpenAsset, onSend, isLast }) {
  const parts = turnParts(turn, root)
  const user = turn.user
  const end = parts.end
  const agentAt = end?.at ?? null
  const hasAgent = live || turn.items.length > 0
  const startedAt = user?.at ?? end?.startedAt ?? null
  const showWorked = parts.entries.length > 0 || live
  // The viewer steps through the turn's images: the steps' first, then the ones its replies delivered.
  const viewerAssets = [...parts.assets]

  for (const asset of replyAssets([...parts.intro, ...parts.outro], root)) {
    if (!viewerAssets.some(entry => entry.path === asset.path && entry.version === asset.version)) {
      viewerAssets.push(asset)
    }
  }

  // The viewer quotes the message that asked for each picture.
  if (user?.text) {
    viewerAssets.forEach((asset, position) => {
      viewerAssets[position] = { ...asset, ask: user.text }
    })
  }

  const viewerRef = useRef(viewerAssets)

  viewerRef.current = viewerAssets

  // Stable, so the memoised replies do not re-render their markdown on every turn update.
  const openAsset = useCallback(asset => {
    const assets = viewerRef.current
    const matched = assets.some(entry => entry.path === asset.path && entry.version === asset.version)

    onOpenAsset(matched ? assets : [...assets, { ...asset, ask: user?.text }], asset)
  }, [onOpenAsset, user?.text])
  const playable = Boolean(game && game.webExport && playableSha(game))
  const inlinePlaying = playable && playerOpen && !chatBusy
  const frames = parts.frames
  const frame = frames.at(-1) ?? null
  const report = parts.report
  // A finished turn that built the game, or reported what it did, ends in its build card.
  const carded = !live && (build || report)
  const hasReplyMedia = [...parts.intro, ...parts.outro].some(item => /^\s*MEDIA:/im.test(item.text))
  const showResult = !live && build?.state !== 'failed'
  const art = showResult ? primaryArt(parts, root) : null
  const replay = showResult && !art && frame ? jsx(FrameReplay, { frames, onOpen: openAsset }) : null
  const featuredPaths = art ? [art] : replay ? frames.map(asset => asset.path) : []
  const compactPlayer = Boolean(art || replay || hasReplyMedia)

  // The newest build plays in a frame under its line; while the agent works, only its line says so.
  let play = null
  let playLabel = null

  if (latestBuild && game) {
    if (chatBusy) {
      playLabel = carded ? jsx('span', { className: 'cs-faint cs-small', children: `Playable again when ${AGENT} finishes` }) : null
    } else if (!playable) {
      play = jsx(PlayCard, { compact: compactPlayer, frame, game, state: 'unplayable' })
    } else if (playerOpen) {
      play = jsx(InlinePlayer, { build, ctx, game, note: parts.note, onClose: onClosePlayer, report, stored }, `player:${game.id}`)
    } else {
      play = jsx(PlayCard, { compact: compactPlayer, build: playsBuild(game, build) ? build.n : null, frame, game, note: parts.note, onPlay, state: 'ready' })
    }
  } else if (build?.state === 'built' && !live) {
    playLabel = jsx('span', { className: 'cs-faint cs-small', children: 'Earlier build' })
  }

  const took = startedAt && end?.at ? spanWords(end.at - startedAt) : null
  const card = carded || art
    ? jsx(BuildCard, {
        art,
        replay,
        play: inlinePlaying ? null : play,
        at: agentAt,
        build,
        chatBusy,
        isLast,
        onOpenAsset: openAsset,
        onSend,
        parts: { ...parts, startedAt: startedAt ?? null, endedAt: end?.at ?? null },
        playLabel,
        report,
        root,
        took
      })
    : replay
  const outro = parts.outro.map((item, index) => jsx(AgentText, { item, featuredPaths, onOpenAsset: openAsset, root }, `o${index}`))

  return jsxs('div', {
    className: 'cs-b-turn-body',
    children: [
      user ? jsx(UserMessage, { user }) : null,
      ...turn.items.filter(item => item.kind === 'user' && item.followup).map((item, index) =>
        jsx(UserMessage, { user: item }, item.submission ?? `followup${index}`)
      ),
      hasAgent
        ? jsxs('div', {
            className: 'cs-b-her',
            children: [
              // No name over the reply (it is the agent's thread); a line only where the model changed.
              user?.model && previousModel && (user.model !== previousModel.model || (user.effort ?? '') !== (previousModel.effort ?? ''))
                ? jsx('div', { className: 'cs-b-who', children: `${modelName(user.model).name}${user.effort ? ` · ${effortLabel(user.effort)}` : ''}` })
                : null,
              ...parts.intro.map((item, index) => jsx(AgentText, { item, featuredPaths, onOpenAsset: openAsset, root }, `i${index}`)),
              ...outro,
              showWorked
                ? jsx(Worked, { endedAt: end?.at ?? null, live, onOpenAsset: openAsset, parts, root, startedAt: live ? (turnStartedAt ?? startedAt ?? Date.now()) : startedAt, status: end?.status ?? null }, 'worked')
                : null,
              card,
              inlinePlaying || (!carded && !art) ? play : null,
              ...parts.errors.map((item, index) =>
                jsxs(
                  'div',
                  {
                    className: 'cs-b-card bad',
                    children: [
                      jsxs('div', { className: 'cs-row', children: [jsx(Codicon, { name: 'error', size: 14 }), jsx('b', { children: 'Something went wrong' })] }),
                      jsx('p', { className: 'cs-small', children: item.text }),
                      isLast && !chatBusy && item.resend
                        ? jsx('div', { className: 'cs-row', children: jsx(Button, { onClick: () => onSend(item.resend.text, item.resend.shown, item.resend.attachments ?? []), size: 'sm', variant: 'outline', children: 'Try again' }) })
                        : null
                    ]
                  },
                  `e${index}`
                )
              ),
              parts.buildFailed && !live && !carded
                ? jsxs('div', {
                    className: 'cs-b-card bad',
                    children: [
                      jsxs('div', { className: 'cs-row', children: [jsx(Codicon, { name: 'error', size: 14 }), jsx('b', { children: 'The build failed' })] }),
                      jsx('p', { className: 'cs-small', children: parts.buildFailed }),
                      isLast && !chatBusy
                        ? jsx('div', { className: 'cs-row', children: jsx(Button, { onClick: () => onSend('The build failed. Please fix it and build again.'), size: 'sm', variant: 'outline', children: `Ask ${AGENT} to fix it` }) })
                        : null
                    ]
                  })
                : null,
              end?.status === 'interrupted' && isLast && !chatBusy
                ? jsxs('div', {
                    className: 'cs-b-stopped',
                    children: [
                      jsx('span', { children: 'You stopped it here. Nothing is lost, and the last build still plays.' }),
                      jsx(Button, { onClick: () => onSend('Please carry on where you left off.'), size: 'sm', variant: 'outline', children: 'Carry on' })
                    ]
                  })
                : null,
              isLast && !chatBusy && !live ? jsx(NextSteps, { stored, suggestions: report?.suggestions }) : null
            ]
          })
        : null
    ]
  })
}

// Only mount a past build's transcript and media when someone opens it.
function TurnView(props) {
  const { turn, build, isLast, live, expanded, onToggleBuild, playerOpen, chatBusy, game, onPlay } = props
  const historical = Boolean(build && !isLast)
  const playing = playerOpen && !chatBusy
  const open = !historical || expanded || playing
  const toggle = () => {
    if (playing) {
      props.onClosePlayer()
    }

    if (!playing || expanded) {
      onToggleBuild(turn.key)
    }
  }

  return jsxs('section', {
    className: 'cs-b-turn',
    'data-history': historical || undefined,
    'data-live': live || undefined,
    'data-turn': turn.key,
    children: [
      historical ? jsxs('div', {
        className: 'cs-b-history',
        children: [
          jsxs('button', {
            'aria-expanded': open,
            className: 'cs-b-history-row',
            onClick: toggle,
            type: 'button',
            children: [
              jsx('span', { className: 'cs-b-history-number', children: `#${build.n}` }),
              jsx('span', { className: 'cs-b-history-title', children: build.title }),
              build.state === 'failed' ? jsx('span', { className: 'cs-b-history-failed', children: 'Failed' }) : null,
              build.state === 'unknown' ? jsx('span', { className: 'cs-faint', children: 'Outcome unknown' }) : null,
              jsx(Codicon, { name: open ? 'chevron-down' : 'chevron-right', size: 12 })
            ]
          }),
          !open && !chatBusy && game?.webExport && playableSha(game)
            ? jsx('button', { className: 'cs-b-link cs-b-history-play', onClick: onPlay, type: 'button', children: playsBuild(game, build) ? `Play build #${build.n}` : 'Play' })
            : null
        ]
      }) : null,
      open ? jsx(TurnBody, { ...props }) : null
    ]
  })
}

const sameItems = (a, b) => a.length === b.length && a.every((item, index) => item === b[index])

export const TurnMemo = memo(
  TurnView,
  (previous, next) =>
    sameItems(previous.turn.items, next.turn.items) &&
    previous.turn.user === next.turn.user &&
    previous.live === next.live &&
    previous.turnStartedAt === next.turnStartedAt &&
    previous.previousModel?.model === next.previousModel?.model &&
    previous.previousModel?.effort === next.previousModel?.effort &&
    previous.chatBusy === next.chatBusy &&
    previous.latestBuild === next.latestBuild &&
    previous.build === next.build &&
    previous.isLast === next.isLast &&
    previous.expanded === next.expanded &&
    previous.playerOpen === next.playerOpen &&
    previous.root === next.root &&
    previous.stored === next.stored &&
    (!next.latestBuild || previous.game === next.game) &&
    previous.onOpenAsset === next.onOpenAsset
)
