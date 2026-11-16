import { MONO } from '../styles/tokens.js'

export const CARDS_CSS = `
/* cards */
.cs-b-card { animation: cs-b-in .2s ease-out; border-radius: 12px; display: flex; flex-direction: column; gap: 10px; padding: 12px 14px; }
.cs-b-card.ask { background: color-mix(in srgb, var(--ui-accent) 7%, var(--ui-bg-secondary)); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 45%, transparent), 0 8px 26px color-mix(in srgb, black 18%, transparent); }
.cs-b-card.warn { background: color-mix(in srgb, var(--ui-yellow) 7%, var(--ui-bg-secondary)); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 45%, transparent); }
.cs-b-card.bad { background: color-mix(in srgb, var(--ui-red) 6%, var(--ui-bg-secondary)); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-red) 40%, transparent); }
.cs-b-card.bad > .cs-row > i { color: var(--ui-red); }
.cs-b-card p { margin: 0; }
.cs-b-qs { display: flex; flex-direction: column; gap: 14px; }
.cs-b-q { display: flex; flex-direction: column; gap: 7px; }
.cs-b-qt { font-weight: 600; margin: 0; }
.cs-b-choices { display: grid; gap: 6px; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
.cs-b-choice { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-primary); cursor: pointer; display: flex; font: inherit; gap: 9px; padding: 8px 10px; text-align: left; transition: background .12s ease, box-shadow .12s ease; }
.cs-b-choice:hover { background: var(--ui-bg-quaternary); }
.cs-b-choice kbd { border: 1px solid var(--ui-stroke-secondary); border-bottom-width: 2px; border-radius: 3px; color: var(--ui-text-tertiary); font: 600 10px ${MONO}; padding: 0 4px; }
.cs-b-choice[aria-pressed='true'] { background: color-mix(in srgb, var(--ui-accent) 16%, var(--ui-bg-secondary)); box-shadow: inset 0 0 0 1.5px var(--ui-accent); }
.cs-b-sugg { border: 1px solid color-mix(in srgb, var(--ui-accent) 50%, transparent); border-radius: 3px; color: var(--ui-accent); flex: none; font: 700 9px ${MONO}; letter-spacing: .08em; padding: 0 4px; text-transform: uppercase; }
.cs-b-own { background: transparent; border: 0; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); color: var(--ui-text-primary); font: inherit; padding: 7px 10px; }
.cs-b-cmd { background: var(--ui-bg-quaternary); border-radius: 6px; font: 11px/1.5 ${MONO}; margin: 0; overflow: auto; padding: 8px 10px; white-space: pre-wrap; }
.cs-b-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.cs-b-chip { align-items: center; background: var(--ui-bg-secondary); border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); display: inline-flex; font-size: 11.5px; gap: 5px; max-width: 100%; overflow: hidden; padding: 2px 9px; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-chip.pic { padding-left: 3px; }
.cs-b-chip.pic img { border-radius: 4px; display: block; flex: none; height: 20px; image-rendering: pixelated; object-fit: contain; width: 20px; }
.cs-b-tool .cs-b-chips { padding-left: 22px; }
.cs-b-stopped { align-items: center; color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font-size: 12px; gap: 10px; }

/* empty and loading */
.cs-b-empty { align-content: center; display: grid; flex: 1; gap: 12px; justify-items: start; padding: 24px; }
.cs-b-hello { padding: 30px 0 4px; }
.cs-b-skel { display: flex; flex-direction: column; gap: 10px; margin-top: 18px; }
.cs-b-skel i { animation: cs-b-skel 1.2s ease-in-out infinite; background: var(--ui-bg-quaternary); border-radius: 8px; display: block; height: 14px; }
.cs-b-skel i:nth-child(1) { align-self: flex-end; height: 34px; width: 46%; } .cs-b-skel i:nth-child(2) { width: 82%; } .cs-b-skel i:nth-child(3) { width: 64%; }
.cs-b-jump { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 999px; bottom: 12px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary), 0 6px 18px color-mix(in srgb, black 30%, transparent); color: var(--ui-text-primary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 6px; left: 50%; padding: 5px 12px; position: absolute; transform: translateX(-50%); }
`
