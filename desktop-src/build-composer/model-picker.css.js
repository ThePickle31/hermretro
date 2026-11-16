export const MODEL_PICKER_CSS = `
/* model and effort */
.cs-b-mp { position: relative; min-width: 0; }
.cs-b-mp-chip { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 8px; color: var(--ui-text-secondary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 6px; max-width: 100%; min-width: 0; padding: 4px 8px 4px 5px; transition: background .12s ease, color .12s ease; white-space: nowrap; }
.cs-b-mp-chip:hover, .cs-b-mp-chip.open { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-mp-chip.open { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); }
.cs-b-mp-chip:disabled { cursor: default; opacity: .55; }
.cs-b-mp-chip.warn { color: var(--ui-yellow); }
.cs-b-mp-name { overflow: hidden; text-overflow: ellipsis; }
.cs-b-mp-dot { color: var(--ui-text-quaternary); }
.cs-b-mp-next { border: 1px solid color-mix(in srgb, var(--ui-accent) 50%, transparent); border-radius: 4px; color: var(--ui-accent); font-size: 10px; line-height: 15px; padding: 0 5px; }
.cs-b-mp-mark { align-items: center; background: color-mix(in srgb, var(--ui-accent) 22%, var(--ui-bg-quaternary)); border-radius: 4px; color: var(--ui-text-primary); display: inline-flex; flex: none; font: 800 9px/1 var(--dt-font-sans, inherit); height: 16px; justify-content: center; width: 16px; }
.cs-b-mp-pop { animation: cs-b-in .14s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 12px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 18px 48px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; left: 0; max-width: calc(100vw - 24px); overflow: hidden; position: absolute; top: calc(100% + 6px); width: 580px; z-index: 30; }
.cs-b-mp-pop.up { bottom: calc(100% + 8px); top: auto; }
.cs-b-mp-body { display: flex; min-height: 0; }
.cs-b-mp-providers { border-right: 1px solid var(--ui-stroke-tertiary); display: flex; flex: none; flex-direction: column; gap: 2px; padding: 10px 6px; width: 190px; }
.cs-b-mp-providers > .cs-eyebrow { padding: 0 8px 4px; }
.cs-b-mp-providers > .cs-faint { padding: 4px 8px; }
.cs-b-mp-providers > .cs-b-link { align-self: flex-start; padding: 6px 8px; }
.cs-b-mp-prov, .cs-b-mp-row { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 7px; color: var(--ui-text-primary); cursor: pointer; display: flex; font: inherit; font-size: 12.5px; gap: 8px; min-width: 0; padding: 6px 8px; text-align: left; width: 100%; }
.cs-b-mp-prov:hover, .cs-b-mp-row:hover { background: var(--ui-bg-quaternary); }
.cs-b-mp-prov[aria-pressed='true'] { background: var(--ui-bg-quaternary); box-shadow: inset 2px 0 0 var(--ui-accent); }
.cs-b-mp-pname { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-mp-prov small { color: var(--ui-text-quaternary); font-size: 10.5px; }
.cs-b-mp-models { display: flex; flex: 1; flex-direction: column; min-width: 0; }
.cs-b-mp-search { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-quaternary); display: flex; gap: 8px; padding: 8px 12px; }
.cs-b-mp-search input { background: transparent; border: 0; color: var(--ui-text-primary); flex: 1; font: inherit; font-size: 12.5px; min-width: 0; outline: none; }
.cs-b-mp-list { display: flex; flex-direction: column; max-height: 236px; overflow-y: auto; overscroll-behavior: contain; padding: 6px; }
.cs-b-mp-list > .cs-faint { margin: 0; padding: 10px; }
.cs-b-mp-row[aria-selected='true'] { background: color-mix(in srgb, var(--ui-accent) 12%, transparent); }
.cs-b-mp-check { color: var(--ui-accent); display: inline-flex; flex: none; width: 14px; }
.cs-b-mp-label { display: flex; flex-direction: column; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-mp-label small { color: var(--ui-text-quaternary); font-size: 10.5px; }
.cs-b-mp-tag { border: 1px solid var(--ui-stroke-secondary); border-radius: 4px; color: var(--ui-text-tertiary); flex: none; font-size: 10px; line-height: 15px; padding: 0 5px; }
.cs-b-mp-effort { border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; gap: 7px; padding: 10px 12px 12px; }
.cs-b-seg { background: var(--ui-bg-quaternary); border-radius: 8px; display: flex; gap: 2px; padding: 2px; }
.cs-b-seg button { appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-tertiary); cursor: pointer; flex: 1; font: inherit; font-size: 11.5px; padding: 5px 0; transition: background .12s ease, color .12s ease; }
.cs-b-seg button:hover:not(:disabled) { color: var(--ui-text-primary); }
.cs-b-seg button[aria-checked='true'] { background: var(--ui-bg-secondary); box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-primary); }
.cs-b-seg button:disabled { cursor: default; opacity: .5; }
.cs-b-mp-confirm { align-items: center; background: color-mix(in srgb, var(--ui-yellow) 10%, var(--ui-bg-secondary)); border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; font-size: 12px; gap: 8px; padding: 8px 12px; }
.cs-b-mp-foot { border-top: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-tertiary); font-size: 11.5px; margin: 0; padding: 7px 12px; }
.cs-b-comp-row { align-items: center; display: flex; gap: 8px; min-width: 0; }
.cs-b-mp-pop.narrow .cs-b-mp-providers { width: 140px; }
.cs-b-mp-pop.narrow .cs-b-seg button { font-size: 10.5px; }
@container (max-width: 560px) { .cs-b-mp-name, .cs-b-mp-dot { display: none; } }
.cs-sr { clip: rect(0 0 0 0); height: 1px; overflow: hidden; position: absolute; white-space: nowrap; width: 1px; }
.cs-b-link { appearance: none; background: none; border: 0; color: var(--ui-accent); cursor: pointer; font: inherit; font-size: 12px; padding: 0; }
`
