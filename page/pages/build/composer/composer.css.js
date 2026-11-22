export const COMPOSER_CSS = `
/* status and the message box */
.cs-b-comp { align-self: center; background: var(--ui-bg-secondary); border-radius: 16px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); box-sizing: border-box; display: flex; flex-direction: column; gap: 8px; margin: 0 clamp(14px, 3cqi, 28px) 16px; max-width: var(--cs-b-width); padding: 9px 9px 9px 14px; width: calc(100% - 2 * clamp(14px, 3cqi, 28px)); }
.cs-b-comp.asking { gap: 4px; padding: 10px 10px 8px 12px; }
.cs-b-comp:focus-within { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 60%, var(--ui-stroke-secondary)); }
.cs-b-comp textarea { background: transparent; border: 0; color: var(--ui-text-primary); font: inherit; font-size: 13.5px; line-height: 1.5; max-height: 200px; min-height: 22px; outline: none; padding: 4px 0; resize: none; }
.cs-b-send, .cs-b-stop { align-items: center; appearance: none; border: 0; border-radius: 50%; cursor: pointer; display: inline-flex; flex: none; height: 30px; justify-content: center; transition: opacity .15s ease, transform .1s ease; width: 30px; }
.cs-b-send { background: var(--ui-accent); color: white; }
.cs-b-send:disabled { background: var(--ui-bg-quaternary); color: var(--ui-text-quaternary); cursor: default; }
.cs-b-send:not(:disabled):active, .cs-b-stop:active { transform: scale(.94); }
.cs-b-stop { background: var(--ui-text-primary); }
.cs-b-stop i { background: var(--ui-bg-editor); border-radius: 2px; height: 10px; width: 10px; }
.cs-b-status { align-items: center; animation: cs-b-in .18s ease-out; border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; font-size: 12px; gap: 8px; margin: -1px -1px 0 -6px; padding: 0 0 8px; }
.cs-b-status b { color: var(--ui-text-primary); font-weight: 600; }
.cs-b-status.wait b { color: var(--ui-yellow); }
.cs-b-status.stuck b { color: var(--ui-red); }
.cs-b-pulse { animation: cs-b-pulse 1.6s infinite; background: var(--ui-green); border-radius: 50%; flex: none; height: 7px; width: 7px; }
.cs-b-pulse.wait { animation-name: cs-b-pulse-y; background: var(--ui-yellow); }
.cs-b-pulse.off { animation: none; background: var(--ui-text-quaternary); }
@keyframes cs-b-pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--ui-green) 55%, transparent); } 70%, 100% { box-shadow: 0 0 0 7px transparent; } }
@keyframes cs-b-pulse-y { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--ui-yellow) 55%, transparent); } 70%, 100% { box-shadow: 0 0 0 7px transparent; } }
`
