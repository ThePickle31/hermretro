// Narrow panes and reduced motion for Build. Kept last.
export const BUILD_RESPONSIVE_CSS = `
@container (max-width: 640px) {
  .cs-b-sw-pop.cs-b-builds { width: min(420px, calc(100cqi - 24px)); }
  .cs-b-ba-pair { gap: 8px; }
}
@media (prefers-reduced-motion: reduce) {
  .cs-b-spin, .cs-b-shimmer, .cs-b-pulse, .cs-b-live.on, .cs-b-game .dot.wait, .cs-b-th.loading, .cs-b-skel i { animation: none; }
  .cs-b-shimmer { color: var(--ui-text-primary); }
  .cs-b-user, .cs-b-her, .cs-b-tool, .cs-b-card, .cs-b-pc, .cs-b-latest, .cs-b-lb, .cs-b-dim, .cs-b-status, .cs-b-th.fresh { animation: none; }
  .cs-b-wk-body { transition: none; }
  .cs-b-mp-pop, .cs-b-sw-pop, .cs-b-ctx { animation: none; }
}
`
