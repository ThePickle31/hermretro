// Drawing a sprite frame as GB Studio places its tiles (page/pages/build/assets/sprite.js): x = 0 is the left of
// the canvas's middle 16 pixels, so a 32-pixel metasprite's first column (x = -8) lands at the canvas's left edge,
// mirrored or not.
import assert from 'node:assert/strict'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

registerAliases()

const { drawSpriteFrame, spriteOriginX } = await import('#pages/build/assets/sprite.js')

/** The canvas left of each tile drawSpriteFrame draws (at scale 1, before its own mirroring). */
function tileLefts(tiles, options) {
  const lefts = []
  const context = {
    drawImage() {},
    restore() {},
    save() {},
    scale() {},
    translate(x) {
      lefts.push(x)
    }
  }

  drawSpriteFrame(context, {}, tiles, { height: 32, left: 0, scale: 1, top: 0, ...options })

  return lefts
}

const WIDE = [-8, 0, 8, 16].map(x => ({ sliceX: x + 8, sliceY: 0, x, y: 0 }))

test('spriteOriginX() is GB Studio\'s canvas origin', () => {
  assert.equal(spriteOriginX(8), 0)
  assert.equal(spriteOriginX(16), 0)
  assert.equal(spriteOriginX(32), 8)
  assert.equal(spriteOriginX(64), 24)
})

test('a 32-pixel frame fills its canvas from the left edge', () => {
  assert.deepEqual(tileLefts(WIDE, { width: 32 }), [0, 8, 16, 24])
})

test('a mirrored 32-pixel frame flips about the canvas, staying inside it', () => {
  // Mirrored tiles are drawn from their right edge (translate + 8, then scale -1).
  assert.deepEqual(tileLefts(WIDE, { flip: true, width: 32 }), [32, 24, 16, 8])
})

test('a 16-pixel frame is drawn as before', () => {
  assert.deepEqual(tileLefts([{ x: 0, y: 0 }, { x: 8, y: 0 }], { width: 16 }), [0, 8])
})
