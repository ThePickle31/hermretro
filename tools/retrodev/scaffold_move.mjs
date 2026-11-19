// `new tab --from-page`'s reading of a page's JavaScript (tools/retrodev/scaffold_move.py runs it): one module,
// parsed by acorn, as JSON on stdout. Usage: node scaffold_move.mjs <acorn's folder> [<Page name>] < source.js
// Offsets are in code points (Python's string indexes), never UTF-16 units. Nothing is written.
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const [acornDir, pageName] = process.argv.slice(2)
const { parse } = await import(pathToFileURL(path.join(acornDir, 'dist', 'acorn.mjs')).href)
const source = readFileSync(0, 'utf8')

// UTF-16 offset -> code point offset
const points = new Int32Array(source.length + 1)
for (let unit = 0, point = 0; unit <= source.length; point++) {
  points[unit] = point
  const wide = unit < source.length && source.codePointAt(unit) > 0xffff
  if (wide) points[unit + 1] = point
  unit += wide ? 2 : 1
}
const at = offset => points[offset]

const comments = []
let program
try {
  program = parse(source, {
    ecmaVersion: 'latest',
    sourceType: 'module',
    onComment: (block, text, start, end) => comments.push({ block, start, end })
  })
} catch (error) {
  process.stdout.write(JSON.stringify({ error: error.message }))
  process.exit(0)
}

/** Each identifier a node uses, never a property name (a.b, { b: 1 }, class { b() {} }) or a label. */
function references(node, found = new Set()) {
  if (!node || typeof node.type !== 'string') return found
  if (node.type === 'Identifier') found.add(node.name)
  for (const [key, value] of Object.entries(node)) {
    if (key === 'label' || key === 'exported') continue
    if (key === 'property' && node.type === 'MemberExpression' && !node.computed) continue
    if (key === 'key' && !node.computed && /Property|MethodDefinition|PropertyDefinition/.test(node.type)) continue
    if (key === 'meta' || (key === 'property' && node.type === 'MetaProperty')) continue
    for (const child of Array.isArray(value) ? value : [value]) {
      if (child && typeof child.type === 'string') references(child, found)
    }
  }
  return found
}

/** The names a top-level statement declares. */
function declared(node) {
  const decl = node.type.startsWith('Export') && node.declaration ? node.declaration : node
  if (decl.type === 'VariableDeclaration') return decl.declarations.flatMap(d => patternNames(d.id))
  return decl.id ? [decl.id.name] : []
}

function patternNames(pattern) {
  if (!pattern) return []
  if (pattern.type === 'Identifier') return [pattern.name]
  if (pattern.type === 'ObjectPattern') return pattern.properties.flatMap(p => patternNames(p.value ?? p.argument))
  if (pattern.type === 'ArrayPattern') return pattern.elements.flatMap(patternNames)
  if (pattern.type === 'RestElement') return patternNames(pattern.argument)
  if (pattern.type === 'AssignmentPattern') return patternNames(pattern.left)
  return []
}

const name = node => node.type === 'Literal' ? String(node.value) : node.name
const imports = []
const declarations = {}
const exports = {} // exported name -> its local binding here, or null (re-exported from another module)
const used = new Set() // what the code outside the import statements uses
let page = null
for (const node of program.body) {
  if (node.type === 'ImportDeclaration') {
    imports.push({
      start: at(node.start),
      end: at(node.end),
      source: node.source.value,
      raw: node.source.raw,
      semicolon: source[node.end - 1] === ';',
      specifiers: node.specifiers.map(s => ({
        kind: { ImportDefaultSpecifier: 'default', ImportNamespaceSpecifier: 'namespace' }[s.type] ?? 'named',
        imported: s.imported ? name(s.imported) : null,
        local: s.local.name
      }))
    })
    continue
  }
  for (const local of declared(node)) declarations[local] = node.type
  if (node.type === 'ExportNamedDeclaration') {
    for (const local of declared(node)) exports[local] = local
    for (const s of node.specifiers) exports[name(s.exported)] = node.source ? null : name(s.local)
    if (node.source) continue // export { X } from './x.js' uses no local binding
  } else if (node.type === 'ExportDefaultDeclaration') {
    exports.default = node.declaration.id?.name ?? null
  } else if (node.type === 'ExportAllDeclaration') {
    if (node.exported) exports[name(node.exported)] = null
    continue
  }
  references(node, used)
  if (pageName && declared(node).includes(pageName) && node.type !== 'ExportDefaultDeclaration') {
    page = pageOf(node)
  }
}

/** The Page's statement, with the comments directly above it: each a whole comment token that starts its own
 * line, with no blank line between it and what follows it. */
function pageOf(node) {
  const decl = node.declaration ?? node
  const single = decl.type === 'FunctionDeclaration' ||
    (decl.type === 'VariableDeclaration' && decl.declarations.length === 1)
  const index = program.body.indexOf(node)
  const floor = index > 0 ? program.body[index - 1].end : 0
  let start = node.start
  for (const comment of comments.filter(c => c.end <= node.start && c.start >= floor).reverse()) {
    const between = source.slice(comment.end, start)
    const before = source.slice(source.lastIndexOf('\n', comment.start - 1) + 1, comment.start)
    if (/\S/.test(between) || (between.match(/\n/g) ?? []).length > 1 || /\S/.test(before)) break
    start = comment.start
  }
  return {
    start: at(start),
    end: at(node.end),
    keyword: at(decl.start), // where `export ` goes when it is not exported yet
    exported: node.type === 'ExportNamedDeclaration',
    movable: single,
    uses: [...references(decl)].filter(n => n !== pageName).sort()
  }
}

process.stdout.write(JSON.stringify({ imports, declarations, exports, used: [...used].sort(), page }))
