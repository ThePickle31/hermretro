import { MONO } from '#shared/styles/tokens.js'

export const CART_SHELF_CSS = `
/* New Game shelf: the games being worked on, standing on the level's floor (--cs-at-ground, from attract/run.js) */
.cs-b-attract > .cs-b-shelf, .cs-b-attract > .cs-b-shelf-probe { position: absolute; }
.cs-b-shelf-probe { height: 0; width: 0; }
.cs-b-shelf { align-items: flex-end; bottom: var(--cs-at-ground, 48px); display: flex; gap: 26px; left: 50%; pointer-events: none; transform: translateX(-50%); }
.cs-b-attract:has(> .cs-b-shelf) .cs-b-new { padding-bottom: calc(var(--cs-at-ground, 48px) + 168px); }
/* the form's menus (the model picker) open over the shelf: the form comes forward only while one is open, so the
   cartridges stay clickable the rest of the time */
.cs-b-attract:has(.cs-b-mp-pop) > .cs-b-new { z-index: 2; }
.cs-b-shelf-cart { align-items: center; display: flex; flex-direction: column; gap: 3px; pointer-events: auto; text-align: center; width: 100px; }
.cs-b-shelf-cart .cs-cart { filter: drop-shadow(0 6px 6px color-mix(in srgb, black 45%, transparent)); width: 100px; }
.cs-b-shelf-cart .cs-cart:hover, .cs-b-shelf-cart .cs-cart:focus-visible { transform: translateY(-10px) rotate(-2deg); }
.cs-b-shelf-cart b, .cs-b-shelf-cart small { background: color-mix(in srgb, var(--cs-at-bg, var(--ui-bg-editor)) 80%, transparent); max-width: 120px; overflow: hidden; padding: 0 6px; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-shelf-cart b { color: var(--ui-text-primary); font-size: 12px; font-weight: 600; }
.cs-b-shelf-cart:has(.cs-cart:hover) b, .cs-b-shelf-cart:has(.cs-cart:focus-visible) b { color: var(--ui-accent); }
.cs-b-shelf-cart small { align-items: center; color: var(--ui-text-secondary); display: inline-flex; font-size: 10.5px; gap: 5px; }
.cs-b-shelf-cart.wait small { color: var(--ui-yellow); }
.cs-b-shelf-cart small .dot { border-radius: 50%; flex: none; height: 7px; width: 7px; }
.cs-b-shelf-cart small .dot.wait { background: var(--ui-yellow); }
.cs-b-shelf-cart small .dot.new { background: var(--ui-accent); }
.cs-b-shelf-cart small .cs-b-spin { height: 8px; width: 8px; }
.cs-b-shelf-more { align-items: center; aspect-ratio: 299 / 340; background: color-mix(in srgb, var(--cs-at-bg, var(--ui-bg-editor)) 55%, transparent); border: 2px dashed var(--ui-text-quaternary, var(--ui-text-tertiary)); border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; display: grid; font: 700 18px ${MONO}; justify-content: center; width: 100px; }
.cs-b-shelf-more:hover, .cs-b-shelf-more:focus-visible { border-color: var(--ui-accent); color: var(--ui-accent); }
.cs-b-shelf-more:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 4px; }
`
