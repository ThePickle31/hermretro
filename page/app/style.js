// The page's one stylesheet: the shared base, the shell, the backgrounds' rules, then each page's own rules (`css` in its index.js).
// app/registry.js composes it at startup (pages here never import the registry, so the side emulator tab
// can render it too). Pages contribute rules in navigation order.
import { jsx } from '#sdk'
import { BACKGROUNDS } from '#backgrounds/index.js'
import { BASE_CSS } from '#shared/styles/base.css.js'
import { RESPONSIVE_CSS } from '#shared/styles/responsive.css.js'
import { FLYER_CSS } from '#shared/ui/flyer.css.js'
import { SHELL_CSS } from './shell.css.js'
import { UPDATE_CSS } from './update/update.css.js'

let stylesheet = ''

/** Every stylesheet chunk of `pages` (and their tabs), in cascade order. */
export function composeStyles(pages) {
  const chunks = page => [...(page.css ?? []), ...(page.tabs ?? []).flatMap(tab => tab.css ?? [])]

  return [
    BASE_CSS,
    SHELL_CSS,
    UPDATE_CSS,
    FLYER_CSS,
    ...BACKGROUNDS.flatMap(background => background.css ?? []),
    ...pages.flatMap(chunks),
    RESPONSIVE_CSS
  ].join('')
}

export function installPageStyles(pages) {
  stylesheet = composeStyles(pages)
}

export function PageStyle() {
  return jsx('style', { children: stylesheet })
}
