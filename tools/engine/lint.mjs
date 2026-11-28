/**
 * ESLint over the engine: its `src/` modules and its `.mjs` scripts, with rules that catch real defects (an undefined
 * name, an unused one, unreachable code, a return in a finally block…) and none about layout. Run by
 * `python tools/check.py lint`.
 *
 *   node tools/engine/lint.mjs           report; exits 1 on an error
 *   node tools/engine/lint.mjs --fix     put every file in Prettier's format first (the only automatic fix)
 *   node tools/engine/lint.mjs FILE...   only these files
 *
 * Every file is also held to Prettier's format (tools/engine/prettier.json: its defaults, 120 columns), the one layout
 * for everyone, so a diff shows only real changes.
 *
 * A deliberate exception is `// hermretro: allow <rule> — <reason>` on its line, as for the page
 * (tools/bundle/eslint-run.mjs). Fixing a report changes the engine: record it with tools/engine/bump.py.
 * ESLint, `globals` and Prettier come from tools/npm only, the versions this repository pins.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import { ROOT, eslintTools, isMain, missing, printReport, runEslint } from '../bundle/eslint-run.mjs'

const PATTERNS = ['engine/src/**/*.js', 'engine/scripts/**/*.mjs']
// The scripts the player's page and the capture page run in the browser (each says `/// <reference lib="dom" />`,
// but native-entry.js, which only starts native-client.js): browser globals only, never Node's.
export const BROWSER = [
  'engine/src/web-annotations/**/*.js',
  'engine/src/device-capture/device-picker.js',
  'engine/src/device-capture/native-client.js',
  'engine/src/device-capture/native-entry.js',
  'engine/src/device-capture/native-timing-diagnostics.js'
]
// GB Studio's web player script defines these on the player's page before the engine's scripts run: only the two
// scripts that page loads and that use them get them.
const PLAYER_PAGE = ['engine/src/web-annotations/player.js', 'engine/src/web-annotations/bridge.js']
const PLAYER_GLOBALS = { vm: 'readonly', emulator: 'readonly', Binjgb: 'readonly', Rewind: 'readonly' }

// What each rule protects and how to fix a report, printed under every message.
const HELP = {
  'no-undef': ['a name that is never declared or imported fails only when that line runs', 'import it or declare it'],
  'no-unused-vars': ['an unused name is usually a leftover or a typo', 'remove it, or use it'],
  'no-unsafe-finally': ['a return or throw in finally replaces the error or value the try block ended with', 'move it out of the finally block'],
  'no-unreachable': ['code after return/throw never runs', 'remove it or move it before the return'],
  'no-fallthrough': ['a case that runs on into the next one is usually a missing break', 'add the break, or say "falls through" in a comment'],
  'no-empty': ['an empty block hides what it ignores', 'handle it, or say in a comment why nothing is done'],
  'no-useless-catch': ['a catch that only rethrows does nothing', 'remove the try/catch'],
  'no-useless-escape': ['an escape that changes nothing misleads the reader', 'remove the backslash'],
  'no-regex-spaces': ['several spaces in a pattern are hard to count', 'write the count, as " {3}"'],
  'no-unused-private-class-members': ['an unused private member is a leftover', 'remove it, or use it']
}

// The correctness rules: ESLint's recommended set, but no-control-regex, since the engine matches control characters
// on purpose (to strip them from names and text a person sees).
const RULES = Object.fromEntries([
  'constructor-super', 'for-direction', 'getter-return', 'no-async-promise-executor', 'no-case-declarations',
  'no-class-assign', 'no-compare-neg-zero', 'no-cond-assign', 'no-const-assign', 'no-constant-binary-expression',
  'no-constant-condition', 'no-debugger', 'no-delete-var', 'no-dupe-args', 'no-dupe-class-members', 'no-dupe-else-if',
  'no-dupe-keys', 'no-duplicate-case', 'no-empty', 'no-empty-character-class', 'no-empty-pattern',
  'no-empty-static-block', 'no-ex-assign', 'no-extra-boolean-cast', 'no-fallthrough', 'no-func-assign',
  'no-global-assign', 'no-import-assign', 'no-invalid-regexp', 'no-irregular-whitespace', 'no-loss-of-precision',
  'no-misleading-character-class', 'no-new-native-nonconstructor', 'no-nonoctal-decimal-escape', 'no-obj-calls',
  'no-octal', 'no-prototype-builtins', 'no-redeclare', 'no-regex-spaces', 'no-self-assign', 'no-setter-return',
  'no-shadow-restricted-names', 'no-sparse-arrays', 'no-this-before-super', 'no-undef', 'no-unexpected-multiline',
  'no-unreachable', 'no-unsafe-finally', 'no-unsafe-negation', 'no-unsafe-optional-chaining', 'no-unused-labels',
  'no-unused-private-class-members', 'no-useless-backreference', 'no-useless-catch', 'no-useless-escape', 'no-with',
  'require-yield', 'use-isnan', 'valid-typeof'
].map(rule => [rule, 'error']))

function engineConfig({ globals }) {
  return [
    {
      files: PATTERNS,
      languageOptions: { ecmaVersion: 'latest', sourceType: 'module' },
      linterOptions: { noInlineConfig: true, reportUnusedDisableDirectives: 'off' },
      rules: { ...RULES, 'no-unused-vars': ['error', { args: 'none', caughtErrors: 'none', ignoreRestSiblings: true }] }
    },
    // Node's own globals, without CommonJS's (require, __dirname): every engine file is an ES module.
    { files: PATTERNS, ignores: BROWSER, languageOptions: { globals: globals.nodeBuiltin } },
    { files: BROWSER, languageOptions: { globals: globals.browser } },
    { files: PLAYER_PAGE, languageOptions: { globals: PLAYER_GLOBALS } }
  ]
}

export const PACKAGES = ['globals', 'prettier'] // besides eslint (lint_tools.py's preflight reads it)
const FORMAT = JSON.parse(readFileSync(new URL('./prettier.json', import.meta.url), 'utf8'))

/** Each file not in Prettier's format, as an error line; with `fix`, each is rewritten in it instead (`fixed`
 * counts those). A file that does not parse is left to ESLint's report of its syntax error. */
async function formatting(prettier, files, fix) {
  const result = { errors: [], fixed: 0 }
  for (const name of files) {
    const file = path.join(ROOT, name)
    const source = readFileSync(file, 'utf8')
    const options = { ...FORMAT, filepath: file }
    try {
      if (await prettier.check(source, options)) continue
      if (fix) {
        writeFileSync(file, await prettier.format(source, options))
        result.fixed += 1
      } else {
        result.errors.push(`${name}:1:1  not in Prettier's format [format]\n    why: one layout for everyone, so a diff shows only real changes. Fix: node tools/engine/lint.mjs --fix.`)
      }
    } catch (error) {
      result.errors.push(`${name}:1:1  Prettier could not read it: ${String(error.message).split('\n')[0]} [format]\n    why: a file Prettier cannot read is not in its format. Fix: make it parse (the error above says where), then node tools/engine/lint.mjs --fix.`)
    }
  }
  return result
}

export async function lintEngine({ fix = false, files = [] } = {}) {
  const found = eslintTools(PACKAGES, { pinned: true })

  if (!found) {
    return { missing: missing(PACKAGES, { pinned: true }) }
  }

  // ESLint picks the files (patterns, paths written any way, globs, its ignores); the format is checked on the same.
  const lint = () => runEslint({ eslint: found.eslint, config: engineConfig(found), patterns: PATTERNS, help: HELP, files })
  let report = await lint()
  const readable = report.paths.filter(name => !report.unparsed.includes(name))
  const format = await formatting(found.prettier, readable, fix)
  if (format.fixed) report = await lint()  // line numbers as the files now stand
  report.errors.push(...format.errors)
  return report
}

if (isMain(import.meta.url)) {
  const argv = process.argv.slice(2)
  const report = await lintEngine({ fix: argv.includes('--fix'), files: argv.filter(arg => !arg.startsWith('--')) })

  process.exit(printReport(report, ' (then python tools/engine/bump.py for the engine change)'))
}
