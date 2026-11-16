export const BUILD_CSS = `
/* build: games rail · the conversation with the agent (the game plays inside it) */
.cs-pad.build { gap: 0; padding: 0; }
.cs-studio-needed { align-self: center; display: flex; flex-direction: column; gap: 12px; margin: 48px auto; max-width: 60ch; }
.cs-studio-needed > h2 { font-size: 1.15rem; margin: 0; }
.cs-b { display: grid; grid-template-columns: minmax(0, 1fr); height: calc(100svh - 130px); min-height: 480px; position: relative; }
.cs-b-game { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; gap: 8px; padding: 7px 8px; text-align: left; transition: background .12s ease; }
.cs-b-game[aria-current] { background: var(--ui-bg-quaternary); box-shadow: inset 2px 0 0 var(--ui-accent); color: var(--ui-text-primary); }
.cs-b-game:hover, .cs-b-game:focus-visible { background: var(--ui-bg-quaternary); }
.cs-b-game .nm { display: flex; flex: 1; flex-direction: column; min-width: 0; }
.cs-b-game .nm b { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-game .nm small { color: var(--ui-text-quaternary); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-game.wait .nm small { color: var(--ui-yellow); }
.cs-b-game .dot { background: var(--ui-text-quaternary); border-radius: 50%; flex: none; height: 6px; width: 6px; }
.cs-b-game .dot.good { background: var(--ui-green); } .cs-b-game .dot.warn { background: var(--ui-yellow); } .cs-b-game .dot.bad { background: var(--ui-red); } .cs-b-game .dot.accent { background: var(--ui-accent); }
.cs-b-game .dot.new { background: var(--ui-accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-accent) 25%, transparent); height: 7px; width: 7px; }
.cs-b-game .dot.wait { animation: cs-b-pulse-y 1.6s infinite; background: var(--ui-yellow); height: 7px; width: 7px; }
.cs-b-spin { animation: cs-b-spin .9s linear infinite; border: 2px solid var(--ui-accent); border-radius: 50%; border-right-color: transparent; display: inline-block; flex: none; height: 10px; width: 10px; }
@keyframes cs-b-spin { to { transform: rotate(360deg); } }
`
