import { DISPLAY, MONO } from '../styles/tokens.js'

export const HOME_CSS = `
/* home: hero, then Continue / Start something / Studio */
.cs-home { display: flex; flex-direction: column; gap: clamp(28px, 3cqi, 48px); }
.cs-hero { align-items: center; display: grid; gap: clamp(24px, 4cqi, 72px); grid-template-columns: minmax(0, 1fr) clamp(150px, 22cqi, 380px); }
.cs-hero > .cs-col { gap: 16px; }
.cs-hero h2 { font-size: clamp(38px, 5cqi, 92px); }
.cs-band { border-top: 1px solid var(--ui-stroke-secondary); display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr) minmax(0, .8fr); }
.cs-band > section { display: flex; flex-direction: column; gap: 14px; min-width: 0; padding: 22px clamp(18px, 2.4cqi, 40px) 8px; }
.cs-band > section:first-child { padding-left: 0; }
.cs-band > section + section { border-left: 1px solid var(--ui-stroke-tertiary); }
.cs-band h3 { margin: 0; }
.cs-cont { align-items: start; display: grid; gap: 18px; grid-template-columns: clamp(120px, 11cqi, 200px) minmax(0, 1fr); }
.cs-cont .name { font: 700 clamp(24px, 2.4cqi, 40px)/.9 ${DISPLAY}; letter-spacing: .03em; margin: 0; overflow-wrap: anywhere; text-transform: uppercase; }
.cs-screen { aspect-ratio: 10 / 9; background: var(--ui-bg-tertiary); display: block; image-rendering: pixelated; object-fit: cover; width: 100%; }
.cs-screen.ph { align-content: center; color: var(--ui-text-quaternary); display: grid; font: 700 10px/1.4 ${MONO}; letter-spacing: .1em; padding: 10px; text-align: center; text-transform: uppercase; }
.cs-quick { display: flex; flex-direction: column; }
.cs-quick button { all: unset; border-top: 1px solid var(--ui-stroke-tertiary); cursor: pointer; display: grid; gap: 2px 12px; grid-template-columns: 1fr auto; padding: 11px 0; }
.cs-quick button:last-child { border-bottom: 1px solid var(--ui-stroke-tertiary); }
.cs-quick .t { color: var(--ui-text-primary); font-weight: 600; }
.cs-quick .d { color: var(--ui-text-tertiary); font-size: 12px; grid-column: 1; }
.cs-quick .a { align-self: center; color: var(--ui-text-quaternary); font: 700 10px ${MONO}; grid-column: 2; grid-row: 1 / span 2; letter-spacing: .12em; text-transform: uppercase; }
.cs-quick button:hover .t, .cs-quick button:hover .a { color: var(--ui-accent); }
.cs-quick button:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-quick button[disabled] { cursor: default; opacity: .45; pointer-events: none; }
.cs-bar7 { display: flex; gap: 3px; }
.cs-bar7 i { background: var(--ui-stroke-secondary); flex: 1; height: 4px; }
.cs-bar7 i.on { background: var(--ui-green); }
.cs-bar7 i.cur { background: var(--ui-accent); }
.cs-stat { display: flex; flex-direction: column; gap: 9px; margin: 0; }
.cs-stat div { display: flex; font-size: 12.5px; gap: 12px; justify-content: space-between; }
.cs-stat dt { color: var(--ui-text-tertiary); }
.cs-stat dd { align-items: center; color: var(--ui-text-primary); display: flex; font: 11.5px ${MONO}; gap: 6px; margin: 0; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-stat dd i { background: var(--ui-text-quaternary); flex: none; height: 6px; width: 6px; }
.cs-stat dd i.good { background: var(--ui-green); }
.cs-stat dd i.warn { background: var(--ui-yellow); }
.cs-stat dd i.bad { background: var(--ui-red); }
.cs-foot { border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; gap: 10px; padding-top: 16px; }
`
