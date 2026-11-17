export const MENTIONS_CSS = `
/* @ assets */
.cs-b-comp { position: relative; }
.cs-b-chip.mention { background: color-mix(in srgb, var(--ui-accent) 15%, transparent); box-shadow: none; color: var(--ui-accent); }
.cs-b-mention { animation: cs-b-in .12s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 12px; bottom: calc(100% + 6px); box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 18px 48px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; gap: 1px; left: 0; max-height: min(50svh, 380px); overflow-y: auto; padding: 6px; position: absolute; width: min(340px, 100%); z-index: 30; }
.cs-b-mention-head { align-items: center; display: flex; font-size: 11px; justify-content: space-between; padding: 4px 6px 6px; }
.cs-b-mention-row { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 7px; color: inherit; cursor: pointer; display: flex; font: inherit; font-size: 12.5px; gap: 9px; padding: 5px 6px; text-align: left; }
.cs-b-mention-row b { flex: 1; font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-mention-row span.cs-faint { font-size: 11px; }
.cs-b-mention-row[aria-selected='true'] { background: color-mix(in srgb, var(--ui-accent) 14%, transparent); }
.cs-b-mention-row .cs-b-th { cursor: inherit; height: 28px; width: 28px; }
.cs-b-mention p { margin: 6px; }
`
