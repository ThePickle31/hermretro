// Everything else that moves: beetles, spinies and hopping blobs out of the pipes (and a beetle now and then dropped
// from the sky), bats on a wave, cannon shots, ? blocks and the power-up they give, and the particles. Mixed into World (world.js).
import { GH, GRAV, T, overlap, physStep, solidAt } from './physics.js'

export const ACTORS = {
  hit(fell, by) {
    const g = this.girl
    if (fell) this.stats.falls++
    else this.stats.hits[by] = (this.stats.hits[by] || 0) + 1
    this.hearts--
    if (this.hearts <= 0) { this.hearts = 3; this.sparkle(g.x, g.y, 6) }
    if (fell) { this.respawn(); return }
    g.inv = 120; g.stun = 16; g.vy = -2.6; g.vx = -g.face * 1.3; g.exec = null; g.ground = null
  },

  bumpBlock(b) {
    if (!b.active) return
    b.active = false; b.bump = 8; this.lastCoin = this.frame
    if (this.rng() < 0.22 && this.items.length === 0) {
      this.items.push({ x: b.x + 1, y: b.y, w: 22, h: 15, rise: 18, got: false, t: 0 })
    } else {
      this.coinsGot++; this.score += 100
      this.parts.push({ type: 'coinpop', x: b.x + 6, y: b.y - 12, vy: -3, g: 0.16, t: 0, life: 30 })
      this.parts.push({ type: 'text', s: '100', x: b.x + 4, y: b.y - 20, vy: -0.4, t: -18, life: 50 })
    }
    for (const e of this.enemies) if (e.state === 'walk' && Math.abs(e.y + e.h - b.y) < 2 && e.x + e.w > b.x && e.x < b.x + T) this.kill(e, true)
  },

  kill(e, flip) {
    if (flip) { e.state = 'flip'; e.vy = -2.5; e.vx = 0.6 * Math.sign(e.vx || 1); e.t = 0 } else { e.state = 'squish'; e.t = 0 }
    this.addScore(200, e.x, e.y - 6)
  },

  updateItems() {
    for (const it of this.items) {
      it.t++
      if (it.rise > 0) { it.y -= 1; it.rise--; continue }
      it.y += Math.sin(it.t * 0.08) * 0.15
      if (it.t > 900) it.got = true
    }
    this.items = this.items.filter(i => !i.got)
  },

  // A blob sits still, squashes, then hops a short arc forward; before a hop it checks the landing and turns
  // round if the hop would take it off its platform. Pure function of its state, so the planner can play it out.
  blobStep(e, L = this.L) {
    if (e.ground && e.vy === 0) {
      e.vx = 0
      if (--e.hopT <= 0) {
        const dir = e.dir || 1
        const probe = { x: e.x, y: e.y, w: e.w, h: e.h, vx: 0.9 * dir, vy: -3.4 }
        let ok = false
        for (let f = 0; f < 80; f++) { const r = physStep(L, probe, false); if (r.wall) break; if (r.ground) { ok = Math.abs(probe.y - e.y) < 30; break } }
        if (!ok) e.dir = -dir
        e.vx = 0.9 * (e.dir || 1); e.vy = -3.4; e.hopT = 70 + ((e.x * 7) | 0) % 40; e.ground = null
      }
    }
    const res = physStep(L, e, false)
    if (res.wall) { e.dir = -(e.dir || 1); e.vx = -e.vx }
    if (res.ground) { if (!e.ground) e.landT = 8; e.ground = res.ground } else e.ground = null
    if (e.landT > 0) e.landT--
    e.res = res
  },

  // where an enemy will be for the next n frames (blobs hop, so they are played out; walkers go straight)
  enemyPath(e, n = 160) {
    if (e.kind !== 'blob') return null
    if (e.pathF === this.frame && e.pathC) return e.pathC
    const c = { ...e, res: null }, out = []
    for (let f = 0; f < n; f++) { this.blobStep(c); out.push({ x: c.x, y: c.y }) }
    e.pathF = this.frame; e.pathC = f => out[Math.min(out.length - 1, Math.max(0, f - 1))]
    return e.pathC
  },

  updateEnemies() {
    const L = this.L, g = this.girl, rng = this.rng
    const maxE = this.H < 160 ? 1 : Math.max(1, Math.min(8, Math.round(this.W * this.H / 60000)))
    for (const p of L.pipes) {
      if (--p.timer > 0) continue
      p.timer = Math.round((320 + rng() * 380) * Math.max(1, L.pipes.length / 3))
      if (this.enemies.length < maxE && !this.enemies.some(e => Math.abs(e.x - p.x - 14) < 40 && Math.abs(e.y - p.y) < 28)) {
        // beetles most often; a spiny now and then (no stomping it), and blobs that hop along
        const k = rng(), kind = k < 0.5 ? 'bug' : k < 0.75 ? 'spiny' : 'blob'
        const sz = { bug: [20, 15], spiny: [20, 14], blob: [18, 13] }[kind]
        this.enemies.push({ kind, x: p.x + 24 - sz[0] / 2, y: p.y + 6, w: sz[0], h: sz[1], vx: (kind === 'spiny' ? 0.4 : 0.5) * p.dir, vy: 0, state: 'emerge', t: 0, edgeTurn: kind === 'blob' || rng() < 0.55, ground: null, pipeY: p.y, hopT: 40 + Math.floor(rng() * 60), dir: p.dir })
      }
    }
    // now and then a beetle drops in from the sky over one of the wider platforms
    const wide = L.surfaces.filter(s => s.x1 - s.x0 >= 72 && s.y < L.groundY - 1)
    if (this.frame % 600 === 300 && this.enemies.length < maxE && wide.length && !this.enemies.some(e => e.dropped)) {
      const top = wide[Math.floor(rng() * wide.length)], d = { x: top.x0, w: top.x1 - top.x0 }
      this.enemies.push({ kind: 'bug', x: d.x + 24 + rng() * (d.w - 48), y: -18, w: 20, h: 15, vx: rng() < 0.5 ? -0.5 : 0.5, vy: 0, state: 'walk', t: 0, edgeTurn: true, ground: null, dropped: true })
    }
    for (const e of this.enemies) {
      e.t++
      if (e.state === 'emerge') { e.y -= 0.35; if (e.y + e.h <= e.pipeY) { e.y = e.pipeY - e.h; e.state = 'walk'; e.noTurn = 90 } continue }
      if (e.noTurn > 0) e.noTurn--
      if (e.state === 'squish') { if (e.t > 30) e.dead = true; continue }
      if (e.state === 'flip') { e.vy += GRAV; e.y += e.vy; e.x += e.vx; if (e.y > this.H + 20) e.dead = true; continue }
      if (e.state === 'leave') { e.x += e.vx; if (++e.leaveT > 50) e.dead = true; continue }
      if (e.kind === 'blob') { this.blobStep(e); if (e.dead) continue }
      const res = e.kind === 'blob' ? e.res : physStep(L, e, false)
      // a bug that has been out a while and walks into the side of a pipe goes down it
      if (res.wall && e.t > 500 && L.pipes.some(pp => e.y + e.h > pp.y && e.y < pp.y + pp.h * T && (e.vx > 0 ? Math.abs(e.x + e.w - pp.x) < 3 : Math.abs(e.x - pp.x - 2 * T) < 3))) { e.state = 'leave'; e.leaveT = 0; continue }
      if (res.wall && e.kind !== 'blob') e.vx = -e.vx
      if (L.tunnel && res.ground && Math.abs(e.y + e.h - L.groundY) < 1) {
        const nx = e.vx > 0 ? e.x + e.w : e.x
        if (nx > L.tunnel.x0 && nx < L.tunnel.x1 && !(e.x + e.w > L.tunnel.x0 && e.x < L.tunnel.x1 && e.inTunnel)) { e.vx = -e.vx; e.x += e.vx * 2; if (e.kind === 'blob') e.dir = -(e.dir || 1) }
        e.inTunnel = e.x + e.w > L.tunnel.x0 && e.x < L.tunnel.x1
      }
      if (res.ground && e.edgeTurn && !(e.noTurn > 0) && e.kind !== 'blob') {
        const probe = e.vx > 0 ? e.x + e.w + 1 : e.x - 1
        if (!solidAt(L, probe, e.y + e.h + 1)) e.vx = -e.vx
      }
      if (e.y > L.groundY + 16) { e.dead = true; this.parts.push({ type: 'splash', x: e.x + 10, y: L.groundY + 14, t: 0, life: 22 }) }
      // against the girl
      if (overlap(g, e)) {
        // a spiny can't be stomped: landing on its spikes hurts
        if (e.kind !== 'spiny' && g.vy > 0 && g.y + GH - e.y < 11) { this.kill(e, false); g.vy = -4.2; this.sparkle(e.x + 7, e.y); this.replanAir() } else if (g.power > 0) this.kill(e, true)
        else if (g.inv === 0) this.hit(false, e.kind)
      }
    }
    for (let i = 0; i < this.enemies.length; i++) for (let j = i + 1; j < this.enemies.length; j++) {
      const a = this.enemies[i], b = this.enemies[j]
      if (a.state !== 'walk' || b.state !== 'walk' || !overlap(a, b) || Math.abs(a.y - b.y) > 3) continue
      const dir = Math.sign(a.x - b.x) || 1
      a.vx = Math.abs(a.vx) * dir; b.vx = -Math.abs(b.vx) * dir
    }
    this.enemies = this.enemies.filter(e => !e.dead)
    for (const b of this.bats) {
      if (b.dead) { if (--b.dead === 0) { b.x = b.vx > 0 ? -16 : this.W + 2; b.t = 0 } continue }
      b.t++; b.x += b.vx
      if (b.x > this.W + 20) b.x = -20
      if (b.x < -20) b.x = this.W + 20
      const box = { x: b.x + 1, y: b.baseY + Math.sin(b.t * 0.045) * 20, w: 20, h: 12 }
      if (overlap(g, box)) {
        if (g.vy > 0 && g.y + GH - box.y < 10) { b.dead = 240; g.vy = -4.2; this.addScore(200, box.x, box.y); this.sparkle(box.x + 4, box.y, 3); this.replanAir() } else if (g.power > 0) { b.dead = 240; this.addScore(200, box.x, box.y) } else if (g.inv === 0) this.hit(false, 'bat')
      }
    }
    for (const c of L.cannons) {
      if (--c.timer > 0) continue
      c.timer = 200 + Math.floor(rng() * 220)
      this.bullets.push({ x: c.dir < 0 ? c.x - 17 : c.x + 27, y: c.y + 5, vx: 1 * c.dir, w: 16, h: 11 })
      this.parts.push({ type: 'dust', x: c.dir < 0 ? c.x - 4 : c.x + 28, y: c.y + 10, vx: 0.3 * c.dir, vy: -0.2, t: 0, life: 14 })
    }
    for (const b of this.bullets) {
      b.x += b.vx
      if (overlap(g, b)) {
        if (g.vy > 0 && g.y + GH - b.y < 9) { b.dead = true; g.vy = -4.2; this.addScore(200, b.x, b.y); this.replanAir() } else if (g.power > 0) { b.dead = true } else if (g.inv === 0) { this.hit(false, 'bullet') }
      }
      if (b.x < -20 || b.x > this.W + 20) b.dead = true
    }
    this.bullets = this.bullets.filter(b => !b.dead)
  },

  addScore(n, x, y) { this.score += n; this.parts.push({ type: 'text', s: String(n), x, y, vy: -0.5, t: 0, life: 45 }) },

  sparkle(x, y, n = 1) { for (let i = 0; i < n; i++) this.parts.push({ type: 'spark', x: x + (this.rng() - 0.5) * 10 * (n > 1), y: y + (this.rng() - 0.5) * 10 * (n > 1), t: -i * 4, life: 18 }) },

  dust(x, y) { for (const s of [-1, 1]) this.parts.push({ type: 'dust', x, y, vx: s * 0.4, vy: -0.15, t: 0, life: 14 }) },

  // a ring of puffs under her feet for the double jump
  puff(x, y) { for (const [vx, vy] of [[-1, 0.2], [1, 0.2], [-0.5, 0.6], [0.5, 0.6], [0, 0.8]]) this.parts.push({ type: 'dust', x, y, vx, vy, t: 0, life: 16 }) }
}
