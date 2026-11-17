export const VIEWER_CSS = `
/* the asset viewer */
.cs-b-dim { align-items: center; animation: cs-b-fade .15s ease-out; background: color-mix(in srgb, var(--ui-bg-editor) 78%, transparent); backdrop-filter: blur(3px); display: flex; inset: 0; justify-content: center; padding: 20px; position: absolute; z-index: 20; }
@keyframes cs-b-fade { from { opacity: 0; } }
.cs-b-lb { animation: cs-b-in .18s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 14px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 24px 60px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; max-height: 100%; max-width: 640px; outline: none; overflow: hidden; width: 100%; }
.cs-b-lb-top { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 10px; min-width: 0; padding: 10px 14px; }
.cs-b-ell { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-lb-body { display: flex; flex-wrap: wrap; gap: 16px; overflow: auto; padding: 16px; }
.cs-b-stage { align-items: center; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 16px 16px; border-radius: 10px; display: flex; flex: none; height: 240px; justify-content: center; width: 240px; }
.cs-b-stage canvas { image-rendering: pixelated; max-height: 228px; max-width: 228px; }
.cs-b-lb-side { display: flex; flex: 1; flex-direction: column; gap: 12px; min-width: 200px; }
.cs-b-frames { display: grid; gap: 6px; grid-template-columns: repeat(auto-fill, minmax(44px, 1fr)); }
.cs-b-frames button { align-items: center; appearance: none; aspect-ratio: 1; background: var(--ui-bg-quaternary); border: 0; border-radius: 6px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); cursor: pointer; display: flex; justify-content: center; padding: 2px; }
.cs-b-frames button[aria-pressed='true'] { box-shadow: inset 0 0 0 2px var(--ui-accent); }
.cs-b-frames canvas { image-rendering: pixelated; max-height: 100%; max-width: 100%; }
.cs-b-pal { display: flex; flex-wrap: wrap; gap: 4px; }
.cs-b-pal i { border-radius: 4px; box-shadow: inset 0 0 0 1px color-mix(in srgb, black 25%, transparent); height: 22px; width: 22px; }
.cs-b-lb-foot { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 14px; }
.cs-b-x { align-items: center; appearance: none; background: none; border: 0; border-radius: 4px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; padding: 3px; }
.cs-b-x:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-v { animation: cs-b-in .18s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 14px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 24px 60px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; height: min(760px, 100%); max-width: 1180px; outline: none; overflow: hidden; width: 100%; }
.cs-v-top { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 8px 10px; min-width: 0; padding: 9px 12px 9px 14px; }
.cs-v-name { flex: none; max-width: 28ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-v-top .cs-b-ell { flex: 1 1 120px; min-width: 0; }
.cs-v-seg { background: var(--ui-bg-editor); border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); display: inline-flex; gap: 2px; padding: 2px; }
.cs-v-seg button { appearance: none; background: none; border: 0; border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; font: inherit; font-size: 12px; padding: 3px 11px; white-space: nowrap; }
.cs-v-seg button:hover { color: var(--ui-text-primary); }
.cs-v-seg button.on { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); font-weight: 600; }
.cs-v-zoom { align-items: center; display: inline-flex; gap: 4px; }
.cs-v-chip { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 99px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); cursor: pointer; display: inline-flex; font: inherit; font-size: 11.5px; gap: 4px; line-height: 1.5; padding: 1px 9px; white-space: nowrap; }
.cs-v-chip:hover { color: var(--ui-text-primary); }
.cs-v-chip.on { background: var(--ui-accent); box-shadow: none; color: var(--ui-bg-editor); }
.cs-v-chip.quiet { cursor: default; }
.cs-v-body { display: grid; flex: 1; grid-template-columns: minmax(0, 1fr) 300px; min-height: 0; }
.cs-v-stage { background: var(--ui-bg-editor); min-height: 0; min-width: 0; overflow: hidden; position: relative; }
.cs-v-stage.checker { background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 16px 16px; }
.cs-v-scroll { inset: 0; overflow: auto; position: absolute; }
.cs-v-scroll.pannable { cursor: grab; }
.cs-v-scroll.pannable:active { cursor: grabbing; }
.cs-v-stage-in { align-items: center; box-sizing: border-box; display: flex; justify-content: center; min-height: 100%; min-width: 100%; padding: 44px 24px 64px; width: max-content; }
.cs-v-canvas { flex: none; position: relative; }
.cs-v-canvas canvas, .cs-v-px { display: block; image-rendering: pixelated; }
.cs-v-canvas.picking { cursor: crosshair; touch-action: none; }
.cs-v-grid { background-image: linear-gradient(color-mix(in srgb, white 22%, transparent) 1px, transparent 1px), linear-gradient(90deg, color-mix(in srgb, white 22%, transparent) 1px, transparent 1px); inset: 0; mix-blend-mode: difference; pointer-events: none; position: absolute; }
.cs-v-area { background: color-mix(in srgb, var(--ui-yellow) 10%, transparent); border: 2px dashed var(--ui-yellow); border-radius: 3px; box-sizing: border-box; pointer-events: none; position: absolute; }
.cs-v-area em { background: var(--ui-yellow); border-radius: 99px; color: black; font-size: 11px; font-style: normal; left: -2px; padding: 1px 8px; position: absolute; top: -24px; white-space: nowrap; }
.cs-v-float { align-items: center; display: flex; flex-wrap: wrap; gap: 5px; max-width: calc(100% - 24px); position: absolute; z-index: 1; }
.cs-v-float.tl { left: 12px; top: 10px; }
.cs-v-float.tr { right: 12px; top: 10px; }
.cs-v-float.br { bottom: 10px; right: 12px; }
.cs-v-float.bottom { bottom: 12px; justify-content: center; left: 50%; transform: translateX(-50%); }
.cs-v-tl-wide .cs-v-float.tl { max-width: 60%; }
.cs-v-frame { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 6px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); cursor: pointer; display: inline-flex; justify-content: center; min-height: 40px; min-width: 40px; padding: 2px; }
.cs-v-frame.on { box-shadow: inset 0 0 0 2px var(--ui-accent); }
.cs-v-working { align-items: center; background: var(--ui-bg-secondary); border-radius: 10px; bottom: 16px; box-shadow: 0 0 0 1px var(--ui-accent), 0 8px 24px color-mix(in srgb, black 35%, transparent); display: flex; gap: 10px; left: 50%; padding: 8px 14px; position: absolute; transform: translateX(-50%); white-space: nowrap; z-index: 2; }
.cs-v-side { border-left: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; min-height: 0; }
.cs-v-tabs { border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; flex: none; }
.cs-v-tabs button { align-items: center; appearance: none; background: none; border: 0; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; flex: 1; font: inherit; font-size: 12.5px; gap: 6px; justify-content: center; padding: 9px 0; }
.cs-v-tabs button:hover { color: var(--ui-text-primary); }
.cs-v-tabs button.on { box-shadow: inset 0 -2px 0 var(--ui-accent); color: var(--ui-text-primary); font-weight: 600; }
.cs-v-pane { display: flex; flex: 1; flex-direction: column; gap: 14px; min-height: 0; overflow: auto; padding: 14px; }
.cs-v-sec { gap: 6px; }
.cs-v-text { color: var(--ui-text-primary); font-size: 12.5px; line-height: 1.5; overflow-wrap: anywhere; }
.cs-v-quote { color: var(--ui-text-primary); font-size: 12.5px; line-height: 1.5; }
.cs-v-note { background: color-mix(in srgb, var(--ui-yellow) 12%, transparent); border-radius: 8px; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 35%, transparent); color: var(--ui-text-primary); display: flex; flex-direction: column; font-size: 12px; gap: 8px; padding: 9px 10px; }
.cs-v-card { background: var(--ui-bg-quaternary); border-radius: 8px; display: flex; flex-direction: column; gap: 3px; padding: 9px 10px; }
.cs-v-pal { display: inline-flex; }
.cs-v-pal button, .cs-v-sw button { appearance: none; border: 0; box-shadow: inset 0 0 0 1px color-mix(in srgb, black 25%, transparent); cursor: copy; height: 22px; padding: 0; width: 22px; }
.cs-v-pal button:first-child { border-radius: 5px 0 0 5px; }
.cs-v-pal button:last-child { border-radius: 0 5px 5px 0; }
.cs-v-sw { display: flex; flex-wrap: wrap; gap: 4px; }
.cs-v-sw button { border-radius: 4px; height: 19px; width: 19px; }
.cs-v-sw button:hover, .cs-v-pal button:hover { outline: 2px solid var(--ui-accent); outline-offset: 1px; position: relative; }
.cs-v-check { align-items: flex-start; color: var(--ui-text-primary); display: flex; font-size: 12px; gap: 6px; line-height: 1.45; }
.cs-v-check > :first-child { color: var(--ui-green); flex: none; margin-top: 2px; }
.cs-v-check.bad > :first-child { color: var(--ui-yellow); }
.cs-v-step { align-items: center; color: var(--ui-text-primary); display: flex; font-size: 12px; gap: 7px; }
.cs-v-step > :first-child { color: var(--ui-green); flex: none; }
.cs-v-step.failed > :first-child { color: var(--ui-red); }
.cs-v-toggle { align-items: center; color: var(--ui-text-secondary); cursor: pointer; display: flex; font-size: 12px; gap: 7px; }
.cs-v-toggle input { accent-color: var(--ui-accent); margin: 0; }
.cs-v-input { background: var(--ui-bg-editor); border: 0; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-primary); font: inherit; font-size: 13px; line-height: 1.5; min-height: 96px; outline: none; padding: 9px 10px; resize: vertical; }
.cs-v-input:focus { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-v-kbd { margin-left: 6px; opacity: .7; }
.cs-v-foot { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 10px; min-height: 62px; padding: 7px 14px; }
.cs-v-vers { align-items: center; display: flex; gap: 8px; min-width: 0; overflow-x: auto; padding: 3px; }
.cs-v-ver { align-items: center; appearance: none; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 8px 8px; border: 0; border-radius: 5px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); cursor: pointer; display: inline-flex; flex: none; height: 44px; justify-content: center; opacity: .6; overflow: hidden; padding: 0; position: relative; transition: opacity .15s ease; width: 50px; }
.cs-v-ver:hover { opacity: .9; }
.cs-v-ver.on { box-shadow: 0 0 0 2px var(--ui-accent); opacity: 1; }
.cs-v-ver img { height: 100%; image-rendering: pixelated; object-fit: contain; width: 100%; }
.cs-v-ver b { background: color-mix(in srgb, black 70%, transparent); border-radius: 3px; bottom: 2px; color: white; font-size: 9.5px; left: 2px; line-height: 1.3; padding: 0 4px; position: absolute; }
.cs-v-ver .cs-v-now { background: var(--ui-green); border-radius: 50%; box-shadow: 0 0 0 2px var(--ui-bg-secondary); height: 7px; position: absolute; right: 3px; top: 3px; width: 7px; }
.cs-v-ver.pending { background: none; box-shadow: inset 0 0 0 1px var(--ui-accent); cursor: default; opacity: 1; }
.cs-v-ver-ph { background: var(--ui-bg-quaternary); display: block; height: 100%; width: 100%; }
.cs-v-ingame { align-items: center; display: flex; flex-wrap: wrap; gap: 36px; justify-content: center; }
.cs-v-ingame figure { align-items: center; display: flex; flex-direction: column; gap: 8px; margin: 0; }
.cs-v-ingame figcaption { color: var(--ui-text-tertiary); font-size: 12px; }
.cs-v-gcard { background: var(--ui-bg-secondary); border-radius: 12px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary); overflow: hidden; width: 230px; }
.cs-v-gcard img, .cs-v-gcard .cs-v-ver-ph { aspect-ratio: 160 / 144; display: block; height: auto; image-rendering: pixelated; width: 100%; }
.cs-v-device { background: linear-gradient(color-mix(in srgb, var(--ui-accent) 62%, black), color-mix(in srgb, var(--ui-accent) 40%, black)); border-radius: 20px 20px 52px 20px; box-shadow: inset 0 0 0 3px color-mix(in srgb, white 8%, transparent); display: flex; flex-direction: column; height: 350px; padding: 24px 26px; width: 240px; }
.cs-v-device-screen { aspect-ratio: 160 / 144; background: color-mix(in srgb, black 88%, white); border-radius: 9px; box-sizing: content-box; padding: 12px; }
.cs-v-device-screen img { display: block; height: 100%; image-rendering: pixelated; width: 100%; }
.cs-v-device-name { color: color-mix(in srgb, white 82%, var(--ui-accent)); font: 700 12px/1 system-ui, sans-serif; letter-spacing: .18em; margin-top: 12px; text-align: center; }
.cs-v-device-pad { align-items: center; display: flex; justify-content: space-between; margin-top: auto; padding: 0 4px 6px; }
.cs-v-device-pad .dpad { background: linear-gradient(var(--cs-v-dpad), var(--cs-v-dpad)) center / 20px 62px no-repeat, linear-gradient(var(--cs-v-dpad), var(--cs-v-dpad)) center / 62px 20px no-repeat; --cs-v-dpad: color-mix(in srgb, black 86%, white); display: block; height: 62px; width: 62px; }
.cs-v-device-pad span { display: flex; gap: 9px; }
.cs-v-device-pad span i { background: var(--ui-red); border-radius: 50%; display: block; height: 27px; width: 27px; }
.cs-v-device-pad span i:last-child { margin-top: -24px; }
@container (max-width: 820px) {
  .cs-v-body { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(260px, 1fr) minmax(0, auto); }
  .cs-v-side { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); max-height: 46%; }
  .cs-v-zoom, .cs-v-nav { display: none; }
}
@media (prefers-reduced-motion: reduce) { .cs-v { animation: none; } }
`
