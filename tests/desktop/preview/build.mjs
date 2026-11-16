// Builds a browser preview of the plugin page, drawn with the installed Hermes Desktop's own
// stylesheet, fonts and icons, in light and dark mode:
//   node tests/desktop/preview/build.mjs <out dir> [apps/desktop of a Hermes checkout]
// Open <out dir>/index.html (a classic script, so it also runs from file://)?s=choice&mode=dark&p=setup
// (the bar at the top switches scenarios; p = home | setup | prompts | games | emulator).
import { copyFileSync, existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const out = path.resolve(process.argv[2] || path.join(os.tmpdir(), 'chromatic-page-preview'))
const desktop = path.resolve(process.argv[3] || path.join(os.homedir(), '.hermes', 'hermes-agent', 'apps', 'desktop'))
const require = createRequire(path.join(desktop, 'package.json'))
const esbuild = require('esbuild')

mkdirSync(out, { recursive: true })

await esbuild.build({
  entryPoints: [path.join(here, 'entry.mjs')],
  bundle: true,
  format: 'iife',
  outfile: path.join(out, 'preview.js'),
  alias: {
    '@hermes/plugin-sdk': path.join(here, 'sdk-preview.mjs'),
    'hermes-theme-presets': path.join(desktop, '..', 'shared', 'src', 'theme-presets.ts')
  },
  nodePaths: [path.join(desktop, 'node_modules')],
  jsx: 'automatic',
  define: { 'process.env.NODE_ENV': '"development"' },
  logLevel: 'warning'
})

const assets = path.join(desktop, 'dist', 'assets')
const css = readdirSync(assets).filter(name => /^main-.*\.css$/.test(name))
const codicons = path.join(desktop, 'node_modules', '@vscode', 'codicons', 'dist')

copyFileSync(path.join(codicons, 'codicon.css'), path.join(out, 'codicon.css'))

// Example title screens and a stand-in player page for the Games / Emulator scenarios (optional:
// taken from the mockups folder when it is there).
const mockups = path.join(os.homedir(), 'projects', 'chromatic-studio-mockups')
const thumbs = path.join(mockups, 'assets', 'thumbs')

mkdirSync(path.join(out, 'thumbs'), { recursive: true })
mkdirSync(path.join(out, 'player'), { recursive: true })

if (existsSync(thumbs)) {
  for (const name of readdirSync(thumbs)) copyFileSync(path.join(thumbs, name), path.join(out, 'thumbs', name))
}

const standIn = path.join(mockups, 'screens', 'player-test.html')

if (existsSync(standIn)) {
  copyFileSync(standIn, path.join(out, 'player', 'index.html'))
} else {
  writeFileSync(path.join(out, 'player', 'index.html'), '<!doctype html><body style="margin:0;display:grid;place-items:center;height:100vh;font:14px sans-serif">Player stand-in</body>')
}
copyFileSync(path.join(codicons, 'codicon.ttf'), path.join(out, 'codicon.ttf'))

writeFileSync(
  path.join(out, 'index.html'),
  `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>hermretro page preview</title>
${css.map(name => `<link rel="stylesheet" href="${path.join(assets, name)}">`).join('\n')}
<link rel="stylesheet" href="codicon.css">
<style>
  html, body { height: 100%; margin: 0; }
  body { background: var(--ui-bg-editor, var(--background)); display: flex; flex-direction: column; font-family: var(--dt-font-sans); }
  #bar { display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; border-bottom: 1px solid var(--ui-stroke-tertiary); background: var(--ui-bg-chrome); font: 12px var(--dt-font-sans); }
  #bar a { color: var(--ui-text-secondary); padding: 3px 8px; text-decoration: none; }
  #bar a[aria-current] { background: var(--ui-accent); color: var(--background); }
  #bar a.mode { margin-left: auto; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); }
  #page { flex: 1; min-height: 0; }
</style></head>
<body><nav id="bar"></nav><div id="page"></div><script src="preview.js"></script></body></html>
`
)

console.log(path.join(out, 'index.html'))
