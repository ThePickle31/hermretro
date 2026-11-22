import { MONO } from '#shared/styles/tokens.js'

// The update chip beside Refresh and its popover (chip.js). The chip reuses .cs-chip; under 900px only its dot shows
// (responsive.css.js hides .cs-top-end .cs-lbl).
export const UPDATE_CSS = `
.cs-top-end { align-items: center; gap: 10px; }
.cs-upd { position: relative; }
.cs-upd-chip { appearance: none; border: 0; color: var(--ui-text-primary); cursor: pointer; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.cs-upd-chip.accent { background: color-mix(in srgb, var(--ui-accent) 14%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 45%, transparent); }
.cs-upd-chip.accent > i { box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-accent) 25%, transparent); }
.cs-upd-chip.good { background: color-mix(in srgb, var(--ui-green) 13%, transparent); }
.cs-upd-chip.warn { background: color-mix(in srgb, var(--ui-yellow) 12%, transparent); }
.cs-upd-chip.bad { background: color-mix(in srgb, var(--ui-red) 12%, transparent); }
.cs-upd-chip:hover { filter: brightness(1.15); }
.cs-upd-chip:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-upd-pop { background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 8px;
  box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 14px 36px color-mix(in srgb, black 40%, transparent); display: flex; flex-direction: column;
  gap: 8px; padding: 14px 16px; position: absolute; right: 0; top: calc(100% + 8px); width: min(340px, calc(100vw - 32px)); z-index: 30; }
.cs-upd-pop h3 { font-size: 17px; }
.cs-upd-pop p { color: var(--ui-text-secondary); font-size: 13px; line-height: 1.45; margin: 0; }
.cs-upd-pop .cs-eyebrow { color: var(--ui-text-tertiary); }
.cs-upd-kv { align-items: baseline; display: flex; gap: 10px; }
.cs-upd-kv b { color: var(--ui-text-tertiary); font: 700 10px ${MONO}; letter-spacing: .12em; text-transform: uppercase; }
.cs-upd-acts { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.cs-upd-fill { flex: 1; }
.cs-upd-pop p.cs-upd-wait { align-items: flex-start; background: color-mix(in srgb, var(--ui-yellow) 10%, transparent); color: var(--ui-text-primary); display: flex; gap: 8px; padding: 7px 9px; }
.cs-upd-wait > :first-child { color: var(--ui-yellow); flex: none; margin-top: 2px; }
.cs-upd-steps { display: flex; flex-direction: column; gap: 5px; list-style: none; margin: 2px 0; padding: 0; }
.cs-upd-steps li { align-items: center; color: var(--ui-text-tertiary); display: flex; font-size: 13px; gap: 9px; }
.cs-upd-steps li > i { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: block; height: 12px; width: 12px; }
.cs-upd-steps li[data-state=done] { color: var(--ui-text-secondary); }
.cs-upd-steps li[data-state=done] > :first-child { color: var(--ui-green); }
.cs-upd-steps li[data-state=now] { color: var(--ui-text-primary); font-weight: 600; }
.cs-repair.bad { background: color-mix(in srgb, var(--ui-red) 10%, transparent); box-shadow: inset 2px 0 0 var(--ui-red); }
.cs-repair.bad > i { color: var(--ui-red); }
.cs-repair-wait { align-items: center; color: var(--ui-text-secondary); display: flex; gap: 6px; }
.cs-upd-pre { background: var(--ui-bg-quaternary); font: 11.5px/1.5 ${MONO}; margin: 0; max-height: 160px; overflow: auto; padding: 8px 10px; white-space: pre-wrap; }
`
