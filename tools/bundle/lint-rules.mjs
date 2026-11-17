/**
 * hermretro's own ESLint rules for page/ (run by tools/bundle/lint-page.mjs). One rule, `boundaries`: how the
 * four layers of the page may import each other, so a feature stays in its folder and connects to others only
 * through what they expose.
 *
 *   shared/   the bottom layer (ui parts, styles, art, player helpers): imports only #sdk and #shared/
 *   app/      the shell and page-wide plumbing: #sdk, #shared/, app/ and, of the pages, only the registry
 *             #pages/index.js
 *   pages/<a> a page: anything in its own folder, #sdk, #shared/, app/ plumbing (not the shell modules), and
 *             another page only through its front door '#pages/<b>/index.js'
 *   pages/index.js  the registry: only './<page>/index.js'
 *   frame/    the player frame script: only frame/ and #shared/ (no React, SDK, shell or pages)
 *   index.js  the entry: sdk.js and app/ (pages start through their descriptors, never directly)
 */
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'

// app/ modules that are the shell itself: pages never import them (they would import every page back).
const SHELL = new Set(['studio-page.js', 'nav.js', 'not-running.js', 'registry.js', 'page-view.js', 'shell.css.js'])
const ALIAS = { '#sdk': 'page/sdk.js', '#app/': 'page/app/', '#pages/': 'page/pages/', '#shared/': 'page/shared/', '#frame/': 'page/frame/' }

/** The repository path an import of `spec` from `file` (both repository-relative) points at, or null. */
function target(file, spec) {
  for (const [alias, to] of Object.entries(ALIAS)) {
    if (spec === alias || (alias.endsWith('/') && spec.startsWith(alias))) {
      return to + spec.slice(alias.length)
    }
  }

  return spec.startsWith('./') ? path.posix.join(path.posix.dirname(file), spec) : null
}

/** Where a page/ file sits: { layer, page? }. */
function zone(file) {
  const parts = file.split('/')

  if (file === 'page/index.js' || file === 'page/sdk.js') {
    return { layer: file === 'page/index.js' ? 'entry' : 'sdk' }
  }

  if (file === 'page/pages/index.js') {
    return { layer: 'registry' }
  }

  return parts[1] === 'pages' ? { layer: 'page', page: parts[2] } : { layer: parts[1] }
}

/** The names `page/pages/<name>/index.js` exports (for the automatic fix). */
function frontDoorNames(root, name) {
  const file = path.join(root, 'page', 'pages', name, 'index.js')

  if (!existsSync(file)) {
    return new Set()
  }

  const text = readFileSync(file, 'utf8')
  const names = new Set([...text.matchAll(/^export\s+(?:const|function|class|let)\s+([A-Za-z_$][\w$]*)/gm)].map(match => match[1]))

  for (const match of text.matchAll(/^export\s*\{([^}]*)\}/gm)) {
    match[1].split(',').map(part => part.trim().split(/\s+as\s+/).pop()).filter(Boolean).forEach(item => names.add(item))
  }

  return names
}

const why = {
  crossPage: "pages connect only through each other's front door (index.js), so a page can change its insides without breaking another",
  registry: 'page/pages/index.js lists every page; only the shell reads it (a page importing it would import every other page)',
  shell: 'the shell (app/studio-page.js, nav, registry, page-view) imports every page; a page importing it makes a cycle',
  shared: 'shared/ is the bottom layer every page and the shell use; it must not depend on either',
  app: 'the shell reaches pages only through the registry, so adding a page never touches app/',
  frame: 'frame/ runs inside the player frame as a classic script, without React, the SDK, the shell or the pages',
  entry: 'the entry starts pages through their descriptors (register, listens), run by startPages in app/registry.js',
  registryOnly: 'the registry is one line per page and nothing else'
}

/** The problem with importing `spec` from `file`, or null: { message, fix? } */
function problem(file, spec, root, node) {
  const to = target(file, spec)

  if (!to || !to.startsWith('page/')) {
    return null
  }

  const from = zone(file)
  const dest = zone(to)

  if (from.layer === 'page') {
    if (dest.layer === 'registry') {
      return { message: `imports '${spec}': ${why.registry}. Fix: import the page you need as '#pages/<page>/index.js'.` }
    }

    if (dest.layer === 'app' && SHELL.has(to.slice('page/app/'.length))) {
      return { message: `imports '${spec}': ${why.shell}. Fix: use what app/ plumbing exposes (events.js, slots.js, backend.js…) or put it in your descriptor.` }
    }

    if (dest.layer === 'page' && dest.page !== from.page && spec !== `#pages/${dest.page}/index.js`) {
      const door = `#pages/${dest.page}/index.js`
      const names = node.specifiers?.filter(item => item.type === 'ImportSpecifier' || item.type === 'ExportSpecifier').map(item => (item.imported ?? item.local).name) ?? []
      const exported = frontDoorNames(root, dest.page)
      const fixable = names.length && names.length === (node.specifiers?.length ?? 0) && names.every(name => exported.has(name))

      return {
        message: `imports '${spec}': ${why.crossPage}. Fix: ${fixable ? `import '${door}' (it exports ${names.join(', ')}; --fix does it)` : `export what you need from page/pages/${dest.page}/index.js (export { name } from './${to.slice(`page/pages/${dest.page}/`.length)}') and import '${door}'`}.`,
        fix: fixable ? door : null
      }
    }

    return null
  }

  if (from.layer === 'shared' && (dest.layer === 'app' || dest.layer === 'page' || dest.layer === 'registry')) {
    return { message: `imports '${spec}': ${why.shared}. Fix: move this module up into app/ (page-wide plumbing) or into the page that uses it, or take what it needs as a prop.` }
  }

  if (from.layer === 'app' && dest.layer === 'page') {
    return { message: `imports '${spec}': ${why.app}. Fix: re-export it from page/pages/index.js (from page/pages/${dest.page}/index.js), or make it part of the page's descriptor.` }
  }

  if (from.layer === 'frame' && !(dest.layer === 'frame' || dest.layer === 'shared')) {
    return { message: `imports '${spec}': ${why.frame}. Fix: import only from frame/ and #shared/player/.` }
  }

  if (from.layer === 'entry' && (dest.layer === 'page' || dest.layer === 'registry')) {
    return { message: `imports '${spec}': ${why.entry}. Fix: give the page a register(ctx) (or listens) in its index.js instead.` }
  }

  if (from.layer === 'registry' && !(dest.layer === 'page' && to === `page/pages/${dest.page}/index.js` && spec === `./${dest.page}/index.js`)) {
    return { message: `imports '${spec}': ${why.registryOnly}. Fix: import only './<page>/index.js' here.` }
  }

  return null
}

const boundaries = {
  meta: {
    type: 'problem',
    fixable: 'code',
    docs: { description: 'How page/ folders may import each other (tools/bundle/lint-rules.mjs)' },
    schema: []
  },
  create(context) {
    const root = context.cwd
    const file = path.relative(root, context.filename).split(path.sep).join('/')

    if (!file.startsWith('page/')) {
      return {}
    }

    const check = node => {
      if (!node.source || typeof node.source.value !== 'string') {
        return
      }

      const found = problem(file, node.source.value, root, node)

      if (found) {
        context.report({
          node: node.source,
          message: found.message,
          fix: found.fix ? fixer => fixer.replaceText(node.source, `'${found.fix}'`) : null
        })
      }
    }

    return { ImportDeclaration: check, ExportNamedDeclaration: check, ExportAllDeclaration: check }
  }
}

export const RULES = { boundaries }
