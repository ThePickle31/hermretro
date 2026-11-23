// The asset viewer.
import { Button, Codicon, host, jsx, jsxs, useEffect, useLayoutEffect, useMemo, useRef, useState } from '#sdk'
import { useAsset } from '#pages/build/assets/cache.js'
import { assetRestoreBlocked, canSendAssetChange } from '#pages/build/assets/changes.js'
import { imagePalette, useImage } from '#pages/build/assets/images.js'
import { canvasImage, paintSheet, spriteAnimations, spriteFrameMs } from '#pages/build/assets/sprite.js'
import { BUILD_CHATS } from '#pages/build/chat/store.js'
import { turnParts } from '#pages/build/transcript/turns.js'
import { baseName } from '#app/paths.js'
import { AssetDetails } from './asset-details.js'
import { ChangeForm } from './change-form.js'
import { artChecks } from './checks.js'
import { CoverInGame, SceneCanvas } from './in-game.js'
import { useAssetInfo, VIEWER_KIND } from './info.js'
import { SpriteFrameCanvas } from './sprite-canvas.js'
import { fitScale, ImageStage, useBoxSize, ZOOM_STEPS } from './stage.js'
import { StageViewport } from './stage-viewport.js'
import { useVersionHistory, VersionHistory } from './version-history.js'

/** Look closer at a picture: see it, see it in the game, check it, change it, go back to a version. */
export function AssetViewer({ ctx, assets, index, onIndex, onClose, onSend, opener, chat, root, game, stored, turns }) {
  const asset = assets[index]
  const path = asset?.path ?? null
  const [refresh, setRefresh] = useState(0)
  const lastChange = chat?.lastAssetChange
  const [edits, setEdits] = useState(() => ({ last: lastChange, byPath: new Map() }))

  if (lastChange && edits.last !== lastChange) {
    setEdits({ last: lastChange, byPath: new Map(edits.byPath).set(lastChange.path, lastChange) })
  }

  const edit = edits.byPath.get(path)
  const info = useAssetInfo(path, refresh, edit)
  const opened = useAsset(path, asset?.version)
  const version = useVersionHistory({
    path, original: asset?.version, edit, info, root,
    canRestore: () => !assetRestoreBlocked(BUILD_CHATS.get()[stored]),
    onRefresh: () => setRefresh(value => value + 1)
  })
  const { state, loaded, shownNumber } = version
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
  const [gameColours, setGameColours] = useState(true)
  const [animationIndex, setAnimationIndex] = useState(0)
  const [frame, setFrame] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [onion, setOnion] = useState(false)
  const [sceneIndex, setSceneIndex] = useState(0)
  const stageRef = useRef(null)
  const box = useBoxSize(stageRef)
  const dialog = useRef(null)
  const palette = useMemo(() => (image ? imagePalette(image, 32) : []), [image])
  const checks = useMemo(() => artChecks(image, kind, info), [image, kind, info])
  const name = sprite?.name || loaded?.sprite?.name || loaded?.name || baseName(path ?? '')
  const animation = animations[Math.min(animationIndex, Math.max(0, animations.length - 1))] ?? null
  const frames = animation?.frames ?? []
  const frameMs = spriteFrameMs(sprite?.animSpeed)
  const colors = gameColours ? info?.palette?.colors : null
  const change = chat?.assetChange
  const working = change?.path === path
  const changeDisabled = version.restoring || !canSendAssetChange(chat)
  const asks = [...new Set(assets.filter(entry => entry.path === path && entry.ask).map(entry => entry.ask))]

  // A new picture starts fresh.
  useEffect(() => {
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

  useEffect(() => {
    if (side !== 'Change') {
      setArea(null)
    }
  }, [side])

  useLayoutEffect(() => {
    const previous = opener ?? document.activeElement
    const element = dialog.current

    element?.focus({ preventScroll: true })

    return () => {
      const active = document.activeElement

      if (previous?.isConnected && (element?.contains(active) || active === document.body)) {
        previous.focus({ preventScroll: true })
      }
    }
  }, [opener])

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

  useEffect(() => {
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
      } else if (event.key === ' ' && shownView === 'Animation' && !event.target?.closest?.('button')) {
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
  }, [area, assets.length, currentScale, frames.length, index, onClose, onIndex, shownView])

  // The wheel zooms (a non-passive listener, so the page does not scroll).
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

  // The steps of the turn the change started, newest last.
  const changeTurn = working ? turns.findLast(turn => turn.user?.assetChange === change) : null
  const progress = changeTurn ? turnParts(changeTurn, root).steps.slice(-6) : []
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
    stage = jsx(SceneCanvas, { highlight: kind === 'sprite' ? sprite?.id : null, refresh, scale: currentScale, scene })
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
            jsx(StageViewport, {
              area, kind, picking, running, shownView, stageRef, working,
              playback: { animation, animations, colors, frame, frames, image, onion, playing, setAnimationIndex, setFrame, setOnion, setPlaying, sprite },
              scenePicker: { scene, scenes, setSceneIndex },
              children: stage
            }),
            jsxs('div', {
              className: 'cs-v-side',
              children: [
                jsx('div', {
                  className: 'cs-v-tabs',
                  role: 'tablist',
                  children: ['Details', 'Change'].map(entry => jsxs('button', { 'aria-selected': side === entry, className: side === entry ? 'on' : '', onClick: () => setSide(entry), role: 'tab', type: 'button', children: [entry, entry === 'Change' && working ? jsx('span', { className: 'cs-b-spin' }) : null] }, entry))
                }),
                jsxs('div', {
                  className: 'cs-v-pane',
                  children: [
                    side === 'Details' ? jsx(AssetDetails, { asset, checks, copyColour, gameColours, info, kind, palette, setGameColours, version, restoreBlocked: assetRestoreBlocked(chat) }) : null,
                    jsx(ChangeForm, {
                      active: side === 'Change', area, asks, change: working ? change : null, disabled: changeDisabled,
                      image, kind, loaded, name, onArea: setArea, onSend, path, progress, shownView, version
                    }, path)
                  ]
                })
              ]
            })
          ]
        }),
        jsxs('div', {
          className: 'cs-v-foot',
          children: [
            jsx(VersionHistory, { path, version, working }),
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
