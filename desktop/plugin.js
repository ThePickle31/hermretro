/**
 * hermretro — Hermes Desktop half.
 *
 * One full page (`/hermretro`) with a sidebar nav row and a ⌘K command.
 * One segmented control in its header switches between five pages
 * (docs/dev/STUDIO-PAGES.md is the contract with the backend):
 *   Home      hero, then Continue (last game or setup) / Start something / Studio.
 *   Setup     the wizard driven by the `status` / `doctor` RPCs (game steps, then a
 *             choice between the emulator and a physical Chromatic, whose steps are
 *             optional), beside the flying Chromatic.
 *   Prompts   the Reader: prompt list, editable prompt, New chat / Add / Copy.
 *   Games     the shelf of real cartridges, from the `games` RPC.
 *   Emulator  ModRetro's real player in a SandboxedFrame (`player` RPC), kept
 *             loaded while other pages are shown.
 * Prompts only ever go into a chat composer; nothing is sent. Two panes sit beside the chat.
 * When the agent presents a game (`chromatic_present_game`) the emulator opens in a workspace tab
 * right of the chat (`host.openWorkspace`, driven by `tool.complete` gateway events; builds open
 * nothing); one game runs at a time, in whichever of the page and the tab opened it last.
 *
 * Plain ESM loaded uncompiled by the desktop app: UI is jsx()/jsxs() calls,
 * and only `@hermes/plugin-sdk`, `react` and `react/jsx-runtime` are imported.
 * Runtime plugins are not scanned by the app's Tailwind build, so the page
 * carries its own scoped stylesheet (`CSS`, classes `cs-*`); every colour is a
 * theme variable (`var(--ui-*)`), so light, dark and every skin repaint it.
 * The artwork is embedded at the end of the file by tools/embed_art.py.
 * Look at it with tests/desktop/preview/build.mjs (light and dark).
 */

import {
  atom,
  Button,
  Codicon,
  CopyButton,
  host,
  PALETTE_AREA,
  ROUTES_AREA,
  SandboxedFrame,
  ScrollArea,
  Separator,
  SIDEBAR_NAV_AREA,
  Tip,
  useQuery,
  useQueryClient,
  useValue
} from '@hermes/plugin-sdk'
import { useCallback, useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'hermretro'
const ROUTE = '/hermretro'
const RPC_STATUS = `plugin.${ID}.status`
const RPC_DOCTOR = `plugin.${ID}.doctor`
const RPC_ACTIVITY = `plugin.${ID}.activity`
const RPC_STUDIO_PROFILE = `plugin.${ID}.studio_profile`
const RPC_INSTALL = `plugin.${ID}.install`
const RPC_GAMES = `plugin.${ID}.games`
const RPC_GAME_THUMB = `plugin.${ID}.game_thumb`
const RPC_PLAYER = `plugin.${ID}.player`
// The built-in demo cartridge (ModRetro's hello-color example in GB Studio's player). The Emulator
// page plays it whenever the library has nothing playable, so the real player is always on screen.
const DEMO_ID = 'demo'
const DEMO_GAME = { id: DEMO_ID, title: 'Hello Color', kind: 'gbdk', note: 'ModRetro example' }
const RPC_CAPTURES = `plugin.${ID}.captures`
const RPC_CAPTURE_IMAGE = `plugin.${ID}.capture_image`
// hermretro works in its own Hermes profile; the first setup step creates it.
const STUDIO_PROFILE = 'hermretro'
const ENABLE_COMMAND = `hermes plugins enable ${ID}`

// The agent half's `config_schema` form lives under Settings ▸ Plugins keyed by
// the agent plugin key (`?agent=`). `pluginSettingsHref()` builds `?plugin=`,
// which addresses pages a DESKTOP half registers — this desktop half registers
// none, so the agent route is the right deep link (it also resolves when the
// form is folded under a desktop entry as "Agent settings").
const AGENT_SETTINGS_HREF = `/settings?tab=plugins&agent=${ID}`
const PLUGINS_HREF = `/capabilities?tab=plugins&plugin=${ID}`

const LINKS = {
  node: 'https://nodejs.org/',
  firmware: 'https://support.modretro.com/en_us/articles/chromatic-firmware-updater-ryhoYnzCx',
  quickstart: 'https://support.modretro.com/en_us/chromatic-codex-edition-quickstart-guide-By1iOlcMg',
  showcase: 'https://developers.openai.com/modretro'
}

const SETUP_PROMPT =
  'Set up hermretro so I can create games, build ROMs, and run automated playtests. Check what is already installed and prepare the missing dependencies.'

const DEVICE_CLI_PROMPT =
  "Install ModRetro's Chromatic device software for hermretro so I can use my physical Chromatic."

// The prompt library, in ModRetro's quickstart order. `{folder}` / `{name}` are filled from the
// inputs on the Prompts page; `src` says whether the prompt follows ModRetro's quickstart or is
// one of Hermes' own. Prompts with `hw` need a set-up Chromatic.
const PROMPT_SECTIONS = [
  {
    id: 'plan',
    n: '01',
    title: 'Plan',
    prompts: [
      {
        id: 'plan',
        title: 'Plan a game',
        src: 'hermes',
        text: 'Use hermretro to help me plan a small Game Boy Color game before we build anything. Interview me briefly, then write the game brief, backlog and test plan into the project.'
      }
    ]
  },
  {
    id: 'create',
    n: '02',
    title: 'Create',
    prompts: [
      {
        id: 'new-game',
        title: 'Create a new game',
        src: 'modretro',
        text: 'Use hermretro to create and select a new GB Studio project at {folder}/{name}. Make a small exploration game where a gardener collects three seeds and plants them to unlock a gate.',
        defaults: { name: 'MoonGarden' },
        note: 'The parent folder must already exist.'
      },
      {
        id: 'remix',
        title: 'Remix an example',
        src: 'modretro',
        text: 'Use hermretro to create and select a Wrecklight remix at {folder}/{name}. Show me its rooms and controls, then help me turn the opening area into an abandoned research station.',
        defaults: { name: 'MyWrecklight' },
        note: 'The Wrecklight source is not bundled; the agent will ask for a local copy if needed.'
      }
    ]
  },
  {
    id: 'play',
    n: '03',
    title: 'Play',
    prompts: [
      {
        id: 'play-game',
        title: 'Play my game',
        src: 'modretro',
        text: 'Build my selected game and show it to me in the emulator beside the chat so I can play it. Show me the new build there whenever we make a change worth trying.'
      },
      {
        id: 'playtest',
        title: 'Build and playtest',
        src: 'hermes',
        text: 'Build my selected game, then run an automated playtest: boot it, walk around the first room, and show me real frames from the emulator.'
      }
    ]
  },
  {
    id: 'polish',
    n: '04',
    title: 'Polish',
    prompts: [
      {
        id: 'scene',
        title: 'Add a scene',
        src: 'modretro',
        text: 'Add a village scene to my selected project with three houses, a central fountain, and a character I can talk to. Connect it to the starting area.'
      },
      {
        id: 'artwork',
        title: 'Characters and artwork',
        src: 'modretro',
        text: "Create a small robot player sprite with idle and walking animations that fit this project's style and Game Boy hardware limits. Add it to the game and show it in a scene."
      },
      {
        id: 'palette',
        title: 'Update the palette',
        src: 'modretro',
        text: 'Give this scene a moonlit palette with cool blue shadows and warm window lights. Check readability and show the result from the emulator.'
      },
      {
        id: 'audit',
        title: 'Hardware limits audit',
        src: 'modretro',
        text: "Audit my project's backgrounds and sprites for Game Boy hardware limits. Identify problems and fix any assets that would prevent a successful build."
      }
    ]
  },
  {
    id: 'device',
    n: '05',
    title: 'On your Chromatic',
    prompts: [
      {
        id: 'stream',
        title: 'Stream to Chromatic',
        src: 'modretro',
        hw: true,
        text: 'Stream a two-minute live demo of my built ROM to the connected Chromatic so I can try its controls, video, and audio.'
      },
      {
        id: 'flash',
        title: 'Flash a cartridge',
        src: 'modretro',
        hw: true,
        text: 'Flash my built homebrew ROM to the connected Chromatic cartridge, then guide me through manual boot, gameplay, and audio checks.'
      }
    ]
  }
]

const ALL_PROMPTS = PROMPT_SECTIONS.flatMap(section => section.prompts.map(prompt => ({ ...prompt, section })))
const promptById = id => ALL_PROMPTS.find(prompt => prompt.id === id) ?? ALL_PROMPTS[0]
const FLASH_PROMPT = promptById('flash').text

// ── Styles (every colour is a theme variable) ─────────────────────────────────

const C = {
  primary: 'var(--ui-text-primary)',
  secondary: 'var(--ui-text-secondary)',
  tertiary: 'var(--ui-text-tertiary)',
  quaternary: 'var(--ui-text-quaternary)',
  stroke: 'var(--ui-stroke-tertiary)',
  fill: 'var(--ui-bg-quaternary)',
  good: 'var(--ui-green)',
  warn: 'var(--ui-yellow)',
  bad: 'var(--ui-red)'
}

const S = {
  row: { alignItems: 'center', display: 'flex', flexWrap: 'wrap', gap: 8 },
  col: { display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 },
  muted: { color: C.tertiary, fontSize: 12, lineHeight: 1.5 },
  faint: { color: C.quaternary, fontSize: 11, lineHeight: 1.5 },
  code: {
    background: C.fill,
    borderRadius: 4,
    color: C.primary,
    fontSize: 12,
    overflowWrap: 'anywhere',
    padding: '4px 8px',
    userSelect: 'text'
  }
}

// The page's own stylesheet. Runtime plugins are not seen by the app's Tailwind build, so the
// page carries plain CSS, scoped under `.cs-page`. Every colour is a theme variable, so light,
// dark and every skin repaint it; the two typefaces are the ones the app itself loads.
const MONO = "var(--dt-font-mono, 'JetBrains Mono', ui-monospace, monospace)"
const DISPLAY = "'Collapse', var(--dt-font-sans, system-ui), sans-serif"

const CSS = `
.cs-page { container-type: inline-size; box-sizing: border-box; color: var(--ui-text-primary); display: flex; flex-direction: column; font-size: 13px; line-height: 1.55; min-height: 100%; overflow-x: clip; position: relative; width: 100%; }
.cs-page *, .cs-page *::before, .cs-page *::after { box-sizing: border-box; }
.cs-eyebrow { align-items: center; color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font: 700 10.5px/1.3 ${MONO}; gap: 4px 10px; letter-spacing: .14em; margin: 0; text-transform: uppercase; }
.cs-accent { color: var(--ui-accent); }
.cs-word { color: var(--ui-text-primary); font-family: ${DISPLAY}; font-weight: 700; letter-spacing: .04em; line-height: .92; margin: 0; text-transform: uppercase; text-wrap: balance; }
.cs-title { font-size: clamp(28px, 3.4cqi, 60px); }
.cs-lede { color: var(--ui-text-secondary); font-size: 14px; line-height: 1.6; margin: 0; max-width: 62ch; text-wrap: pretty; }
.cs-small { color: var(--ui-text-tertiary); font-size: 12px; line-height: 1.55; margin: 0; }
.cs-faint { color: var(--ui-text-quaternary); font-size: 11.5px; line-height: 1.5; margin: 0; overflow-wrap: anywhere; }
.cs-mono { font-family: ${MONO}; }
.cs-row { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; }
.cs-col { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.cs-grow { flex: 1; }
.cs-error { color: var(--ui-red); font: 12px/1.5 ${MONO}; margin: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.cs-warn { color: var(--ui-yellow); }
.cs-draft { color: var(--ui-yellow); font: 700 9.5px ${MONO}; letter-spacing: .1em; text-transform: uppercase; }
.cs-link { all: unset; color: var(--ui-accent); cursor: pointer; font: 700 10px ${MONO}; letter-spacing: .12em; text-transform: uppercase; }
.cs-link:hover { text-decoration: underline; text-underline-offset: 3px; }
.cs-link:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }

/* header: wordmark, one segmented control, refresh */
.cs-top { align-items: center; background: var(--ui-bg-editor); border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 24px; padding: 14px clamp(16px, 3.5cqi, 64px); position: sticky; top: 0; z-index: 10; }
.cs-brand { all: unset; color: var(--ui-text-primary); cursor: pointer; font: 700 18px/.9 ${DISPLAY}; letter-spacing: .04em; text-transform: uppercase; white-space: nowrap; }
.cs-brand span { color: var(--ui-accent); }
.cs-brand:hover span { text-decoration: underline; text-underline-offset: 4px; }
.cs-brand:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 4px; }
.cs-seg { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: inline-flex; margin: 0 auto; }
.cs-seg button { align-items: center; appearance: none; background: transparent; border: 0; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; font: 700 10.5px/1 ${MONO}; gap: 7px; letter-spacing: .12em; padding: 7px 16px; text-transform: uppercase; white-space: nowrap; }
.cs-seg button + button { box-shadow: inset 1px 0 0 var(--ui-stroke-secondary); }
.cs-seg button:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-seg button:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-seg button[aria-current] { background: var(--ui-accent); box-shadow: none; color: var(--ui-bg-editor); }
.cs-seg .pip { background: var(--ui-yellow); height: 6px; width: 6px; }
.cs-seg .live { background: var(--ui-green); border-radius: 50%; box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-green) 25%, transparent); height: 6px; width: 6px; }
.cs-seg button[aria-current] .pip, .cs-seg button[aria-current] .live { background: var(--ui-bg-editor); box-shadow: none; }
.cs-top-end { display: flex; justify-content: flex-end; width: 120px; }
.cs-pad { display: flex; flex: 1; flex-direction: column; gap: 28px; padding: 26px clamp(16px, 3.5cqi, 64px) 36px; }
.cs-pad.flush { gap: 0; padding: 0; }
.cs-chip { align-items: center; background: var(--ui-bg-quaternary); color: var(--ui-text-secondary); display: inline-flex; font: 400 11px/1 ${MONO}; gap: 6px; padding: 5px 8px; white-space: nowrap; }
.cs-chip > i { background: var(--ui-text-quaternary); display: block; flex: none; height: 6px; width: 6px; }
.cs-chip.good > i { background: var(--ui-green); }
.cs-chip.warn > i { background: var(--ui-yellow); }
.cs-chip.bad > i { background: var(--ui-red); }
.cs-chip.accent > i { background: var(--ui-accent); }
.cs-tag { font: 700 9.5px/1 ${MONO}; letter-spacing: .1em; padding: 4px 6px; text-transform: uppercase; white-space: nowrap; }
.cs-tag.good { background: color-mix(in srgb, var(--ui-green) 13%, transparent); color: var(--ui-green); }
.cs-tag.warn { background: color-mix(in srgb, var(--ui-yellow) 12%, transparent); color: var(--ui-yellow); }
.cs-tag.bad { background: color-mix(in srgb, var(--ui-red) 13%, transparent); color: var(--ui-red); }
.cs-tag.quiet { box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); color: var(--ui-text-tertiary); }
.cs-tag.accent { background: var(--ui-bg-secondary); color: var(--ui-accent); }
.cs-art { aspect-ratio: 3 / 4; background: var(--ui-accent); flex: none; justify-self: center; max-width: 440px; pointer-events: none; width: 100%;
  -webkit-mask: var(--cs-hermes) center top / contain no-repeat, linear-gradient(currentColor 0 74%, transparent); -webkit-mask-composite: source-in;
  mask: var(--cs-hermes) center top / contain no-repeat, linear-gradient(currentColor 0 74%, transparent); mask-composite: intersect; }
.cs-page-head { align-items: end; display: grid; gap: 16px 28px; grid-template-columns: minmax(0, 1fr) auto; }
.cs-page-head > .cs-col { gap: 12px; }
.cs-key { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-tertiary); font: 700 10px ${MONO}; padding: 2px 5px; }
.cs-note { align-items: center; display: flex; flex-wrap: wrap; gap: 10px; }

/* setup: rail, current step, flying Chromatic */
.cs-setup { align-items: start; display: grid; gap: clamp(24px, 3.6cqi, 64px); grid-template-columns: clamp(180px, 13cqi, 240px) minmax(0, 820px) minmax(130px, 1fr); }
.cs-rail { display: flex; flex-direction: column; position: sticky; top: 76px; }
.cs-rail-group { color: var(--ui-text-quaternary); display: flex; font: 700 10px/1 ${MONO}; justify-content: space-between; letter-spacing: .14em; padding: 0 0 8px; text-transform: uppercase; }
.cs-rail-group.second { padding-top: 22px; }
.cs-rail-item { align-items: center; appearance: none; background: transparent; border: 0; color: var(--ui-text-tertiary); cursor: pointer; display: grid; font: inherit; gap: 8px; grid-template-columns: 22px 1fr 14px; margin: 0 -8px; padding: 7px 8px; text-align: left; transition: color .1s, background-color .1s; }
.cs-rail-item:hover { color: var(--ui-text-primary); transition: none; }
.cs-rail-item .n { color: var(--ui-text-quaternary); font: 700 11px ${MONO}; }
.cs-rail-item[data-state='done'] { color: var(--ui-text-secondary); }
.cs-rail-item[data-state='skipped'] .l { color: var(--ui-text-quaternary); text-decoration: line-through; }
.cs-rail-item[data-auto] { color: var(--ui-text-primary); font-weight: 600; }
.cs-rail-item[data-auto] .n { color: var(--ui-accent); }
.cs-rail-item[aria-current] { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-meter { display: flex; gap: 3px; margin: 18px 0 8px; }
.cs-meter button { appearance: none; background: transparent; border: 0; cursor: pointer; flex: 1; min-width: 0; padding: 4px 0; }
.cs-meter button > i { background: var(--ui-stroke-tertiary); display: block; height: 3px; }
.cs-meter button[data-state='done'] > i { background: var(--ui-green); }
.cs-meter button[data-state='skipped'] > i { background: var(--ui-stroke-secondary); opacity: .5; }
.cs-meter button[data-auto] > i { background: var(--ui-accent); }
.cs-meter button.gap { margin-left: 6px; }
.cs-stage { display: flex; flex-direction: column; gap: 22px; min-width: 0; }
.cs-stage-head { display: flex; flex-direction: column; gap: 14px; }
.cs-stage-foot { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 10px 16px; justify-content: space-between; margin-top: 4px; padding-top: 14px; }
.cs-content { display: flex; flex-direction: column; gap: 18px; }
.cs-actions { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; }
.cs-prompt { background: var(--ui-bg-quaternary); color: var(--ui-text-secondary); font: 12.5px/1.6 ${MONO}; margin: 0; overflow-wrap: anywhere; padding: 13px 16px 13px 34px; position: relative; user-select: text; white-space: pre-wrap; }
.cs-prompt::before { color: var(--ui-accent); content: '❯'; left: 14px; position: absolute; top: 13px; }
.cs-facts { display: grid; gap: 9px 22px; grid-template-columns: max-content 1fr; margin: 0; }
.cs-facts dt { color: var(--ui-text-tertiary); font: 700 10px/2 ${MONO}; letter-spacing: .12em; text-transform: uppercase; }
.cs-facts dd { color: var(--ui-text-secondary); margin: 0; }
.cs-watch { align-items: center; background: var(--ui-bg-quaternary); color: var(--ui-text-secondary); display: flex; gap: 12px; padding: 11px 14px; }
.cs-watch.quiet { background: transparent; color: var(--ui-text-tertiary); font-size: 12px; gap: 8px; padding: 0; }
.cs-lem { flex: none; height: 18px; width: 34px; }
.cs-watch.quiet .cs-lem { height: 12px; width: 24px; }
.cs-lem path { fill: none; }
.cs-lem .track { stroke: var(--ui-stroke-tertiary); stroke-width: .07; }
.cs-lem .run { animation: cs-lem 1.4s linear infinite; stroke: var(--ui-accent); stroke-dasharray: 18 82; stroke-linecap: round; stroke-width: .11; }
@keyframes cs-lem { to { stroke-dashoffset: -100; } }
.cs-glyph .cs-dash { animation: cs-dash 1s linear infinite; }
@keyframes cs-dash { to { stroke-dashoffset: -10; } }
.cs-comps { display: flex; flex-direction: column; }
.cs-comp { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: grid; gap: 4px 12px; grid-template-columns: 14px minmax(0, 1fr) auto auto; padding: 8px 0; }
.cs-comp:last-child { border-bottom: 1px solid var(--ui-stroke-tertiary); }
.cs-comp .name { color: var(--ui-text-primary); }
.cs-comp .name small { color: var(--ui-text-quaternary); font-size: 11px; margin-left: 6px; }
.cs-comp .ver { color: var(--ui-text-tertiary); font: 11px ${MONO}; text-align: right; }
.cs-comp .st { font: 700 9.5px ${MONO}; letter-spacing: .1em; min-width: 82px; text-align: right; text-transform: uppercase; }
.cs-comp .detail { color: var(--ui-text-quaternary); font-size: 11.5px; grid-column: 2 / -1; }
.cs-comp .st.ready { color: var(--ui-green); }
.cs-comp .st.missing { color: var(--ui-yellow); }
.cs-comp .st.incompatible { color: var(--ui-red); }
.cs-comp .st.optional, .cs-comp .st.unknown { color: var(--ui-text-quaternary); }
.cs-kbd { background: transparent; border: 1px solid var(--ui-stroke-tertiary); border-bottom-width: 3px; color: var(--ui-text-primary); display: inline-grid; font: 700 12px ${MONO}; height: 30px; min-width: 30px; padding: 0 8px; place-items: center; }
.cs-warnline { align-items: flex-start; color: var(--ui-text-primary); display: flex; font-weight: 500; gap: 10px; }
.cs-warnline > span:first-child { color: var(--ui-yellow); display: inline-flex; padding-top: 2px; }
.cs-choice { border-bottom: 1px solid var(--ui-stroke-tertiary); border-top: 1px solid var(--ui-stroke-tertiary); display: grid; grid-template-columns: 1fr 1fr; }
.cs-choice > div { display: flex; flex-direction: column; gap: 8px; padding: 20px 24px 22px 0; }
.cs-choice > div + div { border-left: 1px solid var(--ui-stroke-tertiary); padding-left: 24px; padding-right: 0; }
.cs-choice h3 { color: var(--ui-text-primary); font-size: 16px; font-weight: 600; margin: 0; }
.cs-choice .cs-actions { margin-top: auto; padding-top: 8px; }

/* first-run onboarding: welcome, what gets downloaded / installing, Chromatic?, first game */
.cs-bad { color: var(--ui-red); }
.cs-good { color: var(--ui-green); }
.cs-onb { display: flex; flex: 1; flex-direction: column; justify-content: center; min-height: min(78vh, 900px); }
.cs-onb[data-screen='install'] { justify-content: flex-start; padding-top: clamp(8px, 2cqi, 32px); }
.cs-onb-hero { align-items: center; display: grid; gap: clamp(24px, 4cqi, 72px); grid-template-columns: minmax(0, 1fr) minmax(200px, 30cqi); }
.cs-onb-hero h1 { font-size: clamp(44px, 6.6cqi, 108px); }
.cs-onb-hero .cs-art { max-width: 460px; }
.cs-onb-title { font-size: clamp(38px, 5cqi, 84px); }
.cs-onb-split { align-items: start; display: grid; gap: clamp(28px, 4.5cqi, 80px); grid-template-columns: minmax(260px, 420px) minmax(0, 1fr); }
.cs-onb-steps { align-items: center; color: var(--ui-text-tertiary); display: flex; font: 700 10.5px/1 ${MONO}; gap: 6px; letter-spacing: .14em; margin-left: auto; text-transform: uppercase; }
.cs-onb-steps i { background: var(--ui-stroke-tertiary); display: block; height: 3px; width: 34px; }
.cs-onb-steps i.done { background: var(--ui-green); }
.cs-onb-steps i.cur { background: var(--ui-accent); }
.cs-onb-steps span { margin-left: 10px; white-space: nowrap; }
.cs-onb-facts { background: var(--ui-bg-quaternary); display: grid; gap: 7px 18px; grid-template-columns: max-content minmax(0, 1fr); margin: 0; padding: 14px 16px; }
.cs-onb-facts dt { color: var(--ui-text-tertiary); font-size: 12px; }
.cs-onb-facts dd { color: var(--ui-text-primary); font: 12px ${MONO}; margin: 0; overflow: hidden; text-align: right; text-overflow: ellipsis; white-space: nowrap; }
.cs-onb-facts dd.path { color: var(--ui-text-tertiary); }
.cs-onb-facts dd.good { color: var(--ui-green); }
.cs-onb-facts dd.bad { color: var(--ui-red); }
.cs-dl { border-collapse: collapse; width: 100%; }
.cs-dl th { border-bottom: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-quaternary); font: 700 9.5px/1 ${MONO}; letter-spacing: .12em; padding: 0 12px 9px 0; text-align: left; text-transform: uppercase; }
.cs-dl td { border-bottom: 1px solid var(--ui-stroke-tertiary); padding: 10px 12px 10px 0; vertical-align: top; }
.cs-dl .g { padding-right: 10px; padding-top: 12px; width: 24px; }
.cs-dl td.n { color: var(--ui-text-primary); font-weight: 600; }
.cs-dl td.n .p { color: var(--ui-text-quaternary); display: block; font-size: 11.5px; font-weight: 400; margin-top: 2px; }
.cs-dl td.v, .cs-dl td.s { color: var(--ui-text-tertiary); font: 11.5px/1.6 ${MONO}; }
.cs-dl .z { padding-right: 0; text-align: right; white-space: nowrap; }
.cs-dl td.z { color: var(--ui-text-secondary); font: 11.5px/1.6 ${MONO}; }
.cs-dl td.z.done { color: var(--ui-green); }
.cs-dl td.z.running { color: var(--ui-accent); }
.cs-dl td.z.failed { color: var(--ui-red); }
.cs-dl tr[data-state='pending'] td.n { color: var(--ui-text-tertiary); }
.cs-log { background: var(--ui-bg-quaternary); color: var(--ui-text-tertiary); font: 11.5px/1.75 ${MONO}; overflow-wrap: anywhere; padding: 12px 16px; }
.cs-log .ok { color: var(--ui-green); }
.cs-log .run { color: var(--ui-accent); }
.cs-log .w { color: var(--ui-text-primary); }
.cs-log .bad { color: var(--ui-red); }
.cs-progress { background: var(--ui-stroke-tertiary); height: 4px; overflow: hidden; position: relative; }
.cs-progress > b { background: var(--ui-accent); inset: 0 auto 0 0; position: absolute; transition: width .6s ease; }
.cs-hwcards { display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 440px)); }
.cs-hwcard { align-items: center; appearance: none; background: var(--ui-bg-quaternary); border: 0; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); color: inherit; cursor: pointer; display: flex; font: inherit; gap: 22px; min-height: 190px; padding: 22px; text-align: left; transition: box-shadow .12s; }
.cs-hwcard:hover, .cs-hwcard.primary { box-shadow: inset 0 0 0 1.5px var(--ui-accent); }
.cs-hwcard:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-hwcard .t { color: var(--ui-text-primary); font-size: 28px; }
.cs-hwart { flex: none; height: 140px; width: 78px; }
.cs-hwart.screen { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-accent); display: grid; place-items: center; }
.cs-hwart.device { background: var(--ui-text-secondary); -webkit-mask: var(--cs-fly-body) center / contain no-repeat; mask: var(--cs-fly-body) center / contain no-repeat; }
.cs-idea { background: var(--ui-bg-quaternary); box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: flex; flex-direction: column; gap: 12px; max-width: 760px; padding: 14px 16px; }
.cs-idea:focus-within { box-shadow: inset 0 0 0 1.5px var(--ui-accent); }
.cs-idea textarea { background: transparent; border: 0; color: var(--ui-text-primary); font-family: inherit; font-size: 15px; line-height: 1.5; min-height: 66px; outline: none; padding: 0; resize: vertical; width: 100%; }
.cs-idea textarea::placeholder { color: var(--ui-text-quaternary); }
.cs-ideas { display: flex; flex-wrap: wrap; gap: 8px; }
.cs-ideas button { appearance: none; background: transparent; border: 0; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); cursor: pointer; font: 700 10px/1 ${MONO}; letter-spacing: .1em; padding: 9px 11px; text-transform: uppercase; }
.cs-ideas button:hover { box-shadow: inset 0 0 0 1px var(--ui-accent); color: var(--ui-text-primary); }
.cs-ideas button:disabled { cursor: default; opacity: .5; }
.cs-repair { align-items: center; background: color-mix(in srgb, var(--ui-yellow) 10%, transparent); box-shadow: inset 2px 0 0 var(--ui-yellow); color: var(--ui-text-primary); display: flex; gap: 10px; padding: 9px 14px; }
.cs-repair > i { color: var(--ui-yellow); }
.cs-repair > span { flex: 1; }
@container (max-width: 1000px) {
  .cs-dl .s { display: none; }
}
@container (max-width: 860px) {
  .cs-onb-split, .cs-onb-hero { grid-template-columns: minmax(0, 1fr); }
  .cs-onb-hero .cs-art { display: none; }
  .cs-hwcards { grid-template-columns: minmax(0, 1fr); }
  .cs-onb-steps span { display: none; }
}

/* The flying Chromatic: the body and one wing drawn twice (the left one mirrored), each a 1-bit
   mask painted in the accent colour. Wings beat around the point where they meet the case; the
   whole thing lifts on each downstroke and drifts slowly, tilted like the old winged art. */
.cs-flyer { aspect-ratio: 100 / 108; container-type: inline-size; justify-self: center; margin-top: -6px; max-width: 460px; pointer-events: none; position: relative; width: 100%; }
.cs-flyer .drift, .cs-flyer .lift, .cs-flyer .tilt { inset: 0; position: absolute; }
.cs-flyer .drift { animation: cs-fly-drift 5.4s ease-in-out infinite; }
.cs-flyer .lift { animation: cs-fly-lift .9s ease-in-out infinite; }
.cs-flyer .tilt { transform: perspective(160cqi) translateX(-4cqi) scale(.82) rotateY(-14deg) rotateX(6deg) rotateZ(16deg); transform-style: preserve-3d; }
.cs-flyer .ink { background: var(--ui-accent); inset: 0; position: absolute; -webkit-mask: var(--m) center / 100% 100% no-repeat; mask: var(--m) center / 100% 100% no-repeat; }
.cs-flyer .body { height: 55.9cqi; left: 35cqi; position: absolute; top: 30cqi; width: 30cqi; z-index: 2; }
.cs-flyer .body .ink { --m: var(--cs-fly-body); }
.cs-flyer .wing { height: 41.4cqi; position: absolute; top: 11.6cqi; width: 42cqi; z-index: 1; }
.cs-flyer .wing .ink { --m: var(--cs-fly-wing); }
.cs-flyer .wing.r { animation: cs-flap-r .9s cubic-bezier(.45, 0, .3, 1) infinite; left: 60.7cqi; transform-origin: 3% 87.8%; }
.cs-flyer .wing.l { animation: cs-flap-l .9s cubic-bezier(.45, 0, .3, 1) infinite; left: -2.7cqi; transform-origin: 97% 87.8%; }
.cs-flyer .wing.l .ink { transform: scaleX(-1); }
.cs-flyer .shadow { animation: cs-fly-shadow 5.4s ease-in-out infinite; background: radial-gradient(closest-side, color-mix(in srgb, var(--ui-accent) 38%, transparent), transparent); height: 6cqi; left: 24cqi; position: absolute; top: 98cqi; width: 46cqi; }
@keyframes cs-flap-r { 0%, 100% { transform: rotate(-28deg); } 42% { transform: rotate(20deg) scaleY(.8); } }
@keyframes cs-flap-l { 0%, 100% { transform: rotate(28deg); } 42% { transform: rotate(-20deg) scaleY(.8); } }
@keyframes cs-fly-lift { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-2.4cqi); } }
@keyframes cs-fly-drift { 0%, 100% { transform: translateY(0) rotate(-1.5deg); } 50% { transform: translateY(-7cqi) rotate(1.5deg); } }
@keyframes cs-fly-shadow { 0%, 100% { opacity: .9; transform: scaleX(1); } 50% { opacity: .45; transform: scaleX(.7); } }

/* home: hero, then Continue / Start something / Studio */
.cs-home { display: flex; flex-direction: column; gap: clamp(28px, 3cqi, 48px); }
.cs-hero { align-items: center; display: grid; gap: clamp(24px, 4cqi, 72px); grid-template-columns: minmax(0, 1fr) clamp(150px, 22cqi, 380px); }
.cs-hero > .cs-col { gap: 16px; }
.cs-hero h2 { font-size: clamp(38px, 5cqi, 92px); }
.cs-band { border-top: 1px solid var(--ui-stroke-secondary); display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr) minmax(0, .8fr); }
.cs-band > section { display: flex; flex-direction: column; gap: 14px; min-width: 0; padding: 22px clamp(18px, 2.4cqi, 40px) 8px; }
.cs-band > section:first-child { padding-left: 0; }
.cs-band > section + section { border-left: 1px solid var(--ui-stroke-tertiary); }
.cs-band h3 { margin: 0; }
.cs-cont { align-items: start; display: grid; gap: 18px; grid-template-columns: clamp(120px, 11cqi, 200px) minmax(0, 1fr); }
.cs-cont .name { font: 700 clamp(24px, 2.4cqi, 40px)/.9 ${DISPLAY}; letter-spacing: .03em; margin: 0; overflow-wrap: anywhere; text-transform: uppercase; }
.cs-screen { aspect-ratio: 10 / 9; background: var(--ui-bg-tertiary); display: block; image-rendering: pixelated; object-fit: cover; width: 100%; }
.cs-screen.ph { align-content: center; color: var(--ui-text-quaternary); display: grid; font: 700 10px/1.4 ${MONO}; letter-spacing: .1em; padding: 10px; text-align: center; text-transform: uppercase; }
.cs-quick { display: flex; flex-direction: column; }
.cs-quick button { all: unset; border-top: 1px solid var(--ui-stroke-tertiary); cursor: pointer; display: grid; gap: 2px 12px; grid-template-columns: 1fr auto; padding: 11px 0; }
.cs-quick button:last-child { border-bottom: 1px solid var(--ui-stroke-tertiary); }
.cs-quick .t { color: var(--ui-text-primary); font-weight: 600; }
.cs-quick .d { color: var(--ui-text-tertiary); font-size: 12px; grid-column: 1; }
.cs-quick .a { align-self: center; color: var(--ui-text-quaternary); font: 700 10px ${MONO}; grid-column: 2; grid-row: 1 / span 2; letter-spacing: .12em; text-transform: uppercase; }
.cs-quick button:hover .t, .cs-quick button:hover .a { color: var(--ui-accent); }
.cs-quick button:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-quick button[disabled] { cursor: default; opacity: .45; pointer-events: none; }
.cs-bar7 { display: flex; gap: 3px; }
.cs-bar7 i { background: var(--ui-stroke-secondary); flex: 1; height: 4px; }
.cs-bar7 i.on { background: var(--ui-green); }
.cs-bar7 i.cur { background: var(--ui-accent); }
.cs-stat { display: flex; flex-direction: column; gap: 9px; margin: 0; }
.cs-stat div { display: flex; font-size: 12.5px; gap: 12px; justify-content: space-between; }
.cs-stat dt { color: var(--ui-text-tertiary); }
.cs-stat dd { align-items: center; color: var(--ui-text-primary); display: flex; font: 11.5px ${MONO}; gap: 6px; margin: 0; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-stat dd i { background: var(--ui-text-quaternary); flex: none; height: 6px; width: 6px; }
.cs-stat dd i.good { background: var(--ui-green); }
.cs-stat dd i.warn { background: var(--ui-yellow); }
.cs-stat dd i.bad { background: var(--ui-red); }
.cs-foot { border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; gap: 10px; padding-top: 16px; }

/* prompts: Reader */
.cs-reader { align-items: start; display: grid; gap: clamp(20px, 3.4cqi, 60px); grid-template-columns: clamp(220px, 20cqi, 320px) minmax(0, 1fr) clamp(130px, 18cqi, 300px); }
.cs-rlist { display: flex; flex-direction: column; position: sticky; top: 76px; }
.cs-search { align-items: center; border-bottom: 1px solid var(--ui-stroke-secondary); color: var(--ui-text-quaternary); display: flex; gap: 8px; margin-bottom: 16px; padding: 6px 0; }
.cs-search input { all: unset; color: var(--ui-text-primary); flex: 1; font-size: 13px; min-width: 0; }
.cs-rgrp { color: var(--ui-text-quaternary); display: flex; font: 700 10px/1 ${MONO}; justify-content: space-between; letter-spacing: .14em; padding: 18px 0 6px; text-transform: uppercase; }
.cs-rgrp.first { padding-top: 0; }
.cs-ritem { all: unset; align-items: center; color: var(--ui-text-secondary); cursor: pointer; display: flex; gap: 8px; justify-content: space-between; margin: 0 -8px; padding: 7px 8px; }
.cs-ritem:hover { color: var(--ui-text-primary); }
.cs-ritem:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: -2px; }
.cs-ritem[aria-current] { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); font-weight: 600; }
.cs-ritem.off { color: var(--ui-text-quaternary); }
.cs-rdetail { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.cs-rdetail textarea { background: var(--ui-bg-quaternary); border: 0; color: var(--ui-text-primary); font: 13px/1.65 ${MONO}; min-height: 150px; outline: none; padding: 14px 16px; resize: vertical; width: 100%; }
.cs-rdetail textarea:focus { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-params { align-items: center; display: grid; gap: 10px 16px; grid-template-columns: max-content minmax(0, 420px); }
.cs-params label { color: var(--ui-text-tertiary); font: 700 10px ${MONO}; letter-spacing: .12em; text-transform: uppercase; }
.cs-params input { background: transparent; border: 0; border-bottom: 1px solid var(--ui-stroke-secondary); color: var(--ui-text-primary); font: 12.5px ${MONO}; outline: none; padding: 6px 0; }
.cs-params input:focus { border-bottom-color: var(--ui-accent); }
.cs-uses { border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; gap: 6px; padding-top: 14px; }

/* games: Shelf of real cartridges */
.cs-dev { align-items: center; background: var(--ui-bg-quaternary); display: flex; flex-wrap: wrap; gap: 8px 14px; padding: 11px 14px; }
.cs-dev .dot { background: var(--ui-text-quaternary); flex: none; height: 8px; width: 8px; }
.cs-dev.on .dot { background: var(--ui-green); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-green) 22%, transparent); }
.cs-dev .nm { color: var(--ui-text-primary); font-weight: 600; }
.cs-shelf { display: grid; gap: clamp(18px, 2.2cqi, 36px) clamp(16px, 2cqi, 30px); grid-template-columns: repeat(auto-fill, minmax(min(100%, clamp(200px, 15cqi, 300px)), 1fr)); }
.cs-gcard { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.cs-cart { all: unset; aspect-ratio: 299 / 340; container-type: inline-size; cursor: pointer; display: block; position: relative; transition: transform .16s ease; width: 100%; }
.cs-cart::before { background: var(--cs-cart) center / 100% 100% no-repeat; content: ''; inset: 0; position: absolute; }
.cs-gcard:hover .cs-cart, .cs-cart:focus-visible { transform: translateY(-5px) rotate(-1deg); }
.cs-cart:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 4px; }
.cs-cart .slot { border-radius: 1.5cqw; display: grid; height: 56.76%; left: 13.38%; overflow: hidden; place-items: center; position: absolute; top: 28.82%; width: 73.24%; }
.cs-cart .slot img { display: block; height: 100%; image-rendering: pixelated; object-fit: cover; width: 100%; }
.cs-cart .ph { align-content: center; background: var(--ui-bg-elevated); color: var(--ui-text-tertiary); display: grid; font: 700 5cqw/1.3 ${MONO}; gap: 3cqw; height: 100%; letter-spacing: .06em; padding: 6cqw; text-align: center; text-transform: uppercase; width: 100%; }
.cs-cart .ph small { color: var(--ui-text-quaternary); font-size: 3.6cqw; }
.cs-cart .hov { display: grid; inset: 0; opacity: 0; place-items: center; position: absolute; transition: opacity .15s; }
.cs-gcard:hover .cs-cart .hov, .cs-cart:focus-visible .hov { opacity: 1; }
.cs-cart .hov span { background: var(--ui-accent); border-radius: 50%; color: var(--ui-bg-editor); display: grid; height: 18cqw; place-items: center; width: 18cqw; }
.cs-cart.ghost::before { filter: grayscale(1); opacity: .28; }
.cs-cart.ghost .slot { color: var(--ui-text-secondary); }
.cs-gcard .info { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.cs-gcard h3 { font: 700 20px/1 ${DISPLAY}; letter-spacing: .03em; margin: 0; overflow: hidden; text-overflow: ellipsis; text-transform: uppercase; white-space: nowrap; }
.cs-meta { color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font: 11px ${MONO}; gap: 4px 12px; }
.cs-empty { align-items: start; display: grid; gap: 48px; grid-template-columns: minmax(0, 560px) minmax(0, 1fr); }
.cs-empty > .cs-col { gap: 16px; }
.cs-empty > .cs-art { max-width: 340px; }

/* emulator: bar above ModRetro's real player */
.cs-reload { align-items: center; background: var(--ui-bg-secondary); color: var(--ui-text-primary); display: flex; flex-wrap: wrap; gap: 12px; padding: 10px clamp(12px, 2cqi, 32px); }
.cs-reload .dot { animation: cs-pulse 1.2s ease-in-out infinite; background: var(--ui-accent); flex: none; height: 8px; width: 8px; }
@keyframes cs-pulse { 50% { opacity: .3; } }
.cs-rp-bar { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 6px; padding: 8px clamp(12px, 2cqi, 32px); }
.cs-rp-focus { align-items: center; color: var(--ui-text-quaternary); display: inline-flex; font: 700 9.5px ${MONO}; gap: 6px; letter-spacing: .1em; padding: 0 8px; text-transform: uppercase; }
.cs-rp-focus i { background: var(--ui-text-quaternary); border-radius: 50%; height: 7px; width: 7px; }
.cs-rp-focus.on { color: var(--ui-green); }
.cs-rp-focus.on i { background: var(--ui-green); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-green) 25%, transparent); }
.cs-rp-caps { background: var(--ui-bg-quaternary); border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 12px; overflow-x: auto; padding: 12px clamp(12px, 2cqi, 32px); }
.cs-rp-caps figure { display: flex; flex: none; flex-direction: column; gap: 4px; margin: 0; }
.cs-rp-caps img, .cs-rp-caps video { background: var(--ui-bg-tertiary); height: 120px; image-rendering: pixelated; }
.cs-rp-caps figcaption { color: var(--ui-text-tertiary); font: 10px ${MONO}; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-rp-stage { height: max(560px, calc(100svh - 150px)); position: relative; }
.cs-rp-stage.off { height: 600px; left: -99999px; pointer-events: none; position: absolute; top: 0; visibility: hidden; width: 900px; }
.cs-rp-stage > iframe { border: 0; display: block; height: 100%; width: 100%; }
.cs-rp-stage:fullscreen { background: var(--ui-bg-editor); }
.cs-rp-note { align-items: center; background: var(--ui-bg-secondary); border-left: 2px solid var(--ui-red); display: flex; flex-wrap: wrap; gap: 8px 14px; margin: 10px clamp(12px, 2cqi, 32px) 0; padding: 10px 14px; }
.cs-rp-note > div { display: grid; flex: 1 1 320px; gap: 2px; min-width: 0; }
.cs-rp-note b { color: var(--ui-text-primary); font-size: 13px; }
.cs-rp-note span { color: var(--ui-text-secondary); font-size: 12px; line-height: 1.45; }
.cs-rp-void { background: var(--ui-bg-quaternary); height: 100%; opacity: .5; }
.cs-pad.flush .cs-rp-stage:not(.off) { height: max(500px, calc(100svh - 230px)); }
.cs-rp-foot { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 6px 12px; padding: 6px clamp(12px, 2cqi, 32px); }
.cs-rp-hint { color: var(--ui-text-tertiary); font-size: 12px; }
.cs-side-note { align-items: center; background: var(--ui-bg-secondary); border-bottom: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-secondary); display: flex; font-size: 12px; gap: 8px; line-height: 1.4; padding: 5px clamp(10px, 2cqi, 20px); }
.cs-side-note > i { color: var(--ui-accent); flex: none; }
.cs-side-note-text { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.cs-side-note-x { background: none; border: 0; border-radius: 4px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; flex: none; padding: 2px; }
.cs-side-note-x:hover { color: var(--ui-text-primary); }
.cs-rp-msg.cs-rp-away { justify-items: center; text-align: center; }
.cs-rp-away .cs-eyebrow { justify-content: center; }
.cs-side { height: 100%; min-height: 0; overflow: hidden auto; }
.cs-side .cs-rp-stage { flex: 1 1 auto; height: auto; min-height: 360px; }
.cs-side .cs-rp-bar, .cs-side .cs-reload { padding-left: 10px; padding-right: 10px; }
.cs-side .cs-rp-note { margin: 8px 10px 0; }
.cs-rp-msg { align-content: center; display: grid; gap: 14px; height: 100%; justify-items: start; margin: 0 auto; max-width: 560px; padding: 24px; }

@container (max-width: 1100px) {
  .cs-band { grid-template-columns: 1fr 1fr; }
  .cs-band > section:nth-child(3) { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); grid-column: 1 / -1; padding-left: 0; }
}
@container (max-width: 1000px) {
  .cs-setup { grid-template-columns: clamp(180px, 13cqi, 240px) minmax(0, 1fr); }
  .cs-setup > .cs-flyer { display: none; }
  .cs-reader { grid-template-columns: clamp(200px, 26cqi, 280px) minmax(0, 1fr); }
  .cs-reader > .cs-art { display: none; }
  .cs-empty { grid-template-columns: 1fr; }
  .cs-empty > .cs-art { display: none; }
}
/* Narrow main pane (an emulator tab docked beside it, a small window): the header stays one row.
   The segments tighten, Refresh keeps only its icon, the wordmark goes (Home does the same) and, as
   a last resort, the segments scroll sideways. The player bar stops wrapping the same way and, below
   560px, its buttons keep only their icons (each has a tooltip and an aria-label). */
@container (max-width: 900px) {
  .cs-top { gap: 16px; }
  .cs-seg { min-width: 0; overflow-x: auto; scrollbar-width: none; }
  .cs-seg button { padding: 7px 11px; }
  .cs-top-end { width: auto; }
  .cs-top-end .cs-lbl { display: none; }
}
@container (max-width: 700px) {
  .cs-rp-bar { flex-wrap: nowrap; gap: 2px; overflow-x: auto; scrollbar-width: none; }
}
@container (max-width: 600px) {
  .cs-brand { display: none; }
  .cs-top { gap: 8px; padding-left: 12px; padding-right: 8px; }
  .cs-seg { flex: 1 1 auto; margin: 0; }
  .cs-seg button { flex: 1 0 auto; gap: 5px; justify-content: center; letter-spacing: .06em; padding: 7px 8px; }
}
@container (max-width: 560px) {
  .cs-rp-bar .cs-lbl { display: none; }
  .cs-rp-focus { padding: 0 6px; }
}
@container (max-width: 760px) {
  .cs-setup, .cs-hero, .cs-band, .cs-reader, .cs-page-head { grid-template-columns: 1fr; }
  .cs-rail, .cs-rlist { position: static; }
  .cs-rail-item, .cs-rail-group { display: none; }
  .cs-meter { margin-top: 0; }
  .cs-hero > .cs-art { display: none; }
  .cs-band > section { border-left: 0 !important; border-top: 1px solid var(--ui-stroke-tertiary); padding-left: 0; }
  .cs-choice { grid-template-columns: 1fr; }
  .cs-choice > div + div { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); padding-left: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .cs-lem .run, .cs-glyph .cs-dash, .cs-reload .dot, .cs-flyer * { animation: none !important; }
  .cs-flyer .wing.r { transform: rotate(-10deg); }
  .cs-flyer .wing.l { transform: rotate(10deg); }
  .cs-cart { transition: none; }
}
`

function PageStyle() {
  return jsx('style', { children: CSS })
}

// ── Data ──────────────────────────────────────────────────────────────────────

/** A rejected `host.request` (backend not loaded, unknown method, gateway down). */
function describeRequestError(error) {
  const message = String(error?.message ?? error ?? '')
  const notLoaded = error?.code === -32601 || /-32601|unknown method|method not found/i.test(message)

  return { message, notLoaded }
}

// The page is app-wide, the plugin's backend is per profile. When the profile the app is on
// does not have it, use a profile that does (without switching the app to it) and send
// "Use in chat" prompts to that profile.
// `studio` is set when the route is the dedicated hermretro profile: it is then preferred
// over the profile the app is on, even when that one has the plugin too.
const routing = { route: null, profile: null, scannedAt: 0, studio: false }
const ROUTE_SCAN_EVERY_MS = 30_000

function routeProfile(route) {
  return typeof route === 'string' ? route : (route?.targetProfile ?? route?.profile ?? null)
}

async function findRoute() {
  if (typeof host.profileRoutes !== 'function' || typeof host.requestProfile !== 'function') {
    return null
  }

  let active = null

  try {
    active = host.state.profile?.get?.() ?? null
  } catch {
    active = null
  }

  const routes = [...((await host.profileRoutes().catch(() => [])) ?? [])]

  // The dedicated profile first, when there is one.
  routes.sort((a, b) => Number(routeProfile(b) === STUDIO_PROFILE) - Number(routeProfile(a) === STUDIO_PROFILE))

  for (const route of routes) {
    if (route?.profile === active) {
      continue // already asked, through the ambient connection
    }

    try {
      const data = await host.requestProfile(route, RPC_STATUS, {})

      if (data && typeof data === 'object' && 'ok' in data) {
        return { route }
      }
    } catch {
      // not on in that profile, or its backend is not reachable right now
    }
  }

  return null
}

/** Point the page at the dedicated hermretro profile, once it exists and answers. */
async function adoptStudioRoute() {
  if (typeof host.profileRoutes !== 'function' || typeof host.requestProfile !== 'function') {
    return null
  }

  const routes = (await host.profileRoutes().catch(() => [])) ?? []
  const route = routes.find(candidate => routeProfile(candidate) === STUDIO_PROFILE)

  if (!route) {
    return null
  }

  try {
    const data = await host.requestProfile(route, RPC_STATUS, {})

    if (data?.ok && data.profile?.is_studio) {
      routing.route = route
      routing.profile = STUDIO_PROFILE
      routing.studio = true

      return data
    }
  } catch {
    // created, but its backend is not up yet: asked again on the next poll
  }

  return null
}

/** Call the plugin's backend: in the hermretro profile when there is one, else in the
 *  profile the app is on, else in any profile that has it. */
async function callBackend(method, params = {}, timeoutMs) {
  if (routing.studio && routing.route) {
    try {
      return { data: await host.requestProfile(routing.route, method, params, timeoutMs), profile: routing.profile }
    } catch (error) {
      if (!describeRequestError(error).notLoaded) {
        throw error
      }

      routing.route = null
      routing.profile = null
      routing.studio = false
    }
  }

  try {
    const data = await host.request(method, params, timeoutMs)

    routing.route = null
    routing.profile = null

    return { data, profile: null }
  } catch (error) {
    if (!describeRequestError(error).notLoaded) {
      throw error
    }

    // Asking every profile is not free: do it on open and on Refresh, then only now and again.
    if (!routing.route && Date.now() - routing.scannedAt >= ROUTE_SCAN_EVERY_MS) {
      routing.scannedAt = Date.now()

      const found = await findRoute()

      if (found) {
        routing.route = found.route
        routing.profile = routeProfile(found.route)
        routing.studio = routing.profile === STUDIO_PROFILE
      }
    }

    if (!routing.route) {
      throw error
    }

    try {
      return { data: await host.requestProfile(routing.route, method, params, timeoutMs), profile: routing.profile }
    } catch (inner) {
      if (describeRequestError(inner).notLoaded) {
        routing.route = null
        routing.profile = null
      }

      throw inner
    }
  }
}

async function fetchStatus(sessionId) {
  // `chat` only picks which conversation's project to report. It is deliberately not sent as
  // `session_id`: the gateway treats that as a session to authorize and rejects the whole call
  // (not_found) for a chat that has no live session yet, such as a new draft.
  const { data, profile } = await callBackend(RPC_STATUS, sessionId ? { chat: sessionId } : {})

  // Answered by the profile the plugin was installed into, and the dedicated profile has since
  // been made: move over to it.
  if (data?.ok && data.profile && !data.profile.is_studio && data.profile.studio?.installed && !routing.studio) {
    const studio = await adoptStudioRoute()

    if (studio) {
      return { ...studio, via_profile: STUDIO_PROFILE }
    }
  }

  return profile ? { ...data, via_profile: profile } : data
}

async function fetchDoctor() {
  return (await callBackend(RPC_DOCTOR, {}, 60_000)).data
}

async function fetchActivity(chat, stored) {
  const params = { chat: chat ?? undefined, stored: stored ?? undefined }
  const { data, profile } = await callBackend(RPC_ACTIVITY, params)

  // A chat that lives in the profile the app is on (not the studio profile) is known only to
  // that profile's backend.
  if (routing.studio && data?.matched !== 'chat') {
    try {
      const here = await host.request(RPC_ACTIVITY, params)

      if (here?.matched === 'chat') {
        return here
      }
    } catch {
      // the plugin is not on in this profile
    }
  }

  return profile ? { ...data, via_profile: profile } : data
}

function useBackend({ fast, pollDoctor }) {
  const gateway = useValue(host.state.gateway)
  const sessionId = useValue(host.state.focusedSessionId)
  const connected = gateway === 'open'

  const status = useQuery({
    queryKey: [ID, 'status', sessionId ?? null],
    queryFn: () => fetchStatus(sessionId),
    enabled: connected,
    // Cheap and passive. Poll quickly during setup so a finished step is noticed at once.
    refetchInterval: fast ? 4_000 : 30_000,
    staleTime: 2_000,
    retry: false
  })

  const statusOk = Boolean(status.data?.ok)

  // Doctor reads tool metadata on disk: run it when the page mounts and on Refresh, and
  // repeat it only while the toolchain step is the one waiting to complete.
  const doctor = useQuery({
    queryKey: [ID, 'doctor', status.data?.via_profile ?? null],
    queryFn: fetchDoctor,
    enabled: connected && statusOk,
    staleTime: Infinity,
    refetchInterval: pollDoctor ? 8_000 : false,
    refetchOnMount: 'always',
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
    retry: false
  })

  let backend = 'checking'

  if (!connected) {
    backend = 'offline'
  } else if (status.isError) {
    // Not loaded in any profile, versus loaded but the call itself failed.
    backend = describeRequestError(status.error).notLoaded ? 'unavailable' : 'failed'
  } else if (status.data && !status.data.ok) {
    backend = 'error'
  } else if (statusOk) {
    backend = 'ok'
  }

  return { backend, connected, doctor, gateway, status }
}

function nodeState(node) {
  if (!node) {
    return { ok: false, label: 'Unknown' }
  }

  const required = parseInt(String(node.required ?? '22'), 10) || 22
  const major = parseInt(String(node.version ?? '').replace(/^v/i, ''), 10)
  const ok = Boolean(node.found) && Number.isFinite(major) && major >= required

  return { ok, required, version: node.found ? node.version : null }
}

// ── "Use in chat" ─────────────────────────────────────────────────────────────

async function insertText(target, text) {
  try {
    return (await host.composer.insertText(target, text, { mode: 'block' })) === true
  } catch {
    return false
  }
}

/** A freshly opened chat needs a beat to mount its composer. */
async function insertWhenMounted(ctx, target, text) {
  const sleep = ms => new Promise(resolve => ctx.setTimeout(resolve, ms))

  for (const delay of [150, 250, 400, 600, 900]) {
    await sleep(delay)

    if (await insertText(target, text)) {
      return true
    }
  }

  return false
}

const promptAdded = () => host.notify({ kind: 'success', message: 'Prompt added to the composer' })

/** Put a prompt into a chat composer without sending it. Order: the composer
 *  the user is in → the focused chat's composer → a fresh chat → clipboard.
 *  `fresh` skips straight to a new chat ("Start a new chat"). */
async function sendPromptToChat(ctx, prompt, { fresh = false } = {}) {
  // Set when the plugin lives in another profile: only a chat in that profile has its tools.
  const profile = routing.profile

  if (!profile && !fresh) {
    if (await insertText(null, prompt)) {
      promptAdded()

      return
    }

    const focused = host.state.focusedSessionId.get()

    if (focused && (await insertText(focused, prompt))) {
      promptAdded()

      return
    }
  }

  if (typeof host.newChat === 'function') {
    try {
      profile ? host.newChat(profile) : host.newChat()

      if (await insertWhenMounted(ctx, 'new', prompt)) {
        promptAdded()

        return
      }
    } catch {
      // fall through to the clipboard
    }
  }

  const copied = await ctx.os.writeClipboard(prompt).catch(() => false)

  host.notify(
    copied
      ? { kind: 'info', message: 'Prompt copied — paste it into a chat to use it.' }
      : { kind: 'warning', message: 'Could not reach a chat composer or the clipboard. Copy the prompt from the page.' }
  )
}

/** Open the chat a game was made in (from the games registry). */
async function openGameChat(game) {
  const stored = game?.chat?.sessionId

  if (!stored || typeof host.openSession !== 'function') {
    return false
  }

  try {
    await host.openSession(stored, routing.profile ? { profile: routing.profile } : {})

    return true
  } catch {
    return false
  }
}

/** Text about one game goes into that game's own chat (opened, not sent); without one, into a
 *  hermretro chat the same way as any prompt. */
async function sendToGameChat(ctx, game, text) {
  if ((await openGameChat(game)) && (await insertWhenMounted(ctx, null, text))) {
    promptAdded()

    return
  }

  await sendPromptToChat(ctx, text)
}

// ── Games, the player and captures (contract: docs/dev/STUDIO-PAGES.md) ───────

/** The newer studio RPCs go to the backend that answered `status`, without a profile scan: a
 *  backend that predates them answers -32601, which the pages report as "needs an update". */
async function callStudio(method, params = {}, timeoutMs) {
  return routing.route ? host.requestProfile(routing.route, method, params, timeoutMs) : host.request(method, params, timeoutMs)
}

function studioError(error, what) {
  const { message, notLoaded } = describeRequestError(error)

  return notLoaded
    ? `This hermretro backend cannot ${what} yet. Update the plugin in the profile it runs in, then press Refresh.`
    : message || 'Unknown error'
}

const KIND_LABELS = { gbstudio: 'GB Studio', gbdk: 'GBDK' }
const GAME_STATES = {
  ready: ['good', 'Ready'],
  changed: ['warn', 'Changed since last build'],
  failed: ['bad', 'Build failed'],
  unbuilt: ['quiet', 'Not built yet']
}

function gameMeta(game, now = Date.now()) {
  return [
    KIND_LABELS[game.kind] ?? game.kind ?? null,
    game.rom?.size ? `${Math.max(1, Math.round(game.rom.size / 1024))} KB` : null,
    game.rom?.builtAt ? `built ${ago(game.rom.builtAt, now)}` : 'never built'
  ].filter(Boolean)
}

/** The game to show first: the most recently built one that the player can run. */
function latestGame(games) {
  const list = [...(games ?? [])].sort((a, b) => (b.rom?.builtAt ?? 0) - (a.rom?.builtAt ?? 0))

  return list.find(game => game.webExport) ?? list[0] ?? null
}

const gameLabel = game => `"${game.title}"${game.projectRoot ? ` (${game.projectRoot})` : ''}`

function installPrompt(game) {
  return FLASH_PROMPT.replace('my built homebrew ROM', `the built ROM of ${gameLabel(game)}`)
}

function fixPrompt(game) {
  return `The last build of ${gameLabel(game)} failed${game.error ? `:\n${game.error}\n` : '. '}Find the cause, fix it, rebuild, and show me the result.`
}

function buildPrompt(game) {
  return `Build ${gameLabel(game)} and its playable web player, so I can play it on the Emulator page of hermretro.`
}

/** Draw a frame at the Game Boy's own size, so a title screen stays small (the RPC takes ≤ 64 KB). */
function shrinkFrame(dataUrl) {
  return new Promise(resolve => {
    try {
      const image = new Image()

      image.onload = () => {
        try {
          const canvas = document.createElement('canvas')

          canvas.width = 160
          canvas.height = 144

          const g = canvas.getContext('2d')

          g.imageSmoothingEnabled = false
          g.drawImage(image, 0, 0, 160, 144)

          // A blank (single-colour) frame is not a title screen yet.
          const pixels = g.getImageData(0, 0, 160, 144).data
          let varied = false

          for (let i = 4; i < pixels.length && !varied; i += 4) {
            varied = pixels[i] !== pixels[0] || pixels[i + 1] !== pixels[1] || pixels[i + 2] !== pixels[2]
          }

          resolve(varied ? canvas.toDataURL('image/png') : '')
        } catch {
          resolve('')
        }
      }

      image.onerror = () => resolve('')
      image.src = dataUrl
    } catch {
      resolve('')
    }
  })
}

// ── Small pieces ──────────────────────────────────────────────────────────────

const INDICATOR = {
  done: { icon: 'pass-filled', color: C.good, label: 'Done' },
  todo: { icon: 'circle-large-outline', color: C.warn, label: 'To do' },
  optional: { icon: 'circle-large-outline', color: C.quaternary, label: 'Optional' },
  waiting: { icon: 'circle-large-outline', color: C.quaternary, label: 'Waiting' },
  checking: { icon: 'loading', color: C.tertiary, label: 'Checking', spinning: true },
  error: { icon: 'error', color: C.bad, label: 'Problem' },
  skipped: { icon: 'dash', color: C.quaternary, label: 'Skipped' },
  blocked: { icon: 'circle-slash', color: C.warn, label: 'Not available' }
}

function StateIcon({ state }) {
  const spec = INDICATOR[state] ?? INDICATOR.waiting

  return jsx(Tip, {
    label: spec.label,
    children: jsx('span', {
      'aria-label': spec.label,
      role: 'img',
      style: { color: spec.color, display: 'inline-flex', flexShrink: 0, lineHeight: 1, paddingTop: 1 },
      children: jsx(Codicon, { name: spec.icon, size: 16, spinning: spec.spinning })
    })
  })
}

function ExternalLink({ ctx, href, children, variant = 'link' }) {
  return jsxs(Button, {
    onClick: () => void ctx.os.openExternal(href),
    size: variant === 'link' ? 'inline' : 'sm',
    variant,
    children: [children, jsx(Codicon, { name: 'link-external', size: 12 })]
  })
}

function CommandLine({ command }) {
  return jsxs('div', {
    style: { ...S.row, gap: 4 },
    children: [
      jsx('code', { className: 'font-mono', style: S.code, children: command }),
      jsx(CopyButton, { appearance: 'icon', label: 'Copy command', text: command })
    ]
  })
}

// ── Header ────────────────────────────────────────────────────────────────────

const LEMNISCATE = 'M0 0C.35-.6 1.15-.6 1.15 0S.35.6 0 0-1.15-.6-1.15 0-.35.6 0 0Z'

/** The long-operation loader, after the app's own lemniscate. */
function Working({ children, quiet = false }) {
  return jsxs('div', {
    className: quiet ? 'cs-watch quiet' : 'cs-watch',
    role: 'status',
    children: [
      jsxs('svg', {
        'aria-hidden': true,
        className: 'cs-lem',
        viewBox: '-1.25 -0.62 2.5 1.24',
        children: [
          jsx('path', { className: 'track', d: LEMNISCATE, pathLength: 100 }),
          jsx('path', { className: 'run', d: LEMNISCATE, pathLength: 100 })
        ]
      }),
      jsx('span', { children })
    ]
  })
}

/** A step's state as a small square: filled when done, dashed while checking. */
function Glyph({ state }) {
  const label = (INDICATOR[state] ?? INDICATOR.waiting).label
  const ink = 'var(--background, var(--ui-bg-editor))'
  let shape

  if (state === 'done') {
    shape = [
      jsx('rect', { fill: C.good, height: 12, width: 12, x: 1, y: 1 }, 'box'),
      jsx('path', { d: 'M4 7.2l2 2 4-4.4', fill: 'none', stroke: ink, strokeWidth: 1.6 }, 'tick')
    ]
  } else if (state === 'error') {
    shape = [
      jsx('rect', { fill: C.bad, height: 12, width: 12, x: 1, y: 1 }, 'box'),
      jsx('path', { d: 'M7 4v4M7 9.6v.8', stroke: ink, strokeWidth: 1.6 }, 'mark')
    ]
  } else if (state === 'checking') {
    shape = jsx('rect', {
      className: 'cs-dash',
      fill: 'none',
      height: 11,
      stroke: 'var(--ui-accent)',
      strokeDasharray: '3 2',
      strokeWidth: 1.4,
      width: 11,
      x: 1.5,
      y: 1.5
    })
  } else if (state === 'skipped') {
    shape = jsx('path', { d: 'M3 7h8', stroke: C.quaternary, strokeWidth: 1.4 })
  } else {
    shape = [
      jsx('rect', {
        fill: 'none',
        height: 11,
        stroke: state === 'blocked' ? C.warn : state === 'todo' ? C.tertiary : C.quaternary,
        strokeWidth: 1.2,
        width: 11,
        x: 1.5,
        y: 1.5
      }, 'box'),
      state === 'blocked' ? jsx('path', { d: 'M4 10l6-6', stroke: C.warn, strokeWidth: 1.2 }, 'slash') : null
    ]
  }

  return jsx('svg', { 'aria-label': label, className: 'cs-glyph', height: 14, role: 'img', viewBox: '0 0 14 14', width: 14, children: shape })
}

/** The Hermes bust (Home, Prompts, empty pages). The image itself is a CSS variable on the page. */
function Art() {
  return jsx('div', { 'aria-hidden': true, className: 'cs-art' })
}

/** The flying Chromatic beside every Setup step. Kept mounted by the Setup page, so a status poll
 *  never restarts its animation. */
function Flyer() {
  const wing = side => jsx('div', { className: `wing ${side}`, children: jsx('div', { className: 'ink' }) }, side)

  return jsxs('div', {
    'aria-hidden': true,
    className: 'cs-flyer',
    children: [
      jsx('div', {
        className: 'drift',
        children: jsx('div', {
          className: 'lift',
          children: jsxs('div', {
            className: 'tilt',
            children: [wing('l'), wing('r'), jsx('div', { className: 'body', children: jsx('div', { className: 'ink' }) }, 'body')]
          })
        })
      }),
      jsx('div', { className: 'shadow' })
    ]
  })
}

function Chip({ tone = '', children }) {
  return jsxs('span', { className: `cs-chip ${tone}`, children: [jsx('i', {}), children] })
}

const PAGES = [
  ['home', 'Home'],
  ['setup', 'Setup'],
  ['prompts', 'Prompts'],
  ['games', 'Games'],
  ['emulator', 'Emulator']
]

/** Wordmark, one segmented control (always in the same place) and Refresh. */
function StudioNav({ page, onGo, setupPending, playing, onRefresh, refreshing }) {
  return jsxs('header', {
    className: 'cs-top',
    children: [
      jsxs('button', {
        'aria-label': 'hermretro home',
        className: 'cs-brand',
        onClick: () => onGo('home'),
        type: 'button',
        children: ['herm', jsx('span', { children: 'retro' })]
      }),
      jsx('nav', {
        'aria-label': 'Studio pages',
        className: 'cs-seg',
        children: PAGES.map(([id, label]) =>
          jsxs(
            'button',
            {
              'aria-current': page === id ? 'page' : undefined,
              onClick: () => onGo(id),
              type: 'button',
              children: [
                label,
                id === 'setup' && setupPending ? jsx('i', { 'aria-label': 'setup is not finished', className: 'pip', role: 'img' }) : null,
                id === 'emulator' && playing && page !== 'emulator' ? jsx('i', { 'aria-label': 'a game is loaded', className: 'live', role: 'img' }) : null
              ]
            },
            id
          )
        )
      }),
      jsx('div', {
        className: 'cs-top-end',
        children: jsx(Tip, {
          label: 'Check the setup and reload the studio',
          children: jsx('span', {
            style: { display: 'inline-flex' },
            children: jsxs(Button, {
              'aria-label': 'Refresh',
              disabled: refreshing,
              onClick: onRefresh,
              size: 'sm',
              variant: 'ghost',
              children: [jsx(Codicon, { name: 'refresh', size: 14, spinning: refreshing }), jsx('span', { className: 'cs-lbl', children: 'Refresh' })]
            })
          })
        })
      })
    ]
  })
}

// ── Setup wizard ──────────────────────────────────────────────────────────────
// One step per page. The page shown is always the first step that is not complete
// yet, so finishing a step (detected from the backend) moves the page on by itself.

const HARDWARE_STEPS = ['firmware', 'devmode', 'devicecli', 'hardware']
// Node.js is not a step: Hermes installs its own, which the backend finds. A missing one blocks the
// toolchain step instead.
const STEP_ORDER = ['profile', 'toolchain', ...HARDWARE_STEPS]

const STEP_TITLES = {
  profile: 'Create the hermretro profile',
  toolchain: 'Install the game toolchain',
  firmware: 'Update your Chromatic',
  devmode: 'Activate Developer Mode',
  devicecli: "Install ModRetro's device software",
  hardware: 'Turn on hardware tools'
}

// Steps done outside Hermes cannot be detected; the user confirms them.
const MANUAL_STEPS = { firmware: 'firmwareDone', devmode: 'devmodeDone' }

function useSetupMemory(ctx) {
  const [memory, setMemory] = useState(() => {
    try {
      return { ...(ctx.storage.get('setup', {}) ?? {}) }
    } catch {
      return {}
    }
  })

  const update = patch =>
    setMemory(previous => {
      const next = { ...previous, ...patch }

      try {
        ctx.storage.set('setup', next)
      } catch {
        // not persisted; still applies for this visit
      }

      return next
    })

  return [memory, update]
}

/** The studio profile only exists before onboarding for someone who set up with the older Setup page;
 *  count that as an existing setup once the tools have been checked at all. */
function toolchainStateKnown(status, doctor) {
  return Boolean(status.data?.ok) && (Boolean(doctor.data) || doctor.isError)
}

function toolchainState(data, doctor) {
  const report = doctor.data
  const engine = data.engine ?? {}

  if (doctor.isError || (report && !report.ok)) {
    return 'error'
  }

  if (!report) {
    return 'checking'
  }

  return (report.missing_required ?? []).length || !engine.present || engine.verified === false ? 'todo' : 'done'
}

function computeSteps({ backend, status, doctor, memory }) {
  const data = backend === 'ok' ? status.data : null
  const cli = data?.deps?.device_cli

  const states = {
    // A backend that says nothing about profiles predates this step and cannot make one.
    profile: !data ? 'waiting' : !data.profile || data.profile.is_studio ? 'done' : 'todo',
    toolchain: !data ? 'waiting' : nodeState(data.node).ok ? toolchainState(data, doctor) : 'blocked',
    firmware: memory.firmwareDone ? 'done' : 'todo',
    devmode: memory.devmodeDone ? 'done' : 'todo',
    devicecli: !cli
      ? 'waiting'
      : cli.state === 'installed' || cli.state === 'bundled'
        ? 'done'
        : cli.state === 'unsupported'
          ? 'blocked'
          : 'todo',
    hardware: !data ? 'waiting' : data.hardware_enabled ? 'done' : 'todo'
  }

  return STEP_ORDER.map(id => {
    const hardware = HARDWARE_STEPS.includes(id)
    const state = hardware && memory.hardwareSkipped && states[id] !== 'done' ? 'skipped' : states[id]

    return {
      id,
      title: STEP_TITLES[id],
      hardware,
      manual: id in MANUAL_STEPS,
      state,
      complete: state === 'done' || state === 'skipped'
    }
  })
}

const COMPONENT_STATUS = { ready: 'Ready', missing: 'Missing', incompatible: 'Incompatible', unknown: 'Unknown' }

function ComponentRow({ component }) {
  const status = component.optional && component.status !== 'ready' ? 'optional' : (component.status ?? 'unknown')
  const versions = [
    component.required ? `needs ${component.required}` : null,
    component.detected ? `found ${component.detected}` : component.status === 'missing' ? 'not found' : null
  ]
    .filter(Boolean)
    .join(' · ')

  return jsxs('div', {
    className: 'cs-comp',
    children: [
      jsx(Glyph, { state: component.status === 'ready' ? 'done' : component.status === 'incompatible' ? 'error' : 'todo' }),
      jsxs('span', {
        className: 'name',
        children: [component.label ?? component.id, component.optional ? jsx('small', { children: 'optional' }) : null]
      }),
      jsx('span', { className: 'ver', children: versions }),
      jsx('span', { className: `st ${status}`, children: status === 'optional' ? 'Optional' : COMPONENT_STATUS[status] ?? 'Unknown' }),
      component.detail ? jsx('span', { className: 'detail', children: component.detail }) : null
    ]
  })
}

function PromptActions({ ctx, prompt, primaryLabel = 'Use in chat', primaryVariant = 'secondary' }) {
  const [pending, setPending] = useState(false)

  const run = async () => {
    if (pending) {
      return
    }

    setPending(true)

    try {
      await sendPromptToChat(ctx, prompt)
    } finally {
      setPending(false)
    }
  }

  return jsxs('div', {
    className: 'cs-actions',
    children: [
      jsxs(Button, {
        disabled: pending,
        onClick: () => void run(),
        size: 'sm',
        variant: primaryVariant,
        children: [jsx(Codicon, { name: pending ? 'loading' : 'comment-discussion', size: 14, spinning: pending }), primaryLabel]
      }),
      jsx(CopyButton, { buttonSize: 'sm', buttonVariant: 'outline', label: 'Copy', text: prompt })
    ]
  })
}

/** A prompt shown in full, with the buttons that use it. */
function PromptBlock({ ctx, prompt, label }) {
  return jsxs('div', {
    className: 'cs-col',
    style: { gap: 10 },
    children: [jsx('p', { className: 'cs-prompt', children: prompt }), jsx(PromptActions, { ctx, primaryLabel: label, primaryVariant: 'default', prompt })]
  })
}

function Lede({ children }) {
  return jsx('p', { className: 'cs-lede', children })
}

function Small({ children, tone }) {
  return jsx('p', { className: tone === 'warn' ? 'cs-small cs-warn' : 'cs-small', children })
}

function Facts({ rows }) {
  return jsx('dl', {
    className: 'cs-facts',
    children: rows.flatMap(([term, text]) => [jsx('dt', { children: term }, `t-${term}`), jsx('dd', { children: text }, `d-${term}`)])
  })
}

/** Shown instead of the setup steps while the plugin's backend cannot be reached. Normally
 *  never seen: switching the plugin on in Capabilities turns on the page and the backend. */
function NotRunning({ backend, status, gateway }) {
  let title = 'Checking hermretro…'
  let body = jsx(Working, { children: 'Asking the plugin for its status.' })

  if (backend === 'offline') {
    title = 'Waiting for Hermes'
    body = jsx(Working, { children: `The connection to Hermes is ${gateway || 'idle'}. This page continues by itself.` })
  } else if (backend === 'error') {
    title = 'hermretro reported a problem'
    body = jsx('pre', { className: 'cs-error', children: status.data?.error || 'Unknown error' })
  } else if (backend === 'failed') {
    title = 'Could not read hermretro\'s status'
    body = jsxs('div', {
      className: 'cs-content',
      children: [
        jsx(Lede, { children: 'The plugin is on, but its status request failed. Press Refresh; if this stays, report the message below.' }),
        jsx('pre', { className: 'cs-error', children: describeRequestError(status.error).message || 'Unknown error' })
      ]
    })
  } else if (backend === 'unavailable') {
    const { message, notLoaded } = describeRequestError(status.error)

    title = 'hermretro is not switched on in any profile'
    body = jsxs('div', {
      className: 'cs-content',
      children: [
        jsx(Lede, {
          children:
            'This page is visible, but the part of the plugin that does the work is off. Switch hermretro on in Capabilities → Plugins for the profile you want to use it in. This page continues by itself once it is on.'
        }),
        jsx('div', {
          className: 'cs-actions',
          children: jsxs(Button, {
            onClick: () => host.navigate(PLUGINS_HREF),
            size: 'sm',
            variant: 'default',
            children: [jsx(Codicon, { name: 'extensions', size: 14 }), 'Open Capabilities → Plugins']
          })
        }),
        jsxs('div', {
          className: 'cs-col',
          style: { gap: 6 },
          children: [jsx('span', { className: 'cs-faint', children: 'Or, from a terminal:' }), jsx(CommandLine, { command: ENABLE_COMMAND })]
        }),
        !notLoaded && message ? jsx('span', { className: 'cs-faint', children: `Details: ${message}` }) : null
      ]
    })
  }

  return jsx('section', {
    'aria-live': 'polite',
    className: 'cs-stage',
    style: { maxWidth: 860 },
    children: jsxs('div', {
      className: 'cs-stage',
      style: { display: 'contents' },
      children: [
        jsxs('div', {
          className: 'cs-stage-head',
          children: [jsx('p', { className: 'cs-eyebrow', children: 'Status' }), jsx('h2', { className: 'cs-word cs-title', children: title })]
        }),
        body
      ]
    })
  })
}

const PROFILE_FACTS = [
  ['Sign-in', 'It uses your existing sign-in and keys, so there is nothing to log in to again.'],
  ['Skills', 'hermretro and its six skills are turned on there, with a game-developer persona.'],
  ['Tools', 'Text-to-speech, app connections, computer use and scheduled jobs are turned off there. Everything else keeps the Hermes defaults.'],
  ['Approvals', 'Kept on (smart mode), so installing device software and anything that touches your Chromatic goes through an approval check.']
]

function ProfileBody({ status }) {
  const profile = status.data?.profile
  const [working, setWorking] = useState(false)
  const [failure, setFailure] = useState(null)

  if (!status.data?.ok || !profile) {
    return jsx(Small, { children: 'Checked once the plugin is on.' })
  }

  if (profile.is_studio) {
    return jsx(Lede, { children: `hermretro has its own profile, "${profile.name}". Its chats open there.` })
  }

  const create = async () => {
    if (working) {
      return
    }

    setWorking(true)
    setFailure(null)

    try {
      await createStudioProfileOnce(profile)
      host.notify({ kind: 'success', message: 'hermretro profile created' })
      status.refetch?.()
    } catch (error) {
      setFailure(String(error?.message ?? error))
    } finally {
      setWorking(false)
    }
  }

  const starting = profile.studio?.installed && !working

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          'hermretro works in its own Hermes profile, so it has exactly the tools and skills game development needs, and your other chats stay as they are.'
      }),
      jsx(Facts, { rows: PROFILE_FACTS }),
      starting
        ? jsxs('div', {
            className: 'cs-col',
            children: [
              jsx(Working, { children: 'The profile is created. Waiting for Hermes to start it…' }),
              jsx('div', {
                children: jsx(Button, { disabled: working, onClick: create, size: 'sm', variant: 'ghost', children: 'Set it up again' })
              })
            ]
          })
        : working
          ? jsx(Working, { children: 'Creating the profile…' })
          : jsxs('div', {
              className: 'cs-actions',
              children: [
                jsx(Button, { onClick: create, size: 'sm', variant: 'default', children: 'Create the hermretro profile' }),
                jsx('span', { className: 'cs-faint', children: `The "${profile.name}" profile, where the plugin is installed, is not changed.` })
              ]
            }),
      failure ? jsx('p', { className: 'cs-error', children: failure }) : null
    ]
  })
}

// ── Toolchain install (driven by the page, no chat) ──────────────────────────
// The backend runs the engine's own toolchain_prepare in the broker and reports per-component
// progress (RPC `install`). The page lists every download before anything starts.

const ONBOARD_STAGES = [
  ['install', 'Install'],
  ['chromatic', 'Your hardware'],
  ['make', 'First game']
]

function formatBytes(bytes, approx = false) {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return ''
  }

  const mb = bytes / 1e6
  const text = mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : mb >= 100 ? `${Math.round(mb)} MB` : `${mb.toFixed(1)} MB`

  return approx ? `≈ ${text}` : text
}

async function fetchInstall() {
  return (await callBackend(RPC_INSTALL, { action: 'status' }, 30_000)).data
}

const installInterval = arg => ((arg?.state ? arg.state.data : arg)?.install?.state === 'running' ? 1_500 : 5_000)

/** The install's status: polled quickly while it runs, slowly otherwise. */
function useInstall({ enabled }) {
  return useQuery({
    queryKey: [ID, 'install'],
    queryFn: fetchInstall,
    enabled,
    refetchInterval: enabled ? installInterval : false,
    staleTime: 1_000,
    retry: false
  })
}

/** Hermes creates the profile; the plugin then makes it a hermretro one. */
async function createStudioProfile(profile) {
  if (!profile.studio?.exists) {
    await host.request('profiles.create', profile.create)
  }

  const { data } = await callBackend(RPC_STUDIO_PROFILE, {}, 240_000)

  if (!data?.ok) {
    throw new Error(data?.error || 'The profile could not be set up.')
  }
}

// One profile creation at a time, whether started by the install or the Setup page's own button.
let profileCreation = null

function createStudioProfileOnce(profile) {
  profileCreation ??= createStudioProfile(profile).finally(() => {
    profileCreation = null
  })

  return profileCreation
}

/** Everything one install view needs: phase, rows, actions. Shared by onboarding and the Setup step. */
function useInstaller({ ctx, status, install, toolchainDone }) {
  const [starting, setStarting] = useState(false)
  const [failure, setFailure] = useState(null)
  const [profileWork, setProfileWork] = useState({ state: 'idle', error: null })
  // A chat is already preparing the tools: wait for it instead of reporting a failure.
  const [elsewhere, setElsewhere] = useState(false)
  const data = install.data
  const unsupported = install.isError && describeRequestError(install.error).notLoaded
  const state = data?.install?.state ?? 'idle'
  const profile = status.data?.profile
  const needsProfile = Boolean(profile && !profile.is_studio && !profile.studio?.installed)
  const node = nodeState(status.data?.node)

  const makeProfile = () => {
    if (!needsProfile) {
      return
    }

    setProfileWork({ state: 'running', error: null })
    createStudioProfileOnce(profile).then(
      () => {
        setProfileWork({ state: 'done', error: null })
        status.refetch?.()
      },
      error => setProfileWork({ state: 'failed', error: String(error?.message ?? error) })
    )
  }

  const start = async () => {
    if (starting) {
      return
    }

    setStarting(true)
    setFailure(null)
    // The profile is made while the tools download.
    makeProfile()

    try {
      const { data: answer } = await callBackend(RPC_INSTALL, { action: 'start' }, 60_000)

      if (answer?.code === 'OPERATION_IN_PROGRESS') {
        setElsewhere(true)

        return
      }

      if (!answer?.ok) {
        throw new Error(answer?.error || 'The install could not start.')
      }

      setElsewhere(false)
      await install.refetch?.()
    } catch (error) {
      setFailure(describeRequestError(error).message || String(error?.message ?? error))
    } finally {
      setStarting(false)
    }
  }

  const ask = () =>
    sendPromptToChat(
      ctx,
      `${SETUP_PROMPT}\n\nThe install on the hermretro page stopped with this error:\n${failure ?? data?.install?.error ?? 'unknown error'}`,
      { fresh: true }
    )

  const verifying = (state === 'done' || elsewhere) && !toolchainDone
  const phase = toolchainDone
    ? 'done'
    : starting || state === 'running' || verifying
      ? 'running'
      : failure || state === 'failed'
        ? 'failed'
        : 'review'

  return { ask, data, elsewhere, failure: failure ?? data?.install?.error ?? null, makeProfile, needsProfile, node, phase, profileWork, start, starting, state, unsupported, verifying }
}

const ROW_LABEL = { done: 'verified', running: 'installing', failed: 'failed', pending: '' }

/** The download list: what, which version, from where, how big, and why. Doubles as live progress. */
function DownloadTable({ manifest, install, phase, profileRow }) {
  const components = install?.run?.components ?? {}
  const current = install?.current
  const rows = (manifest?.items ?? []).map(item => {
    const component = components[item.component]
    const state = phase === 'done' || install?.state === 'done' ? 'done' : component?.state ?? (phase === 'review' ? null : 'pending')

    return { ...item, state, running: state === 'running' && current === item.component }
  })

  const row = item =>
    jsxs(
      'tr',
      {
        'data-state': item.state ?? undefined,
        children: [
          item.state ? jsx('td', { className: 'g', children: jsx(Glyph, { state: { done: 'done', running: 'checking', failed: 'error', pending: 'waiting' }[item.state] }) }) : null,
          jsxs('td', { className: 'n', children: [item.name, jsx('span', { className: 'p', children: item.purpose })] }),
          jsx('td', { className: 'v', children: item.version }),
          jsx('td', { className: 's', children: item.source }),
          jsx('td', {
            className: `z ${item.state ?? ''}`,
            children: item.state && item.state !== 'pending' ? ROW_LABEL[item.state] : item.bytes ? formatBytes(item.bytes, item.approx) : 'no download'
          })
        ]
      },
      item.id
    )

  const live = phase !== 'review'

  return jsxs('table', {
    className: 'cs-dl',
    children: [
      jsx('thead', {
        children: jsxs('tr', {
          children: [
            live ? jsx('th', { className: 'g' }) : null,
            jsx('th', { children: 'Component' }),
            jsx('th', { children: 'Version' }),
            jsx('th', { className: 's', children: 'From' }),
            jsx('th', { className: 'z', children: live ? 'Status' : 'Download' })
          ]
        })
      }),
      jsx('tbody', {
        children: [
          profileRow
            ? row({
                id: 'profile',
                name: 'Your hermretro profile',
                purpose: 'A Hermes profile with just the game tools and skills',
                version: '',
                source: 'this computer',
                bytes: 0,
                state: live ? profileRow : null
              })
            : null,
          ...rows.map(item => row({ ...item, state: live ? item.state : null }))
        ]
      })
    ]
  })
}

/** Checksums proven so far, and what is being installed now. */
function InstallLog({ install, phase }) {
  const components = install?.run?.components ?? {}
  const lines = []

  for (const id of ['gbdk', 'cli', 'uv', 'emulator']) {
    const component = components[id]

    for (const check of component?.checks ?? []) {
      lines.push(
        jsxs('div', {
          children: [
            jsx('span', { className: 'ok', children: '✓ ' }),
            `${check.file}  sha256 ${String(check.sha256).slice(0, 8)}…  ${check.reused ? 'verified (cached)' : 'verified'}`
          ]
        }, `${id}:${check.file}`)
      )
    }

    if (component?.state === 'done' && !component.checks?.length) {
      lines.push(jsxs('div', { children: [jsx('span', { className: 'ok', children: '✓ ' }), `${id} ${component.version ?? ''} already installed, checked`] }, `${id}:reused`))
    }

    if (component?.state === 'failed') {
      lines.push(jsxs('div', { className: 'bad', children: ['✗ ', `${id}: ${component.error ?? 'failed'}`] }, `${id}:failed`))
    }
  }

  if (phase === 'running' && install?.current) {
    const label = (install.current === 'cli' ? 'GB Studio and its packages' : { gbdk: 'GBDK', uv: 'uv', emulator: 'Python, PyBoy and Pillow' }[install.current]) ?? install.current

    lines.push(jsxs('div', { className: 'w', children: [jsx('span', { className: 'run', children: '↓ ' }), `Installing ${label}…`] }, 'now'))
  }

  return lines.length ? jsx('div', { 'aria-live': 'polite', className: 'cs-log', role: 'log', children: lines }) : null
}

/** The last few folders of a long path, so the end (the part that says where) stays readable. */
function shortPath(path, keep = 4) {
  if (!path) {
    return null
  }

  const parts = String(path).split(/[\\/]/).filter(Boolean)

  return parts.length > keep ? `…/${parts.slice(-keep).join('/')}` : path
}

function InstallFacts({ manifest, status, root }) {
  const node = nodeState(status.data?.node)

  return jsxs('dl', {
    className: 'cs-onb-facts',
    children: [
      jsx('dt', { children: 'Download' }),
      jsx('dd', { children: formatBytes(manifest?.bytes ?? 0, true) }),
      jsx('dt', { children: 'On disk' }),
      jsx('dd', { children: formatBytes(manifest?.disk_bytes ?? 0, true) }),
      jsx('dt', { children: 'Installs to' }),
      jsx('dd', { className: 'path', title: root ?? '', children: shortPath(root) ?? "the plugin's deps folder" }),
      jsx('dt', { children: 'Already here' }),
      jsx('dd', { className: node.ok ? 'good' : 'bad', children: node.ok ? `Node.js ${node.version} (from Hermes)` : 'Node.js not found' })
    ]
  })
}

function InstallProgress({ install, phase, verifying, elsewhere }) {
  if (phase !== 'running') {
    return null
  }

  if (elsewhere && install?.state !== 'running') {
    return jsx(Working, { children: 'The tools are being installed from a chat. This page moves on when they are verified.' })
  }

  const fraction = Math.max(0.02, Math.min(1, install?.fraction ?? 0))
  const downloaded = install?.downloaded_bytes ?? 0

  return jsxs('div', {
    className: 'cs-col',
    style: { gap: 8 },
    children: [
      jsxs('div', {
        className: 'cs-row cs-mono',
        style: { justifyContent: 'space-between', fontSize: 11.5 },
        children: [
          jsx('span', { children: verifying ? 'Checking the installed tools…' : `${Math.round(fraction * 100)}%` }),
          jsx('span', { className: 'cs-faint', children: downloaded > 0 ? `${formatBytes(downloaded)} downloaded` : install?.seeded ? 'Using files already on this computer' : '' })
        ]
      }),
      jsx('div', { className: 'cs-progress', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': Math.round(fraction * 100), children: jsx('b', { style: { width: `${fraction * 100}%` } }) })
    ]
  })
}

/** The buttons under an install: start, retry, ask Hermes. */
function InstallActions({ installer, compact = false }) {
  const { phase, start, starting, ask, node, unsupported } = installer

  if (unsupported) {
    return jsxs('div', {
      className: 'cs-col',
      style: { gap: 10 },
      children: [
        jsx(Small, { tone: 'warn', children: 'This hermretro backend cannot install from the page yet. Update the plugin, or let Hermes do it in a chat.' }),
        jsx('div', { className: 'cs-actions', children: jsx(AsyncButton, { icon: 'comment-discussion', run: ask, variant: 'default', children: 'Set up in chat' }) })
      ]
    })
  }

  if (!node.ok) {
    return jsx(Small, {
      tone: 'warn',
      children: node.version
        ? `Found Node.js ${node.version}, which is too old (hermretro needs ${node.required} or newer). Update Hermes, then come back.`
        : `Node.js was not found. Hermes normally installs it; run "hermes update", restart Hermes, then come back.`
    })
  }

  if (phase === 'done' && installer.needsProfile) {
    return installer.profileWork.state === 'running'
      ? jsx(Working, { children: 'Creating the hermretro profile…' })
      : jsx('div', {
          className: 'cs-actions',
          children: jsx(Button, { onClick: installer.makeProfile, size: compact ? 'sm' : 'lg', variant: 'default', children: 'Create the hermretro profile' })
        })
  }

  if (phase === 'done' && installer.profileWork.state !== 'failed') {
    return jsx(Working, { quiet: true, children: 'Tools verified. Waiting for Hermes to start the hermretro profile…' })
  }

  if (phase === 'review') {
    return jsx('div', {
      className: 'cs-actions',
      children: jsxs(Button, {
        disabled: starting,
        onClick: () => void start(),
        size: compact ? 'sm' : 'lg',
        variant: 'default',
        children: [jsx(Codicon, { name: 'cloud-download', size: 14 }), 'Download and install']
      })
    })
  }

  if (phase === 'failed') {
    return jsxs('div', {
      className: 'cs-actions',
      children: [
        jsxs(Button, {
          disabled: starting,
          onClick: () => void start(),
          size: compact ? 'sm' : 'lg',
          variant: 'default',
          children: [jsx(Codicon, { name: 'refresh', size: 14 }), 'Try again']
        }),
        jsx(AsyncButton, { icon: 'comment-discussion', run: ask, title: 'Opens a chat with the error in it, not sent', children: 'Ask Hermes to fix it' })
      ]
    })
  }

  return null
}

function InstallError({ installer }) {
  const { failure, phase, profileWork } = installer

  return [
    phase === 'failed' && failure ? jsx('p', { className: 'cs-error', children: failure }, 'error') : null,
    profileWork.state === 'failed'
      ? jsx('p', { className: 'cs-error', children: `The hermretro profile could not be created: ${profileWork.error}` }, 'profile')
      : null
  ]
}

function profileRowState(installer, profileStep, status) {
  const profile = status.data?.profile

  if (!profile) {
    return null // a backend that predates the studio profile
  }

  if (profileStep?.state === 'done') {
    return 'done'
  }

  if (installer.profileWork.state === 'failed') {
    return 'failed'
  }

  // Being made, or made and waiting for Hermes to start it.
  return installer.profileWork.state !== 'idle' || profile.studio?.installed ? 'running' : 'pending'
}

/** The toolchain step on the Setup page (repairs after onboarding): the same install, compact. */
function InstallPanel({ ctx, status, install, step, profileStep }) {
  const installer = useInstaller({ ctx, install, status, toolchainDone: step.state === 'done' })
  const data = install.data

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(InstallFacts, { manifest: data?.manifest, root: data?.root, status }),
      jsx(InstallProgress, { elsewhere: installer.elsewhere, install: data?.install, phase: installer.phase, verifying: installer.verifying }),
      data?.manifest
        ? jsx(DownloadTable, { install: data.install, manifest: data.manifest, phase: installer.phase, profileRow: profileRowState(installer, profileStep, status) })
        : install.isError
          ? null
          : jsx(Working, { quiet: true, children: 'Reading the download list…' }),
      jsx(InstallLog, { install: data?.install, phase: installer.phase }),
      ...InstallError({ installer }),
      jsx(InstallActions, { compact: true, installer })
    ]
  })
}

// ── First-run onboarding ──────────────────────────────────────────────────────
// A new user sees only this until the game tools are installed and they have chosen how to play:
// Welcome → what gets downloaded / installing → "Do you have a Chromatic?" → "What do you want to make?".

function OnboardHeader({ stage }) {
  const index = ONBOARD_STAGES.findIndex(([id]) => id === stage)

  return jsxs('header', {
    className: 'cs-top',
    children: [
      jsxs('span', { className: 'cs-brand', style: { cursor: 'default' }, children: ['herm', jsx('span', { children: 'retro' })] }),
      index >= 0
        ? jsxs('div', {
            'aria-label': `Setup, step ${index + 1} of ${ONBOARD_STAGES.length}: ${ONBOARD_STAGES[index][1]}`,
            className: 'cs-onb-steps',
            role: 'img',
            children: [
              ...ONBOARD_STAGES.map(([id], position) => jsx('i', { className: position < index ? 'done' : position === index ? 'cur' : '' }, id)),
              jsx('span', { children: `${index + 1} / ${ONBOARD_STAGES.length} · ${ONBOARD_STAGES[index][1]}` })
            ]
          })
        : jsx('span', { className: 'cs-onb-steps', children: jsx('span', { children: 'First-time setup' }) })
    ]
  })
}

function OnboardWelcome({ manifest, onStart }) {
  return jsxs('div', {
    className: 'cs-onb-hero',
    children: [
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 24 },
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [jsx('span', { className: 'cs-accent', children: '● Welcome' }), jsx('span', { children: 'First-time setup · a few minutes' })]
          }),
          jsxs('h1', { className: 'cs-word', children: ['Make a game.', jsx('br', {}), jsx('span', { className: 'cs-accent', children: 'Play it tonight.' })] }),
          jsx(Lede, {
            children:
              "hermretro turns a chat with Hermes into a real Game Boy Color game. Before your first game it needs the tools that build and playtest ROMs. Everything goes into the plugin's own folder."
          }),
          jsxs('div', {
            className: 'cs-actions',
            style: { gap: 16 },
            children: [
              jsxs(Button, { onClick: onStart, size: 'lg', variant: 'default', children: ['Get started', jsx(Codicon, { name: 'arrow-right', size: 14 })] }),
              manifest
                ? jsx('span', { className: 'cs-faint cs-mono', children: `${formatBytes(manifest.bytes, true)} download · ${formatBytes(manifest.disk_bytes, true)} on disk` })
                : null
            ]
          })
        ]
      }),
      jsx(Art, {})
    ]
  })
}

function OnboardInstall({ ctx, status, install, toolchainDone, profileStep }) {
  const installer = useInstaller({ ctx, install, status, toolchainDone })
  const data = install.data
  const { phase } = installer
  const title =
    phase === 'failed'
      ? ['One part ', jsx('span', { className: 'cs-bad', children: "didn't finish" }, 'a')]
      : phase === 'review'
        ? ["Here's what gets ", jsx('span', { className: 'cs-accent', children: 'downloaded' }, 'a')]
        : ['Setting up the ', jsx('span', { className: 'cs-accent', children: 'studio' }, 'a')]
  const lede =
    phase === 'failed'
      ? 'Nothing is broken, and the parts that finished are kept. Try again, or ask Hermes to look at the error.'
      : phase === 'review'
        ? "Every file is pinned to an exact version and checked against its SHA-256 before it is used. Nothing is installed system-wide: it all goes into the plugin's folder, and removing the plugin removes it."
        : 'You can leave this page: the install keeps running, and this page moves on when the tools are verified.'

  return jsxs('div', {
    className: 'cs-onb-split',
    children: [
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 22 },
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [
              jsx('span', { className: phase === 'failed' ? 'cs-bad' : 'cs-accent', children: 'Step 1 of 3' }),
              jsx('span', { children: { review: 'Install', running: 'Installing', failed: 'Stopped', done: 'Installed' }[phase] })
            ]
          }),
          jsx('h2', { className: 'cs-word cs-title', children: title }),
          jsx(Lede, { children: lede }),
          jsx(InstallFacts, { manifest: data?.manifest, root: data?.root, status }),
          jsx(InstallProgress, { elsewhere: installer.elsewhere, install: data?.install, phase, verifying: installer.verifying }),
          ...InstallError({ installer }),
          jsx(InstallActions, { installer })
        ]
      }),
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 18 },
        children: [
          data?.manifest
            ? jsx(DownloadTable, { install: data.install, manifest: data.manifest, phase, profileRow: profileRowState(installer, profileStep, status) })
            : install.isError && !installer.unsupported
              ? jsx('p', { className: 'cs-error', children: describeRequestError(install.error).message })
              : installer.unsupported
                ? null
                : jsx(Working, { quiet: true, children: 'Reading the download list…' }),
          jsx(InstallLog, { install: data?.install, phase }),
          data?.manifest && !data.manifest.exact
            ? jsx('span', { className: 'cs-faint', children: `Sizes were measured on ${data.manifest.measured_on} and are approximate here.` })
            : null
        ]
      })
    ]
  })
}

function OnboardChromatic({ onEmulator, onDevice }) {
  const card = ({ tag, tone, title, text, onClick, art, primary }) =>
    jsxs('button', {
      className: primary ? 'cs-hwcard primary' : 'cs-hwcard',
      onClick,
      type: 'button',
      children: [
        art,
        jsxs('span', {
          className: 'cs-col',
          style: { gap: 8 },
          children: [
            jsx('span', { className: `cs-tag ${tone}`, style: { alignSelf: 'flex-start' }, children: tag }),
            jsx('span', { className: 'cs-word t', children: title }),
            jsx('span', { className: 'cs-small', children: text })
          ]
        })
      ]
    })

  return jsxs('div', {
    className: 'cs-col',
    style: { gap: 28 },
    children: [
      jsxs('p', { className: 'cs-eyebrow', children: [jsx('span', { className: 'cs-accent', children: 'Step 2 of 3' }), jsx('span', { children: 'Your hardware' })] }),
      jsxs('h2', { className: 'cs-word cs-onb-title', children: ['Do you have a ', jsx('span', { className: 'cs-accent', children: 'Chromatic?' })] }),
      jsx(Lede, { children: 'Every game plays in the emulator here, with sound. With a ModRetro Chromatic you can also stream games to it and write them to a cartridge.' }),
      jsxs('div', {
        className: 'cs-hwcards',
        children: [
          card({
            art: jsx('span', { 'aria-hidden': true, className: 'cs-hwart screen', children: jsx(Codicon, { name: 'play', size: 22 }) }),
            onClick: onEmulator,
            primary: true,
            tag: 'Ready now',
            text: 'Make and play games in the emulator. You can add a Chromatic later from Setup.',
            title: 'Not yet',
            tone: 'good'
          }),
          card({
            art: jsx('span', { 'aria-hidden': true, className: 'cs-hwart device' }),
            onClick: onDevice,
            tag: '4 more steps',
            text: "Update its firmware, turn on Developer Mode and install ModRetro's device software.",
            title: 'Yes, I have one',
            tone: 'quiet'
          })
        ]
      })
    ]
  })
}

const IDEAS = [
  ['Tiny platformer', 'a tiny platformer where a frog hops across lily pads to reach home'],
  ['Top-down adventure', 'a top-down adventure where a gardener collects three seeds to open a gate'],
  ['Puzzle game', 'a short puzzle game about pushing crates onto switches'],
  ['Spooky story', 'a spooky little story game set in an abandoned lighthouse']
]

function makePrompt(idea) {
  const text = idea.trim()

  return text
    ? `Use hermretro to make a new Game Boy Color game: ${text}. Ask me a few quick questions first, then create the project, build it and show it to me in the emulator.`
    : NEW_GAME_PROMPT
}

function OnboardMake({ ctx, onDone }) {
  const [idea, setIdea] = useState('')
  const [busy, setBusy] = useState(false)

  const go = async prompt => {
    if (busy) {
      return
    }

    setBusy(true)

    try {
      await sendPromptToChat(ctx, prompt, { fresh: true })
      onDone()
    } finally {
      setBusy(false)
    }
  }

  return jsxs('div', {
    className: 'cs-onb-hero',
    children: [
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 22 },
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [jsx('span', { className: 'cs-good', children: '● Studio ready' }), jsx('span', { children: 'Step 3 of 3' })]
          }),
          jsxs('h2', { className: 'cs-word cs-onb-title', children: ['What do you', jsx('br', {}), 'want to ', jsx('span', { className: 'cs-accent', children: 'make?' })] }),
          jsxs('div', {
            className: 'cs-idea',
            children: [
              jsx('textarea', {
                'aria-label': 'Your game idea',
                onChange: event => setIdea(event.target.value),
                onKeyDown: event => {
                  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault()
                    void go(makePrompt(idea))
                  }
                },
                placeholder: 'A frog who delivers mail across a flooded town…',
                rows: 3,
                value: idea
              }),
              jsxs('div', {
                className: 'cs-row',
                style: { justifyContent: 'space-between' },
                children: [
                  jsx('span', { className: 'cs-faint', children: 'Hermes asks a few questions, then builds the first room. The prompt opens in a new chat.' }),
                  jsxs(Button, {
                    disabled: busy,
                    onClick: () => void go(makePrompt(idea)),
                    size: 'sm',
                    variant: 'default',
                    children: ['Start in chat', jsx(Codicon, { name: 'arrow-right', size: 14 })]
                  })
                ]
              })
            ]
          }),
          jsxs('div', {
            'aria-label': 'Ideas',
            className: 'cs-ideas',
            role: 'group',
            children: [
              ...IDEAS.map(([label, text]) => jsx('button', { onClick: () => setIdea(text), type: 'button', children: label }, label)),
              jsx('button', { disabled: busy, onClick: () => void go(promptById('plan').text), type: 'button', children: 'Plan it first' }, 'plan')
            ]
          }),
          jsx('div', { children: jsx(Button, { onClick: onDone, size: 'sm', variant: 'ghost', children: 'Skip, take me to the studio' }) })
        ]
      }),
      jsx(Art, {})
    ]
  })
}

function Onboarding({ ctx, screen, status, install, steps, update, onFinish, onDevice }) {
  const toolchain = steps.find(step => step.id === 'toolchain')
  const profileStep = steps.find(step => step.id === 'profile')
  let body

  if (screen === 'checking') {
    body = jsx(Working, { children: 'Checking what is already installed…' })
  } else if (screen === 'welcome') {
    body = jsx(OnboardWelcome, { manifest: install.data?.manifest, onStart: () => update({ onboardStarted: true }) })
  } else if (screen === 'install') {
    body = jsx(OnboardInstall, { ctx, install, profileStep, status, toolchainDone: toolchain?.state === 'done' })
  } else if (screen === 'chromatic') {
    body = jsx(OnboardChromatic, { onDevice, onEmulator: () => update({ hardwareSkipped: true, hardwareWanted: false }) })
  } else {
    body = jsx(OnboardMake, { ctx, onDone: onFinish })
  }

  return jsx('section', { 'aria-live': 'polite', className: 'cs-onb', 'data-screen': screen, children: body })
}

function ToolchainBody({ ctx, step, status, doctor, install, steps }) {
  if (!status.data?.ok) {
    return jsx(Small, { children: 'Checked once the plugin is on.' })
  }

  const platform = status.data.platform
  const engine = status.data.engine ?? {}
  const deps = status.data.deps ?? {}
  const report = doctor.data

  // The engine has its own row; Node.js comes with Hermes and is not listed.
  const rows = (report?.ok ? (report.components ?? []) : [])
    .filter(component => component.id !== 'node' && component.id !== 'runtime')
    .map(component => jsx(ComponentRow, { component }, component.id ?? component.label))

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          'The compilers and emulator that turn a project into a real Game Boy Color ROM and let Hermes playtest it: GB Studio, GBDK and PyBoy.'
      }),
      step.state === 'error'
        ? jsxs('div', {
            className: 'cs-col',
            style: { gap: 10 },
            children: [
              jsx('p', {
                className: 'cs-error',
                children: `Toolchain check failed: ${report?.error || describeRequestError(doctor.error).message || 'unknown error'}`
              }),
              jsx('div', {
                className: 'cs-actions',
                children: jsxs(Button, {
                  disabled: doctor.isFetching,
                  onClick: () => void doctor.refetch?.(),
                  size: 'sm',
                  variant: 'default',
                  children: [jsx(Codicon, { name: 'refresh', size: 14, spinning: doctor.isFetching }), 'Check again']
                })
              })
            ]
          })
        : null,
      platform && platform.qualified === false
        ? jsx(Small, {
            tone: 'warn',
            children: `${platform.system ?? 'This system'} ${platform.machine ?? ''} has not been tested yet; some steps may not work.`
          })
        : null,
      (step.state === 'todo' || step.state === 'blocked') && install
        ? jsx(InstallPanel, { ctx, install, profileStep: steps?.find(item => item.id === 'profile'), status, step })
        : null,
      step.state === 'done' || step.state === 'error'
        ? jsx('div', {
            className: 'cs-comps',
            children: [
              jsx(ComponentRow, {
                component: {
                  id: 'engine',
                  label: 'Chromatic engine',
                  status: engine.present ? (engine.verified === false ? 'incompatible' : 'ready') : 'missing',
                  detected: engine.present ? engine.version : '',
                  detail: engine.detail || (engine.present && engine.verified === false ? 'Engine could not be verified.' : '')
                }
              }, 'engine'),
              ...rows
            ]
          })
        : null,
      !report && step.state === 'checking' ? jsx(Working, { quiet: true, children: 'Checking installed tools…' }) : null,
      deps.toolchain_root && step.state === 'done'
        ? jsxs('span', {
            className: 'cs-faint',
            children: [
              deps.inside_plugin ? 'Install folder (inside the plugin): ' : 'Install folder: ',
              jsx('span', { className: 'cs-mono', children: deps.toolchain_root }),
              deps.toolchain_cache_reused_from ? '. Downloads were reused from an existing ModRetro install on this computer.' : ''
            ]
          })
        : null
    ]
  })
}

/** Steps done in ModRetro's own app: the user says when they are done. */
function Confirm({ step, update }) {
  return step.state === 'done'
    ? jsx(Button, { onClick: () => update({ [MANUAL_STEPS[step.id]]: false }), size: 'sm', variant: 'ghost', children: 'Mark as not done' })
    : jsxs(Button, {
        onClick: () => update({ [MANUAL_STEPS[step.id]]: true }),
        size: 'sm',
        variant: 'default',
        children: [jsx(Codicon, { name: 'check', size: 14 }), "I've done this"]
      })
}

function FirmwareBody({ ctx, step, update }) {
  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          "Install the latest firmware with ModRetro's Chromatic Firmware Updater. This happens in ModRetro's app, not in Hermes, so confirm here when it is done."
      }),
      jsxs('div', {
        className: 'cs-actions',
        children: [
          jsx(ExternalLink, { ctx, href: LINKS.firmware, variant: 'outline', children: 'Open the Firmware Updater guide' }),
          jsx(Confirm, { step, update })
        ]
      })
    ]
  })
}

function Keys({ keys }) {
  return jsxs('span', {
    className: 'cs-row',
    style: { gap: 6 },
    children: keys.flatMap((key, index) => [
      index ? jsx('span', { className: 'cs-faint', children: '+' }, `p${index}`) : null,
      jsx('kbd', { className: 'cs-kbd', children: key }, key)
    ])
  })
}

function DevModeBody({ step, update }) {
  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          "Developer Mode lets this computer write your games to the cartridge. In ModRetro's Chromatic Firmware Updater press"
      }),
      jsxs('div', {
        className: 'cs-row',
        style: { gap: 10 },
        children: [
          jsx(Keys, { keys: ['Ctrl', 'I'] }),
          jsx('span', { className: 'cs-faint', children: 'or, on macOS,' }),
          jsx(Keys, { keys: ['⌘', 'I'] })
        ]
      }),
      jsx(Small, { children: 'then enter the activation code included with the Chromatic: Codex Edition.' }),
      jsxs('div', {
        className: 'cs-warnline',
        children: [
          jsx('span', { children: jsx(Codicon, { name: 'warning', size: 14 }) }),
          jsx('span', { children: "Activation happens only in ModRetro's Updater. Never type the code into a chat." })
        ]
      }),
      jsx('div', { className: 'cs-actions', children: jsx(Confirm, { step, update }) })
    ]
  })
}

function DeviceSoftwareBody({ ctx, step, status }) {
  const cli = status.data?.deps?.device_cli

  if (!cli) {
    return jsx(Small, {
      children: status.data?.ok ? 'Not reported yet. Start a new chat to finish loading the plugin.' : 'Checked once the plugin is on.'
    })
  }

  if (step.state === 'done') {
    return jsx(Lede, { children: `ModRetro Chromatic CLI${cli.version ? ` ${cli.version}` : ''} is installed inside the plugin folder.` })
  }

  if (cli.state === 'unsupported') {
    return jsx(Small, { tone: 'warn', children: cli.detail || 'ModRetro does not publish its device software for this computer.' })
  }

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children:
          "hermretro talks to the device through ModRetro's own Chromatic CLI. It is ModRetro's software, so it is not included: Hermes downloads it from ModRetro, checks it, and keeps it inside the plugin folder."
      }),
      jsx(Facts, {
        rows: [
          [
            'Source',
            jsxs('span', {
              children: [
                "ModRetro's npm package, checked against pinned hashes. ",
                cli.terms ? jsx(ExternalLink, { ctx, href: cli.terms, children: "ModRetro's terms" }) : null
              ]
            })
          ],
          ['Approval', 'Hermes asks for your approval before downloading, unless Approvals are turned off.']
        ]
      }),
      jsx(PromptBlock, { ctx, label: 'Install in chat', prompt: DEVICE_CLI_PROMPT })
    ]
  })
}

const HARDWARE_ABILITIES = ['Detect the device', 'Stream', 'Flash a cartridge', 'Capture']

function HardwareBody({ step }) {
  const on = step.state === 'done'

  return jsxs('div', {
    className: 'cs-content',
    children: [
      jsx(Lede, {
        children: on
          ? 'Hardware tools are on for this profile: device detection, streaming, flashing and capture are available.'
          : 'Device detection, streaming, flashing and capture are off until you allow them. Turn on "Chromatic hardware tools" in the plugin settings; this page continues once it is on.'
      }),
      jsx('div', {
        className: 'cs-row',
        style: { gap: 6 },
        children: HARDWARE_ABILITIES.map(label => jsx(Chip, { tone: on ? 'good' : '', children: label }, label))
      }),
      jsx(Small, {
        children: 'Writing a cartridge, streaming and driver setup ask for your approval first, unless Approvals are turned off in Hermes.'
      }),
      jsx('div', {
        className: 'cs-actions',
        children: jsxs(Button, {
          onClick: () => host.navigate(AGENT_SETTINGS_HREF),
          size: 'sm',
          variant: on ? 'outline' : 'default',
          children: [jsx(Codicon, { name: 'settings-gear', size: 14 }), 'Open plugin settings']
        })
      })
    ]
  })
}

function stepBody(step, props) {
  switch (step.id) {
    case 'profile':
      return jsx(ProfileBody, props)
    case 'toolchain':
      return jsx(ToolchainBody, { ...props, step })
    case 'firmware':
      return jsx(FirmwareBody, { ...props, step })
    case 'devmode':
      return jsx(DevModeBody, { ...props, step })
    case 'devicecli':
      return jsx(DeviceSoftwareBody, { ...props, step })
    default:
      return jsx(HardwareBody, { ...props, step })
  }
}

const STEP_SHORT = {
  profile: 'Studio profile',
  toolchain: 'Game toolchain',
  firmware: 'Firmware',
  devmode: 'Developer Mode',
  devicecli: 'Device software',
  hardware: 'Hardware tools'
}

/** The list of steps beside the page: the game steps, then the optional Chromatic ones. */
function StepRail({ steps, shownId, autoId, onPick, skipped }) {
  const done = steps.filter(step => step.state === 'done').length
  const item = (step, position) =>
    jsxs(
      'button',
      {
        'aria-current': step.id === shownId ? 'step' : undefined,
        className: 'cs-rail-item',
        'data-auto': step.id === autoId ? '' : undefined,
        'data-state': step.state,
        onClick: () => onPick(step.id),
        type: 'button',
        children: [
          jsx('span', { className: 'n', children: String(position + 1).padStart(2, '0') }),
          jsx('span', { className: 'l', children: STEP_SHORT[step.id] }),
          jsx(Glyph, { state: step.state })
        ]
      },
      step.id
    )

  return jsxs('nav', {
    'aria-label': 'Setup steps',
    className: 'cs-rail',
    children: [
      jsx('span', { className: 'cs-rail-group', children: 'Make games' }),
      ...steps.filter(step => !step.hardware).map(step => item(step, steps.indexOf(step))),
      jsxs('span', { className: 'cs-rail-group second', children: [jsx('span', { children: 'Your Chromatic' }), jsx('span', { children: 'optional' })] }),
      ...steps.filter(step => step.hardware).map(step => item(step, steps.indexOf(step))),
      jsx('div', {
        className: 'cs-meter',
        children: steps.map((step, position) =>
          jsx(
            'button',
            {
              'aria-label': `Step ${position + 1}: ${step.title} (${(INDICATOR[step.state] ?? INDICATOR.waiting).label})`,
              className: step.id === HARDWARE_STEPS[0] ? 'gap' : undefined,
              'data-auto': step.id === autoId ? '' : undefined,
              'data-state': step.state,
              onClick: () => onPick(step.id),
              type: 'button',
              children: jsx('i', {})
            },
            step.id
          )
        )
      }),
      jsx('span', { className: 'cs-faint cs-mono', children: `${done} / ${steps.length} done${skipped ? ' · emulator only' : ''}` })
    ]
  })
}

function StepStage({ step, number, total, children, footer }) {
  const tag =
    step.state === 'done'
      ? jsx('span', { className: 'cs-tag good', children: 'Done' })
      : step.state === 'error'
        ? jsx('span', { className: 'cs-tag bad', children: 'Problem' })
        : step.state === 'skipped'
          ? jsx('span', { className: 'cs-tag quiet', children: 'Skipped' })
          : step.hardware
            ? jsx('span', { className: 'cs-tag quiet', children: 'Only for a physical Chromatic' })
            : null

  return jsxs('section', {
    'aria-live': 'polite',
    className: 'cs-stage',
    children: [
      jsxs('div', {
        className: 'cs-stage-head',
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [
              jsx('span', { className: 'cs-accent', children: `Step ${number} of ${total}` }),
              jsx('span', { children: step.hardware ? 'Your Chromatic' : 'Make games' }),
              tag
            ]
          }),
          jsx('h2', { className: 'cs-word cs-title', children: step.title })
        ]
      }),
      children,
      footer
    ]
  })
}

/** Between the game steps and the Chromatic ones: everything needed for the emulator is done,
 *  and a physical Chromatic is optional. */
function HardwareChoice({ steps, update }) {
  const remaining = steps.filter(step => step.hardware && step.state !== 'done').length

  return jsxs('section', {
    'aria-live': 'polite',
    className: 'cs-stage',
    children: [
      jsxs('div', {
        className: 'cs-stage',
        style: { display: 'contents' },
        children: [
          jsxs('div', {
            className: 'cs-stage-head',
            children: [
              jsxs('p', {
                className: 'cs-eyebrow',
                children: [jsx('span', { className: 'cs-accent', children: 'Steps 1–2 done' }), jsx('span', { children: 'The emulator is ready' })]
              }),
              jsx('h2', { className: 'cs-word cs-title', children: 'Ready to make games' })
            ]
          }),
          jsx(Lede, {
            children:
              'Hermes can now create, build and playtest your games, and you play them on the Emulator page, with sound. A physical Chromatic is optional: set it up now, or any time later.'
          }),
          jsxs('div', {
            className: 'cs-choice',
            children: [
              jsxs('div', {
                children: [
                  jsx('p', { className: 'cs-eyebrow', children: 'Emulator' }),
                  jsx('h3', { children: 'Start making games' }),
                  jsx(Small, { children: 'Build and play everything inside Hermes. Nothing else to install.' }),
                  jsx('div', {
                    className: 'cs-actions',
                    children: jsxs(Button, {
                      onClick: () => update({ hardwareSkipped: true, hardwareWanted: false }),
                      size: 'sm',
                      variant: 'default',
                      children: ['Start making games', jsx(Codicon, { name: 'arrow-right', size: 14 })]
                    })
                  })
                ]
              }),
              jsxs('div', {
                children: [
                  jsx('p', { className: 'cs-eyebrow', children: 'ModRetro Chromatic' }),
                  jsx('h3', { children: 'I have a Chromatic' }),
                  jsx(Small, {
                    children: `${remaining} more ${remaining === 1 ? 'step' : 'steps'} to stream your games to the handheld and write them to a cartridge: firmware, Developer Mode, ModRetro's device software and hardware tools.`
                  }),
                  jsx('div', {
                    className: 'cs-actions',
                    children: jsx(Button, {
                      onClick: () => update({ hardwareSkipped: false, hardwareWanted: true }),
                      size: 'sm',
                      variant: 'outline',
                      children: 'Set up my Chromatic'
                    })
                  })
                ]
              })
            ]
          }),
          jsx('span', { className: 'cs-faint', children: 'You can change this any time: the Chromatic steps stay in the setup list.' })
        ]
      })
    ]
  })
}

function SetupWizard({ ctx, steps, shown, autoId, backend, status, doctor, gateway, install, update, onPick, onContinue }) {
  const position = steps.indexOf(shown)
  const reviewing = shown.id !== autoId
  const waiting = !reviewing && !shown.manual && !shown.complete && shown.state !== 'blocked'
  const left = []
  const right = []

  if (position > 0) {
    left.push(
      jsxs(
        Button,
        {
          onClick: () => onPick(steps[position - 1].id),
          size: 'sm',
          variant: 'ghost',
          children: [jsx(Codicon, { name: 'arrow-left', size: 14 }), 'Back']
        },
        'back'
      )
    )
  }

  if (waiting) {
    left.push(jsx(Working, { quiet: true, children: 'Checking automatically; this page moves on when the step is done.' }, 'waiting'))
  }

  if (shown.hardware && !shown.complete) {
    right.push(
      jsx(Button, { onClick: () => update({ hardwareSkipped: true }), size: 'sm', variant: 'ghost', children: "Skip, I'll use the emulator" }, 'skip')
    )
  }

  if (shown.state === 'skipped') {
    right.push(
      jsx(
        Button,
        { onClick: () => update({ hardwareSkipped: false, hardwareWanted: true }), size: 'sm', variant: 'outline', children: 'Set up my Chromatic' },
        'unskip'
      )
    )
  }

  if (reviewing) {
    right.push(
      jsxs(
        Button,
        { onClick: onContinue, size: 'sm', variant: 'default', children: ['Continue', jsx(Codicon, { name: 'arrow-right', size: 14 })] },
        'continue'
      )
    )
  }

  const footer =
    left.length || right.length
      ? jsxs('div', {
          className: 'cs-stage-foot',
          children: [jsx('div', { className: 'cs-row', style: { flex: '1 1 auto' }, children: left }), jsx('div', { className: 'cs-row', children: right })]
        })
      : null

  return jsx(StepStage, {
    step: shown,
    number: position + 1,
    total: steps.length,
    footer,
    children: jsxs('div', {
      className: 'cs-content',
      children: [
        shown.state === 'skipped'
          ? jsx(Small, { children: 'Skipped: you are using the emulator. Streaming and flashing stay off until your Chromatic is set up.' })
          : null,
        stepBody(shown, { backend, ctx, doctor, gateway, install, status, steps, update })
      ]
    })
  })
}

// ── Studio panes (docked beside the chat) ──────────────────────────────────────
// The chat stays the real Hermes chat. These panes show what is happening to the game
// in that chat: the screen the agent last saw, the last build, and a log of its work.

// Ids changed from 'studio'/'log' when the panes moved next to the chat: Hermes places a pane once,
// by id, so a new position needs a new id.
const PANE_GAME = 'live'
const PANE_LOG = 'worklog'
const ALWAYS_VISIBLE = atom(true)

const BUILD_PLAYTEST_PROMPT = promptById('playtest').text
const PLAY_PROMPT = promptById('play-game').text
const NEW_GAME_PROMPT =
  'Use hermretro to help me start a new Game Boy Color game. Ask me what I want to make, then create the project, build it and show me the first frame.'

const TOOL_LABELS = {
  rom_build: 'Built the ROM',
  web_build: 'Built the player',
  web_preview: 'Opened the player',
  web_preview_close: 'Closed the player',
  emulator_run: 'Started the emulator',
  emulator_step: 'Played the game',
  emulator_observe: 'Looked at the screen',
  emulator_close: 'Closed the emulator',
  project_create: 'Created the project',
  project_create_blank: 'Created the project',
  project_select: 'Opened the project',
  project_inspect: 'Read the project',
  scene_create: 'Added a scene',
  scene_update: 'Edited a scene',
  actor_create: 'Added a character',
  dialogue_update: 'Edited dialogue',
  graphics_analyze: 'Checked graphics limits',
  toolchain_prepare: 'Installed the toolchain',
  toolchain_doctor: 'Checked the toolchain',
  device: 'Checked the Chromatic',
  play: 'Streamed to the Chromatic',
  flash: 'Wrote the cartridge'
}

const WORKING_LABELS = {
  rom_build: 'Building the ROM…',
  web_build: 'Building the player…',
  emulator_step: 'Playing the game…',
  emulator_run: 'Starting the emulator…',
  toolchain_prepare: 'Installing the toolchain…',
  flash: 'Writing the cartridge…',
  play: 'Streaming to the Chromatic…'
}

const KIND_ICONS = {
  read: 'eye',
  'project-write': 'edit',
  runtime: 'play',
  prepare: 'cloud-download',
  select: 'folder-opened',
  hardware: 'plug'
}

function toolLabel(tool) {
  return TOOL_LABELS[tool] ?? String(tool ?? '').replaceAll('_', ' ')
}

function ago(seconds, now) {
  const elapsed = Math.max(0, Math.round(now / 1000 - seconds))

  if (elapsed < 5) {
    return 'just now'
  }

  if (elapsed < 60) {
    return `${elapsed}s ago`
  }

  if (elapsed < 3600) {
    return `${Math.round(elapsed / 60)} min ago`
  }

  return `${Math.round(elapsed / 3600)} h ago`
}

/** One shared poll for both panes, running only while one of them is on screen. */
function useActivity(paneId) {
  const gateway = useValue(host.state.gateway)
  const chat = useValue(host.state.focusedSessionId)
  const stored = useValue(host.state.focusedStoredSessionId)
  const visible = useValue(
    typeof host.paneVisibility === 'function' ? host.paneVisibility(`${ID}:${paneId}`) : ALWAYS_VISIBLE
  )

  return useQuery({
    queryKey: [ID, 'activity', chat ?? null, stored ?? null],
    queryFn: () => fetchActivity(chat, stored),
    enabled: gateway === 'open' && visible !== false,
    refetchInterval: 1_500,
    staleTime: 1_000,
    retry: false
  })
}

function PaneShell({ children }) {
  return jsx(ScrollArea, {
    className: 'h-full',
    style: { height: '100%' },
    children: jsx('div', {
      style: { boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, padding: 12 },
      children
    })
  })
}

/** What to show instead of a game: backend off, not started, or nothing happening yet. */
function paneNotice(activity) {
  if (activity.isError) {
    const { message, notLoaded } = describeRequestError(activity.error)

    return notLoaded ? 'hermretro is not switched on. Open its page to set it up.' : `Could not read the studio state: ${message}`
  }

  const data = activity.data

  if (!data) {
    return 'Checking…'
  }

  if (data.ok === false) {
    return `Could not read the studio state: ${data.error ?? 'unknown error'}`
  }

  return data.lane ? null : 'No game is open yet. Ask Hermes to create or open one and it will appear here.'
}

// The last screen Hermes saw in its own (headless) playtest. The game you play is in the Studio emulator.
function TestScreen({ frame, now }) {
  return jsxs('div', {
    style: { ...S.col, gap: 4 },
    children: [
      jsx('div', {
        style: {
          alignItems: 'center',
          aspectRatio: '160 / 144',
          background: C.fill,
          border: `1px solid ${C.stroke}`,
          borderRadius: 6,
          display: 'flex',
          justifyContent: 'center',
          overflow: 'hidden',
          width: '100%'
        },
        children: frame
          ? jsx('img', {
              alt: 'What Hermes last saw in its playtest',
              src: frame.src,
              style: { height: '100%', imageRendering: 'pixelated', objectFit: 'contain', width: '100%' }
            })
          : jsx('span', {
              style: { ...S.faint, padding: 12, textAlign: 'center' },
              children: 'The last screen Hermes saw in its playtest appears here.'
            })
      }),
      frame
        ? jsx('span', {
            style: S.faint,
            children: `What Hermes last saw${Number.isFinite(frame.frame) ? ` · frame ${frame.frame}` : ''} · ${ago(frame.t, now)}`
          })
        : null
    ]
  })
}

function GamePane({ ctx }) {
  const activity = useActivity(PANE_GAME)
  const notice = paneNotice(activity)
  const now = activity.dataUpdatedAt || 0

  if (notice) {
    return jsxs(PaneShell, {
      children: [
        jsx('span', { style: S.muted, children: notice }),
        activity.data?.ok && !activity.data.lane
          ? jsx(PromptActions, { ctx, primaryLabel: 'Start a game', primaryVariant: 'default', prompt: NEW_GAME_PROMPT })
          : jsx('div', {
              children: jsx(Button, {
                onClick: () => host.navigate(ROUTE),
                size: 'sm',
                variant: 'outline',
                children: 'Open hermretro'
              })
            })
      ]
    })
  }

  const { lane, frame, build, matched } = activity.data
  const working = lane.busy ? (WORKING_LABELS[lane.current_tool] ?? 'Working…') : null

  return jsxs(PaneShell, {
    children: [
      jsxs('div', {
        style: { ...S.col, gap: 2 },
        children: [
          jsxs('div', {
            style: { ...S.row, justifyContent: 'space-between' },
            children: [
              jsx('span', {
                style: { color: C.primary, fontSize: 13, fontWeight: 600, overflowWrap: 'anywhere' },
                children: lane.project_name ?? 'No project selected'
              }),
              working
                ? jsxs('span', {
                    style: { ...S.row, ...S.faint, color: C.secondary, gap: 4 },
                    children: [jsx(Codicon, { name: 'loading', size: 12, spinning: true }), working]
                  })
                : null
            ]
          }),
          lane.project_root ? jsx('span', { style: { ...S.faint, overflowWrap: 'anywhere' }, children: lane.project_root }) : null,
          matched === 'recent'
            ? jsx('span', { style: S.faint, children: 'This chat has no game yet. Showing the most recent Chromatic chat.' })
            : null
        ]
      }),
      jsx(TestScreen, { frame, now }),
      build
        ? jsxs('div', {
            style: { ...S.row, gap: 6 },
            children: [
              jsx(StateIcon, { state: build.ok ? 'done' : 'error' }),
              jsxs('div', {
                style: { ...S.col, flex: 1, gap: 2 },
                children: [
                  jsx('span', {
                    style: { color: C.secondary, fontSize: 12.5 },
                    children: build.ok ? `Last build succeeded · ${ago(build.t, now)}` : `Last build failed · ${ago(build.t, now)}`
                  }),
                  build.ok && build.rom ? jsx('span', { style: { ...S.faint, overflowWrap: 'anywhere' }, children: build.rom }) : null,
                  !build.ok && build.error ? jsx('span', { style: { ...S.faint, color: C.bad }, children: build.error }) : null
                ]
              })
            ]
          })
        : jsx('span', { style: S.faint, children: 'No build yet in this chat.' }),
      jsx(Separator, {}),
      jsxs('div', {
        style: { ...S.col, gap: 6 },
        children: [
          jsx(PromptActions, { ctx, primaryLabel: 'Build and playtest', primaryVariant: 'default', prompt: BUILD_PLAYTEST_PROMPT }),
          jsx(PromptActions, { ctx, primaryLabel: 'Play it myself', prompt: PLAY_PROMPT }),
          jsx('span', {
            style: S.faint,
            children: 'These put a prompt in the chat. With "Play it myself" Hermes builds the game and shows it in the emulator beside the chat.'
          })
        ]
      })
    ]
  })
}

function LogPane() {
  const activity = useActivity(PANE_LOG)
  const notice = paneNotice(activity)
  const now = activity.dataUpdatedAt || 0

  if (notice) {
    return jsx(PaneShell, { children: jsx('span', { style: S.muted, children: notice }) })
  }

  const events = [...(activity.data.events ?? [])].reverse()

  return jsx(PaneShell, {
    children: events.length
      ? jsx('div', {
          role: 'log',
          style: { display: 'flex', flexDirection: 'column' },
          children: events.map((event, index) =>
            jsxs(
              'div',
              {
                style: {
                  alignItems: 'flex-start',
                  borderTop: index ? `1px solid ${C.stroke}` : 0,
                  display: 'flex',
                  gap: 8,
                  minWidth: 0,
                  padding: '6px 0'
                },
                children: [
                  jsx('span', {
                    style: { color: event.ok ? C.tertiary : C.bad, display: 'inline-flex', paddingTop: 2 },
                    children: jsx(Codicon, { name: event.ok ? (KIND_ICONS[event.kind] ?? 'circle-filled') : 'error', size: 13 })
                  }),
                  jsxs('div', {
                    style: { ...S.col, flex: 1, gap: 1 },
                    children: [
                      jsx('span', {
                        style: { color: event.ok ? C.secondary : C.bad, fontSize: 12.5 },
                        children: event.ok ? toolLabel(event.tool) : `Failed: ${toolLabel(event.tool)}`
                      }),
                      !event.ok && event.error ? jsx('span', { style: S.faint, children: event.error }) : null
                    ]
                  }),
                  jsx('span', { style: { ...S.faint, flexShrink: 0 }, children: ago(event.t, now) })
                ]
              },
              `${event.t}-${index}`
            )
          )
        })
      : jsx('span', { style: S.muted, children: 'Nothing has happened in this game yet.' })
  })
}

// ── Shared page pieces ────────────────────────────────────────────────────────

function Footer({ ctx }) {
  return jsxs('footer', {
    className: 'cs-foot',
    children: [
      jsxs('div', {
        className: 'cs-row',
        style: { gap: 16 },
        children: [
          jsx(ExternalLink, { ctx, href: LINKS.quickstart, children: 'ModRetro Chromatic quickstart' }),
          jsx(ExternalLink, { ctx, href: LINKS.showcase, children: 'Games showcase' })
        ]
      }),
      jsx('p', {
        className: 'cs-faint',
        children:
          'For original, user-created ROMs only. Do not use it for piracy or commercial games. Developer Mode is at your own risk. hermretro is an independent plugin and is not made or endorsed by ModRetro.'
      })
    ]
  })
}

function PageHead({ number, label, title, lede, children }) {
  return jsxs('div', {
    className: 'cs-page-head',
    children: [
      jsxs('div', {
        className: 'cs-col',
        children: [
          jsxs('p', { className: 'cs-eyebrow', children: [jsx('span', { className: 'cs-accent', children: number }), label] }),
          jsx('h2', { className: 'cs-word cs-title', children: title }),
          lede ? jsx(Lede, { children: lede }) : null
        ]
      }),
      children ? jsx('div', { className: 'cs-row', children }) : null
    ]
  })
}

/** A game's title screen, or a plain stand-in until the player has saved one. */
function Screen({ game, className = 'cs-screen' }) {
  return game?.thumb
    ? jsx('img', { alt: `${game.title} title screen`, className, src: game.thumb })
    : jsx('span', { 'aria-hidden': true, className: `${className} ph`, children: game?.title ?? '' })
}

function StateTag({ game }) {
  const [tone, label] = GAME_STATES[game.state] ?? GAME_STATES.unbuilt

  return jsx('span', { className: `cs-tag ${tone}`, children: label })
}

/** A button that runs an async action once at a time. */
function AsyncButton({ run, disabled, icon, title, variant = 'outline', children }) {
  const [pending, setPending] = useState(false)

  return jsx(Tip, {
    label: title ?? children,
    children: jsx('span', {
      style: { display: 'inline-flex' },
      children: jsxs(Button, {
        disabled: disabled || pending,
        onClick: async () => {
          setPending(true)

          try {
            await run()
          } finally {
            setPending(false)
          }
        },
        size: 'sm',
        variant,
        'aria-label': icon && typeof children === 'string' ? children : undefined,
        children: [icon ? jsx(Codicon, { name: pending ? 'loading' : icon, size: 14, spinning: pending }) : null, icon ? jsx('span', { className: 'cs-lbl', children }) : children]
      })
    })
  })
}

// ── Home ──────────────────────────────────────────────────────────────────────

const QUICK_STARTS = [
  { id: 'start', title: 'Start a new game', text: 'Hermes asks what you want to make, creates it and shows the first frame.' },
  { id: 'remix', title: 'Remix an example', text: 'Start from Wrecklight and make it your own.' },
  { id: 'plan', title: 'Plan a game', text: 'A short interview, then a brief, backlog and test plan.' },
  { id: 'play-game', title: 'Play my game', text: 'Hermes builds the selected game and shows it to you in the emulator beside the chat.' }
]

function SetupBar({ steps, autoId }) {
  return jsx('div', {
    'aria-hidden': true,
    className: 'cs-bar7',
    children: steps.map(step => jsx('i', { className: step.complete ? 'on' : step.id === autoId ? 'cur' : '' }, step.id))
  })
}

function ContinuePanel({ ctx, steps, auto, autoId, choosing, games, onGo, onPlay }) {
  if (auto) {
    // The next step by name; the bar under it shows where it sits (the hero counts the done steps).
    const title = choosing ? 'Emulator or Chromatic?' : `Next: ${STEP_SHORT[auto.id]}`

    return [
      jsx('p', { className: 'cs-eyebrow', children: jsx('span', { className: 'cs-accent', children: 'Continue setup' }) }, 'e'),
      jsx('h3', { className: 'cs-word', style: { fontSize: 'clamp(24px, 2.4cqi, 40px)' }, children: title }, 'h'),
      jsx(SetupBar, { autoId, steps }, 'bar'),
      jsx(
        Small,
        {
          children: choosing
            ? 'The emulator is ready. Choose whether to set up a physical Chromatic too.'
            : auto.hardware
              ? 'Only for a physical Chromatic. You can skip it and use the emulator.'
              : 'The page installs what is missing inside the plugin, then moves on by itself.'
        },
        's'
      ),
      jsx('div', { className: 'cs-actions', children: jsx(Button, { onClick: () => onGo('setup'), size: 'sm', variant: 'default', children: 'Continue setup' }) }, 'a')
    ]
  }

  const eyebrow = jsx('p', { className: 'cs-eyebrow', children: jsx('span', { className: 'cs-accent', children: 'Continue' }) }, 'e')

  if (games.isError || games.data?.games === undefined) {
    return [
      eyebrow,
      games.isError
        ? jsx(Small, { children: studioError(games.error, 'list your games') }, 'err')
        : jsx(Working, { quiet: true, children: 'Reading your games…' }, 'wait')
    ]
  }

  const game = latestGame(games.data.games)

  if (!game) {
    return [
      eyebrow,
      jsx('h3', { className: 'cs-word', style: { fontSize: 'clamp(24px, 2.4cqi, 40px)' }, children: 'No games yet' }, 'h'),
      jsx(Small, { children: 'Games you make with Hermes land here, ready to play on the Emulator page.' }, 's'),
      jsx('div', { className: 'cs-actions', children: jsx(PromptButton, { ctx, label: 'Start a new game', prompt: NEW_GAME_PROMPT, variant: 'default' }) }, 'a')
    ]
  }

  return [
    eyebrow,
    jsxs(
      'div',
      {
        className: 'cs-cont',
        children: [
          jsx(Screen, { game }),
          jsxs('div', {
            className: 'cs-col',
            style: { gap: 10 },
            children: [
              jsx('h3', { className: 'name', children: game.title }),
              jsxs('div', { className: 'cs-row', style: { gap: 10 }, children: [jsx(StateTag, { game }), jsx('span', { className: 'cs-meta', children: gameMeta(game).join(' · ') })] }),
              game.chat?.title ? jsx('span', { className: 'cs-faint', children: `Chat: ${game.chat.title}` }) : null,
              jsxs('div', {
                className: 'cs-actions',
                children: [
                  game.chat ? jsx(AsyncButton, { icon: 'comment-discussion', run: () => openGameChat(game), title: 'Open the chat this game was made in', variant: 'default', children: 'Open chat' }) : null,
                  jsxs(Button, {
                    disabled: game.state === 'unbuilt',
                    onClick: () => onPlay(game.id),
                    size: 'sm',
                    variant: game.chat ? 'outline' : 'default',
                    children: [jsx(Codicon, { name: 'play', size: 14 }), 'Play']
                  })
                ]
              })
            ]
          })
        ]
      },
      'cont'
    )
  ]
}

/** A plain button that puts a prompt into a chat. */
function PromptButton({ ctx, label, prompt, variant = 'outline', fresh = false, disabled }) {
  return jsx(AsyncButton, { disabled, icon: 'comment-discussion', run: () => sendPromptToChat(ctx, prompt, { fresh }), title: 'Puts the prompt in a chat, not sent', variant, children: label })
}

function HomePage({ ctx, steps, auto, autoId, choosing, status, doctor, memory, games, onGo, onPlay, onOpenPrompt, onSetUpDevice }) {
  const ready = !auto
  const hardwareOn = Boolean(status.data?.hardware_enabled)
  const emulatorOnly = Boolean(memory.hardwareSkipped) && !hardwareOn
  // Steps verified done, not skipped ones. The Chromatic steps count only for someone setting one up.
  const counted = steps.filter(step => !step.hardware || memory.hardwareWanted || hardwareOn)
  const done = counted.filter(step => step.state === 'done').length
  const [busy, setBusy] = useState(null)

  const quick = async item => {
    if (item.id === 'remix') {
      onOpenPrompt('remix')

      return
    }

    setBusy(item.id)

    try {
      await sendPromptToChat(ctx, item.id === 'start' ? NEW_GAME_PROMPT : promptById(item.id).text)
    } finally {
      setBusy(null)
    }
  }

  const toolchain = toolchainState(status.data, doctor)
  const gameCount = games.data?.games?.length
  const statRow = (term, tone, value) =>
    jsxs('div', { children: [jsx('dt', { children: term }), jsxs('dd', { title: String(value), children: [jsx('i', { className: tone }), value] })] }, term)

  return jsxs('div', {
    className: 'cs-home',
    children: [
      jsxs('div', {
        className: 'cs-hero',
        children: [
          jsxs('div', {
            className: 'cs-col',
            children: [
              jsxs('p', {
                className: 'cs-eyebrow',
                children: [
                  jsx('span', { className: 'cs-accent', children: '●' }),
                  ready ? (emulatorOnly ? 'Ready to make games in the emulator' : 'Setup is complete') : `Setup: ${done} of ${counted.length} done`
                ]
              }),
              jsxs('h2', {
                className: 'cs-word',
                children: ['Make a game.', jsx('br', {}), jsx('span', { className: 'cs-accent', children: 'Play it tonight.' })]
              }),
              jsx(Lede, {
                children:
                  'Build your game by chatting. Hermes builds and playtests it; you play it on the Emulator page, with sound, or on your Chromatic.'
              }),
              jsxs('div', {
                className: 'cs-actions',
                children: [
                  ready
                    ? jsx(PromptButton, { ctx, fresh: true, label: 'Start a new game', prompt: NEW_GAME_PROMPT, variant: 'default' })
                    : jsx(Button, { onClick: () => onGo('setup'), size: 'sm', variant: 'default', children: 'Continue setup' }),
                  ready && emulatorOnly ? jsx(Small, { children: 'Your Chromatic is not set up, so streaming and flashing are off.' }) : null,
                  ready && emulatorOnly ? jsx(Button, { onClick: onSetUpDevice, size: 'sm', variant: 'outline', children: 'Set up my Chromatic' }) : null
                ]
              })
            ]
          }),
          jsx(Art, {})
        ]
      }),
      jsxs('div', {
        className: 'cs-band',
        children: [
          jsx('section', { children: ContinuePanel({ ctx, auto, autoId, choosing, games, onGo, onPlay, steps }) }),
          jsxs('section', {
            children: [
              jsxs('p', { className: 'cs-eyebrow', children: ['Start something', ready ? null : jsx('span', { className: 'cs-draft', children: 'after setup' })] }),
              jsx('div', {
                className: 'cs-quick',
                children: QUICK_STARTS.map(item =>
                  jsxs(
                    'button',
                    {
                      disabled: !ready || busy !== null,
                      onClick: () => void quick(item),
                      type: 'button',
                      children: [
                        jsx('span', { className: 't', children: item.title }),
                        jsx('span', { className: 'a', children: item.id === 'remix' ? 'Open prompt →' : busy === item.id ? 'Opening…' : 'Use in chat →' }),
                        jsx('span', { className: 'd', children: item.text })
                      ]
                    },
                    item.id
                  )
                )
              }),
              jsx('div', { children: jsx('button', { className: 'cs-link', onClick: () => onGo('prompts'), type: 'button', children: `All ${ALL_PROMPTS.length} prompts →` }) })
            ]
          }),
          jsxs('section', {
            children: [
              jsx('p', { className: 'cs-eyebrow', children: 'Studio' }),
              jsxs('dl', {
                className: 'cs-stat',
                children: [
                  statRow('Setup', ready ? 'good' : 'warn', `${done} of ${counted.length} done`),
                  statRow('Profile', status.data?.profile?.is_studio === false ? 'warn' : 'good', status.data?.profile?.name ?? status.data?.via_profile ?? 'this profile'),
                  statRow('Toolchain', { done: 'good', todo: 'warn', error: 'bad' }[toolchain] ?? '', { done: 'ready', todo: 'missing', error: 'check failed' }[toolchain] ?? 'checking…'),
                  statRow('Chromatic', hardwareOn ? 'good' : '', hardwareOn ? 'on' : emulatorOnly ? 'emulator only' : 'not set up'),
                  statRow('Games', '', gameCount === undefined ? (games.isError ? 'unavailable' : '…') : String(gameCount))
                ]
              }),
              jsxs('div', {
                className: 'cs-row',
                style: { gap: 14 },
                children: [
                  jsx('button', { className: 'cs-link', onClick: () => onGo('setup'), type: 'button', children: 'Setup →' }),
                  jsx('button', { className: 'cs-link', onClick: () => onGo('games'), type: 'button', children: 'Games →' })
                ]
              })
            ]
          })
        ]
      })
    ]
  })
}

// ── Setup ─────────────────────────────────────────────────────────────────────

/** Everything is verified (or the Chromatic part was skipped). */
function SetupComplete({ steps, status, doctor, emulatorOnly, onRecheck, rechecking, onSetUpDevice, onGo }) {
  const data = status.data ?? {}
  const report = doctor.data?.ok ? doctor.data : null
  const tools = (report?.components ?? [])
    .filter(component => component.status === 'ready' && !component.optional && component.id !== 'node' && component.id !== 'runtime')
    .map(component => `${component.label ?? component.id} ${component.detected ?? ''}`.trim())
  const cli = data.deps?.device_cli

  return jsxs('section', {
    'aria-live': 'polite',
    className: 'cs-stage',
    children: [
      jsxs('div', {
        className: 'cs-stage-head',
        children: [
          jsxs('p', {
            className: 'cs-eyebrow',
            children: [
              jsx('span', { className: 'cs-accent', children: '●' }),
              emulatorOnly ? `Steps 1–2 done · emulator only` : `All ${steps.length} steps done`
            ]
          }),
          jsx('h2', { className: 'cs-word cs-title', children: 'Setup is complete' })
        ]
      }),
      jsx(Lede, {
        children: emulatorOnly
          ? 'Everything the emulator needs is installed and verified. A Chromatic is optional: set it up any time to stream games to it and write cartridges. Open any step to review it.'
          : 'Everything is installed and verified, including your Chromatic. Open any step to review it.'
      }),
      jsx(Facts, {
        rows: [
          ['Profile', data.profile?.name ?? data.via_profile ?? 'this profile'],
          ['Toolchain', [tools.join(' · '), data.engine?.version ? `engine ${data.engine.version}` : ''].filter(Boolean).join(' · ') || 'Ready'],
          [
            'Chromatic',
            data.hardware_enabled
              ? `Device software${cli?.version ? ` ${cli.version}` : ''} · hardware tools on`
              : 'Not set up: streaming and flashing are off'
          ]
        ]
      }),
      jsxs('div', {
        className: 'cs-actions',
        children: [
          jsx(Button, { onClick: () => onGo('home'), size: 'sm', variant: 'default', children: 'Go to the studio' }),
          jsxs(Button, {
            disabled: rechecking,
            onClick: onRecheck,
            size: 'sm',
            variant: 'ghost',
            children: [jsx(Codicon, { name: 'refresh', size: 14, spinning: rechecking }), 'Check everything again']
          }),
          emulatorOnly ? jsx(Button, { onClick: onSetUpDevice, size: 'sm', variant: 'outline', children: 'Set up my Chromatic' }) : null
        ]
      })
    ]
  })
}

// ── Prompts: Reader ───────────────────────────────────────────────────────────

function fillPrompt(prompt, values) {
  return prompt.text.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? `{${key}}`)
}

function promptFields(prompt) {
  return [...new Set([...prompt.text.matchAll(/\{(\w+)\}/g)].map(match => match[1]))]
}

const WHAT_HAPPENS = {
  device: 'Hermes asks for your approval before it touches the device, unless Approvals are turned off.',
  create: 'Hermes creates the project in that folder, selects it for the chat and builds the first ROM. It then shows up on the Games page.',
  other: 'Works on the game selected in that chat. Start with Create if the chat has none yet.'
}

function PromptsPage({ ctx, storage, selected, onSelect, gameReady, hardwareOn, profileLabel, defaultFolder, onSetUpDevice, onGo }) {
  const [query, setQuery] = useState('')
  const [edits, setEdits] = useState({})
  const [names, setNames] = useState({})
  const [folder, setFolder] = useState(() => {
    try {
      return storage.get('promptFolder', null)
    } catch {
      return null
    }
  })
  const listRef = useRef(null)

  const needle = query.trim().toLowerCase()
  const matches = prompt => !needle || `${prompt.title} ${prompt.text} ${prompt.section.title}`.toLowerCase().includes(needle)
  const visible = ALL_PROMPTS.filter(matches)
  const prompt = visible.find(item => item.id === selected) ?? visible[0] ?? promptById(selected)
  const locked = Boolean(prompt.hw) && !hardwareOn
  const values = { folder: folder ?? defaultFolder ?? '~', name: names[prompt.id] ?? prompt.defaults?.name ?? 'MyGame' }
  const text = edits[prompt.id] ?? fillPrompt(prompt, values)
  const fields = promptFields(prompt)
  const canChat = gameReady && !locked

  const state = useRef({})

  state.current = { visible, prompt, onSelect }

  // ↑ / ↓ move through the list (not while typing).
  useEffect(() => {
    const onKey = event => {
      if ((event.key !== 'ArrowDown' && event.key !== 'ArrowUp') || event.metaKey || event.ctrlKey || event.altKey) {
        return
      }

      const target = event.target

      if (target && (target.isContentEditable || /^(TEXTAREA|SELECT)$/.test(target.tagName ?? '') || (target.tagName === 'INPUT' && target.type !== 'search'))) {
        return
      }

      const { visible: list, prompt: current, onSelect: select } = state.current
      const index = list.findIndex(item => item.id === current.id)
      const next = list[Math.max(0, Math.min(list.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))]

      if (next) {
        event.preventDefault()
        select(next.id)
        ctx.setTimeout(() => listRef.current?.querySelector?.(`[data-prompt="${next.id}"]`)?.focus?.(), 0)
      }
    }

    window.addEventListener('keydown', onKey)

    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const setField = (key, value) => {
    setEdits(previous => ({ ...previous, [prompt.id]: undefined }))

    if (key === 'folder') {
      setFolder(value)

      try {
        storage.set('promptFolder', value)
      } catch {
        // remembered for this visit only
      }
    } else {
      setNames(previous => ({ ...previous, [prompt.id]: value }))
    }
  }

  const groups = PROMPT_SECTIONS.map(section => ({ section, items: visible.filter(item => item.section === section) })).filter(group => group.items.length)

  return [
    jsx(PageHead, {
      label: `Prompts · ${ALL_PROMPTS.length} ready to use`,
      lede: jsxs('span', {
        children: [
          'Every prompt opens a chat in ',
          jsx('span', { className: 'cs-mono', children: profileLabel }),
          ' with the text in its composer, ready for you to edit and send. Or copy it and paste it anywhere.'
        ]
      }),
      number: '02',
      title: 'Start building'
    }, 'head'),
    jsxs(
      'div',
      {
        className: 'cs-reader',
        children: [
          jsxs('nav', {
            'aria-label': 'Prompts',
            className: 'cs-rlist',
            ref: listRef,
            children: [
              jsxs('label', {
                className: 'cs-search',
                children: [
                  jsx(Codicon, { name: 'search', size: 14 }),
                  jsx('input', { 'aria-label': 'Find a prompt', onChange: event => setQuery(event.target.value), placeholder: 'Find a prompt', type: 'search', value: query })
                ]
              }),
              groups.length
                ? groups.flatMap(({ section, items }, index) => [
                    jsxs('span', { className: index ? 'cs-rgrp' : 'cs-rgrp first', children: [jsx('span', { children: section.title }), jsx('span', { children: items.length })] }, `g-${section.id}`),
                    ...items.map(item =>
                      jsxs(
                        'button',
                        {
                          'aria-current': item.id === prompt.id ? 'true' : undefined,
                          className: item.hw && !hardwareOn ? 'cs-ritem off' : 'cs-ritem',
                          'data-prompt': item.id,
                          onClick: () => onSelect(item.id),
                          type: 'button',
                          children: [jsx('span', { children: item.title }), item.hw && !hardwareOn ? jsx('span', { className: 'cs-tag quiet', children: 'device' }) : null]
                        },
                        item.id
                      )
                    )
                  ])
                : jsx(Small, { children: 'No prompts match.' }),
              jsxs('p', {
                className: 'cs-faint',
                style: { paddingTop: 18 },
                children: [jsx('span', { className: 'cs-key', children: '↑' }), ' ', jsx('span', { className: 'cs-key', children: '↓' }), ' to move through the list']
              })
            ]
          }),
          jsxs('section', {
            'aria-label': prompt.title,
            className: 'cs-rdetail',
            children: [
              jsxs('div', {
                className: 'cs-col',
                style: { gap: 10 },
                children: [
                  jsxs('p', {
                    className: 'cs-eyebrow',
                    children: [
                      jsx('span', { className: 'cs-accent', children: prompt.section.n }),
                      prompt.section.title,
                      jsx('span', { className: 'cs-tag quiet', children: prompt.src === 'modretro' ? 'ModRetro quickstart' : 'Hermes' }),
                      locked ? jsx('span', { className: 'cs-tag warn', children: 'Needs your Chromatic' }) : null
                    ]
                  }),
                  jsx('h3', { className: 'cs-word', style: { fontSize: 'clamp(28px, 3cqi, 52px)' }, children: prompt.title })
                ]
              }),
              fields.length
                ? jsx('div', {
                    className: 'cs-params',
                    children: fields.flatMap(key => [
                      jsx('label', { htmlFor: `cs-f-${key}`, children: key === 'folder' ? 'Parent folder' : 'Project name' }, `l-${key}`),
                      jsx('input', { id: `cs-f-${key}`, onChange: event => setField(key, event.target.value), spellCheck: false, value: values[key] }, `i-${key}`)
                    ])
                  })
                : null,
              jsx('textarea', {
                'aria-label': 'Prompt text',
                onChange: event => setEdits(previous => ({ ...previous, [prompt.id]: event.target.value })),
                spellCheck: false,
                value: text
              }),
              prompt.note ? jsx('p', { className: 'cs-faint', children: prompt.note }) : null,
              jsxs('div', {
                className: 'cs-actions',
                children: [
                  jsx(PromptButton, { ctx, disabled: !canChat, fresh: true, label: 'Start a new chat', prompt: text, variant: 'default' }),
                  jsx(AsyncButton, {
                    disabled: !canChat,
                    icon: 'insert',
                    run: () => sendPromptToChat(ctx, text),
                    title: 'Adds the prompt to the hermretro chat you were last in, else a new one',
                    variant: 'secondary',
                    children: 'Add to current chat'
                  }),
                  jsx(CopyButton, { buttonSize: 'sm', buttonVariant: 'outline', label: 'Copy', text }),
                  jsx('span', { className: 'cs-grow' }),
                  edits[prompt.id] !== undefined
                    ? jsx(Button, { onClick: () => setEdits(previous => ({ ...previous, [prompt.id]: undefined })), size: 'sm', variant: 'ghost', children: 'Reset text' })
                    : null
                ]
              }),
              locked
                ? jsxs('div', {
                    className: 'cs-note',
                    children: [
                      jsx(Small, { children: 'Streaming and flashing need your Chromatic set up. You can still read and copy those prompts.' }),
                      jsx(Button, { onClick: onSetUpDevice, size: 'sm', variant: 'outline', children: 'Set up my Chromatic' })
                    ]
                  })
                : !gameReady
                  ? jsxs('div', {
                      className: 'cs-note',
                      children: [
                        jsx(Small, { children: 'After setup: these prompts need the game toolchain, so the chat buttons turn on once it is installed.' }),
                        jsx(Button, { onClick: () => onGo('setup'), size: 'sm', variant: 'outline', children: 'Continue setup' })
                      ]
                    })
                  : null,
              jsxs('div', {
                className: 'cs-uses',
                children: [
                  jsx('p', { className: 'cs-eyebrow', children: 'What happens' }),
                  jsx(Small, { children: prompt.hw ? WHAT_HAPPENS.device : prompt.section.id === 'create' ? WHAT_HAPPENS.create : WHAT_HAPPENS.other }),
                  jsx('span', { className: 'cs-faint', children: 'Nothing is sent until you press send in the chat.' })
                ]
              })
            ]
          }),
          jsx(Art, {})
        ]
      },
      'reader'
    )
  ]
}

// ── Games: Shelf ──────────────────────────────────────────────────────────────

function DeviceStrip({ hardwareOn, onSetUpDevice }) {
  return hardwareOn
    ? jsxs('div', {
        className: 'cs-dev on',
        children: [
          jsx('span', { className: 'dot' }),
          jsx('span', { className: 'nm', children: 'Chromatic hardware tools are on' }),
          jsx(Small, { children: "Install puts the flash prompt in the game's chat. Hermes asks before it writes the cartridge, unless Approvals are off." })
        ]
      })
    : jsxs('div', {
        className: 'cs-dev',
        children: [
          jsx('span', { className: 'dot' }),
          jsx('span', { className: 'nm', children: 'Playing in the emulator.' }),
          jsx(Small, { children: 'Set up a Chromatic to install games on a real cartridge.' }),
          jsx('span', { className: 'cs-grow' }),
          jsx(Button, { onClick: onSetUpDevice, size: 'sm', variant: 'outline', children: 'Set up my Chromatic' })
        ]
      })
}

function InstallButton({ ctx, game, hardwareOn, label = 'Install' }) {
  return jsx(AsyncButton, {
    disabled: !hardwareOn || !game.rom,
    icon: 'desktop-download',
    run: () => sendToGameChat(ctx, game, installPrompt(game)),
    title: !hardwareOn ? 'Needs your Chromatic' : !game.rom ? 'Build it first' : "Puts the flash prompt in this game's chat; Hermes asks before writing",
    variant: 'outline',
    children: label
  })
}

function GameCard({ ctx, game, hardwareOn, onPlay }) {
  const playable = game.state !== 'unbuilt' && game.state !== 'failed'
  const primary =
    game.state === 'failed'
      ? jsx(AsyncButton, { icon: 'tools', run: () => sendToGameChat(ctx, game, fixPrompt(game)), title: 'Puts the build error in its chat, not sent', variant: 'outline', children: 'Fix in chat' })
      : game.state === 'unbuilt'
        ? jsx(AsyncButton, { icon: 'play', run: () => sendToGameChat(ctx, game, buildPrompt(game)), title: 'Puts a build prompt in its chat, not sent', variant: 'default', children: 'Build in chat' })
        : jsxs(Button, { onClick: () => onPlay(game.id), size: 'sm', variant: 'default', children: [jsx(Codicon, { name: 'play', size: 14 }), 'Play'] })

  return jsxs('article', {
    className: 'cs-gcard',
    children: [
      jsxs('button', {
        'aria-label': playable ? `Play ${game.title}` : game.title,
        className: 'cs-cart',
        disabled: !playable,
        onClick: () => onPlay(game.id),
        type: 'button',
        children: [
          jsx('span', {
            className: 'slot',
            children: game.thumb
              ? jsx('img', { alt: `${game.title} title screen`, src: game.thumb })
              : jsxs('span', { className: 'ph', children: [game.title, jsx('small', { children: playable ? 'Title screen after first play' : 'No build yet' })] })
          }),
          playable ? jsx('span', { className: 'hov', children: jsx('span', { children: jsx(Codicon, { name: 'play', size: 22 }) }) }) : null
        ]
      }),
      jsxs('div', {
        className: 'info',
        children: [
          jsx('h3', { title: game.title, children: game.title }),
          jsx('div', { className: 'cs-row', style: { minHeight: 20 }, children: jsx(StateTag, { game }) }),
          jsx('div', { className: 'cs-meta', children: gameMeta(game).map(part => jsx('span', { children: part }, part)) }),
          game.state === 'failed' && game.error ? jsx('span', { className: 'cs-faint', title: game.error, children: game.error.slice(0, 120) }) : null
        ]
      }),
      jsxs('div', {
        className: 'cs-actions',
        style: { gap: 6 },
        children: [
          primary,
          game.state === 'failed' ? null : jsx(InstallButton, { ctx, game, hardwareOn }),
          jsx(Tip, {
            label: game.chat ? `Open its chat${game.chat.title ? `: ${game.chat.title}` : ''}` : 'No chat recorded for this game',
            children: jsx('span', {
              style: { display: 'inline-flex' },
              children: jsx(Button, {
                disabled: !game.chat,
                onClick: () => void openGameChat(game),
                size: 'sm',
                variant: 'ghost',
                children: jsx(Codicon, { name: 'comment-discussion', size: 14 })
              })
            })
          })
        ]
      })
    ]
  })
}

function GamesPage({ ctx, games, hardwareOn, onPlay, onOpenPrompt, onSetUpDevice }) {
  const list = games.data?.games
  const newGame = jsxs(Button, { onClick: () => onOpenPrompt('new-game'), size: 'sm', variant: 'default', children: [jsx(Codicon, { name: 'add', size: 14 }), 'New game'] })

  if (games.isError || (games.data && !Array.isArray(list))) {
    return [
      jsx(PageHead, { label: 'Games', number: '03', title: 'Your games' }, 'head'),
      jsxs('div', {
        className: 'cs-col',
        style: { gap: 12, maxWidth: '72ch' },
        children: [
          jsx(Lede, { children: games.isError ? studioError(games.error, 'list your games') : games.data?.error || 'The games list could not be read.' }),
          jsx('div', { children: newGame })
        ]
      }, 'err')
    ]
  }

  if (!list) {
    return [jsx(PageHead, { label: 'Games', number: '03', title: 'Your games' }, 'head'), jsx(Working, { quiet: true, children: 'Reading your games…' }, 'wait')]
  }

  if (!list.length) {
    return [
      jsx(DeviceStrip, { hardwareOn, onSetUpDevice }, 'dev'),
      jsxs(
        'div',
        {
          className: 'cs-empty',
          children: [
            jsxs('div', {
              className: 'cs-col',
              children: [
                jsxs('p', { className: 'cs-eyebrow', children: [jsx('span', { className: 'cs-accent', children: '03' }), 'Games'] }),
                jsx('h2', { className: 'cs-word cs-title', children: 'No games yet' }),
                jsx(Lede, {
                  children:
                    'Games you make with Hermes land here, ready to play in the emulator or install on your Chromatic. Start with a new game or remix the example.'
                }),
                jsxs('div', {
                  className: 'cs-actions',
                  children: [
                    jsx(Button, { onClick: () => onOpenPrompt('new-game'), size: 'sm', variant: 'default', children: 'Create a new game' }),
                    jsx(Button, { onClick: () => onOpenPrompt('remix'), size: 'sm', variant: 'outline', children: 'Remix Wrecklight' })
                  ]
                }),
                jsx('p', { className: 'cs-faint', children: 'Already have a GB Studio project? Ask Hermes to select it and it shows up here.' })
              ]
            }),
            jsx(Art, {})
          ]
        },
        'empty'
      )
    ]
  }

  return [
    jsx(PageHead, { label: `Games · ${list.length} in your studio`, number: '03', title: 'Your games', children: newGame }, 'head'),
    jsx(DeviceStrip, { hardwareOn, onSetUpDevice }, 'dev'),
    jsxs(
      'div',
      {
        className: 'cs-shelf',
        children: [
          ...list.map(game => jsx(GameCard, { ctx, game, hardwareOn, onPlay }, game.id)),
          jsxs(
            'article',
            {
              className: 'cs-gcard',
              children: [
                jsx('button', {
                  'aria-label': 'New game',
                  className: 'cs-cart ghost',
                  onClick: () => onOpenPrompt('new-game'),
                  type: 'button',
                  children: jsx('span', {
                    className: 'slot',
                    children: jsxs('span', {
                      className: 'cs-col',
                      style: { alignItems: 'center', gap: 8 },
                      children: [jsx(Codicon, { name: 'add', size: 26 }), jsx('span', { className: 'cs-eyebrow', children: 'New game' })]
                    })
                  })
                }),
                jsxs('div', {
                  className: 'info',
                  children: [
                    jsx('h3', { style: { color: 'var(--ui-text-tertiary)' }, children: 'Blank cartridge' }),
                    jsx('div', { className: 'cs-meta', children: jsx('span', { children: 'Make a new game with Hermes' }) })
                  ]
                })
              ]
            },
            'new'
          )
        ]
      },
      'shelf'
    )
  ]
}

// ── Emulator: ModRetro's real player in a sandboxed frame ─────────────────────

// Keys typed on the page (not inside the frame) still reach the game.
const GAME_KEYS = new Set(['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'z', 'Z', 'x', 'X', 'Enter', 'Shift', 'p', 'P'])

/** Talks to the player frame (protocol in docs/dev/STUDIO-PAGES.md): focus, snaps, annotate
 *  results and logs come in; keys, snap requests and hold/release go out. */
function usePlayerBridge({ ctx, frameRef, visible, onAnnotate, scopeRef = null }) {
  const [focused, setFocused] = useState(false)
  const snaps = useRef(new Map())
  const sequence = useRef(0)
  const latest = useRef({})
  // Beside the chat the page is shared with the chat: keys reach the game only after the user last
  // clicked inside the emulator tab, so arrows and Enter in the chat stay the chat's.
  const armed = useRef(!scopeRef)

  useEffect(() => {
    if (!scopeRef) {
      return undefined
    }

    const arm = event => {
      armed.current = Boolean(scopeRef.current && event.target && scopeRef.current.contains(event.target))
    }

    window.addEventListener('pointerdown', arm, true)
    window.addEventListener('focusin', arm, true)

    return () => {
      window.removeEventListener('pointerdown', arm, true)
      window.removeEventListener('focusin', arm, true)
    }
  }, [])

  latest.current = { onAnnotate }

  const post = useCallback(message => {
    try {
      frameRef.current?.contentWindow?.postMessage(message, '*')
    } catch {
      // the frame is gone or still loading
    }
  }, [])

  useEffect(() => {
    const onMessage = event => {
      const frame = frameRef.current
      const data = event.data

      if (!frame || event.source !== frame.contentWindow || !data || typeof data !== 'object' || !data.cs) {
        return
      }

      if (data.cs === 'focus') {
        setFocused(Boolean(data.value))
      } else if (data.cs === 'snap') {
        const resolve = snaps.current.get(data.id)

        if (resolve) {
          snaps.current.delete(data.id)
          resolve(typeof data.url === 'string' ? data.url : '')
        }
      } else if (data.cs === 'annotate') {
        void latest.current.onAnnotate?.(data)
      } else if (data.cs === 'log' && data.level === 'error') {
        console.warn('[Chromatic player]', String(data.text ?? '').slice(0, 500))
      }
    }

    window.addEventListener('message', onMessage)

    return () => window.removeEventListener('message', onMessage)
  }, [])

  useEffect(() => {
    if (!visible) {
      return undefined
    }

    const forward = event => {
      if (!GAME_KEYS.has(event.key) || event.metaKey || event.ctrlKey || event.altKey || !frameRef.current || !armed.current) {
        return
      }

      const target = event.target

      if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName ?? ''))) {
        return
      }

      event.preventDefault()

      if (!event.repeat) {
        post({ cs: 'cmd', type: 'key', key: event.key, code: event.code, down: event.type === 'keydown' })
      }
    }

    window.addEventListener('keydown', forward)
    window.addEventListener('keyup', forward)

    return () => {
      window.removeEventListener('keydown', forward)
      window.removeEventListener('keyup', forward)
    }
  }, [visible])

  // Leaving the page pauses the game and its sound; coming back resumes it (the frame stays loaded).
  const shown = useRef(visible)

  useEffect(() => {
    if (shown.current !== visible) {
      shown.current = visible
      post({ cs: 'cmd', type: visible ? 'release' : 'hold' })
    }
  }, [visible])

  const snap = useCallback(
    () =>
      new Promise(resolve => {
        const id = ++sequence.current

        snaps.current.set(id, resolve)
        post({ cs: 'cmd', type: 'snap', id })
        ctx.setTimeout(() => {
          if (snaps.current.has(id)) {
            snaps.current.delete(id)
            resolve('')
          }
        }, 2500)
      }),
    []
  )

  return { focused, snap }
}

/** Save a frame into the game's captures folder; the path goes into the chat text. */
async function saveCapture(game, png) {
  if (!png) {
    return { path: null, failure: 'the frame could not be captured' }
  }

  try {
    const result = await callStudio(RPC_CAPTURE_IMAGE, { id: game.id, png })

    return result?.path ? { path: result.path, failure: null } : { path: null, failure: result?.error || 'no path returned' }
  } catch (error) {
    return { path: null, failure: studioError(error, 'save screenshots') }
  }
}

function annotationText(game, data, path) {
  const target = data.target ?? {}
  const role = String(target.role ?? '').replace(/^game-/, '')
  const lines = [`In ${game.title}, I marked ${target.name || 'part of the screen'}${role ? ` (${role})` : ''}.`]

  if (data.note) {
    lines.push(String(data.note))
  }

  if (target.metadata && typeof target.metadata === 'object' && Object.keys(target.metadata).length) {
    lines.push(`Details: ${JSON.stringify(target.metadata).slice(0, 800)}`)
  }

  if (path) {
    lines.push(`Screenshot: ${path}`)
  }

  return lines.join('\n')
}

/** An annotation from the player: save the marked frame, then put the note into the game's chat. */
async function annotateGame(ctx, game, data) {
  if (!game) {
    return
  }

  const { path, failure } = await saveCapture(game, typeof data.image === 'string' ? data.image : '')

  await sendToGameChat(ctx, game, annotationText(game, data, path))

  if (failure) {
    host.notify({ kind: 'warning', message: `The screenshot was not saved: ${failure}` })
  }
}

/** Ask Hermes: the current frame and a line about it go into the game's chat, not sent. */
async function askAboutGame(ctx, game, snap) {
  if (!game) {
    return
  }

  const { path, failure } = await saveCapture(game, await snap())

  await sendToGameChat(ctx, game, [`Here is what ${game.title} shows right now.`, path ? `Screenshot: ${path}` : null].filter(Boolean).join('\n') + '\n')

  if (failure) {
    host.notify({ kind: 'warning', message: `The screenshot was not saved: ${failure}` })
  }
}

/** The ROM the player would load now: the web export's own (its ROM is a separate compilation, not the
 *  native build's bytes), else the last build for a backend that predates `web`. */
function playableSha(game) {
  return game?.web?.sha256 ?? game?.rom?.sha256 ?? null
}

/** Why the player RPC failed, worded for the person looking at the page; null while it has not. */
function playerFailure(game, player) {
  if (player?.isError) {
    return describeRequestError(player.error).notLoaded
      ? 'This profile is running an older copy of the hermretro backend. Reload the plugin (Capabilities › Plugins, switch it off and on) and press Refresh.'
      : studioError(player.error, 'run the player')
  }

  // A user's game without a web build keeps its own message (with "Build it in chat") in the stage.
  return game?.id === DEMO_ID && player?.data?.error ? String(player.data.error) : null
}

function PlayerNotice({ game, player, onRefresh, refreshing }) {
  const reason = playerFailure(game, player)

  if (!reason) {
    return null
  }

  return jsxs('div', {
    className: 'cs-rp-note',
    role: 'alert',
    children: [
      jsxs('div', { children: [jsx('b', { children: 'The player could not start' }), jsx('span', { children: reason })] }),
      jsxs(Button, { disabled: refreshing, onClick: onRefresh, size: 'sm', variant: 'outline', children: [jsx(Codicon, { name: 'refresh', size: 14 }), 'Refresh'] })
    ]
  })
}

function PlayerStage({ game, player, visible, frameRef, stageRef, frameKey, onLoad, ctx }) {
  let inner = null

  if (game) {
    const data = player?.data

    if (playerFailure(game, player)) {
      inner = jsx('div', { 'aria-hidden': true, className: 'cs-rp-void' })
    } else if (data?.error) {
      inner = jsxs('div', {
        className: 'cs-rp-msg',
        children: [
          jsx('p', { className: 'cs-eyebrow', children: 'The player could not start' }),
          jsx(Lede, { children: data.error }),
          jsx(AsyncButton, { icon: 'comment-discussion', run: () => sendToGameChat(ctx, game, buildPrompt(game)), variant: 'default', children: 'Build it in chat' })
        ]
      })
    } else if (data?.url) {
      inner = jsx(
        SandboxedFrame,
        { onLoad, ref: frameRef, sandbox: 'allow-scripts allow-downloads', src: data.url, title: `${game.title} in ModRetro's Chromatic player` },
        frameKey
      )
    } else {
      inner = jsx('div', { className: 'cs-rp-msg', children: jsx(Working, { children: `Starting the player for ${game.title}…` }) })
    }
  } else {
    inner = jsx('div', { className: 'cs-rp-msg', children: jsx(Working, { quiet: true, children: 'Reading your games…' }) })
  }

  return jsx('div', { 'aria-hidden': visible ? undefined : true, className: visible ? 'cs-rp-stage' : 'cs-rp-stage off', ref: stageRef, children: inner })
}

function Captures({ game, open }) {
  const captures = useQuery({
    queryKey: [ID, 'captures', game?.id ?? null],
    queryFn: () => callStudio(RPC_CAPTURES, { id: game.id }),
    enabled: Boolean(open && game),
    refetchInterval: open ? 5_000 : false,
    retry: false
  })

  if (!open) {
    return null
  }

  const list = captures.data?.captures ?? []

  return jsx('div', {
    className: 'cs-rp-caps',
    children: captures.isError
      ? jsx(Small, { children: studioError(captures.error, 'list captures') })
      : list.length
        ? list.map(capture =>
            jsxs(
              'figure',
              {
                children: [
                  capture.kind === 'screenshot' || /\.png$/i.test(capture.path ?? '')
                    ? jsx('img', { alt: '', src: capture.url })
                    : jsx('video', { controls: true, src: capture.url }),
                  jsx('figcaption', { title: capture.path, children: String(capture.path ?? '').split('/').pop() })
                ]
              },
              capture.path ?? capture.url
            )
          )
        : jsx(Small, {
            children: "Screenshots and videos you take with the camera and video buttons beside the device land here and in the game's captures folder."
          })
  })
}

/** The rebuilt banner and the bar above the player: only the player's controls. Below a narrow width
 *  the bar's buttons drop their labels (`.cs-lbl`) and keep their icons and tooltips. */
function EmulatorBar({ ctx, game, player, focused, hardwareOn, rebuilt, capturesOpen, onAsk, onToggleCaptures, onFull, onReload, onLater }) {
  const onDemo = game?.id === DEMO_ID

  return [
    rebuilt
      ? jsxs(
          'div',
          {
            className: 'cs-reload',
            role: 'status',
            children: [
              jsx('span', { className: 'dot' }),
              jsxs('span', { children: [jsx('b', { children: `Hermes rebuilt ${game.title}` }), jsx('span', { className: 'cs-small', children: ' · the player is still running the earlier build' })] }),
              jsx('span', { className: 'cs-grow' }),
              jsxs(Button, { onClick: onReload, size: 'sm', variant: 'default', children: [jsx(Codicon, { name: 'refresh', size: 14 }), 'Load the new build'] }),
              jsx(Button, { onClick: onLater, size: 'sm', variant: 'ghost', children: 'Later' })
            ]
          },
          'reload'
        )
      : null,
    jsxs(
      'div',
      {
        className: 'cs-rp-bar',
        children: [
          jsx('span', { className: 'cs-grow' }),
          jsx(Tip, {
            label: 'Lit while the player has keyboard focus. Keys typed on this page also reach the game.',
            children: jsxs('span', { className: focused ? 'cs-rp-focus on' : 'cs-rp-focus', children: [jsx('i', {}), jsx('span', { className: 'cs-lbl', children: 'Keyboard' })] })
          }),
          game && !onDemo ? jsx(InstallButton, { ctx, game, hardwareOn }) : null,
          jsx(AsyncButton, { disabled: !player?.data?.url, icon: 'comment-discussion', run: onAsk, title: "Puts this frame and a note into the game's chat, not sent", variant: 'ghost', children: 'Ask Hermes' }),
          jsx(Tip, {
            label: 'Screenshots and videos of this game',
            children: jsx('span', {
              style: { display: 'inline-flex' },
              children: jsxs(Button, {
                'aria-label': 'Captures',
                disabled: !game,
                onClick: onToggleCaptures,
                size: 'sm',
                variant: capturesOpen ? 'secondary' : 'ghost',
                children: [jsx(Codicon, { name: 'device-camera', size: 14 }), jsx('span', { className: 'cs-lbl', children: 'Captures' })]
              })
            })
          }),
          jsx(Tip, {
            label: 'Full screen',
            children: jsx('span', {
              style: { display: 'inline-flex' },
              children: jsx(Button, { 'aria-label': 'Full screen', disabled: !player?.data?.url, onClick: onFull, size: 'sm', variant: 'ghost', children: jsx(Codicon, { name: 'screen-full', size: 14 }) })
            })
          })
        ]
      },
      'bar'
    ),
    jsx(Captures, { game, open: capturesOpen }, 'caps')
  ]
}

// ── The emulator beside the chat ──────────────────────────────────────────────
// Opens only when the agent presents the game (`chromatic_present_game`), in a workspace tab docked
// right of the chat (`host.openWorkspace`). Builds open nothing: an open tab shows the rebuilt banner,
// and presenting again loads the newest build there directly, with the agent's note above the player.
// One game runs at a time: whichever surface opened last owns the live player.

const PRESENT_TOOL = 'chromatic_present_game'
const BUILD_TOOLS = new Set(['chromatic_rom_build', 'chromatic_web_preview'])
const RPC_PRESENTATIONS = `plugin.${ID}.presentations`
// The surface running the one live player: 'page', 'side:<game id>' or null.
const LIVE_PLAYER = atom(null)
// Bumped after every finished build or turn, so an open emulator asks for the library at once.
const BUILD_TICK = atom(0)
// Game id → the latest presentation the tab should show: { seq, note, t }.
const PRESENTED = atom({})
// Game id → close() of its open side tab.
const sideTabs = new Map()
// Presentations already acted on ('<game id>:<presentedAt>'), so the fallback never repeats one.
const presentationsSeen = new Set()
const sideSurface = id => `side:${id}`
const sideKey = id => `${ID}.emulator.${id}`

const claimLive = surface => {
  if (LIVE_PLAYER.get() !== surface) {
    LIVE_PLAYER.set(surface)
  }
}

const releaseLive = surface => {
  if (LIVE_PLAYER.get() === surface) {
    LIVE_PLAYER.set(null)
  }
}

/** A finished tool's result as an object (the gateway parses JSON results; a multimodal one keeps
 *  its text). */
function toolResultObject(value) {
  if (value && typeof value === 'object') {
    return value._multimodal ? toolResultObject(value.text_summary ?? value.content?.[0]?.text) : value
  }

  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)

      return parsed && typeof parsed === 'object' ? parsed : null
    } catch {
      return null
    }
  }

  return null
}

/** The `studio` part of a successful `chromatic_present_game` result, from a `tool.complete` payload. */
function presentedGame(payload) {
  if (!payload || payload.name !== PRESENT_TOOL || payload.error) {
    return null
  }

  const result = toolResultObject(payload.result)
  const studio = result?.studio

  if (!result || result.ok !== true || result.error || !studio || typeof studio.gameId !== 'string' || !studio.gameId) {
    return null
  }

  return studio
}

/** Open (or bring forward) the emulator tab for one game, beside the chat. */
function openSideEmulator(ctx, game) {
  if (!game || typeof host.openWorkspace !== 'function') {
    return false
  }

  const key = sideKey(game.id)
  const surface = sideSurface(game.id)

  claimLive(surface)

  try {
    const close = host.openWorkspace(key, {
      dock: { pane: 'workspace', pos: 'right' },
      minWidth: '22rem',
      title: `Emulator · ${game.title}`,
      render: () => jsx(SideEmulator, { ctx, gameId: game.id, paneId: `plugin-workspace:${key}`, title: game.title }),
      onClose: () => {
        sideTabs.delete(game.id)
        releaseLive(surface)
      }
    })

    sideTabs.set(game.id, typeof close === 'function' ? close : () => {})

    return true
  } catch (error) {
    releaseLive(surface)
    console.warn('[hermretro] the emulator could not open beside the chat:', String(error?.message ?? error))

    return false
  }
}

/** The agent presented a game: note it for the tab (which then loads the newest build) and open or
 *  front the tab beside the chat. Each presentation is acted on once. */
function presentGame(ctx, { gameId, title, note, presentedAt }) {
  const mark = `${gameId}:${presentedAt ?? ''}`

  if (presentedAt != null && presentationsSeen.has(mark)) {
    return false
  }

  presentationsSeen.add(mark)

  const shown = PRESENTED.get()
  const seq = (shown[gameId]?.seq ?? 0) + 1

  PRESENTED.set({ ...shown, [gameId]: { seq, note: typeof note === 'string' && note.trim() ? note.trim() : null, t: presentedAt ?? null } })
  BUILD_TICK.set(BUILD_TICK.get() + 1)

  return openSideEmulator(ctx, { id: gameId, title: typeof title === 'string' && title ? title : 'Game' })
}

/** Listen in every chat (registered with the plugin, so it works before the Studio page was ever
 *  opened). Only a successful `chromatic_present_game` opens the emulator; builds just refresh what
 *  open players know. A gateway with tool progress off sends no `tool.complete`, so each turn end
 *  also asks the backend for presentations since the last one seen. */
function watchBuilds(ctx) {
  const listen = typeof ctx.onEvent === 'function' ? ctx.onEvent : typeof host.onEvent === 'function' ? host.onEvent : null

  if (!listen) {
    return
  }

  // Backend clock (seconds) of the last `presentations` answer; until then, this plugin's start.
  let since = Date.now() / 1000 - 5
  let pending = null

  listen('tool.complete', event => {
    const payload = event?.payload

    if (!payload || event.replayed) {
      return
    }

    if (BUILD_TOOLS.has(payload.name)) {
      BUILD_TICK.set(BUILD_TICK.get() + 1) // an open tab re-reads the library and shows the rebuilt banner
    } else if (payload.name === PRESENT_TOOL) {
      const studio = presentedGame(payload)

      if (studio) {
        presentGame(ctx, studio)
      }
    }
  })

  listen('message.complete', event => {
    if (event?.replayed) {
      return
    }

    pending?.()

    const run = async () => {
      BUILD_TICK.set(BUILD_TICK.get() + 1)

      let answer

      try {
        answer = (await callBackend(RPC_PRESENTATIONS, { since })).data
      } catch {
        return // an older backend without the RPC, or none running
      }

      if (!answer?.ok) {
        return
      }

      if (typeof answer.now === 'number') {
        since = answer.now - 1 // the backend's clock; a repeat inside that second is skipped below
      }

      const list = Array.isArray(answer.presentations) ? answer.presentations : []
      // Only the newest presentation per game counts.
      const newest = new Map()

      for (const item of list) {
        if (item && typeof item.gameId === 'string') {
          newest.set(item.gameId, item)
        }
      }

      for (const item of newest.values()) {
        presentGame(ctx, { gameId: item.gameId, title: item.title, note: item.note, presentedAt: item.t })
      }
    }

    const cancel = ctx.setTimeout?.(() => void run(), 600)

    pending = typeof cancel === 'function' ? cancel : null
  })

  ctx.onDispose?.(() => {
    for (const close of [...sideTabs.values()]) {
      try {
        close()
      } catch {
        // already gone
      }
    }
  })
}

/** Where the live player is, shown by the surface that does not have it. */
function PlayerAway({ where, onBring }) {
  return jsx('div', {
    className: 'cs-rp-stage',
    children: jsxs('div', {
      className: 'cs-rp-msg cs-rp-away',
      children: [
        jsx('p', { className: 'cs-eyebrow', children: where }),
        jsx(Lede, { children: 'The game runs in one place at a time. Bringing it here starts it again from the title screen.' }),
        jsxs(Button, { onClick: onBring, size: 'sm', variant: 'default', children: [jsx(Codicon, { name: 'arrow-swap', size: 14 }), 'Bring it here'] })
      ]
    })
  })
}

/** Under the Emulator page's player: the user's own way to move the game beside the chat. */
function SideEmulatorRow({ ctx, game }) {
  const canOpen = typeof host.openWorkspace === 'function'

  return jsxs('div', {
    className: 'cs-rp-foot',
    children: [
      jsx('span', { className: 'cs-rp-hint', children: 'Hermes shows your game beside the chat when it is ready for you to try.' }),
      jsx('span', { className: 'cs-grow' }),
      canOpen && game
        ? jsxs(Button, {
            onClick: () => openSideEmulator(ctx, game),
            size: 'sm',
            variant: 'ghost',
            children: [jsx(Codicon, { name: 'split-horizontal', size: 14 }), 'Open beside the chat']
          })
        : null
    ]
  })
}

/** The emulator tab beside the chat: the Emulator page's bar and player, sized to the tab. */
function SideEmulator({ ctx, gameId, title, paneId }) {
  const surface = sideSurface(gameId)
  const owner = useValue(LIVE_PLAYER)
  const tick = useValue(BUILD_TICK)
  const [paneShown] = useState(() => (typeof host.paneVisibility === 'function' ? host.paneVisibility(paneId) : ALWAYS_VISIBLE))
  const shown = useValue(paneShown) !== false
  const live = owner === surface

  // Nobody is playing (the Studio page was left, another tab closed): a visible tab takes the game.
  useEffect(() => {
    if (owner === null && shown) {
      claimLive(surface)
    }
  }, [owner, shown])

  useEffect(() => () => releaseLive(surface), [])

  const games = useQuery({
    queryKey: [ID, 'games', 'side', gameId],
    queryFn: async () => (await callBackend(RPC_GAMES)).data,
    refetchInterval: shown ? 5_000 : 30_000,
    staleTime: 2_000,
    retry: false
  })
  const firstTick = useRef(tick)

  useEffect(() => {
    if (tick !== firstTick.current) {
      void games.refetch?.()
    }
  }, [tick])

  const list = Array.isArray(games.data?.games) ? games.data.games : []
  const demo = { ...DEMO_GAME, ...(games.data?.demo && typeof games.data.demo === 'object' ? games.data.demo : {}), id: DEMO_ID }
  const game = gameId === DEMO_ID ? demo : (list.find(item => item.id === gameId) ?? { id: gameId, title, rom: null, web: null, chat: null })
  const [reload, setReload] = useState(0)
  const [dismissed, setDismissed] = useState(null)
  const [capturesOpen, setCapturesOpen] = useState(false)
  // The agent's latest presentation of this game: a new one loads the newest build directly (it is
  // an explicit "try this now") and shows its note until the user dismisses it.
  const presentation = useValue(PRESENTED)[gameId] ?? null
  const seenSeq = useRef(presentation?.seq ?? 0)
  const [noteHidden, setNoteHidden] = useState(null)

  useEffect(() => {
    const seq = presentation?.seq ?? 0

    if (seq !== seenSeq.current) {
      seenSeq.current = seq
      setDismissed(null)
      setReload(value => value + 1)
      void games.refetch?.()
    }
  }, [presentation?.seq])

  const note = presentation?.note && noteHidden !== presentation.seq ? presentation.note : null
  const player = useQuery({
    queryKey: [ID, 'player', 'side', gameId, reload],
    queryFn: async () => (await callBackend(RPC_PLAYER, { id: gameId }, 30_000)).data,
    enabled: live,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false
  })
  const frameRef = useRef(null)
  const stageRef = useRef(null)
  const scopeRef = useRef(null)
  const loadedSha = player.data?.url ? (player.data.romSha256 ?? null) : null
  const currentSha = playableSha(game)
  const rebuilt = Boolean(live && loadedSha && currentSha && loadedSha !== currentSha && dismissed !== currentSha)
  const bridge = usePlayerBridge({ ctx, frameRef, onAnnotate: data => annotateGame(ctx, game, data), scopeRef, visible: live && shown })
  const hardwareOn = Boolean(games.data?.device?.hardwareEnabled)

  return jsxs('div', {
    className: 'cs-page cs-side',
    'data-page': 'emulator',
    ref: scopeRef,
    children: [
      jsx(PageStyle, {}, 'style'),
      ...(live
        ? [
            jsx(EmulatorBar, {
              capturesOpen,
              ctx,
              focused: bridge.focused,
              game,
              hardwareOn,
              onAsk: () => askAboutGame(ctx, game, bridge.snap),
              onFull: () => void stageRef.current?.requestFullscreen?.()?.catch?.(() => {}),
              onLater: () => setDismissed(currentSha),
              onReload: () => setReload(value => value + 1),
              onToggleCaptures: () => setCapturesOpen(open => !open),
              player,
              rebuilt
            }, 'bar'),
            note
              ? jsxs('div', {
                  className: 'cs-side-note',
                  role: 'note',
                  children: [
                    jsx(Codicon, { name: 'comment', size: 14 }),
                    jsx('span', { className: 'cs-side-note-text', children: note }),
                    jsx('button', {
                      'aria-label': 'Dismiss note',
                      className: 'cs-side-note-x',
                      onClick: () => setNoteHidden(presentation.seq),
                      title: 'Dismiss',
                      type: 'button',
                      children: jsx(Codicon, { name: 'close', size: 12 })
                    })
                  ]
                }, 'note')
              : null,
            jsx(PlayerNotice, { game, onRefresh: () => setReload(value => value + 1), player, refreshing: player.isFetching }, 'notice'),
            jsx(PlayerStage, { ctx, frameKey: `${gameId}:${reload}`, frameRef, game, player, stageRef, visible: true }, 'player')
          ]
        : [jsx(PlayerAway, { onBring: () => claimLive(surface), where: 'Playing in hermretro' }, 'away')])
    ]
  })
}

// ── Page ──────────────────────────────────────────────────────────────────────

function StudioPage({ ctx }) {
  const queryClient = useQueryClient()
  const [memory, update] = useSetupMemory(ctx)
  const [page, setPage] = useState(() => {
    try {
      const stored = ctx.storage.get('page', 'home')

      return PAGES.some(([id]) => id === stored) ? stored : 'home'
    } catch {
      return 'home'
    }
  })
  // Step the user chose to look at; null follows the first incomplete step.
  const [pinned, setPinned] = useState(null)
  const [promptId, setPromptId] = useState('new-game')
  const [polling, setPolling] = useState({ fast: true, pollDoctor: false })
  const { backend, doctor, gateway, status } = useBackend(polling)
  const refreshing = status.isFetching || doctor.isFetching

  const running = backend === 'ok'
  const steps = computeSteps({ backend, doctor, memory, status })
  const auto = running ? (steps.find(step => !step.complete) ?? null) : null
  // The game steps are done and the Chromatic ones are next: ask whether there is a Chromatic
  // before showing them, so people without one go straight to making games.
  const choosing = Boolean(auto?.hardware) && !memory.hardwareWanted && !memory.hardwareSkipped
  const autoId = !running ? 'not-running' : !auto ? 'ready' : choosing ? 'choice' : auto.id
  const pinnedStep = running ? (steps.find(step => step.id === pinned) ?? null) : null
  const shown = pinnedStep ?? (choosing ? null : auto)
  const viaProfile = running ? (status.data.via_profile ?? null) : null
  const hardwareOn = Boolean(status.data?.hardware_enabled)
  const emulatorOnly = Boolean(memory.hardwareSkipped) && !hardwareOn
  const gameReady = running && steps.filter(step => !step.hardware).every(step => step.complete)

  // Initial answers have arrived; only changes after this are worth announcing.
  const settled = running && (Boolean(doctor.data) || doctor.isError)
  const lastAuto = useRef(autoId)
  const wasSettled = useRef(false)
  const stepsRef = useRef(steps)

  stepsRef.current = steps

  // A step was completed: leave any reviewed page and move on to the next one.
  useEffect(() => {
    const before = lastAuto.current

    lastAuto.current = autoId

    if (before === autoId) {
      return
    }

    setPinned(null)

    const finished = stepsRef.current.find(step => step.id === before)

    if (wasSettled.current && finished?.state === 'done') {
      host.notify({ kind: 'success', message: `${finished.title}: done` })
    }
  }, [autoId])

  useEffect(() => {
    wasSettled.current = settled
  }, [settled])

  // First-run onboarding: until the game tools are in and the user has chosen how to play, the page
  // shows only the guided setup. A setup finished before onboarding existed skips it.
  const priorSetup = Boolean(memory.hardwareSkipped || memory.hardwareWanted || memory.firmwareDone || memory.devmodeDone)
  const legacyReady =
    settled && !memory.onboardStarted && (gameReady || priorSetup || Boolean(status.data?.profile?.is_studio && toolchainStateKnown(status, doctor)))
  const onboarding = running && !memory.onboarded && !legacyReady
  const onboardScreen = !onboarding
    ? null
    : !settled
      ? 'checking'
      : !memory.onboardStarted
        ? 'welcome'
        : !gameReady
          ? 'install'
          : !memory.hardwareSkipped && !memory.hardwareWanted
            ? 'chromatic'
            : 'make'

  useEffect(() => {
    if (legacyReady && !memory.onboarded) {
      update({ onboarded: true })
    }
  }, [legacyReady, memory.onboarded])

  const toolchainStep = steps.find(step => step.id === 'toolchain')
  const wantInstall = running && (onboarding || page === 'setup' || toolchainStep?.state === 'todo')
  const install = useInstall({ enabled: wantInstall })
  const installState = install.data?.install?.state ?? null
  const lastInstall = useRef(installState)

  // The page's install finished: read the tools again so the step can verify.
  useEffect(() => {
    const before = lastInstall.current

    lastInstall.current = installState

    if (before === 'running' && installState === 'done') {
      void doctor.refetch?.()
    }
  }, [installState])

  const finishOnboarding = () => {
    update({ onboarded: true })
    go('home')
  }

  useEffect(() => {
    const toolchainOpen = toolchainStep && toolchainStep.state !== 'done' && toolchainStep.state !== 'checking'
    const next = {
      fast: autoId !== 'ready',
      pollDoctor: Boolean(toolchainOpen) && installState !== 'running' && (autoId === 'toolchain' || onboardScreen === 'install')
    }

    setPolling(current => (current.fast === next.fast && current.pollDoctor === next.pollDoctor ? current : next))
  }, [autoId, toolchainStep?.state, installState, onboardScreen])

  const go = id => {
    setPage(id)

    try {
      ctx.storage.set('page', id)
    } catch {
      // remembered for this visit only
    }
  }

  const refresh = () => {
    routing.scannedAt = 0 // look through the profiles again
    routing.route = null // and forget a profile that may have been removed or stopped
    routing.profile = null
    routing.studio = false
    void queryClient.invalidateQueries({ queryKey: [ID] })
  }

  const pick = id => setPinned(id === autoId ? null : id)
  const setUpDevice = () => {
    update({ hardwareSkipped: false, hardwareWanted: true, onboarded: true })
    setPinned(null)
    go('setup')
  }
  const openPrompt = id => {
    setPromptId(id)
    go('prompts')
  }

  // ── games and the player ──
  const onEmulator = page === 'emulator'
  const games = useQuery({
    queryKey: [ID, 'games', viaProfile],
    queryFn: () => callStudio(RPC_GAMES),
    enabled: running,
    // While the player is on screen, a rebuild in chat is noticed within seconds.
    refetchInterval: onEmulator ? 5_000 : 30_000,
    staleTime: 2_000,
    retry: false
  })
  const gameList = Array.isArray(games.data?.games) ? games.data.games : []
  const [emu, setEmu] = useState({ id: null, reload: 0 })
  const [emuOpened, setEmuOpened] = useState(false)
  const [dismissed, setDismissed] = useState(null)
  const [capturesOpen, setCapturesOpen] = useState(false)
  const demo = { ...DEMO_GAME, ...(games.data?.demo && typeof games.data.demo === 'object' ? games.data.demo : {}), id: DEMO_ID }
  // A game picked on the shelf plays even without a web build (its error says how to build it); left
  // to itself the page plays the newest playable game, else the demo cartridge. While the library is
  // still loading nothing is chosen, so the frame does not load the demo and then switch.
  const libraryKnown = Boolean(games.data) || games.isError
  const game =
    emu.id === DEMO_ID
      ? demo
      : (gameList.find(item => item.id === emu.id) ?? (libraryKnown ? (latestGame(gameList.filter(item => item.webExport)) ?? demo) : null))

  useEffect(() => {
    if (onEmulator && game) {
      setEmuOpened(true)
    }
  }, [onEmulator, game?.id])

  // One game runs at a time. Visiting the Emulator page never takes the game from a tab beside the
  // chat (that would restart a game the user is playing); the page offers "Bring it here" instead and
  // only plays when nothing else does.
  const liveOwner = useValue(LIVE_PLAYER)
  const pageLive = liveOwner === 'page'

  useEffect(() => {
    if (onEmulator && running && liveOwner === null) {
      claimLive('page')
    }
  }, [onEmulator, running, liveOwner])

  useEffect(() => () => releaseLive('page'), [])

  const player = useQuery({
    queryKey: [ID, 'player', game?.id ?? null, emu.reload],
    queryFn: () => callStudio(RPC_PLAYER, { id: game.id }, 30_000),
    enabled: running && emuOpened && Boolean(game) && pageLive,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false
  })
  const frameRef = useRef(null)
  const stageRef = useRef(null)
  const loadedSha = player.data?.url ? (player.data.romSha256 ?? null) : null
  const currentSha = playableSha(game)
  const rebuilt = Boolean(pageLive && loadedSha && currentSha && loadedSha !== currentSha && dismissed !== currentSha)
  const thumbTried = useRef(new Set())

  const bridge = usePlayerBridge({ ctx, frameRef, onAnnotate: data => annotateGame(ctx, game, data), visible: onEmulator && running && pageLive })
  const ask = () => askAboutGame(ctx, game, bridge.snap)

  // After a game first loads, keep its title screen for the shelf (when it has none yet).
  const onFrameLoad = () => {
    const target = game

    if (!target || target.id === DEMO_ID || target.thumb || thumbTried.current.has(target.id)) {
      return
    }

    thumbTried.current.add(target.id)

    const attempt = async remaining => {
      const png = await shrinkFrame(await bridge.snap())

      if (!png) {
        if (remaining > 0) {
          ctx.setTimeout(() => void attempt(remaining - 1), 5_000)
        }

        return
      }

      try {
        await callStudio(RPC_GAME_THUMB, { id: target.id, png })
        void queryClient.invalidateQueries({ queryKey: [ID, 'games'] })
      } catch (error) {
        console.warn('[hermretro] title screen not saved:', describeRequestError(error).message)
      }
    }

    ctx.setTimeout(() => void attempt(3), 3_000)
  }

  const play = id => {
    setEmu(current => ({ id, reload: current.reload }))
    go('emulator')
  }

  // ── body ──
  let body

  if (!running) {
    body = [jsx(NotRunning, { backend, gateway, status }, 'off')]
  } else if (onboardScreen) {
    body = [
      jsx(
        Onboarding,
        { ctx, install, onDevice: setUpDevice, onFinish: finishOnboarding, screen: onboardScreen, status, steps, update },
        'onboarding'
      )
    ]
  } else if (page === 'setup') {
    body = [
      jsxs(
        'div',
        {
          className: 'cs-setup',
          children: [
            jsx(StepRail, { autoId, onPick: pick, shownId: shown?.id ?? null, skipped: Boolean(memory.hardwareSkipped), steps }, 'rail'),
            shown
              ? jsx(SetupWizard, { autoId, backend, ctx, doctor, gateway, install, onContinue: () => setPinned(null), onPick: pick, shown, status, steps, update }, 'wizard')
              : choosing
                ? jsx(HardwareChoice, { steps, update }, 'choice')
                : jsx(SetupComplete, { doctor, emulatorOnly, onGo: go, onRecheck: refresh, onSetUpDevice: setUpDevice, rechecking: refreshing, status, steps }, 'complete'),
            jsx(Flyer, {}, 'flyer')
          ]
        },
        'setup'
      )
    ]
  } else if (page === 'prompts') {
    body = [
      jsx(PromptsPage, {
      ctx,
      // New games go in the plugin's games folder (the backend reports it); an older backend without
      // it falls back to the folder of the latest game.
      defaultFolder: (() => {
        if (typeof games.data?.gamesDir === 'string' && games.data.gamesDir) {
          return games.data.gamesDir
        }

        const root = latestGame(gameList)?.projectRoot

        return root ? root.replace(/[\\/][^\\/]+[\\/]?$/, '') || null : null
      })(),
      gameReady,
      hardwareOn,
      onGo: go,
      onSelect: setPromptId,
      onSetUpDevice: setUpDevice,
      profileLabel: routing.profile ?? status.data?.profile?.name ?? 'this profile',
      selected: promptId,
      storage: ctx.storage
    }, 'prompts')
    ]
  } else if (page === 'games') {
    body = [jsx(GamesPage, { ctx, games, hardwareOn, onOpenPrompt: openPrompt, onPlay: play, onSetUpDevice: setUpDevice }, 'games')]
  } else if (page === 'emulator') {
    // Always the player: the user's game, or the demo cartridge when there is nothing of theirs to play.
    body = [
      jsx(EmulatorBar, {
        capturesOpen,
        ctx,
        focused: bridge.focused,
        game,
        hardwareOn,
        onAsk: ask,
        onFull: () => void stageRef.current?.requestFullscreen?.()?.catch?.(() => {}),
        onLater: () => setDismissed(currentSha),
        onReload: () => setEmu(current => ({ id: game.id, reload: current.reload + 1 })),
        onToggleCaptures: () => setCapturesOpen(open => !open),
        player,
        rebuilt
      }, 'bar'),
      jsx(PlayerNotice, {
        game,
        onRefresh: () => {
          refresh()
          setEmu(current => ({ id: current.id, reload: current.reload + 1 }))
        },
        player,
        refreshing: player.isFetching
      }, 'notice')
    ]
  } else {
    body = [
      jsx(
        HomePage,
        { auto, autoId, choosing, ctx, doctor, games, memory, onGo: go, onOpenPrompt: openPrompt, onPlay: play, onSetUpDevice: setUpDevice, status, steps },
        'home'
      )
    ]
  }

  const flush = running && page === 'emulator' && !onboardScreen
  // After onboarding a broken game step is a banner, not the onboarding again.
  const broken = running && settled && !onboardScreen && page !== 'setup' ? steps.find(step => !step.hardware && !step.complete) : null
  // The player stays mounted (hidden and paused) while another page is shown, so the game is not reloaded.
  // Beside the chat instead: the Emulator page says so; other pages drop the hidden frame.
  const stage =
    running && !onboardScreen && (emuOpened || onEmulator)
      ? pageLive
        ? jsx(PlayerStage, { ctx, frameKey: `${game?.id ?? 'none'}:${emu.reload}`, frameRef, game, onLoad: onFrameLoad, player, stageRef, visible: onEmulator }, 'player')
        : onEmulator
          ? jsx(PlayerAway, { onBring: () => claimLive('page'), where: 'Playing beside the chat' }, 'player')
          : null
      : null

  return jsx(ScrollArea, {
    className: 'h-full',
    style: { height: '100%' },
    children: jsxs('div', {
      className: 'cs-page',
      'data-page': page,
      style: {
        '--cs-hermes': `url("${ART_DATA.hermes}")`,
        '--cs-cart': `url("${ART_DATA.cart}")`,
        '--cs-fly-body': `url("${ART_DATA.chromBody}")`,
        '--cs-fly-wing': `url("${ART_DATA.chromWing}")`
      },
      children: [
        jsx(PageStyle, {}, 'style'),
        onboardScreen
          ? jsx(OnboardHeader, { stage: ONBOARD_STAGES.some(([id]) => id === onboardScreen) ? onboardScreen : null }, 'nav')
          : jsx(
              StudioNav,
              {
                onGo: go,
                onRefresh: refresh,
                page,
                playing: Boolean(stage && game && player.data?.url),
                refreshing,
                setupPending: running && Boolean(auto)
              },
              'nav'
            ),
        jsxs(
          'div',
          {
            className: flush ? 'cs-pad flush' : 'cs-pad',
            children: [
              viaProfile && !flush && !onboardScreen
                ? jsx(
                    'p',
                    {
                      className: 'cs-small',
                      style: flush ? { padding: '8px clamp(12px, 2cqi, 32px) 0' } : { marginBottom: -8 },
                      children: `Showing the "${viaProfile}" profile, where hermretro is switched on. Prompts open a chat in that profile.`
                    },
                    'via'
                  )
                : null,
              broken
                ? jsxs(
                    'div',
                    {
                      className: 'cs-repair',
                      role: 'status',
                      children: [
                        jsx(Codicon, { name: 'warning', size: 14 }),
                        jsx('span', { children: `${STEP_SHORT[broken.id]} needs attention: ${broken.title.toLowerCase()} again to keep building games.` }),
                        jsx(Button, { onClick: () => go('setup'), size: 'sm', variant: 'outline', children: 'Repair' })
                      ]
                    },
                    'repair'
                  )
                : null,
              ...body,
              stage,
              flush ? jsx(SideEmulatorRow, { ctx, game }, 'side') : null,
              flush ? null : jsx(Footer, { ctx }, 'foot')
            ]
          },
          'pad'
        )
      ]
    })
  })
}

export default {
  id: ID,
  name: 'hermretro',
  register(ctx) {
    watchBuilds(ctx)
    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: ROUTE },
        render: () => jsx(StudioPage, { ctx })
      },
      // Two panes on purpose: Hermes disables a plugin whose only pane is closed.
      {
        id: PANE_GAME,
        area: 'panes',
        title: 'Chromatic',
        // Its own column right of the chat, so the agent's playtest stays visible while you chat.
        data: { placement: 'right', dock: { pane: 'workspace', pos: 'right' }, width: '300px' },
        render: () => jsx(GamePane, { ctx })
      },
      {
        id: PANE_LOG,
        area: 'panes',
        title: 'Chromatic log',
        data: { placement: 'right', dock: { pane: `${ID}:${PANE_GAME}`, pos: 'bottom' }, width: '300px', height: '220px' },
        render: () => jsx(LogPane, {})
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        order: 60,
        data: { codicon: 'game', label: 'hermretro', path: ROUTE }
      },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: {
          id: `${ID}.open`,
          label: 'hermretro: Open',
          keywords: ['chromatic', 'modretro', 'game boy', 'gbc', 'gb studio', 'rom', 'cartridge'],
          run: () => host.navigate(ROUTE)
        }
      }
    ])
  }
}

// ── Artwork (generated by tools/embed_art.py; do not edit by hand) ──
const ART_DATA = {
  hermes: [
    'data:image/png;base64,',
    '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',
  ].join(''),
  cart: [
    'data:image/png;base64,',
    'iVBORw0KGgoAAAANSUhEUgAAASsAAAFUCAYAAAB80BqgAACvQUlEQVR4nO39245lS3bm+YVHxN55TmaSTCaTWaoSUI8gQPfq',
    'ggqtrlapBaEBPYAE6CWoC/Vj9AsIaEGFLqABAf0M6vu6KECiwEoeM5knMjN37HBhOP3n/MfYc/khzoc1gAVfvuacNu0w7LNv',
    'DBtmdvFf/9f/x6///d///f/i5z//+X/z6NGjH11cXDy+uLh49Pjx40eXl5dXn/nf3/l88cUXj377298++ta3vvVo5GJ+fPTo',
    '6cXFxY8eP3782Zdffnn1/Hz+4R/+4dHnn38urS8uLi5+cnFx8Wweef78+dPnz5//6MmTJ589f/78i8ePH//kyy+/fPbkyZPL',
    '58+fz/VHT548mb8Xjx8/fvrs2bMfffbZZ5/N+ydNMmnPvdd5uXovmbyMTDpz39OnTx/95je/uSmf+/199uzZC2ldv3/+/eLZ',
    's2c/efz48bPPP//8ctIYUc6578mTJxd///d//3Tq8Wtf+9qU6So9aahHz8z3ua5enjx58uwfi/OP5Zlr85myyst8pKl91NXI',
    '3Dv1I//q5xvf+MbFb3/726u8PXr06LPWz5MnT754/vz5Ty4vL5/Ny6eO5pl5R+v4us2uPtWPSeMb3/jGvHdU4enl5eXVO9Tr',
    'yOjL17/+9Zv8Vp98plzabvTh8vLySlceP358Odd/97vfPfrss89eaN/IxbNnz670aXRw6mHun7w9ffr0qnxPnz4dvbtUnuuy',
    '3zw7dTPPTvmfPXt2pY9ffPHFs6997WuX9EgbKoN2ffr06cVU3ePHj3/07Nmzz3afmTr+4osvrvTnun88ffr06Y9+97vffTb1',
    'Mm22ynV1/6NHj549fTpV+o/5bX3N/ddpXUxiX3zxxY+eP39+1bbSSn3etNn0ya997Wu9/sWXX355VddTNfRs7tN3rtvx+fSB',
    '3/72t4MVP/nhD3/4229961t//t/9d//33z16C3LxX/6X/7t/+fOf//y//cY3vvG//Pzzz7++lWkUaBTkutGvlG5+GxmworwD',
    'KE+fTlvdVODVc9MInr1u7OejMJP2l19+efH8+fOrZ64b4/kAlfeMss075trvfve7i88+++zxfJ9rU9kaop2WQrUz+U2lTyNo',
    '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',
    'rYCaI8R9fEjSbnhBWYZ0ONEBTTtaAVbYgfdikmYDd10UlJtOG7r1WP/Esu+/cl87v3bpkhoDSp9tZ8b8tKuOWwX1bP0o7egF',
    '2wGtsuaCawHbdQyFLrXOKXCn6aXZwFdtiokelbfpHQFlB5R2zKZVAAUUBT4dmM9MndFNs70d4OlJdXiX5fL6/q4tVac1P9tX',
    'gFsBvPWub1YHN/utYLh1o3TlQO+rfhFlElKi3ypHZ0iv+/rjqzirJ0+e/MvxxNdhaqfIYVg6mwLWXu0UcCk7gOso2EpSuBZi',
    'O4zrfJbmHpFPVUjzceq33VnftWyF2Pl76PX9f0fCo+tbdvp7NN7p3SV35f+hz98ld6X/0Po5lf8OEKc658vktwP1fdK76/5t',
    'xTS/ZaUFxPbdzijXXQBcrYfc2zZt1grk64JqHGQnrK7dOl/+5je/+Y9XkNyMlZb9/Oc/v/oMVd0NU8ZwNMLX7OhuinxORp7K',
    '9v/cJs3PKeAqOPWZjpLvkzw0Pw8Fm7vuf1XwetPg81B5aPq7s285dW33jVPvvy3to8F1///8jvwdvbNyql81/52x3f7ngkwZ',
    'qDx2YmBParFMihkjfuM+qNVRrLl6n4yUEnvRbIE6YDWR5b/3e7/3FdRuRPi+Jp2GHjSAsjNxzVRNiaNKPTJ3ajbe1nAbpI4U',
    '403KXcr6UHB5KPM6eudD7n8ok7vr+Tcle3B6mWe3vG8s/GXkyHWwhdVT/9MelOpTbn882uamPmZEyDNcULCn7prtbrm6v8gJ',
    '0diSDckfP9awrf0ydnJ9HV7AZHStvheFrYyjsT6tI0p7yv9wHwXdDsL3TR4KVm/a7LorvbdtBr5pOTVIvq78bjPxTQ8ulwf3',
    '3+b+ACx8jY2/bFQAEBoRzM1va2a2+3zBgsbsNcwBWYIN/FXbhfO00/KldPxHIzO7Mc7mcbr/0R/90QurzbtERVp8WXuGip/L',
    'fXVgcnybkagzuuB1inG9DmXccpcP41XNnv38BulTDPBl5U37jF7FRLmPvGr6p+rb5y7wvU/7VQzkI9tdclse71tPF4mF3JNK',
    'I9vnu6XO+IZSyOP4nsyGu4efymG6yI3vjfo3CQZ4uHmOgobn//GPi/WED4Dsysxka3bansOsG4nZdXC2a5lE5/+9Ql8FFWwq',
    'KkQGeqBET4ot+/F9OwP7t413H+V62Y7/ppnA9rHdNgq/jLxvTOZNyhEwnHJ+v4rZeJc8xOG+B/T7+BifZBb9vkxX3dQvtGPM',
    'atrpx90TTRwVC8vMJDDSv1lpZVadXe/+WJ3Ew8gEmF+dremiKeM6t+YG08jzv/Pbxo8FkBpQp7LF3jT2qRXazHU6VkMdmXVH',
    'DbcV4XWbd4152Y19nzzdJa+b2bzu9z1UHpq/h97/kPzvTl8Wciofp67fV07FLt12fctt+byt/rauHrHxHTzsN/cjHuqurGg+',
    'WNNMuO09vEb4nLqVUl1CDXHyjmKG/NfCsLvpFSg2tGD7k0SDd1HjANb8nfP6xgFvhwEvqN27xSLaxtgo5NEylCMAOjKTfL+L',
    '9r4sOPh75KDf975Jed0+rHftQ3qTYDWylyK9a5/i6zCjL6L7Ddo+Zcmc+h8oNBaLf7lBnXbMIEy59uN51oLornLxDoSnltt8',
    'H9LjgA/Ehex1j1dg1a142wlFLCuI9UPju5oXDOsaH9YAloIVgIqQI13KYtagEbPs1DKsXdkqRsUXuY9o/6sq131o+33v3Q3d',
    'SPeauq+Sn4eC06s6yF9VXub9zJWHmD1vSh7aHq/DQX+bf/OUP7cEpLN9NckAzdbH6atm/QuG3WNuu1eKJd0/DeGZ9wyGSG8v',
    '++ricCRq5MpnhV3VIdZlGX2RRPmwBh0nrAGV25T7aEW6zrrDGJpBinmfwLcdZdxrb6qz3WYCnlLKAm1Z5Kn8bnlVU/ehYPiu',
    'mdeWbVacys9mwqfkbbDhNykX92zPAhY2BfBr/hWsyrY8I8SgjvSu2pj7/O6ZLvrWd/m4gCZBWGp6Fp9mW+MXnGYcZt22BbrV',
    'cT73ju06MVgDWGMedn3QUQR630Xhtt2tQ96mSEcKe8pkfJ1y3/RO3VdGsJcl3Cf9D71zvQ6hM1t3jnTg6P+Hyl16eN/n7zPQ',
    'PNQnd3HP+7fbpAHZZvXrq3bf3qmibhusqjvG1toR0d7Qpq7RHemaR+/vbhebZT1llnXVcxcH7wIUjOxvNKbhANaYhHPfoOZ8',
    'Zm3hXmcGKY9MuL7rqDHa2Eej5uv2UZySUw72nd8jH0JjSjaY35X/hzLFVzVT3jdw3K6Fo/pv2+w1bQ9dTvM65FX8mq/DR3lx',
    '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',
    '27Sjbv1MZTplMgCoYNl8TZqdhe1n6w992O2xmXoZeydDhM0UzMr+DDY1312Txy4eLjOqm8H7ClRfHuwYq15qIrePKiu3ym4/',
    'Ojt/Z3JEGnSmflXArIyOle8171a/2qeDY5mkuu0mlZVrPfjts2fP/uzrX//6nz39/PPP//zRo0d/+vz58//m0aNH//zRo0c/',
    'nvpTWV9++eXF8+fPb5bl1AGsQuaFY7d2G9dTglobUZqx+n2K0mQrlC04dAR7UmnY/i2tVQ6srMcb1c/iHkqJZchf0zqq7Jbv',
    'yA73zm0qSmtvrwNQujjbKKwslNjZexs8tMFW3vohvLOMcjNJ9V0zQv7Kjgq0u47UbR3FNY2nnNOJ+F/mN+npyBTd75X9vjLd',
    '+T51JJ1Tn7K6fc6gjrddD/Ssg18ZTB392r67EBT86O1FnNpz3cqAzXzcWz1qG3cQtq/b/Fafb9Np3V3n5/k3vvGNy2uXwsWT',
    'J0+udm7ZLLMDnt+ryxucLy8vn19cXFyuPvPb58+f/0+fffbZ//Vb3/rWn1+l/G/+zb/9+pdffvnj58+fD1j96aNHj2ZZ/ZR0',
    'ro+2/uji4uIzyt1o384eqaA9DWmEakMd2amepcidtdl0dY+U0zHFX1FInZnCdKlHR8DdoGSbgR3dqiDbDGyM1M6vvzoJlsQ0',
    'rZJYooI9MpnksU7XmoQ1N7E2Z8lReEyxdVi/i9F7Dx71e9Qd0JF0t1dH1pqBrVO6ROk7i9jBo+Xdu0wc6VOlroUCMsCvDvf+',
    'WguAf+qSmS0PR66N6gv9atyY93Zw3fk9Svsi21UXxCqecZ9npF1da9nrB1xA98Xz589/8vnnnz+7rvshO4MVn3UwPWUGbsaX',
    '/vnFb3/725/85je/efb8+XMFfX55efmTp0+f/un3vve9/+l//B//X//QFn78r//1/+bz58+f/2gyMeUYRnV5eTmZ+dOLi4sf',
    'XV5e3m+O8YQcNeZD5Egh3+b7T+WjCvuQ9x/dv30gtz3/Kvl91TSP3lFge5l0j+qnafaeozrav21mu1nKm6iHj1ieX0/GjQU2',
    'f0eusCHk5u5Evrqjxk26X3zxxU+uGda0zeU3v/nNZ59//vlP/of/4d9fmU//f28B5rINcwryAAAAAElFTkSuQmCC',
  ].join(''),
  chromBody: [
    'data:image/png;base64,',
    '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',
    'AABJRU5ErkJggg==',
  ].join(''),
  chromWing: [
    'data:image/png;base64,',
    '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',
    'tAAAAABJRU5ErkJggg==',
  ].join(''),
}
// ── End of artwork ──
