import { MONO } from '../styles/tokens.js'

export const SETUP_CSS = `
/* setup: rail, current step, flying Chromatic */
.cs-setup { align-items: start; display: grid; gap: clamp(24px, 3.6cqi, 64px); grid-template-columns: clamp(180px, 13cqi, 240px) minmax(0, 820px) minmax(130px, 1fr); }
.cs-rail { display: flex; flex-direction: column; position: sticky; top: 76px; }
.cs-rail-group { color: var(--ui-text-quaternary); display: flex; font: 700 10px/1 ${MONO}; justify-content: space-between; letter-spacing: .14em; padding: 0 0 8px; text-transform: uppercase; }
.cs-rail-group.second { padding-top: 22px; }
.cs-rail-item { align-items: center; appearance: none; background: transparent; border: 0; color: var(--ui-text-tertiary); cursor: pointer; display: grid; font: inherit; gap: 8px; grid-template-columns: 22px 1fr 14px; margin: 0 -8px; padding: 7px 8px; text-align: left; transition: color .1s, background-color .1s; }
.cs-rail-item:hover { color: var(--ui-text-primary); transition: none; }
.cs-rail-item .n { color: var(--ui-text-quaternary); font: 700 11px ${MONO}; }
.cs-rail-item[data-state='done'] { color: var(--ui-text-secondary); }
.cs-rail-item[data-state='skipped'] .l { color: var(--ui-text-quaternary); text-decoration: line-through; }
.cs-rail-item[data-auto] { color: var(--ui-text-primary); font-weight: 600; }
.cs-rail-item[data-auto] .n { color: var(--ui-accent); }
.cs-rail-item[aria-current] { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-meter { display: flex; gap: 3px; margin: 18px 0 8px; }
.cs-meter button { appearance: none; background: transparent; border: 0; cursor: pointer; flex: 1; min-width: 0; padding: 4px 0; }
.cs-meter button > i { background: var(--ui-stroke-tertiary); display: block; height: 3px; }
.cs-meter button[data-state='done'] > i { background: var(--ui-green); }
.cs-meter button[data-state='skipped'] > i { background: var(--ui-stroke-secondary); opacity: .5; }
.cs-meter button[data-auto] > i { background: var(--ui-accent); }
.cs-meter button.gap { margin-left: 6px; }
.cs-stage { display: flex; flex-direction: column; gap: 22px; min-width: 0; }
.cs-stage-head { display: flex; flex-direction: column; gap: 14px; }
.cs-stage-foot { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 10px 16px; justify-content: space-between; margin-top: 4px; padding-top: 14px; }
.cs-content { display: flex; flex-direction: column; gap: 18px; }
.cs-actions { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; }
.cs-prompt { background: var(--ui-bg-quaternary); color: var(--ui-text-secondary); font: 12.5px/1.6 ${MONO}; margin: 0; overflow-wrap: anywhere; padding: 13px 16px 13px 34px; position: relative; user-select: text; white-space: pre-wrap; }
.cs-prompt::before { color: var(--ui-accent); content: '❯'; left: 14px; position: absolute; top: 13px; }
.cs-facts { display: grid; gap: 9px 22px; grid-template-columns: max-content 1fr; margin: 0; }
.cs-facts dt { color: var(--ui-text-tertiary); font: 700 10px/2 ${MONO}; letter-spacing: .12em; text-transform: uppercase; }
.cs-facts dd { color: var(--ui-text-secondary); margin: 0; }
.cs-watch { align-items: center; background: var(--ui-bg-quaternary); color: var(--ui-text-secondary); display: flex; gap: 12px; padding: 11px 14px; }
.cs-watch.quiet { background: transparent; color: var(--ui-text-tertiary); font-size: 12px; gap: 8px; padding: 0; }
.cs-lem { flex: none; height: 18px; width: 34px; }
.cs-watch.quiet .cs-lem { height: 12px; width: 24px; }
.cs-lem path { fill: none; }
.cs-lem .track { stroke: var(--ui-stroke-tertiary); stroke-width: .07; }
.cs-lem .run { animation: cs-lem 1.4s linear infinite; stroke: var(--ui-accent); stroke-dasharray: 18 82; stroke-linecap: round; stroke-width: .11; }
@keyframes cs-lem { to { stroke-dashoffset: -100; } }
.cs-glyph .cs-dash { animation: cs-dash 1s linear infinite; }
@keyframes cs-dash { to { stroke-dashoffset: -10; } }
.cs-comps { display: flex; flex-direction: column; }
.cs-comp { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: grid; gap: 4px 12px; grid-template-columns: 14px minmax(0, 1fr) auto auto; padding: 8px 0; }
.cs-comp:last-child { border-bottom: 1px solid var(--ui-stroke-tertiary); }
.cs-comp .name { color: var(--ui-text-primary); }
.cs-comp .name small { color: var(--ui-text-quaternary); font-size: 11px; margin-left: 6px; }
.cs-comp .ver { color: var(--ui-text-tertiary); font: 11px ${MONO}; text-align: right; }
.cs-comp .st { font: 700 9.5px ${MONO}; letter-spacing: .1em; min-width: 82px; text-align: right; text-transform: uppercase; }
.cs-comp .detail { color: var(--ui-text-quaternary); font-size: 11.5px; grid-column: 2 / -1; }
.cs-comp .st.ready { color: var(--ui-green); }
.cs-comp .st.missing { color: var(--ui-yellow); }
.cs-comp .st.incompatible { color: var(--ui-red); }
.cs-comp .st.optional, .cs-comp .st.unknown { color: var(--ui-text-quaternary); }
.cs-kbd { background: transparent; border: 1px solid var(--ui-stroke-tertiary); border-bottom-width: 3px; color: var(--ui-text-primary); display: inline-grid; font: 700 12px ${MONO}; height: 30px; min-width: 30px; padding: 0 8px; place-items: center; }
.cs-warnline { align-items: flex-start; color: var(--ui-text-primary); display: flex; font-weight: 500; gap: 10px; }
.cs-warnline > span:first-child { color: var(--ui-yellow); display: inline-flex; padding-top: 2px; }
.cs-choice { border-bottom: 1px solid var(--ui-stroke-tertiary); border-top: 1px solid var(--ui-stroke-tertiary); display: grid; grid-template-columns: 1fr 1fr; }
.cs-choice > div { display: flex; flex-direction: column; gap: 8px; padding: 20px 24px 22px 0; }
.cs-choice > div + div { border-left: 1px solid var(--ui-stroke-tertiary); padding-left: 24px; padding-right: 0; }
.cs-choice h3 { color: var(--ui-text-primary); font-size: 16px; font-weight: 600; margin: 0; }
.cs-choice .cs-actions { margin-top: auto; padding-top: 8px; }
`
