// Theme colours, inline style snippets and the two typefaces.
export const C = {
  primary: 'var(--ui-text-primary)',
  secondary: 'var(--ui-text-secondary)',
  tertiary: 'var(--ui-text-tertiary)',
  quaternary: 'var(--ui-text-quaternary)',
  stroke: 'var(--ui-stroke-tertiary)',
  fill: 'var(--ui-bg-quaternary)',
  good: 'var(--ui-green)',
  warn: 'var(--ui-yellow)',
  bad: 'var(--ui-red)'
}

export const S = {
  row: { alignItems: 'center', display: 'flex', flexWrap: 'wrap', gap: 8 },
  col: { display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 },
  muted: { color: C.tertiary, fontSize: 12, lineHeight: 1.5 },
  faint: { color: C.quaternary, fontSize: 11, lineHeight: 1.5 },
  code: {
    background: C.fill,
    borderRadius: 4,
    color: C.primary,
    fontSize: 12,
    overflowWrap: 'anywhere',
    padding: '4px 8px',
    userSelect: 'text'
  }
}

// The page's own stylesheet. Runtime plugins are not seen by the app's Tailwind build, so the
// page carries plain CSS, scoped under `.cs-page`. Every colour is a theme variable, so light,
// dark and every skin repaint it; the two typefaces are the ones the app itself loads.
export const MONO = "var(--dt-font-mono, 'JetBrains Mono', ui-monospace, monospace)"
export const DISPLAY = "'Collapse', var(--dt-font-sans, system-ui), sans-serif"
