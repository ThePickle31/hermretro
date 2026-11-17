export const ASSETS_CSS = `
/* images */
.cs-b-strip { align-items: center; display: inline-flex; flex-wrap: wrap; gap: 6px; }
.cs-b-more { color: var(--ui-text-quaternary); font-size: 11px; }
.cs-b-th { align-items: center; appearance: none; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-secondary) 0 50%) 0 0 / 8px 8px; border: 0; border-radius: 6px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); cursor: zoom-in; display: inline-flex; flex: none; height: 40px; justify-content: center; overflow: hidden; padding: 0; transition: box-shadow .15s ease, transform .15s ease; width: 40px; }
.cs-b-th:hover { box-shadow: inset 0 0 0 1px var(--ui-accent); transform: translateY(-1px); }
.cs-b-th img { height: 100%; image-rendering: pixelated; object-fit: contain; width: 100%; }
.cs-b-spr { display: block; height: 100%; image-rendering: pixelated; max-height: 100%; max-width: 100%; object-fit: contain; width: 100%; }
.cs-b-th.xs { border-radius: 4px; height: 20px; width: 20px; }
.cs-b-th.lg { border-radius: 8px; height: 84px; width: 112px; }
.cs-b-th.cs-b-reply-img { border-radius: 6px; display: flex; margin: 10px 0; max-width: 100%; }
.cs-b-th.cs-b-reply-img.loading { height: 120px; width: 160px; }
.cs-b-sprite { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 10px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: inherit; cursor: zoom-in; display: flex; font: inherit; gap: 14px; margin: 4px 0; max-width: 100%; padding: 10px 16px 10px 10px; text-align: left; transition: box-shadow .15s ease; }
.cs-b-sprite:hover { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-sprite-stage { align-items: center; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 12px 12px; border-radius: 7px; display: flex; flex: none; height: 120px; justify-content: center; width: 120px; }
.cs-b-sprite-stage img { image-rendering: pixelated; max-height: 100%; max-width: 100%; }
.cs-b-th.screen { aspect-ratio: 160 / 144; border-radius: 4px; height: auto; width: 100%; }
.cs-b-th.fresh { animation: cs-b-pop .35s ease-out; box-shadow: inset 0 0 0 1px var(--ui-accent), 0 0 0 3px color-mix(in srgb, var(--ui-accent) 22%, transparent); }
.cs-b-th.loading { animation: cs-b-skel 1.2s ease-in-out infinite; background: var(--ui-bg-quaternary); cursor: default; }
@keyframes cs-b-pop { from { opacity: 0; transform: scale(.85); } }
@keyframes cs-b-skel { 50% { opacity: .45; } }
`
