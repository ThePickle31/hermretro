// The New Game form as frosted glass over the page's background (app/background.js; Build shows `platformer`).
// `--cs-at-bg` is the page colour behind it, which the platformer keeps on the page area as the theme changes.
export const NEW_GAME_GLASS_CSS = `
.cs-b-attract { --cs-at-glass: color-mix(in srgb, var(--cs-at-bg, var(--ui-bg-editor)) 60%, transparent); }
.cs-b-attract > * { position: relative; z-index: 1; }
/* the header above the form, so the game switcher's menu opens over it; the composer above the choice cards, so its
   model picker opens over them (the glass's backdrop-filter makes each a stacking context that would trap it) */
.cs-b-attract > .cs-b-head { z-index: 2; }
.cs-b-attract .cs-b-new .cs-title { align-self: center; text-shadow: 0 2px 0 color-mix(in srgb, var(--cs-at-bg, var(--ui-bg-editor)) 70%, black), 0 0 18px var(--cs-at-bg, var(--ui-bg-editor)), 0 0 6px var(--cs-at-bg, var(--ui-bg-editor)); }
.cs-b-attract .cs-b-new .cs-b-comp { position: relative; z-index: 2; -webkit-backdrop-filter: blur(10px) saturate(.8); backdrop-filter: blur(10px) saturate(.8); background: var(--cs-at-glass); box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary), 0 0 0 1px color-mix(in srgb, var(--ui-accent) 45%, transparent); }
.cs-b-attract .cs-b-opt { -webkit-backdrop-filter: blur(10px) saturate(.8); backdrop-filter: blur(10px) saturate(.8); background: var(--cs-at-glass); }
.cs-b-attract .cs-b-opt.on { background: color-mix(in srgb, var(--ui-accent) 10%, var(--cs-at-glass)); }
`
