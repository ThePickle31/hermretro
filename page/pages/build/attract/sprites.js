// Turning the pixel art into canvases for one palette: every sprite and its mirror image, the Nous Girl with her
// night outline and her inverted flash frames. Runs in the page only (it needs a 2D canvas).
import { PAL } from './palettes.js'
import { ngFrames } from './girl.js'
import { BULLET, CANNON, COIN, COIN_SMALL, HEART, QMARK, SPARK, WING } from './art.js'
import { BAT, BLOB, BLOB_FLAT, BUG, BUG_FLAT, SPINY } from './art-enemies.js'

export function canvas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c }
function sprite(rows, map) {
  const c = canvas(rows[0].length, rows.length), x = c.getContext('2d')
  rows.forEach((row, y) => { for (let i = 0; i < row.length; i++) { const ch = row[i]; if (ch !== '.' && map[ch]) { x.fillStyle = map[ch]; x.fillRect(i, y, 1, 1) } } })
  return c
}
function outlined(c, color) {
  const x = c.getContext('2d'), d = x.getImageData(0, 0, c.width, c.height), w = c.width, h = c.height
  const on = (i, j) => i >= 0 && j >= 0 && i < w && j < h && d.data[(j * w + i) * 4 + 3] > 0
  const add = []
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) if (!on(i, j) && (on(i - 1, j) || on(i + 1, j) || on(i, j - 1) || on(i, j + 1))) add.push([i, j])
  x.fillStyle = color
  for (const [i, j] of add) x.fillRect(i, j, 1, 1)
  return c
}
function pair(rows, map) { const r = sprite(rows, map); return [r, flipped(r)] }
export function flipped(c) { const f = canvas(c.width, c.height), x = f.getContext('2d'); x.translate(c.width, 0); x.scale(-1, 1); x.drawImage(c, 0, 0); return f }

const NG_FRAMES = ngFrames()

/** Every sprite for the palette named `name` ('day' or 'night'). */
export function makeSprites(name) {
  const p = PAL[name]
  // one clear pixel all round so the white outline (night only) is never clipped
  const pairO = (rows, map) => { const w = rows[0].length + 2; const r = sprite(['.'.repeat(w), ...rows.map(row => '.' + row + '.'), '.'.repeat(w)], map); if (p.girlLine) outlined(r, p.girlLine); return [r, flipped(r)] }
  const set = map => Object.fromEntries(Object.entries(NG_FRAMES).map(([k, v]) => [k, Array.isArray(v[0]) ? v.map(f => pairO(f, map)) : pairO(v, map)]))
  // hurt flash and the power-up flicker stay black and white: the sprite inverted
  const girl = set(p.girl)
  girl.inv = set({ K: '#ffffff', W: '#000000' })
  return {
    girl,
    bug: BUG.map(f => pair(f, p.bug)), bugFlat: pair(BUG_FLAT, p.bug),
    spiny: SPINY.map(f => pair(f, p.spiny)), blob: BLOB.map(f => pair(f, p.blob)), blobFlat: pair(BLOB_FLAT, p.blob),
    bat: BAT.map(f => pair(f, p.bat)), bullet: pair(BULLET, p.bullet), cannon: pair(CANNON, p.cannon),
    coin: COIN.map(f => sprite(f, p.coin)), coinHud: sprite(COIN_SMALL, p.coin), wing: pair(WING, p.wing),
    heart: sprite(HEART, { K: p.hud[0], R: p.hud[2] }), heartOff: sprite(HEART, { K: p.hud[0], R: p.hud[4] }),
    spark: SPARK.map(f => sprite(f, { W: p.spark })), q: sprite(QMARK, { K: p.block[3] }), qHi: sprite(QMARK, { K: p.block[2] })
  }
}
