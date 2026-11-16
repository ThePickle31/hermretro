import { MONO } from '../styles/tokens.js'

export const PROMPTS_CSS = `
/* prompts: Reader */
.cs-reader { align-items: start; display: grid; gap: clamp(20px, 3.4cqi, 60px); grid-template-columns: clamp(220px, 20cqi, 320px) minmax(0, 1fr) clamp(130px, 18cqi, 300px); }
.cs-rlist { display: flex; flex-direction: column; position: sticky; top: 76px; }
.cs-search { align-items: center; border-bottom: 1px solid var(--ui-stroke-secondary); color: var(--ui-text-quaternary); display: flex; gap: 8px; margin-bottom: 16px; padding: 6px 0; }
.cs-search input { all: unset; color: var(--ui-text-primary); flex: 1; font-size: 13px; min-width: 0; }
.cs-rgrp { color: var(--ui-text-quaternary); display: flex; font: 700 10px/1 ${MONO}; justify-content: space-between; letter-spacing: .14em; padding: 18px 0 6px; text-transform: uppercase; }
.cs-rgrp.first { padding-top: 0; }
.cs-ritem { all: unset; align-items: center; color: var(--ui-text-secondary); cursor: pointer; display: flex; gap: 8px; justify-content: space-between; margin: 0 -8px; padding: 7px 8px; }
.cs-ritem:hover { color: var(--ui-text-primary); }
.cs-ritem:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: -2px; }
.cs-ritem[aria-current] { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); font-weight: 600; }
.cs-ritem.off { color: var(--ui-text-quaternary); }
.cs-rdetail { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.cs-rdetail textarea { background: var(--ui-bg-quaternary); border: 0; color: var(--ui-text-primary); font: 13px/1.65 ${MONO}; min-height: 150px; outline: none; padding: 14px 16px; resize: vertical; width: 100%; }
.cs-rdetail textarea:focus { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-params { align-items: center; display: grid; gap: 10px 16px; grid-template-columns: max-content minmax(0, 420px); }
.cs-params label { color: var(--ui-text-tertiary); font: 700 10px ${MONO}; letter-spacing: .12em; text-transform: uppercase; }
.cs-params input { background: transparent; border: 0; border-bottom: 1px solid var(--ui-stroke-secondary); color: var(--ui-text-primary); font: 12.5px ${MONO}; outline: none; padding: 6px 0; }
.cs-params input:focus { border-bottom-color: var(--ui-accent); }
.cs-uses { border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; gap: 6px; padding-top: 14px; }
`
