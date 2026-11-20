// Classes every page shares.
import { DISPLAY, MONO } from './tokens.js'

export const BASE_CSS = `
.cs-page { container-type: inline-size; box-sizing: border-box; color: var(--ui-text-primary); display: flex; flex-direction: column; font-size: 13px; line-height: 1.55; min-height: 100%; overflow-x: clip; position: relative; width: 100%; }
.cs-page *, .cs-page *::before, .cs-page *::after { box-sizing: border-box; }
.cs-eyebrow { align-items: center; color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font: 700 10.5px/1.3 ${MONO}; gap: 4px 10px; letter-spacing: .14em; margin: 0; text-transform: uppercase; }
.cs-accent { color: var(--ui-accent); }
.cs-word { color: var(--ui-text-primary); font-family: ${DISPLAY}; font-weight: 700; letter-spacing: .04em; line-height: .92; margin: 0; text-transform: uppercase; text-wrap: balance; }
.cs-title { font-size: clamp(28px, 3.4cqi, 60px); }
.cs-lede { color: var(--ui-text-secondary); font-size: 14px; line-height: 1.6; margin: 0; max-width: 62ch; text-wrap: pretty; }
.cs-small { color: var(--ui-text-tertiary); font-size: 12px; line-height: 1.55; margin: 0; }
.cs-faint { color: var(--ui-text-quaternary); font-size: 11.5px; line-height: 1.5; margin: 0; overflow-wrap: anywhere; }
.cs-mono { font-family: ${MONO}; }
.cs-row { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; }
.cs-col { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.cs-grow { flex: 1; }
.cs-error { color: var(--ui-red); font: 12px/1.5 ${MONO}; margin: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.cs-warn { color: var(--ui-yellow); }
.cs-bad { color: var(--ui-red); }
.cs-good { color: var(--ui-green); }
.cs-link { all: unset; color: var(--ui-accent); cursor: pointer; font: 700 10px ${MONO}; letter-spacing: .12em; text-transform: uppercase; }
.cs-link:hover { text-decoration: underline; text-underline-offset: 3px; }
.cs-link:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
`
