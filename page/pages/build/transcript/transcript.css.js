export const TRANSCRIPT_CSS = `
/* the conversation */
.cs-b-chat { display: flex; flex-direction: column; min-height: 0; min-width: 0; position: relative; }
.cs-b-head { align-items: center; align-self: center; box-sizing: border-box; display: flex; gap: 10px; max-width: var(--cs-b-width); min-height: 46px; padding: 8px clamp(14px, 3cqi, 28px) 2px; width: 100%; }
.cs-b-head .cs-word { font-size: 22px; }
.cs-top-profile { align-items: center; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-tertiary); cursor: default; display: inline-flex; font-size: 11px; gap: 5px; margin-left: 10px; padding: 1px 9px 1px 7px; white-space: nowrap; }
.cs-b-txwrap { display: flex; flex: 1; flex-direction: column; min-height: 0; position: relative; }
.cs-b-tx { flex: 1; -webkit-mask-image: linear-gradient(transparent, black 18px); mask-image: linear-gradient(transparent, black 18px); min-height: 0; overflow-anchor: none; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.cs-b-chat { --cs-b-width: clamp(720px, 62cqi, 1280px); }
.cs-b-col { box-sizing: border-box; display: flex; flex-direction: column; gap: 22px; margin: 0 auto; max-width: var(--cs-b-width); padding: 22px clamp(14px, 3cqi, 28px) 18px; width: 100%; }
.cs-b-earlier { display: flex; justify-content: center; }
.cs-b-turn { display: flex; flex-direction: column; gap: 14px; }
.cs-b-turn:not([data-live]) { contain: layout style; }
.cs-b-user { align-self: flex-end; animation: cs-b-in .18s ease-out; background: var(--ui-bg-quaternary); border-radius: 16px 16px 4px 16px; display: flex; flex-direction: column; gap: 6px; line-height: 1.55; max-width: min(78%, 640px); overflow-wrap: anywhere; padding: 9px 14px; white-space: pre-wrap; }
.cs-b-user.queued { background: transparent; border: 1px dashed var(--ui-stroke-secondary); color: var(--ui-text-secondary); }
.cs-b-qlabel { color: var(--ui-text-quaternary); font-size: 11px; }
.cs-b-her { animation: cs-b-in .2s ease-out; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.cs-b-who { color: var(--ui-text-secondary); font-size: 12px; font-weight: 600; }
.cs-b-who span { color: var(--ui-text-quaternary); font-size: 11px; font-weight: 400; margin-left: 7px; }
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
