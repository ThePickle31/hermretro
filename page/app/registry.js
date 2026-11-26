// The pages as the shell sees them. page/pages/index.js lists them (one line each, in nav order); each
// page's index.js describes itself:
//   id, label           its nav segment (`id` is also what `go(id)` and the remembered page use)
//   Page({ shell })     what it shows; `shell` is the data and actions every page shares (app/studio-page.js)
//   tabs                instead of (or beside) Page: [{ id, label, Page, ...the fields below }], a tab bar
//   Badge({ nav })      a small mark on its nav segment (Setup's dot, the Emulator's live dot);
//                       nav = { page, setupPending, playing }
//   pad                 'flush' or 'build': its own padding, without the footer
//   BelowPlayer({ shell }) what follows the shell's one player on this page (needs pad)
//   css                 its stylesheet chunks (app/style.js has the cascade order)
//   events              { 'page.name': 'what happened, the payload' }: the events it emits (app/events.js)
//   listens             { 'other.event': (payload, ctx) => ... }: listeners for the plugin's whole life
//   slots               { 'page.name': 'where, the props' }: places others may fill (app/slots.js)
//   contributes         { 'other.slot': [Component] }: what it puts into other pages' slots
//   register(ctx)       work started with the plugin (gateway listeners), before any page is shown
//   flag                a feature flag (app/flags.js): hidden until it is on; a tab takes one too. A page or tab flags
//                       can hide (its own flag, its page's, or every tab of a page without a Page flagged) has no
//                       listens, contributes or register, which would run for users who cannot see it. The first
//                       page can never be hidden: hidden pages fall back to it
// This module checks every descriptor, declares the events and slots, fills the slots and composes the
// stylesheet, once, when the bundle loads; startPages(ctx) runs `register` and `listens` from index.js.
import { PAGES } from '#pages/index.js'
import { FLAGS } from './flags.js'
import { PAGE_EVENTS } from './events.js'
import { PAGE_SLOTS } from './slots.js'
import { installPageStyles } from './style.js'

const PAGE_FIELDS = new Set(['id', 'label', 'Page', 'tabs', 'Badge', 'pad', 'BelowPlayer', 'css', 'events', 'listens', 'slots', 'contributes', 'register', 'flag'])
const TAB_FIELDS = new Set(['id', 'label', 'Page', 'css', 'events', 'listens', 'slots', 'contributes', 'flag'])
const ID = /^[a-z][a-z0-9-]*$/
const NAME = /^[a-z][a-z0-9-]*\.[a-zA-Z][a-zA-Z0-9]*$/
const isFunction = value => typeof value === 'function'

/** Every problem with `pages` as sentences (empty when they are fine); `flags` are the feature flags they may name. */
export function pageProblems(pages, flags = FLAGS) {
  const problems = []
  const seen = new Set()
  const declared = { events: new Set(), slots: new Set() }
  const parts = []

  pages.forEach((page, index) => {
    const where = `page/pages/${page?.id ?? `<#${index}>`}/index.js`

    if (!page || typeof page !== 'object') {
      problems.push(`page/pages/index.js lists something that is not a page descriptor at position ${index + 1}`)

      return
    }

    if (!ID.test(page.id ?? '') || seen.has(page.id)) {
      problems.push(`${where}: id must be a unique lowercase name, got ${JSON.stringify(page.id)}`)
    }

    const tabs = Array.isArray(page.tabs) ? page.tabs : []
    // Hidden by its own flag, or with nothing left to show once flags hide every tab (visiblePages).
    const hideable = page.flag != null || (!isFunction(page.Page) && tabs.length > 0 && tabs.every(tab => tab?.flag != null))

    // A hidden page falls back to the first, so it is always shown.
    if (index === 0 && hideable) {
      problems.push(`${where}: the first page cannot be hidden (no flag, and its own Page or a tab without a flag): a hidden page falls back to it`)
    }

    seen.add(page.id)
    parts.push(...describe(page, where, PAGE_FIELDS, problems, flags, hideable).map(part => ({ ...part, owner: page.id })))

    if (!isFunction(page.Page) && !tabs.length) {
      problems.push(`${where}: give the page a Page component, or tabs`)
    }

    const tabIds = new Set()

    for (const tab of tabs) {
      const at = `${where} (tab ${tab?.id})`

      if (!ID.test(tab?.id ?? '') || tabIds.has(tab.id)) {
        problems.push(`${at}: tab id must be a unique lowercase name within the page`)
      }

      if (!isFunction(tab?.Page)) {
        problems.push(`${at}: a tab needs a Page component`)
      }

      tabIds.add(tab?.id)
      parts.push(...describe(tab ?? {}, at, TAB_FIELDS, problems, flags, hideable || tab?.flag != null).map(part => ({ ...part, owner: page.id })))
    }
  })

  // Names first (events and slots of every page), then what refers to them.
  for (const { kind, name, where, owner } of parts.filter(part => part.kind === 'events' || part.kind === 'slots')) {
    if (!NAME.test(name) || !name.startsWith(`${owner}.`)) {
      problems.push(`${where}: ${kind} "${name}" must be named "${owner}.<name>" (the owning page's id, a dot, a camelCase name)`)
    } else if (declared[kind].has(name)) {
      problems.push(`${where}: ${kind} "${name}" is declared twice; one page owns each name`)
    }

    declared[kind].add(name)
  }

  for (const { kind, name, where, value } of parts) {
    if (kind === 'listens' && !declared.events.has(name)) {
      problems.push(`${where}: listens to "${name}", which no page declares in events`)
    } else if (kind === 'listens' && !isFunction(value)) {
      problems.push(`${where}: listens["${name}"] must be a function (payload, ctx) => ...`)
    } else if (kind === 'contributes' && !declared.slots.has(name)) {
      problems.push(`${where}: contributes to "${name}", which no page declares in slots`)
    } else if (kind === 'contributes' && !(Array.isArray(value) && value.length && value.every(isFunction))) {
      problems.push(`${where}: contributes["${name}"] must be a list of components`)
    }
  }

  return problems
}

/** The named parts of one page or tab, after checking its plain fields. `hideable`: flags can hide it (its own, or
 *  its page's), so it may not run anything for users who cannot see it. */
function describe(item, where, fields, problems, flags, hideable) {
  for (const key of Object.keys(item)) {
    if (!fields.has(key)) {
      problems.push(`${where}: unknown field "${key}" (known: ${[...fields].join(', ')})`)
    }
  }

  if (typeof item.label !== 'string' || !item.label) {
    problems.push(`${where}: label must be the text its nav segment or tab shows`)
  }

  for (const key of ['Badge', 'BelowPlayer', 'register']) {
    if (item[key] != null && !isFunction(item[key])) {
      problems.push(`${where}: ${key} must be a function`)
    }
  }

  if (item.flag != null && (typeof item.flag !== 'string' || !Object.hasOwn(flags, item.flag))) {
    problems.push(`${where}: flag ${JSON.stringify(item.flag)} is not in app/flags.js (known: ${Object.keys(flags).join(', ') || 'none'})`)
  }

  if (hideable) {
    for (const key of ['listens', 'contributes', 'register'].filter(name => item[name] != null)) {
      problems.push(`${where}: a page or tab flags can hide cannot have ${key}: it would run for users who cannot see it. FIX: add it when the flag ships`)
    }
  }

  if (item.css != null && !(Array.isArray(item.css) && item.css.every(chunk => typeof chunk === 'string'))) {
    problems.push(`${where}: css must be a list of stylesheet strings`)
  }

  const parts = []

  for (const kind of ['events', 'slots', 'listens', 'contributes']) {
    for (const [name, value] of Object.entries(item[kind] ?? {})) {
      if ((kind === 'events' || kind === 'slots') && (typeof value !== 'string' || !value)) {
        problems.push(`${where}: ${kind}["${name}"] needs a one-line description (what it is, the payload or props)`)
      }

      parts.push({ kind, name, value, where })
    }
  }

  return parts
}

/** Check `pages`, declare their events and slots in `events` and `slots`, and fill the slots. Throws on a
 *  problem, listing every one: a page that does not fit fails the build's tests, not a user's page. */
export function wirePages(pages, { events, slots }) {
  const problems = pageProblems(pages)

  if (problems.length) {
    throw new Error(`the page registry has problems:\n  ${problems.join('\n  ')}\nFIX: see .agents/skills/hermretro-dev-page/references/adding.md, "Adding to the page"`)
  }

  const items = pages.flatMap(page => [{ owner: page.id, item: page }, ...(page.tabs ?? []).map(tab => ({ owner: page.id, item: tab }))])

  for (const { owner, item } of items) {
    Object.entries(item.events ?? {}).forEach(([name, doc]) => events.declare(name, owner, doc))
    Object.entries(item.slots ?? {}).forEach(([name, doc]) => slots.declare(name, owner, doc))
  }

  for (const { owner, item } of items) {
    Object.entries(item.contributes ?? {}).forEach(([name, list]) => list.forEach(Component => slots.fill(name, Component, owner)))
  }

  return {
    pages,
    listeners: items.flatMap(({ owner, item }) => Object.entries(item.listens ?? {}).map(([name, fn]) => ({ name, fn, owner }))),
    registers: pages.filter(page => page.register).map(page => page.register)
  }
}

const REGISTRY = wirePages(PAGES, { events: PAGE_EVENTS, slots: PAGE_SLOTS })

installPageStyles(PAGES)

/** The pages in nav order, checked. */
export const NAV_PAGES = REGISTRY.pages

export const pageById = id => NAV_PAGES.find(page => page.id === id) ?? null

/** The pages the feature flags that are on (`on`, a Set) show, in nav order, each with only the tabs they show. A page
 *  keeps its descriptor unless a tab of it is hidden; a page left with neither tabs nor a Page is hidden too. */
export function visiblePages(on, pages = NAV_PAGES) {
  const shown = item => item.flag == null || on.has(item.flag)

  return pages.filter(shown).flatMap(page => {
    const tabs = page.tabs?.filter(shown)

    if (!tabs || tabs.length === page.tabs.length) {
      return [page]
    }

    return tabs.length || page.Page ? [{ ...page, tabs }] : []
  })
}

// The listeners of the last `register`: registering again replaces them, so no event is handled twice.
let started = []

/** Start every page's own work with the plugin (page/index.js `register`): `register(ctx)`, then `listens`. */
export function startPages(ctx) {
  started.forEach(stop => stop())
  started = []

  for (const register of REGISTRY.registers) {
    register(ctx)
  }

  for (const { name, fn } of REGISTRY.listeners) {
    started.push(PAGE_EVENTS.on(name, payload => fn(payload, ctx)))
  }
}
