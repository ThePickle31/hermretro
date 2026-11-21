// A provider's mark in the model picker: its official logo (page/shared/art/providers), in the version the brand
// publishes for the theme on screen, or its letters when it has none (custom endpoints, Mixture of Agents).
import { jsx, useTheme } from '#sdk'
import { providerLogo } from '#shared/art/providers/index.js'

export function ProviderMark({ slug, letters, className }) {
  const logo = providerLogo(slug)
  const dark = useTheme().renderedMode === 'dark'

  if (!logo) {
    return jsx('span', { 'aria-hidden': true, className, children: letters })
  }

  return jsx('span', {
    'aria-hidden': true,
    className: `${className} cs-b-logo${logo.plate === 'dark' && dark ? ' plate' : ''}`,
    'data-brand': logo.name,
    children: jsx('img', { alt: '', draggable: false, src: dark ? logo.dark : logo.light })
  })
}
