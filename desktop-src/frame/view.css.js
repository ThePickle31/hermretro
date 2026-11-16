// Styles the frame adds to ModRetro's player page.
//  - Always: the Hermes Edition finishes first in the colour rail, and in the full player the handheld
//    fills the frame (sized by its height, capped by its width) instead of the engine's fixed 420 px.
//  - Inline UI (`html[data-hr-ui=inline]`): the page draws every control, so the player's header,
//    colour rail, capture rail, source switch and key hints are hidden and the handheld (view
//    `device`) or the bare screen (view `screen`) fills the frame exactly. The page sizes the frame to
//    a whole-number scale, so the game stays sharp.
//  - The annotate overlay (`.hr-ann`): our own look, coloured by `--hr-accent` (set by the page).

const FULL = `
.codex-game-view .cgv-color[data-device-color^="hermes-"]{order:-4}
html:not([data-hr-ui=inline]) .codex-game-view .cgv-player,
html:not([data-hr-ui=inline]) .codex-game-view .cgv-mode-views{width:max(220px,min(calc((100svh - 136px)*850/1440),calc(100vw - 112px)));max-width:none}
`

const INLINE = `
html[data-hr-ui=inline],html[data-hr-ui=inline] body{margin:0;width:100%;height:100%;overflow:hidden!important;background:transparent!important}
html[data-hr-ui=inline] .codex-game-view{position:fixed;inset:0;display:grid;place-items:center;margin:0;padding:0;gap:0;min-height:0}
html[data-hr-ui=inline] .codex-game-view :is(.cgv-header,.cgv-colors,.cgv-recording,.cgv-source-modes,.cgv-hint-area,.cgv-install-slot,.cgv-device-view){display:none!important}
html[data-hr-ui=inline] .codex-game-view .cgv-mode-views{width:100vw;height:100vh;max-width:none;display:grid;place-items:center}
html[data-hr-ui=inline] .codex-game-view :is(.cgv-views-stage,.cgv-player,.cgv-device-stage){width:100%;height:100%;display:grid;place-items:center;margin:0}
html[data-hr-ui=inline] .codex-game-view .cgv-shared-footer{position:fixed;left:50%;bottom:8px;transform:translateX(-50%);width:min(320px,calc(100vw - 16px));margin:0;z-index:5}
html[data-hr-ui=inline] .codex-game-view .cgv-handheld{width:min(100vw,calc(100vh*850/1440));filter:none;overflow-clip-margin:0}
html[data-hr-ui=inline][data-hr-view=screen] .codex-game-view .cgv-handheld{width:min(100vw,calc(100vh*10/9));aspect-ratio:10/9;overflow:hidden;border-radius:4px}
html[data-hr-ui=inline][data-hr-view=screen] .codex-game-view :is(.cgv-shell,.cgv-title,.cgv-device-controls){display:none!important}
html[data-hr-ui=inline][data-hr-view=screen] .codex-game-view .cgv-screen{inset:0;top:0;left:0;width:100%;height:100%}
`

// The engine marks its selected target with its own orange outline (a fixed div it appends to the
// body, bridge.js) and explains annotate in its status line; our overlay and the page do both.
const ENGINE_ANNOTATE = `
body>div[aria-hidden=true][style*="z-index: 999"]{display:none!important}
html[data-hr-ui=inline] .codex-game-view[data-annotating=true] .cgv-status{display:none!important}
`

const OVERLAY = `
.hr-ann{position:fixed;z-index:40;cursor:crosshair;--hr-a:var(--hr-accent,#3d7bff);font:600 11.5px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.hr-ann .hr-veil{position:absolute;inset:0;background:#0a0f1950;pointer-events:none;border-radius:2px}
.hr-ann .hr-box{position:absolute;pointer-events:none;border-radius:3px}
.hr-ann .hr-box.hov{outline:2px dashed var(--hr-a);background:color-mix(in srgb,var(--hr-a) 14%,transparent)}
.hr-ann .hr-box.mark{outline:2px solid var(--hr-a);box-shadow:0 0 0 4px color-mix(in srgb,var(--hr-a) 30%,transparent)}
.hr-ann .hr-box.mark.on{outline-width:3px}
.hr-ann .hr-n{position:absolute;top:-9px;right:-9px;display:grid;place-items:center;width:18px;height:18px;border-radius:50%;background:var(--hr-a);color:#fff;font:700 10.5px/1 ui-monospace,monospace}
.hr-ann .hr-n.in-top{top:2px}
.hr-ann .hr-n.in-right{right:2px}
.hr-ann .hr-label{position:absolute;transform:translateY(calc(-100% - 6px));white-space:nowrap;pointer-events:none;background:#141b29ee;color:#e8edf6;border:1px solid #ffffff22;border-radius:7px;padding:3px 8px;box-shadow:0 6px 16px #0006}
.hr-ann .hr-frozen{position:absolute;left:8px;bottom:8px;pointer-events:none;background:#000b;color:#fff;border-radius:6px;padding:3px 8px;font:600 11px/1.2 ui-monospace,monospace}
.hr-ann .hr-tip{position:absolute;left:50%;bottom:8px;transform:translateX(-50%);pointer-events:none;white-space:nowrap;background:#000b;color:#fff;border-radius:999px;padding:4px 10px}
.hr-card{position:fixed;z-index:41;width:min(290px,calc(100vw - 16px));padding:12px;border-radius:12px;background:#141b29;color:#e8edf6;border:1px solid #ffffff22;box-shadow:0 18px 50px #0008;display:flex;flex-direction:column;gap:8px;cursor:default;font:13px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.hr-card small{color:#9aa8c0;margin-top:-6px}
.hr-card textarea{min-height:60px;resize:vertical;border:1px solid var(--hr-accent,#3d7bff);border-radius:8px;padding:7px 9px;font:inherit;color:inherit;background:#0d1320}
.hr-card div{display:flex;justify-content:flex-end;gap:6px}
.hr-card button{min-height:30px;padding:5px 11px;border:0;border-radius:8px;background:transparent;color:#9aa8c0;font:600 12.5px inherit;cursor:pointer}
.hr-card button[data-primary]{background:var(--hr-accent,#3d7bff);color:#fff}
`

export const FRAME_CSS = FULL + INLINE + ENGINE_ANNOTATE + OVERLAY
