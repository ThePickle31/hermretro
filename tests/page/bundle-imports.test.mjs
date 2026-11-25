// The bundler's import check (tools/bundle/bundle.mjs, importsOf and loaderImports): it reads real module
// declarations, never import-shaped text in a string or comment, and accepts exactly the forms Hermes Desktop's
// loader rewrites (apps/desktop/src/contrib/runtime-loader.ts), which the bundle then emits.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { EXTERNAL, importsOf, loaderImports } from '../../tools/bundle/bundle.mjs'
import { findModules, MISSING_HINT } from '../../tools/bundle/node-modules.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const modules = findModules(['typescript'])
if (!modules) throw new Error(`typescript is missing. FIX: ${MISSING_HINT}`)
const ts = createRequire(path.join(modules, 'package.json'))('typescript')

// The loader's own specifier pattern (importSpecifierRe), kept here to hold the check to it.
const DESKTOP = /(from\s*|import\s*\(\s*|import\s+)(['"])([^'"]+)\2/g
const desktopMaps = (text, at) => [...text.matchAll(DESKTOP)].some(match => match.index + match[1].length === at)

test('import-shaped text in a string, a template or a comment is not an import', () => {
  const text = [
    'import{jsx}from"react/jsx-runtime";',
    "var a=';import{jsx}from\"react/jsx-runtime\";';",
    "var b='import\"react\";';",
    'var c=`;import{x}from"@hermes/plugin-sdk";`;',
    '/* import"react"; */',
    'export default a+b+c;'
  ].join('')

  assert.deepEqual(
    importsOf(ts, text).map(declaration => declaration.specifier),
    ['react/jsx-runtime']
  )
})

test('every form the loader rewrites is accepted, and only those', () => {
  const forms = {
    'import{a}from"react";': true,
    'import a from"react";': true,
    'import*as a from"react";': true,
    "import{a}from 'react';": true,
    'import "react";': true,
    'export*from"react";': true,
    'export{a}from"react";': true,
    'import"react";': false,
    "import'react';": false
  }

  for (const [text, rewritten] of Object.entries(forms)) {
    const [declaration] = importsOf(ts, text)

    assert.equal(declaration.specifier, 'react', text)
    assert.equal(declaration.rewritten, rewritten, text)
    assert.equal(desktopMaps(text, declaration.at), rewritten, `${text}: the loader's pattern disagrees`)
  }
})

test('the bundle puts back the space a side-effect import needs and leaves the rest alone', () => {
  const text = 'import{a}from"react";import"react/jsx-runtime";import\'@hermes/plugin-sdk\';var s=";import\\"react\\";";'
  const spaced = loaderImports(ts, text)

  assert.equal(spaced, 'import{a}from"react";import "react/jsx-runtime";import \'@hermes/plugin-sdk\';var s=";import\\"react\\";";')
  assert.ok(importsOf(ts, spaced).every(declaration => declaration.rewritten && desktopMaps(spaced, declaration.at)))
})

test('the committed bundle imports exactly the three packages, each in a form the loader rewrites', () => {
  const text = readFileSync(path.join(root, 'desktop', 'plugin.js'), 'utf8')
  const declarations = importsOf(ts, text)

  assert.deepEqual(declarations.map(declaration => declaration.specifier).sort(), [...EXTERNAL].sort())
  assert.ok(declarations.every(declaration => declaration.rewritten && desktopMaps(text, declaration.at)))
})
