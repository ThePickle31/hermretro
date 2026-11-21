// The Build model picker's provider logos (page/pages/build/composer/provider-logo.js, page/shared/art/providers):
// each provider's official logo in the rail, the model rows and the model button, in the version for the theme on
// screen, and letters for a provider with none.
// Run alone: node tests/page/page-build-logos.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { registerAliases } from './aliases.mjs'
import { runScenario } from './harness.mjs'

// The logo index imports its files the way the bundle does: resolve those first (aliases.mjs).
registerAliases()

const ART = new URL('../../page/shared/art/providers/', import.meta.url)
// Every provider Hermes's catalogue lists (hermes_cli/provider_catalog.py, Hermes 0.23) and the brand whose logo it
// shows; null keeps letters (Hermes's own custom endpoint and Mixture of Agents). A provider Hermes adds later shows
// letters until its logo is added here and in page/shared/art/providers/index.js.
const CATALOGUE = {
  'nous': 'Nous Research',
  'fireworks': 'Fireworks AI',
  'openrouter': 'OpenRouter',
  'moa': null,
  'novita': 'Novita AI',
  'lmstudio': 'LM Studio',
  'anthropic': 'Anthropic',
  'openai-codex': 'OpenAI',
  'openai-api': 'OpenAI',
  'alibaba': 'Qwen',
  'xai-oauth': 'xAI (Grok)',
  'xiaomi': 'Xiaomi MiMo',
  'tencent-tokenhub': 'Tencent Cloud',
  'tencent-tokenplan': 'Tencent Cloud',
  'nvidia': 'NVIDIA',
  'huggingface': 'Hugging Face',
  'gemini': 'Google AI Studio',
  'vertex': 'Google Cloud Vertex AI',
  'deepseek': 'DeepSeek',
  'xai': 'xAI (Grok)',
  'zai': 'Z.AI',
  'kimi-coding': 'Kimi (Moonshot AI)',
  'kimi-coding-cn': 'Kimi (Moonshot AI)',
  'stepfun': 'StepFun',
  'minimax': 'MiniMax',
  'minimax-oauth': 'MiniMax',
  'minimax-cn': 'MiniMax',
  'ollama-cloud': 'Ollama',
  'arcee': 'Arcee AI',
  'gmi': 'GMI Cloud',
  'kilocode': 'Kilo Code',
  'opencode-zen': 'OpenCode',
  'opencode-go': 'OpenCode',
  'bedrock': 'Amazon Bedrock',
  'azure-foundry': 'Microsoft Foundry',
  'ai-gateway': 'Vercel',
  'qwen-oauth': 'Qwen',
  'actual': 'Actual',
  'alibaba-cn': 'Alibaba Cloud',
  'alibaba-token-plan': 'Alibaba Cloud',
  'alibaba-token-plan-cn': 'Alibaba Cloud',
  'alibaba-coding-plan': 'Alibaba Cloud',
  'alibaba-coding-plan-cn': 'Alibaba Cloud',
  'commandcode': 'Command Code',
  'commandcode-anthropic': 'Command Code',
  'custom': null,
  'deepinfra': 'DeepInfra',
  'meta-ai': 'Meta',
  'nebius-token-factory': 'Nebius',
  'router': 'Ramp',
  'upstage': 'Upstage',
  'claude-subscription-directsdk-experimental': 'Claude'
}

// Each brand's light and dark files, written out here rather than read from the logo index, so an index that
// points a brand at another brand's image fails.
const FILES = {
  nous: ['nous.png', 'nous-dark.png'],
  fireworks: ['fireworks.svg', 'fireworks.svg'],
  openrouter: ['openrouter.svg', 'openrouter-dark.svg'],
  novita: ['novita.svg', 'novita.svg'],
  lmstudio: ['lmstudio.png', 'lmstudio.png'],
  anthropic: ['anthropic.svg', 'anthropic-dark.svg'],
  claude: ['claude.png', 'claude.png'],
  openai: ['openai.png', 'openai-dark.png'],
  xai: ['xai.svg', 'xai-dark.svg'],
  qwen: ['qwen.svg', 'qwen.svg'],
  alibabacloud: ['alibabacloud.png', 'alibabacloud.png'],
  xiaomimimo: ['xiaomimimo.png', 'xiaomimimo.png'],
  tencentcloud: ['tencentcloud.png', 'tencentcloud.png'],
  nvidia: ['nvidia.png', 'nvidia.png'],
  huggingface: ['huggingface.png', 'huggingface.png'],
  gemini: ['gemini.png', 'gemini.png'],
  vertexai: ['vertexai.png', 'vertexai.png'],
  deepseek: ['deepseek.png', 'deepseek.png'],
  zai: ['zai.png', 'zai.png'],
  kimi: ['kimi.png', 'kimi-dark.png'],
  stepfun: ['stepfun.svg', 'stepfun.svg'],
  minimax: ['minimax.png', 'minimax.png'],
  ollama: ['ollama.png', 'ollama.png'],
  arcee: ['arcee.svg', 'arcee.svg'],
  gmi: ['gmi.png', 'gmi.png'],
  kilocode: ['kilocode.svg', 'kilocode.svg'],
  opencode: ['opencode.png', 'opencode-dark.png'],
  bedrock: ['bedrock.png', 'bedrock.png'],
  azurefoundry: ['azurefoundry.png', 'azurefoundry.png'],
  vercel: ['vercel.svg', 'vercel-dark.svg'],
  actual: ['actual.png', 'actual-dark.png'],
  commandcode: ['commandcode.png', 'commandcode.png'],
  deepinfra: ['deepinfra.png', 'deepinfra.png'],
  meta: ['meta.png', 'meta.png'],
  nebius: ['nebius.png', 'nebius.png'],
  ramp: ['ramp.png', 'ramp.png'],
  upstage: ['upstage.png', 'upstage.png']
}

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
  check('each brand shows its own files, light and dark', () => {
    const url = file => `data:image/${file.endsWith('.svg') ? 'svg+xml' : 'png'};base64,${readFileSync(new URL(file, ART)).toString('base64')}`

    assert.deepEqual(Object.keys(LOGOS).sort(), Object.keys(FILES).sort())
    // Marks with no version for one theme: Novita's black and Qwen's dark blue on dark, StepFun's white disc on light.
    assert.deepEqual(Object.entries(LOGOS).filter(([, logo]) => logo.plate).map(([brand, logo]) => `${brand}:${logo.plate}`).sort(), ['novita:dark', 'qwen:dark', 'stepfun:light'])
    // The shipped bundle says the embedded marks are not under the MIT licence.
    assert.match(readFileSync(new URL('../../desktop/plugin.js', import.meta.url), 'utf8').slice(0, 800), /not covered by the MIT licence/)
    for (const [brand, [light, dark]] of Object.entries(FILES)) {
      assert.equal(LOGOS[brand].light, url(light), `${brand} light`)
      assert.equal(LOGOS[brand].dark, url(dark), `${brand} dark`)
    }
  })
  check('the provider slugs Hermes lists have a logo, except Hermes\u2019s own custom endpoint and Mixture of Agents', () => {
    assert.equal(providerLogo('openai-codex').name, 'OpenAI')
    assert.equal(providerLogo('claude-subscription-directsdk-experimental').name, 'Claude')
    assert.equal(providerLogo('NOUS').name, 'Nous Research', 'slugs match whatever their case')
    assert.equal(providerLogo('custom'), null)
    assert.equal(providerLogo(undefined), null)
    for (const [slug, brand] of Object.entries(CATALOGUE)) assert.equal(providerLogo(slug)?.name ?? null, brand, slug)
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
    assert.equal(chip().querySelector('.cs-b-mp-mark img').getAttribute('src'), LOGOS.openai.dark)
    assert.notEqual(LOGOS.openai.dark, LOGOS.openai.light)
    assert.ok(tiles()[1].classList.contains('plate'), 'Novita has no version for dark backgrounds')
    assert.ok(!tiles()[2].classList.contains('plate'), 'StepFun\u2019s white disc shows on dark')
  })
  scenario.theme = 'light'
  await view.rerender()
  check('light theme: the light version, and no plate', () => {
    assert.equal(chip().querySelector('.cs-b-mp-mark img').getAttribute('src'), LOGOS.openai.light)
    assert.ok(!tiles()[1].classList.contains('plate'))
    assert.ok(tiles()[2].classList.contains('plate'), 'StepFun\u2019s white disc gets a dark plate on light')
  })
})
