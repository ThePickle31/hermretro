/**
 * ESLint over page/: the boundaries between pages, shell, shared code and the frame script
 * (tools/bundle/lint-rules.mjs), and a small set of correctness rules. Run by `python tools/check.py lint`.
 *
 *   node tools/bundle/lint-page.mjs           report; exits 1 on an error (warnings are printed, never fail)
 *   node tools/bundle/lint-page.mjs --fix     apply the automatic fixes first (imports through a page's front
 *                                             door, const for never-reassigned names; nothing about layout)
 *   node tools/bundle/lint-page.mjs FILE...   only these files
 *
 * A deliberate exception is written on the line it excuses (or alone on the line above it), with its reason:
 *   import { x } from '#pages/games/model.js' // hermretro: allow hermretro/boundaries — why this one is fine
 * `eslint-disable` comments are ignored. An allow without a reason, or one that excuses nothing, is an error;
 * every allow in use is listed at the end of the report, so exceptions stay visible.
 * ESLint, its React hooks plugin and `globals` come from tools/npm (npm ci --prefix tools/npm --ignore-scripts).
 */
import { readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { RULES } from './lint-rules.mjs'
import { findModules, MISSING_HINT } from './node-modules.mjs'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const ALLOW = /\/\/\s*hermretro:\s*allow\s+(\S+)(?:\s+(?:\u2014|--|-)\s*(.*))?$/
const FIX = 'node tools/bundle/lint-page.mjs --fix'
// Generated files: their generator decides their shape (page/app/rpc-names.js: tools/bundle/rpc_names.py).
const GENERATED = ['page/app/rpc-names.js']

// What each rule protects and how to fix a report, printed under every message.
const HELP = {
  'hermretro/boundaries': ['', ''],
  'no-undef': ['a name that is never declared or imported fails only when that line runs', 'import it (React and SDK names come from #sdk) or declare it'],
  'no-unused-vars': ['an unused name is usually a leftover or a typo', 'remove it, or use it'],
  'no-dupe-keys': ['the second key silently replaces the first', 'remove or rename one of them'],
  'no-unreachable': ['code after return/throw never runs', 'remove it or move it before the return'],
  'no-self-assign': ['assigning a value to itself does nothing and hides a typo', 'assign what was meant'],
  'no-dupe-else-if': ['the second branch can never run', 'fix the condition'],
  'no-duplicate-case': ['the second case can never run', 'remove or fix it'],
  'no-const-assign': ['assigning to a const throws when that line runs', 'use let, or a new name'],
  'no-import-assign': ['an imported binding is read-only; assigning throws', "change it through the owning module's functions"],
  'use-isnan': ['nothing equals NaN', 'use Number.isNaN(value)'],
  'valid-typeof': ['typeof never returns that string', 'compare with a real typeof result'],
  'no-var': ['var leaks out of blocks', `use let or const (${FIX})`],
  'prefer-const': ['const tells the reader the name never changes', `use const (${FIX})`],
  'react-hooks/rules-of-hooks': ['React matches hooks by call order; a hook in a condition or loop breaks state', 'call hooks unconditionally at the top of the component or hook']
}

function tools() {
  const modules = findModules(['eslint', 'eslint-plugin-react-hooks', 'globals'])

  if (!modules) {
    return null
  }

  const require = createRequire(path.join(modules, 'package.json'))

  return { eslint: require('eslint'), hooks: require('eslint-plugin-react-hooks'), globals: require('globals') }
}

function config({ hooks, globals }) {
  return [
    { ignores: GENERATED },
    {
      files: ['page/**/*.js'],
      languageOptions: { ecmaVersion: 'latest', sourceType: 'module', globals: { ...globals.browser, ...globals.es2021 } },
      linterOptions: { noInlineConfig: true, reportUnusedDisableDirectives: 'off' },
      plugins: { hermretro: { rules: RULES }, 'react-hooks': hooks },
      rules: {
        'hermretro/boundaries': 'error',
        'no-undef': 'error',
        'no-unused-vars': ['warn', { args: 'none', caughtErrors: 'none', ignoreRestSiblings: true }],
        'no-dupe-keys': 'error',
        'no-unreachable': 'error',
        'no-self-assign': 'error',
        'no-dupe-else-if': 'error',
        'no-duplicate-case': 'error',
        'no-const-assign': 'error',
        'no-import-assign': 'error',
        'use-isnan': 'error',
        'valid-typeof': 'error',
        'no-var': 'error',
        'prefer-const': ['warn', { destructuring: 'all' }],
        'react-hooks/rules-of-hooks': 'error'
      }
    }
  ]
}

/** Apply `// hermretro: allow <rule> — <reason>` lines to one file's messages. */
function applyAllows(file, messages) {
  const lines = readFileSync(path.join(ROOT, file), 'utf8').split('\n')
  const allows = new Map()
  const kept = []
  const used = []

  lines.forEach((text, index) => {
    const match = ALLOW.exec(text)

    if (!match) {
      return
    }

    const commentOnly = text.trim().startsWith('//')
    const covers = commentOnly ? index + 2 : index + 1

    allows.set(index + 1, { rule: match[1], reason: (match[2] ?? '').trim(), covers, hit: false })
  })

  for (const message of messages) {
    const allow = [...allows.values()].find(item => item.covers === message.line && item.rule === message.ruleId && item.reason)

    if (allow) {
      allow.hit = true
      used.push(`${file}:${message.line}  ${message.ruleId}: ${allow.reason}`)
    } else {
      kept.push(message)
    }
  }

  for (const [line, allow] of allows) {
    if (!allow.reason) {
      kept.push({ line, column: 1, severity: 2, ruleId: 'hermretro/allow', message: `the exception for ${allow.rule} has no reason. Fix: write "// hermretro: allow ${allow.rule} \u2014 <why this one is fine>"` })
    } else if (!allow.hit) {
      kept.push({ line, column: 1, severity: 2, ruleId: 'hermretro/allow', message: `this allows ${allow.rule}, but nothing it covers breaks that rule. Fix: remove the comment` })
    }
  }

  return { kept, used }
}

export async function lintPage({ fix = false, files = [] } = {}) {
  const found = tools()

  if (!found) {
    return { missing: `eslint, eslint-plugin-react-hooks and globals were not found; ${MISSING_HINT}` }
  }

  const eslint = new found.eslint.ESLint({ cwd: ROOT, overrideConfigFile: true, overrideConfig: config(found), fix, errorOnUnmatchedPattern: false })
  const results = await eslint.lintFiles(files.length ? files : ['page/**/*.js'])

  if (fix) {
    await found.eslint.ESLint.outputFixes(results)
  }

  const report = { errors: [], warnings: [], allowed: [], files: results.length }

  for (const result of results) {
    const file = path.relative(ROOT, result.filePath).split(path.sep).join('/')
    const { kept, used } = applyAllows(file, result.messages)

    report.allowed.push(...used)

    for (const message of kept) {
      const [purpose, howTo] = HELP[message.ruleId] ?? ['', '']
      const help = purpose ? `\n    why: ${purpose}. Fix: ${howTo}.` : ''
      const line = `${file}:${message.line}:${message.column}  ${message.message} [${message.ruleId ?? 'parse'}]${help}`

      ;(message.severity === 2 || message.fatal ? report.errors : report.warnings).push(line)
    }
  }

  return report
}

async function main(argv) {
  const fix = argv.includes('--fix')
  const report = await lintPage({ fix, files: argv.filter(arg => !arg.startsWith('--')) })

  if (report.missing) {
    console.error(`error: ${report.missing}`)

    return 1
  }

  for (const line of report.warnings) {
    console.log(`warning: ${line}`)
  }

  for (const line of report.errors) {
    console.log(`error: ${line}`)
  }

  if (report.allowed.length) {
    console.log(`allowed exceptions (${report.allowed.length}):\n  ${report.allowed.join('\n  ')}`)
  }

  console.log(`${report.files} files: ${report.errors.length} errors, ${report.warnings.length} warnings, ${report.allowed.length} allowed exceptions`)

  if (report.errors.length) {
    console.log(`FIX: fix each error above as its message says (automatic ones: ${FIX}); a deliberate exception gets "// hermretro: allow <rule> \u2014 <reason>" on its line`)
  }

  return report.errors.length ? 1 : 0
}

const realPath = file => {
  try {
    return realpathSync(file)
  } catch {
    return path.resolve(file)
  }
}

if (process.argv[1] && realPath(process.argv[1]) === realPath(fileURLToPath(import.meta.url))) {
  process.exit(await main(process.argv.slice(2)))
}
