export const HEADER_CSS = `
/* the header: status pill and Builds */
.cs-b-pill { align-items: center; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-tertiary); display: inline-flex; flex: none; font-size: 11.5px; gap: 6px; padding: 2px 10px; white-space: nowrap; }
.cs-b-pill-dot { background: currentColor; border-radius: 50%; flex: none; height: 7px; width: 7px; }
.cs-b-pill.good { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-green) 35%, transparent); color: var(--ui-green); }
.cs-b-pill.warn { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 35%, transparent); color: var(--ui-yellow); }
.cs-b-pill.bad { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-red) 40%, transparent); color: var(--ui-red); }
.cs-b-pill.busy { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 40%, transparent); color: var(--ui-accent); font-variant-numeric: tabular-nums; }
.cs-b-pill .cs-b-spin { height: 8px; width: 8px; }
.cs-b-sw-pop.cs-b-builds { left: auto; right: 0; width: 420px; }
.cs-b-brow { align-items: center; border-radius: 8px; display: flex; gap: 10px; padding: 7px 8px; }
.cs-b-brow.on { background: var(--ui-bg-quaternary); }
.cs-b-brow .cs-col { gap: 0; min-width: 0; }
.cs-b-brow b { font-size: 12.5px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-brow small { color: var(--ui-text-quaternary); font-size: 11px; }
.cs-b-brow-acts { display: flex; flex: none; gap: 4px; }
`
