// The platformer: a Game Boy Color style level where the Nous Girl plays by herself (no ROM). The level is built
// for the page area's size, its sky follows the theme (day on a light page, night on a dark one), and it shows one
// still frame under reduced motion. The running is in run.js, the game in world.js.
import { PLATFORMER_CSS } from './platformer.css.js'
import { runAttract } from './run.js'
import { World } from './world.js'

export const PLATFORMER = {
  id: 'platformer',
  css: [PLATFORMER_CSS],
  start({ host, layer, env }) {
    // the page tests' jsdom has no 2D canvas
    if (typeof CanvasRenderingContext2D !== 'function') {
      return () => {}
    }

    const canvas = layer.ownerDocument.createElement('canvas')
    layer.append(canvas)
    const stop = runAttract({ host, canvasEl: canvas, makeWorld: seed => new World(seed), env, seed: 1 + Math.floor(Math.random() * 1e6) })

    return () => {
      stop()
      canvas.remove()
    }
  }
}
