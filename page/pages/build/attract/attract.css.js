export const ATTRACT_CSS = `
/* New Game attract mode: the level behind the form, dimmed, with a pool of the page colour behind the composer */
.cs-b-attract { --cs-at-bg: var(--ui-bg-editor); }
.cs-at { inset: 0; overflow: hidden; pointer-events: none; position: absolute; z-index: 0; }
.cs-at canvas { bottom: 0; image-rendering: pixelated; image-rendering: crisp-edges; left: 0; opacity: .5; position: absolute; }
.cs-at-spot { background: radial-gradient(ellipse 560px 300px at var(--cs-at-sx, 50%) var(--cs-at-sy, 50%), color-mix(in srgb, var(--cs-at-bg) 92%, transparent) 0%, color-mix(in srgb, var(--cs-at-bg) 70%, transparent) 50%, transparent 80%); inset: 0; position: absolute; }
.cs-b-attract > :not(.cs-at) { position: relative; z-index: 1; }
/* the header above the form, so the game switcher's menu opens over it */
.cs-b-attract > .cs-b-head { z-index: 2; }
.cs-b-attract .cs-b-new .cs-title { align-self: center; -webkit-text-stroke: 7px var(--cs-at-bg, transparent); paint-order: stroke fill; }
.cs-b-attract .cs-b-new .cs-b-comp { background: var(--ui-bg-editor); box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary), 0 0 0 1px color-mix(in srgb, var(--ui-accent) 45%, transparent); }
.cs-b-attract .cs-b-opt { background: var(--ui-bg-editor); }
.cs-b-attract .cs-b-opt.on { background: color-mix(in srgb, var(--ui-accent) 8%, var(--ui-bg-editor)); }
`
