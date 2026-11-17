// Narrow panes and reduced motion, for every page but Build. Kept after the pages' own rules.
export const RESPONSIVE_CSS = `
@container (max-width: 1100px) {
  .cs-band { grid-template-columns: 1fr 1fr; }
  .cs-band > section:nth-child(3) { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); grid-column: 1 / -1; padding-left: 0; }
}
@container (max-width: 1000px) {
  .cs-setup { grid-template-columns: clamp(180px, 13cqi, 240px) minmax(0, 1fr); }
  .cs-setup > .cs-flyer { display: none; }
  .cs-reader { grid-template-columns: clamp(200px, 26cqi, 280px) minmax(0, 1fr); }
  .cs-reader > .cs-art { display: none; }
  .cs-empty { grid-template-columns: 1fr; }
  .cs-empty > .cs-art { display: none; }
}
/* Narrow main pane (an emulator tab docked beside it, a small window): the header stays one row.
   The segments tighten, Refresh keeps only its icon, the wordmark goes (Home does the same) and, as
   a last resort, the segments scroll sideways. The player bar stops wrapping the same way and, below
   560px, its buttons keep only their icons (each has a tooltip and an aria-label). */
@container (max-width: 900px) {
  .cs-top { gap: 16px; }
  .cs-seg { min-width: 0; overflow-x: auto; scrollbar-width: none; }
  .cs-seg button { padding: 7px 11px; }
  .cs-top-end { width: auto; }
  .cs-top-end .cs-lbl { display: none; }
}
@container (max-width: 700px) {
  .cs-rp-bar { flex-wrap: nowrap; gap: 2px; overflow-x: auto; scrollbar-width: none; }
}
@container (max-width: 600px) {
  .cs-brand { display: none; }
  .cs-top { gap: 8px; padding-left: 12px; padding-right: 8px; }
  .cs-seg { flex: 1 1 auto; margin: 0; }
  .cs-seg button { flex: 1 0 auto; gap: 5px; justify-content: center; letter-spacing: .06em; padding: 7px 8px; }
}
@container (max-width: 560px) {
  .cs-rp-bar .cs-lbl { display: none; }
  .cs-rp-focus { padding: 0 6px; }
}
@container (max-width: 760px) {
  .cs-setup, .cs-hero, .cs-band, .cs-reader, .cs-page-head { grid-template-columns: 1fr; }
  .cs-rail, .cs-rlist { position: static; }
  .cs-rail-item, .cs-rail-group { display: none; }
  .cs-meter { margin-top: 0; }
  .cs-hero > .cs-art { display: none; }
  .cs-band > section { border-left: 0 !important; border-top: 1px solid var(--ui-stroke-tertiary); padding-left: 0; }
  .cs-choice { grid-template-columns: 1fr; }
  .cs-choice > div + div { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); padding-left: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .cs-lem .run, .cs-glyph .cs-dash, .cs-reload .dot, .cs-flyer * { animation: none !important; }
  .cs-flyer .wing.r { transform: rotate(-10deg); }
  .cs-flyer .wing.l { transform: rotate(10deg); }
  .cs-cart { transition: none; }
}
`
