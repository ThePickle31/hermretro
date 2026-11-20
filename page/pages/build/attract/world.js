// The attract-mode game without any drawing: the level, the Nous Girl, the actors and one 60 Hz step. The page
// draws it (draw.js, mixed in); the tests run it headless. Methods live by subject: pilot.js (her play),
// actors.js (everything else that moves), draw.js and hud.js (pictures).
import { GH, GW, physStep, rngOf } from './physics.js'
import { buildLevel } from './level.js'
import { shortest } from './paths.js'
import { PILOT } from './pilot.js'
import { ACTORS } from './actors.js'
import { DRAW } from './draw.js'

export class World {
  /** A new game; `seed` picks the layout and everything random after it. */
  constructor(seed = 1) {
    this.seed = seed
    this.frame = 0; this.score = 0; this.coinsGot = 0; this.hearts = 3
    this.rng = rngOf(seed * 7 + 1)
    // counters the tests read: hits by what caused them, falls, coin waves (and how many came from the 90% rule)
    this.stats = { hits: {}, falls: 0, unsticks: 0, waves: 0, waves90: 0 }
  }

  /** Build the level for a W x H screen (native pixels) around the page's boxes ({ x, y, w, h, kind }). */
  build(W, H) {
    this.W = W; this.H = H
    this.L = buildLevel(W, H, this.seed)
    const L = this.L
    this.coins = L.coinSpots.map(s => ({ x: s.x, y: s.y, w: 12, h: 16, on: true, t: 0, loose: false, arc: s.arc || null }))
    for (const a of L.arcs) a.live = this.coins.filter(c => c.arc === a)
    this.lastCoin = this.frame
    this.enemies = []; this.bats = []; this.bullets = []; this.items = []; this.parts = []
    const batN = Math.max(1, Math.min(3, Math.round(W / 320)))
    for (let i = 0; i < batN; i++) this.bats.push({ x: this.rng() * W, baseY: 30 + this.rng() * Math.max(20, H * 0.5), vx: (this.rng() < 0.5 ? -1 : 1) * (0.5 + this.rng() * 0.3), t: this.rng() * 400, w: 20, h: 12, dead: 0, out: 0 })
    this.clouds = []
    const n = Math.max(3, Math.round(W / 90))
    for (let i = 0; i < n; i++) this.clouds.push(this.makeCloud(this.rng() * W, 12 + this.rng() * H * 0.45, 0.04 + this.rng() * 0.08))
    const g0 = L.surfaces.filter(s => Math.abs(s.y - L.groundY) < 1).sort((a, b) => (b.x1 - b.x0) - (a.x1 - a.x0))[0] || L.surfaces[0]
    this.spawnSurface = g0
    // the coins that count toward the next wave: those she can reach
    const reach = shortest(L, g0.id).dist
    for (const c of this.coins) { if (c.arc) { c.counts = reach.has(c.arc.from); continue } const t = this.surfaceUnder(c); c.counts = !!t && reach.has(t.id) }
    this.girl = null
    this.respawn()
  }

  // a cloud's shape (drawn by draw.js)
  makeCloud(x, y, vx) {
    const rng = this.rng, w = 26 + Math.floor(rng() * 26), h = 10 + Math.floor(rng() * 6)
    const circles = []
    for (let i = 0; i < 4; i++) circles.push({ cx: 6 + rng() * (w - 12), cy: h - 4 - rng() * (h - 8), r: 4 + rng() * (h * 0.55) })
    circles.push({ cx: w / 2, cy: h - 5, r: h * 0.5 })
    return { x, y, vx, circles, w, h, c: null }
  }

  surfaceUnder(c) { let best = null; for (const t of this.L.surfaces) if (c.x + 6 >= t.x0 - 2 && c.x + 6 <= t.x1 + 2 && t.y >= c.y + 16 && t.y - c.y - 16 <= 70 && (!best || t.y < best.y)) best = t; return best }

  coinsLeft() { let n = 0, all = 0; for (const c of this.coins) if (!c.loose && c.counts) { all++; if (c.on) n++ } return { n, all } }

  // Coins come back all together, only once she has collected 90% of them (or after a long spell with no coin at
  // all, so a coin she somehow can't reach never stalls the level). ? blocks refill with them.
  coinWave() {
    let k = 0
    for (const c of this.coins) if (!c.loose && !c.on) { c.on = false; c.t = 8 + (k++ % 40) * 3; c.pending = true; c.skipUntil = 0 }
    for (const b of this.L.blocks) { b.active = true; b.skipUntil = 0 }
    this.stats.waves++
    this.lastCoin = this.frame
  }

  respawn() {
    const s = this.spawnSurface
    this.girl = { seen: this.girl && this.girl.seen || new Map(), x: (s.l + s.r) / 2 - GW / 2, y: s.y - GH, w: GW, h: GH, vx: 0, vy: 0, face: 1, ground: null, inv: 90, stun: 0, power: 0, exec: null, goal: null, goalT: 0, wait: 0, anim: 0, alive: true, through: 0, idle: 0 }
  }

  step() {
    this.frame++
    const L = this.L
    for (const m of L.movers) { const nx = m.x + m.vx; if (nx < m.x0 || nx > m.x1) m.vx = -m.vx; m.dx = m.vx; m.x += m.vx }
    for (const c of this.clouds) { c.x += c.vx; if (c.x > this.W + 4) c.x = -c.w - 4 }
    this.updateGirl()
    this.updateEnemies()
    this.updateItems()
    for (const b of L.blocks) if (b.bump > 0) b.bump--
    for (const c of this.coins) {
      if (!c.on) { if (c.pending && --c.t <= 0) { c.on = true; c.pending = false; this.sparkle(c.x + 2, c.y + 4) } continue }
      if (c.loose) {
        if (!c.rest) { const r = physStep(L, c, false); if (r.ground) { c.rest = true; c.vx = 0 } c.vx *= 0.96 }
        if (--c.life <= 0 || c.y > this.H) c.on = false
      }
    }
    this.coins = this.coins.filter(c => c.on || !c.loose)
    this.parts = this.parts.filter(pt => { pt.t++; pt.x += pt.vx || 0; pt.y += pt.vy || 0; if (pt.g) pt.vy += pt.g; return pt.t < pt.life })
  }
}

Object.assign(World.prototype, PILOT, ACTORS, DRAW)
