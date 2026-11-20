// The autopilot: how the Nous Girl plays by herself. She picks goals (coins, ? blocks, coin arcs, power-ups, and
// platforms she has not stood on for a while, so she roams the whole level), walks the shortest way there over the
// simulated jumps of paths.js, checks every jump against the enemies, shots and bats that will be in its way, jumps
// over or stomps what comes at her, re-plans her landing after a bounce, and a watchdog moves her on if she ever
// stays in one place. Mixed into World (world.js).
import { DJUMPV, GH, GW, JUMPV, SPEED, T, overlap, physStep } from './physics.js'
import { firstEdge, landsFrom, shortest, simulate, surfaceAt } from './paths.js'

export const PILOT = {
  pickGoal(s) {
    const L = this.L, g = this.girl
    const paths = shortest(L, s.id)
    const cands = []
    const below = (x, y, reach) => { let best = null; for (const t of L.surfaces) if (x >= t.x0 - 2 && x <= t.x1 + 2 && t.y >= y && t.y - y <= reach && (!best || t.y < best.y)) best = t; return best }
    const left = this.coinsLeft(), hunt = left.all ? 1 - left.n / left.all : 0
    for (const c of this.coins) {
      if (!c.on || c.arc || (c.loose && !c.rest) || c.skipUntil > this.frame) continue
      const t = below(c.x + 6, c.y + 16, 70)
      if (!t) continue
      const cost = paths.dist.get(t.id)
      if (cost === undefined) continue
      cands.push({ kind: 'coin', ref: c, s: t, x: c.x + 6, jump: c.y + 16 < t.y - GH + 2, w: (c.loose ? 2.2 : 1 + this.rng() * 0.5) * (1 + 2 * hunt), cost, far: hunt > 0.5 })
    }
    // a coin arc: run to where its jump starts and take it
    for (const a of L.arcs) {
      const n = a.live.filter(c => c.on).length
      if (!n || a.skipUntil > this.frame) continue
      const cost = paths.dist.get(a.from)
      if (cost === undefined) continue
      cands.push({ kind: 'arc', ref: a, s: L.surfaces[a.from], x: a.tx, jump: false, w: (0.5 + 0.35 * n) * (1 + 2 * hunt), cost, far: hunt > 0.5 })
    }
    for (const b of L.blocks) {
      if (!b.active || b.skipUntil > this.frame) continue
      const t = below(b.x + T / 2, b.y + T, 70)
      if (!t) continue
      const cost = paths.dist.get(t.id)
      if (cost === undefined) continue
      cands.push({ kind: 'block', ref: b, s: t, x: b.x + T / 2, jump: true, w: 1.3, cost })
    }
    for (const it of this.items) {
      const t = below(it.x + 11, it.y + it.h - 1, 40)
      if (!t) continue
      const cost = paths.dist.get(t.id)
      if (cost !== undefined) cands.push({ kind: 'item', ref: it, s: t, x: it.x + 11, jump: false, w: 4, cost })
    }
    // explore: platforms she has not stood on for a while pull hardest, high ones more than low ones, the
    // ground least, and distance matters much less than for a coin, so she crosses the whole level
    const sx = L.surfaces.filter(t => t !== s && paths.dist.has(t.id))
    for (const t of sx) {
      const ago = this.frame - (g.seen.get(t.id) ?? -1e9), stale = Math.min(1, ago / 2400)
      if (stale < 0.25) continue
      const ground = !t.dom && Math.abs(t.y - L.groundY) < 1, height = (L.groundY - t.y) / L.groundY
      cands.push({ kind: 'wander', s: t, x: t.l + this.rng() * (t.r - t.l), jump: false, w: stale * (ground ? 1.5 : 1 + 0.35 * height) * (t.dom ? 1.15 : 1), cost: paths.dist.get(t.id), far: true })
    }
    let best = null, bestScore = -1
    for (const c of cands) {
      if ((c.kind === 'block' || c.kind === 'coin') && Math.abs(Math.max(c.s.l, Math.min(c.s.r, c.x)) - c.x) > (c.kind === 'block' ? 6 : 8)) continue
      const sc = c.w * (0.6 + this.rng() * 0.8) / (1 + c.cost / (c.far ? 520 : 140)); if (sc > bestScore) { bestScore = sc; best = c } }
    if (best) best.x = Math.max(best.s.l, Math.min(best.s.r, best.x))
    g.goalTries = 0
    g.goal = best; g.goalT = 720; g.paths = paths; g.pathsFrom = s.id
  },

  goalValid(goal) {
    if (!goal) return false
    if (goal.kind === 'coin') return goal.ref.on
    if (goal.kind === 'block') return goal.ref.active
    if (goal.kind === 'item') return this.items.includes(goal.ref)
    if (goal.kind === 'arc') return goal.ref.live.some(c => c.on)
    return true
  },

  // Play a jump out frame by frame against where the threat will be: safe if she never touches it, or only
  // lands on top of it.
  safeJump(cx, feet, tx, box, mode = 'jump') {
    const L = this.L, b = { x: cx - GW / 2, y: feet - GH, w: GW, h: GH, vx: 0, vy: -JUMPV }
    let dj = mode !== 'djump', stomped = false
    // a little wider than the real thing, and a stomp only counts when clearly from above; a box with a path()
    // (a bat) moves along it instead of in a straight line
    const e = { x: box.x - 2, y: box.y, w: box.w + 4, h: box.h }
    for (let f = 0; f < 160; f++) {
      if (!dj && f > 0 && b.vy >= -0.5) { b.vy = -DJUMPV; dj = true }
      const c = b.x + GW / 2
      b.vx = Math.abs(tx - c) > 1.2 ? Math.sign(tx - c) * SPEED : 0
      const prevFeet = b.y + GH
      const res = physStep(L, b, false)
      if (box.path) { const q = box.path(f + 1); e.x = q.x - 2; e.y = q.y } else e.x += box.vx
      // a stomp only counts if the jump would also land safely without it (the bug may turn back at an edge)
      if (!stomped && overlap(b, e)) { if (!(box.stompable && b.vy > 0 && prevFeet <= e.y + 3)) return false; stomped = true }
      if (res.ground && f > 0) {
        // after landing, she must not be standing where it walks into her within a few frames
        const q = box.path ? box.path(f + 10) : null
        const ahead = q ? { x: q.x - 2, y: q.y, w: e.w, h: e.h } : { x: e.x + box.vx * 10, y: e.y, w: e.w, h: e.h }
        return (stomped || !overlap(b, ahead)) && !!surfaceAt(L, b.x + GW / 2, b.y + GH)
      }
      if (b.y > L.H) return false
    }
    return false
  },

  // every jump she plans is checked against the bugs and bullets close to her
  jumpSafe(tx, mode = 'jump') {
    const g = this.girl, cx = g.x + GW / 2, feet = g.y + GH
    for (const e of this.enemies) if (e.state === 'walk' && Math.abs(e.x + e.w / 2 - cx) < 110 && Math.abs(e.y + e.h - feet) < 64 && !this.safeJump(cx, feet, tx, { x: e.x, y: e.y, w: e.w, h: e.h, vx: e.vx, path: this.enemyPath(e), stompable: e.kind !== 'spiny' }, mode)) return false
    for (const b of this.bullets) if (Math.abs(b.x + 8 - cx) < 120 && Math.abs(b.y - feet) < 140 && !this.safeJump(cx, feet, tx, { x: b.x, y: b.y, w: b.w, h: b.h, vx: b.vx, stompable: true }, mode)) return false
    for (const bt of this.bats) {
      if (bt.dead) continue
      const path = f => ({ x: bt.x + 1 + bt.vx * f, y: bt.baseY + Math.sin((bt.t + f) * 0.045) * 20 })
      const now = path(0)
      if (Math.abs(now.x + 10 - cx) < 160 && now.y > feet - 170 && now.y < feet + 20 && !this.safeJump(cx, feet, tx, { ...now, w: 20, h: 12, path, stompable: false }, mode)) return false
    }
    return true
  },

  // a bullet that will cross the air above her soon: wait for it before jumping
  airBusy() {
    const g = this.girl, gx = g.x + GW / 2, feet = g.y + GH
    for (const b of this.bullets) {
      const dx = gx - (b.x + 8)
      if (Math.sign(dx) === Math.sign(b.vx) && Math.abs(dx) < 120 && b.y > feet - 110 && b.y < feet - 6) return true
    }
    return false
  },

  // after a bounce in the air, steer to somewhere she will land on
  replanAir() {
    const g = this.girl, cx = g.x + GW / 2, base = g.exec ? g.exec.target : cx
    if (!g.exec) g.exec = { mode: 'jump', target: cx, left: true, t: 0, dj: true }
    for (const d of [0, 14, -14, 28, -28, 42, -42, 60, -60, 84, -84]) if (landsFrom(this.L, g, base + d)) { g.exec.target = base + d; return }
    for (const d of [0, 20, -20, 40, -40, 70, -70, 100, -100]) if (landsFrom(this.L, g, cx + d)) { g.exec.target = cx + d; return }
  },

  startExec(mode, target) {
    const g = this.girl
    g.exec = { mode, target, left: mode !== 'walk', t: 0, dj: mode !== 'djump' }
    if (mode === 'jump' || mode === 'djump') { g.vy = -JUMPV; g.ground = null }
    if (mode === 'through') { g.through = 14; g.ground = null }
  },

  threat() {
    const g = this.girl, gx = g.x + GW / 2, feet = g.y + GH
    for (const e of this.enemies) {
      if (e.state !== 'walk') continue
      const ex = e.x + e.w / 2
      if (Math.abs(e.y + e.h - feet) >= (e.kind === 'blob' ? 40 : 6)) continue
      const toward = Math.sign(gx - ex) === Math.sign((e.kind === 'blob' ? e.dir : e.vx) || 1)
      const chasing = !toward && Math.sign(ex - gx) === Math.sign(g.vx) && g.vx !== 0
      if ((toward && Math.abs(ex - gx) < 64) || (chasing && Math.abs(ex - gx) < 32)) {
        // mostly hop clean over it and land beyond; now and then go for the stomp
        const over = Math.sign(ex - gx || 1) * 42
        const stomp = e.kind !== 'spiny' && this.rng() < 0.3
        return { x: stomp ? ex + e.vx * 22 : ex + over, alt: [ex + over, ex + e.vx * 22, ex + over * 1.6, gx], stomp, from: ex, need: e.kind === 'blob' ? 30 : 20, box: { x: e.x, y: e.y, w: e.w, h: e.h, vx: e.vx, path: this.enemyPath(e), stompable: e.kind !== 'spiny' } }
      }
    }
    for (const b of this.bullets) {
      const bx = b.x + 8
      if (b.y + 11 > g.y && b.y < feet && Math.abs(bx - gx) < 64 && Math.sign(gx - bx) === Math.sign(b.vx)) return { x: gx, alt: [gx, gx - Math.sign(b.vx) * 20, gx + Math.sign(b.vx) * 20], stomp: false, from: bx, need: feet - b.y + 2, box: { x: b.x, y: b.y, w: b.w, h: b.h, vx: b.vx, stompable: true } }
    }
    for (const bt of this.bats) {
      if (bt.dead) continue
      const bx = bt.x + 11, by = bt.baseY + Math.sin(bt.t * 0.045) * 20
      if (by + 12 > g.y - 4 && by < feet && Math.abs(bx - gx) < 64 && Math.sign(gx - bx) === Math.sign(bt.vx)) return { x: gx - Math.sign(bt.vx) * 6, stomp: false, from: bx, need: Infinity }
    }
    return null
  },

  // A watchdog for anything the planner gets wrong: if her feet stay inside one small box for 6 s, she drops
  // her goal (and avoids it for a while), and heads for a platform far from here.
  watchdog() {
    const g = this.girl, cx = g.x + GW / 2, feet = g.y + GH
    // pacing: the same platform, or the same moving platform, for 20 s
    if (g.ground) {
      const s = g.ground.mover ? null : surfaceAt(this.L, cx, feet), key = g.ground.mover ? 'mover' : s ? s.id : null
      if (key !== null && key !== g.pace?.key) g.pace = { key, t: this.frame }
    }
    const pacing = g.pace && this.frame - g.pace.t > 1200
    if (!pacing && (!g.wd || Math.abs(cx - g.wd.x) > 40 || Math.abs(feet - g.wd.y) > 40 || g.stun > 0)) { g.wd = { x: cx, y: feet, t: this.frame }; return }
    if (!pacing && this.frame - g.wd.t < 360) return
    if (!g.ground) return
    g.wd = { x: cx, y: feet, t: this.frame }; if (g.pace) g.pace.t = this.frame
    this.stats.unsticks++
    if (g.goal) { if (g.goal.ref) g.goal.ref.skipUntil = this.frame + 2400; g.seen.set(g.goal.s.id, this.frame) }
    g.goal = null; g.exec = null; g.retreat = 0; g.wait = 0
    const s = g.ground && !g.ground.mover ? surfaceAt(this.L, cx, feet) : null
    if (!s) {
      for (const mode of ['jump', 'djump', 'walk']) for (const dx of [56, -56, 84, -84, 28, -28, 40, -40]) { const sim = simulate(this.L, cx, feet, mode, cx + dx); if (sim && sim.s) { this.startExec(mode, cx + dx); return } }
      return
    }
    const paths = shortest(this.L, s.id)
    const far = this.L.surfaces.filter(t => paths.dist.has(t.id) && Math.hypot((t.l + t.r) / 2 - cx, t.y - feet) > 160)
    if (far.length) { const t = far[Math.floor(this.rng() * far.length)]; g.goal = { kind: 'wander', s: t, x: (t.l + t.r) / 2, jump: false, w: 1, cost: paths.dist.get(t.id) }; g.goalT = 900; g.paths = paths; g.pathsFrom = s.id }
  },

  updateGirl() {
    const g = this.girl, L = this.L
    this.watchdog()
    if (g.inv > 0) g.inv--
    if (g.power > 0) { g.power--; if (this.frame % 3 === 0) this.parts.push({ type: 'spark', x: g.x + GW / 2 - 3 + (this.rng() - 0.5) * 8, y: g.y + 6 + this.rng() * 14, t: 0, life: 14 }) }
    if (g.ground && g.ground.mover) { g.x += g.ground.dx }
    let input = 0
    const cx = g.x + GW / 2, feet = g.y + GH
    if (g.stun > 0) { g.stun--; input = 0; g.vx *= 0.92 } else if (g.exec) {
      const e = g.exec
      e.t++
      // the double jump fires at the top of the first, exactly where the planner fired it
      if (!e.dj && !g.ground && g.vy >= -0.5) { e.dj = true; g.vy = -DJUMPV; g.spin = 16; this.puff(cx, feet) }
      input = Math.abs(e.target - cx) > 1.2 ? Math.sign(e.target - cx) : 0
      if (!g.ground) e.left = true
      if ((g.ground && e.left && e.t > 1) || e.t > 200) { g.exec = null; if (g.ground) this.dust(cx, feet) }
    } else if (g.ground) {
      const s = g.ground.mover ? null : surfaceAt(L, cx, feet)
      const th = this.threat()
      let dodge = null
      if (th && g.inv === 0) {
        const tries = th.box ? [th.x, ...(th.alt || [])] : [th.x, cx, cx - Math.sign(th.x - cx) * 42]
        for (const tx of tries) {
          if (th.box ? this.safeJump(cx, feet, tx, th.box) : (() => { const sim = simulate(L, cx, feet, 'jump', tx); return sim && sim.s && sim.rise >= th.need })()) { dodge = tx; break }
        }
        // no room to jump over it (low ceiling, edge): back off and let it pass
        if (dodge === null && !g.retreat) { const away = Math.max(s ? s.l : cx, Math.min(s ? s.r : cx, cx + Math.sign(cx - th.from || 1) * 60)); if (Math.abs(away - cx) > 8) { g.retreat = 50; g.retreatTo = away } }
      }
      if (g.retreat > 0) {
        g.retreat--
        input = Math.abs(g.retreatTo - cx) > 1.2 ? Math.sign(g.retreatTo - cx) : 0
        if (input === 0 || g.retreat === 0) g.retreat = 0
      } else if (dodge !== null) { this.startExec('jump', dodge); input = Math.abs(dodge - cx) > 1.2 ? Math.sign(dodge - cx) : 0 } else if (!s) {
        // on a moving platform: hop off toward the goal once a safe landing is under the jump
        const tx = g.goal ? g.goal.x : this.W / 2
        const dir = Math.sign(tx - cx) || 1
        g.ride = (g.ride || 0) + 1
        if (this.frame % 6 === 0) {
          const tries = g.ride > 240 ? [dir * 56, dir * 28, 0, -dir * 28, -dir * 56, dir * 84, -dir * 84] : [dir * 56, dir * 34]
          let done = false
          for (const d of tries) { const sim = simulate(L, cx, feet, 'jump', cx + d); if (sim && sim.s) { this.startExec('jump', cx + d); g.ride = 0; done = true; break } }
          if (!done && g.ride > 120) for (const d of [dir * 40, -dir * 40, dir * 70, -dir * 70]) { const sim = simulate(L, cx, feet, 'walk', cx + d); if (sim && sim.s) { this.startExec('walk', cx + d); g.ride = 0; break } }
        }
      } else {
        g.seen.set(s.id, this.frame)
        if (g.goal && g.goalT <= 1 && g.goal.ref) g.goal.ref.skipUntil = this.frame + 2400
        if (!this.goalValid(g.goal) || --g.goalT <= 0) this.pickGoal(s)
        const goal = g.goal
        if (goal) {
          if (goal.s.id === s.id) {
            const d = goal.x - cx
            if (Math.abs(d) <= SPEED) {
              g.x = goal.x - GW / 2
              if (goal.jump) { if (g.wait > 0) g.wait--; else if (this.airBusy() || !this.jumpSafe(goal.x)) g.wait = 6; else if (++g.goalTries > 3) { if (goal.ref) goal.ref.skipUntil = this.frame + 2400; g.goal = null } else { this.startExec('jump', goal.x); g.wait = 4 + Math.floor(this.rng() * 10) } } else if (goal.kind === 'arc') { if (g.wait > 0) g.wait--; else if (this.airBusy() || !this.jumpSafe(goal.ref.lx)) g.wait = 6; else if (++g.goalTries > 3) { goal.ref.skipUntil = this.frame + 2400; g.goal = null } else { this.startExec('jump', goal.ref.lx); g.goal = null } } else if (goal.kind === 'wander') { g.idle++; if (g.idle > 40 + this.rng() * 60) { g.goal = null; g.idle = 0 } } else g.goal = null
            } else input = Math.sign(d)
          } else {
            if (g.pathsFrom !== s.id) { g.paths = shortest(L, s.id); g.pathsFrom = s.id }
            const e = firstEdge(g.paths, s.id, goal.s.id)
            if (!e) g.goal = null
            else if (Math.abs(e.tx - cx) <= SPEED) {
              g.x = e.tx - GW / 2
              if (g.wait > 0) g.wait--
              else if (e.mode !== 'walk' && (this.airBusy() || !this.jumpSafe(e.lx, e.mode))) g.wait = 6
              else { this.startExec(e.mode, e.lx); input = Math.abs(e.lx - cx) > 1.2 ? Math.sign(e.lx - cx) : 0; g.wait = this.rng() < 0.3 ? 4 + Math.floor(this.rng() * 14) : 0 }
            } else input = Math.sign(e.tx - cx)
          }
        }
      }
    }
    if (g.stun <= 0) g.vx = input * SPEED * (g.power > 0 ? 1 : 1)
    if (input) g.face = input
    const res = physStep(L, g, g.through > 0)
    if (g.through > 0) g.through--
    const wasAir = !g.ground
    g.ground = res.ground
    // animation state: distance run (keeps feet from sliding), landing squash, skid on a turn, blinks
    g.dist = (g.dist || 0) + Math.abs(g.vx)
    if (res.ground && wasAir) g.landT = g.vy === 0 && g.fallFrom && g.y - g.fallFrom > 36 ? 8 : 4
    if (!res.ground) { if (!wasAir) g.fallFrom = g.y; g.fallFrom = Math.min(g.fallFrom ?? g.y, g.y) } else g.fallFrom = null
    if (g.landT > 0) g.landT--
    if (g.skidT > 0) g.skidT--
    if (g.cheerT > 0) g.cheerT--
    if (g.spin > 0) g.spin--
    if (res.ground && input && g.lastInput && input !== g.lastInput) g.skidT = 7
    if (input) g.lastInput = input
    if (--g.blinkT <= 0 || g.blinkT === undefined || isNaN(g.blinkT)) g.blinkT = 150 + Math.floor(this.rng() * 200)
    if (res.ground && wasAir && !g.exec) this.dust(g.x + GW / 2, g.y + GH)
    if (res.bumped && res.bumped.kind === 'block') this.bumpBlock(res.bumped.ref)
    if (res.bumped && res.bumped.kind === 'dom') this.sparkle(g.x + GW / 2 - 3, g.y - 4)
    g.anim = g.ground ? (input ? g.anim + 1 : 0) : g.anim
    // coins
    for (const c of this.coins) if (c.on && overlap(g, c)) { c.on = false; this.coinsGot++; this.score += 100; this.sparkle(c.x, c.y); this.lastCoin = this.frame }
    if (!this.coins.some(c => c.pending)) { const { n, all } = this.coinsLeft(); if (all && n <= all * 0.1) { this.stats.waves90++; this.coinWave() } else if (this.frame - this.lastCoin > 60 * 75) this.coinWave() }
    for (const it of this.items) if (overlap(g, it)) { it.got = true; g.power = 480; g.cheerT = 32; this.addScore(1000, it.x, it.y - 6); this.sparkle(it.x + 4, it.y, 5) }
    if (g.y > L.groundY + 20) { this.parts.push({ type: 'splash', x: g.x + 5, y: L.groundY + 14, t: 0, life: 22 }); this.hit(true) }
  }
}
