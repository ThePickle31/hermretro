// The factory reset's settings page and dialog (settings-page.js, reset-dialog.js). They render outside the hermretro
// page, so this sheet comes with the settings page itself; the dialog's frame, header and footer are Hermes's own.
export const RESET_CSS = `
.cs-rst-page { display: flex; flex-direction: column; gap: 8px; }
.cs-rst-head { color: var(--ui-text-tertiary); font-size: 11.5px; font-weight: 600; letter-spacing: .06em; margin: 8px 0 0; text-transform: uppercase; }
.cs-rst-card { border-radius: 8px; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-red) 40%, transparent); padding: 0 14px; }
.cs-rst-dlg { width: min(560px, calc(100vw - 32px)); }
.cs-rst-parts { display: flex; flex-direction: column; gap: 6px; list-style: none; margin: 0; padding: 0; }
.cs-rst-part { align-items: center; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: flex; gap: 12px; padding: 9px 12px; }
.cs-rst-name { display: flex; flex: 1; flex-direction: column; min-width: 0; }
.cs-rst-name b { color: var(--ui-text-primary); font-weight: 500; }
.cs-rst-name span { color: var(--ui-text-tertiary); font-size: 12px; }
.cs-rst-part > :last-child { flex: none; width: 140px; }
.cs-rst-cols { display: grid; gap: 16px; grid-template-columns: 1fr 1fr; }
.cs-rst-col h4 { font-size: 11.5px; letter-spacing: .06em; margin: 0 0 4px; text-transform: uppercase; }
.cs-rst-col[data-kind=delete] h4 { color: var(--ui-red); }
.cs-rst-col[data-kind=keep] h4 { color: var(--ui-green); }
.cs-rst-col ul, .cs-rst-steps { list-style: none; margin: 0; padding: 0; }
.cs-rst-col li { border-bottom: 1px dashed var(--ui-stroke-secondary); display: flex; font-size: 12.5px; justify-content: space-between; padding: 5px 2px; }
.cs-rst-col li span:last-child, .cs-rst-done dd { color: var(--ui-text-tertiary); }
.cs-rst-type { display: flex; flex-direction: column; gap: 6px; margin-top: 14px; }
.cs-rst-type > span { color: var(--ui-text-tertiary); font-size: 12px; }
.cs-rst-type b { color: var(--ui-text-primary); }
.cs-rst-bar { background: var(--ui-bg-quaternary); border-radius: 99px; height: 4px; margin-bottom: 12px; overflow: hidden; }
.cs-rst-bar i { background: var(--ui-red); display: block; height: 100%; transition: width .3s; }
.cs-rst-steps { display: flex; flex-direction: column; gap: 8px; }
.cs-rst-steps li { align-items: center; color: var(--ui-text-tertiary); display: flex; font-size: 13px; gap: 10px; }
.cs-rst-steps li > i { border-radius: 50%; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: block; height: 13px; width: 13px; }
.cs-rst-steps li[data-state=done] { color: var(--ui-text-secondary); }
.cs-rst-steps li[data-state=done] > :first-child { color: var(--ui-green); }
.cs-rst-steps li[data-state=now] { color: var(--ui-text-primary); font-weight: 600; }
.cs-rst-done { margin: 0; }
.cs-rst-done div { border-bottom: 1px dashed var(--ui-stroke-secondary); display: flex; font-size: 12.5px; gap: 16px; justify-content: space-between; padding: 6px 2px; }
.cs-rst-done dd { margin: 0; text-align: right; }
.cs-rst-done [data-error] dd, .cs-rst-note[data-error] { color: var(--ui-red); }
.cs-rst-note { align-items: center; color: var(--ui-text-secondary); display: flex; gap: 8px; margin: 0; }
.cs-rst-foot .cs-rst-left { margin-right: auto; }
@media (max-width: 520px) { .cs-rst-cols { grid-template-columns: 1fr; } .cs-rst-part > :last-child { width: 120px; } }
`
