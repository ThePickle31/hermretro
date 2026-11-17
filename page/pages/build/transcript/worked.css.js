import { MONO } from '#shared/styles/tokens.js'

export const WORKED_CSS = `
/* Worked for… */
.cs-b-wk { display: flex; flex-direction: column; }
.cs-b-wk-row { align-items: center; display: flex; flex-wrap: wrap; gap: 4px 8px; }
.cs-b-wk-head { align-items: center; align-self: flex-start; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; flex-wrap: wrap; font: inherit; font-size: 12px; gap: 7px; margin-left: -6px; max-width: 100%; padding: 4px 8px 4px 6px; transition: background .12s ease, color .12s ease; }
.cs-b-wk-head:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-secondary); }
.cs-b-wk-head b { color: var(--ui-text-secondary); font-weight: 600; }
.cs-b-ico { align-items: center; color: var(--ui-green); display: inline-flex; flex: none; height: 14px; justify-content: center; width: 14px; }
.cs-b-ico.interrupted { color: var(--ui-text-tertiary); } .cs-b-ico.error { color: var(--ui-red); }
.cs-b-wk-body { display: grid; grid-template-rows: 0fr; transition: grid-template-rows .22s ease; }
.cs-b-wk[data-open='true'] > .cs-b-wk-body { grid-template-rows: 1fr; }
.cs-b-wk-inner { border-left: 2px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; gap: 3px; margin: 6px 0 2px 6px; min-height: 0; overflow: hidden; padding-left: 12px; }
.cs-b-wk[data-open='false'] .cs-b-wk-inner { margin-top: 0; }
.cs-b-wk.live .cs-b-wk-inner { border-left-color: color-mix(in srgb, var(--ui-accent) 55%, transparent); }
.cs-b-tool { animation: cs-b-in .16s ease-out; color: var(--ui-text-tertiary); display: flex; flex-direction: column; font-size: 12.5px; gap: 5px; padding: 3px 0; }
.cs-b-tool-line { align-items: center; display: flex; gap: 8px; min-width: 0; }
.cs-b-tool[data-state='running'] { color: var(--ui-text-primary); }
.cs-b-tool[data-state='running'] .cs-b-ico { color: var(--ui-accent); }
.cs-b-tool[data-state='failed'] .cs-b-ico { color: var(--ui-red); }
.cs-b-tool[data-state='stopped'] .cs-b-ico { color: var(--ui-text-quaternary); }
.cs-b-tool-name { flex: none; }
.cs-b-tool-detail { color: var(--ui-text-quaternary); flex: 0 1 auto; font-size: 11.5px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-tool[data-state='failed'] .cs-b-tool-detail { color: var(--ui-red); white-space: normal; }
.cs-b-tool-assets { padding-left: 22px; }
.cs-b-next { color: var(--ui-text-quaternary); font-size: 12px; padding-left: 22px; }
.cs-b-dur { color: var(--ui-text-quaternary); flex: none; font: 600 10.5px ${MONO}; font-variant-numeric: tabular-nums; }
.cs-b-bar { background: var(--ui-bg-quaternary); border-radius: 2px; height: 3px; margin-left: 22px; max-width: 220px; overflow: hidden; }
.cs-b-bar i { background: var(--ui-accent); display: block; height: 100%; transition: width .3s ease; }
.cs-b-shimmer { animation: cs-b-sheen 2.2s linear infinite; background: linear-gradient(90deg, var(--ui-text-secondary) 0%, var(--ui-text-primary) 40%, var(--ui-text-secondary) 60%) 0 0 / 200% 100%; -webkit-background-clip: text; background-clip: text; color: transparent; }
@keyframes cs-b-sheen { to { background-position: -200% 0; } }
.cs-b-wk-assets { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-accent); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 7px; padding: 3px 7px 3px 4px; transition: background .12s ease; }
.cs-b-wk-assets:hover { background: var(--ui-bg-quaternary); }
.cs-b-stack { align-items: center; display: inline-flex; }
.cs-b-stack-i { background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-secondary) 0 50%) 0 0 / 6px 6px; border-radius: 4px; box-shadow: 0 0 0 1.5px var(--ui-bg-editor); display: inline-flex; height: 20px; overflow: hidden; width: 20px; }
.cs-b-stack-i + .cs-b-stack-i { margin-left: -6px; }
.cs-b-stack-i img { height: 100%; image-rendering: pixelated; object-fit: cover; width: 100%; }
.cs-b-wk-inner.phased { border-left: 0; gap: 0; margin-left: 0; padding-left: 0; }
.cs-b-phases { background: var(--ui-bg-secondary); border-radius: 9px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); margin: 4px 0 2px; max-width: 680px; overflow: hidden; }
.cs-b-ph + .cs-b-ph { border-top: 1px solid var(--ui-stroke-tertiary); }
.cs-b-ph-head { align-items: center; appearance: none; background: transparent; border: 0; border-radius: inherit; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; font-size: 12.5px; gap: 8px; padding: 7px 10px; text-align: left; width: 100%; }
.cs-b-ph-head:hover { background: var(--ui-bg-quaternary); }
.cs-b-ph[data-state='running'] .cs-b-ico { color: var(--ui-accent); } .cs-b-ph[data-state='failed'] .cs-b-ico { color: var(--ui-red); }
.cs-b-ph-name { font-weight: 600; }
.cs-b-ph-meta { color: var(--ui-text-quaternary); flex: none; font-size: 11.5px; }
.cs-b-ph-head > i { color: var(--ui-text-tertiary); }
.cs-b-ph-body { display: flex; flex-direction: column; gap: 3px; padding: 0 12px 9px 32px; }
.cs-b-ph-more { align-self: flex-start; appearance: none; background: none; border: 0; border-radius: 4px; color: var(--ui-text-quaternary); cursor: pointer; font: inherit; font-size: 11.5px; padding: 2px 4px; margin-left: -4px; }
.cs-b-ph-more:hover { color: var(--ui-accent); }
.cs-b-rimgs { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 4px; }
.cs-b-rchip { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: inherit; cursor: zoom-in; display: inline-flex; font: inherit; gap: 9px; max-width: 280px; min-width: 0; padding: 5px 12px 5px 5px; text-align: left; transition: box-shadow .15s ease; }
.cs-b-rchip:hover { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-rchip .cs-col { gap: 0; line-height: 1.35; min-width: 0; }
.cs-b-rchip b { font-size: 12.5px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-rchip .cs-col > span { color: var(--ui-text-tertiary); font-size: 11px; }
.cs-b-rchip.loading { animation: cs-b-skel 1.2s ease-in-out infinite; background: var(--ui-bg-quaternary); height: 50px; width: 180px; }
.cs-b-rchip .cs-b-th { pointer-events: none; }
.cs-b-turn[data-flash] .cs-b-her { animation: cs-b-flash 1.6s ease-out; border-radius: 10px; }
@keyframes cs-b-flash { 0%, 40% { box-shadow: 0 0 0 6px color-mix(in srgb, var(--ui-accent) 16%, transparent); background: color-mix(in srgb, var(--ui-accent) 6%, transparent); } }
.cs-b-badge { background: var(--ui-accent); border-radius: 999px; color: var(--ui-bg-editor); font-size: 10px; font-weight: 700; line-height: 16px; padding: 0 6px; }
.cs-b-latest { align-items: center; animation: cs-b-in .22s ease-out; background: var(--ui-bg-secondary); border-radius: 10px; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 35%, transparent); display: flex; gap: 12px; margin: 6px 0 2px; padding: 8px; }
.cs-b-latest .cs-col { gap: 2px; min-width: 0; }
.cs-b-latest b { font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
`
