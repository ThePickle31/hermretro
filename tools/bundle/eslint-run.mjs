/**
 * What hermretro's two ESLint runs share (tools/bundle/lint-page.mjs over page/, tools/engine/lint.mjs over the
 * engine): ESLint and `globals` from tools/npm, the `// hermretro: allow <rule> — <reason>` exceptions, and the report
 * every run prints. Each run brings its own files, rules and help.
 *
 * A deliberate exception is written on the line it excuses (or alone on the line above it), with its reason.
 * `eslint-disable` comments are ignored (each config sets noInlineConfig). An allow without a reason, or one that
 * excuses nothing, is an error; every allow in use is listed at the end of the report, so exceptions stay visible.
 */
import { readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { findModules, MISSING_HINT, PINNED_MODULES } from './node-modules.mjs'

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
// A run's exit code when ESLint or a package it needs is not installed (an error is 1), so a caller never has to read
// the report to tell the two apart.
export const MISSING_TOOLS = 3
const ALLOW = /\/\/\s*hermretro:\s*allow\s+(\S+)(?:\s+(?:—|--|-)\s*(.*))?$/

/** ESLint and the named packages by name, or null when they are not installed: from the first folder that holds
 * them all (node-modules.mjs), or with `pinned`, from tools/npm only, the versions this repository pins. */
export function eslintTools(names, { pinned = false } = {}) {
  const wanted = ['eslint', ...names]
  const modules = pinned ? (findModules(wanted, [PINNED_MODULES]) ?? null) : findModules(wanted)

  if (!modules) {
    return null
  }

  const require = createRequire(path.join(modules, 'package.json'))

  return Object.fromEntries(wanted.map(name => [name, require(name)]))
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
      kept.push({ line, column: 1, severity: 2, ruleId: 'hermretro/allow', message: `the exception for ${allow.rule} has no reason. Fix: write "// hermretro: allow ${allow.rule} — <why this one is fine>"` })
    } else if (!allow.hit) {
      kept.push({ line, column: 1, severity: 2, ruleId: 'hermretro/allow', message: `this allows ${allow.rule}, but nothing it covers breaks that rule. Fix: remove the comment` })
    }
  }

  return { kept, used }
}

/** One ESLint run: { errors, warnings, allowed, files }, each message with what its rule protects (`help`). */
export async function runEslint({ eslint, config, patterns, help, fix = false, files = [] }) {
  const run = new eslint.ESLint({ cwd: ROOT, overrideConfigFile: true, overrideConfig: config, fix, errorOnUnmatchedPattern: false })
  const results = await run.lintFiles(files.length ? files : patterns)

  if (fix) {
    await eslint.ESLint.outputFixes(results)
  }

  // paths: each file ESLint read, from the root; unparsed: those it could not parse (their syntax error is an error).
  const report = { errors: [], warnings: [], allowed: [], files: results.length, paths: [], unparsed: [] }

  for (const result of results) {
    const file = path.relative(ROOT, result.filePath).split(path.sep).join('/')
    report.paths.push(file)
    if (result.messages.some(message => message.fatal)) report.unparsed.push(file)
    const { kept, used } = applyAllows(file, result.messages)

    report.allowed.push(...used)

    for (const message of kept) {
      const [purpose, howTo] = help[message.ruleId] ?? ['', '']
      const why = purpose ? `\n    why: ${purpose}. Fix: ${howTo}.` : ''
      const line = `${file}:${message.line}:${message.column}  ${message.message} [${message.ruleId ?? 'parse'}]${why}`

      ;(message.severity === 2 || message.fatal ? report.errors : report.warnings).push(line)
    }
  }

  return report
}

/** Print a run's report as check.py reads it; the exit code (1 on an error, MISSING_TOOLS without its tools). */
export function printReport(report, fixHint) {
  if (report.missing) {
    console.error(`error: ${report.missing.found}\nFIX: ${report.missing.install}`)

    return MISSING_TOOLS
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
    console.log(`FIX: fix each error above as its message says${fixHint}; a deliberate exception gets "// hermretro: allow <rule> — <reason>" on its line`)
  }

  return report.errors.length ? 1 : 0
}

/** What a run reports without its tools: what is missing, and the command that installs it. */
export function missing(names, { pinned = false } = {}) {
  const install = pinned ? 'npm ci --prefix tools/npm --ignore-scripts' : MISSING_HINT.replace(/^run: /, '')

  return { found: `${['eslint', ...names].join(', ')} were not found`, install }
}

const realPath = file => {
  try {
    return realpathSync(file)
  } catch {
    return path.resolve(file)
  }
}

/** Whether the module at `url` is the script node was started with. */
export function isMain(url) {
  return Boolean(process.argv[1]) && realPath(process.argv[1]) === realPath(fileURLToPath(url))
}
