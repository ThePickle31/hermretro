export const TRANSCRIPT_CSS = `
/* the conversation */
.cs-b-chat { display: flex; flex-direction: column; min-height: 0; min-width: 0; position: relative; }
.cs-b-head { align-items: center; align-self: center; box-sizing: border-box; display: flex; gap: 10px; max-width: var(--cs-b-width); min-height: 46px; padding: 8px clamp(14px, 3cqi, 28px) 2px; width: 100%; }
.cs-b-head .cs-word { font-size: 22px; }
.cs-top-profile { align-items: center; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-tertiary); cursor: default; display: inline-flex; font-size: 11px; gap: 5px; margin-left: 10px; padding: 1px 9px 1px 7px; white-space: nowrap; }
.cs-b-swwrap { align-items: center; display: flex; gap: 10px; min-width: 0; position: relative; }
.cs-b-sw { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 8px; color: var(--ui-text-primary); cursor: pointer; display: inline-flex; gap: 8px; margin-left: -8px; min-width: 0; padding: 3px 8px; transition: background .12s ease; }
.cs-b-sw:hover, .cs-b-sw.open { background: var(--ui-bg-quaternary); }
.cs-b-sw h2 { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-sw > i { color: var(--ui-text-tertiary); }
.cs-b-needs { appearance: none; background: var(--ui-yellow); border: 0; border-radius: 999px; color: var(--ui-bg-editor); cursor: pointer; flex: none; font: 700 11px/18px inherit; padding: 0 9px; white-space: nowrap; }
.cs-b-others { align-items: center; color: var(--ui-text-tertiary); display: inline-flex; flex: none; font-size: 11.5px; gap: 6px; white-space: nowrap; }
.cs-b-otherdot { background: var(--ui-accent); border-radius: 50%; box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-accent) 25%, transparent); flex: none; height: 7px; width: 7px; }
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
.cs-b-ctx { animation: cs-b-in .1s ease-out; background: linear-gradient(var(--ui-bg-tertiary, var(--ui-bg-secondary)), var(--ui-bg-tertiary, var(--ui-bg-secondary))), var(--ui-bg-editor); border-radius: 8px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 12px 30px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; gap: 1px; min-width: 180px; padding: 4px; position: absolute; z-index: 40; }
.cs-b-ctx button { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 5px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; font-size: 12px; gap: 8px; outline: none; padding: 6px 9px; text-align: left; }
.cs-b-ctx button:hover:not(:disabled), .cs-b-ctx button:focus-visible { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-ctx button.danger { color: var(--ui-red); }
.cs-b-ctx button:disabled { cursor: default; opacity: .45; }
.cs-b-ctx hr { border: 0; border-top: 1px solid var(--ui-stroke-tertiary); margin: 3px 2px; }
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
