import { MONO } from '../styles/tokens.js'

export const EMULATOR_CSS = `
/* emulator: bar above ModRetro's real player */
.cs-reload { align-items: center; background: var(--ui-bg-secondary); color: var(--ui-text-primary); display: flex; flex-wrap: wrap; gap: 12px; padding: 10px clamp(12px, 2cqi, 32px); }
.cs-reload .dot { animation: cs-pulse 1.2s ease-in-out infinite; background: var(--ui-accent); flex: none; height: 8px; width: 8px; }
@keyframes cs-pulse { 50% { opacity: .3; } }
.cs-rp-bar { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 6px; padding: 8px clamp(12px, 2cqi, 32px); }
.cs-rp-focus { align-items: center; color: var(--ui-text-quaternary); display: inline-flex; font: 700 9.5px ${MONO}; gap: 6px; letter-spacing: .1em; padding: 0 8px; text-transform: uppercase; }
.cs-rp-focus i { background: var(--ui-text-quaternary); border-radius: 50%; height: 7px; width: 7px; }
.cs-rp-focus.on { color: var(--ui-green); }
.cs-rp-focus.on i { background: var(--ui-green); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-green) 25%, transparent); }
.cs-rp-caps { background: var(--ui-bg-quaternary); border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 12px; overflow-x: auto; padding: 12px clamp(12px, 2cqi, 32px); }
.cs-rp-caps figure { display: flex; flex: none; flex-direction: column; gap: 4px; margin: 0; }
.cs-rp-caps img, .cs-rp-caps video { background: var(--ui-bg-tertiary); height: 120px; image-rendering: pixelated; }
.cs-rp-caps figcaption { color: var(--ui-text-tertiary); font: 10px ${MONO}; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-rp-stage { height: max(560px, calc(100svh - 150px)); position: relative; }
.cs-rp-stage.off { height: 600px; left: -99999px; pointer-events: none; position: absolute; top: 0; visibility: hidden; width: 900px; }
.cs-rp-stage > iframe { border: 0; display: block; height: 100%; width: 100%; }
.cs-rp-stage:fullscreen { background: var(--ui-bg-editor); }
.cs-rp-note { align-items: center; background: var(--ui-bg-secondary); border-left: 2px solid var(--ui-red); display: flex; flex-wrap: wrap; gap: 8px 14px; margin: 10px clamp(12px, 2cqi, 32px) 0; padding: 10px 14px; }
.cs-rp-note > div { display: grid; flex: 1 1 320px; gap: 2px; min-width: 0; }
.cs-rp-note b { color: var(--ui-text-primary); font-size: 13px; }
.cs-rp-note span { color: var(--ui-text-secondary); font-size: 12px; line-height: 1.45; }
.cs-rp-void { background: var(--ui-bg-quaternary); height: 100%; opacity: .5; }
.cs-pad.flush .cs-rp-stage:not(.off) { height: max(500px, calc(100svh - 230px)); }
.cs-rp-foot { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 6px 12px; padding: 6px clamp(12px, 2cqi, 32px); }
.cs-rp-hint { color: var(--ui-text-tertiary); font-size: 12px; }
.cs-side-note { align-items: center; background: var(--ui-bg-secondary); border-bottom: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-secondary); display: flex; font-size: 12px; gap: 8px; line-height: 1.4; padding: 5px clamp(10px, 2cqi, 20px); }
.cs-side-note > i { color: var(--ui-accent); flex: none; }
.cs-side-note-text { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.cs-side-note-x { background: none; border: 0; border-radius: 4px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; flex: none; padding: 2px; }
.cs-side-note-x:hover { color: var(--ui-text-primary); }
.cs-rp-msg.cs-rp-away { justify-items: center; text-align: center; }
.cs-rp-away .cs-eyebrow { justify-content: center; }
.cs-side { height: 100%; min-height: 0; overflow: hidden auto; }
.cs-side .cs-rp-stage { flex: 1 1 auto; height: auto; min-height: 360px; }
.cs-side .cs-rp-bar, .cs-side .cs-reload { padding-left: 10px; padding-right: 10px; }
.cs-side .cs-rp-note { margin: 8px 10px 0; }
.cs-rp-msg { align-content: center; display: grid; gap: 14px; height: 100%; justify-items: start; margin: 0 auto; max-width: 560px; padding: 24px; }
`
