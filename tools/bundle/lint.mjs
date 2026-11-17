/**
 * Rules for the modules in page/, checked on every build by tools/bundle/bundle.mjs. Each one guards
 * something that used to be impossible to get wrong in a single file, or that Hermes's install
 * scanner would note:
 *   - only sdk.js imports a package; every other import is ./file.js (the same folder),
 *     ./sub/file.js (a folder inside it) or an alias from bundle.mjs (#sdk, #app/, #pages/, #shared/,
 *     #frame/); no import climbs a folder, so no relative path in the sources climbs at all; the frame
 *     shim's modules (frame/) never import sdk.js;
 *   - every source file is part of the bundle;
 *   - no import cycles (a module never reads a value before the module defining it has run);
 *   - no identifier that was never imported (it would only fail when that code runs);
 *   - exported names are unique (the bundler would rename one of them);
 *   - no file over LINE_LIMIT lines.
 */
import { readdirSync } from 'node:fs'
import path from 'node:path'

const LINE_LIMIT = 400
// Files that are one large function today. Split them and remove them here; never add to this list.
const OVER_LIMIT = new Set(['pages/build/viewer/asset-viewer.js', 'pages/build/build-page.js', 'app/studio-page.js'])
const CLIMBS = '..' + '/'

// What counts as source (and goes into the banner's hash): modules and the art they import. Dotfiles and
// editor leftovers (.orig, ~ backups) are not, so they cannot make a clean checkout look stale.
const SOURCE_FILE = /\.(js|png)$/

export const lineCount = text => text.split('\n').length - (text.endsWith('\n') ? 1 : 0)

/** Every source file under `dir`, as sorted paths relative to it. */
export function sourceFiles(dir, prefix = '') {
  return readdirSync(dir, { withFileTypes: true })
    .filter(entry => !entry.name.startsWith('.'))
    .flatMap(entry =>
      entry.isDirectory() ? sourceFiles(path.join(dir, entry.name), `${prefix}${entry.name}/`) : SOURCE_FILE.test(entry.name) ? [`${prefix}${entry.name}`] : []
    )
    .sort()
}

/** Whether `original` (as written in `file`) is an allowed specifier for `target`: ./ for the importer's own
 *  folder and below, the alias whose folder holds the target for anything else. */
function allowedImport(source, aliases, file, original, target) {
  if (original.includes(CLIMBS) || !target.startsWith(`${source}/`)) {
    return false
  }

  const inOwnFolder = target.startsWith(`${path.posix.dirname(file)}/`)

  if (original.startsWith('./') || inOwnFolder) {
    return original.startsWith('./') && inOwnFolder
  }

  return Object.entries(aliases).some(([alias, to]) => (to.endsWith('.js') ? original === alias && target === to : original.startsWith(`${alias}/`) && target.startsWith(`${to}/`)))
}

function layoutProblems(source, aliases, inputs, onDisk) {
  const problems = []

  for (const file of onDisk.filter(name => name.endsWith('.js'))) {
    if (!inputs[`${source}/${file}`]) {
      problems.push(`${file} is not imported by anything`)
    }
  }

  for (const [file, { imports }] of Object.entries(inputs)) {
    for (const { external, original, path: target } of imports) {
      if (external) {
        if (file !== `${source}/sdk.js`) {
          problems.push(`${file} imports ${original}: only sdk.js imports packages`)
        }
      } else if (!allowedImport(source, aliases, file, original, target)) {
        problems.push(`${file} imports ${original}: use ./file.js, ./folder/file.js or an alias (${Object.entries(aliases).map(([alias, to]) => (to.endsWith('.js') ? alias : `${alias}/`)).join(', ')}), never ${CLIMBS}`)
      } else if (file.startsWith(`${source}/frame/`) && target === `${source}/sdk.js`) {
        problems.push(`${file} imports ${original}: the frame shim runs without React or the SDK`)
      }
    }
  }

  return problems
}

function cycleProblems(inputs) {
  const state = new Map()
  const trail = []

  const visit = file => {
    state.set(file, 'open')
    trail.push(file)

    for (const { external, path: target } of inputs[file].imports) {
      if (external || state.get(target) === 'done') {
        continue
      }

      const found = state.get(target) === 'open' ? [...trail.slice(trail.indexOf(target)), target] : visit(target)

      if (found) {
        return found
      }
    }

    trail.pop()
    state.set(file, 'done')

    return null
  }

  for (const file of Object.keys(inputs)) {
    const cycle = state.has(file) ? null : visit(file)

    if (cycle) {
      return [`import cycle: ${cycle.join(' -> ')}`]
    }
  }

  return []
}

/** The names a declaration binds, through `{ a, b }` and `[a, b]` patterns. */
function boundNames(ts, name) {
  return ts.isIdentifier(name) ? [name.text] : name.elements.flatMap(element => (ts.isOmittedExpression(element) ? [] : boundNames(ts, element.name)))
}

function exportedNames(ts, statement) {
  if (ts.isExportDeclaration(statement)) {
    // `export { x } from './y.js'` (a page's front door) passes y's binding on; it declares nothing new.
    return statement.moduleSpecifier ? [] : (statement.exportClause?.elements ?? []).map(element => element.name.text)
  }

  if (!ts.getModifiers(statement)?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword)) {
    return []
  }

  if (ts.isVariableStatement(statement)) {
    return statement.declarationList.declarations.flatMap(declaration => boundNames(ts, declaration.name))
  }

  return statement.name ? [statement.name.text] : ['default']
}

/** The two checks that need a parser: names used but never imported, and names exported twice. */
function nameProblems(ts, root, aliases, files) {
  const problems = []
  const exportedBy = new Map()
  const program = ts.createProgram(files.map(file => path.join(root, file)), {
    allowJs: true,
    checkJs: true,
    noEmit: true,
    target: ts.ScriptTarget.ESNext,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    types: [],
    skipLibCheck: true,
    paths: Object.fromEntries(Object.entries(aliases).map(([alias, to]) => (to.endsWith('.js') ? [alias, [path.join(root, to)]] : [`${alias}/*`, [path.join(root, to, '*')]])))
  })
  const relative = file => path.relative(root, file.fileName).split(path.sep).join('/')
  // TS2304 / TS2552: "Cannot find name". Every other diagnostic is type checking we do not do.
  const unknownName = diagnostic => diagnostic.file && (diagnostic.code === 2304 || diagnostic.code === 2552)

  for (const diagnostic of ts.getPreEmitDiagnostics(program).filter(unknownName)) {
    const { line } = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start)

    problems.push(`${relative(diagnostic.file)}:${line + 1}: ${ts.flattenDiagnosticMessageText(diagnostic.messageText, ' ')}`)
  }

  for (const file of files.map(name => program.getSourceFile(path.join(root, name)))) {
    for (const statement of file.statements) {
      for (const name of exportedNames(ts, statement)) {
        if (exportedBy.has(name)) {
          problems.push(`${name} is exported by both ${exportedBy.get(name)} and ${relative(file)}`)
        }

        exportedBy.set(name, relative(file))
      }
    }
  }

  return { problems, program }
}

function sizeProblems(source, files, program, root) {
  const problems = []
  const long = new Set()

  for (const file of files) {
    const name = file.slice(source.length + 1)
    const lines = lineCount(program.getSourceFile(path.join(root, file)).text)

    if (lines > LINE_LIMIT) {
      long.add(name)

      if (!OVER_LIMIT.has(name)) {
        problems.push(`${file} has ${lines} lines; the limit is ${LINE_LIMIT}`)
      }
    }
  }

  for (const name of OVER_LIMIT) {
    if (!long.has(name)) {
      problems.push(`${name} is within ${LINE_LIMIT} lines now: remove it from OVER_LIMIT in tools/bundle/lint.mjs`)
    }
  }

  return problems
}

/** Every problem with the source tree, as sentences. `inputs` are esbuild's metafile inputs of every
 *  output built from it (the page bundle and the frame shim). */
export function lintSources({ root, source, aliases, inputs, ts }) {
  const files = Object.keys(inputs).filter(file => file.endsWith('.js'))
  const names = nameProblems(ts, root, aliases, files)

  return [
    ...layoutProblems(source, aliases, inputs, sourceFiles(path.join(root, source))),
    ...cycleProblems(inputs),
    ...names.problems,
    ...sizeProblems(source, files, names.program, root)
  ]
}
