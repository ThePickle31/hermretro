export const HEADER_CSS = `
/* the header: the game title and switcher (switcher.js), status pill and Builds menu (builds-menu.js) */
.cs-b-swwrap { align-items: center; display: flex; gap: 10px; min-width: 0; position: relative; }
.cs-b-sw { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 8px; color: var(--ui-text-primary); cursor: pointer; display: inline-flex; gap: 8px; margin-left: -8px; min-width: 0; padding: 3px 8px; transition: background .12s ease; }
.cs-b-sw:hover, .cs-b-sw.open { background: var(--ui-bg-quaternary); }
.cs-b-sw h2 { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-sw > i { color: var(--ui-text-tertiary); }
.cs-b-sw-pop { animation: cs-b-in .14s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 12px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 18px 48px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; gap: 2px; left: -8px; max-width: calc(100vw - 24px); padding: 6px; position: absolute; top: calc(100% + 6px); width: 340px; z-index: 30; }
.cs-b-sw-pop > .cs-eyebrow { padding: 8px 8px 2px; }
.cs-b-sw-list { display: flex; flex-direction: column; gap: 2px; max-height: min(60svh, 460px); overflow-y: auto; overscroll-behavior: contain; }
.cs-b-sw-pop .cs-b-game { outline: none; width: 100%; }
.cs-b-sw-new { color: var(--ui-accent); }
.cs-b-sw-thumb { align-items: center; aspect-ratio: 160 / 144; background: var(--ui-bg-quaternary); border-radius: 4px; color: var(--ui-text-tertiary); display: inline-flex; flex: none; font-size: 0; height: 28px; image-rendering: pixelated; justify-content: center; object-fit: cover; overflow: hidden; width: auto; }
.cs-b-sw-thumb.add { background: transparent; border: 1px dashed var(--ui-stroke-secondary); color: var(--ui-accent); }
.cs-b-sw-key { color: var(--ui-text-quaternary); flex: none; font: 600 10px var(--dt-font-mono, ui-monospace, monospace); margin-left: 4px; }
.cs-b-sw-empty { margin: 0; padding: 8px; }
.cs-b-sw-pop.lib { width: 400px; }
.cs-b-sw-thumb.edit { background: transparent; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-accent); }
.cs-b-sw-go { color: var(--ui-text-tertiary); flex: none; }
.cs-b-sw-back { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-primary); cursor: pointer; display: flex; font: inherit; font-weight: 600; gap: 8px; outline: none; padding: 6px 8px; text-align: left; }
.cs-b-sw-back > i { color: var(--ui-text-tertiary); }
.cs-b-sw-back:hover, .cs-b-sw-back:focus-visible { background: var(--ui-bg-quaternary); }
.cs-b-sw-search { align-items: center; background: var(--ui-bg-editor); border-radius: 7px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-quaternary); display: flex; gap: 8px; margin: 2px 2px 4px; padding: 6px 9px; }
.cs-b-sw-search:focus-within { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-sw-search input { background: transparent; border: 0; color: var(--ui-text-primary); flex: 1; font: inherit; font-size: 12.5px; min-width: 0; outline: none; }
.cs-b-sw-pop .cs-b-game .go { color: var(--ui-accent); flex: none; font-size: 11.5px; opacity: 0; }
.cs-b-sw-pop .cs-b-game:hover .go, .cs-b-sw-pop .cs-b-game:focus-visible .go { opacity: 1; }
.cs-b-sw-foot { border-top: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-quaternary); font-size: 11px; margin: 4px 0 0; padding: 7px 8px 3px; }
.cs-b-needs { appearance: none; background: var(--ui-yellow); border: 0; border-radius: 999px; color: var(--ui-bg-editor); cursor: pointer; flex: none; font: 700 11px/18px inherit; padding: 0 9px; white-space: nowrap; }
.cs-b-others { align-items: center; color: var(--ui-text-tertiary); display: inline-flex; flex: none; font-size: 11.5px; gap: 6px; white-space: nowrap; }
.cs-b-otherdot { background: var(--ui-accent); border-radius: 50%; box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-accent) 25%, transparent); flex: none; height: 7px; width: 7px; }
.cs-b-ctx { animation: cs-b-in .1s ease-out; background: linear-gradient(var(--ui-bg-tertiary, var(--ui-bg-secondary)), var(--ui-bg-tertiary, var(--ui-bg-secondary))), var(--ui-bg-editor); border-radius: 8px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 12px 30px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; gap: 1px; min-width: 180px; padding: 4px; position: absolute; z-index: 40; }
.cs-b-ctx button { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 5px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; font-size: 12px; gap: 8px; outline: none; padding: 6px 9px; text-align: left; }
.cs-b-ctx button:hover:not(:disabled), .cs-b-ctx button:focus-visible { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-ctx button.danger { color: var(--ui-red); }
.cs-b-ctx button:disabled { cursor: default; opacity: .45; }
.cs-b-ctx hr { border: 0; border-top: 1px solid var(--ui-stroke-tertiary); margin: 3px 2px; }
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
