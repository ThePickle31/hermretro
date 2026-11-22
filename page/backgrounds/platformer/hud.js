// The HUD strip along the bottom of the screen (hearts, coins, score, WORLD 1-1, a blinking DEMO PLAY) and the
// small score numbers that float up, drawn with a built-in 5x7 pixel font so nothing has to be loaded.
import { canvas } from './sprites.js'

// 5x7 glyphs, one string of 0s and 1s per row; only the characters the HUD uses
const FONT = {
  0: '01110 10001 10011 10101 11001 10001 01110', 1: '00100 01100 00100 00100 00100 00100 01110',
  2: '01110 10001 00001 00010 00100 01000 11111', 3: '11110 00001 00001 01110 00001 00001 11110',
  4: '00010 00110 01010 10010 11111 00010 00010', 5: '11111 10000 11110 00001 00001 10001 01110',
  6: '00110 01000 10000 11110 10001 10001 01110', 7: '11111 00001 00010 00100 01000 01000 01000',
  8: '01110 10001 10001 01110 10001 10001 01110', 9: '01110 10001 10001 01111 00001 00010 01100',
  A: '01110 10001 10001 11111 10001 10001 10001', C: '01110 10001 10000 10000 10000 10001 01110',
  D: '11110 10001 10001 10001 10001 10001 11110', E: '11111 10000 10000 11110 10000 10000 11111',
  L: '10000 10000 10000 10000 10000 10000 11111', M: '10001 11011 10101 10101 10001 10001 10001',
  O: '01110 10001 10001 10001 10001 10001 01110', P: '11110 10001 10001 11110 10000 10000 10000',
  R: '11110 10001 10001 11110 10100 10010 10001', S: '01111 10000 10000 01110 00001 00001 11110',
  W: '10001 10001 10001 10101 10101 10101 01010', Y: '10001 10001 01010 00100 00100 00100 00100',
  x: '00000 00000 10001 01010 00100 01010 10001', '-': '00000 00000 00000 11111 00000 00000 00000'
}
// 3x5 digits for the scores that float up
const DIGITS = { 0: '111101101101111', 1: '010110010010111', 2: '111001111100111', 3: '111001111001111', 4: '101101111001001', 5: '111100111001111', 6: '111100111101111', 7: '111001001001001', 8: '111101111101111', 9: '111101111001111' }

const cache = new Map()
function remember(key, make) {
  if (!cache.has(key)) {
    if (cache.size > 300) cache.clear()
    cache.set(key, make())
  }
  return cache.get(key)
}

/** `str` in the HUD font, in `color`: a canvas 6 px per character, 7 px tall. */
export function pixelText(str, color) {
  return remember(`t|${str}|${color}`, () => {
    const c = canvas(str.length * 6, 7), x = c.getContext('2d')
    x.fillStyle = color
    ;[...str].forEach((ch, i) => {
      const rows = FONT[ch]?.split(' ') || []
      rows.forEach((row, y) => { for (let k = 0; k < 5; k++) if (row[k] === '1') x.fillRect(i * 6 + k, y, 1, 1) })
    })
    return c
  })
}

/** A score that floats up: 3x5 digits with a dark drop shadow. */
export function smallText(str, color) {
  return remember(`s|${str}|${color}`, () => {
    const c = canvas(str.length * 4 + 2, 7), t = c.getContext('2d')
    for (let i = 0; i < str.length; i++) {
      const m = DIGITS[str[i]]
      if (!m) continue
      for (let k = 0; k < 15; k++) {
        if (m[k] !== '1') continue
        const xx = i * 4 + (k % 3) + 1, yy = Math.floor(k / 3) + 1
        t.fillStyle = '#000'; t.fillRect(xx + 1, yy + 1, 1, 1)
        t.fillStyle = color; t.fillRect(xx, yy, 1, 1)
      }
    }
    return c
  })
}

/** The HUD strip, 10 px tall, along the bottom of the screen. */
export function drawHud(world, x) {
  const p = world.p, W = world.W, y = world.H - 10, spr = world.spr
  x.fillStyle = p.hud[0]; x.fillRect(0, y, W, 10)
  x.fillStyle = p.hud[4]; x.fillRect(0, y, W, 1)
  let cx = 6
  for (let i = 0; i < 3; i++) { x.drawImage(i < world.hearts ? spr.heart : spr.heartOff, cx, y + 2); cx += 9 }
  cx += 6
  x.drawImage(spr.coinHud, cx, y + 1); cx += 10
  const coins = pixelText('x' + String(world.coinsGot % 100).padStart(2, '0'), p.hud[3])
  x.drawImage(coins, cx, y + 2); cx += coins.width + 6
  const score = pixelText('SCORE ' + String(world.score % 1000000).padStart(6, '0'), p.hud[1])
  const demo = pixelText('DEMO PLAY', p.hud[3])
  const stage = pixelText('WORLD 1-1', p.hud[1])
  const right = W - 6 - demo.width
  if ((world.frame % 70) < 48) x.drawImage(demo, right, y + 2)
  const sx = Math.round(W / 2 - score.width / 2)
  if (sx > cx + 8 && sx + score.width < right - 8) x.drawImage(score, sx, y + 2)
  if (W > 420 && cx + 14 + stage.width < sx - 12) x.drawImage(stage, cx + 14, y + 2)
}
