import { DISPLAY, MONO } from '../styles/tokens.js'

export const SHELL_CSS = `
/* header: wordmark, one segmented control, refresh */
.cs-top { align-items: center; background: var(--ui-bg-editor); border-bottom: 1px solid var(--ui-stroke-tertiary); display: grid; gap: 24px; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); padding: 14px clamp(16px, 3.5cqi, 64px); position: sticky; top: 0; z-index: 10; }
.cs-brand { all: unset; color: var(--ui-text-primary); cursor: pointer; font: 700 18px/.9 ${DISPLAY}; letter-spacing: .04em; text-transform: uppercase; white-space: nowrap; }
.cs-brand span { color: var(--ui-accent); }
.cs-brand:hover span { text-decoration: underline; text-underline-offset: 4px; }
.cs-brand:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 4px; }
.cs-seg { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: inline-flex; margin: 0 auto; }
.cs-seg button { align-items: center; appearance: none; background: transparent; border: 0; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; font: 700 10.5px/1 ${MONO}; gap: 7px; letter-spacing: .12em; padding: 7px 16px; text-transform: uppercase; white-space: nowrap; }
.cs-seg button + button { box-shadow: inset 1px 0 0 var(--ui-stroke-secondary); }
.cs-seg button:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-seg button:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-seg button[aria-current] { background: var(--ui-accent); box-shadow: none; color: var(--ui-bg-editor); }
.cs-seg .pip { background: var(--ui-yellow); height: 6px; width: 6px; }
.cs-seg .live { background: var(--ui-green); border-radius: 50%; box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-green) 25%, transparent); height: 6px; width: 6px; }
.cs-seg button[aria-current] .pip, .cs-seg button[aria-current] .live { background: var(--ui-bg-editor); box-shadow: none; }
.cs-top-start { align-items: center; display: flex; min-width: 0; }
.cs-top-end { display: flex; justify-content: flex-end; justify-self: end; }
.cs-pad { display: flex; flex: 1; flex-direction: column; gap: 28px; padding: 26px clamp(16px, 3.5cqi, 64px) 36px; }
.cs-pad.flush { gap: 0; padding: 0; }
.cs-chip { align-items: center; background: var(--ui-bg-quaternary); color: var(--ui-text-secondary); display: inline-flex; font: 400 11px/1 ${MONO}; gap: 6px; padding: 5px 8px; white-space: nowrap; }
.cs-chip > i { background: var(--ui-text-quaternary); display: block; flex: none; height: 6px; width: 6px; }
.cs-chip.good > i { background: var(--ui-green); }
.cs-chip.warn > i { background: var(--ui-yellow); }
.cs-chip.bad > i { background: var(--ui-red); }
.cs-chip.accent > i { background: var(--ui-accent); }
.cs-tag { font: 700 9.5px/1 ${MONO}; letter-spacing: .1em; padding: 4px 6px; text-transform: uppercase; white-space: nowrap; }
.cs-tag.good { background: color-mix(in srgb, var(--ui-green) 13%, transparent); color: var(--ui-green); }
.cs-tag.warn { background: color-mix(in srgb, var(--ui-yellow) 12%, transparent); color: var(--ui-yellow); }
.cs-tag.bad { background: color-mix(in srgb, var(--ui-red) 13%, transparent); color: var(--ui-red); }
.cs-tag.quiet { box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); color: var(--ui-text-tertiary); }
.cs-tag.accent { background: var(--ui-bg-secondary); color: var(--ui-accent); }
.cs-art { aspect-ratio: 3 / 4; background: var(--ui-accent); flex: none; justify-self: center; max-width: 440px; pointer-events: none; width: 100%;
  -webkit-mask: var(--cs-hermes) center top / contain no-repeat, linear-gradient(currentColor 0 74%, transparent); -webkit-mask-composite: source-in;
  mask: var(--cs-hermes) center top / contain no-repeat, linear-gradient(currentColor 0 74%, transparent); mask-composite: intersect; }
.cs-page-head { align-items: end; display: grid; gap: 16px 28px; grid-template-columns: minmax(0, 1fr) auto; }
.cs-page-head > .cs-col { gap: 12px; }
.cs-key { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-tertiary); font: 700 10px ${MONO}; padding: 2px 5px; }
.cs-note { align-items: center; display: flex; flex-wrap: wrap; gap: 10px; }
`
