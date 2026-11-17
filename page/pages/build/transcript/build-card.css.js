import { MONO } from '#shared/styles/tokens.js'

export const BUILD_CARD_CSS = `
/* the build card (a turn that built the game, or reported what it did) */
.cs-b-bc { animation: cs-b-in .2s ease-out; background: var(--ui-bg-secondary); border-radius: 12px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.cs-b-bc.bad { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-red) 45%, transparent); }
.cs-b-bc-head { align-items: center; display: flex; flex-wrap: wrap; gap: 6px 10px; min-height: 30px; padding: 11px 14px 4px 16px; }
.cs-b-bc-title { color: var(--ui-text-primary); font-size: 14.5px; font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
.cs-b-bc-meta { font-size: 11.5px; white-space: nowrap; }
.cs-b-bn { background: var(--ui-accent); border-radius: 5px; color: var(--ui-bg-editor); flex: none; font: 700 10.5px/1 ${MONO}; padding: 4px 6px; }
.cs-b-bn.old { background: var(--ui-bg-quaternary); color: var(--ui-text-tertiary); }
.cs-b-bn.bad { background: color-mix(in srgb, var(--ui-red) 22%, transparent); color: var(--ui-red); }
.cs-b-bn.live { background: transparent; box-shadow: inset 0 0 0 1px var(--ui-accent); color: var(--ui-accent); }
.cs-b-bc-sum { color: var(--ui-text-primary); line-height: 1.6; margin: 0; padding: 2px 16px 12px; }
.cs-b-bc-changes { border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; font-size: 12.5px; gap: 6px; list-style: none; margin: 0; padding: 10px 16px 12px; }
.cs-b-bc-changes li { align-items: center; color: var(--ui-text-secondary); display: flex; gap: 8px; min-width: 0; }
.cs-b-bc-mark { color: var(--ui-accent); flex: none; font: 700 12px ${MONO}; text-align: center; width: 10px; }
.cs-b-bc-changes li[data-kind='added'] .cs-b-bc-mark { color: var(--ui-green); }
.cs-b-bc-changes li[data-kind='removed'] .cs-b-bc-mark { color: var(--ui-text-quaternary); }
.cs-b-bc-foot { align-items: center; background: color-mix(in srgb, var(--ui-bg-editor) 45%, transparent); border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; font-size: 12px; gap: 6px 14px; padding: 8px 16px; }
.cs-b-bc-foot .cs-b-link { align-items: center; display: inline-flex; gap: 3px; }
.cs-b-ok { color: var(--ui-green); font-weight: 700; }
.cs-b-bc-details { border-top: 1px solid var(--ui-stroke-tertiary); display: grid; font-size: 12.5px; gap: 12px 20px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); padding: 10px 16px 14px; }
.cs-b-bc-details p { line-height: 1.45; margin: 5px 0 0; }
.cs-b-bc-details pre { margin: 6px 0 0; white-space: pre-wrap; }
.cs-b-ba { border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; gap: 10px; padding: 12px 16px; }
.cs-b-ba-pair { align-items: center; display: flex; gap: 16px; justify-content: center; }
.cs-b-ba-side { align-items: center; appearance: none; background: none; border: 0; color: inherit; cursor: zoom-in; display: flex; flex-direction: column; font: inherit; gap: 6px; min-width: 0; padding: 0; }
.cs-b-ba-img { align-items: center; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 12px 12px; border-radius: 9px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); box-sizing: border-box; display: flex; height: clamp(90px, 13cqi, 150px); justify-content: center; max-width: 100%; padding: 8px; width: clamp(110px, 17cqi, 190px); }
.cs-b-ba-side:not(.now) .cs-b-ba-img { opacity: .72; }
.cs-b-ba-side.now .cs-b-ba-img { box-shadow: inset 0 0 0 2px var(--ui-accent); }
.cs-b-ba-img img, .cs-b-ba-img .cs-b-spr { height: 100%; image-rendering: pixelated; max-height: 100%; max-width: 100%; object-fit: contain; width: auto; }
.cs-b-ba-cap { color: var(--ui-text-tertiary); font-size: 11.5px; }
.cs-b-ba-side.now .cs-b-ba-cap { color: var(--ui-text-primary); font-weight: 600; }
.cs-b-ba-arrow { color: var(--ui-accent); flex: none; font-size: 20px; }
.cs-b-ba-acts { gap: 8px; }
/* next steps (a reply's suggestions, New Game's ideas) and the @ hint */
.cs-b-next-steps, .cs-b-ideas { display: flex; flex-wrap: wrap; gap: 8px; }
.cs-b-ideas { justify-content: center; }
.cs-b-sugg-chip { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12.5px; gap: 5px; padding: 5px 12px; transition: box-shadow .12s ease, color .12s ease; }
.cs-b-sugg-chip:hover:not(:disabled) { box-shadow: inset 0 0 0 1px var(--ui-accent); color: var(--ui-text-primary); }
.cs-b-sugg-chip:disabled { cursor: default; opacity: .5; }
.cs-b-sugg-chip > i { color: var(--ui-accent); }
.cs-b-hint { align-items: center; border: 1px dashed var(--ui-stroke-secondary); border-radius: 12px; color: var(--ui-text-tertiary); display: flex; font-size: 12.5px; gap: 12px; line-height: 1.45; padding: 10px 14px; }
.cs-b-hint b { color: var(--ui-text-primary); }
.cs-b-hint-tiles { display: flex; flex: none; gap: 5px; }
.cs-b-hint-tiles i { background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, transparent 0 50%) 0 0 / 8px 8px; border-radius: 6px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); height: 26px; width: 26px; }
.cs-b-hint-tiles i:nth-child(2) { opacity: .6; } .cs-b-hint-tiles i:nth-child(3) { opacity: .35; }
`
