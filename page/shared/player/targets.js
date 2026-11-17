// What the engine's annotate hit test calls a thing on the game screen, in plain words. The engine
// (dist/web-annotations/targets.js) names targets like "Inferred sprite group; 4 parts",
// "Sprite 12; tile 3A" or "Background tile 2F" with a role of game-sprite, game-background or
// game-window. Shared by the frame (hover label) and the page (mark list, chips, message text).

const KIND_WORDS = { sprite: 'Sprite', background: 'Background tile', window: 'Window tile', frame: 'Whole screen' }

/** `game-sprite` → `sprite`. */
export function targetKind(role) {
  return String(role ?? '').replace(/^game-/, '') || 'frame'
}

/** A short label: "Sprite · 4 parts", "Sprite part", "Background tile". */
export function targetLabel(name, role) {
  const kind = targetKind(role)
  const group = /group;\s*(\d+)\s*parts/i.exec(String(name ?? ''))

  if (kind === 'sprite') {
    return group ? `Sprite \u00b7 ${group[1]} parts` : 'Sprite part'
  }

  return KIND_WORDS[kind] ?? 'Part of the screen'
}

/** The target's box on the 160 × 144 screen, read from the engine's metadata ("84,36 16x16px; …"). */
export function targetRect(metadata) {
  const found = /^(-?\d+),(-?\d+)\s+(\d+)x(\d+)px/.exec(String(metadata?.Hardware ?? ''))

  return found ? { x: Number(found[1]), y: Number(found[2]), w: Number(found[3]), h: Number(found[4]) } : null
}
