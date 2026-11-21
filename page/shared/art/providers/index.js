// Each provider's official logo for the model picker. Every file is the company's own artwork, from the source
// beside it (its site, brand or press kit, or official GitHub organisation), never redrawn or recoloured: an SVG is
// the published file byte for byte; a PNG is the published image (or SVG) scaled to 36 px, twice the size the picker
// draws it, where that is smaller than the SVG (the bundle has a size budget). OpenAI's files carry a wide empty
// margin, trimmed so its mark is the size of the others (the tile gives it room). bundle.mjs turns each
// import into a data URL. `dark` is the brand's own version for dark backgrounds (else the same file);
// `plate: 'dark'` puts a mark that has no version for dark backgrounds on a light plate in the dark theme (Novita);
// `plate: 'light'` puts one with none for light backgrounds on a dark plate in the light theme (StepFun's white disc).
// A provider missing from PROVIDER_BRANDS (custom endpoints, Mixture of Agents, ones Hermes adds later) keeps its
// letter mark.
// Each mark belongs to its company and is used only to name its provider; hermretro's MIT licence does not cover
// this artwork (see each source for its owner's terms).
import nous from './nous.png'
import nousDark from './nous-dark.png'
import fireworks from './fireworks.svg'
import openrouter from './openrouter.svg'
import openrouterDark from './openrouter-dark.svg'
import novita from './novita.svg'
import lmstudio from './lmstudio.png'
import anthropic from './anthropic.svg'
import anthropicDark from './anthropic-dark.svg'
import claude from './claude.png'
import openai from './openai.png'
import openaiDark from './openai-dark.png'
import xai from './xai.svg'
import xaiDark from './xai-dark.svg'
import qwen from './qwen.svg'
import alibabacloud from './alibabacloud.png'
import xiaomimimo from './xiaomimimo.png'
import tencentcloud from './tencentcloud.png'
import nvidia from './nvidia.png'
import huggingface from './huggingface.png'
import gemini from './gemini.png'
import vertexai from './vertexai.png'
import deepseek from './deepseek.png'
import zai from './zai.png'
import kimi from './kimi.png'
import kimiDark from './kimi-dark.png'
import stepfun from './stepfun.svg'
import minimax from './minimax.png'
import ollama from './ollama.png'
import arcee from './arcee.svg'
import gmi from './gmi.png'
import kilocode from './kilocode.svg'
import opencode from './opencode.png'
import opencodeDark from './opencode-dark.png'
import bedrock from './bedrock.png'
import azurefoundry from './azurefoundry.png'
import vercel from './vercel.svg'
import vercelDark from './vercel-dark.svg'
import actual from './actual.png'
import actualDark from './actual-dark.png'
import commandcode from './commandcode.png'
import deepinfra from './deepinfra.png'
import meta from './meta.png'
import nebius from './nebius.png'
import ramp from './ramp.png'
import upstage from './upstage.png'

export const LOGOS = {
  nous: { name: 'Nous Research', light: nous, dark: nousDark, source: 'https://nousresearch.com/ (its header badge, the girl\u2019s head only, as the owner asked: black, white on dark)' },
  fireworks: { name: 'Fireworks AI', light: fireworks, dark: fireworks, source: 'https://fireworks.ai/icon.svg' },
  openrouter: { name: 'OpenRouter', light: openrouter, dark: openrouterDark, source: 'https://openrouter.ai/brand' },
  novita: { name: 'Novita AI', light: novita, dark: novita, plate: 'dark', source: 'https://novita.ai/logo/logo_small.svg' },
  lmstudio: { name: 'LM Studio', light: lmstudio, dark: lmstudio, source: 'https://lmstudio.ai/brand' },
  anthropic: { name: 'Anthropic', light: anthropic, dark: anthropicDark, source: 'https://www.anthropic.com/press-kit' },
  claude: { name: 'Claude', light: claude, dark: claude, source: 'https://www.anthropic.com/press-kit' },
  openai: { name: 'OpenAI', light: openai, dark: openaiDark, source: 'https://openai.com/brand/' },
  xai: { name: 'xAI (Grok)', light: xai, dark: xaiDark, source: 'https://x.ai/legal/brand-guidelines' },
  qwen: { name: 'Qwen', light: qwen, dark: qwen, source: 'https://github.com/QwenLM/qwen-code' },
  alibabacloud: { name: 'Alibaba Cloud', light: alibabacloud, dark: alibabacloud, source: 'https://www.alibabacloud.com/' },
  xiaomimimo: { name: 'Xiaomi MiMo', light: xiaomimimo, dark: xiaomimimo, source: 'https://platform.xiaomimimo.com/' },
  tencentcloud: { name: 'Tencent Cloud', light: tencentcloud, dark: tencentcloud, source: 'https://cloud.tencent.com/' },
  nvidia: { name: 'NVIDIA', light: nvidia, dark: nvidia, source: 'https://www.nvidia.com/' },
  huggingface: { name: 'Hugging Face', light: huggingface, dark: huggingface, source: 'https://huggingface.co/brand' },
  gemini: { name: 'Google AI Studio', light: gemini, dark: gemini, source: 'https://aistudio.google.com/' },
  vertexai: { name: 'Google Cloud Vertex AI', light: vertexai, dark: vertexai, source: 'https://cloud.google.com/icons' },
  deepseek: { name: 'DeepSeek', light: deepseek, dark: deepseek, source: 'https://github.com/deepseek-ai/awesome-deepseek-integration/tree/main/docs/_logo%20svg' },
  zai: { name: 'Z.AI', light: zai, dark: zai, source: 'https://z.ai/' },
  kimi: { name: 'Kimi (Moonshot AI)', light: kimi, dark: kimiDark, source: 'https://moonshotai.github.io/Branding-Guide/scenarios/04-k-only/' },
  stepfun: { name: 'StepFun', light: stepfun, dark: stepfun, plate: 'light', source: 'https://www.stepfun.com/' },
  minimax: { name: 'MiniMax', light: minimax, dark: minimax, source: 'https://agent.minimax.io/' },
  ollama: { name: 'Ollama', light: ollama, dark: ollama, source: 'https://ollama.com/' },
  arcee: { name: 'Arcee AI', light: arcee, dark: arcee, source: 'https://www.arcee.ai/' },
  gmi: { name: 'GMI Cloud', light: gmi, dark: gmi, source: 'https://www.gmicloud.ai/' },
  kilocode: { name: 'Kilo Code', light: kilocode, dark: kilocode, source: 'https://kilo.ai/' },
  opencode: { name: 'OpenCode', light: opencode, dark: opencodeDark, source: 'https://opencode.ai/brand' },
  bedrock: { name: 'Amazon Bedrock', light: bedrock, dark: bedrock, source: 'https://aws.amazon.com/architecture/icons/' },
  azurefoundry: { name: 'Microsoft Foundry', light: azurefoundry, dark: azurefoundry, source: 'https://learn.microsoft.com/en-us/azure/architecture/icons/' },
  vercel: { name: 'Vercel', light: vercel, dark: vercelDark, source: 'https://vercel.com/geist/brands' },
  actual: { name: 'Actual', light: actual, dark: actualDark, source: 'https://actual.inc/favicon.svg' },
  commandcode: { name: 'Command Code', light: commandcode, dark: commandcode, source: 'https://commandcode.ai/brand' },
  deepinfra: { name: 'DeepInfra', light: deepinfra, dark: deepinfra, source: 'https://deepinfra.com/media-center' },
  meta: { name: 'Meta', light: meta, dark: meta, source: 'https://dev.meta.ai/' },
  nebius: { name: 'Nebius', light: nebius, dark: nebius, source: 'https://nebius.com/' },
  ramp: { name: 'Ramp', light: ramp, dark: ramp, source: 'https://router.com/' },
  upstage: { name: 'Upstage', light: upstage, dark: upstage, source: 'https://www.upstage.ai/resources/brand-resource-center' }
}

// Hermes provider slugs (hermes_cli.provider_catalog and the registry's aliases) by brand.
const PROVIDER_BRANDS = {
  nous: ['nous'],
  fireworks: ['fireworks', 'fireworks-ai', 'fw'],
  openrouter: ['openrouter'],
  novita: ['novita', 'novita-ai', 'novitaai'],
  lmstudio: ['lmstudio'],
  anthropic: ['anthropic'],
  claude: ['claude-subscription-directsdk-experimental'],
  openai: ['openai-api', 'openai-codex'],
  qwen: ['alibaba', 'qwen-oauth'],
  xai: ['xai', 'xai-oauth'],
  xiaomimimo: ['xiaomi'],
  tencentcloud: ['tencent-tokenhub', 'tencent-tokenplan'],
  nvidia: ['nvidia'],
  huggingface: ['huggingface'],
  gemini: ['gemini'],
  vertexai: ['vertex'],
  deepseek: ['deepseek'],
  zai: ['zai'],
  kimi: ['kimi-coding', 'kimi-coding-cn'],
  stepfun: ['stepfun'],
  minimax: ['minimax', 'minimax-cn', 'minimax-oauth'],
  ollama: ['ollama-cloud'],
  arcee: ['arcee'],
  gmi: ['gmi'],
  kilocode: ['kilocode'],
  opencode: ['opencode-go', 'opencode-zen'],
  bedrock: ['bedrock'],
  azurefoundry: ['azure-foundry'],
  vercel: ['ai-gateway'],
  actual: ['actual'],
  alibabacloud: ['alibaba-cloud-cn', 'alibaba-cn', 'alibaba-coding-cn', 'alibaba-coding-plan', 'alibaba-coding-plan-cn', 'alibaba-token-plan', 'alibaba-token-plan-cn', 'dashscope-cn', 'dashscope-coding-cn', 'dashscope-token-plan', 'dashscope-token-plan-cn'],
  commandcode: ['commandcode', 'commandcode-anthropic', 'commandcode-chat', 'commandcode-claude'],
  deepinfra: ['deep-infra', 'deepinfra', 'deepinfra-ai'],
  meta: ['meta', 'meta-ai', 'model-api', 'msl', 'muse', 'muse-spark'],
  nebius: ['nebius', 'nebius-tf', 'nebius-token-factory', 'nebius-tokenfactory', 'token-factory', 'tokenfactory'],
  ramp: ['ramp', 'ramp-router', 'router', 'router.com'],
  upstage: ['solar', 'upstage']
}

const BRAND_OF = new Map(Object.entries(PROVIDER_BRANDS).flatMap(([brand, slugs]) => slugs.map(slug => [slug, brand])))

/** The logo for a provider slug, or null when it has none. */
export const providerLogo = slug => LOGOS[BRAND_OF.get(String(slug ?? '').toLowerCase())] ?? null
