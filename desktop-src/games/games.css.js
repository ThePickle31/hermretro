import { DISPLAY, MONO } from '../styles/tokens.js'

export const GAMES_CSS = `
/* games: Shelf of real cartridges */
.cs-dev { align-items: center; background: var(--ui-bg-quaternary); display: flex; flex-wrap: wrap; gap: 8px 14px; padding: 11px 14px; }
.cs-dev .dot { background: var(--ui-text-quaternary); flex: none; height: 8px; width: 8px; }
.cs-dev.on .dot { background: var(--ui-green); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-green) 22%, transparent); }
.cs-dev .nm { color: var(--ui-text-primary); font-weight: 600; }
.cs-shelf { display: grid; gap: clamp(18px, 2.2cqi, 36px) clamp(16px, 2cqi, 30px); grid-template-columns: repeat(auto-fill, minmax(min(100%, clamp(200px, 15cqi, 300px)), 1fr)); }
.cs-gcard { display: grid; gap: 10px; grid-template-rows: auto 1fr auto; min-width: 0; }
.cs-cart { all: unset; aspect-ratio: 299 / 340; container-type: inline-size; cursor: pointer; display: block; position: relative; transition: transform .16s ease; width: 100%; }
.cs-cart::before { background: var(--cs-cart) center / 100% 100% no-repeat; content: ''; inset: 0; position: absolute; }
.cs-gcard:hover .cs-cart, .cs-cart:focus-visible { transform: translateY(-5px) rotate(-1deg); }
.cs-cart:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 4px; }
.cs-cart .slot { border-radius: 1.5cqw; display: grid; height: 56.76%; left: 13.38%; overflow: hidden; place-items: center; position: absolute; top: 28.82%; width: 73.24%; }
.cs-cart .slot img { display: block; height: 100%; image-rendering: pixelated; object-fit: cover; width: 100%; }
.cs-cart .ph { align-content: center; background: var(--ui-bg-elevated); color: var(--ui-text-tertiary); display: grid; font: 700 5cqw/1.3 ${MONO}; gap: 3cqw; height: 100%; letter-spacing: .06em; padding: 6cqw; text-align: center; text-transform: uppercase; width: 100%; }
.cs-cart .ph small { color: var(--ui-text-quaternary); font-size: 3.6cqw; }
.cs-cart .hov { display: grid; inset: 0; opacity: 0; place-items: center; position: absolute; transition: opacity .15s; }
.cs-gcard:hover .cs-cart .hov, .cs-cart:focus-visible .hov { opacity: 1; }
.cs-cart .hov span { background: var(--ui-accent); border-radius: 50%; color: var(--ui-bg-editor); display: grid; height: 18cqw; place-items: center; width: 18cqw; }
.cs-cart.ghost::before { filter: grayscale(1); opacity: .28; }
.cs-cart.ghost .slot { color: var(--ui-text-secondary); }
.cs-gcard .info { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.cs-gcard h3 { font: 700 20px/1 ${DISPLAY}; letter-spacing: .03em; margin: 0; overflow: hidden; text-overflow: ellipsis; text-transform: uppercase; white-space: nowrap; }
.cs-gtag { color: var(--ui-text-secondary); font-size: 12px; line-height: 1.4; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-meta { color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font: 11px ${MONO}; gap: 4px 12px; }
.cs-gtag.none { color: var(--ui-text-quaternary); font-style: italic; }
.cs-gtag.bad { color: var(--ui-red); }
.cs-gline { align-items: center; color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font: 11px ${MONO}; gap: 4px 12px; min-height: 18px; }
.cs-gst { align-items: center; display: inline-flex; font: 700 10px/1 ${MONO}; gap: 6px; letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; }
.cs-gst i { background: currentColor; border-radius: 50%; height: 7px; width: 7px; }
.cs-gst.good { color: var(--ui-green); } .cs-gst.warn { color: var(--ui-yellow); } .cs-gst.bad { color: var(--ui-red); } .cs-gst.quiet { color: var(--ui-text-tertiary); }
.cs-cart .nocover { align-items: center; background: color-mix(in srgb, black 72%, transparent); border-radius: 1cqw; bottom: 17.5%; color: white; display: inline-flex; font: 700 3.4cqw/1 ${MONO}; gap: 1.4cqw; letter-spacing: .08em; padding: 1.4cqw 2.2cqw; position: absolute; right: 16%; text-transform: uppercase; }
.cs-split { display: inline-flex; position: relative; }
.cs-split > button, .cs-split > span > button { align-items: center; appearance: none; border: 1px solid transparent; cursor: pointer; display: inline-flex; font: 500 12.5px/1 inherit; gap: 6px; height: 30px; padding: 0 12px; white-space: nowrap; }
.cs-split .main { border-radius: 6px 0 0 6px; }
.cs-split .caret { border-radius: 0 6px 6px 0; padding: 0 8px; }
.cs-split .solid { background: var(--ui-accent); color: var(--ui-bg-editor); }
.cs-split .caret.solid { border-left-color: color-mix(in srgb, var(--ui-bg-editor) 35%, transparent); }
.cs-split .solid:hover:not(:disabled) { filter: brightness(1.08); }
.cs-split .outline { background: transparent; border-color: var(--ui-stroke-secondary); color: var(--ui-text-primary); }
.cs-split .caret.outline { border-left-width: 0; }
.cs-split .outline:hover:not(:disabled) { background: var(--ui-bg-quaternary); }
.cs-split button:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-split button:disabled { cursor: default; opacity: .6; }
.cs-gmenu { animation: cs-b-in .1s ease-out; background: linear-gradient(var(--ui-bg-tertiary, var(--ui-bg-secondary)), var(--ui-bg-tertiary, var(--ui-bg-secondary))), var(--ui-bg-editor); border-radius: 8px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 12px 30px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; gap: 1px; left: 0; min-width: 230px; padding: 4px; position: absolute; top: calc(100% + 6px); z-index: 40; }
.cs-gmenu button { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 5px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; font-size: 12.5px; gap: 9px; outline: none; padding: 7px 9px; text-align: left; white-space: nowrap; }
.cs-gmenu button:hover:not(:disabled), .cs-gmenu button:focus-visible { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-gmenu button:disabled { color: var(--ui-text-quaternary); cursor: default; }
.cs-gmenu em { color: var(--ui-text-quaternary); font-size: 11px; font-style: normal; margin-left: auto; padding-left: 12px; }
.cs-hwchip { align-items: center; appearance: none; background: transparent; border: 1px solid var(--ui-stroke-tertiary); border-radius: 999px; color: var(--ui-text-secondary); display: inline-flex; font: 700 10.5px/1 ${MONO}; gap: 8px; letter-spacing: .08em; padding: 7px 11px; text-transform: uppercase; white-space: nowrap; }
button.cs-hwchip { cursor: pointer; }
button.cs-hwchip:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-hwchip i { background: var(--ui-text-quaternary); border-radius: 50%; height: 7px; width: 7px; }
.cs-hwchip.on i { background: var(--ui-green); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-green) 22%, transparent); }
.cs-empty { align-items: start; display: grid; gap: 48px; grid-template-columns: minmax(0, 560px) minmax(0, 1fr); }
.cs-empty > .cs-col { gap: 16px; }
.cs-empty > .cs-art { max-width: 340px; }
`
