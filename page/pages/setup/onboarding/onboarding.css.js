import { MONO } from '#shared/styles/tokens.js'

export const ONBOARDING_CSS = `
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
`
