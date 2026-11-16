import { MONO } from '../styles/tokens.js'

export const NEW_GAME_CSS = `
/* New Game: the Build page's composer, centred, with the two ways to start under it */
.cs-b-new { box-sizing: border-box; display: flex; flex: 1; flex-direction: column; gap: 18px; justify-content: center; margin: 0 auto; max-width: 680px; min-height: 0; overflow: auto; padding: 24px clamp(14px, 3cqi, 28px); width: 100%; }
.cs-b-new .cs-title { margin: 0; text-align: center; }
.cs-b-new .cs-b-comp { margin: 0; max-width: none; width: 100%; }
.cs-b-new .cs-b-comp textarea { max-height: 220px; min-height: 66px; }
.cs-b-opts { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }
@container (max-width: 560px) { .cs-b-opts { grid-template-columns: 1fr; } }
.cs-b-opt { align-items: flex-start; background: transparent; border: 0; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: inherit; cursor: pointer; display: flex; font: inherit; gap: 10px; padding: 12px 14px; text-align: left; }
.cs-b-opt:hover { box-shadow: inset 0 0 0 1px var(--ui-stroke-primary, var(--ui-text-tertiary)); }
.cs-b-opt:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-b-opt.on { background: color-mix(in srgb, var(--ui-accent) 8%, transparent); box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-opt-dot { border-radius: 50%; box-shadow: inset 0 0 0 1px var(--ui-text-tertiary); flex: none; height: 12px; margin-top: 3px; width: 12px; }
.cs-b-opt.on .cs-b-opt-dot { background: radial-gradient(var(--ui-accent) 42%, transparent 48%); box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-opt b { color: var(--ui-text-primary); display: block; font-size: 13.5px; font-weight: 600; }
.cs-b-opt span span { color: var(--ui-text-tertiary); display: block; font-size: 12.5px; line-height: 1.45; margin-top: 2px; }
.cs-b-opt em { color: var(--ui-text-quaternary, var(--ui-text-tertiary)); display: block; font: 700 10px/1.3 ${MONO}; font-style: normal; letter-spacing: .1em; margin-top: 7px; text-transform: uppercase; }
`
