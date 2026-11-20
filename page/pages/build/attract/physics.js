// The attract-mode world's units and physics: 24-px tiles, the Nous Girl's box and jump, the collider grid and one
// physics step (solid tiles, one-way planks, moving platforms). Shared by the level builder, the planner and the game.

export const T = 24
export const GRAV = 0.25, MAXFALL = 5, JUMPV = 6.6, SPEED = 1.4
// the double jump: a second, smaller push at the top of the first (a spin)
export const DJUMPV = 5.2
export const GW = 10, GH = 28 // the girl's box (35 px from hair top to shoes; the hair dome may brush ceilings)

/** A small seeded random generator (mulberry32), so a layout can be rebuilt and tested. */
export function rngOf(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6D2B79F5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
export const overlap = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y

// A coarse grid of colliders so a body only tests what is near it (a big level has hundreds).
export const CELL = 32
export function indexColliders(L) {
  const gw = Math.ceil(L.W / CELL) + 1, gh = Math.ceil((L.H + 64) / CELL) + 2
  const mk = () => Array.from({ length: gw * gh }, () => [])
  const put = (grid, r) => {
    const c0 = Math.max(0, Math.floor(r.x / CELL)), c1 = Math.min(gw - 1, Math.floor((r.x + r.w) / CELL))
    const r0 = Math.max(0, Math.floor((r.y + 64) / CELL)), r1 = Math.min(gh - 1, Math.floor((r.y + r.h + 64) / CELL))
    for (let j = r0; j <= r1; j++) for (let i = c0; i <= c1; i++) grid[j * gw + i].push(r)
  }
  L.gw = gw; L.gh = gh
  L.sGrid = mk(); L.oGrid = mk()
  for (const r of L.solids) put(L.sGrid, r)
  for (const o of L.oneways) if (!o.mover) put(L.oGrid, o)
  L.stamp = 0
}
export function near(L, grid, b, extra) {
  const out = []
  const st = ++L.stamp
  const c0 = Math.max(0, Math.floor((b.x - 8) / CELL)), c1 = Math.min(L.gw - 1, Math.floor((b.x + b.w + 8) / CELL))
  const r0 = Math.max(0, Math.floor((b.y - 8 + 64) / CELL)), r1 = Math.min(L.gh - 1, Math.floor((b.y + b.h + 8 + 64) / CELL))
  for (let j = r0; j <= r1; j++) for (let i = c0; i <= c1; i++) for (const r of grid[j * L.gw + i]) if (r._st !== st) { r._st = st; out.push(r) }
  if (extra) for (const r of extra) out.push(r)
  return out
}

export function physStep(L, b, ignoreOneway, gravity = GRAV) {
  let ground = null, bumped = null, wall = false
  b.vy = Math.min(b.vy + gravity, MAXFALL)
  const solids = L.sGrid ? near(L, L.sGrid, { x: b.x + Math.min(0, b.vx), y: b.y + Math.min(0, b.vy), w: b.w + Math.abs(b.vx), h: b.h + Math.abs(b.vy) }) : L.solids
  const oneways = L.oGrid ? near(L, L.oGrid, { x: b.x + Math.min(0, b.vx), y: b.y, w: b.w + Math.abs(b.vx), h: b.h + Math.abs(b.vy) + 2 }, L.movers) : L.oneways
  // resolve only against what we were not already inside of, so nothing ever teleports across a block
  const px = b.x
  b.x += b.vx
  if (b.vx !== 0) {
    for (const r of solids) {
      if (!overlap(b, r)) continue
      if (b.vx > 0 && px + b.w <= r.x + 0.01) { b.x = r.x - b.w; wall = true } else if (b.vx < 0 && px >= r.x + r.w - 0.01) { b.x = r.x + r.w; wall = true }
    }
    if (b.x < 0) { b.x = 0; wall = true }
    if (b.x + b.w > L.W) { b.x = L.W - b.w; wall = true }
  }
  const prevBottom = b.y + b.h, prevTop = b.y
  b.y += b.vy
  for (const r of solids) {
    if (!overlap(b, r)) continue
    if (b.vy > 0 && prevBottom <= r.y + 0.01) { b.y = r.y - b.h; b.vy = 0; ground = r } else if (b.vy < 0 && prevTop >= r.y + r.h - 0.01) { b.y = r.y + r.h; b.vy = 0; bumped = r }
  }
  if (!ignoreOneway && b.vy >= 0) {
    for (const o of oneways) {
      const top = o.y
      if (b.x + b.w > o.x && b.x < o.x + o.w && prevBottom <= top + 0.01 + Math.max(0, o.dy || 0) + (o.dy < 0 ? -o.dy : 0) && b.y + b.h >= top) {
        b.y = top - b.h; b.vy = 0; ground = o
      }
    }
  }
  return { ground, bumped, wall }
}

export function solidAt(L, x, y) {
  const p = { x, y, w: 1, h: 1 }
  for (const r of near(L, L.sGrid, p)) if (x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h) return true
  for (const o of near(L, L.oGrid, p)) if (x >= o.x && x < o.x + o.w && y >= o.y && y < o.y + 4) return true
  return false
}
