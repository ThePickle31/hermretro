// The New Game attract mode (page/pages/build/attract/): the real game run headless, without a canvas. For a few
// window sizes and layouts, minutes of play each: she never falls or stays stuck, uses the whole level, coins come
// back only when 90% are taken and are all reachable, the form takes no part in it, and the sprites keep their rules.
// Run alone: node tests/page/attract.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'

const { World } = await import('../../page/pages/build/attract/world.js')
const { NG_H, NG_W, ngFrames } = await import('../../page/pages/build/attract/girl.js')
const { GH } = await import('../../page/pages/build/attract/physics.js')


/** Play `minutes` of the game; what the tests look at. */
function play(W, H, seed, minutes) {
  const world = new World(seed)
  world.build(W, H)
  const bands = [0, 0, 0, 0], frames = 3600 * minutes
  let box = null, since = 0, stuck = 0
  for (let i = 0; i < frames; i++) {
    world.step()
    const g = world.girl, cx = g.x + 5, feet = g.y + GH
    bands[Math.min(3, Math.max(0, Math.floor(feet / (world.L.groundY / 4 + 0.01))))]++
    // stuck: her feet inside one 80x80 box for 10 s
    if (!box || Math.abs(cx - box.x) > 40 || Math.abs(feet - box.y) > 40) { box = { x: cx, y: feet }; since = world.frame }
    if (world.frame - since === 600) stuck++
  }
  return { world, bands: bands.map(b => b / frames), stuck, visited: world.girl.seen.size / world.L.surfaces.length }
}

const SIZES = [[856, 579], [755, 490], [639, 379]]
const SEEDS = [11, 3, 29]
const runs = []
for (const [W, H] of SIZES) for (const seed of SEEDS) runs.push({ W, H, seed, ...play(W, H, seed, 4) })
const name = r => `${r.W}x${r.H} seed ${r.seed}`

test('she never falls into the water and never stays stuck', () => {
  for (const r of runs) {
    assert.equal(r.world.stats.falls, 0, `${name(r)}: fell`)
    assert.equal(r.stuck, 0, `${name(r)}: stood in one place for 10 s`)
  }
})

test('she uses the whole level: most platforms, every height', () => {
  for (const r of runs) {
    assert.ok(r.visited >= 0.6, `${name(r)}: stood on only ${Math.round(r.visited * 100)}% of the platforms`)
    r.bands.forEach((b, i) => assert.ok(b >= 0.02, `${name(r)}: ${Math.round(b * 100)}% of the time in height band ${i} (top = 0)`))
    assert.ok(r.bands[3] <= 0.7, `${name(r)}: ${Math.round(r.bands[3] * 100)}% of the time at the bottom`)
  }
})

test('coins come back only when 90% are collected, and every coin counts', () => {
  for (const r of runs) {
    const { stats, coins } = r.world
    assert.ok(stats.waves >= 1, `${name(r)}: no coin wave in 4 minutes`)
    assert.equal(stats.waves90, stats.waves, `${name(r)}: a wave came from the 75 s fallback, so some coin is out of reach`)
    assert.ok(coins.filter(c => !c.loose).every(c => c.counts), `${name(r)}: a coin she cannot reach`)
  }
})

test('the form takes no part in the level: nothing of the page is solid, walkable or measured', async () => {
  for (const r of runs) {
    const { L } = r.world
    assert.ok(!('dom' in L), `${name(r)}: the level still holds page boxes`)
    for (const p of L.solids) assert.ok(p.kind === 'tile' || p.kind === 'block', `${name(r)}: a ${p.kind} collider`)
    for (const s of L.surfaces) assert.ok(!('dom' in s), `${name(r)}: a surface on the page`)
  }
  const { readFile } = await import('node:fs/promises')
  const source = await readFile(new URL('../../page/pages/build/new-game.js', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /data-plat/, 'new-game.js marks nothing for the level')
})

test('the same seed builds the same level', () => {
  const a = new World(7), b = new World(7)
  a.build(856, 579); b.build(856, 579)
  assert.deepEqual(a.L.surfaces.map(s => [s.x0, s.x1, s.y]), b.L.surfaces.map(s => [s.x0, s.x1, s.y]))
  assert.deepEqual(a.coins.map(c => [c.x, c.y]), b.coins.map(c => [c.x, c.y]))
})

test('the Nous Girl: every frame the same size, black and white only', () => {
  const frames = ngFrames()
  const all = Object.values(frames).flatMap(v => (Array.isArray(v[0]) ? v : [v]))
  assert.ok(all.length >= 20, 'every pose')
  for (const f of all) {
    assert.equal(f.length, NG_H)
    for (const row of f) { assert.equal(row.length, NG_W); assert.match(row, /^[KW.]+$/) }
  }
})
