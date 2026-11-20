// Drawing the world on a canvas at native pixels (the page scales it up x2 with pixelated scaling): the sky, hills
// and static tiles prerendered once per layout, then each frame the moving parts, the sprites and the particles.
// Mixed into World (world.js); the HUD is in hud.js.
import { GH, GW, T } from './physics.js'
import { PAL } from './palettes.js'
import { canvas, makeSprites } from './sprites.js'
import { drawHud, smallText } from './hud.js'

const hexRgb = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]

export const DRAW = {
  /** Draw on `cv` (a canvas element), with the sky named `name` ('day' or 'night'). */
  attach(cv, name) {
    this.cv = cv; this.ctx = cv.getContext('2d')
    this.setPalette(name)
  },

  setPalette(name) {
    this.palName = name; this.p = PAL[name]; this.spr = makeSprites(name)
    for (const c of this.clouds || []) c.c = null
    if (this.L && this.cv) this.prerender()
  },

  // a cloud: two tones, the lower edge in the darker one
  cloudCanvas(cl) {
    const { w, h, circles } = cl
    const c = canvas(w, h + 2), x2 = c.getContext('2d')
    for (let py = 0; py < h + 2; py++) for (let px = 0; px < w; px++) {
      const inside = circles.some(k => (px - k.cx) ** 2 + (py - k.cy) ** 2 <= k.r * k.r) && py <= h
      if (!inside) continue
      const lower = !circles.some(k => (px - k.cx) ** 2 + (py - 2 - k.cy) ** 2 <= k.r * k.r)
      x2.fillStyle = (lower || py > h - 3) ? this.p.cloud[1] : this.p.cloud[0]
      x2.fillRect(px, py, 1, 1)
    }
    return c
  },

  prerender() {
    const L = this.L, p = this.p, W = this.W, H = this.H
    this.cv.width = W; this.cv.height = H
    const bg = this.bg = canvas(W, H), b = bg.getContext('2d')
    {
      const n = p.sky.length, img = b.createImageData(W, H), rgb = p.sky.map(hexRgb)
      for (let y = 0; y < H; y++) {
        const f = y / H * n, i = Math.min(n - 1, Math.floor(f)), frac = f - i
        for (let x = 0; x < W; x++) {
          let ci = i
          if (i < n - 1 && frac > 0.78) ci = ((x + y) % 2 === 0) ? i + 1 : i
          if (i < n - 1 && frac > 0.9) ci = i + 1 - (((x + y * 3) % 4 === 0) ? 1 : 0)
          const o = (y * W + x) * 4, c = rgb[ci]
          img.data[o] = c[0]; img.data[o + 1] = c[1]; img.data[o + 2] = c[2]; img.data[o + 3] = 255
        }
      }
      b.putImageData(img, 0, 0)
      if (p.dither) for (let y = 0; y < H * 0.6; y += 4) for (let x = (y / 4) % 2 * 2; x < W; x += 4) { b.fillStyle = p.dither; b.fillRect(x, y, 1, 1) }
      if (p.moon) { const mx = Math.round(W * 0.84), my = Math.round(Math.min(40, H * 0.14)); b.fillStyle = p.moon; for (let y = -9; y <= 9; y++) for (let x = -9; x <= 9; x++) if (x * x + y * y <= 81 && (x + 4) ** 2 + (y - 2) ** 2 > 40) b.fillRect(mx + x, my + y, 1, 1) }
    }
    this.stars = []
    // stars hold still: most are dim, a few brighter; one in eight slowly brightens now and then, and only a
    // rare bright one shows a small glint
    if (p.stars) { const n = Math.round(W * H / 1500); for (let i = 0; i < n; i++) { const r = this.rng(); this.stars.push({ x: Math.floor(this.rng() * W), y: Math.floor(this.rng() * H * 0.6), lvl: r < 0.7 ? 0 : 1, tw: this.rng() < 0.12, per: 420 + Math.floor(this.rng() * 480), ph: Math.floor(this.rng() * 900), glint: r > 0.96 }) } }
    // hills
    const gy = L.groundY
    const hill = (amp, base, f1, f2, ph, col) => { b.fillStyle = col; for (let x = 0; x < W; x++) { const h = Math.round(base + amp * (0.5 + 0.5 * Math.sin(x * f1 + ph)) + amp * 0.35 * Math.sin(x * f2 + ph * 2)); b.fillRect(x, gy - h, 1, h) } }
    hill(Math.min(40, H * 0.16), 18, 0.017, 0.053, 1.3, p.hill[0])
    hill(Math.min(22, H * 0.09), 6, 0.031, 0.081, 4.1, p.hill[1])
    // tiles
    const tl = this.tiles = canvas(W, H), t = tl.getContext('2d')
    const isSolidTop = v => v === 1 || v === 2 || v === 3 || v === 4 || v === 6 || v === 7 || v === 8
    for (const d of L.decos) if (d.type === 'tree') this.drawTree(t, d.x, d.y)
    for (let r = 0; r < L.rows; r++) for (let c = 0; c < L.cols; c++) {
      const v = L.at(c, r), x = c * T, y = L.oy + r * T
      if (v === 1) this.drawGround(t, x, y, !isSolidTop(L.at(c, r - 1)), L.at(c - 1, r) === 0, L.at(c + 1, r) === 0)
      else if (v === 2) this.drawDirt(t, x, y, L.at(c - 1, r) === 0, L.at(c + 1, r) === 0, r < L.gTop && L.at(c, r + 1) === 0)
      else if (v === 3) this.drawBrick(t, x, y)
      else if (v === 5) this.drawLedge(t, x, y, L.at(c - 1, r) !== 5, L.at(c + 1, r) !== 5)
      else if (v === 8) this.drawStone(t, x, y)
    }
    for (const pp of L.pipes) this.drawPipe(t, pp.x, pp.y, pp.h)
    for (const cn of L.cannons) this.drawCannon(t, cn.x, cn.y, cn.dir)
    if (L.flag) this.drawPole(t, L.flag)
    for (const d of L.decos) if (d.type === 'bush') this.drawBush(t, d.x, d.y)
  },

  render() {
    const x = this.ctx, L = this.L, p = this.p, sp = this.spr, f = this.frame
    x.imageSmoothingEnabled = false
    x.clearRect(0, 0, this.W, this.H)
    x.drawImage(this.bg, 0, 0)
    for (const s of this.stars) {
      const ph = s.tw ? (f + s.ph) % s.per : 999, up = ph < 48
      x.fillStyle = up ? (ph > 16 && ph < 32 ? '#ffffff' : p.cloud[0]) : (s.lvl ? p.cloud[1] : p.sky[Math.min(p.sky.length - 1, 1)])
      x.fillRect(s.x, s.y, 1, 1)
      if (up && s.glint && ph > 20 && ph < 28) { x.fillStyle = p.cloud[1]; x.fillRect(s.x - 1, s.y, 1, 1); x.fillRect(s.x + 1, s.y, 1, 1); x.fillRect(s.x, s.y - 1, 1, 1); x.fillRect(s.x, s.y + 1, 1, 1) }
    }
    for (const c of this.clouds) x.drawImage(c.c || (c.c = this.cloudCanvas(c)), Math.round(c.x), Math.round(c.y))
    // emerging enemies sit behind the pipes
    for (const e of this.enemies) if (e.state === 'emerge' || e.state === 'leave') this.drawEnemy(x, e)
    x.drawImage(this.tiles, 0, 0)
    if (L.flag) {
      const fx = L.flag.x + 2, fy = L.flag.y - L.flag.h + 2
      for (let i = 0; i < 24; i++) { const wv = Math.round(Math.sin((f * 0.12) - i * 0.5) * 1.5 * (i / 18)); this.px(x, i < 1 ? p.hud[0] : p.block[0], fx + i, fy + wv, 1, 18 - Math.floor(i / 2)); this.px(x, p.hud[0], fx + i, fy + wv + 18 - Math.floor(i / 2), 1, 1); this.px(x, p.hud[0], fx + i, fy + wv - 1, 1, 1) }
      x.drawImage(this.spr.q, fx + 5, fy + 2)
    }
    // movers
    for (const m of L.movers) { this.drawLedgeLive(x, Math.round(m.x), m.y, m.w); x.fillStyle = p.ledge[2]; for (let i = m.x0; i < m.x1 + m.w; i += 6) x.fillRect(Math.round(i), m.y + 12, 2, 1) }
    // ? blocks
    for (const b of L.blocks) {
      const by = b.y - (b.bump > 0 ? Math.round(Math.sin((8 - b.bump) / 8 * Math.PI) * 4) : 0)
      if (b.active) {
        this.px(x, p.block[3], b.x, by, T, T); this.px(x, p.block[0], b.x + 1, by + 1, T - 2, T - 2)
        this.px(x, p.block[2], b.x + 1, by + 1, T - 2, 1); this.px(x, p.block[2], b.x + 1, by + 1, 1, T - 2)
        this.px(x, p.block[1], b.x + 1, by + T - 2, T - 2, 1); this.px(x, p.block[1], b.x + T - 2, by + 1, 1, T - 2)
        for (const [a, c] of [[3, 3], [T - 4, 3], [3, T - 4], [T - 4, T - 4]]) this.px(x, p.block[3], b.x + a, by + c, 1, 1)
        const shimmer = (f >> 4) % 6 === 0
        x.drawImage(shimmer ? sp.qHi : sp.q, b.x + 7, by + 5)
      } else {
        this.px(x, p.used[1], b.x, by, T, T); this.px(x, p.used[0], b.x + 1, by + 1, T - 2, T - 2)
        for (const [a, c] of [[4, 4], [T - 5, 4], [4, T - 5], [T - 5, T - 5]]) this.px(x, p.used[1], b.x + a, by + c, 2, 2)
      }
    }
    // water in the pits
    for (const pit of L.pits) {
      const x0 = pit.c0 * T, w = (pit.c1 - pit.c0 + 1) * T, y0 = L.groundY + 14
      this.px(x, p.water[0], x0, y0, w, this.H - y0)
      for (let i = 0; i < w; i++) if (((i + (f >> 3)) % 6) < 2) this.px(x, p.water[1], x0 + i, y0, 1, 1)
      for (let i = 0; i < w; i += 1) if (((i * 3 + (f >> 4)) % 11) === 0) this.px(x, p.water[1], x0 + i, y0 + 4, 2, 1)
    }
    // flowers
    for (const d of L.decos) if (d.type === 'flower') { const sway = ((f + d.ph) >> 5) & 1; this.px(x, p.deco[1], d.x + 4, d.y - 6, 1, 6); this.px(x, p.deco[1], d.x + 5, d.y - 3, 2, 1); this.px(x, p.deco[2], d.x + 2 + sway, d.y - 10, 5, 4); this.px(x, p.deco[2], d.x + 3 + sway, d.y - 11, 3, 6); this.px(x, p.deco[3], d.x + 4 + sway, d.y - 9, 1, 2) }
    // items
    for (const it of this.items) { const flap = (f >> 3) & 1; x.drawImage(sp.wing[0], Math.round(it.x), Math.round(it.y) - flap) }
    // coins
    for (const c of this.coins) {
      if (!c.on) continue
      if (c.loose && c.life < 120 && (f & 4)) continue
      const fr = [0, 0, 1, 2, 3][((f + (c.x * 7 + c.y * 3)) >> 3) % 5]
      x.drawImage(sp.coin[fr], Math.round(c.x), Math.round(c.y))
    }
    // enemies
    for (const e of this.enemies) {
      if (e.state === 'emerge' || e.state === 'leave') continue
      this.drawEnemy(x, e)
    }
    for (const b of this.bats) { if (b.dead) continue; const y = b.baseY + Math.sin(b.t * 0.045) * 20; x.drawImage(sp.bat[(b.t >> 3) % 4][b.vx > 0 ? 0 : 1], Math.round(b.x), Math.round(y)) }
    for (const b of this.bullets) x.drawImage(sp.bullet[b.vx < 0 ? 0 : 1], Math.round(b.x), Math.round(b.y))
    // the girl
    const g = this.girl
    if (!(g.inv > 0 && (f & 4) && g.power <= 0)) {
      const inv = g.stun > 0 || (g.power > 0 && (f >> 2) % 2)
      const S = inv ? sp.girl.inv : sp.girl
      let fr
      if (g.stun > 0) fr = S.hurt
      else if (!g.ground) fr = g.vy < -1.6 ? S.jumpUp : g.vy < 0.9 ? S.jumpTop : S.fall[(f >> 3) & 1]
      else if (g.cheerT > 0) fr = S.cheer[(g.cheerT >> 3) & 1]
      else if (g.landT > 0) fr = S.land
      else if (g.skidT > 0 && g.vx !== 0) fr = S.skid
      else if (g.vx !== 0) fr = S.run[Math.floor((g.dist || 0) / 3) % 8]
      else fr = g.blinkT < 8 ? S.blink : S.idle[(f >> 4) % 4]
      const face = g.spin > 0 && !g.ground ? ((g.spin >> 2) % 2 ? -g.face : g.face) : g.face
      if (g.spin > 0 && !g.stun && !g.ground) fr = S.jumpTop
      const img = fr[face > 0 ? 0 : 1]
      x.drawImage(img, Math.round(g.x + GW / 2 - img.width / 2), Math.round(g.y + GH - img.height + 1))
    }
    // particles
    for (const pt of this.parts) {
      if (pt.t < 0) continue
      if (pt.type === 'spark') x.drawImage(sp.spark[Math.min(2, Math.floor(pt.t / 6))], Math.round(pt.x), Math.round(pt.y))
      else if (pt.type === 'text') x.drawImage(smallText(pt.s, p.hud[1]), Math.round(pt.x), Math.round(pt.y))
      else if (pt.type === 'dust') { x.fillStyle = p.cloud[0]; const s = pt.t < 7 ? 2 : 1; x.fillRect(Math.round(pt.x), Math.round(pt.y) - s, s, s) } else if (pt.type === 'coinpop') x.drawImage(sp.coin[(pt.t >> 2) % 4], Math.round(pt.x), Math.round(pt.y))
      else if (pt.type === 'splash') { x.fillStyle = p.water[1]; for (const k of [-6, -2, 2, 6]) x.fillRect(Math.round(pt.x + k * pt.t * 0.15), Math.round(pt.y - 10 * Math.sin(pt.t / pt.life * Math.PI) * (1 - Math.abs(k) / 10)), 1, 2) }
    }
    drawHud(this, x)
  },

  px(x, c, X, Y, w = 1, h = 1) { x.fillStyle = c; x.fillRect(X, Y, w, h) },

  drawGround(t, x, y, top, openL, openR) {
    const p = this.p
    this.drawDirt(t, x, y, openL, openR)
    if (!top) return
    this.px(t, p.grass[0], x, y, T, 1); this.px(t, p.grass[1], x, y + 1, T, 3)
    for (let i = 0; i < T; i++) { const dip = (i * 7 + x) % 5 < 2 ? 1 : 0; this.px(t, p.grass[1], x + i, y + 4, 1, dip + 1); this.px(t, p.grass[2], x + i, y + 5 + dip, 1, 1) }
    for (let i = 1; i < T; i += 4) this.px(t, p.grass[0], x + i, y + 2, 1, 1)
    if (openL) this.px(t, p.grass[2], x, y, 1, 6)
    if (openR) this.px(t, p.grass[2], x + T - 1, y, 1, 6)
  },

  drawDirt(t, x, y, openL, openR, openB) {
    const p = this.p
    this.px(t, p.dirt[0], x, y, T, T)
    if (openB) { this.px(t, p.dirt[2], x, y + T - 2, T, 2); for (let i = 1; i < T; i += 3) this.px(t, p.dirt[2], x + i, y + T, 1, 1 + (i % 2)) }
    const specks = [[3, 4], [13, 3], [20, 10], [7, 13], [16, 18], [4, 20], [10, 8], [20, 21], [12, 22]]
    for (const [a, b] of specks) { this.px(t, p.dirt[1], x + a, y + b, 2, 1); this.px(t, p.dirt[2], x + a, y + b + 1, 1, 1) }
    if (openL) this.px(t, p.dirt[2], x, y, 1, T)
    if (openR) this.px(t, p.dirt[2], x + T - 1, y, 1, T)
  },

  drawBrick(t, x, y) {
    const p = this.p
    this.px(t, p.brick[0], x, y, T, T)
    // two courses of bricks, 12 px wide, staggered
    this.px(t, p.brick[1], x, y + 11, T, 1); this.px(t, p.brick[1], x, y + 23, T, 1)
    this.px(t, p.brick[1], x + 11, y, 1, 11); this.px(t, p.brick[1], x + 23, y, 1, 11)
    this.px(t, p.brick[1], x + 5, y + 12, 1, 11); this.px(t, p.brick[1], x + 17, y + 12, 1, 11)
    this.px(t, p.brick[2], x, y, 11, 1); this.px(t, p.brick[2], x + 12, y, 11, 1)
    this.px(t, p.brick[2], x, y + 12, 5, 1); this.px(t, p.brick[2], x + 6, y + 12, 11, 1); this.px(t, p.brick[2], x + 18, y + 12, 5, 1)
  },

  drawLedge(t, x, y, capL, capR) {
    const p = this.p
    // a plank 8 px thick with bolts, and brackets under the ends
    this.px(t, p.ledge[0], x, y, T, 1); this.px(t, p.ledge[1], x, y + 1, T, 6); this.px(t, p.ledge[2], x, y + 7, T, 1)
    this.px(t, p.ledge[0], x, y + 2, T, 1)
    for (let i = 3; i < T; i += 8) { this.px(t, p.ledge[2], x + i, y + 4, 2, 2); this.px(t, p.ledge[0], x + i, y + 4, 1, 1) }
    if (capL) { this.px(t, p.ledge[2], x, y, 1, 8); this.px(t, p.ledge[2], x + 3, y + 8, 3, 4); this.px(t, p.ledge[2], x + 4, y + 12, 1, 2) }
    if (capR) { this.px(t, p.ledge[2], x + T - 1, y, 1, 8); this.px(t, p.ledge[2], x + T - 6, y + 8, 3, 4); this.px(t, p.ledge[2], x + T - 5, y + 12, 1, 2) }
  },

  drawPipe(t, x, y, h = 2) {
    const p = this.p, w = 2 * T, cap = 12, body = h * T - cap
    this.px(t, p.pipe[3], x, y, w, cap); this.px(t, p.pipe[0], x + 1, y + 1, w - 2, cap - 2); this.px(t, p.pipe[2], x + 5, y + 1, 4, cap - 2); this.px(t, p.pipe[1], x + w - 9, y + 1, 7, cap - 2)
    this.px(t, p.pipe[3], x + 3, y + cap, w - 6, body); this.px(t, p.pipe[0], x + 4, y + cap, w - 8, body); this.px(t, p.pipe[2], x + 8, y + cap, 4, body); this.px(t, p.pipe[1], x + w - 13, y + cap, 7, body)
  },

  drawCannon(t, x, y, dir = -1) {
    t.drawImage(this.spr.cannon[dir < 0 ? 0 : 1], dir < 0 ? x - 2 : x, y)
  },

  drawStone(t, x, y) {
    const p = this.p
    this.px(t, p.dirt[2], x, y, T, T); this.px(t, p.ledge[1], x + 1, y + 1, T - 2, T - 2)
    this.px(t, p.ledge[0], x + 1, y + 1, T - 2, 1); this.px(t, p.ledge[0], x + 1, y + 1, 1, T - 2)
    this.px(t, p.ledge[2], x + 2, y + T - 2, T - 3, 1); this.px(t, p.ledge[2], x + T - 2, y + 2, 1, T - 3)
    this.px(t, p.ledge[0], x + 5, y + 5, 3, 3); this.px(t, p.ledge[2], x + 15, y + 14, 3, 3)
  },

  drawPole(t, f) {
    const p = this.p
    this.px(t, p.dirt[2], f.x - 4, f.y - 8, 10, 8); this.px(t, p.ledge[1], f.x - 3, f.y - 7, 8, 6)
    this.px(t, p.hud[0], f.x, f.y - f.h, 2, f.h - 8); this.px(t, p.ledge[0], f.x, f.y - f.h, 1, f.h - 8)
    this.px(t, p.hud[0], f.x - 2, f.y - f.h - 5, 6, 6); this.px(t, p.block[0], f.x - 1, f.y - f.h - 4, 4, 4); this.px(t, p.block[2], f.x - 1, f.y - f.h - 4, 1, 1)
  },

  drawBush(t, x, y) {
    const p = this.p
    const shape = ['......DDDDD.............', '...DDDLLLDDD....DDD.....', '..DLLLLDDDDDD..DLLLDD...', '.DLLLDDDDDDDDDDLLDDDDDD.', 'DLLDDDDDDDDDDDDDDDDDDDDD', 'DDDDDDDDDDDDDDDDDDDDDDDD', 'DDDDDDDDDDDDDDDDDDDDDDDD']
    shape.forEach((row, i) => { for (let j = 0; j < 24; j++) { const ch = row[j]; if (ch === '.') continue; this.px(t, ch === 'L' ? p.deco[0] : p.deco[1], x + j, y - 7 + i, 1, 1) } })
  },

  drawTree(t, x, y) {
    const p = this.p
    this.px(t, p.dirt[2], x + 6, y - 22, 4, 22)
    for (let yy = -40; yy < -16; yy++) for (let xx = -6; xx < 22; xx++) { const dx = xx - 8, dy = yy + 28; if (dx * dx / 160 + dy * dy / 120 <= 1) this.px(t, dy > 4 || dx > 6 ? p.deco[1] : p.deco[0], x + xx, y + yy) }
  },

  drawEnemy(x, e) {
    const sp = this.spr, kind = e.kind || 'bug'
    const dir = (kind === 'blob' ? (e.dir || 1) : e.vx) > 0 ? 0 : 1
    const X = Math.round(e.x - 1), bottom = Math.round(e.y + e.h)
    let img
    if (kind === 'bug') img = e.state === 'squish' ? sp.bugFlat[dir] : sp.bug[e.state === 'flip' ? 0 : (e.t >> 3) % 4][dir]
    else if (kind === 'spiny') img = sp.spiny[e.state === 'flip' ? 0 : (e.t >> 3) & 1][dir]
    else img = e.state === 'squish' ? sp.blobFlat[dir] : sp.blob[e.state === 'flip' ? 0 : !e.ground ? 2 : (e.landT > 0 || e.hopT < 10) ? 1 : 0][dir]
    if (e.state === 'flip') { x.save(); x.translate(X, bottom); x.scale(1, -1); x.drawImage(img, 0, 0); x.restore(); return }
    x.drawImage(img, X, bottom - img.height + (e.state === 'squish' ? 0 : kind === 'bug' ? 1 : 0))
  },

  drawLedgeLive(x, X, Y, w) { const p = this.p; this.px(x, p.ledge[0], X, Y, w, 1); this.px(x, p.ledge[1], X, Y + 1, w, 6); this.px(x, p.ledge[0], X, Y + 2, w, 1); this.px(x, p.ledge[2], X, Y + 7, w, 1); this.px(x, p.ledge[2], X, Y, 1, 8); this.px(x, p.ledge[2], X + w - 1, Y, 1, 8); for (let i = 4; i < w - 2; i += 8) this.px(x, p.ledge[2], X + i, Y + 4, 2, 2) }
}
