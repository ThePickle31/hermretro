import { MONO } from '#shared/styles/tokens.js'

// The update chip at the header's end (chip.js), the corner card (update-card.js) and the dialog (update-dialog.js).
// The chip reuses .cs-chip; under 900px only its dot shows (responsive.css.js hides .cs-top-end .cs-lbl).
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
.cs-upd-scrim { align-items: center; background: color-mix(in srgb, black 55%, transparent); backdrop-filter: blur(2px); display: flex; inset: 0; justify-content: center; padding: 24px; position: fixed; z-index: 80; }
.cs-upd-dlg { background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 10px;
  box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 24px 60px color-mix(in srgb, black 55%, transparent); display: flex; flex-direction: column;
  max-height: min(640px, calc(100vh - 48px)); overflow: hidden; width: min(520px, 100%); }
.cs-upd-card { bottom: 20px; position: fixed; right: 20px; width: min(380px, calc(100vw - 32px)); z-index: 70; }
.cs-upd-card .cs-upd-dlg { max-height: min(460px, calc(100vh - 120px)); width: 100%; }
.cs-upd-head { display: flex; flex-direction: column; gap: 10px; padding: 22px 24px 16px; position: relative; }
.cs-upd-head h2 { font-size: 30px; padding-right: 24px; }
.cs-upd-card .cs-upd-head { padding: 16px 18px 12px; }
.cs-upd-card .cs-upd-head h2 { font-size: 22px; }
.cs-upd-head h2 span { color: var(--ui-accent); }
.cs-upd-ver { align-items: center; color: var(--ui-text-secondary); display: flex; font: 700 11px ${MONO}; gap: 8px; letter-spacing: .1em; }
.cs-upd-ver b { background: color-mix(in srgb, var(--ui-accent) 16%, transparent); border-radius: 4px; color: var(--ui-text-primary); padding: 3px 7px; }
.cs-upd-x { appearance: none; background: none; border: 0; color: var(--ui-text-tertiary); cursor: pointer; position: absolute; right: 14px; top: 14px; }
.cs-upd-x:hover { color: var(--ui-text-primary); }
.cs-upd-notes, .cs-upd-body { border-top: 1px solid var(--ui-stroke-secondary); display: flex; flex-direction: column; gap: 18px; min-height: 0; overflow: auto; padding: 16px 24px 18px; }
.cs-upd-body { gap: 10px; }
.cs-upd-card .cs-upd-notes { padding: 12px 18px 14px; }
.cs-upd-text { color: var(--ui-text-secondary); font-size: 13.5px; line-height: 1.45; margin: 0; }
.cs-upd-rel { display: flex; flex-direction: column; gap: 10px; }
.cs-upd-rel + .cs-upd-rel { border-top: 1px dashed var(--ui-stroke-secondary); padding-top: 16px; }
.cs-upd-relh { align-items: baseline; display: flex; gap: 10px; }
.cs-upd-relh b { color: var(--ui-text-primary); font: 700 12px ${MONO}; letter-spacing: .08em; }
.cs-upd-relh span { color: var(--ui-text-tertiary); font: 11px ${MONO}; }
.cs-upd-grp { display: flex; flex-direction: column; gap: 6px; }
.cs-upd-tag { align-self: flex-start; border-radius: 3px; font: 700 9.5px ${MONO}; letter-spacing: .14em; padding: 2px 6px; text-transform: uppercase; }
.cs-upd-tag[data-kind=new] { background: color-mix(in srgb, var(--ui-accent) 16%, transparent); color: var(--ui-accent); }
.cs-upd-tag[data-kind=fixed] { background: color-mix(in srgb, var(--ui-green) 14%, transparent); color: var(--ui-green); }
.cs-upd-grp ul { display: flex; flex-direction: column; gap: 5px; margin: 0; padding-left: 18px; }
.cs-upd-grp li { color: var(--ui-text-secondary); font-size: 13.5px; line-height: 1.45; }
.cs-upd-link { align-self: flex-start; margin: 0 24px 12px; }
.cs-upd-foot { align-items: center; border-top: 1px solid var(--ui-stroke-secondary); display: flex; flex-wrap: wrap; gap: 10px; padding: 14px 24px; }
.cs-upd-card .cs-upd-foot { padding: 12px 18px; }
.cs-upd-fill { flex: 1; }
.cs-upd-note { color: var(--ui-text-tertiary); font-size: 12px; }
.cs-upd-ok { align-items: center; color: var(--ui-green); display: flex; font: 700 11px ${MONO}; gap: 8px; letter-spacing: .12em; text-transform: uppercase; }
.cs-upd-bar { background: var(--ui-bg-quaternary); height: 3px; overflow: hidden; }
.cs-upd-bar i { background: var(--ui-accent); display: block; height: 100%; transition: width .3s; }
.cs-upd-wait { align-items: flex-start; background: color-mix(in srgb, var(--ui-yellow) 10%, transparent); border-radius: 6px; color: var(--ui-text-primary); display: flex; font-size: 13px; gap: 8px; line-height: 1.45; margin: 0 24px 14px; padding: 9px 11px; }
.cs-upd-card .cs-upd-wait { margin: 0 18px 12px; }
.cs-upd-wait > :first-child { color: var(--ui-yellow); flex: none; margin-top: 2px; }
.cs-upd-steps { border-top: 1px solid var(--ui-stroke-secondary); display: flex; flex-direction: column; gap: 8px; list-style: none; margin: 0; padding: 16px 24px 18px; }
.cs-upd-steps li { align-items: center; color: var(--ui-text-tertiary); display: flex; font-size: 13.5px; gap: 10px; }
.cs-upd-steps li > i { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: block; height: 13px; width: 13px; }
.cs-upd-steps li[data-state=done] { color: var(--ui-text-secondary); }
.cs-upd-steps li[data-state=done] > :first-child { color: var(--ui-green); }
.cs-upd-steps li[data-state=now] { color: var(--ui-text-primary); font-weight: 600; }
.cs-upd-pre { background: var(--ui-bg-quaternary); font: 11.5px/1.5 ${MONO}; margin: 0; max-height: 160px; overflow: auto; padding: 8px 10px; white-space: pre-wrap; }
`
