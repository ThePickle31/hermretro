// Coins, placed the way a level designer would: small groups well apart at running height, and arcs that trace a
// real jump between two platforms (the same physics she uses), so the coins show a way up through the level and she
// collects them by taking that jump. Never over or beside the page's boxes, never where she can't reach them.
import { GH, GW, JUMPV, overlap, physStep } from './physics.js'
import { trail, withoutMovers } from './paths.js'

export function placeCoins(L, dom, rng) {
  const W = L.W, H = L.H, cols = L.cols
  // Coins, placed the way a level designer would:
  //  - rows of 3 to 5, evenly spaced and centred, at running height on the wider platforms (now and then a row
  //    one jump up), never over the page boxes so the form stays calm;
  //  - arcs that trace a real jump between two platforms (the same physics she uses), so the coins show a route
  //    up through the level and she collects them by taking that jump.
  L.coinSpots = []
  L.arcs = []
  const pad = 10
  const blocked = box => {
    for (const r of L.solids) if (overlap({ x: box.x - 2, y: box.y - 2, w: box.w + 4, h: box.h + 4 }, r)) return true
    for (const o of L.oneways) if (!o.mover && overlap({ x: box.x - 1, y: box.y, w: box.w + 2, h: box.h + 3 }, o)) return true
    for (const d of dom) if (overlap(box, { x: d.x - pad, y: d.y - pad - 14, w: d.w + 2 * pad, h: d.h + 2 * pad + 14 })) return true
    return box.x < 2 || box.x + box.w > W - 2 || box.y < 14
  }
  // groups keep their distance from each other, so the coins are spread over the level, not bunched
  const apart = W * H > 380000 ? 56 : 42
  const crowded = box => L.coinSpots.some(c => Math.hypot(c.x - box.x, c.y - box.y) < apart)
  const add = (list, arc) => { const out = []; for (const c of list) { const box = { x: c.x, y: c.y, w: 12, h: 16 }; if (blocked(box) || crowded(box)) return null; out.push(c) } for (const c of out) { if (arc) c.arc = arc; L.coinSpots.push(c) } return out }
  // arcs first: they are the most deliberate shapes
  const ids = L.surfaces.map(s => s.id).sort(() => rng() - 0.5)
  const wantArcs = Math.max(3, Math.round(cols / 5))
  withoutMovers(L, () => {
    for (const id of ids) {
      if (L.arcs.length >= wantArcs) break
      const A = L.surfaces[id]
      if (A.dom) continue
      // across or up only: a jump down a whole row draws a long drooping trail instead of a neat arc
      const es = (L.edges.get(id) || []).filter(e => e.mode === 'jump' && !L.surfaces[e.to].dom && Math.abs(e.lx - e.tx) >= 40 && L.surfaces[e.to].y <= A.y + 4).sort(() => rng() - 0.5)
      for (const e of es) {
        const pts = trail(L, e.tx, A.y, e.lx)
        if (!pts) continue
        // a coin about every 20 px along the path, at her chest
        const spots = []
        let last = null
        for (const q of pts) if (!last || Math.hypot(q.x - last.x, q.y - last.y) >= 30) { spots.push({ x: Math.round(q.x) - 6, y: Math.round(q.y) - 8 }); last = q }
        const mid = spots.slice(1, -1).filter(c => !blocked({ x: c.x, y: c.y, w: 12, h: 16 }))
        if (mid.length < 3) continue
        const k0 = Math.floor((mid.length - Math.min(4, mid.length)) / 2)
        const arc = { from: id, to: e.to, tx: e.tx, lx: e.lx, coins: [] }
        const got = add(mid.slice(k0, k0 + Math.min(4, mid.length)), arc)
        if (got) { arc.coins = got; L.arcs.push(arc); break }
      }
    }
  })
  // rows on the platforms the arcs left alone, until the level holds a fair number of coins: spread over the
  // height (one row band at a time, top to bottom and back) so every part of the level has some
  const wantCoins = Math.max(30, Math.round(W * H / 9000))
  const bands = [[], [], [], []]
  for (const s of L.surfaces) if (!s.dom && s.r - s.l >= 34) bands[Math.min(3, Math.floor(s.y / (L.groundY / 4 + 0.01)))].push(s)
  for (const b of bands) b.sort(() => rng() - 0.5)
  const order = []
  for (let k = 0; bands.some(b => b.length); k++) { const b = bands[k % 4]; if (b.length) order.push(b.shift()) }
  for (const s of order) {
    if (L.coinSpots.length >= wantCoins) break
    if (L.arcs.some(a => a.from === s.id || a.to === s.id) && rng() < (apart < 50 ? 0.2 : 0.6)) continue
    // two or three coins, well apart; on a long platform at a random spot along it, not always the middle
    // a long platform (the ground) gets one small group per stretch of about 200 px
    const parts = Math.max(1, Math.floor((s.r - s.l) / 200)), seg = (s.r - s.l) / parts
    for (let j = 0; j < parts && L.coinSpots.length < wantCoins; j++) {
      const l = s.l + j * seg, r = l + seg
      const n = r - l >= 90 && rng() < 0.6 ? 3 : 2, gap = 30
      const hi = rng() < 0.25 ? 52 : 0
      const span = (n - 1) * gap, cx = l + span / 2 + rng() * Math.max(0, r - l - span)
      add(Array.from({ length: n }, (_, k) => ({ x: Math.round(cx + (k - (n - 1) / 2) * gap) - 6, y: s.y - 22 - hi })))
    }
  }
  // keep only row coins she can actually touch from the platform under them: by walking through, or with a
  // straight jump (arc coins are taken by their jump)
  L.coinSpots = L.coinSpots.filter(c => {
    if (c.arc) return true
    const box = { x: c.x, y: c.y, w: 12, h: 16 }
    let s = null
    for (const t of L.surfaces) if (c.x + 6 >= t.l - 1 && c.x + 6 <= t.r + 1 && t.y >= c.y + 16 && (!s || t.y < s.y)) s = t
    if (!s) return false
    const b = { x: c.x + 6 - GW / 2, y: s.y - GH, w: GW, h: GH, vx: 0, vy: 0 }
    if (overlap(b, box)) return true
    const j = { ...b, vy: -JUMPV }
    for (let f = 0; f < 90; f++) { physStep(L, j, false); if (overlap(j, box)) return true; if (j.vy === 0 && f > 2) break }
    return false
  })
}
