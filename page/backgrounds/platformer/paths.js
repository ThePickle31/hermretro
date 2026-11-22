// Where she can stand and how she gets between places: walkable surfaces (split around anything low over them),
// every jump, double jump, walk-off and drop-through simulated with the real physics, a repair pass that adds small
// ledges under platforms she can't reach, and shortest paths over the result.
import { CELL, DJUMPV, GH, GRAV, GW, JUMPV, SPEED, T, near, overlap, physStep } from './physics.js'

export function buildSurfaces(L) {
  const S = []
  const isTop = v => v >= 1 && v <= 8
  for (let r = 0; r < L.rows; r++) {
    let c = 0
    while (c < L.cols) {
      const v = L.at(c, r)
      if (isTop(v) && !isTop(L.at(c, r - 1))) {
        let e = c
        while (e + 1 < L.cols && isTop(L.at(e + 1, r)) && !isTop(L.at(e + 1, r - 1))) e++
        S.push({ x0: c * T, x1: (e + 1) * T, y: L.oy + r * T })
        c = e + 1
      } else c++
    }
  }
  const out = []
  for (const s of S) { const a = Math.max(0, s.x0), b = Math.min(L.W, s.x1); if (b - a >= 12) out.push({ ...s, x0: a, x1: b }) }
  // a platform with something low over part of it splits into the parts she can stand on
  const kept = []
  for (const s of out) for (const part of standRuns(L, s)) { part.id = kept.length; kept.push(part) }
  L.surfaces = kept
}

export function standRuns(L, s) {
  const standFree = cx => { const b = { x: cx - GW / 2, y: s.y - GH, w: GW, h: GH - 0.5 }; for (const r of near(L, L.sGrid, b)) if (overlap(b, r)) return false; return true }
  const lo = Math.max(s.x0 + 4, GW / 2 + 1), hi = Math.min(s.x1 - 4, L.W - GW / 2 - 1)
  const runs = []
  let start = null
  for (let x = Math.ceil(lo); x <= hi + 1; x++) {
    const ok = x <= hi && standFree(x)
    if (ok && start === null) start = x
    if (!ok && start !== null) { if (x - 1 - start >= 2) runs.push({ ...s, x0: Math.max(s.x0, start - 4), x1: Math.min(s.x1, x - 1 + 4), l: start, r: x - 1 }); start = null }
  }
  if (!runs.length && hi < lo && standFree((s.x0 + s.x1) / 2)) runs.push({ ...s, l: (s.x0 + s.x1) / 2, r: (s.x0 + s.x1) / 2 })
  return runs
}
// Trim a walkable span to where her standing body touches nothing solid; false when nothing is left.
export function trimSpan(L, s) {
  const standFree = (cx, y) => { const b = { x: cx - GW / 2, y: y - GH, w: GW, h: GH - 0.5 }; for (const r of near(L, L.sGrid, b)) if (overlap(b, r)) return false; return true }
  let l = Math.max(s.x0 + 4, GW / 2 + 1), r = Math.min(s.x1 - 4, L.W - GW / 2 - 1)
  if (r < l) l = r = (s.x0 + s.x1) / 2
  while (l <= r && !standFree(l, s.y)) l++
  while (r >= l && !standFree(r, s.y)) r--
  s.l = l; s.r = r
  return r >= l
}

export function surfaceAt(L, cx, feet) {
  let best = null
  for (const s of L.surfaces) if (Math.abs(s.y - feet) < 0.6 && cx >= s.x0 - GW / 2 && cx <= s.x1 + GW / 2) { if (!best || (cx >= s.x0 && cx <= s.x1)) best = s }
  return best
}

// Simulate one move with the same physics and steering the autopilot uses.
export function simulate(L, cx, feet, mode, targetX) {
  const b = { x: cx - GW / 2, y: feet - GH, w: GW, h: GH, vx: 0, vy: mode === 'jump' || mode === 'djump' ? -JUMPV : 0 }
  let left = mode !== 'walk', through = mode === 'through' ? 14 : 0, top = feet, dj = mode !== 'djump'
  for (let f = 0; f < 200; f++) {
    top = Math.min(top, b.y + GH)
    if (!dj && f > 0 && b.vy >= -0.5) { b.vy = -DJUMPV; dj = true }
    const c = b.x + GW / 2
    const input = Math.abs(targetX - c) > 1.2 ? Math.sign(targetX - c) : 0
    b.vx = input * SPEED
    const res = physStep(L, b, through > 0 || false, GRAV)
    if (through > 0) through--
    if (b.y > L.H + 10) return null
    if (res.ground) {
      if (res.ground.mover) return null
      if (!left) { if (input === 0) return null; continue }
      if (f === 0) continue
      return { s: surfaceAt(L, b.x + GW / 2, b.y + GH), frames: f, rise: feet - top }
    }
    left = true
  }
  return null
}

// The path of her centre on a jump from (cx, feet) steering toward targetX, until she lands; null if she doesn't.
export function trail(L, cx, feet, targetX) {
  const b = { x: cx - GW / 2, y: feet - GH, w: GW, h: GH, vx: 0, vy: -JUMPV }, pts = []
  for (let f = 0; f < 200; f++) {
    const c = b.x + GW / 2
    b.vx = Math.abs(targetX - c) > 1.2 ? Math.sign(targetX - c) * SPEED : 0
    const res = physStep(L, b, false, GRAV)
    if (b.y > L.groundY + 10) return null
    pts.push({ x: b.x + GW / 2, y: b.y + GH * 0.45 })
    if (res.ground && f > 0) return res.ground.mover ? null : pts
  }
  return null
}
// Where a body already in the air lands, steering toward targetX (after a bounce off an enemy).
export function landsFrom(L, b0, targetX) {
  const b = { x: b0.x, y: b0.y, w: GW, h: GH, vx: 0, vy: b0.vy }
  for (let f = 0; f < 200; f++) {
    const c = b.x + GW / 2
    b.vx = Math.abs(targetX - c) > 1.2 ? Math.sign(targetX - c) * SPEED : 0
    const res = physStep(L, b, false, GRAV)
    if (b.y > L.groundY + 10) return null
    if (res.ground) return res.ground.mover ? null : surfaceAt(L, b.x + GW / 2, b.y + GH)
  }
  return null
}
// For every platform, try a fan of jumps, walk-offs and drop-throughs from points along it and keep the cheapest
// way found to each platform it lands on.
const OFFS = [-120, -84, -60, -42, -27, -14, 0, 14, 27, 42, 60, 84, 120]
export function edgesFor(L, A) {
  const best = new Map()
  const keep = (res, tx, lx, mode) => {
    if (!res || !res.s || res.s === A) return
    const cost = res.frames + 24 + (mode === 'walk' ? 0 : mode === 'djump' ? 16 : 6)
    const cur = best.get(res.s.id)
    if (!cur || cost < cur.cost) best.set(res.s.id, { to: res.s.id, tx, lx, mode, cost })
  }
  const txs = new Set([Math.round(A.l), Math.round(A.r)])
  const stepX = Math.max(16, (A.r - A.l) / 9)
  for (let x = A.l + stepX; x < A.r - 6; x += stepX) txs.add(Math.round(x))
  const isOneway = L.oneways.some(o => !o.mover && Math.abs(o.y - A.y) < 0.5 && o.x <= A.x0 + 1 && o.x + o.w >= A.x1 - 1)
  for (const tx of txs) {
    for (const d of OFFS) keep(simulate(L, tx, A.y, 'jump', tx + d), tx, tx + d, 'jump')
    for (const d of OFFS) keep(simulate(L, tx, A.y, 'djump', tx + d), tx, tx + d, 'djump')
    if (isOneway) for (const d of [-21, 0, 21]) keep(simulate(L, tx, A.y, 'through', tx + d), tx, tx + d, 'through')
  }
  for (const [tx, dir] of [[Math.round(A.l), -1], [Math.round(A.r), 1]]) {
    for (const d of [18, 36, 60, 90]) keep(simulate(L, tx, A.y, 'walk', tx + dir * d), tx, tx + dir * d, 'walk')
  }
  return [...best.values()]
}
export function withoutMovers(L, fn) {
  const save = L.oneways, saveM = L.movers
  L.oneways = L.oneways.filter(o => !o.mover); L.movers = []
  try { return fn() } finally { L.oneways = save; L.movers = saveM }
}
export function buildEdges(L) {
  withoutMovers(L, () => { for (const A of L.surfaces) L.edges.set(A.id, edgesFor(L, A)) })
}

// Make every platform reachable: under the lowest one she cannot reach, add a small one-way ledge three tiles
// down (or beside), re-test the jumps near it, and repeat until nothing is left out.
export function connect(L, free) {
  const ground = L.surfaces.filter(s => Math.abs(s.y - L.groundY) < 1)
  const reach = () => { const all = new Set(); for (const g of ground) if (!all.has(g.id)) for (const k of shortest(L, g.id).dist.keys()) all.add(k); return all }
  const rowOf = y => Math.round((y - L.oy) / T)
  const skip = new Set()
  let added = 0
  for (let it = 0; it < 90; it++) {
    const ok = reach()
    const lost = L.surfaces.filter(s => !ok.has(s.id) && !skip.has(s.id)).sort((a, b) => b.y - a.y)
    if (!lost.length) break
    const U = lost[0], rU = rowOf(U.y)
    const c0U = Math.floor(U.x0 / T), c1U = Math.ceil(U.x1 / T) - 1
    let placed = null
    const tryAt = (r, c) => {
      if (r >= L.gTop - 1 || c < 0 || c + 2 >= L.cols) return false
      for (let k = c; k < c + 3; k++) {
        if (!free(k, r) || L.at(k, r) !== 0 || L.at(k, r - 1) !== 0 || L.at(k, r - 2) !== 0 || L.at(k, r + 1) !== 0) return false
        if (k > 0 && L.at(k - 1, r) !== 0 && k === c) return false
        if (L.at(k + 1, r) !== 0 && k === c + 2) return false
      }
      return true
    }
    for (const dr of [3, 2]) {
      for (const c of [c0U - 1, c1U - 1, c0U - 3, c1U + 1, Math.floor((c0U + c1U) / 2) - 1, c0U - 4, c1U + 2]) if (tryAt(rU + dr, c)) { placed = { r: rU + dr, c }; break }
      if (placed) break
    }
    if (!placed) { skip.add(U.id); continue }
    const { r, c } = placed
    for (let k = c; k < c + 3; k++) L.grid[r * L.cols + k] = 5
    const o = { x: c * T, y: L.oy + r * T, w: 3 * T, h: 8, kind: 'ledge', step: true }
    L.oneways.push(o)
    const gw = L.gw
    for (let j = Math.max(0, Math.floor((o.y + 64) / CELL)); j <= Math.min(L.gh - 1, Math.floor((o.y + o.h + 64) / CELL)); j++) for (let i = Math.max(0, Math.floor(o.x / CELL)); i <= Math.min(gw - 1, Math.floor((o.x + o.w) / CELL)); i++) L.oGrid[j * gw + i].push(o)
    const S = { x0: o.x, x1: o.x + o.w, y: o.y, id: L.surfaces.length }
    if (!trimSpan(L, S)) { skip.add(U.id); continue }
    L.surfaces.push(S)
    withoutMovers(L, () => {
      for (const A of L.surfaces) if (A === S || (Math.abs(A.y - S.y) < 160 && A.x1 > S.x0 - 160 && A.x0 < S.x1 + 160)) L.edges.set(A.id, edgesFor(L, A))
    })
    added++
  }
  return added
}

export function shortest(L, fromId) {
  const dist = new Map([[fromId, 0]]), prev = new Map(), done = new Set()
  for (;;) {
    let u = null, best = Infinity
    for (const [k, v] of dist) if (!done.has(k) && v < best) { best = v; u = k }
    if (u === null) break
    done.add(u)
    for (const e of L.edges.get(u) || []) {
      const nd = best + e.cost
      if (nd < (dist.get(e.to) ?? Infinity)) { dist.set(e.to, nd); prev.set(e.to, { from: u, e }) }
    }
  }
  return { dist, prev }
}
export function firstEdge(paths, fromId, toId) {
  let cur = toId, step = null, guard = 0
  while (cur !== fromId && guard++ < 200) { const p = paths.prev.get(cur); if (!p) return null; step = p.e; cur = p.from }
  return step
}
