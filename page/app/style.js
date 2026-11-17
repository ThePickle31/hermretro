// The page's one stylesheet: the shared base, the shell, then each page's own rules (`css` in its index.js).
// app/registry.js composes it at startup (pages here never import the registry, so the side emulator tab
// can render it too). Order is the cascade: pages in nav order, then the narrow-pane rules for those pages,
// then a page marked `cssLast` (Build: its inline player overrides the Emulator page's stage rules).
import { jsx } from '#sdk'
import { BASE_CSS } from '#shared/styles/base.css.js'
import { RESPONSIVE_CSS } from '#shared/styles/responsive.css.js'
import { FLYER_CSS } from '#shared/ui/flyer.css.js'
import { SHELL_CSS } from './shell.css.js'

let stylesheet = ''

/** Every stylesheet chunk of `pages` (and their tabs), in cascade order. */
export function composeStyles(pages) {
  const chunks = page => [...(page.css ?? []), ...(page.tabs ?? []).flatMap(tab => tab.css ?? [])]

  return [
    BASE_CSS,
    SHELL_CSS,
    FLYER_CSS,
    ...pages.filter(page => !page.cssLast).flatMap(chunks),
    RESPONSIVE_CSS,
    ...pages.filter(page => page.cssLast).flatMap(chunks)
  ].join('')
}

export function installPageStyles(pages) {
  stylesheet = composeStyles(pages)
}

export function PageStyle() {
  return jsx('style', { children: stylesheet })
}
