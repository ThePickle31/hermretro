export const TRANSCRIPT_CSS = `
/* the conversation */
.cs-b-chat { display: flex; flex-direction: column; min-height: 0; min-width: 0; position: relative; }
.cs-b-head { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); box-sizing: border-box; display: flex; gap: 10px; min-height: 50px; padding: 8px clamp(14px, 3cqi, 28px); width: 100%; }
.cs-b-head .cs-word { font-size: 22px; }
.cs-top-profile { align-items: center; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-tertiary); cursor: default; display: inline-flex; font-size: 11px; gap: 5px; margin-left: 10px; padding: 1px 9px 1px 7px; white-space: nowrap; }
.cs-b-txwrap { display: flex; flex: 1; flex-direction: column; min-height: 0; position: relative; }
.cs-b-tx { flex: 1; -webkit-mask-image: linear-gradient(transparent, black 18px); mask-image: linear-gradient(transparent, black 18px); min-height: 0; overflow-anchor: none; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.cs-b-chat { --cs-b-width: 46rem; }
.cs-b-col { box-sizing: border-box; display: flex; flex-direction: column; margin: 0 auto; max-width: calc(var(--cs-b-width) + 2 * clamp(14px, 3cqi, 28px)); padding: 22px clamp(14px, 3cqi, 28px) 18px; width: 100%; }
.cs-b-earlier { display: flex; justify-content: center; }
.cs-b-turn, .cs-b-turn-body { display: flex; flex-direction: column; min-width: 0; }
.cs-b-turn-body { gap: 14px; }
.cs-b-turn + .cs-b-turn, .cs-b-turn + .cs-b-user, .cs-b-earlier { margin-block-start: 18px; }
.cs-b-turn[data-history] + .cs-b-turn[data-history] { margin-block-start: 0; }
.cs-b-history { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 8px; }
.cs-b-history-row { align-items: center; appearance: none; background: transparent; border: 0; color: var(--ui-text-tertiary); cursor: pointer; display: flex; flex: 1; font: inherit; font-size: 12px; gap: 10px; min-height: 30px; min-width: 0; padding: 3px 2px; text-align: start; }
.cs-b-history-row:hover, .cs-b-history-row:focus-visible { color: var(--ui-text-primary); }
.cs-b-history-number { color: var(--ui-accent); font-variant-numeric: tabular-nums; }
.cs-b-history-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-history-failed { color: var(--ui-red); }
.cs-b-history + .cs-b-turn-body { margin-block: 12px 18px; }
.cs-b-turn:not([data-live]) { contain: layout style; }
.cs-b-user { align-self: flex-end; animation: cs-b-in .18s ease-out; background: var(--ui-bg-quaternary); border-radius: 16px 16px 4px 16px; display: flex; flex-direction: column; gap: 6px; line-height: 1.55; max-width: min(78%, 640px); overflow-wrap: anywhere; padding: 9px 14px; white-space: pre-wrap; }
.cs-b-user.queued { background: transparent; border: 1px dashed var(--ui-stroke-secondary); color: var(--ui-text-secondary); }
.cs-b-qlabel { color: var(--ui-text-quaternary); font-size: 11px; }
.cs-b-her { animation: cs-b-in .2s ease-out; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.cs-b-who { color: var(--ui-text-quaternary); font-size: 11.5px; }
.cs-b-agent { color: var(--ui-text-primary); line-height: 1.65; min-width: 0; overflow-wrap: anywhere; }
/* The app un-does Typography's margins only inside its own chat ([data-slot='aui_assistant-message-content']).
   Here its \`.prose :where(img) { margin: 2em 0 }\` would slide a MEDIA: image down out of its reserved frame,
   over the next paragraph, and \`.prose :where(p)\` would space paragraphs looser than the chat. */
.cs-b-agent .aui-md :where(p, [data-tool-media-paragraph]) { margin-block: var(--paragraph-gap, 0.7rem) 0; }
.cs-b-agent .aui-md > :first-child { margin-top: 0; }
.cs-b-agent .aui-md [data-slot='aui_markdown-image'] img { margin: 0; }
.cs-b-note { border-left: 2px solid var(--ui-stroke-secondary); color: var(--ui-text-secondary); font-size: 12.5px; line-height: 1.5; margin: 2px 0; padding: 1px 0 1px 10px; white-space: pre-wrap; }
@keyframes cs-b-in { from { opacity: 0; transform: translateY(4px); } }
`
