import { MONO } from '#shared/styles/tokens.js'

// The game inside a build card: the resting play card, and the inline player (`cs-ip-*`): one bar,
// the game at a whole-number scale, the play-test or annotate panel beside it (under it when narrow).
export const INLINE_PLAYER_CSS = `
/* the game, resting under the newest build: its screen at twice its size in a dark frame, Play at the corner */
.cs-b-pc { animation: cs-b-in .2s ease-out; display: flex; flex-direction: column; gap: 6px; max-width: 560px; transition: opacity .2s ease; }
.cs-b-pc-stage { align-items: center; background: color-mix(in srgb, var(--ui-bg-editor) 55%, black); border-radius: 12px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); display: flex; justify-content: center; padding: 16px; position: relative; }
.cs-b-pc.busy .cs-b-pc-stage, .cs-b-pc.unplayable .cs-b-pc-stage { opacity: .62; }
.cs-b-pc-screen { appearance: none; background: none; border: 0; cursor: pointer; display: block; padding: 0; width: min(320px, 100%); }
.cs-b-pc-screen:disabled { cursor: default; }
.cs-b-pc-img { aspect-ratio: 160 / 144; border-radius: 3px; display: block; image-rendering: pixelated; object-fit: cover; width: 100%; }
.cs-b-pc-go { align-items: center; appearance: none; backdrop-filter: blur(6px); background: color-mix(in srgb, white 14%, transparent); border: 0; border-radius: 999px; bottom: 12px; color: white; cursor: pointer; display: inline-flex; font: inherit; font-size: 12.5px; gap: 6px; padding: 6px 13px; position: absolute; right: 12px; transition: background .12s ease; }
.cs-b-pc-go:hover { background: color-mix(in srgb, white 24%, transparent); }
.cs-b-pc-wait { bottom: 12px; color: var(--ui-text-tertiary); font-size: 12px; position: absolute; right: 14px; }
.cs-b-pc-note { border-left: 2px solid var(--ui-stroke-secondary); color: var(--ui-text-secondary); font-size: 12.5px; line-height: 1.45; margin: 0; padding-left: 10px; }
.cs-b-old { color: var(--ui-text-quaternary); font-size: 11.5px; margin: 0; }
.cs-b-live { background: var(--ui-text-quaternary); border-radius: 50%; flex: none; height: 7px; transition: background .2s ease; width: 7px; }
.cs-b-live.on { animation: cs-b-pulse 1.6s infinite; background: var(--ui-green); }

/* the inline player */
.cs-ip { animation: cs-b-in .22s ease-out; background: color-mix(in srgb, var(--ui-bg-editor) 70%, black); border-radius: 12px; box-shadow: 0 0 0 1px color-mix(in srgb, var(--ui-accent) 55%, transparent), 0 14px 36px color-mix(in srgb, black 35%, transparent); container-type: inline-size; display: flex; flex-direction: column; overflow: hidden; }
.cs-ip-bar { align-items: center; background: var(--ui-bg-secondary); border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 4px; min-height: 40px; padding: 5px 8px 5px 12px; white-space: nowrap; }
.cs-ip-bar.annotating { background: color-mix(in srgb, var(--ui-accent) 14%, var(--ui-bg-secondary)); }
.cs-ip-title { font-size: 12.5px; margin-left: 4px; overflow: hidden; text-overflow: ellipsis; }
.cs-ip-hint { font-size: 12px; margin-left: 6px; overflow: hidden; text-overflow: ellipsis; }
.cs-ip-hint.marked { color: var(--ui-accent); font-weight: 600; }
.cs-ip-ann-ic { color: var(--ui-accent); display: inline-flex; }
.cs-ip-sep { background: var(--ui-stroke-secondary); height: 16px; margin: 0 4px; width: 1px; }
.cs-ip-btn { align-items: center; background: none; border: 0; border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; display: inline-flex; flex: none; font: inherit; font-size: 12px; gap: 5px; height: 28px; padding: 0 7px; }
.cs-ip-btn:hover:not(:disabled) { background: var(--ui-bg-tertiary); color: var(--ui-text-primary); }
.cs-ip-btn:disabled { cursor: default; opacity: .45; }
.cs-ip-btn[aria-pressed=true] { background: color-mix(in srgb, var(--ui-accent) 18%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 55%, transparent); color: var(--ui-text-primary); }
.cs-ip-btn.primary { background: var(--ui-accent); color: white; }
.cs-ip-btn.primary:hover:not(:disabled) { background: color-mix(in srgb, var(--ui-accent) 85%, white); color: white; }
.cs-ip-seg { border: 1px solid var(--ui-stroke-secondary); border-radius: 7px; display: inline-flex; flex: none; overflow: hidden; }
.cs-ip-seg button { background: none; border: 0; color: var(--ui-text-secondary); cursor: pointer; font: 600 11px ${MONO}; height: 24px; padding: 0 7px; }
.cs-ip-seg button[aria-checked=true] { background: var(--ui-accent); color: white; }
.cs-ip-seg button:disabled { cursor: default; opacity: .4; }
.cs-ip-menu { flex: none; position: relative; }
.cs-ip-pop { background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 9px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 12px 30px color-mix(in srgb, black 35%, transparent); display: flex; flex-direction: column; min-width: 170px; padding: 4px; position: absolute; right: 0; top: calc(100% + 6px); z-index: 20; }
.cs-ip-pop-row { align-items: center; background: none; border: 0; border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; font-size: 12.5px; gap: 8px; padding: 6px 8px; text-align: left; }
.cs-ip-pop-row:hover { background: var(--ui-bg-tertiary); color: var(--ui-text-primary); }
.cs-ip-pop-row > span { flex: 1; }
.cs-ip-swatch { border-radius: 4px; box-shadow: inset 0 0 0 1px color-mix(in srgb, white 25%, transparent); display: block; height: 14px; width: 14px; }
.cs-ip-body { display: flex; min-height: 0; }
.cs-ip-stage { align-items: center; background: radial-gradient(ellipse at center, color-mix(in srgb, var(--ui-bg-editor) 85%, black), color-mix(in srgb, var(--ui-bg-editor) 55%, black) 75%); display: flex; flex: 1; flex-direction: column; justify-content: center; min-width: 0; padding: 16px; }
.cs-ip-screen { flex: none; max-width: 100%; position: relative; }
.cs-ip-screen[data-view=screen] { border-radius: 4px; box-shadow: 0 0 0 1px color-mix(in srgb, white 8%, transparent), 0 20px 50px color-mix(in srgb, black 55%, transparent); overflow: hidden; }
.cs-ip-screen:fullscreen { align-items: center; background: black; border-radius: 0; display: flex; height: 100%; justify-content: center; width: 100%; }
.cs-ip-fit { flex: none; max-width: 100%; }
.cs-ip-fit .cs-rp-stage, .cs-ip-fit .cs-rp-stage:not(.off) { height: 100%; width: 100%; }
.cs-ip-panel { background: var(--ui-bg-secondary); border-left: 1px solid var(--ui-stroke-tertiary); display: flex; flex: none; flex-direction: column; gap: 4px; font-size: 12.5px; overflow-y: auto; padding: 12px 14px; width: 300px; }
.cs-ip-panel.tabs { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); padding-top: 0; width: auto; }
.cs-ip-sec { display: flex; flex-direction: column; gap: 6px; }
.cs-ip-sh { align-items: center; color: var(--ui-text-quaternary); display: flex; font: 700 10px ${MONO}; justify-content: space-between; letter-spacing: .08em; margin-top: 10px; text-transform: uppercase; }
.cs-ip-sec:first-child .cs-ip-sh, .cs-ip-panel > .cs-ip-sh:first-child { margin-top: 0; }
.cs-ip-count { color: var(--ui-green); }
.cs-ip-note { color: var(--ui-text-secondary); line-height: 1.45; margin: 0; }
.cs-ip-checks, .cs-ip-marks { display: flex; flex-direction: column; gap: 8px; list-style: none; margin: 0; padding: 0; }
.cs-ip-check label { align-items: flex-start; color: var(--ui-text-secondary); cursor: pointer; display: flex; gap: 8px; }
.cs-ip-check input { accent-color: var(--ui-accent); flex: none; margin: 2px 0 0; }
.cs-ip-check label > span { display: flex; flex-direction: column; gap: 1px; }
.cs-ip-check em { font-size: 11px; font-style: normal; }
.cs-ip-check[data-state=done] .cs-ip-check-text { color: var(--ui-text-quaternary); text-decoration: line-through; }
.cs-ip-check[data-state=untested] em { color: var(--ui-yellow); }
.cs-ip-check[data-state=reported] em { color: var(--ui-accent); }
.cs-ip-check[data-state=fixed] em { color: var(--ui-green); }
.cs-ip-ask { background: color-mix(in srgb, var(--ui-yellow) 7%, transparent); border-radius: 8px; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 40%, transparent); color: var(--ui-text-secondary); display: flex; flex-direction: column; gap: 6px; margin: 6px 0 0 22px; padding: 8px; }
.cs-ip-keys { background: var(--ui-bg-secondary); border-top: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-quaternary); display: flex; flex-wrap: wrap; font-size: 11px; gap: 14px; padding: 6px 12px; }
.cs-ip-keys.stacked { background: none; border: 0; flex-direction: column; gap: 5px; padding: 0; }
.cs-ip-keys kbd { border: 1px solid var(--ui-stroke-secondary); border-bottom-width: 2px; border-radius: 3px; color: var(--ui-text-tertiary); font: 600 10px ${MONO}; padding: 0 4px; }
.cs-ip-moment { flex-wrap: wrap; gap: 4px; }
.cs-ip-tabs { border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; margin: 0 -14px 8px; padding: 0 6px; }
.cs-ip-tabs button { background: none; border: 0; color: var(--ui-text-secondary); cursor: pointer; font: inherit; font-size: 12px; padding: 8px 10px; }
.cs-ip-tabs button[aria-selected=true] { box-shadow: inset 0 -2px var(--ui-accent); color: var(--ui-text-primary); }
.cs-ip-fold { align-items: center; background: var(--ui-bg-secondary); border: 0; border-left: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-secondary); cursor: pointer; display: flex; flex: none; flex-direction: column; gap: 10px; padding: 12px 0; width: 34px; }
.cs-ip-fold:hover { color: var(--ui-text-primary); }
.cs-ip-pill { background: var(--ui-yellow); border-radius: 999px; color: black; font: 700 10px ${MONO}; padding: 2px 5px; }
.cs-ip-pill.ok { background: var(--ui-green); }
.cs-ip-vt { font-size: 12px; writing-mode: vertical-rl; }
.cs-ip-mark { border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: flex; flex-direction: column; gap: 8px; padding: 8px; }
.cs-ip-mark-head { align-items: center; display: flex; gap: 8px; }
.cs-ip-n { background: var(--ui-accent); border-radius: 50%; color: white; display: grid; flex: none; font: 700 10.5px ${MONO}; height: 18px; place-items: center; width: 18px; }
.cs-ip-crop { border-radius: 5px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary); flex: none; height: 44px; image-rendering: pixelated; object-fit: contain; width: 44px; }
.cs-ip-mark-name { display: flex; flex: 1; flex-direction: column; min-width: 0; }
.cs-ip-mark-name span { font-size: 11px; }
.cs-ip-colors { align-items: center; display: flex; gap: 6px; }
.cs-ip-swatch-in { border-radius: 6px; cursor: pointer; display: block; height: 24px; position: relative; width: 24px; }
.cs-ip-swatch-in i { border-radius: 6px; box-shadow: inset 0 0 0 1px color-mix(in srgb, white 22%, transparent); display: block; height: 100%; width: 100%; }
.cs-ip-swatch-in.changed { outline: 2px solid var(--ui-accent); outline-offset: 1px; }
.cs-ip-swatch-in input { cursor: pointer; height: 100%; inset: 0; opacity: 0; position: absolute; width: 100%; }
.cs-ip-mark-note { background: var(--ui-bg-editor); border: 1px solid var(--ui-stroke-secondary); border-radius: 7px; color: var(--ui-text-primary); font: inherit; font-size: 12.5px; padding: 6px 8px; resize: vertical; }
.cs-ip-mark-note:focus { border-color: var(--ui-accent); outline: none; }
.cs-b-bc > .cs-ip, .cs-b-bc > .cs-b-pc { margin: 0 12px 12px; }
@container (max-width: 640px) { .cs-ip-lbl, .cs-ip-hint { display: none; } }
@media (prefers-reduced-motion: reduce) { .cs-ip, .cs-b-pc, .cs-b-live.on { animation: none; } }
`
