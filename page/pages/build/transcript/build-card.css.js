import { MONO } from '#shared/styles/tokens.js'

export const BUILD_CARD_CSS = `
/* a build: one quiet line (number, title, time), what changed under it, what was tested; no box around it */
.cs-b-bc { animation: cs-b-in .2s ease-out; display: flex; flex-direction: column; background: var(--ui-bg-secondary); border: 1px solid var(--ui-stroke-tertiary); border-radius: 10px; box-sizing: border-box; gap: 8px; max-width: 565px; min-width: 0; padding: 10px 12px; }
.cs-b-bc-head { align-items: center; display: flex; flex-wrap: wrap; gap: 4px 10px; min-height: 26px; }
.cs-b-bc-title { color: var(--ui-text-primary); font-size: 13.5px; font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
.cs-b-bc-meta { font-size: 11.5px; white-space: nowrap; }
.cs-b-bn { border-radius: 5px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); flex: none; font: 700 10.5px/1 ${MONO}; padding: 4px 6px; }
.cs-b-bn.old { color: var(--ui-text-tertiary); }
.cs-b-bn.bad { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-red) 55%, transparent); color: var(--ui-red); }
.cs-b-bn.live { box-shadow: inset 0 0 0 1px var(--ui-accent); color: var(--ui-accent); }
.cs-b-bc.bad .cs-b-bc-title { color: var(--ui-red); }
.cs-b-bc-unfinished { border-radius: 5px; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 45%, transparent); color: var(--ui-yellow); flex: none; font-size: 11px; font-weight: 600; padding: 2px 6px; }
.cs-b-bc-unfinished-why .cs-eyebrow { color: var(--ui-yellow); }
.cs-b-bc-sum { color: var(--ui-text-secondary); line-height: 1.55; margin: 0; }
.cs-b-bc-changes { display: flex; flex-direction: column; font-size: 12.5px; gap: 5px; list-style: none; margin: 0; padding: 0 0 0 2px; }
.cs-b-bc-changes li { align-items: center; color: var(--ui-text-tertiary); display: flex; gap: 8px; min-width: 0; }
.cs-b-bc-mark { color: var(--ui-yellow); flex: none; font: 700 12px ${MONO}; text-align: center; width: 10px; }
.cs-b-bc-changes li[data-kind='added'] .cs-b-bc-mark { color: var(--ui-green); }
.cs-b-bc-changes li[data-kind='removed'] .cs-b-bc-mark { color: var(--ui-red); }
.cs-b-bc-foot { align-items: center; color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font-size: 12px; gap: 6px 14px; padding-left: 2px; }
.cs-b-bc-foot .cs-b-link { align-items: center; display: inline-flex; gap: 3px; }
.cs-b-ok { color: var(--ui-green); font-weight: 700; }
.cs-b-bad { color: var(--ui-red); font-weight: 700; }
.cs-b-bc-details { border-left: 2px solid var(--ui-stroke-tertiary); display: grid; font-size: 12.5px; gap: 12px 20px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-left: 2px; padding: 2px 0 4px 12px; }
.cs-b-bc-details p { line-height: 1.45; margin: 5px 0 0; }
.cs-b-bc-details pre { margin: 6px 0 0; white-space: pre-wrap; }
.cs-b-ba { display: flex; flex-direction: column; gap: 8px; padding: 2px 0; }
.cs-b-ba-pair { align-items: center; display: flex; gap: 12px; }
.cs-b-ba-side { align-items: center; appearance: none; background: none; border: 0; color: inherit; cursor: zoom-in; display: flex; flex-direction: column; font: inherit; gap: 4px; min-width: 0; padding: 0; }
.cs-b-ba-img { align-items: center; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 10px 10px; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); box-sizing: border-box; display: flex; height: 72px; justify-content: center; padding: 6px; width: 72px; }
.cs-b-ba-side:not(.now) .cs-b-ba-img { opacity: .72; }
.cs-b-ba-img img, .cs-b-ba-img .cs-b-spr { height: 100%; image-rendering: pixelated; max-height: 100%; max-width: 100%; object-fit: contain; width: auto; }
.cs-b-ba-cap { color: var(--ui-text-quaternary); font-size: 11px; }
.cs-b-ba-side.now .cs-b-ba-cap { color: var(--ui-text-secondary); }
.cs-b-ba-arrow { color: var(--ui-text-quaternary); flex: none; font-size: 16px; }
.cs-b-ba-acts { gap: 8px; }
.cs-b-replay { align-items: center; display: flex; flex-wrap: wrap; gap: 16px; max-width: 565px; }
.cs-b-replay .cs-b-th { aspect-ratio: 160 / 144; height: auto; max-width: 100%; padding: 0; width: 160px; }
.cs-b-replay .cs-b-th img { image-rendering: pixelated; object-fit: contain; }
.cs-b-replay .cs-b-link { align-items: center; align-self: flex-start; display: inline-flex; gap: 4px; }
.cs-b-replay input { accent-color: var(--ui-accent); max-width: 120px; }
/* next steps (a reply's suggestions) */
.cs-b-next-steps { display: flex; flex-wrap: wrap; gap: 8px; }
.cs-b-sugg-chip { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12.5px; gap: 5px; padding: 5px 12px; transition: box-shadow .12s ease, color .12s ease; }
.cs-b-sugg-chip:hover:not(:disabled) { box-shadow: inset 0 0 0 1px var(--ui-accent); color: var(--ui-text-primary); }
.cs-b-sugg-chip:disabled { cursor: default; opacity: .5; }
.cs-b-sugg-chip > i { color: var(--ui-accent); }
`
