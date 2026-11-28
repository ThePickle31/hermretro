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
 * How exceptions and the report work, and where ESLint comes from: tools/bundle/eslint-run.mjs (shared with the
 * engine's lint). ESLint, its React hooks plugin and `globals` come from tools/npm.
 */
import { eslintTools, isMain, missing, printReport, runEslint } from './eslint-run.mjs'
import { RULES } from './lint-rules.mjs'

const FIX = 'node tools/bundle/lint-page.mjs --fix'
// These files are generated through tools/bundle/page_declarations.py.
const GENERATED = ['page/app/rpc-names.js', 'page/pages/build/workflow.js']

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

function pageConfig({ hooks, globals }) {
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

export const PACKAGES = ['eslint-plugin-react-hooks', 'globals'] // besides eslint (lint_tools.py's preflight reads it)

export async function lintPage({ fix = false, files = [] } = {}) {
  const found = eslintTools(PACKAGES)

  if (!found) {
    return { missing: missing(PACKAGES) }
  }

  const config = pageConfig({ hooks: found['eslint-plugin-react-hooks'], globals: found.globals })

  return runEslint({ eslint: found.eslint, config, patterns: ['page/**/*.js'], help: HELP, fix, files })
}

if (isMain(import.meta.url)) {
  const argv = process.argv.slice(2)
  const report = await lintPage({ fix: argv.includes('--fix'), files: argv.filter(arg => !arg.startsWith('--')) })

  process.exit(printReport(report, ` (automatic ones: ${FIX})`))
}
