// The attract-mode level: one fixed screen built around the page's boxes. Ground with water pits and moving platforms,
// pipes, stone stairs, a lattice of planks and brick rows up to the top (rows three tiles apart, offset so there is
// always a diagonal way up), open air around the headline, cannons, the goal flag, coins and decorations.
import { GH, T, indexColliders, rngOf } from './physics.js'
import { buildEdges, buildSurfaces, connect } from './paths.js'
import { placeCoins } from './coins.js'

export function buildLevel(W, H, dom, seed) {
  const rng = rngOf(seed)
  const cols = Math.ceil(W / T), rows = Math.max(4, Math.floor(H / T)), oy = H - rows * T
  const grid = new Uint8Array(cols * rows)
  const at = (c, r) => (c < 0 || c >= cols || r < 0 || r >= rows) ? 0 : grid[r * cols + c]
  const set = (c, r, v) => { if (c >= 0 && c < cols && r >= 0 && r < rows) grid[r * cols + c] = v }
  const cellY = r => oy + r * T
  // the page's boxes, and a no-build zone around them
  const ex = dom.length ? dom.reduce((u, d) => ({ x0: Math.min(u.x0, d.x), y0: Math.min(u.y0, d.y), x1: Math.max(u.x1, d.x + d.w), y1: Math.max(u.y1, d.y + d.h) }), { x0: 1e9, y0: 1e9, x1: -1e9, y1: -1e9 }) : null
  const free = (c, r) => {
    if (r < 1) return false
    if (!ex) return true
    const x0 = c * T, y0 = cellY(r)
    // open air over the page (she stands on the title and jumps from it); below it, room to stand on what is there
    return !(x0 + T > ex.x0 - 10 && x0 < ex.x1 + 10 && y0 + T > ex.y0 - (GH + 26) && y0 < ex.y1 + GH + 6)
  }
  const gTop = rows - 2
  for (let c = 0; c < cols; c++) { set(c, gTop, 1); set(c, gTop + 1, 2) }
  // the page's columns (nothing is dug or stacked under the page)
  const exL = ex ? Math.floor((ex.x0 - 12) / T) : Math.floor(cols * 0.45), exR = ex ? Math.ceil((ex.x1 + 12) / T) : Math.ceil(cols * 0.55)
  // under the page only when there is room above the ground to jump a pit
  const roomy = ex && ex.y1 < cellY(gTop) - 96
  const underPage = c => !roomy && c >= exL - 1 && c <= exR
  const taken = new Uint8Array(cols) // ground columns already used by a pit, pipe or stairs
  const claim = (c0, c1) => { for (let c = Math.max(0, c0); c <= Math.min(cols - 1, c1); c++) taken[c] = 1 }
  const open = (c0, c1) => { for (let c = c0; c <= c1; c++) if (c < 2 || c > cols - 3 || taken[c] || underPage(c)) return false; return true }
  // pipes: one at each end, more along a wide level
  const pipes = []
  const pipe = (c, dir, h) => {
    for (let k = 1; k <= h; k++) { set(c, gTop - k, 6); set(c + 1, gTop - k, 6) }
    pipes.push({ c, dir, h, x: c * T, y: cellY(gTop - h), timer: 60 + Math.floor(rng() * 300) })
    claim(c - 1, c + 2)
  }
  if (cols >= 10 && rows >= 6) {
    pipe(1, 1, 2); claim(0, 4)
    pipe(cols - 3, -1, 2); claim(cols - 5, cols - 1)
    const extra = Math.floor(cols / 26)
    for (let i = 0; i < extra * 3 && pipes.length < 2 + extra; i++) {
      const c = 4 + Math.floor(rng() * (cols - 8))
      if (open(c - 1, c + 2)) pipe(c, rng() < 0.5 ? -1 : 1, 2)
    }
  }
  // pits of water: about one every 16 columns, never under the page
  const pits = []
  if (cols >= 14) {
    const want = Math.max(1, Math.round(cols / 18))
    for (let i = 0; i < want * 6 && pits.length < want; i++) {
      const w = 2, c0 = 3 + Math.floor(rng() * (cols - 6 - w))
      if (!open(c0 - 2, c0 + w + 1)) continue
      // never under the page, even when it is high: the moving platform would ride under a low ceiling
      if (ex && (c0 + w + 2) * T > ex.x0 - 12 && (c0 - 3) * T < ex.x1 + 12) continue
      for (let c = c0; c < c0 + w; c++) { set(c, gTop, 0); set(c, gTop + 1, 0) }
      pits.push({ c0, c1: c0 + w - 1 }); claim(c0 - 2, c0 + w + 1)
    }
  }
  // stone staircases on the ground
  if (rows >= 9) {
    const want = Math.floor(cols / 22)
    for (let i = 0, made = 0; i < want * 6 && made < want; i++) {
      const h = 2 + Math.floor(rng() * 2), c0 = 3 + Math.floor(rng() * (cols - 6 - 2 * h))
      if (!open(c0 - 1, c0 + 2 * h)) continue
      for (let k = 0; k < h; k++) for (let j = 0; j <= k; j++) { set(c0 + k, gTop - 1 - j, 8); set(c0 + 2 * h - 1 - k, gTop - 1 - j, 8) }
      claim(c0 - 1, c0 + 2 * h); made++
    }
  }
  // stone towers on tall levels
  if (rows >= 18) {
    const want = Math.floor(cols / 30)
    for (let i = 0, made = 0; i < want * 8 && made < want; i++) {
      const h = 4 + Math.floor(rng() * Math.min(6, rows / 4)), c0 = 4 + Math.floor(rng() * (cols - 9))
      let ok = open(c0 - 1, c0 + 2)
      for (let k = 1; k <= h + 2 && ok; k++) for (let j = c0 - 1; j <= c0 + 2; j++) if (!free(j, gTop - k) || at(j, gTop - k) !== 0) ok = false
      if (!ok) continue
      for (let k = 1; k <= h; k++) { set(c0, gTop - k, 8); set(c0 + 1, gTop - k, 8) }
      set(c0 - 1, gTop - h, 5); set(c0 + 2, gTop - h, 5)
      claim(c0 - 1, c0 + 2); made++
    }
  }
  // The sky: a designed lattice of platforms. Rows sit three tiles apart (a single jump), from just above the
  // ground to the top of the screen; on each row, platforms alternate with gaps and every row is shifted half a
  // step from the one below, so there is always a diagonal way up. Over the page only the top row is built: a
  // bridge of planks above the title joining the two sides.
  const blocks = []
  const clear = (c, r, h = 3) => { for (let k = 0; k <= h; k++) if (at(c, r + k) !== 0 && k > 0) return false; return at(c, r) === 0 }
  // planks may sit closer above the page than solid tiles: they are thin and she can jump up through them
  const freeLedge = (c, r) => {
    if (r < 1) return false
    if (!ex) return true
    const x0 = c * T, y0 = cellY(r)
    // keep a pocket of open air over the title: she can stand on it and jump, and nothing crowds the headline
    return !(x0 + T > ex.x0 - 12 && x0 < ex.x1 + 12 && y0 + 8 > ex.y0 - (GH + 26) && y0 < ex.y1 + GH + 6)
  }
  {
    const latRows = []
    for (let r = gTop - 3; r >= 1; r -= 3) latRows.push(r)
    if (latRows[latRows.length - 1] > 1) latRows.push(1)
    latRows.forEach((r, i) => {
      const top = i === latRows.length - 1
      let c = (i % 2 ? 0 : 3) + Math.floor(rng() * 2)
      let lastKind = ''
      while (c < cols) {
        const w = top ? 3 + Math.floor(rng() * 3) : 3 + Math.floor(rng() * 2)
        const cells = []
        for (let k = c; k < Math.min(cols, c + w); k++) cells.push(k)
        const head = k => at(k, r - 1) === 0 && (r < 2 || at(k, r - 2) === 0)
        const okL = cells.filter(k => freeLedge(k, r) && at(k, r) === 0 && head(k) && clear(k, r, 2))
        const okS = cells.filter(k => free(k, r) && at(k, r) === 0 && head(k) && clear(k, r, 2))
        // pick a kind: planks most often; brick rows with ? blocks; a grass island; a line of ? blocks
        let kind = rng()
        // the top row and the row just above the ground are planks only: she jumps up through them, so a solid
        // row can never box in the ground or a pipe
        if (top || i === 0) kind = 0
        // no grass islands: a block of ground floating in the sky looked out of place
        let kindName = kind < 0.52 ? 'ledge' : kind < 0.84 ? 'brick' : 'qline'
        if (kindName === lastKind && kindName !== 'ledge') kindName = 'ledge'
        if (kindName === 'island' && (r > gTop - 4 || okS.length < 3 || okS.some(k => !free(k, r + 1) || at(k, r + 1) !== 0))) kindName = 'ledge'
        if ((kindName === 'brick' || kindName === 'qline') && okS.length < 3) kindName = 'ledge'
        let made = false
        if (kindName === 'ledge') { for (const k of okL) { set(k, r, 5); made = true } } else if (kindName === 'brick') {
          for (const k of okS) set(k, r, 3)
          const q = okS[1 + Math.floor(rng() * (okS.length - 2))]
          set(q, r, 4); made = true
        } else if (kindName === 'island') { for (const k of okS) { set(k, r, 1); set(k, r + 1, 2) } made = true } else {
          for (let j = 0; j < okS.length; j += 2) set(okS[j], r, 4)
          made = true
        }
        if (made) lastKind = kindName
        // gaps of two or three tiles: a short hop across, and room to jump up from the row below
        c += w + (made ? 2 + Math.floor(rng() * 2) : 1)
      }
    })
  }
  // bridge ledges beside the composer and the title so the page is reachable from the sides
  for (const d of dom) {
    if (d.kind !== 'composer' && d.kind !== 'title' && d.kind !== 'panel') continue
    const r = Math.round((d.y + 30 - oy) / T)
    if (r < 2 || r >= gTop - 1) continue
    for (const side of [-1, 1]) {
      const c = side < 0 ? Math.floor((d.x - 14) / T) : Math.ceil((d.x + d.w + 14) / T) - 1
      for (let k = 0; k < 2; k++) { const cc = c + side * k; if (free(cc, r) && at(cc, r) === 0 && at(cc, r - 1) === 0) set(cc, r, 5) }
    }
  }
  // cannons near both edges, aimed at the middle
  const cannons = []
  if (W >= 300 && rows >= 8) {
    for (const side of [1, -1]) {
      const span = Math.max(4, Math.floor(cols / 4))
      const cands = []
      for (let r = 3; r < gTop - 3; r++) for (let k = 0; k < span; k++) {
        const c = side > 0 ? cols - 1 - k : k
        if ((at(c, r) === 5 || at(c, r) === 3) && at(c, r - 1) === 0 && at(c - side, r - 1) === 0 && free(c, r - 1)) cands.push([c, r])
      }
      if (!cands.length) continue
      const [c, r] = cands[Math.floor(rng() * cands.length)]
      set(c, r - 1, 7)
      cannons.push({ c, r: r - 1, x: c * T, y: cellY(r - 1), timer: 100 + Math.floor(rng() * 200), dir: -side })
    }
  }
  // the goal flag near the right end
  let flag = null
  if (cols >= 18) { for (let c = cols - 5; c > cols - 11; c--) if (at(c, gTop) === 1 && at(c, gTop - 1) === 0 && at(c + 1, gTop - 1) === 0 && !underPage(c)) { flag = { x: c * T + 11, y: cellY(gTop), h: Math.min(5, gTop - 2) * T }; break } }
  // the moving platforms ride in their own lane: nothing static in their row (or the row above) along the track,
  // so the platform never slides into a plank and she never stands half on one, half on the other
  for (const p of pits) {
    const r = gTop - 3, x0 = p.c0 * T - 40, x1 = (p.c1 + 1) * T - 8 + 48
    for (let c = Math.floor(x0 / T) - 1; c <= Math.ceil(x1 / T); c++) for (const rr of [r, r - 1]) if (at(c, rr) === 5) set(c, rr, 0)
  }
  // colliders
  const solids = [], oneways = []
  for (let r = 0; r < rows; r++) {
    let c = 0
    while (c < cols) {
      const v = at(c, r)
      if (v === 1 || v === 2 || v === 3 || v === 6 || v === 7 || v === 8) {
        let e = c
        while (e + 1 < cols && [1, 2, 3, 6, 7, 8].includes(at(e + 1, r))) e++
        solids.push({ x: c * T, y: cellY(r), w: (e - c + 1) * T, h: T, kind: 'tile' })
        c = e + 1
      } else if (v === 4) {
        const blk = { c, r, x: c * T, y: cellY(r), active: true, bump: 0, reset: 0 }
        blocks.push(blk)
        solids.push({ x: blk.x, y: blk.y, w: T, h: T, kind: 'block', ref: blk })
        c++
      } else if (v === 5) {
        let e = c
        while (e + 1 < cols && at(e + 1, r) === 5) e++
        oneways.push({ x: c * T, y: cellY(r), w: (e - c + 1) * T, h: 8, kind: 'ledge' })
        c = e + 1
      } else c++
    }
  }
  for (const d of dom) solids.push({ x: d.x, y: d.y, w: d.w, h: d.h, kind: 'dom', name: d.kind })
  // moving platforms over the pits
  const movers = []
  for (const p of pits) {
    const y = cellY(gTop - 3)
    if (y < T * 2) continue
    const x0 = p.c0 * T - 40, x1 = (p.c1 + 1) * T - 8
    let clash = false
    for (const d of dom) if (y > d.y - 30 && y < d.y + d.h + GH + 60 && x1 + 48 > d.x && x0 < d.x + d.w) clash = true
    if (clash) continue
    const m = { x: x0, y, w: 48, h: 8, x0, x1, vx: 0.5, dx: 0, dy: 0, mover: true, kind: 'mover' }
    movers.push(m); oneways.push(m)
  }
  // a page too low to jump under: bugs on the ground turn back at its edges
  const tunnel = ex && !roomy ? { x0: ex.x0 - 6, x1: ex.x1 + 6 } : null
  const L = { W, H, cols, rows, oy, gTop, grid, at, solids, oneways, surfaces: [], edges: new Map(), blocks, pipes, pits, movers, cannons, flag, dom, rng, groundY: cellY(gTop), tunnel }
  indexColliders(L)
  buildSurfaces(L)
  buildEdges(L)
  L.steps = connect(L, free)
  placeCoins(L, dom, rng)
  // decorations on the ground
  L.decos = []
  for (let c = 0; c < cols; c++) {
    if (at(c, gTop) !== 1 || at(c, gTop - 1) !== 0) continue
    const v = rng()
    if (v < 0.22) L.decos.push({ type: 'bush', x: c * T, y: L.groundY })
    else if (v < 0.36) L.decos.push({ type: 'flower', x: c * T + 4, y: L.groundY, ph: Math.floor(rng() * 60) })
    else if (v < 0.42) L.decos.push({ type: 'tree', x: c * T, y: L.groundY })
  }
  return L
}
