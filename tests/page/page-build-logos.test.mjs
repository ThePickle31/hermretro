// The Build model picker's provider logos (page/pages/build/composer/provider-logo.js, page/shared/art/providers):
// each provider's official logo in the rail, the model rows and the model button, in the version for the theme on
// screen, and letters for a provider with none.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { registerAliases } from './aliases.mjs'
import { runScenario } from './harness.mjs'

// The logo index imports its files the way the bundle does: resolve those first (aliases.mjs).
registerAliases()

const ART = new URL('../../page/shared/art/providers/', import.meta.url)
const png = name => `data:image/png;base64,${readFileSync(new URL(name, ART)).toString('base64')}`

await runScenario(async ({ buildScenario, act, dom, emit, scenario, page, settle, mount, check, answered }) => {
  const { LOGOS, providerLogo } = await import('../../page/shared/art/providers/index.js')

  check('every logo has a light and a dark file that is in the folder, and the official page it came from', () => {
    const files = readFileSync(new URL('index.js', ART), 'utf8').match(/from '\.\/([^']+)'/g).map(line => line.slice(8, -1))

    for (const file of files) assert.ok(readFileSync(new URL(file, ART)).length > 0, file)
    for (const [brand, logo] of Object.entries(LOGOS)) {
      assert.match(logo.light, /^data:image\/(png;base64|svg\+xml(;base64)?),/, brand)
      assert.match(logo.dark, /^data:image\/(png;base64|svg\+xml(;base64)?),/, brand)
      assert.match(logo.source, /^https:\/\//, brand)
      assert.ok(logo.name, brand)
    }
  })
  check('the shipped page carries the provider artwork notice', () => {
    assert.match(readFileSync(new URL('../../desktop/plugin.js', import.meta.url), 'utf8').slice(0, 800), /not covered by the MIT licence/)
  })
  check('provider aliases and unknown providers', () => {
    assert.equal(providerLogo('openai-codex').name, 'OpenAI')
    assert.equal(providerLogo('claude-subscription-directsdk-experimental').name, 'Claude')
    assert.equal(providerLogo('NOUS').name, 'Nous Research', 'slugs match whatever their case')
    assert.equal(providerLogo('custom'), null)
    assert.equal(providerLogo(undefined), null)
    assert.equal(providerLogo('unknown-provider'), null)
  })

  buildScenario({ selected: 'fff666fff666' })
  scenario.games = answered({ games: [{ id: 'fff666fff666', title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio',
    state: 'ready', rom: null, webExport: true, thumb: null, chat: null, error: null, session: { storedId: 'st-frog' } }],
  device: { hardwareEnabled: false, skipped: true } })
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, running: false, messages: [] })
  scenario.models = answered({ model: 'gpt-6.2-sol', provider: 'openai-codex', providers: [
    { slug: 'openai-codex', name: 'ChatGPT or Codex Subscription', authenticated: true, models: ['gpt-6.2-sol'] },
    { slug: 'novita', name: 'Novita AI', authenticated: true, models: ['deepseek-v4'] },
    { slug: 'stepfun', name: 'StepFun', authenticated: true, models: ['step-4'] },
    { slug: 'custom', name: 'Custom endpoint', authenticated: true, models: ['local-1'] }] })
  scenario.theme = 'dark'

  const view = await mount(page)
  await settle()
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-frog', payload: { model: 'gpt-6.2-sol', provider: 'openai-codex', reasoning_effort: 'medium' } }) })
  await settle()
  const chip = () => view.node.querySelector('.cs-b-mp-chip')
  const pop = () => view.node.querySelector('.cs-b-mp-pop')
  const tiles = () => [...pop().querySelectorAll('.cs-b-mp-prov')].map(node => node.firstChild)
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })

  check('the button, the rail and the model rows show the provider\u2019s logo, hidden from screen readers', () => {
    const mark = chip().querySelector('.cs-b-mp-mark')
    assert.equal(mark.dataset.brand, 'OpenAI')
    assert.equal(mark.getAttribute('aria-hidden'), 'true')
    assert.equal(mark.querySelector('img').getAttribute('alt'), '')
    assert.deepEqual(tiles().map(node => node.dataset.brand ?? node.textContent), ['OpenAI', 'Novita AI', 'StepFun', 'Cu'], 'no logo: letters, two when another provider starts the same')
    assert.equal(pop().querySelector('.cs-b-mp-row .cs-b-mp-glyph').dataset.brand, 'OpenAI')
    assert.equal(pop().querySelector('.cs-b-mp-prov[aria-label="ChatGPT or Codex Subscription"]').title, 'ChatGPT or Codex Subscription', 'the name stays on the tile')
  })
  check('the bundle embeds an SVG logo byte for byte (StepFun: non-ASCII text and a # colour)', () => {
    const src = tiles()[2].querySelector('img').getAttribute('src')
    const prefix = 'data:image/svg+xml,'

    assert.ok(src.startsWith(prefix), src.slice(0, 40))
    // A bare # would end the image at a URL fragment in a browser; anything outside printable ASCII is escaped.
    assert.equal(new URL(src).hash, '', 'no # left unescaped')
    assert.match(src, /^[\x20-\x7e]*$/, 'only printable ASCII')
    assert.deepEqual(Buffer.from(decodeURIComponent(src.slice(prefix.length)), 'utf8'), readFileSync(new URL('stepfun.svg', ART)))
  })
  check('dark theme: the brand\u2019s version for dark backgrounds, and a plate under a mark that has none', () => {
    assert.equal(chip().querySelector('.cs-b-mp-mark img').getAttribute('src'), png('openai-dark.png'))
    assert.ok(tiles()[1].classList.contains('plate'), 'Novita has no version for dark backgrounds')
    assert.ok(!tiles()[2].classList.contains('plate'), 'StepFun\u2019s white disc shows on dark')
  })
  scenario.theme = 'light'
  await view.rerender()
  check('light theme: the light version, and no plate', () => {
    assert.equal(chip().querySelector('.cs-b-mp-mark img').getAttribute('src'), png('openai.png'))
    assert.ok(!tiles()[1].classList.contains('plate'))
    assert.ok(tiles()[2].classList.contains('plate'), 'StepFun\u2019s white disc gets a dark plate on light')
  })
})
