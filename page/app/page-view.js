// One page's body: its Page, or, for a page with tabs, a tab bar and the chosen tab (remembered per page).
import { jsx, jsxs, useState } from '#sdk'

// The remembered tab, even one its flag hides for now: the tab shown falls back to the first until it is back.
function storedTab(ctx, page) {
  try {
    const id = ctx?.storage?.get?.(`tab:${page.id}`, null)

    return typeof id === 'string' && id ? id : (page.tabs[0]?.id ?? null)
  } catch {
    return page.tabs[0]?.id ?? null
  }
}

function TabbedPage({ page, shell }) {
  const [chosen, setChosen] = useState(() => storedTab(shell.ctx, page))
  // Undefined once flags hide every tab: the page's own Page stays mounted alone.
  const tab = page.tabs.find(item => item.id === chosen) ?? page.tabs[0]

  const pick = id => {
    setChosen(id)

    try {
      shell.ctx?.storage?.set?.(`tab:${page.id}`, id)
    } catch {
      // remembered for this visit only
    }
  }

  return [
    tab ? jsx(
      'div',
      {
        'aria-label': `${page.label} tabs`,
        className: 'cs-tabs',
        role: 'tablist',
        children: page.tabs.map(item =>
          jsx('button', { 'aria-selected': item.id === tab.id, className: item.id === tab.id ? 'on' : '', onClick: () => pick(item.id), role: 'tab', type: 'button', children: item.label }, item.id)
        )
      },
      'tabs'
    ) : null,
    page.Page ? jsx(page.Page, { shell, tab: tab?.id ?? null }, 'page') : null,
    tab ? jsxs('div', { className: 'cs-tab-body', role: 'tabpanel', children: [jsx(tab.Page, { shell }, tab.id)] }, 'tab') : null
  ]
}

/** What `page` shows, given the data every page shares. A page with tabs stays a TabbedPage while flags hide some or
 *  all of them (visiblePages keeps `tabs`), so its own Page is not remounted when a tab comes or goes. */
export function PageView({ page, shell }) {
  return Array.isArray(page.tabs) ? jsx(TabbedPage, { page, shell }) : jsx(page.Page, { shell })
}
