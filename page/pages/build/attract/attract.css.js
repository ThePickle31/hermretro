export const ATTRACT_CSS = `
/* New Game attract mode: the level behind the form, dimmed; the form floats over it as frosted glass, apart from the game */
.cs-b-attract { --cs-at-bg: var(--ui-bg-editor); --cs-at-glass: color-mix(in srgb, var(--cs-at-bg) 60%, transparent); }
.cs-at { inset: 0; overflow: hidden; pointer-events: none; position: absolute; z-index: 0; }
.cs-at canvas { bottom: 0; filter: saturate(.78); image-rendering: pixelated; image-rendering: crisp-edges; left: 0; opacity: .4; position: absolute; }
.cs-b-attract > :not(.cs-at) { position: relative; z-index: 1; }
/* the header above the form, so the game switcher's menu opens over it */
.cs-b-attract > .cs-b-head { z-index: 2; }
.cs-b-attract .cs-b-new .cs-title { align-self: center; text-shadow: 0 2px 0 color-mix(in srgb, var(--cs-at-bg) 70%, black), 0 0 18px var(--cs-at-bg), 0 0 6px var(--cs-at-bg); }
.cs-b-attract .cs-b-new .cs-b-comp { -webkit-backdrop-filter: blur(10px) saturate(.8); backdrop-filter: blur(10px) saturate(.8); background: var(--cs-at-glass); box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary), 0 0 0 1px color-mix(in srgb, var(--ui-accent) 45%, transparent); }
.cs-b-attract .cs-b-opt { -webkit-backdrop-filter: blur(10px) saturate(.8); backdrop-filter: blur(10px) saturate(.8); background: var(--cs-at-glass); }
.cs-b-attract .cs-b-opt.on { background: color-mix(in srgb, var(--ui-accent) 10%, var(--cs-at-glass)); }
`
