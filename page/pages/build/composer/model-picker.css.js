export const MODEL_PICKER_CSS = `
/* model and effort: the button under the message box */
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
.cs-b-mp-bolt { align-items: center; color: var(--ui-yellow); display: inline-flex; flex: none; }
/* the panel: provider rail | models | effort, and the speed bar along the bottom */
.cs-b-mp-pop { animation: cs-b-in .14s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 12px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 18px 48px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; left: 0; max-width: calc(100vw - 24px); overflow: hidden; position: absolute; top: calc(100% + 6px); width: 560px; z-index: 30; }
.cs-b-mp-pop.up { bottom: calc(100% + 8px); top: auto; }
.cs-b-mp-body { display: flex; height: 304px; min-height: 0; }
.cs-b-mp-rail { align-items: center; border-right: 1px solid var(--ui-stroke-tertiary); display: flex; flex: none; flex-direction: column; gap: 4px; overflow-y: auto; padding: 8px 0; scrollbar-width: none; width: 46px; }
.cs-b-mp-tile { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 7px; color: var(--ui-text-tertiary); cursor: pointer; display: flex; flex: none; font: 800 12px/1 var(--dt-font-sans, inherit); height: 30px; justify-content: center; position: relative; width: 30px; }
.cs-b-mp-tile:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-mp-tile[aria-pressed='true'] { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-mp-tile[aria-pressed='true']::before { background: var(--ui-accent); border-radius: 0 2px 2px 0; content: ''; height: 18px; left: -8px; position: absolute; top: 6px; width: 2px; }
.cs-b-mp-sep { background: var(--ui-stroke-tertiary); flex: none; height: 1px; margin: 2px 0; width: 22px; }
.cs-b-mp-models { display: flex; flex: 1; flex-direction: column; min-width: 0; }
.cs-b-mp-search { align-items: center; border-bottom: 1px solid var(--ui-stroke-secondary); color: var(--ui-text-quaternary); display: flex; gap: 8px; margin: 8px 10px 2px; padding: 5px 6px; }
.cs-b-mp-search:focus-within { border-bottom-color: var(--ui-accent); }
.cs-b-mp-search input { background: transparent; border: 0; color: var(--ui-text-primary); flex: 1; font: inherit; font-size: 13px; min-width: 0; outline: none; }
.cs-b-mp-head { color: var(--ui-text-quaternary); display: flex; flex-wrap: wrap; font-size: 11px; gap: 0 5px; min-width: 0; padding: 6px 16px 2px; }
.cs-b-mp-head b { color: var(--ui-text-secondary); font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
.cs-b-mp-head span { white-space: nowrap; }
.cs-b-mp-list { display: flex; flex: 1; flex-direction: column; gap: 1px; min-height: 0; -webkit-mask-image: linear-gradient(black calc(100% - 28px), transparent); mask-image: linear-gradient(black calc(100% - 28px), transparent); overflow-y: auto; overscroll-behavior: contain; padding: 4px 8px 24px; }
.cs-b-mp-list > .cs-faint { margin: 0; padding: 10px 8px; }
.cs-b-mp-group { color: var(--ui-text-quaternary); flex: none; font: 700 9.5px/1.3 var(--dt-font-mono, ui-monospace, monospace); letter-spacing: .12em; padding: 8px 8px 3px; text-transform: uppercase; }
.cs-b-mp-item { align-items: center; border-radius: 7px; display: flex; flex: none; min-width: 0; }
.cs-b-mp-item:hover { background: var(--ui-bg-quaternary); }
.cs-b-mp-item.on { background: color-mix(in srgb, var(--ui-accent) 12%, transparent); }
.cs-b-mp-row { align-items: center; appearance: none; background: transparent; border: 0; color: var(--ui-text-primary); cursor: pointer; display: flex; flex: 1; font: inherit; font-size: 13px; gap: 8px; min-width: 0; padding: 6px 4px 6px 8px; text-align: left; }
.cs-b-mp-glyph { color: var(--ui-text-quaternary); flex: none; font: 800 10px/1 var(--dt-font-sans, inherit); text-align: center; width: 16px; }
.cs-b-mp-label { min-width: 0; overflow-wrap: anywhere; }
.cs-b-mp-tag { border: 1px solid var(--ui-stroke-secondary); border-radius: 4px; color: var(--ui-text-tertiary); flex: none; font-size: 10px; line-height: 15px; padding: 0 5px; }
.cs-b-mp-check { color: var(--ui-text-secondary); display: inline-flex; flex: none; }
.cs-b-mp-label.two { display: flex; flex-direction: column; white-space: normal; }
.cs-b-mp-label.two > span { overflow-wrap: anywhere; }
.cs-b-mp-from { color: var(--ui-text-quaternary); font-size: 11px; line-height: 1.3; }
.cs-b-mp-star { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 5px; color: var(--ui-text-quaternary); cursor: pointer; display: inline-flex; flex: none; height: 24px; justify-content: center; margin-right: 4px; opacity: 0; width: 24px; }
.cs-b-mp-item:hover .cs-b-mp-star, .cs-b-mp-item.on .cs-b-mp-star, .cs-b-mp-star:focus-visible, .cs-b-mp-item.starred .cs-b-mp-star { opacity: 1; }
.cs-b-mp-star:hover { color: var(--ui-text-primary); }
.cs-b-mp-item.starred .cs-b-mp-star { color: var(--ui-yellow); }
.cs-b-mp-effort { border-left: 1px solid var(--ui-stroke-tertiary); display: flex; flex: none; flex-direction: column; min-height: 0; padding: 8px 0 0; width: 172px; }
.cs-b-mp-ehead { align-items: baseline; color: var(--ui-text-tertiary); display: flex; font-size: 12px; gap: 8px; padding: 5px 14px 6px; white-space: nowrap; }
.cs-b-mp-emodel { color: var(--ui-text-quaternary); font-size: 11px; margin-left: auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.cs-b-mp-levels { display: flex; flex-direction: column; }
.cs-b-mp-levels button { align-items: center; appearance: none; background: transparent; border: 0; color: var(--ui-text-primary); cursor: pointer; display: flex; font: inherit; font-size: 13px; justify-content: space-between; padding: 5px 14px; text-align: left; white-space: nowrap; }
.cs-b-mp-levels button:hover:not(:disabled) { background: var(--ui-bg-quaternary); }
.cs-b-mp-levels button[aria-checked='true'] { background: color-mix(in srgb, var(--ui-accent) 10%, transparent); }
.cs-b-mp-levels button:disabled { color: var(--ui-text-quaternary); cursor: default; }
.cs-b-mp-enote { border-top: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-tertiary); font-size: 11px; line-height: 1.35; margin-top: auto; padding: 8px 14px 10px; }
.cs-b-mp-enote b { color: var(--ui-text-primary); display: block; font-size: 12px; font-weight: 500; }
.cs-b-mp-bar { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 10px; min-height: 44px; padding: 7px 10px; }
.cs-b-seg { background: var(--ui-bg-quaternary); border-radius: 8px; display: flex; gap: 2px; padding: 2px; }
.cs-b-seg button { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 4px; padding: 4px 10px; transition: background .12s ease, color .12s ease; white-space: nowrap; }
.cs-b-seg button:hover:not(:disabled) { color: var(--ui-text-primary); }
.cs-b-seg button[aria-checked='true'] { background: var(--ui-bg-secondary); box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-primary); }
.cs-b-seg button.cs-b-mp-fast[aria-checked='true'] { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 55%, transparent); color: var(--ui-yellow); }
.cs-b-seg button:disabled { cursor: default; opacity: .5; }
.cs-b-mp-manage { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 4px; padding: 4px 6px; white-space: nowrap; }
.cs-b-mp-manage:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-mp-held { color: var(--ui-text-tertiary); font-size: 11.5px; white-space: nowrap; }
.cs-b-mp-confirm { align-items: center; background: color-mix(in srgb, var(--ui-yellow) 10%, var(--ui-bg-secondary)); border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; font-size: 12px; gap: 8px; padding: 8px 12px; }
.cs-b-mp-pop.narrow .cs-b-mp-effort { width: 120px; }
.cs-b-mp-pop.narrow .cs-b-mp-emodel { display: none; }
/* too narrow for three columns: Effort moves under the models as a wrapping row */
.cs-b-mp-pop.tiny .cs-b-mp-body { flex-wrap: wrap; height: auto; }
.cs-b-mp-pop.tiny .cs-b-mp-rail, .cs-b-mp-pop.tiny .cs-b-mp-models { height: 250px; }
.cs-b-mp-pop.tiny .cs-b-mp-effort { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); flex-basis: 100%; padding: 4px 8px 8px; width: auto; }
.cs-b-mp-pop.tiny .cs-b-mp-ehead { padding: 4px 6px; }
.cs-b-mp-pop.tiny .cs-b-mp-levels { flex-direction: row; flex-wrap: wrap; gap: 2px; }
.cs-b-mp-pop.tiny .cs-b-mp-levels button { border-radius: 6px; gap: 4px; justify-content: center; padding: 4px 8px; }
.cs-b-comp-row { align-items: center; display: flex; gap: 8px; min-width: 0; }
@container (max-width: 560px) { .cs-b-mp-name, .cs-b-mp-dot { display: none; } }
.cs-sr { clip: rect(0 0 0 0); height: 1px; overflow: hidden; position: absolute; white-space: nowrap; width: 1px; }
.cs-b-link { appearance: none; background: none; border: 0; color: var(--ui-accent); cursor: pointer; font: inherit; font-size: 12px; padding: 0; }
`
