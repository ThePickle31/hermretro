// The asset viewer.
import { Button, Codicon, host, jsx, jsxs, useEffect, useMemo, useRef, useState } from '#sdk'
import { forgetAsset, useAsset } from '#pages/build/assets/cache.js'
import { imagePalette, useImage } from '#pages/build/assets/images.js'
import { canvasImage, paintSheet, spriteAnimations, spriteFrameMs } from '#pages/build/assets/sprite.js'
import { stepWords } from '#pages/build/transcript/step-words.js'
import { deriveTurns, turnParts } from '#pages/build/transcript/turns.js'
import { callStudioOnly } from '#app/backend.js'
import { AGENT } from '#app/ids.js'
import { baseName } from '#app/paths.js'
import { RPC_ASSET_RESTORE } from '#app/rpc.js'
import { timeOfDay } from '#shared/ui/time.js'
import { artChecks } from './checks.js'
import { CoverInGame, SceneCanvas } from './in-game.js'
import { useAssetInfo, useImages, VIEWER_KIND } from './info.js'
import { SpriteFrameCanvas } from './sprite-canvas.js'
import { fitScale, ImageStage, useBoxSize, VersionThumb, versionTime, ZOOM_STEPS } from './stage.js'

/** Look closer at a picture: see it, see it in the game, check it, change it, go back to a version. */
export function AssetViewer({ ctx, assets, index, onIndex, onClose, onSend, chat, root, game }) {
  const asset = assets[index]
  const path = asset?.path ?? null
  const [refresh, setRefresh] = useState(0)
  const info = useAssetInfo(path, refresh)
  const opened = useAsset(path, asset?.version)
  const [picked, setPicked] = useState(null)
  const shownVersion = picked ? `kept:${picked}` : asset?.version
  const { state, asset: loaded } = useAsset(path, shownVersion)
  const image = useImage(loaded?.dataUrl)
  const kind = info?.kind ?? (loaded?.sprite ? 'sprite' : opened.asset?.kind) ?? 'image'
  const sprite = info?.sprite ?? null
  const animations = useMemo(() => spriteAnimations(sprite), [sprite])
  const scenes = info?.scenes ?? []
  const views = kind === 'cover' ? ['Image', 'In game'] : kind === 'sprite' ? [...(animations.length ? ['Animation'] : []), 'Sheet', ...(scenes.length ? ['In game'] : [])] : kind === 'background' && scenes.length ? ['Image', 'In game'] : ['Image']
  const [view, setView] = useState(null)
  const shownView = views.includes(view) ? view : views[0]
  const [side, setSide] = useState('Details')
  const [zoom, setZoom] = useState('fit')
  const [grid, setGrid] = useState(false)
  const [area, setArea] = useState(null)
  const [request, setRequest] = useState('')
  const [rebuild, setRebuild] = useState(true)
  const [gameColours, setGameColours] = useState(true)
  const [animationIndex, setAnimationIndex] = useState(0)
  const [frame, setFrame] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [onion, setOnion] = useState(false)
  const [sceneIndex, setSceneIndex] = useState(0)
  const [sentAt, setSentAt] = useState(null)
  const [restoring, setRestoring] = useState(false)
  const stageRef = useRef(null)
  const box = useBoxSize(stageRef)
  const dialog = useRef(null)
  const input = useRef(null)
  const palette = useMemo(() => (image ? imagePalette(image, 32) : []), [image])
  const checks = useMemo(() => artChecks(image, kind, info), [image, kind, info])
  const sceneImages = useImages(
    useMemo(() => [...new Set(scenes.flatMap(scene => [scene.background, ...(scene.actors ?? []).map(actor => actor.sprite)]).filter(Boolean))], [scenes]),
    `scene:${refresh}`
  )
  const versions = info?.versions ?? []
  const currentId = versions.find(entry => entry.current)?.id ?? null
  const shownId = picked ?? loaded?.versionId ?? null
  const shownEntry = versions.find(entry => entry.id === shownId) ?? null
  const shownNumber = shownEntry ? versions.indexOf(shownEntry) + 1 : null
  const older = Boolean(shownEntry && currentId && shownEntry.id !== currentId)
  const name = sprite?.name || loaded?.sprite?.name || loaded?.name || baseName(path ?? '')
  const animation = animations[Math.min(animationIndex, Math.max(0, animations.length - 1))] ?? null
  const frames = animation?.frames ?? []
  const frameMs = spriteFrameMs(sprite?.animSpeed)
  const colors = gameColours ? info?.palette?.colors : null
  const working = Boolean(sentAt && chat?.busy)
  const asks = [...new Set(assets.filter(entry => entry.path === path && entry.ask).map(entry => entry.ask))]

  // A new picture starts fresh.
  useEffect(() => {
    setPicked(null)
    setView(null)
    setArea(null)
    setFrame(0)
    setAnimationIndex(0)
    setSceneIndex(0)
    setZoom('fit')
  }, [path, asset?.version])

  useEffect(() => setFrame(0), [animationIndex])

  // A sprite opens on a walking animation when it has one.
  useEffect(() => {
    if (!animations.length) {
      return
    }

    const walking = animations.findIndex(entry => /walk|run|moving/i.test(entry.name) && entry.frames.length > 1)

    setAnimationIndex(walking === -1 ? Math.max(0, animations.findIndex(entry => entry.frames.length > 1)) : walking)
  }, [animations])

  useEffect(() => {
    if (shownView !== 'Animation' || !playing || frames.length < 2) {
      return undefined
    }

    const id = setInterval(() => setFrame(value => (value + 1) % frames.length), frameMs)

    return () => clearInterval(id)
  }, [shownView, playing, frames.length, frameMs])

  // A change sent from here: when the agent finishes, the new version is fetched and shown.
  const wasWorking = useRef(false)

  useEffect(() => {
    if (working) {
      wasWorking.current = true
    } else if (sentAt && wasWorking.current) {
      wasWorking.current = false
      setSentAt(null)
      setPicked(null)
      setRefresh(value => value + 1)
    }
  }, [working, sentAt])

  // Once the new versions arrive after a change, show the one in the game.
  useEffect(() => {
    if (refresh && currentId) {
      setPicked(currentId)
    }
  }, [refresh, currentId])

  useEffect(() => {
    if (side === 'Change') {
      input.current?.focus?.()
    } else {
      setArea(null)
    }
  }, [side])

  useEffect(() => {
    dialog.current?.focus?.()

    const onKey = event => {
      const typing = /^(TEXTAREA|INPUT|SELECT)$/.test(event.target?.tagName ?? '')

      if (event.key === 'Escape') {
        event.preventDefault()

        if (area) {
          setArea(null)
        } else {
          onClose()
        }
      } else if (typing) {
        return
      } else if (event.key === 'ArrowRight' && assets.length > 1) {
        event.preventDefault()
        onIndex((index + 1) % assets.length)
      } else if (event.key === 'ArrowLeft' && assets.length > 1) {
        event.preventDefault()
        onIndex((index - 1 + assets.length) % assets.length)
      } else if ((event.key === ',' || event.key === '.') && shownView === 'Animation' && frames.length > 1) {
        event.preventDefault()
        setPlaying(false)
        setFrame(value => (value + (event.key === '.' ? 1 : frames.length - 1)) % frames.length)
      } else if (event.key === ' ' && shownView === 'Animation') {
        event.preventDefault()
        setPlaying(value => !value)
      } else if (event.key === '+' || event.key === '=') {
        setZoom(value => ZOOM_STEPS.find(step => step > (value === 'fit' ? currentScale : value)) ?? 16)
      } else if (event.key === '-') {
        setZoom(value => [...ZOOM_STEPS].reverse().find(step => step < (value === 'fit' ? currentScale : value)) ?? 1)
      }
    }

    window.addEventListener('keydown', onKey)

    return () => window.removeEventListener('keydown', onKey)
  })

  // The size of what the stage shows, at 1×.
  const scene = scenes[Math.min(sceneIndex, Math.max(0, scenes.length - 1))] ?? null
  let contentWidth = image?.naturalWidth ?? 0
  let contentHeight = image?.naturalHeight ?? 0

  if (shownView === 'Animation' && sprite) {
    contentWidth = sprite.canvasWidth
    contentHeight = sprite.canvasHeight
  } else if (shownView === 'In game' && scene) {
    contentWidth = (Number(scene.width) || 20) * 8
    contentHeight = (Number(scene.height) || 18) * 8
  }

  const fit = fitScale(box, contentWidth, contentHeight, shownView === 'Animation' ? 140 : 48)
  const currentScale = zoom === 'fit' ? fit : zoom
  const zoomable = shownView !== 'In game' || kind !== 'cover'

  // The wheel zooms (a non-passive listener, so the page does not scroll); dragging pans a big picture.
  useEffect(() => {
    const element = stageRef.current

    if (!element || !zoomable) {
      return undefined
    }

    const onWheel = event => {
      event.preventDefault()
      setZoom(value => {
        const now = value === 'fit' ? currentScale : value

        return event.deltaY < 0 ? (ZOOM_STEPS.find(step => step > now) ?? 16) : ([...ZOOM_STEPS].reverse().find(step => step < now) ?? 1)
      })
    }

    element.addEventListener('wheel', onWheel, { passive: false })

    return () => element.removeEventListener('wheel', onWheel)
  }, [zoomable, currentScale])

  const pan = useRef(null)

  if (!asset) {
    return null
  }

  const reveal = async () => {
    const shown = await ctx.os?.revealPath?.(path).catch(() => false)

    if (!shown) {
      const copied = await ctx.os?.writeClipboard?.(path).catch(() => false)

      host.notify({ kind: 'info', message: copied ? 'The file is on the computer running Hermes. Its path is copied.' : path })
    }
  }

  const copyImage = async () => {
    try {
      const blob = await (await fetch(loaded.dataUrl)).blob()

      await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })])
      host.notify({ kind: 'success', message: 'Image copied' })
    } catch {
      const copied = await ctx.os?.writeClipboard?.(path).catch(() => false)

      host.notify({ kind: 'info', message: copied ? 'The image could not be copied, so its path was.' : 'The image could not be copied.' })
    }
  }

  const copyColour = async color => {
    const copied = await ctx.os?.writeClipboard?.(color).catch(() => false)

    host.notify({ kind: copied ? 'success' : 'info', message: copied ? `${color} copied` : color })
  }

  const restore = async () => {
    if (!shownEntry || restoring) {
      return
    }

    setRestoring(true)

    try {
      const answer = await callStudioOnly(RPC_ASSET_RESTORE, { path, root, version: shownEntry.id }, 20_000)

      if (!answer?.ok) {
        throw new Error(answer?.error ?? 'It could not be restored.')
      }

      forgetAsset(path, answer.path)
      host.notify({ kind: 'success', message: `v${shownNumber} is back in the game. Build again to play it.` })
      setRefresh(value => value + 1)
    } catch (error) {
      host.notify({ kind: 'error', message: error instanceof Error ? error.message : String(error) })
    } finally {
      setRestoring(false)
    }
  }

  const send = () => {
    const words = request.trim()

    if (!words || !onSend || working) {
      return
    }

    const notes = []

    if (area && image) {
      notes.push(`Only change the area from (${area.x}, ${area.y}) to (${area.x + area.w - 1}, ${area.y + area.h - 1}), in pixels of the ${image.naturalWidth}×${image.naturalHeight} image. Keep everything outside it exactly as it is.`)
    }

    if (older && shownEntry) {
      notes.push(`Start from version ${shownNumber} (from ${versionTime(shownEntry)}), kept at ${shownEntry.file}. The file in the game is a newer version.`)
    }

    if (rebuild && (kind === 'sprite' || kind === 'background')) {
      notes.push('When it is done, build the game and show it to me with chromatic_present_game.')
    }

    const text = notes.length ? `${words}\n\n${notes.map(note => `- ${note}`).join('\n')}` : words

    onSend(text, area ? `${words} (the marked area)` : words, [{ path, name: loaded?.name ?? baseName(path) }])
    setRequest('')
    setArea(null)
    setSentAt(Date.now())
  }

  // The steps of the turn the change started, newest last.
  let progress = []

  if (sentAt && chat?.items?.length) {
    const turns = deriveTurns(chat.items)
    const last = turns[turns.length - 1]

    progress = last ? turnParts(last, root).steps.slice(-6) : []
  }

  const running = progress.find(tool => tool.state === 'running') ?? null
  const picking = side === 'Change' && (shownView === 'Image' || shownView === 'Sheet') && !working

  // ── stage ──
  let stage

  if (state === 'loading' || (!image && state !== 'none')) {
    stage = jsx('span', { className: 'cs-b-th lg loading' })
  } else if (!image) {
    stage = jsx('p', { className: 'cs-small', children: 'This picture could not be loaded.' })
  } else if (shownView === 'Animation' && animation) {
    const tiles = frames[Math.min(frame, frames.length - 1)] ?? []
    const before = onion && frames.length > 1 ? frames[(frame + frames.length - 1) % frames.length] : null

    stage = jsx(SpriteFrameCanvas, { colors, flip: animation.flip, image, scale: currentScale, sprite, tiles, under: before })
  } else if (shownView === 'In game' && kind === 'cover') {
    stage = jsx(CoverInGame, { game, image })
  } else if (shownView === 'In game' && scene) {
    stage = jsx(SceneCanvas, { highlight: kind === 'sprite' ? sprite?.id : null, images: sceneImages, refresh, scale: currentScale, scene })
  } else {
    const sheetColours = kind === 'sprite' && colors ? paintSheet(image, colors) : null

    stage = jsx(ImageStage, {
      area,
      grid,
      gridSize: kind === 'sprite' ? [8, 16] : [8, 8],
      image: sheetColours && sheetColours !== image ? canvasImage(sheetColours, image) : image,
      onArea: setArea,
      picking,
      scale: currentScale
    })
  }

  const chips = []

  if (shownView === 'Animation' && animations.length) {
    chips.push(
      jsx('div', {
        className: 'cs-v-float tl',
        children: animations.map((entry, position) =>
          jsx('button', { 'aria-pressed': entry === animation, className: `cs-v-chip${entry === animation ? ' on' : ''}`, onClick: () => setAnimationIndex(position), type: 'button', children: entry.name }, entry.slot)
        )
      }, 'anims'),
      jsxs('div', {
        className: 'cs-v-float tr',
        children: [
          jsx('button', { 'aria-label': playing ? 'Pause' : 'Play', className: 'cs-v-chip', onClick: () => setPlaying(value => !value), type: 'button', children: jsx(Codicon, { name: playing ? 'debug-pause' : 'play', size: 12 }) }),
          jsx('span', { className: 'cs-v-chip quiet', title: 'The speed the game plays it at', children: sprite?.animSpeed != null && Number(sprite.animSpeed) < 255 ? `${Math.round((60 / (Number(sprite.animSpeed) + 1)) * 10) / 10} fps` : 'Not animated in game' }),
          jsx('button', { 'aria-pressed': onion, className: `cs-v-chip${onion ? ' on' : ''}`, onClick: () => setOnion(value => !value), type: 'button', children: 'Onion skin' })
        ]
      }, 'play'),
      frames.length > 1
        ? jsx('div', {
            className: 'cs-v-float bottom',
            children: frames.map((tiles, position) =>
              jsx('button', {
                'aria-label': `Frame ${position + 1}`,
                'aria-pressed': position === frame,
                className: `cs-v-frame${position === frame ? ' on' : ''}`,
                onClick: () => {
                  setPlaying(false)
                  setFrame(position)
                },
                type: 'button',
                children: jsx(SpriteFrameCanvas, { colors, flip: animation.flip, image, scale: Math.max(1, Math.floor(36 / Math.max(sprite.canvasWidth, sprite.canvasHeight))), sprite, tiles })
              }, position)
            )
          }, 'frames')
        : null
    )
  }

  if (shownView === 'In game' && kind !== 'cover' && scenes.length) {
    chips.push(
      jsxs('div', {
        className: 'cs-v-float tl',
        children: [
          ...scenes.map((entry, position) =>
            jsx('button', { 'aria-pressed': entry === scene, className: `cs-v-chip${entry === scene ? ' on' : ''}`, onClick: () => setSceneIndex(position), type: 'button', children: entry.name }, entry.id ?? position)
          )
        ]
      }, 'scenes'),
      jsx('span', { className: 'cs-v-float br cs-v-chip quiet', children: 'As the scene starts, from the project files' }, 'note')
    )
  }

  if (picking && !area) {
    chips.push(jsx('span', { className: 'cs-v-float bottom cs-v-chip quiet', children: 'Drag on the picture to mark the area to change' }, 'hint'))
  }

  if (working) {
    chips.push(
      jsxs('div', {
        className: 'cs-v-working',
        children: [jsx('span', { className: 'cs-b-spin' }), jsx('span', { children: running ? `${AGENT}: ${stepWords(running)[0]}` : `${AGENT} is working on it` })]
      }, 'working')
    )
  }

  // ── side panel ──
  const madeBy = asset.step || asset.at
    ? jsxs('div', {
        className: 'cs-col cs-v-sec',
        children: [
          jsx('span', { className: 'cs-eyebrow', children: asset.step === 'In the reply' ? `Shown by ${AGENT}` : `Made by ${AGENT}` }),
          asset.ask ? jsx('span', { className: 'cs-v-quote', children: `\u201c${asset.ask.length > 140 ? `${asset.ask.slice(0, 140)}…` : asset.ask}\u201d` }) : null,
          jsx('span', { className: 'cs-faint', children: [asset.at ? timeOfDay(asset.at) : '', asset.step && asset.step !== 'In the reply' ? asset.step : ''].filter(Boolean).join(' · ') })
        ]
      })
    : null

  const details = [
    older
      ? jsxs('div', {
          className: 'cs-v-note',
          children: [
            jsx('span', { children: `This is v${shownNumber} from ${versionTime(shownEntry)}. The game uses v${versions.findIndex(entry => entry.current) + 1}.` }),
            jsxs('div', {
              className: 'cs-row',
              style: { gap: 6 },
              children: [
                jsx(Button, { disabled: restoring || working, onClick: () => void restore(), size: 'sm', children: restoring ? 'Restoring…' : `Restore v${shownNumber}` }),
                jsx(Button, { onClick: () => setPicked(currentId), size: 'sm', variant: 'ghost', children: 'Show the current one' })
              ]
            })
          ]
        }, 'older')
      : null,
    madeBy ? jsx('div', { children: madeBy }, 'made') : null,
    kind === 'sprite' && info?.palette
      ? jsxs('div', {
          className: 'cs-col cs-v-sec',
          children: [
            jsx('span', { className: 'cs-eyebrow', children: 'In-game palette' }),
            jsxs('div', {
              className: 'cs-row',
              style: { gap: 8 },
              children: [
                jsx('div', { className: 'cs-v-pal', children: info.palette.colors.map((color, position) => jsx('button', { onClick: () => void copyColour(color), style: { background: color }, title: `${color}${position === 2 ? ' (not used by sprites)' : ''}`, type: 'button' }, position)) }),
                info.palette.name ? jsx('span', { className: 'cs-tag', children: info.palette.name }) : null
              ]
            }),
            jsxs('label', { className: 'cs-v-toggle', children: [jsx('input', { checked: gameColours, onChange: event => setGameColours(event.target.checked), type: 'checkbox' }), 'Show it in these colours'] })
          ]
        }, 'palette')
      : null,
    palette.length
      ? jsxs('div', {
          className: 'cs-col cs-v-sec',
          children: [
            jsx('span', { className: 'cs-eyebrow', children: `Colours in the file · ${palette.length}${palette.length >= 32 ? '+' : ''}` }),
            jsx('div', { className: 'cs-v-sw', children: palette.map(color => jsx('button', { onClick: () => void copyColour(color), style: { background: color }, title: `${color} · click to copy`, type: 'button' }, color)) })
          ]
        }, 'colours')
      : null,
    checks.length
      ? jsxs('div', {
          className: 'cs-col cs-v-sec',
          children: [
            jsx('span', { className: 'cs-eyebrow', children: 'Checks' }),
            ...checks.map((check, position) => jsxs('span', { className: `cs-v-check${check.ok ? '' : ' bad'}`, children: [jsx(Codicon, { name: check.ok ? 'check' : 'warning', size: 12 }), check.text] }, position))
          ]
        }, 'checks')
      : null,
    kind === 'cover'
      ? jsxs('div', { className: 'cs-col cs-v-sec', children: [jsx('span', { className: 'cs-eyebrow', children: 'Shown on' }), jsx('span', { className: 'cs-v-text', children: 'Its Games page card and the Build page' })] }, 'shown')
      : info?.usedIn
        ? jsxs('div', {
            className: 'cs-col cs-v-sec',
            children: [
              jsx('span', { className: 'cs-eyebrow', children: 'Used in' }),
              ...(info.usedIn.length
                ? info.usedIn.map(use => jsxs('span', { className: 'cs-v-text', children: [jsx('b', { children: use.scene }), ` · ${use.count > 1 ? `${use.count}: ` : ''}${use.as.join(', ')}`] }, use.sceneId))
                : [jsx('span', { className: 'cs-faint', children: 'Not placed in any scene yet' }, 'none')])
            ]
          }, 'used')
        : null,
  ]

  const change = working || (sentAt && progress.length)
    ? [
        jsxs('div', {
          className: 'cs-v-card',
          children: [jsx('span', { className: 'cs-faint', children: 'You asked' }), jsx('span', { className: 'cs-v-text', children: chat?.items?.findLast?.(item => item.kind === 'user')?.text ?? '' })]
        }, 'asked'),
        jsxs('div', {
          className: 'cs-col cs-v-sec',
          children: [
            jsx('span', { className: 'cs-eyebrow', children: 'Progress' }),
            ...(progress.length ? progress : []).map(tool =>
              jsxs('span', {
                className: `cs-v-step ${tool.state}`,
                children: [tool.state === 'running' ? jsx('span', { className: 'cs-b-spin' }) : jsx(Codicon, { name: tool.state === 'failed' ? 'error' : 'check', size: 12 }), stepWords(tool)[tool.state === 'running' ? 0 : 1]]
              }, tool.id)
            ),
            !progress.length ? jsx('span', { className: 'cs-faint', children: 'Starting…' }) : null
          ]
        }, 'progress'),
        jsx('span', { className: 'cs-grow' }, 'grow'),
        jsx('span', { className: 'cs-faint', children: 'You can close this. The new version shows up here and in the chat.' }, 'close')
      ]
    : [
        jsx('textarea', {
          className: 'cs-v-input',
          disabled: !onSend,
          onChange: event => setRequest(event.target.value),
          onKeyDown: event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent?.isComposing) {
              event.preventDefault()
              send()
            }
          },
          placeholder: onSend ? `What should ${AGENT} change in ${name}?` : 'Open this game\u2019s conversation to ask for changes.',
          ref: input,
          rows: 4,
          value: request
        }, 'input'),
        area
          ? jsxs('div', {
              className: 'cs-row cs-v-sec',
              style: { gap: 6 },
              children: [jsx('span', { className: 'cs-v-text', children: `Only the marked area · ${area.w}×${area.h}` }), jsx('span', { className: 'cs-grow' }), jsx(Button, { onClick: () => setArea(null), size: 'sm', variant: 'ghost', children: 'Clear' })]
            }, 'area')
          : shownView === 'Image' || shownView === 'Sheet'
            ? jsx('span', { className: 'cs-faint', children: 'Drag on the picture to change just one area.' }, 'area')
            : null,
        older ? jsx('span', { className: 'cs-faint', children: `It starts from v${shownNumber}, the version shown.` }, 'from') : null,
        kind === 'sprite' || kind === 'background'
          ? jsxs('label', { className: 'cs-v-toggle', children: [jsx('input', { checked: rebuild, onChange: event => setRebuild(event.target.checked), type: 'checkbox' }), 'Build and show the game after'] }, 'rebuild')
          : null,
        jsxs(Button, { disabled: !onSend || !request.trim(), onClick: send, size: 'sm', children: [`Send to ${AGENT}`, jsx('span', { className: 'cs-v-kbd', children: '\u21b5' })] }, 'send'),
        jsx('span', { className: 'cs-grow' }, 'grow'),
        asks.length
          ? jsxs('div', {
              className: 'cs-col cs-v-sec',
              children: [jsx('span', { className: 'cs-eyebrow', children: 'Asked before' }), ...asks.slice(-4).map((ask, position) => jsx('span', { className: 'cs-faint', title: ask, children: `\u201c${ask.length > 80 ? `${ask.slice(0, 80)}…` : ask}\u201d` }, position))]
            }, 'asks')
          : null
      ]

  return jsx('div', {
    className: 'cs-b-dim',
    onClick: onClose,
    children: jsxs('div', {
      'aria-label': `${name}, ${VIEWER_KIND[kind] ?? 'Image'}`,
      'aria-modal': 'true',
      className: 'cs-v',
      onClick: event => event.stopPropagation(),
      ref: dialog,
      role: 'dialog',
      tabIndex: -1,
      children: [
        jsxs('div', {
          className: 'cs-v-top',
          children: [
            jsx('span', { className: 'cs-eyebrow', children: VIEWER_KIND[kind] ?? 'Image' }),
            jsx('b', { className: 'cs-v-name', title: path, children: name }),
            jsx('span', {
              className: 'cs-faint cs-b-ell',
              title: path,
              children: [
                info?.relative ?? loaded?.relative ?? loaded?.name ?? '',
                loaded ? `${loaded.width}×${loaded.height}` : '',
                kind === 'sprite' && sprite ? `${animations.length} ${animations.length === 1 ? 'animation' : 'animations'} of ${sprite.canvasWidth}×${sprite.canvasHeight}` : '',
                shownNumber ? `v${shownNumber}` : ''
              ].filter(Boolean).join(' · ')
            }),
            jsx('span', { className: 'cs-grow' }),
            views.length > 1
              ? jsx('div', { className: 'cs-v-seg', role: 'tablist', children: views.map(entry => jsx('button', { 'aria-selected': entry === shownView, className: entry === shownView ? 'on' : '', onClick: () => setView(entry), role: 'tab', type: 'button', children: entry }, entry)) })
              : null,
            zoomable
              ? jsxs('div', {
                  className: 'cs-v-zoom',
                  children: [
                    jsx('button', { className: `cs-v-chip${zoom === 'fit' ? ' on' : ''}`, onClick: () => setZoom('fit'), title: 'Fit (the biggest whole zoom that fits)', type: 'button', children: 'Fit' }),
                    ...[1, 2, 3, 4, 8].map(step => jsx('button', { className: `cs-v-chip${zoom === step ? ' on' : ''}`, onClick: () => setZoom(step), type: 'button', children: `${step}×` }, step)),
                    shownView === 'Image' || shownView === 'Sheet'
                      ? jsx('button', { 'aria-pressed': grid, className: `cs-v-chip${grid ? ' on' : ''}`, onClick: () => setGrid(value => !value), title: kind === 'sprite' ? '8×16 tile grid' : '8×8 tile grid', type: 'button', children: jsx(Codicon, { name: 'symbol-numeric', size: 12 }) })
                      : null
                  ]
                })
              : null,
            jsx('button', { 'aria-label': 'Close', className: 'cs-b-x', onClick: onClose, type: 'button', children: jsx(Codicon, { name: 'close', size: 14 }) })
          ]
        }),
        jsxs('div', {
          className: 'cs-v-body',
          children: [
            jsxs('div', {
              className: `cs-v-stage${kind === 'sprite' && shownView !== 'In game' ? ' checker' : ''}`,
              children: [
                jsx('div', {
                  className: `cs-v-scroll${picking ? '' : ' pannable'}`,
                  onPointerDown: event => {
                    const element = stageRef.current

                    if (picking || event.button !== 0 || !element || (element.scrollWidth <= element.clientWidth && element.scrollHeight <= element.clientHeight)) {
                      return
                    }

                    pan.current = { x: event.clientX, y: event.clientY, left: element.scrollLeft, top: element.scrollTop }
                    element.setPointerCapture?.(event.pointerId)
                  },
                  onPointerMove: event => {
                    const element = stageRef.current

                    if (pan.current && element) {
                      element.scrollLeft = pan.current.left - (event.clientX - pan.current.x)
                      element.scrollTop = pan.current.top - (event.clientY - pan.current.y)
                    }
                  },
                  onPointerUp: () => {
                    pan.current = null
                  },
                  ref: stageRef,
                  children: jsx('div', { className: 'cs-v-stage-in', children: stage })
                }),
                ...chips
              ]
            }),
            jsxs('div', {
              className: 'cs-v-side',
              children: [
                jsx('div', {
                  className: 'cs-v-tabs',
                  role: 'tablist',
                  children: ['Details', 'Change'].map(entry => jsxs('button', { 'aria-selected': side === entry, className: side === entry ? 'on' : '', onClick: () => setSide(entry), role: 'tab', type: 'button', children: [entry, entry === 'Change' && working ? jsx('span', { className: 'cs-b-spin' }) : null] }, entry))
                }),
                jsx('div', { className: 'cs-v-pane', children: side === 'Details' ? details : change })
              ]
            })
          ]
        }),
        jsxs('div', {
          className: 'cs-v-foot',
          children: [
            versions.length
              ? jsxs('div', {
                  className: 'cs-v-vers',
                  children: [
                    jsx('span', { className: 'cs-eyebrow', children: 'Versions' }),
                    ...versions.map((entry, position) => jsx(VersionThumb, { entry, number: position + 1, onPick: setPicked, path, selected: entry.id === shownId }, entry.id)),
                    working ? jsxs('span', { className: 'cs-v-ver pending', title: 'Being made now', children: [jsx('span', { className: 'cs-b-spin' }), jsx('b', { children: `v${versions.length + 1}` })] }) : null
                  ]
                })
              : null,
            jsx('span', { className: 'cs-grow' }),
            assets.length > 1 ? jsx('span', { className: 'cs-faint cs-v-nav', children: `\u2190 \u2192 other pictures · ${index + 1} of ${assets.length}` }) : null,
            jsxs(Button, { onClick: () => void reveal(), size: 'sm', variant: 'ghost', children: [jsx(Codicon, { name: 'folder-opened', size: 13 }), 'Show in folder'] }),
            loaded ? jsxs(Button, { onClick: () => void copyImage(), size: 'sm', variant: 'ghost', children: [jsx(Codicon, { name: 'copy', size: 13 }), 'Copy image'] }) : null
          ]
        })
      ]
    })
  })
}
