/**
 * hermretro — Hermes Desktop half. GENERATED FILE, do not edit.
 * Source: page/ (one folder per page). Rebuild: node tools/bundle/bundle.mjs
 * Plain ESM; imports only @hermes/plugin-sdk, react and react/jsx-runtime.
 * Embeds provider logos (page/shared/art/providers/): each belongs to its company, is used only to name its
 * provider and is not covered by the MIT licence; its source is beside it in page/shared/art/providers/index.js.
 * build: esbuild 0.28.2
 * sources: sha256 aaf129faf828299cd3aa6f886852ebf9b6ff17af7060df7765d1260ea90133ba
 * body: sha256 1e94e68cf345881e37271773862305b1d28ee4f1ccf6133ba417f701bebee87f
 */
// page/sdk.js
import {
  atom,
  Button,
  Codicon,
  CopyButton,
  host,
  MessageTextContent,
  PALETTE_AREA,
  randomUuid,
  ROUTES_AREA,
  SandboxedFrame,
  ScrollArea,
  SIDEBAR_NAV_AREA,
  Tip,
  useQuery,
  useQueryClient,
  useTheme,
  useValue
} from "@hermes/plugin-sdk";
import { createContext, memo, useCallback, useContext, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";

// page/app/ids.js
var ID = "hermretro";
var ROUTE = "/hermretro";
var DEMO_ID = "demo";
var DEMO_GAME = { id: DEMO_ID, title: "Hello Color", kind: "gbdk", note: "ModRetro example" };
var STUDIO_PROFILE = "hermretro";
var ENABLE_COMMAND = `hermes plugins enable ${ID}`;
var AGENT_SETTINGS_HREF = `/settings?tab=plugins&agent=${ID}&profile=${STUDIO_PROFILE}`;
var PLUGINS_HREF = `/capabilities?tab=plugins&plugin=${ID}`;
var AGENT = "HermRetro";

// page/pages/build/assets/assets.css.js
var ASSETS_CSS = `
/* images */
.cs-b-strip { align-items: center; display: inline-flex; flex-wrap: wrap; gap: 6px; }
.cs-b-more { color: var(--ui-text-quaternary); font-size: 11px; }
.cs-b-th { align-items: center; appearance: none; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-secondary) 0 50%) 0 0 / 8px 8px; border: 0; border-radius: 6px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); cursor: zoom-in; display: inline-flex; flex: none; height: 40px; justify-content: center; overflow: hidden; padding: 0; transition: box-shadow .15s ease, transform .15s ease; width: 40px; }
.cs-b-th:hover { box-shadow: inset 0 0 0 1px var(--ui-accent); transform: translateY(-1px); }
.cs-b-th img { height: 100%; image-rendering: pixelated; object-fit: contain; width: 100%; }
.cs-b-spr { display: block; height: 100%; image-rendering: pixelated; max-height: 100%; max-width: 100%; object-fit: contain; width: 100%; }
.cs-b-th.xs { border-radius: 4px; height: 20px; width: 20px; }
.cs-b-th.lg { border-radius: 8px; height: 84px; width: 112px; }
.cs-b-th.cs-b-reply-img { border-radius: 6px; display: flex; margin: 10px 0; max-width: 100%; }
.cs-b-th.cs-b-reply-img.loading { height: 120px; width: 160px; }
.cs-b-sprite { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 10px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: inherit; cursor: zoom-in; display: flex; font: inherit; gap: 14px; margin: 4px 0; max-width: 100%; padding: 10px 16px 10px 10px; text-align: left; transition: box-shadow .15s ease; }
.cs-b-sprite:hover { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-sprite-stage { align-items: center; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 12px 12px; border-radius: 7px; display: flex; flex: none; height: 120px; justify-content: center; width: 120px; }
.cs-b-sprite-stage img { image-rendering: pixelated; max-height: 100%; max-width: 100%; }
.cs-b-th.screen { aspect-ratio: 160 / 144; border-radius: 4px; height: auto; width: 100%; }
.cs-b-th.fresh { animation: cs-b-pop .35s ease-out; box-shadow: inset 0 0 0 1px var(--ui-accent), 0 0 0 3px color-mix(in srgb, var(--ui-accent) 22%, transparent); }
.cs-b-th.loading { animation: cs-b-skel 1.2s ease-in-out infinite; background: var(--ui-bg-quaternary); cursor: default; }
@keyframes cs-b-pop { from { opacity: 0; transform: scale(.85); } }
@keyframes cs-b-skel { 50% { opacity: .45; } }
`;

// page/pages/build/new-game-glass.css.js
var NEW_GAME_GLASS_CSS = `
.cs-b-attract { --cs-at-glass: color-mix(in srgb, var(--cs-at-bg, var(--ui-bg-editor)) 60%, transparent); }
.cs-b-attract > * { position: relative; z-index: 1; }
/* the header above the form, so the game switcher's menu opens over it; the composer above the choice cards, so its
   model picker opens over them (the glass's backdrop-filter makes each a stacking context that would trap it) */
.cs-b-attract > .cs-b-head { z-index: 2; }
.cs-b-attract .cs-b-new .cs-title { align-self: center; text-shadow: 0 2px 0 color-mix(in srgb, var(--cs-at-bg, var(--ui-bg-editor)) 70%, black), 0 0 18px var(--cs-at-bg, var(--ui-bg-editor)), 0 0 6px var(--cs-at-bg, var(--ui-bg-editor)); }
.cs-b-attract .cs-b-new .cs-b-comp { position: relative; z-index: 2; -webkit-backdrop-filter: blur(10px) saturate(.8); backdrop-filter: blur(10px) saturate(.8); background: var(--cs-at-glass); box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary), 0 0 0 1px color-mix(in srgb, var(--ui-accent) 45%, transparent); }
.cs-b-attract .cs-b-opt { -webkit-backdrop-filter: blur(10px) saturate(.8); backdrop-filter: blur(10px) saturate(.8); background: var(--cs-at-glass); }
.cs-b-attract .cs-b-opt.on { background: color-mix(in srgb, var(--ui-accent) 10%, var(--cs-at-glass)); }
`;

// page/pages/build/build-responsive.css.js
var BUILD_RESPONSIVE_CSS = `
@container (max-width: 640px) {
  .cs-b-sw-pop.cs-b-builds { width: min(420px, calc(100cqi - 24px)); }
  .cs-b-bc-head { padding: 10px 12px 2px 12px; }
  .cs-b-bc-sum, .cs-b-bc-changes, .cs-b-ba, .cs-b-bc-foot, .cs-b-bc-details { padding-left: 12px; padding-right: 12px; }
  .cs-b-ba-pair { gap: 8px; }
  .cs-b-gist { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .cs-b-spin, .cs-b-shimmer, .cs-b-pulse, .cs-b-live.on, .cs-b-game .dot.wait, .cs-b-th.loading, .cs-b-skel i { animation: none; }
  .cs-b-shimmer { color: var(--ui-text-primary); }
  .cs-b-user, .cs-b-her, .cs-b-tool, .cs-b-card, .cs-b-pc, .cs-b-latest, .cs-b-lb, .cs-b-dim, .cs-b-status, .cs-b-th.fresh { animation: none; }
  .cs-b-wk-body { transition: none; }
  .cs-b-mp-pop, .cs-b-sw-pop, .cs-b-ctx { animation: none; }
}
`;

// page/pages/build/build.css.js
var BUILD_CSS = `
/* build: games rail · the conversation with the agent (the game plays inside it) */
/* the page area ends with the Build area, so its background's ground and the New Game shelf share a bottom edge */
.cs-pad.build { flex: none; gap: 0; padding: 0; }
.cs-studio-needed { align-self: center; display: flex; flex-direction: column; gap: 12px; margin: 48px auto; max-width: 60ch; }
.cs-studio-needed > h2 { font-size: 1.15rem; margin: 0; }
.cs-b { display: grid; grid-template-columns: minmax(0, 1fr); height: calc(100svh - 130px); min-height: 480px; position: relative; }
.cs-b-game { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; gap: 8px; padding: 7px 8px; text-align: left; transition: background .12s ease; }
.cs-b-game[aria-current] { background: var(--ui-bg-quaternary); box-shadow: inset 2px 0 0 var(--ui-accent); color: var(--ui-text-primary); }
.cs-b-game:hover, .cs-b-game:focus-visible { background: var(--ui-bg-quaternary); }
.cs-b-game .nm { display: flex; flex: 1; flex-direction: column; min-width: 0; }
.cs-b-game .nm b { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-game .nm small { color: var(--ui-text-quaternary); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-game.wait .nm small { color: var(--ui-yellow); }
.cs-b-game .dot { background: var(--ui-text-quaternary); border-radius: 50%; flex: none; height: 6px; width: 6px; }
.cs-b-game .dot.good { background: var(--ui-green); } .cs-b-game .dot.warn { background: var(--ui-yellow); } .cs-b-game .dot.bad { background: var(--ui-red); } .cs-b-game .dot.accent { background: var(--ui-accent); }
.cs-b-game .dot.new { background: var(--ui-accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-accent) 25%, transparent); height: 7px; width: 7px; }
.cs-b-game .dot.wait { animation: cs-b-pulse-y 1.6s infinite; background: var(--ui-yellow); height: 7px; width: 7px; }
.cs-b-spin { animation: cs-b-spin .9s linear infinite; border: 2px solid var(--ui-accent); border-radius: 50%; border-right-color: transparent; display: inline-block; flex: none; height: 10px; width: 10px; }
@keyframes cs-b-spin { to { transform: rotate(360deg); } }
`;

// page/shared/styles/tokens.js
var C = {
  primary: "var(--ui-text-primary)",
  secondary: "var(--ui-text-secondary)",
  tertiary: "var(--ui-text-tertiary)",
  quaternary: "var(--ui-text-quaternary)",
  stroke: "var(--ui-stroke-tertiary)",
  fill: "var(--ui-bg-quaternary)",
  good: "var(--ui-green)",
  warn: "var(--ui-yellow)",
  bad: "var(--ui-red)"
};
var S = {
  row: { alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8 },
  col: { display: "flex", flexDirection: "column", gap: 6, minWidth: 0 },
  muted: { color: C.tertiary, fontSize: 12, lineHeight: 1.5 },
  faint: { color: C.quaternary, fontSize: 11, lineHeight: 1.5 },
  code: {
    background: C.fill,
    borderRadius: 4,
    color: C.primary,
    fontSize: 12,
    overflowWrap: "anywhere",
    padding: "4px 8px",
    userSelect: "text"
  }
};
var MONO = "var(--dt-font-mono, 'JetBrains Mono', ui-monospace, monospace)";
var DISPLAY = "'Collapse', var(--dt-font-sans, system-ui), sans-serif";

// page/pages/build/cart-shelf.css.js
var CART_SHELF_CSS = `
/* New Game shelf: the games being worked on, standing on the level's floor (--cs-at-ground, from the platformer background) */
.cs-b-attract > .cs-b-shelf, .cs-b-attract > .cs-b-shelf-probe { position: absolute; }
.cs-b-shelf-probe { height: 0; width: 0; }
.cs-b-attract { --cs-b-cap: 38px; }
/* the cartridges' bottoms on the ground's top; their captions hang below it, over the ground, at a fixed height */
.cs-b-shelf { align-items: flex-end; bottom: calc(var(--cs-at-ground, 48px) - var(--cs-b-cap)); display: flex; gap: 26px; left: 50%; pointer-events: none; transform: translateX(-50%); }
.cs-b-attract:has(> .cs-b-shelf) .cs-b-new { padding-bottom: calc(var(--cs-at-ground, 48px) + 140px); }
/* the form's menus (the model picker) open over the shelf: the form comes forward only while one is open, so the
   cartridges stay clickable the rest of the time */
.cs-b-attract:has(.cs-b-mp-pop) > .cs-b-new { z-index: 2; }
.cs-b-shelf-cart { align-items: center; display: flex; flex-direction: column; pointer-events: auto; text-align: center; width: 100px; }
.cs-b-shelf-cart .cs-cart { filter: drop-shadow(0 6px 6px color-mix(in srgb, black 45%, transparent)); width: 100px; }
.cs-b-shelf-cart .cs-cart:hover, .cs-b-shelf-cart .cs-cart:focus-visible { transform: translateY(-10px) rotate(-2deg); }
.cs-b-shelf-cart .cap { align-items: center; box-sizing: border-box; display: flex; flex-direction: column; gap: 2px; height: var(--cs-b-cap); justify-content: flex-start; padding-top: 3px; }
.cs-b-shelf-cart .cap b, .cs-b-shelf-cart .cap small { background: color-mix(in srgb, var(--cs-at-bg, var(--ui-bg-editor)) 80%, transparent); max-width: 120px; overflow: hidden; padding: 0 6px; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-shelf-cart .cap b { color: var(--ui-text-primary); font-size: 12px; font-weight: 600; line-height: 16px; }
.cs-b-shelf-cart:has(.cs-cart:hover) .cap b, .cs-b-shelf-cart:has(.cs-cart:focus-visible) .cap b { color: var(--ui-accent); }
.cs-b-shelf-cart .cap small { align-items: center; color: var(--ui-text-secondary); display: inline-flex; font-size: 10.5px; gap: 5px; line-height: 15px; }
.cs-b-shelf-cart.wait .cap small { color: var(--ui-yellow); }
.cs-b-shelf-cart .cap small .dot { border-radius: 50%; flex: none; height: 7px; width: 7px; }
.cs-b-shelf-cart .cap small .dot.wait { background: var(--ui-yellow); }
.cs-b-shelf-cart .cap small .dot.new { background: var(--ui-accent); }
.cs-b-shelf-cart .cap small .cs-b-spin { height: 8px; width: 8px; }
.cs-b-shelf-more { align-items: center; aspect-ratio: 299 / 340; background: color-mix(in srgb, var(--cs-at-bg, var(--ui-bg-editor)) 55%, transparent); border: 2px dashed var(--ui-text-quaternary, var(--ui-text-tertiary)); border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; display: grid; font: 700 18px ${MONO}; justify-content: center; width: 100px; }
.cs-b-shelf-more:hover, .cs-b-shelf-more:focus-visible { border-color: var(--ui-accent); color: var(--ui-accent); }
.cs-b-shelf-more:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 4px; }
`;

// page/app/rpc-names.js
var RPC_NAMES = Object.freeze({
  activity: `plugin.${ID}.activity`,
  asset: `plugin.${ID}.asset`,
  asset_info: `plugin.${ID}.asset_info`,
  asset_restore: `plugin.${ID}.asset_restore`,
  assets: `plugin.${ID}.assets`,
  build: `plugin.${ID}.build`,
  build_restore: `plugin.${ID}.build_restore`,
  builds: `plugin.${ID}.builds`,
  capture_image: `plugin.${ID}.capture_image`,
  captures: `plugin.${ID}.captures`,
  doctor: `plugin.${ID}.doctor`,
  game_thumb: `plugin.${ID}.game_thumb`,
  games: `plugin.${ID}.games`,
  install: `plugin.${ID}.install`,
  player: `plugin.${ID}.player`,
  presentations: `plugin.${ID}.presentations`,
  remove_tools: `plugin.${ID}.remove_tools`,
  status: `plugin.${ID}.status`,
  studio_profile: `plugin.${ID}.studio_profile`
});
var RPC_ACTIVITY = RPC_NAMES.activity;
var RPC_ASSET = RPC_NAMES.asset;
var RPC_ASSET_INFO = RPC_NAMES.asset_info;
var RPC_ASSET_RESTORE = RPC_NAMES.asset_restore;
var RPC_ASSETS = RPC_NAMES.assets;
var RPC_BUILD = RPC_NAMES.build;
var RPC_BUILD_RESTORE = RPC_NAMES.build_restore;
var RPC_BUILDS = RPC_NAMES.builds;
var RPC_CAPTURE_IMAGE = RPC_NAMES.capture_image;
var RPC_CAPTURES = RPC_NAMES.captures;
var RPC_DOCTOR = RPC_NAMES.doctor;
var RPC_GAME_THUMB = RPC_NAMES.game_thumb;
var RPC_GAMES = RPC_NAMES.games;
var RPC_INSTALL = RPC_NAMES.install;
var RPC_PLAYER = RPC_NAMES.player;
var RPC_PRESENTATIONS = RPC_NAMES.presentations;
var RPC_REMOVE_TOOLS = RPC_NAMES.remove_tools;
var RPC_STATUS = RPC_NAMES.status;
var RPC_STUDIO_PROFILE = RPC_NAMES.studio_profile;

// page/app/routing.js
var routing = { route: null, profile: null, scannedAt: 0, studio: false, ambientStudio: false };
var StudioProfileMissing = class extends Error {
  constructor() {
    super("The hermretro profile is not set up. Repair it from the Build page or Setup.");
    this.code = "STUDIO_PROFILE_MISSING";
  }
};
function studioTarget() {
  if (routing.studio && routing.route) {
    return { route: routing.route, profile: STUDIO_PROFILE };
  }
  return routing.ambientStudio || activeProfile() === STUDIO_PROFILE ? { route: null, profile: null } : null;
}
function activeProfile() {
  try {
    return host.state.profile?.get?.() ?? null;
  } catch {
    return null;
  }
}
function forgetRoute() {
  routing.route = null;
  routing.profile = null;
  routing.studio = false;
}
var ROUTE_SCAN_EVERY_MS = 3e4;
function routeProfile(route) {
  return typeof route === "string" ? route : route?.targetProfile ?? route?.profile ?? null;
}
async function findRoute() {
  if (typeof host.profileRoutes !== "function" || typeof host.requestProfile !== "function") {
    return null;
  }
  let active = null;
  try {
    active = host.state.profile?.get?.() ?? null;
  } catch {
    active = null;
  }
  const routes = [...await host.profileRoutes().catch(() => []) ?? []];
  routes.sort((a, b) => Number(routeProfile(b) === STUDIO_PROFILE) - Number(routeProfile(a) === STUDIO_PROFILE));
  for (const route of routes) {
    if (route?.profile === active) {
      continue;
    }
    try {
      const data = await host.requestProfile(route, RPC_STATUS, {});
      if (data && typeof data === "object" && "ok" in data) {
        return { route };
      }
    } catch {
    }
  }
  return null;
}
async function adoptStudioRoute() {
  if (typeof host.profileRoutes !== "function" || typeof host.requestProfile !== "function") {
    return null;
  }
  const routes = await host.profileRoutes().catch(() => []) ?? [];
  const route = routes.find((candidate) => routeProfile(candidate) === STUDIO_PROFILE);
  if (!route) {
    return null;
  }
  try {
    const data = await host.requestProfile(route, RPC_STATUS, {});
    if (data?.ok && data.profile?.is_studio) {
      routing.route = route;
      routing.profile = STUDIO_PROFILE;
      routing.studio = true;
      return data;
    }
  } catch {
  }
  return null;
}

// page/app/backend.js
function describeRequestError(error) {
  const message = String(error?.message ?? error ?? "");
  const notLoaded = error?.code === -32601 || /-32601|unknown method|method not found/i.test(message);
  return { message, notLoaded };
}
async function callBackend(method, params = {}, timeoutMs) {
  if (routing.studio && routing.route) {
    try {
      return { data: await host.requestProfile(routing.route, method, params, timeoutMs), profile: routing.profile };
    } catch (error) {
      if (!describeRequestError(error).notLoaded) {
        throw error;
      }
      routing.route = null;
      routing.profile = null;
      routing.studio = false;
    }
  }
  try {
    const data = await host.request(method, params, timeoutMs);
    routing.route = null;
    routing.profile = null;
    return { data, profile: null };
  } catch (error) {
    if (!describeRequestError(error).notLoaded) {
      throw error;
    }
    if (!routing.route && Date.now() - routing.scannedAt >= ROUTE_SCAN_EVERY_MS) {
      routing.scannedAt = Date.now();
      const found = await findRoute();
      if (found) {
        routing.route = found.route;
        routing.profile = routeProfile(found.route);
        routing.studio = routing.profile === STUDIO_PROFILE;
      }
    }
    if (!routing.route) {
      throw error;
    }
    try {
      return { data: await host.requestProfile(routing.route, method, params, timeoutMs), profile: routing.profile };
    } catch (inner) {
      if (describeRequestError(inner).notLoaded) {
        routing.route = null;
        routing.profile = null;
      }
      throw inner;
    }
  }
}
async function fetchStatus(sessionId) {
  const { data, profile } = await callBackend(RPC_STATUS, sessionId ? { chat: sessionId } : {});
  if (data?.ok && data.profile && !data.profile.is_studio && data.profile.studio?.installed && !routing.studio) {
    const studio = await adoptStudioRoute();
    if (studio) {
      return { ...studio, via_profile: STUDIO_PROFILE };
    }
  }
  return profile ? { ...data, via_profile: profile } : data;
}
async function fetchDoctor() {
  return (await callBackend(RPC_DOCTOR, {}, 6e4)).data;
}
function useBackend({ fast, pollDoctor }) {
  const gateway = useValue(host.state.gateway);
  const sessionId = useValue(host.state.focusedSessionId);
  const connected = gateway === "open";
  const status = useQuery({
    queryKey: [ID, "status", sessionId ?? null],
    queryFn: () => fetchStatus(sessionId),
    enabled: connected,
    // Cheap and passive. Poll quickly during setup so a finished step is noticed at once.
    refetchInterval: fast ? 4e3 : 3e4,
    staleTime: 2e3,
    retry: false
  });
  const statusOk = Boolean(status.data?.ok);
  const doctor = useQuery({
    queryKey: [ID, "doctor", status.data?.via_profile ?? null],
    queryFn: fetchDoctor,
    enabled: connected && statusOk,
    staleTime: Infinity,
    refetchInterval: pollDoctor ? 8e3 : false,
    refetchOnMount: "always",
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
    retry: false
  });
  let backend = "checking";
  if (!connected) {
    backend = "offline";
  } else if (status.isError) {
    backend = describeRequestError(status.error).notLoaded ? "unavailable" : "failed";
  } else if (status.data && !status.data.ok) {
    backend = "error";
  } else if (statusOk) {
    backend = "ok";
  }
  return { backend, connected, doctor, gateway, status };
}
function nodeState(node) {
  if (!node) {
    return { ok: false, label: "Unknown" };
  }
  const required = parseInt(String(node.required ?? "22"), 10) || 22;
  const major = parseInt(String(node.version ?? "").replace(/^v/i, ""), 10);
  const ok = Boolean(node.found) && Number.isFinite(major) && major >= required;
  return { ok, required, version: node.found ? node.version : null };
}
async function callStudio(method, params = {}, timeoutMs) {
  return routing.route ? host.requestProfile(routing.route, method, params, timeoutMs) : host.request(method, params, timeoutMs);
}
async function callStudioOnly(method, params = {}, timeoutMs) {
  const target = studioTarget();
  if (!target) {
    throw new StudioProfileMissing();
  }
  return target.route ? host.requestProfile(target.route, method, params, timeoutMs) : host.request(method, params, timeoutMs);
}
function studioError(error, what) {
  const { message, notLoaded } = describeRequestError(error);
  return notLoaded ? `This hermretro backend cannot ${what} yet. Update the plugin in the profile it runs in.` : message || "Unknown error";
}

// page/app/update/lock.js
var UPDATE_LOCK = atom(false);
function isUpdating() {
  return Boolean(UPDATE_LOCK.get());
}
function useUpdating() {
  return Boolean(useValue(UPDATE_LOCK));
}
function setUpdating(active) {
  UPDATE_LOCK.set(Boolean(active));
}
var UPDATING_MESSAGE = "hermretro is updating. You can start again in a moment.";

// page/pages/build/chat/attachments.js
var attachmentKey = (item) => item.key ?? item.path;
function mergeAttachments(current, more) {
  const known = new Set(current.map(attachmentKey));
  return [...current, ...more.filter((item) => !known.has(attachmentKey(item)))];
}
var attachmentLine = (item) => item.detail ?? `About ${item.path}:`;

// page/app/tools.js
var PRESENT_TOOL = "chromatic_present_game";
var BUILD_TOOLS = /* @__PURE__ */ new Set(["chromatic_rom_build", "chromatic_web_preview"]);
var REPORT_TOOL = "chromatic_build_report";

// page/pages/build/chat/report.js
var REPORT_KINDS = /* @__PURE__ */ new Set(["added", "changed", "removed"]);
function normalizeReport(value) {
  if (!value || typeof value !== "object") {
    return null;
  }
  const line = (text2, max) => typeof text2 === "string" && text2.trim() ? text2.trim().slice(0, max) : null;
  const lines = (list, count, max) => Array.isArray(list) ? list.map((item) => line(item, max)).filter(Boolean).slice(0, count) : [];
  const title = line(value.title, 60);
  const summary = line(value.summary, 400);
  if (!title && !summary) {
    return null;
  }
  return {
    title,
    summary,
    changes: (Array.isArray(value.changes) ? value.changes : []).map((change) => ({
      kind: REPORT_KINDS.has(change?.kind) ? change.kind : "changed",
      text: line(change?.text, 140),
      asset: line(change?.asset, 4096)
    })).filter((change) => change.text).slice(0, 8),
    tested: lines(value.tested, 6, 100),
    untested: lines(value.untested, 6, 100),
    notes: lines(value.notes, 3, 200),
    suggestions: lines(value.suggestions, 4, 60)
  };
}
var reportOf = (name, args) => String(name ?? "") === REPORT_TOOL ? normalizeReport(args) : null;

// page/pages/build/chat/tool-results.js
function toolResultObject(value) {
  if (value && typeof value === "object") {
    return value._multimodal ? toolResultObject(value.text_summary ?? value.content?.[0]?.text) : value;
  }
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch {
      return null;
    }
  }
  return null;
}
function unwrapCalls(id, name, args) {
  let parsed = args;
  if (typeof parsed === "string") {
    try {
      parsed = JSON.parse(parsed);
    } catch {
      parsed = null;
    }
  }
  if (name === "tool_call" && Array.isArray(parsed?.calls) && parsed.calls.length) {
    return parsed.calls.map((call, index) => {
      let inner = call?.arguments ?? null;
      if (typeof inner === "string") {
        try {
          inner = JSON.parse(inner);
        } catch {
          inner = null;
        }
      }
      return { id: id == null ? null : `${id}:${index}`, name: String(call?.name ?? "tool"), args: inner && typeof inner === "object" ? inner : null };
    });
  }
  return [{ id, name: String(name ?? "tool"), args: parsed && typeof parsed === "object" ? parsed : null }];
}

// page/pages/build/chat/steps.js
function toolFailed(payload) {
  const result = toolResultObject(payload?.result);
  return Boolean(
    payload?.error || result?.ok === false || result?.isError === true || result?.structuredContent?.success === false || result && typeof result.error === "string" && result.error
  );
}
function engineError(parsed, content) {
  if (content.success !== false) {
    return null;
  }
  const diagnostics = Array.isArray(content.diagnostics) ? content.diagnostics : [];
  const error = diagnostics.find((item) => item?.severity === "error" && typeof item.message === "string");
  return error?.message ?? (typeof parsed.result === "string" && parsed.result ? parsed.result : null);
}
var STEP_ARG_KEYS = ["name", "file_path", "path", "command", "image_url", "assetPath", "outputPath", "kind", "query", "url", "question", "questions", "goal", "sceneId", "note"];
function stepArgs(args) {
  if (!args || typeof args !== "object") {
    return null;
  }
  const kept = {};
  for (const key of STEP_ARG_KEYS) {
    const value = args[key];
    if (typeof value === "string") {
      kept[key] = value.length > 400 ? `${value.slice(0, 400)}…` : value;
    } else if (key === "questions" && Array.isArray(value)) {
      kept.questions = value.slice(0, 8).map((question) => typeof question === "string" ? question : String(question?.question ?? "")).filter(Boolean);
    }
  }
  return Object.keys(kept).length ? kept : null;
}
function stepInfo(name, result) {
  const parsed = toolResultObject(result);
  if (!parsed || typeof parsed !== "object") {
    return null;
  }
  const content = parsed.structuredContent && typeof parsed.structuredContent === "object" ? parsed.structuredContent : {};
  const text2 = (value) => typeof value === "string" && value ? value : null;
  const images = (Array.isArray(parsed.images) ? parsed.images : []).map((image) => typeof image?.file === "string" ? image.file.replace(/^MEDIA:/, "") : null).filter(Boolean).slice(0, 8);
  return {
    error: (text2(parsed.error) ?? engineError(parsed, content))?.slice(0, 400) ?? null,
    projectRoot: text2(content.projectRoot),
    assetPath: text2(content.assetPath),
    outputPath: text2(content.outputPath) ?? (text2(content.path) && /\.(png|gif)$/i.test(content.path) ? content.path : null),
    images,
    note: String(name ?? "") === PRESENT_TOOL && parsed.ok === true ? text2(parsed.studio?.note) : null,
    report: String(name ?? "") === REPORT_TOOL && parsed.ok === true ? normalizeReport(parsed.report) : null
  };
}
function withInfo(chat, info) {
  if (!info || typeof info !== "object") {
    return chat;
  }
  const current = chat.info ?? {};
  const next = {
    model: typeof info.model === "string" && info.model ? info.model : current.model ?? null,
    provider: typeof info.provider === "string" && info.provider ? info.provider : current.provider ?? null,
    effort: typeof info.reasoning_effort === "string" ? info.reasoning_effort : current.effort ?? "",
    fast: typeof info.fast === "boolean" ? info.fast : current.fast ?? false
  };
  return next.model === current.model && next.provider === current.provider && next.effort === current.effort && next.fast === current.fast ? chat : { ...chat, info: next };
}

// page/pages/build/chat/store.js
var BUILD_VIEWING = atom(null);
var BUILD_PRESENTED = atom({});
function notePresented({ gameId, seq, note, t }) {
  BUILD_PRESENTED.set({ ...BUILD_PRESENTED.get(), [gameId]: { seq, note, t } });
}
var buildShowing = () => BUILD_VIEWING.get();
var BUILD_INJECT = atom({});
function injectBuildDraft(stored, text2) {
  const all = BUILD_INJECT.get();
  BUILD_INJECT.set({ ...all, [stored]: { seq: (all[stored]?.seq ?? 0) + 1, text: text2 } });
}
var BUILD_CHATS = atom({});
var BUILD_STARTING = atom(/* @__PURE__ */ new Set());
var buildRuntime = /* @__PURE__ */ new Map();
var isBuildSession = (runtime) => buildRuntime.has(runtime);
var buildRetained = /* @__PURE__ */ new Map();
var BUILD_EVENTS = [
  "message.start",
  "message.delta",
  "message.interim",
  "message.complete",
  "reasoning.delta",
  "thinking.delta",
  "status.update",
  "tool.generating",
  "tool.start",
  "tool.progress",
  "tool.complete",
  "approval.request",
  "clarify.request",
  "approval.settled",
  "clarify.settled",
  "error",
  "session.replay_gap",
  "session.info"
];
var newId = () => typeof randomUuid === "function" ? randomUuid() : globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
async function retainChatRoute() {
  const route = studioTarget()?.route;
  if (!route || typeof host.retainProfile !== "function") {
    return;
  }
  const key = routeProfile(route) ?? "default";
  if (buildRetained.has(key)) {
    return;
  }
  try {
    buildRetained.set(key, await host.retainProfile(route, { spawnPriority: "foreground" }));
  } catch (error) {
    console.warn("[hermretro] could not keep the studio profile connection open:", describeRequestError(error).message);
  }
}
async function chatRequest(method, params = {}, timeoutMs) {
  const target = studioTarget();
  if (!target) {
    throw new StudioProfileMissing();
  }
  const { route } = target;
  return route ? host.requestProfile(route, method, params, timeoutMs, { spawnPriority: "foreground" }) : host.request(method, params, timeoutMs);
}
function patchChat(stored, change) {
  const all = BUILD_CHATS.get();
  const current = all[stored] ?? { stored, items: [], busy: false, segments: {} };
  const next = change(current);
  if (next !== current) {
    BUILD_CHATS.set({ ...all, [stored]: next });
  }
}

// page/pages/build/chat/model-pick.js
var FAST_PROVIDERS = /* @__PURE__ */ new Set(["openai-codex", "openai-api"]);
var hasFastMode = (provider, caps) => FAST_PROVIDERS.has(provider) && caps?.fast === true;
var failedAt = /* @__PURE__ */ new Map();
async function pickBuildModel(stored, pick) {
  const chat = BUILD_CHATS.get()[stored];
  if (!chat?.runtime) {
    return { ok: false };
  }
  patchChat(stored, (current) => ({ ...current, heldPick: { ...current.heldPick ?? {}, ...pick } }));
  return chat.busy ? { ok: true, held: true } : applyBuildPick(stored);
}
async function applyBuildPick(stored, { confirmed = false } = {}) {
  const chat = BUILD_CHATS.get()[stored];
  const pick = chat?.heldPick;
  if (!chat?.runtime || !pick || chat.applyingPick) {
    return { ok: false };
  }
  patchChat(stored, (current) => ({ ...current, applyingPick: true }));
  try {
    if (pick.model && pick.provider) {
      const answer = await chatRequest("config.set", {
        session_id: chat.runtime,
        key: "model",
        value: `${pick.model} --provider ${pick.provider} --session`,
        ...confirmed ? { confirm_expensive_model: true } : {}
      });
      if (answer?.confirm_required) {
        patchChat(stored, (current) => ({ ...current, applyingPick: false, pickConfirm: { message: String(answer.confirm_message || "This model costs more to run.") } }));
        return { ok: false, confirm: true };
      }
      patchChat(stored, (current) => withInfo(current, { model: pick.model, provider: pick.provider }));
    }
    if (pick.effort) {
      await chatRequest("config.set", { session_id: chat.runtime, key: "reasoning", value: pick.effort });
      patchChat(stored, (current) => withInfo(current, { reasoning_effort: pick.effort }));
    }
    const fast = pick.fast === true && pick.model && pick.fastOk === false ? false : pick.fast;
    if (typeof fast === "boolean") {
      await chatRequest("config.set", { session_id: chat.runtime, key: "fast", value: fast ? "fast" : "normal" });
      patchChat(stored, (current) => withInfo(current, { fast }));
    }
    patchChat(stored, (current) => {
      const { heldPick, applyingPick: _applying, pickConfirm: _confirm, ...rest } = current;
      const newer = heldPick && heldPick !== pick ? heldPick : null;
      return newer ? { ...rest, heldPick: newer } : rest;
    });
    const next = BUILD_CHATS.get()[stored];
    if (next?.heldPick && !next.busy) {
      void applyBuildPick(stored);
    }
    return { ok: true };
  } catch (error) {
    const { message } = describeRequestError(error);
    failedAt.set(stored, Date.now());
    patchChat(stored, (current) => {
      const { heldPick: _held, applyingPick: _applying, pickConfirm: _confirm, ...rest } = current;
      return rest;
    });
    host.notify({ kind: "error", message: `Could not switch: ${message}` });
    return { ok: false };
  }
}
async function settleBuildPick(stored, limitMs = 3e4) {
  const since = Date.now();
  while (Date.now() - since < limitMs) {
    const chat = BUILD_CHATS.get()[stored];
    if ((failedAt.get(stored) ?? 0) >= since) {
      return { ok: false };
    }
    if (!chat?.heldPick || chat.pickConfirm) {
      return { ok: true };
    }
    if (!chat.applyingPick) {
      await applyBuildPick(stored);
    } else {
      await new Promise((done) => setTimeout(done, 25));
    }
  }
  return { ok: true };
}
function cancelBuildPick(stored) {
  patchChat(stored, (current) => {
    const { heldPick: _held, pickConfirm: _confirm, applyingPick: _applying, ...rest } = current;
    return rest;
  });
}

// page/pages/build/chat/history.js
function messageText(message) {
  if (typeof message.text === "string" && message.text) {
    return message.text;
  }
  if (typeof message.content === "string") {
    return message.content;
  }
  return Array.isArray(message.content) ? message.content.map((part) => part?.type === "text" && typeof part.text === "string" ? part.text : "").join("") : "";
}
function historyItems(messages, running = false) {
  const items = [];
  const tools = /* @__PURE__ */ new Map();
  let agentSinceUser = false;
  let lastAt = null;
  const closeTurn = () => {
    if (agentSinceUser) {
      const startedAt = [...items].reverse().find((item) => item.kind === "user")?.at ?? null;
      items.push({ kind: "end", status: "complete", at: lastAt, startedAt, history: true });
    }
    agentSinceUser = false;
  };
  const addTool = (call, at) => {
    if (call.id && tools.has(call.id)) {
      return;
    }
    const tool = { id: call.id ?? `${items.length}`, name: call.name, args: stepArgs(call.args), report: reportOf(call.name, call.args), state: "done", startedAt: at };
    const last = items[items.length - 1];
    if (call.id) {
      tools.set(call.id, tool);
    }
    if (last?.kind === "tools") {
      last.tools.push(tool);
    } else {
      items.push({ kind: "tools", tools: [tool] });
    }
  };
  for (const message of Array.isArray(messages) ? messages : []) {
    if (!message || message.display_kind === "hidden") {
      continue;
    }
    const text2 = messageText(message);
    const at = typeof message.timestamp === "number" && message.timestamp > 0 ? message.timestamp * 1e3 : null;
    if (message.role === "user") {
      if (!text2.trim()) {
        continue;
      }
      closeTurn();
      items.push({ kind: "user", text: text2, at });
    } else if (message.role === "assistant") {
      agentSinceUser = true;
      if (text2.trim()) {
        items.push({ kind: "assistant", open: false, text: text2, at });
      }
      for (const call of Array.isArray(message.tool_calls) ? message.tool_calls : []) {
        for (const inner of unwrapCalls(call?.id ?? null, call?.function?.name ?? call?.name, call?.function?.arguments ?? call?.args)) {
          addTool(inner, at);
        }
      }
    } else if (message.role === "tool") {
      agentSinceUser = true;
      for (const inner of unwrapCalls(message.tool_call_id ?? null, message.name, message.args)) {
        const known = inner.id && (tools.get(inner.id) ?? (!message.name || message.name === "tool_call" ? tools.get(`${inner.id}:0`) : null));
        if (known) {
          if (at && known.startedAt) {
            known.duration = Math.max(0, (at - known.startedAt) / 1e3);
          }
          known.args = known.args ?? stepArgs(inner.args);
          const result = text2.trim().startsWith("{") ? text2 : null;
          if (result) {
            known.info = stepInfo(known.name, result);
            if (toolFailed({ result })) {
              known.state = "failed";
            }
          }
        } else {
          addTool(inner, at);
        }
      }
    }
    if (at) {
      lastAt = at;
    }
  }
  if (!running) {
    closeTurn();
  }
  return items;
}

// page/pages/build/chat/reducer.js
var lastItem = (chat) => chat.items[chat.items.length - 1];
function sealText(chat) {
  const last = lastItem(chat);
  return last?.kind === "assistant" && last.open ? { ...chat, items: [...chat.items.slice(0, -1), { ...last, open: false }] } : chat;
}
function appendText(chat, text2) {
  const last = lastItem(chat);
  if (last?.kind === "assistant" && last.open) {
    return { ...chat, items: [...chat.items.slice(0, -1), { ...last, text: last.text + text2 }] };
  }
  return { ...chat, items: [...chat.items, { kind: "assistant", open: true, text: text2 }] };
}
function updateTool(chat, id, change) {
  if (id == null) {
    return chat;
  }
  const key = String(id);
  let hit = false;
  const items = chat.items.map((item) => {
    if (item.kind !== "tools" || !item.tools.some((tool) => tool.id === key || String(tool.id).startsWith(`${key}:`))) {
      return item;
    }
    hit = true;
    return { ...item, tools: item.tools.map((tool) => tool.id === key || String(tool.id).startsWith(`${key}:`) ? change(tool) : tool) };
  });
  return hit ? { ...chat, items } : chat;
}
function touched(chat, now = Date.now()) {
  return now - (chat.lastEventAt ?? 0) > 500 ? { ...chat, lastEventAt: now } : chat;
}
function withActivity(chat, activity) {
  return chat.activity === activity ? chat : { ...chat, activity };
}
function endTurn(chat, status, now = Date.now()) {
  const items = sealText(chat).items.map(
    (item) => item.kind === "tools" && item.tools.some((tool) => tool.state === "running") ? { ...item, tools: item.tools.map((tool) => tool.state === "running" ? { ...tool, state: status === "interrupted" ? "stopped" : "done" } : tool) } : item
  );
  return {
    ...chat,
    items: [...items, { kind: "end", status, at: now, startedAt: chat.turnStartedAt ?? null }],
    busy: false,
    waiting: false,
    turnText: 0,
    activity: null,
    turnStartedAt: null,
    lastCompleteAt: now,
    lastEventAt: now
  };
}
function lostTurns(pending) {
  return Array.isArray(pending) ? pending.filter((row) => row?.status === "unknown" && typeof row.admission_id === "string").map((row) => ({ id: row.admission_id })) : [];
}
function reduceChat(chat, event) {
  const payload = event.payload ?? {};
  const epoch = event.replay_epoch ?? payload.replay_epoch;
  if (typeof epoch === "string" && epoch !== chat.epoch) {
    chat = { ...chat, epoch, seq: null, segments: {} };
  }
  if (typeof event.seq === "number") {
    if (typeof chat.seq === "number" && event.seq <= chat.seq) {
      return chat;
    }
    chat = { ...chat, seq: event.seq };
  }
  const now = Date.now();
  switch (event.type) {
    case "message.start": {
      const [next, ...rest] = !chat.busy || lastItem(chat)?.kind === "end" ? chat.queued ?? [] : [];
      if (next) {
        chat = { ...sealText(chat), items: [...sealText(chat).items, { ...next, at: now }], queued: rest };
      }
      return {
        ...sealText(chat),
        busy: true,
        turn: payload.turn_id ?? null,
        turnText: 0,
        segments: {},
        activity: "thinking",
        turnStartedAt: chat.busy && chat.turnStartedAt ? chat.turnStartedAt : now,
        lastEventAt: now
      };
    }
    case "message.delta": {
      if (payload.text == null) {
        return sealText(chat);
      }
      let text2 = String(payload.text);
      if (typeof payload.offset === "number") {
        const key = `${payload.turn_id ?? ""}:${payload.segment ?? 0}`;
        const applied = chat.segments?.[key] ?? 0;
        if (payload.offset + text2.length <= applied) {
          return chat;
        }
        text2 = payload.offset < applied ? text2.slice(applied - payload.offset) : text2;
        chat = { ...chat, segments: { ...chat.segments, [key]: payload.offset + payload.text.length } };
      }
      return text2 ? touched(withActivity({ ...appendText(chat, text2), turnText: (chat.turnText ?? 0) + text2.length }, "writing"), now) : chat;
    }
    case "reasoning.delta":
    case "thinking.delta":
      return chat.busy ? touched(withActivity(chat, "thinking"), now) : chat;
    case "status.update": {
      const kind = String(payload.kind ?? "");
      if (/compress|compact/.test(kind) && chat.busy) {
        return touched(withActivity(chat, "compacting"), now);
      }
      return chat.activity === "compacting" && kind === "ready" ? withActivity(chat, "thinking") : chat;
    }
    case "message.interim":
      return payload.already_streamed || !payload.text ? sealText(chat) : { ...sealText(chat), items: [...sealText(chat).items, { kind: "assistant", open: false, text: String(payload.text) }], turnText: (chat.turnText ?? 0) + 1 };
    case "tool.generating":
      return chat.busy ? touched(withActivity(chat, "preparing"), now) : chat;
    case "tool.start": {
      if (payload.tool_id != null && updateTool(chat, payload.tool_id, (tool) => tool) !== chat) {
        return chat;
      }
      const sealed = sealText(chat);
      const tools = unwrapCalls(payload.tool_id ?? `t${now}`, String(payload.name ?? ""), payload.args).map((call) => ({
        id: call.id,
        name: call.name,
        args: stepArgs(call.args),
        report: reportOf(call.name, call.args),
        preview: payload.preview ?? payload.context ?? null,
        state: "running",
        startedAt: now
      }));
      const last = lastItem(sealed);
      const items = last?.kind === "tools" ? [...sealed.items.slice(0, -1), { ...last, tools: [...last.tools, ...tools] }] : [...sealed.items, { kind: "tools", tools }];
      return { ...sealed, items, activity: "tool", lastEventAt: now };
    }
    case "tool.progress": {
      const progress2 = { percent: typeof payload.percent === "number" ? payload.percent : null, message: payload.message ?? null };
      return touched(updateTool(chat, payload.tool_id, (tool) => ({ ...tool, progress: progress2 })), now);
    }
    case "tool.complete": {
      const done = (tool) => ({
        ...tool,
        args: tool.args ?? stepArgs(payload.args),
        report: tool.report ?? reportOf(tool.name, unwrapCalls(null, String(payload.name ?? ""), payload.args)[0]?.args),
        state: toolFailed(payload) ? "failed" : "done",
        summary: payload.summary ?? null,
        duration: typeof payload.duration_s === "number" ? payload.duration_s : tool.startedAt ? (now - tool.startedAt) / 1e3 : null,
        image: typeof payload.image_path === "string" ? payload.image_path : null,
        info: stepInfo(tool.name, payload.result),
        progress: null
      });
      const updated = updateTool(chat, payload.tool_id, done);
      const next = updated !== chat ? updated : {
        ...sealText(chat),
        items: [
          ...sealText(chat).items,
          { kind: "tools", tools: unwrapCalls(payload.tool_id ?? `t${now}`, String(payload.name ?? ""), payload.args).map((call) => done({ id: call.id, name: call.name, args: stepArgs(call.args), report: reportOf(call.name, call.args) })) }
        ]
      };
      return { ...next, activity: chat.busy ? "thinking" : chat.activity, lastEventAt: now };
    }
    case "message.complete": {
      if (!chat.busy && lastItem(chat)?.kind === "end") {
        return chat;
      }
      let next = sealText(chat);
      const text2 = typeof payload.text === "string" ? payload.text : "";
      if (text2 && !payload.response_reused && !(chat.turnText > 0)) {
        next = { ...next, items: [...next.items, { kind: "assistant", open: false, text: text2 }] };
      }
      const failure = payload.error ?? payload.failure_reason ?? (payload.status === "error" ? "The turn failed." : null);
      if (failure) {
        next = { ...next, items: [...next.items, { kind: "error", text: String(failure) }] };
      }
      return endTurn(next, payload.status === "interrupted" ? "interrupted" : failure ? "error" : "complete", now);
    }
    case "approval.request":
    case "clarify.request": {
      const requestId = payload.request_id ?? payload.prompt_id ?? null;
      if (requestId && chat.items.some((item) => item.requestId === requestId)) {
        return chat;
      }
      return {
        ...sealText(chat),
        waiting: true,
        lastEventAt: now,
        items: [...sealText(chat).items, { kind: event.type === "approval.request" ? "approval" : "clarify", payload, requestId }]
      };
    }
    case "approval.settled":
    case "clarify.settled": {
      const requestId = payload.request_id ?? payload.prompt_id ?? null;
      const items = chat.items.map(
        (item) => requestId && item.requestId === requestId && !item.answered ? { ...item, answered: "answered" } : item
      );
      return { ...chat, items, waiting: items.some((item) => item.requestId && !item.answered) };
    }
    case "session.info": {
      const next = withInfo(chat, payload);
      if (!Array.isArray(payload.pending)) {
        return next;
      }
      const lost = lostTurns(payload.pending);
      const known = next.lost ?? [];
      const changed2 = lost.length !== known.length || lost.some((turn, index) => turn.id !== known[index].id);
      const out = changed2 ? { ...next, lost } : next;
      return lost.length && out.busy && payload.running === false ? { ...out, busy: false, waiting: false, activity: null, turnStartedAt: null } : out;
    }
    case "error": {
      const next = { ...sealText(chat), items: [...sealText(chat).items, { kind: "error", text: String(payload.message ?? "Something went wrong.") }] };
      return chat.busy ? endTurn(next, "error", now) : { ...next, busy: false, waiting: false };
    }
    default:
      return chat;
  }
}

// page/pages/build/chat/requests.js
var promptChecks = /* @__PURE__ */ new Map();
function toolRunning(chat) {
  return Boolean(chat?.busy && chat.items.some((item) => item.kind === "tools" && item.tools.some((tool) => tool.state === "running")));
}
function mergeOpenRequests(chat, open) {
  const ids = new Set(open.map((request) => request.id));
  const known = new Set(chat.items.filter((item) => item.requestId).map((item) => item.requestId));
  const items = chat.items.map(
    (item) => item.requestId && !item.answered && !ids.has(item.requestId) ? { ...item, answered: "answered elsewhere" } : item
  );
  const added = open.filter((request) => !known.has(request.id)).map((request) => ({ kind: request.method === "approval" ? "approval" : "clarify", requestId: request.id, payload: request.params ?? {} }));
  return added.length || items.some((item, index) => item !== chat.items[index]) ? { ...chat, items: [...items, ...added], waiting: added.length > 0 || items.some((item) => item.requestId && !item.answered) } : chat;
}
async function checkOpenRequests(stored) {
  promptChecks.delete(stored);
  const chat = BUILD_CHATS.get()[stored];
  if (!chat?.runtime || !chat.busy) {
    return;
  }
  try {
    const snapshot = await chatRequest("session.resume", { session_id: stored, omit_messages: true });
    const open = (Array.isArray(snapshot?.open_requests) ? snapshot.open_requests : []).filter(
      (request) => request && typeof request.id === "string" && (request.method === "clarify" || request.method === "approval")
    );
    patchChat(stored, (current) => {
      const merged = mergeOpenRequests(current, open);
      return snapshot?.running === false && !open.length && merged.busy ? endTurn(merged, "complete") : merged;
    });
    patchChat(stored, (current) => current.unreachable ? { ...current, unreachable: 0 } : current);
    if (!BUILD_CHATS.get()[stored]?.busy && BUILD_CHATS.get()[stored]?.heldPick) {
      void applyBuildPick(stored);
    }
  } catch {
    patchChat(stored, (current) => ({ ...current, unreachable: (current.unreachable ?? 0) + 1 }));
  }
  if (BUILD_CHATS.get()[stored]?.busy) {
    schedulePromptCheck(stored, toolRunning(BUILD_CHATS.get()[stored]) ? 2500 : 4e3);
  }
}
function schedulePromptCheck(stored, delay = 1200) {
  if (!promptChecks.has(stored)) {
    promptChecks.set(stored, setTimeout(() => void checkOpenRequests(stored), delay));
  }
}
var APPROVAL_LABELS = { once: "Allow once", session: "Allow for this chat", always: "Always allow", deny: "Deny" };

// page/pages/build/chat/actions.js
async function openBuildChat(stored) {
  const known = BUILD_CHATS.get()[stored];
  if (known?.runtime || known?.opening) {
    return;
  }
  patchChat(stored, (chat) => ({ ...chat, opening: true, failure: null }));
  await retainChatRoute();
  try {
    const result = await chatRequest("session.resume", { session_id: stored }, 6e4);
    const runtime = result?.session_id;
    if (runtime) {
      buildRuntime.set(runtime, stored);
    }
    const running = typeof result?.running === "boolean" ? result.running : Boolean(BUILD_CHATS.get()[stored]?.busy);
    const pending = result?.pending ?? result?.info?.pending_submissions;
    const at = Date.now();
    patchChat(stored, (chat) => ({
      ...withInfo(chat, result?.info),
      runtime,
      opening: false,
      items: historyItems(result?.messages, running),
      // Messages Hermes holds for later (behind a running or lost turn) wait under the conversation.
      queued: (Array.isArray(pending) ? pending : []).filter((row) => row?.status === "queued" && typeof row.text === "string" && row.text).map((row) => ({ kind: "user", text: row.text, at })),
      lost: lostTurns(pending),
      lostFailure: null,
      missing: false,
      busy: running,
      activity: running ? chat.activity ?? "thinking" : null,
      turnStartedAt: running ? chat.turnStartedAt ?? Date.now() : null,
      lastEventAt: Date.now(),
      unreachable: 0
    }));
  } catch (error) {
    const { message } = describeRequestError(error);
    const missing = error?.code === 4007 || /^session not found$/i.test(message.trim());
    patchChat(stored, (chat) => ({ ...chat, opening: false, failure: message, missing }));
  }
}
async function reopenBuildChat(stored) {
  const known = BUILD_CHATS.get()[stored];
  if (known?.opening) {
    return;
  }
  for (const [runtime, owner] of buildRuntime) {
    if (owner === stored) {
      buildRuntime.delete(runtime);
    }
  }
  patchChat(stored, (chat2) => ({ ...chat2, runtime: null, seq: null, epoch: null, segments: {}, failure: null }));
  await openBuildChat(stored);
  const chat = BUILD_CHATS.get()[stored];
  if (chat?.runtime && chat.busy) {
    schedulePromptCheck(stored);
  }
}
async function createBuildChat(title, pick = null) {
  await retainChatRoute();
  const choice = {
    ...pick?.model && pick?.provider ? { model: pick.model, provider: pick.provider } : {},
    ...pick?.effort ? { reasoning_effort: pick.effort } : {},
    ...typeof pick?.fast === "boolean" && FAST_PROVIDERS.has(pick?.provider) ? { fast: pick.fast } : {}
  };
  const result = await chatRequest("session.create", { hidden: true, source: "gui", ...choice }, 6e4);
  const stored = result?.stored_session_id ?? result?.session_id;
  const runtime = result?.session_id;
  const info = result?.info;
  if (!stored || !runtime) {
    throw new Error("Hermes did not return a session.");
  }
  if (result.message_count > 0 || result.messages?.length) {
    throw new Error("Hermes returned an existing conversation. Your message was not sent.");
  }
  if (choice.model && (info?.model !== choice.model || info?.provider !== choice.provider)) {
    throw new Error(`Hermes did not confirm ${choice.model} (${choice.provider}) for the new conversation. Your message was not sent.`);
  }
  buildRuntime.set(runtime, stored);
  patchChat(stored, (chat) => ({ ...withInfo(chat, info), runtime, title, items: [] }));
  return stored;
}
async function sendBuildChat(stored, text2, shown = text2, attachments = [], { mustLand = false } = {}) {
  if (isUpdating()) {
    host.notify({ kind: "warning", message: UPDATING_MESSAGE });
    return false;
  }
  if (!BUILD_CHATS.get()[stored]?.runtime) {
    await openBuildChat(stored);
    if (isUpdating()) {
      host.notify({ kind: "warning", message: UPDATING_MESSAGE });
      return false;
    }
  }
  const before = BUILD_CHATS.get()[stored];
  const settled = before?.runtime && !before.busy && before.heldPick ? await settleBuildPick(stored) : { ok: true };
  const chat = BUILD_CHATS.get()[stored];
  const now = Date.now();
  const live = Boolean(chat?.runtime);
  const paused = Boolean(chat?.lost?.length);
  const behindTurn = Boolean(chat?.busy) || paused;
  patchChat(stored, (current) => ({
    ...current,
    busy: live && !paused,
    activity: live && !paused ? "thinking" : current.activity,
    turnStartedAt: live && !paused ? current.busy && current.turnStartedAt ? current.turnStartedAt : now : current.turnStartedAt,
    lastEventAt: now,
    items: [
      ...sealText(current).items,
      { kind: "user", text: shown, at: now, ...current.info?.model ? { model: current.info.model, effort: current.info.effort ?? "" } : {}, ...attachments.length ? { attachments } : {} }
    ]
  }));
  if (!chat?.runtime) {
    patchChat(stored, (current) => ({ ...current, items: [...current.items, { kind: "error", text: "This conversation could not be opened, so the message was not sent." }] }));
    return !mustLand;
  }
  if (!settled.ok) {
    patchChat(stored, (current) => endTurn({ ...current, items: [...current.items, { kind: "error", text: "The model change did not go through, so the message was not sent.", resend: { text: text2, shown, attachments } }] }, "error"));
    return !mustLand;
  }
  schedulePromptCheck(stored);
  try {
    const named = attachments.length ? `${attachments.map(attachmentLine).join("\n")}
${text2}` : text2;
    const reply = await chatRequest("prompt.submit", { session_id: chat.runtime, submission_id: newId(), text: named });
    if (reply?.status === "queued" && behindTurn) {
      patchChat(stored, (current) => {
        const index = current.items.findLastIndex((item2) => item2.kind === "user" && item2.at === now);
        if (index === -1) {
          return current;
        }
        const item = current.items[index];
        return { ...current, items: [...current.items.slice(0, index), ...current.items.slice(index + 1)], queued: [...current.queued ?? [], item] };
      });
    }
  } catch (error) {
    const { message } = describeRequestError(error);
    patchChat(stored, (current) => endTurn({ ...current, items: [...current.items, { kind: "error", text: message, resend: { text: text2, shown, attachments } }] }, "error"));
    if (/not.?found|4007|unknown session/i.test(message)) {
      void reopenBuildChat(stored);
    }
    return !mustLand;
  }
  return true;
}
async function stopBuildChat(stored) {
  const chat = BUILD_CHATS.get()[stored];
  if (chat?.runtime) {
    await chatRequest("session.interrupt", { session_id: chat.runtime }).catch(() => {
    });
  }
}
async function resumeBuildChat(stored) {
  const chat = BUILD_CHATS.get()[stored];
  if (!chat?.runtime || chat.resuming) {
    return;
  }
  if (isUpdating()) {
    host.notify({ kind: "warning", message: UPDATING_MESSAGE });
    return;
  }
  patchChat(stored, (current) => ({ ...current, resuming: true, lostFailure: null }));
  try {
    const snapshot = await chatRequest("session.resume", { session_id: stored, omit_messages: true }, 6e4);
    const runtime = snapshot?.session_id ?? chat.runtime;
    const pending = snapshot?.pending ?? snapshot?.info?.pending_submissions ?? [];
    for (const turn of lostTurns(pending)) {
      if (isUpdating()) {
        patchChat(stored, (current) => ({ ...current, resuming: false }));
        host.notify({ kind: "warning", message: UPDATING_MESSAGE });
        return;
      }
      await chatRequest("prompt.resolve_unknown", { session_id: runtime, admission_id: turn.id });
    }
    const waiting = Array.isArray(pending) && pending.some((row) => row?.status === "queued");
    patchChat(stored, (current) => ({ ...current, lost: [], resuming: false }));
    if (!waiting) {
      await sendBuildChat(stored, "Your last turn was cut off when Hermes restarted. Continue where you left off.", "Continue");
    }
  } catch (error) {
    patchChat(stored, (current) => ({ ...current, resuming: false, lostFailure: describeRequestError(error).message }));
  }
}
async function answerBuildPrompt(stored, item, answer) {
  const chat = BUILD_CHATS.get()[stored];
  if (!chat?.runtime) {
    return;
  }
  const payload = item.payload ?? {};
  let call;
  if (item.requestId && item.kind === "clarify") {
    call = (async () => {
      try {
        for (const [qid, value] of Object.entries(answer ?? {})) {
          await chatRequest("clarify.lock", { request_id: item.requestId, question_id: qid, answer: value ?? "" });
        }
      } catch (error) {
        if (!describeRequestError(error).notLoaded) {
          throw error;
        }
        const reply = await chatRequest("request.answer", { id: item.requestId, result: { answers: answer, outcome: "submitted" } });
        if (reply?.status === "expired") {
          throw new Error("That question has already closed.");
        }
      }
    })();
  } else if (item.kind === "approval") {
    call = chatRequest("approval.respond", { session_id: chat.runtime, choice: answer, ...payload.request_id ? { request_id: payload.request_id } : {} });
  } else {
    const id = payload.prompt_id ?? payload.request_id;
    const text2 = typeof answer === "string" ? answer : Object.values(answer ?? {}).filter(Boolean).join("; ");
    call = chatRequest("clarify.respond", { session_id: chat.runtime, answer: text2, ...id ? { request_id: id } : {} });
  }
  try {
    await call;
    const label = typeof answer === "string" ? answer : Object.values(answer ?? {}).map((value) => value ?? "skipped").join("; ");
    const picked = typeof answer === "string" ? [APPROVAL_LABELS[answer] ?? answer] : Object.values(answer ?? {}).map((value) => String(value ?? "skipped"));
    patchChat(stored, (current) => ({
      ...current,
      waiting: false,
      items: current.items.map(
        (entry) => entry === item || item.requestId && entry.requestId === item.requestId ? { ...entry, answered: label, answers: picked } : entry
      )
    }));
  } catch (error) {
    host.notify({ kind: "error", message: `Could not answer Hermes: ${describeRequestError(error).message}` });
  }
}
function openInFullChat(stored) {
  const target = studioTarget();
  if (target && typeof host.openSession === "function") {
    void host.openSession(stored, target.profile ? { profile: target.profile } : {}).catch(
      (error) => host.notify({ kind: "error", message: `Could not open the chat: ${describeRequestError(error).message}` })
    );
  }
}

// page/app/paths.js
var baseName = (value) => String(value ?? "").split(/[\\/]/).filter(Boolean).pop() ?? "";
var isAbsolute = (value) => typeof value === "string" && (value.startsWith("/") || /^[a-zA-Z]:[\\/]/.test(value) || value.startsWith("file://"));
var joinPath = (root, relative) => root ? `${root.replace(/[\\/]+$/, "")}/${relative.replace(/^\.?[\\/]+/, "")}` : null;

// page/pages/build/composer/attachment-chip.js
function AttachmentChip({ item, onRemove = null, disabled = false }) {
  const label = item.name || baseName(item.path);
  return jsxs("span", {
    className: item.image ? "cs-b-chip mention pic" : "cs-b-chip mention",
    title: item.path,
    children: [
      item.image ? jsx("img", { alt: "", src: item.image }) : "@",
      label,
      onRemove ? jsx("button", { "aria-label": `Remove ${label}`, className: "cs-b-x", disabled, onClick: () => onRemove(item), type: "button", children: jsx(Codicon, { name: "close", size: 10 }) }) : null
    ]
  });
}

// page/pages/build/assets/cache.js
var AssetGame = createContext(null);
var assetCache = /* @__PURE__ */ new Map();
var PUT_BACK = atom(0);
var ASSET_CACHE_LIMIT = 200;
var ASSET_RETRY_MS = 15e3;
var assetQueue = [];
var assetsLoading = 0;
function pumpAssets() {
  while (assetsLoading < 4 && assetQueue.length) {
    const job = assetQueue.shift();
    assetsLoading += 1;
    job().finally(() => {
      assetsLoading -= 1;
      pumpAssets();
    });
  }
}
function assetEntry(path, version, root) {
  const key = `${path}#${version ?? ""}#${root ?? ""}`;
  let entry = assetCache.get(key);
  if (entry?.done && !entry.value && Date.now() - entry.failedAt > ASSET_RETRY_MS) {
    assetCache.delete(key);
    entry = null;
  }
  if (!entry) {
    entry = { done: false, value: null };
    entry.promise = new Promise((resolve) => {
      assetQueue.push(async () => {
        try {
          const at = typeof version === "string" && version.startsWith("reply:") ? Number(version.slice(6)) || null : null;
          const kept = typeof version === "string" && version.startsWith("kept:") ? version.slice(5) : null;
          const answer = await callStudioOnly(RPC_ASSET, { path, root, ...kept ? { version: kept } : at ? { at } : {} }, 2e4);
          entry.value = answer?.ok && typeof answer.dataUrl === "string" ? answer : null;
          entry.code = entry.value ? null : answer?.code ?? null;
        } catch {
          entry.value = null;
        }
        entry.done = true;
        entry.failedAt = entry.value ? 0 : Date.now();
        resolve(entry.value);
      });
      pumpAssets();
    });
    assetCache.set(key, entry);
    while (assetCache.size > ASSET_CACHE_LIMIT) {
      assetCache.delete(assetCache.keys().next().value);
    }
  }
  return entry;
}
function forgetAsset(...paths) {
  for (const [key, entry] of [...assetCache]) {
    if (paths.some((path) => key.startsWith(`${path}#`) || entry.value?.path === path)) {
      assetCache.delete(key);
    }
  }
  PUT_BACK.set(PUT_BACK.get() + 1);
}
function usePutBack() {
  return useValue(PUT_BACK);
}
function useAsset(path, version) {
  usePutBack();
  const root = useContext(AssetGame);
  const entry = path ? assetEntry(path, version, root) : null;
  const [, rerender] = useState(0);
  useEffect(() => {
    if (!entry || entry.done) {
      return void 0;
    }
    let live = true;
    void entry.promise.then(() => live && rerender((value) => value + 1));
    return () => {
      live = false;
    };
  }, [entry]);
  if (!entry) {
    return { state: "none" };
  }
  return entry.done ? entry.value ? { state: "ok", asset: entry.value } : { state: "none", code: entry.code } : { state: "loading" };
}

// page/pages/build/assets/sprite.js
var SPRITE_SHADES = /* @__PURE__ */ new Map([[14743759, 0], [8831084, 1], [3172432, 2], [464929, 3]]);
var paintedSheets = /* @__PURE__ */ new WeakMap();
function paintSheet(image, colors) {
  const key = colors ? colors.join(",") : "plain";
  let byPalette = paintedSheets.get(image);
  if (!byPalette) {
    byPalette = /* @__PURE__ */ new Map();
    paintedSheets.set(image, byPalette);
  }
  if (byPalette.has(key)) {
    return byPalette.get(key);
  }
  const canvas2 = document.createElement("canvas");
  canvas2.width = image.naturalWidth;
  canvas2.height = image.naturalHeight;
  const context = canvas2.getContext("2d");
  if (!context) {
    return image;
  }
  context.drawImage(image, 0, 0);
  try {
    const data = context.getImageData(0, 0, canvas2.width, canvas2.height);
    const pixels = data.data;
    const rgb = colors?.map((color) => parseInt(String(color).replace("#", ""), 16));
    for (let index = 0; index < pixels.length; index += 4) {
      const value = pixels[index] << 16 | pixels[index + 1] << 8 | pixels[index + 2];
      if (value === 6684416 || pixels[index] < 130 && pixels[index + 1] > 215 && pixels[index + 2] < 80) {
        pixels[index + 3] = 0;
      } else if (rgb && SPRITE_SHADES.has(value)) {
        const to = rgb[SPRITE_SHADES.get(value)];
        pixels[index] = to >> 16 & 255;
        pixels[index + 1] = to >> 8 & 255;
        pixels[index + 2] = to & 255;
      }
    }
    context.putImageData(data, 0, 0);
  } catch {
  }
  byPalette.set(key, canvas2);
  return canvas2;
}
function drawSpriteFrame(context, sheet, tiles, { width, height, left, top, scale, flip = false }) {
  for (const tile of tiles ?? []) {
    const x = Number(tile.x) || 0;
    const y = Number(tile.y) || 0;
    const mirror = Boolean(tile.flipX) !== flip;
    const tileLeft = flip ? width - x - 8 : x;
    const tileTop = height - 16 - y;
    context.save();
    context.translate(left + (tileLeft + (mirror ? 8 : 0)) * scale, top + (tileTop + (tile.flipY ? 16 : 0)) * scale);
    context.scale(mirror ? -1 : 1, tile.flipY ? -1 : 1);
    context.drawImage(sheet, Number(tile.sliceX) || 0, Number(tile.sliceY) || 0, 8, 16, 0, 0, 8 * scale, 16 * scale);
    context.restore();
  }
}
function spriteAnimations(sprite2) {
  const all = sprite2?.animations ?? [];
  const filled = (frames) => frames.some((tiles) => tiles.length);
  return all.map((animation) => {
    if (filled(animation.frames)) {
      return { ...animation, flip: false };
    }
    if (sprite2.flipLeft && /left/i.test(animation.name)) {
      const right = all.find((other) => other.name === animation.name.replace(/left/i, (match) => match === "Left" ? "Right" : "right"));
      if (right && filled(right.frames)) {
        return { ...animation, frames: right.frames, flip: true };
      }
    }
    return null;
  }).filter(Boolean);
}
function spriteFrameMs(animSpeed) {
  const speed = Number(animSpeed);
  return Number.isFinite(speed) && speed >= 0 && speed < 255 ? (speed + 1) * 1e3 / 60 : 250;
}
function canvasImage(canvas2, image) {
  return Object.assign(canvas2, { naturalHeight: image.naturalHeight, naturalWidth: image.naturalWidth });
}

// page/pages/build/assets/images.js
function AssetThumb({ asset, onOpen, size = "sm", fresh = false }) {
  const { state, asset: loaded } = useAsset(asset.path, asset.version);
  if (state === "none") {
    return null;
  }
  if (state === "loading") {
    return jsx("span", { "aria-hidden": true, className: `cs-b-th ${size} loading` });
  }
  return jsx("button", {
    "aria-label": `Look closer at ${loaded.name}`,
    className: `cs-b-th ${size}${fresh ? " fresh" : ""}`,
    onClick: (event) => {
      event.stopPropagation();
      onOpen?.(asset);
    },
    title: `${loaded.name} · ${loaded.width}×${loaded.height}`,
    type: "button",
    children: jsx(SheetFrame, { animate: size === "lg", loaded })
  });
}
function SpriteImage({ loaded, animate = false, className = "cs-b-spr" }) {
  const ref = useRef(null);
  const image = useImage(loaded.dataUrl);
  const sprite2 = loaded.sprite;
  const moving = sprite2.moving?.frames?.length > 1 ? sprite2.moving : null;
  const frames = animate && moving ? moving.frames : null;
  const [frame, setFrame] = useState(0);
  const frameMs = spriteFrameMs(sprite2.animSpeed);
  useEffect(() => {
    if (!frames) {
      return void 0;
    }
    const id = setInterval(() => setFrame((value) => (value + 1) % frames.length), frameMs);
    return () => clearInterval(id);
  }, [frames?.length, frameMs]);
  const tiles = frames ? frames[frame % frames.length] : sprite2.standing?.tiles;
  const flip = frames ? Boolean(moving.flip) : Boolean(sprite2.standing?.flip);
  const width = sprite2.canvasWidth ?? sprite2.frameWidth ?? 16;
  const height = sprite2.canvasHeight ?? sprite2.frameHeight ?? 16;
  useLayoutEffect(() => {
    const canvas2 = ref.current;
    const context = canvas2?.getContext?.("2d");
    if (!context || !image) {
      return;
    }
    const scale = 4;
    canvas2.width = width * scale;
    canvas2.height = height * scale;
    context.imageSmoothingEnabled = false;
    context.clearRect(0, 0, canvas2.width, canvas2.height);
    const sheet = paintSheet(image, sprite2.palette ?? null);
    if (tiles?.length) {
      drawSpriteFrame(context, sheet, tiles, { flip, height, left: 0, scale, top: 0, width });
    } else {
      context.drawImage(sheet, 0, 0, sprite2.frameWidth ?? width, sprite2.frameHeight ?? height, 0, 0, width * scale, height * scale);
    }
  }, [image, tiles, flip, width, height, sprite2.palette?.join(",")]);
  return jsx("canvas", { "aria-hidden": true, className, ref, style: { aspectRatio: `${width} / ${height}` } });
}
function SheetFrame({ loaded, animate = false }) {
  return loaded.sprite ? jsx(SpriteImage, { animate, loaded }) : jsx("img", { alt: "", draggable: false, src: loaded.dataUrl });
}
function AssetImage({ asset, className, fallback = null }) {
  const { state, asset: loaded } = useAsset(asset.path, asset.version);
  if (state !== "ok") {
    return fallback;
  }
  return loaded.sprite ? jsx(SpriteImage, { className: className ? `cs-b-spr ${className}` : "cs-b-spr", loaded }) : jsx("img", { alt: "", className, draggable: false, src: loaded.dataUrl });
}
function LatestAsset({ asset, onOpen }) {
  const { state } = useAsset(asset.path, asset.version);
  if (state === "none") {
    return null;
  }
  return jsxs("div", {
    className: "cs-b-latest",
    children: [
      jsx(AssetThumb, { asset, fresh: true, onOpen, size: "lg" }),
      jsxs("div", {
        className: "cs-col",
        children: [
          jsx("span", { className: "cs-eyebrow", children: "Latest" }),
          jsx("b", { children: baseName(asset.path) }),
          jsx("span", { className: "cs-faint", children: `${asset.kind} · ${asset.step}` }),
          jsx("span", { className: "cs-faint", children: state === "ok" ? "Click it to look closer" : "Loading…" })
        ]
      })
    ]
  });
}
function AssetStrip({ assets, onOpen, size = "sm", max = 6, freshFrom = null }) {
  if (!assets.length) {
    return null;
  }
  const shown = assets.slice(-max);
  return jsxs("span", {
    className: "cs-b-strip",
    children: [
      ...shown.map((asset) => jsx(AssetThumb, { asset, fresh: freshFrom != null && asset.at != null && asset.at >= freshFrom, onOpen, size }, `${asset.path}#${asset.version}`)),
      assets.length > shown.length ? jsx("span", { className: "cs-b-more", children: `+${assets.length - shown.length}` }) : null
    ]
  });
}
function useImage(src) {
  const [image, setImage] = useState(null);
  useEffect(() => {
    if (!src) {
      setImage(null);
      return void 0;
    }
    let live = true;
    const element = document.createElement("img");
    element.onload = () => live && setImage(element);
    element.src = src;
    return () => {
      live = false;
    };
  }, [src]);
  return image;
}
function FrameCanvas({ image, frame, scale, className }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const canvas2 = ref.current;
    if (!canvas2 || !image || !frame?.w || !frame?.h) {
      return;
    }
    const context = canvas2.getContext?.("2d");
    if (!context) {
      return;
    }
    canvas2.width = frame.w * scale;
    canvas2.height = frame.h * scale;
    context.imageSmoothingEnabled = false;
    context.clearRect(0, 0, canvas2.width, canvas2.height);
    context.drawImage(image, frame.x, frame.y, frame.w, frame.h, 0, 0, frame.w * scale, frame.h * scale);
  }, [image, frame?.x, frame?.y, frame?.w, frame?.h, scale]);
  return jsx("canvas", { className, ref });
}
function imagePalette(image, max = 16) {
  try {
    const canvas2 = document.createElement("canvas");
    canvas2.width = Math.min(image.naturalWidth, 512);
    canvas2.height = Math.min(image.naturalHeight, 512);
    const context = canvas2.getContext("2d");
    if (!context) {
      return [];
    }
    context.drawImage(image, 0, 0);
    const { data } = context.getImageData(0, 0, canvas2.width, canvas2.height);
    const counts = /* @__PURE__ */ new Map();
    for (let index = 0; index < data.length; index += 4) {
      if (data[index + 3] < 128) {
        continue;
      }
      const key = `#${[data[index], data[index + 1], data[index + 2]].map((value) => value.toString(16).padStart(2, "0")).join("")}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
      if (counts.size > Math.max(64, max)) {
        break;
      }
    }
    return [...counts].sort((a, b) => b[1] - a[1]).slice(0, max).map(([color]) => color);
  } catch {
    return [];
  }
}

// page/pages/build/composer/mentions.js
var MENTION_AT = /(^|\s)@([^\s@]{0,40})$/;
var later = (fn) => typeof requestAnimationFrame === "function" ? requestAnimationFrame(fn) : fn();
var MENTION_KIND = { cover: "Game cover", sprite: "Sprite", background: "Background", ui: "Interface", image: "Image" };
function MentionPicker({ items, query, index, onPick, onHover }) {
  return jsxs("div", {
    className: "cs-b-mention",
    role: "listbox",
    children: [
      jsxs("div", { className: "cs-b-mention-head", children: [jsx("span", { className: "cs-eyebrow", children: "Assets" }), jsx("span", { className: "cs-faint", children: items === null ? "Loading…" : query ? `matching “${query}”` : `${items.length} in this game` })] }),
      items && items.length ? items.map(
        (item, position) => jsxs(
          "button",
          {
            "aria-selected": position === index,
            className: "cs-b-mention-row",
            onClick: () => onPick(item),
            onMouseDown: (event) => event.preventDefault(),
            onMouseEnter: () => onHover(position),
            role: "option",
            type: "button",
            children: [jsx(AssetTile, { asset: { path: item.path, version: `list:${item.modifiedAt}` } }), jsx("b", { children: item.name }), jsx("span", { className: "cs-faint", children: MENTION_KIND[item.kind] ?? "Image" })]
          },
          item.path
        )
      ) : items ? jsx("p", { className: "cs-small cs-faint", children: query ? "No asset matches that." : `No pictures yet. They show up here as ${AGENT} draws them.` }) : null
    ]
  });
}
function useProjectAssets(gameId, refresh) {
  const [list, setList] = useState(null);
  useEffect(() => {
    if (!gameId) {
      setList(false);
      return void 0;
    }
    let live = true;
    callStudioOnly(RPC_ASSETS, { game: gameId }, 2e4).then((answer) => live && setList(answer?.ok && Array.isArray(answer.assets) ? answer.assets : false)).catch(() => live && setList(false));
    return () => {
      live = false;
    };
  }, [gameId, refresh]);
  return list;
}
function AssetTile({ asset, size = "sm", animate = false }) {
  const { state, asset: loaded } = useAsset(asset.path, asset.version);
  return jsx("span", {
    "aria-hidden": true,
    className: `cs-b-th ${size}${state === "loading" ? " loading" : ""}`,
    children: state === "ok" ? jsx(SheetFrame, { animate, loaded }) : null
  });
}

// page/pages/build/composer/composer.js
function attachToBuild(stored, attachments, text2 = "") {
  const all = BUILD_INJECT.get();
  const current = all[stored];
  BUILD_INJECT.set({ ...all, [stored]: { seq: (current?.seq ?? 0) + 1, text: text2, attach: attachments } });
}
function BuildComposer({ busy, disabled, placeholder, onSend, onStop, stored = null, status = null, picker = null, game = null, fresh = false, ask = null }) {
  const [text2, setText] = useState("");
  const [attachments, setAttachments] = useState([]);
  const [mention, setMention] = useState(null);
  const [pick, setPick] = useState(0);
  const inject = useValue(BUILD_INJECT)[stored ?? ""] ?? null;
  const box = useRef(null);
  const assets = useProjectAssets(mention && game ? game.id : null, mention ? "open" : "closed");
  const query = (mention?.query ?? "").toLowerCase();
  const matches = Array.isArray(assets) ? assets.filter((item) => !query || String(item.name).toLowerCase().includes(query) || String(item.file ?? "").toLowerCase().includes(query)).slice(0, 8) : assets === false ? [] : null;
  useEffect(() => {
    if (inject && !inject.used) {
      BUILD_INJECT.set({ ...BUILD_INJECT.get(), [stored ?? ""]: { ...inject, used: true } });
      if (inject.attach?.length) {
        setAttachments((current) => mergeAttachments(current, inject.attach));
      }
      if (inject.text) {
        setText((current) => current.trim() ? `${current.trimEnd()}
${inject.text}` : inject.text);
      }
      const focus = () => box.current?.focus?.();
      if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(focus);
      } else {
        focus();
      }
    }
  }, [inject?.seq, stored]);
  useLayoutEffect(() => {
    const element = box.current;
    if (element) {
      element.style.height = "auto";
      element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
    }
  }, [text2]);
  const track = (value, caret) => {
    const found = game ? MENTION_AT.exec(value.slice(0, caret ?? value.length)) : null;
    if (found) {
      setMention({ start: (caret ?? value.length) - found[2].length - 1, query: found[2] });
      setPick(0);
    } else {
      setMention(null);
    }
  };
  const choose = (item) => {
    if (!item || !mention || disabled) {
      return;
    }
    const element = box.current;
    const caret = element?.selectionStart ?? text2.length;
    const next = `${text2.slice(0, mention.start)}${text2.slice(caret)}`.replace(/^\s+$/, "");
    setText(next);
    setAttachments((current) => mergeAttachments(current, [{ path: item.path, name: item.name }]));
    setMention(null);
    later(() => {
      element?.focus?.();
      element?.setSelectionRange?.(mention.start, mention.start);
    });
  };
  const openPicker = () => {
    const element = box.current;
    const caret = element?.selectionStart ?? text2.length;
    const before = text2.slice(0, caret);
    const insert = before && !/\s$/.test(before) ? " @" : "@";
    const value = `${before}${insert}${text2.slice(caret)}`;
    setText(value);
    setMention({ start: caret + insert.length - 1, query: "" });
    setPick(0);
    later(() => {
      element?.focus?.();
      element?.setSelectionRange?.(caret + insert.length, caret + insert.length);
    });
  };
  const send = async () => {
    const value = text2.trim();
    if (!value && !attachments.length || disabled) {
      return;
    }
    if (fresh && !await onSend(value, attachments)) {
      return;
    }
    setText("");
    setAttachments([]);
    setMention(null);
    if (!fresh) {
      void onSend(value, attachments);
    }
  };
  if (ask) {
    return jsxs("div", {
      className: "cs-b-comp asking",
      children: [
        status,
        ask,
        busy ? jsx("div", {
          className: "cs-b-comp-row",
          children: [
            jsx("span", { className: "cs-grow" }, "grow"),
            jsx(Tip, {
              label: `Stop ${AGENT}`,
              children: jsxs("button", { "aria-label": "Stop", className: "cs-b-stop", onClick: onStop, type: "button", children: [jsx("i", {}), jsx("span", { className: "cs-sr", children: "Stop" })] })
            }, "stop")
          ]
        }) : null
      ]
    });
  }
  return jsxs("div", {
    className: "cs-b-comp",
    children: [
      status,
      mention && game && !disabled ? jsx(MentionPicker, { index: pick, items: matches, onHover: setPick, onPick: choose, query: mention.query }) : null,
      attachments.length ? jsx("div", {
        className: "cs-b-chips",
        children: attachments.map(
          (item) => jsx(AttachmentChip, { item, disabled, onRemove: (gone) => setAttachments((current) => current.filter((entry) => attachmentKey(entry) !== attachmentKey(gone))) }, attachmentKey(item))
        )
      }) : null,
      jsx("textarea", {
        "aria-label": "Message Hermes",
        disabled,
        onBlur: () => setMention(null),
        onChange: (event) => {
          setText(event.target.value);
          track(event.target.value, event.target.selectionStart);
        },
        onKeyDown: (event) => {
          if (mention && game) {
            const count = matches?.length ?? 0;
            if (event.key === "Escape") {
              event.preventDefault();
              setMention(null);
              return;
            }
            if (count && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
              event.preventDefault();
              setPick((value) => (value + (event.key === "ArrowDown" ? 1 : count - 1)) % count);
              return;
            }
            if (count && (event.key === "Enter" || event.key === "Tab") && !event.shiftKey) {
              event.preventDefault();
              choose(matches[Math.min(pick, count - 1)]);
              return;
            }
          }
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent?.isComposing) {
            event.preventDefault();
            send();
          }
        },
        placeholder,
        ref: box,
        rows: 1,
        value: text2
      }),
      jsxs("div", {
        className: "cs-b-comp-row",
        children: [
          game ? jsx(Tip, {
            label: "Point at a sprite, background or cover",
            children: jsx("span", {
              style: { display: "inline-flex" },
              children: jsxs(Button, { "aria-label": "Mention an asset", disabled, onClick: openPicker, size: "sm", variant: "ghost", children: ["@", jsx("span", { className: "cs-lbl", children: "Asset" })] })
            })
          }) : null,
          picker,
          jsx("span", { className: "cs-grow" }),
          busy ? jsx(Tip, {
            label: `Stop ${AGENT}`,
            children: jsxs("button", { "aria-label": "Stop", className: "cs-b-stop", onClick: onStop, type: "button", children: [jsx("i", {}), jsx("span", { className: "cs-sr", children: "Stop" })] })
          }) : null,
          jsx("button", {
            "aria-label": "Send",
            className: "cs-b-send",
            disabled: disabled || !text2.trim() && !attachments.length,
            onClick: send,
            type: "button",
            children: [jsx(Codicon, { name: "arrow-up", size: 14 }, "icon"), jsx("span", { className: "cs-sr", children: "Send" }, "label")]
          })
        ]
      })
    ]
  });
}

// page/pages/build/composer/model-names.js
var EFFORTS = [
  ["none", "Off", "No extra thinking"],
  ["minimal", "Minimal", "Fastest. Fine for small tweaks"],
  ["low", "Low", "Quick edits: text, colours, timing"],
  ["medium", "Medium", "Most changes"],
  ["high", "High", "New mechanics, tricky bugs"],
  ["xhigh", "X-high", "Big features, whole levels"],
  ["max", "Max", "Slowest, uses the most of your plan"]
];
var effortLabel = (value) => EFFORTS.find(([key]) => key === value)?.[1] ?? (value === "ultra" ? "Ultra" : value ? value : "Default");
function modelName(id) {
  let raw = String(id ?? "").split("/").pop();
  const tags = [];
  raw = raw.replace(/\[(\d+)m\]$/i, (_, size) => {
    tags.push(`${size}M`);
    return "";
  });
  raw = raw.replace(/-(\d+)k$/i, (_, size) => {
    tags.push(`${size}K`);
    return "";
  });
  raw = raw.replace(/-\d{8}$/, "");
  const words = [];
  for (const part of raw.split("-").filter(Boolean)) {
    const last = words[words.length - 1];
    if (/^\d+$/.test(part) && last && /\d$/.test(last)) {
      words[words.length - 1] = `${last}.${part}`;
    } else {
      words.push(part);
    }
  }
  const name = words.map((word) => /^gpt$/i.test(word) ? "GPT" : /^[a-z]/.test(word) ? word[0].toUpperCase() + word.slice(1) : word).join(" ").replace(/^GPT (\d)/, "GPT-$1");
  return { name: name || String(id ?? ""), tags };
}
var providerMark = (name) => (String(name ?? "?").replace(/[^A-Za-z0-9]/g, "")[0] ?? "?").toUpperCase();
function providerMarks(providers) {
  const letters = providers.map((item) => String(item.name ?? item.slug ?? "?").replace(/[^A-Za-z0-9]/g, ""));
  const first = letters.map((word) => (word[0] ?? "?").toUpperCase());
  return new Map(providers.map((item, index) => [
    item.slug,
    first.filter((letter) => letter === first[index]).length > 1 ? first[index] + (letters[index][1] ?? "").toLowerCase() : first[index]
  ]));
}

// page/shared/art/providers/nous.png
var nous_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/nous-dark.png
var nous_dark_default = [
  "data:image/png;base64,",
  "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",
  "RK5CYII="
].join("");

// page/shared/art/providers/fireworks.svg
var fireworks_default = [
  "data:image/svg+xml,",
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">%0A  <rect width="32" he',
  'ight="32" rx="7" fill="%23f9f7f5"/>%0A  <g transform="translate(3.2 3.2) scale(0.301176)">%0A   ',
  ' <path d="M81.7059 54.1818C78.5142 54.6039 55.4095 56.7847 55.4095 56.7847C55.4095 56.7847 73.55',
  "55 41.8118 75.8594 40.0496L72.5652 32.0864L53.2692 51.3455C47.3171 57.2857 49.3284 62.1476 57.73",
  "76 62.1466L85 62.1447L81.7059 54.1818ZM12.4348 32.0864L9.14057 40.0496C11.4445 41.8118 29.5906 5",
  "6.7847 29.5906 56.7847C29.5906 56.7847 6.48583 54.6039 3.29425 54.1818L3.8147e-06 62.1447L27.262",
  "5 62.1466C35.6717 62.1476 37.683 57.2857 31.7308 51.3455L12.4348 32.0864ZM58.7645 22.8534L48.344",
  "5 48.046C45.1308 55.8169 39.8694 55.8169 36.6556 48.046L26.2356 22.8534H34.8532C35.6009 25.6561 ",
  '42.5 48.1476 42.5 48.1476C42.5 48.1476 49.3169 25.9641 50.147 22.8534H58.7645Z" fill="%23280016"',
  "/>%0A  </g>%0A</svg>%0A"
].join("");

// page/shared/art/providers/openrouter.svg
var openrouter_default = [
  "data:image/svg+xml,",
  '<svg width="1024" height="730" viewBox="0 0 1024 730" fill="none" xmlns="http://www.w3.org/2000/',
  'svg">%0A<path d="M795.893 0C915.776 0 1012.95 97.9963 1012.95 218.88C1012.95 339.764 915.776 437',
  ".76 795.893 437.76L1011.2 654.869C1038.55 682.447 1019.18 729.6 980.504 729.6H361.77C161.97 729.",
  "6 0 566.273 0 364.8C0 163.327 161.97 0 361.77 0L795.893 0ZM361.77 145.92C241.89 145.92 144.708 2",
  "43.916 144.708 364.8C144.708 485.684 241.89 583.68 361.77 583.68C481.649 583.68 578.831 485.684 ",
  '578.831 364.8C578.831 243.916 481.649 145.92 361.77 145.92Z" fill="%237624F4"/>%0A</svg>%0A'
].join("");

// page/shared/art/providers/openrouter-dark.svg
var openrouter_dark_default = [
  "data:image/svg+xml,",
  '<svg width="1024" height="730" viewBox="0 0 1024 730" fill="none" xmlns="http://www.w3.org/2000/',
  'svg">%0A<path d="M795.893 0C915.776 0 1012.95 97.9963 1012.95 218.88C1012.95 339.764 915.776 437',
  ".76 795.893 437.76L1011.2 654.869C1038.55 682.447 1019.18 729.6 980.504 729.6H361.77C161.97 729.",
  "6 0 566.273 0 364.8C0 163.327 161.97 0 361.77 0L795.893 0ZM361.77 145.92C241.89 145.92 144.708 2",
  "43.916 144.708 364.8C144.708 485.684 241.89 583.68 361.77 583.68C481.649 583.68 578.831 485.684 ",
  '578.831 364.8C578.831 243.916 481.649 145.92 361.77 145.92Z" fill="%23C8FF00"/>%0A</svg>%0A'
].join("");

// page/shared/art/providers/novita.svg
var novita_default = [
  "data:image/svg+xml,",
  '<svg width="24" height="15" viewBox="0 0 24 15" fill="none" xmlns="http://www.w3.org/2000/svg">%',
  '0A<path d="M24 14.8323V14.8326H14.3246L9.16716 9.67507V14.8326H0V14.8314L9.16716 5.66422V0H9.167',
  '74L24 14.8323Z" fill="black"/>%0A</svg>%0A'
].join("");

// page/shared/art/providers/lmstudio.png
var lmstudio_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/anthropic.svg
var anthropic_default = [
  "data:image/svg+xml,",
  '<svg width="92" height="64" viewBox="0 0 92 64" fill="none" xmlns="http://www.w3.org/2000/svg">%',
  '0A<path d="M66.4915 0H52.5029L78.0115 64H92.0001L66.4915 0Z" fill="%23141413"/>%0A<path d="M26.0',
  "8 0L0.571472 64H14.8343L20.0512 50.56H46.7374L51.9543 64H66.2172L40.7086 0H26.08ZM24.6647 38.674",
  '3L33.3943 16.1829L42.1239 38.6743H24.6647Z" fill="%23141413"/>%0A</svg>%0A'
].join("");

// page/shared/art/providers/anthropic-dark.svg
var anthropic_dark_default = [
  "data:image/svg+xml,",
  '<svg width="92" height="64" viewBox="0 0 92 64" fill="none" xmlns="http://www.w3.org/2000/svg">%',
  '0A<path d="M65.92 0H51.9314L77.44 64H91.4286L65.92 0Z" fill="%23FAF9F5"/>%0A<path d="M25.5086 0L',
  "0 64H14.2629L19.4798 50.56H46.166L51.3829 64H65.6457L40.1371 0H25.5086ZM24.0933 38.6743L32.8229 ",
  '16.1829L41.5525 38.6743H24.0933Z" fill="%23FAF9F5"/>%0A</svg>%0A'
].join("");

// page/shared/art/providers/claude.png
var claude_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/openai.png
var openai_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/openai-dark.png
var openai_dark_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/xai.svg
var xai_default = [
  "data:image/svg+xml,",
  '<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none" xmlns="http://www.w3.org/200',
  '0/svg">%0A<path d="M395.479 633.828L735.91 381.105C752.599 368.715 776.454 373.548 784.406 392.7',
  "92C826.26 494.285 807.561 616.253 724.288 699.996C641.016 783.739 525.151 802.104 419.247 760.27",
  "7L303.556 814.143C469.49 928.202 670.987 899.995 796.901 773.282C896.776 672.843 927.708 535.937",
  " 898.785 412.476L899.047 412.739C857.105 231.37 909.358 158.874 1016.4 10.6326C1018.93 7.11771 1",
  '021.47 3.60279 1024 0L883.144 141.651V141.212L395.392 633.916" fill="%230A0A0A"/>%0A<path d="M32',
  "5.226 695.251C206.128 580.84 226.662 403.776 328.285 301.668C403.431 226.097 526.549 195.254 634",
  ".026 240.596L749.454 186.994C728.657 171.88 702.007 155.623 671.424 144.2C533.19 86.9942 367.693",
  " 115.465 255.323 228.382C147.234 337.081 113.244 504.215 171.613 646.833C215.216 753.423 143.739",
  ' 828.818 71.7385 904.916C46.2237 931.893 20.6216 958.87 0 987.429L325.139 695.339" fill="%230A0A',
  '0A"/>%0A</svg>%0A'
].join("");

// page/shared/art/providers/xai-dark.svg
var xai_dark_default = [
  "data:image/svg+xml,",
  '<svg width="1024" height="1024" viewBox="0 0 1024 1024" fill="none" xmlns="http://www.w3.org/200',
  '0/svg">%0A<path d="M395.479 633.828L735.91 381.105C752.599 368.715 776.454 373.548 784.406 392.7',
  "92C826.26 494.285 807.561 616.253 724.288 699.996C641.016 783.739 525.151 802.104 419.247 760.27",
  "7L303.556 814.143C469.49 928.202 670.987 899.995 796.901 773.282C896.776 672.843 927.708 535.937",
  " 898.785 412.476L899.047 412.739C857.105 231.37 909.358 158.874 1016.4 10.6326C1018.93 7.11771 1",
  '021.47 3.60279 1024 0L883.144 141.651V141.212L395.392 633.916" fill="white"/>%0A<path d="M325.22',
  "6 695.251C206.128 580.84 226.662 403.776 328.285 301.668C403.431 226.097 526.549 195.254 634.026",
  " 240.596L749.454 186.994C728.657 171.88 702.007 155.623 671.424 144.2C533.19 86.9942 367.693 115",
  ".465 255.323 228.382C147.234 337.081 113.244 504.215 171.613 646.833C215.216 753.423 143.739 828",
  '.818 71.7385 904.916C46.2237 931.893 20.6216 958.87 0 987.429L325.139 695.339" fill="white"/>%0A',
  "</svg>%0A"
].join("");

// page/shared/art/providers/qwen.svg
var qwen_default = [
  "data:image/svg+xml,",
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="17.5 27.7 135.6 135.6">%0A  <path fill="%23082D',
  'FF" d="M130.06,43.66h-33.37c0-1.42-.37-2.84-1.1-4.11l-4.47-7.74c-1.47-2.54-4.18-4.11-7.12-4.11h-',
  "8.93c-2.94,0-5.65,1.57-7.12,4.11l-13.68,23.69c-1.47,2.54-1.47,5.67,0,8.22l4.47,7.74c1.47,2.54,4.",
  "18,4.11,7.12,4.11h64.19c2.94,0,5.65-1.57,7.12-4.11l4.47-7.74c1.47-2.54,1.47-5.67,0-8.22l-4.47-7.",
  '74c-1.47-2.54-4.18-4.11-7.12-4.11Z" />%0A  <path fill="%23082DFF" d="M19.75,83.66l16.68,28.9c-1.',
  "23.71-2.27,1.74-3.01,3.01l-4.47,7.74c-1.47,2.54-1.47,5.67,0,8.22l4.47,7.74c1.47,2.54,4.18,4.11,7",
  ".12,4.11h27.35c2.94,0,5.65-1.57,7.12-4.11l4.47-7.74c1.47-2.54,1.47-5.67,0-8.22l-32.1-55.59c-1.47",
  "-2.54-4.18-4.11-7.12-4.11h-8.93c-2.94,0-5.65,1.57-7.12,4.11l-4.47,7.74c-1.47,2.54-1.47,5.67,0,8.",
  '22Z" />%0A  <path fill="%23082DFF" d="M109.55,159.19l16.68-28.9c1.23.71,2.64,1.1,4.11,1.1h8.93c2',
  ".94,0,5.65-1.57,7.12-4.11l4.47-7.74c1.47-2.54,1.47-5.67,0-8.22l-13.68-23.69c-1.47-2.54-4.18-4.11",
  "-7.12-4.11h-8.93c-2.94,0-5.65,1.57-7.12,4.11l-32.1,55.59c-1.47,2.54-1.47,5.67,0,8.22l4.47,7.74c1",
  '.47,2.54,4.18,4.11,7.12,4.11h8.93c2.94,0,5.65-1.57,7.12-4.11Z" />%0A</svg>%0A'
].join("");

// page/shared/art/providers/alibabacloud.png
var alibabacloud_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABU0lEQVR42u2XMW6DMBSGP1DkNb1BjpAr0KkeLCU5QejKkt6g",
  "OUJygpITJJEY2MoVeoP0Bu3KQpdHh8rBJgLRqvwTwvb7f377vWeChyfDkAgZGKOAUcCkfsjLbAlsgbljzb1WprAN5GUWAa+O",
  "9W/AVitz+nYgL7MUOHqQ76+RA8jY3hFjDhyFk6BKiIEXx6JP4KSViX1sleBLYOqY+hhUCRdgZhl8B05AUdvVFrKtkYixcgRV",
  "QmVTppVJuzxseZlZnbZlwblrcjkfKXD2ERD3mHWxU4BW5qMvdlvsSYs9jORA+aBoStebBAj5c4v5xd8qxR5Ifb8KuHQuQCtz",
  "aRP45m6Yl9ldX3bbYodXrO4LqY+AhZRNeijFi5/vf0UzGrQdh9IkDo6JU2Cdl9nOg3wHrD3ID1qZNJQUi4GVXJeasJGS3FSu",
  "Nx5XslXtZjD+GY0C/r2AL3Dbem2/HdotAAAAAElFTkSuQmCC"
].join("");

// page/shared/art/providers/xiaomimimo.png
var xiaomimimo_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAAGa0lEQVR42u2YW0hUXRvH/2vtPTOKhxoNOqAdpDxkMXWRKRaG",
  "Qd11pNCLRMmBssI0IngLQiksESOqq0KoICw6EUkYk5CR4qECKyzsQi9KxXJm0HLj7L3/3823NzOvWn0fvbxdtGDBXouHZ//2",
  "s571f9baAsAYgFj8Hu2rxG/W/gD9AfrlQEKI6Q2lhKIov/TlqqpOed8UIJKQUkaAAIBpmjAM45cC6boOkjMDWREwTRNSSggh",
  "YJomhBBYu3YtvF4vhBBQVRWKokBVVRtYSglVVSPmLBtFUexujV0uF8rLy7FkyZKIlZHWQAiB6Oho3Lt3D7t27YJpmiCJmpoa",
  "nDhxApmZmSgoKLC/zDAM6LpuA5umCV3XI+YsG8Mw7G6NY2JiUFRUhMWLF09JlTEAlFISAAsLC2kYBlNTU7lnzx6GQiGmp6fT",
  "4/GwtLSULpeLJ0+e5JMnT9jY2MjU1FQCYFZWFu/cucP79+8zNzeXAFhUVMRjx47x8ePHLCkpYVlZGZubm7l9+3YCYEVFBZOT",
  "kwmAQggCGLeBwqGOHj3K/v5+DgwMcNOmTQTAyspK9vb2Mj4+npcuXeKWLVt4+/Zt+nw+pqSk0O/3s66ujjU1NQwGg0xLS+Ob",
  "N2/Y1dXF6upqkuStW7d47tw5TkxMMCUlhV++fLH9K4oyPZAQgrNmzSJJ9vT02Mb79+/ny5cvCYBer5d3795lZ2cnu7q6WFNT",
  "w6dPn9Ly09zczLNnz7KlpYXFxcUEwKGhIebl5REAR0dHuW7dOvb29jI/Pz8CSIZvd5IgCZ/Ph6tXr0LTNFy+fBmGYUBRFAQC",
  "AZSUlKC+vh4XLlyAz+eDqqrQdR0Oh8POAafTaeeL0+mEoiiYmJhAdHQ0nE4nNE2bsrtsKQhPaiklbty4AbfbjeLiYqSkpKCv",
  "rw/t7e0IhUJwu90QQiAUCiEjIwNbt27F3Llz0dDQAK/XiytXrmBychIrV67E3r17sWPHDjgcDhiGgcTERDgcDpimiYSEBDgc",
  "DsyePTviQwBAAfCXEMJJEomJiUhNTUV5eTmCwSD8fj+ePXuG5ORkdHd3o7+/Hw0NDdB1HdnZ2bh58yZaWlrg8/nQ1NSE9evX",
  "IyoqCvv27cO7d+8wOTmJ9vZ2DA8PY3x8HG1tbfD7/RgbG8Pz58/x6dMndHR0IBAIWDwhMdN5yIqaaZo/FDhruX809zPnIfXv",
  "ThRFgWmatg5ZYknS1hZL8i1YwzAgpYxQddM0oSgKSMI0TaiqCsMwQNJ+VhTFnrMZwiM0U1SklNNGYCY7y9ZSewvqf46Q5UxK",
  "aTsIf56u5n3PLnz8d9iZmp3UAJCYmIg5c+YgGAxG1LKFCxfCMAzEx8cjJiYGiqJg/vz5CAQC9lKZpomkpCQoioLJyUlIKeHx",
  "eJCbmwuXy4XBwcGfiVAIAMYshc7Pz6emaczJybFFbs2aNfT7/dy4cSOrqqp4/vx5pqWlUdM0btiwwbbzeDwcHR1laWkpAXD5",
  "8uUcGBhgT08PR0ZGeO3aNTqdTgohrDIxXR+fUssqKipIkqtWreLq1asZDAap6zo3b97M06dPs7GxkQBYVlZGkszOzmZmZiY/",
  "f/5MXddZWFjI3bt30+v1ct68eQTAZcuWcXBwkNXV1eGqPC2QDF//vLw8hEIhVFZWorOzEx0dHaiqqsKLFy8QFxcH0zQRCASQ",
  "kZEBl8uFgwcPorW1Fa9evcKZM2fQ2toKt9uNw4cPIzY2FkNDQ3C5XOjr68OhQ4dQUFDwQylRw0u/x+PBgQMHkJaWZqtqfX09",
  "ioqK7CTWNA1Lly7FkSNHkJSUBCEEEhISUFdXh23bttk79ePHjxEHPIfDgaioqAgJmS7BI3aZpml2otbW1k7ZHZajUCgEv98P",
  "KSUuXrwYccT99u0bmpqacOrUKTx69AhjY2MQQiAuLg7Xr1+fsju/e6ZWFAXR0dEwTRNOpxOqqtrP4SdFIQSioqJs8XO5XLb4",
  "ud1u1NbWYnBwEG/fvsXDhw/x+vVrdHd34/jx49+FsYVRCBFLEgsWLMCiRYvQ3t5uLyNJ5OTk4MOHD4iPj4eqqhgZGUF6ejra",
  "2toiykRWVhaGh4cxMDAAANi5cydWrFiB9+/f48GDB5iYmPiRDn0V/8Td/v+sY9PXMinllNuFVd/CozadXXi+Wb4suJ+9sYg/",
  "fz/+3O1/AdDvBCVVANp/FZv/MowAoP0HbVq+SmcMIWQAAAAASUVORK5CYII="
].join("");

// page/shared/art/providers/tencentcloud.png
var tencentcloud_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAADN0lEQVR42u3XW4hWVRgG4GfN5DQahYqVWjMTzaa8qCAy/AsL",
  "oahIw6Kxk246QdFpgm4SKogwCLv7KaIDFhhZTAcyootqOkK7IJq6qtzaWFGIhzCkccyZ3YXrz800/7gnBW9m3e13fet73/Ud",
  "1lo7FEXhaI4WR3lMCQiTsu4tpuMmLMMinBR9bMeX2IgN6uGvIy+gt1iFJzH3EJbb8aB6ePHICOgtpuFZ3DrO7DBGMX2cuXW4",
  "Uz3sP9waeG4M+Rbcgw710K4eZqAD9+Knkt1tce1hRKC3uBGvlJAXcJ962NvEvh3P4JYSmqqHlycvoLdowyDmReR59XBHhZSF",
  "GP6GiG3oUg/Dk03BdSXyX3B/pWKthwJ3R/E/4HssbGZ+zASulpbdqoehyh1TD0N6i9OjmEnWQJafgxW2HH8ZjrO3dZ+5Q++Z",
  "Pfy0WvJbJQHri/lYhQsxC7vxLfqk4bvxBWT5rFhA1zdx+zeewGNqyf4mxNPwCFZjWhM/r+EuafjjoIAsn4ePcUaF/X2EFWrJ",
  "zjHkM/AmLq/g40cskYbfgywP+BSL42QRW+9V/IoFsaguKjnIcYVasjmSn4h3cX7J5jM8FclOjZFdWYr657g4yPKr8VYER3Ct",
  "WvL2mLoIeABrS50zoJacG8n7cVZpxWqslY4pwvXFcryB1ohcE2T5RlwVgcfVkoebBi7Ll2MDdmGJTd17Y0qSaDGK26XhpQkK",
  "dA0eil/vBFm+E7Mj0KWW/Dxh9rL8POy2qXsE76O7VKQrpaHvEB3Sia3xa1eQ5Y0w7VNLjq3YZkks2lNK5D3SsLHi+mG0NU7C",
  "PRFuk+UzKyw+G5+UyIdw5STIZzbIsacFA6XpGyqQ92N+wwGWScMHk3jWlDkGWuLB0BhrZHnShHxRbK05EfkTl0pDf2XqA6lb",
  "Uz6UgixvjxdGVwR34FG8rpZsiwsXxz4/oWSzVBq+qkh8Mnqi38YGtmJB4yS8AB+O87IZMtK62WBnt9GW8ty+mPsqo21cv1wi",
  "DV+U74KF6MNp/2IjrZts7egw0tp+BB/Cg7Fjvv7vbXggHTejx0jrHIOdZ47Z+f8dO/BNPHHXSQ8+TsLUr9mUgKMt4B+B4voP",
  "aiZMiQAAAABJRU5ErkJggg=="
].join("");

// page/shared/art/providers/nvidia.png
var nvidia_default = [
  "data:image/png;base64,",
  "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",
  "3ta/wiv8Gf4LLGRRbhEQvgEAAAAASUVORK5CYII="
].join("");

// page/shared/art/providers/huggingface.png
var huggingface_default = [
  "data:image/png;base64,",
  "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",
  "/+/Fffmk5b8qjcJ3D2n9EAAAAABJRU5ErkJggg=="
].join("");

// page/shared/art/providers/gemini.png
var gemini_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAAIZ0lEQVR42s2YbaxcRRnHf8/MnHN2977f2t6+oSUEsSBF0ooY",
  "EtEPGKN8MIa9CA0QE1JMAPElaKIJy2pCIgbfICSCUYEophtionwo+NI0JobEVGiiJsRiI5S2t9JyX/bt7JmZxw+7t7297W2L",
  "kOhsJmdPzjlzfvPMM/P/z4H/syLnfacu3qvv0FtF/7tHd1YtWjPvdCSqO9W+tQjVaoZ6PZ44//WOCiFPYRNjjMPsJsZPOYIr",
  "q8LEWUF8B3GHae19TIrzB9KaQeqRWs3wkQM3EuUzppDLTSiPJX5CsnyKUmcDpc5Gsu5anB/DxXI0MQn9Ns1Kw64IIpaj6vnp",
  "i9+Qh1EV5OTwuRVhnr1xM9k/HydJrhEREIMUKSZmWFPByjBWRrC2go1lDBlizi/FxLDBDnPlBx5QeUnkh1TV0pAAy7tSG8Ds",
  "uu19lNLfUU6uod0LNItAL0QpVKVApSdqCqNSoBRR8UHVe9UiqnrOWUOBDz0iyleurWmpD6NyaoQUgbpyWbUM/ilK2XqaeYGY",
  "pH/dgAiIHfTDIGIQLCKDa+c5aQUsHoA18zAJHEJPG+yqQVDGspsZzrbR7HlEkqUJcOIoOjjXQWK8tRmsiheLAIemJjm2NJvN",
  "SehGHKw1n0WjIsu6K6BEVAJRPNEUg+pBIhAHjZ4VLqoSbEqCASPct+seyampWVyX3InOC8ru28YhvJ88CopZfIGKILoIUxBN",
  "TjQdgun0/0uBGAvRIJgTDS4DUZtiEYieP0vkm3/5ujw7mGVxpVlWAiaJemp7qqgoanwfwLbxrol1TWwYwsQMUYMRAewACkCi",
  "KtE4nLUQevxV4TsvHeBpHpOCmpqlMKcDLfQ8qe1gSQnLVitVlEg0Od62sck8NlSwMcOo6/MHxcQUolGwwVjnrMP4bnwlFuYh",
  "2+OJvXVpA1Sraht1CcvH9FSgwyNzvKf1D5zbSvARsEvXNCQQTUFwLYqYYtIUi8WJorZAimEllKKzFWvdqCuanYO+Z36geefH",
  "++oTs4uS0ZiW0GicDnMSSFB0p0WmC3Zt30Vit9HxenIOLg5hRE1B1A6a9Ke7c4Es6WjZz8YRO2KH0nHbWzBHevnYo2uyw489",
  "+8UPz4hArbbb1esfDY3pM4OcLh395ILf3LqeNO4jMasoYlgaJRCsGhIShjRlTMs6SSmuc2W7YWQY23JvhO7Y46Om8+iDn9xx",
  "sP+M7c9AFN2J5W+o1InnZz8WZeO57TeQuQY+go++n6kiBshEGBHR1c7EC1NjL51MmSx0LovpT2xXH/7C1Y8cANj/3JY1E/HA",
  "RaNJr6TBtBPj9st1C8f6r8GsBHX60rqzapluBHbdtJ00eYSSG6fjMUXUxEQdN8imYZEtE8KFsehMWXlyVbDf+/Tmn78M8MIz",
  "H7ti49Chu4fd7HUp3XeXSwWhG8DzquTuOTNnH5Rb5/drFSsNwltT++dvuhiT3CvoJ1IrF0xksMkWXJr51y7J4vPrjH341kt2",
  "7gN4/Omvbl7jjt8zlRy8ZcPI8Urij2HjgmamExO8KYkK0cFRN9+bKd2V3XvkqTNFamXxWYwUwO6b3lUudNP61IxsTqS51bnX",
  "6h964gjAjp/9/qLRonn3anfocxtH/j1a8f9ilTsUVqVHZdQeM0O2SUqO8zFK20TXTp05XsHPuBuSbx94ZjnU2dWwVjNc9nc5",
  "AbakXP/9V97tQ3rnkGvdPjmUT1b8QSbMobA2O2jWZq/KmvR1ViVHGDVvUqFFWgRMR+DNJCRzFRuPZsfssfIVPLnvEH1pjmf2",
  "Q0tLvR5BZeuP9iZ7P7+tQOGDDx5Ya/3UHce68c5ypbw6FMfpzs6GMbfGhBRrJeKkRyo5GV1S0yMlYHs9JAeTJ9a3jE9iaVWM",
  "7LBQ050YplcyaMt8b2Nawt47KLZ+TcfCeLg9BLnHlMwFoYCFVu4Tyaw341a8RVASCkqmQ0VaDGmTiu1QigVJF2gBrQTpJELL",
  "qHbd9Qp1mSZoP0rqzgbSmJaw8UtaXr2a2yJ82WX2YvXQ6+JFgzXiXIEZiKrigmfOd6mYBUaZpRVn6Zomhc8JbYgLEdNMoJkY",
  "2la0Zy6a+/jV4zz/wvGVLWxNTWNaQrWqdv82biZwr824XAP4DkH6tsSpWCKKKHgSerFEhwodRmgzRiuO0/ZjdHUO3+sQW4rO",
  "B5g30HbQtVDYZCzR8spaNrACW+v6qf0l7jOOqzDgu30QEezpWzXTNzk4ipiRU6bLEN0wTK7DeD+Mz1vEZkQXemhToG2hZ8FL",
  "i146d0agalVtQyRc+S29hQpPmghhBZAz7SFVDRFDCI4QUjwlgq8QeiVip4y2CmgKtBW6ElFnRHWf7NnTXGp2BvKp0mhIuPoh",
  "LaulRkBDDz8AMefjkhVBo0GDRQsH3QRtJehCBgtpv7YTyB3ijRKtoPo0ANdea2VgNZc6RkJgTOCC6OFcUTkNSRWjYAIYDyYX",
  "bNdgOw5pOeg6yC1aUDixic/9XhfdL7SfJmFZhAY+c4x5hcPiUIUw8O/n+EWVGNTEoDYUmvhCk9xr2vXqOlFtO6rtEiUn0JOQ",
  "SZJEH18PxO2yZ0+X++8XWWLE+0AiWq2q3XuHtIHv2gxjHU4ccrZqHGKtFWcTSYyRDJFyjDIcvAwXXkaKIEOFylAQM4GzQzax",
  "0cc/FsJ1pd1/ellrNSNLt+unSodKf+hEr3xA7xLL7RpYSzxzFgkRiYohkkRPJbbtaDEvq7tvsD4/zAWtg2zsvM66zoxO9o6/",
  "OR66LzrNf5X99g+/7Esldvr81F4FRKmq3XIVpaR57k3XOiBvHpEpZphihrXMsGVmhimOMDUzw4J9w7931658if80i9r1tj6V",
  "vJ2iYLRatXoOQT/LRZW3CXBK8/KOfOn6H5T/AFHnWOqHp7fcAAAAAElFTkSuQmCC"
].join("");

// page/shared/art/providers/vertexai.png
var vertexai_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAAFDElEQVR42u2YW2yURRTHf2e++XapUJVL0QeCdzDBSxBKJEpo",
  "2bZEEhMvocbLg6gxgg9egICXQAsoJCKJxmui6IvWtN4SE6Fla31QiriggRAFMRA0GjZQgS2wu9/sd3xgG6DsLqVrNFHPy87O",
  "/M+Zf86cy8wH/8u/TX6/ZWLVbzWTRpVrZ9rzqaqapiNntSOlFpM1E4Zhz9uniqqXGXtxx7ajgyFT05QcZvzz9gFqI0PHdiyU",
  "onZMKUOHKzIBSlKUZMo75gbrnYoRVQGQBJJeFFeWqxVET/Gki3v3BnF7xG3w7immUxCjKqjK2fYzAzhTFdBTpuqASoT6Empn",
  "YkQUES2LkIIkY9WvJmPVr+hZ4q20m1VmrEgtjz2XWlYWoZ6G6jHAPODR/HhQMrP5yHBEnlHk2ZtXHho+aELZrOcVGveXCa2z",
  "IxNaZ0eKrbc3XdCjcJ/CfV89deEfpfa05daXqa2zK4Iw3AlozTv3j/9yzrvpQriuZ4a9PxB7plxC2Yq0AD4QyQw9KuUWxrIJ",
  "bbn1s2PHjbnquDFXdTe2HS9WGH2VncY3Oxte0KF/6ZGpyK8oKPJL39yOxrbefunZiwBCCoBo5SjC3HCArEtXAUf/MkLWuGYX",
  "2nXWuM19c5M+uHMugm6566M3ALwwtzzw/N3WuRYAk0MHWjRKErKBd1C93GFAPVIHAKQWB25jH2bKx7ePDLO8hsLU1tmt3Y1t",
  "PTKTJAQvFbIZcaWplYyhqq+/TilmvGKuHv3ljl4AbWd0ttN/XNsZDbD5jk8OispCFV3Q3djWUwhjLDrgEzgb4KLOb/af1qc8",
  "+7SoPuaMvQTcEwDf3v3h6lIY41TDvF9CK1IWof0zpjxiJNSqzsSbAGqkRUK9Qo209GGu/PyWKMDuWesyxTB9Erq0DPo+9Gts",
  "ysgIegAgau3IC9q7ewoWRg13oeiw45XjChXGhqbUaOfLfgDjeZfEF1fsG5CHVBHXaZ9SlZRvg9eldvPB/bEpi5BQC5EB0Fxw",
  "EeKNAUgPOXQxsLc/pqOpMjljRe9CDDa+uGKfdmED588V0UobcytFTsbYaR5KfxEd74W5H/N/E6GaB6L12e2nxccG7x4VeV1E",
  "H7GxXMuNLbdd6sTbA2A1d9mmuz/d2x9zqn5mQ+RaI+FaYDJALvTGDWnI/FQwy6K1mV3AGiAEJhsJE0HcLtEE/smaJ+OA8/O/",
  "Ra4tZ2I0gR/E7RIjYSJPJgTWROszu4umvQjq17n5CNMQfgQiQLM7bLdm4341gP3DLddQqu1Bt6JoHPTDZOKR69whuwloBiKC",
  "/gzU+XVu/qnHVbQO+TG30Ro3EaUZCFCuEXRjELerqMKPNAQJaSRXNFMayUUaggSXY4JOu8gQfgvcADjgZS+Xu96vc13nVBil",
  "lrRf75rUSDXwXT4BFuWctz3osNNPBvXQnnxvOpofn7gFbPBvdIfs9yir8p7eoSI3+XXuMZlZvJcNqMNoAt8dtk+iLMsbDwV9",
  "y/Ny86WW3ur37rxcfKObG9v26EYq3DG7FFgAeHmvvGizbqnMIlPWu6y/ZNoj1xgvXAtUn1DWPSrykB9zXwAEHfYmDG8D4/Mq",
  "21RkTiQWbB3oHud8cdcurHN2AcJSYAiggr6Wz655eZtplGZr3eoTzXjgMuiXRLoreqUX5t5Cmd5vqTtU82C0PvvD3/7uV0Wy",
  "cf/hIG5TQdweCzrtIm3F+8c/SOh6Ruh6Rvz/aeY/KX8Cl5Q2QEQE2CQAAAAASUVORK5CYII="
].join("");

// page/shared/art/providers/deepseek.png
var deepseek_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAbCAYAAAAULC3gAAAEnUlEQVR42q2XW2xUVRSGv393SlsqCiRUixE0kipIghHQkKjx",
  "QQOUTuuDiFyUWFOUThusSghqsL6UmFQxTDuYisYYEUy90JlixVYRNSoPXmPUlEQwEJBW641LWzpn+TBTHKYz7dSyns45a2Xt",
  "f6/9r3+vI8Zo/nU2zXkUWZRoTjcfNzcrmugvqbL75XmzIqGs9Znk8w3nvK3WfOO7mO3EVCfygT4zjjrI9uTdiWkZA3aVBxh0",
  "MElfAX8l5pDZg0hFC2ts894t6hkJkFLuutJuluwRg0VAXgYbO51rurQ5pJNDcgW8k0C+oNOkDZEGWkCWHLfkIZvtsmzTeRVa",
  "WmkX9cprAFttozu5caeNAiAJkAlsHLEKFmH2TknAXm5t5IHaWnNfdnO9wWWCeWCPAWfOVai03CZYnn0E3PA/6fQLnlZHtml/",
  "UoUOAjOSDqYC7FHg2qQc7W5wJ5Znu8YABmA6ztpLKu2+pCq9NTTUXkwBBqQ3HEBpFSuBYsZu2ZK94g/YhnNr+NwW4AQjs/n7",
  "3Gxel3+NjSfbOoHLuYAm9Hi4UZsHmwRZCzA5TWd1elkqad2qg04+Fl1oMDESW50/YJvAFAnpUzndniLsCFgdZzSvdasOxnTI",
  "eWWYAA7Hztv1mLxCmebHOZU9BlhP+wN2nWQ15p2/aed0R0tQHUOE0UzzYgKmZ8Mh1zBUBrgHbG0GhD8FtgNTAaIUiDeM7jaz",
  "JcDvSSVMySsHFMQVY8j5Nod0MtKo7ZFGNxfTCuDXYQAdRm53boGWOaeFSZqUD0xLePfGeRxKB+jieMyM4bYfCWlnVrZmmtGR",
  "JuRqzPP3dnt1LUF1CFUMk64zlaoDOEFXvLQLRmLE7uf159QBFUv2agp3LmixxBSAcKN2Cd5MySzZJ+nWcAbH4s8zStfaNSOB",
  "amrS2ZwTrhx4L4X7SjPdsnSNXRKjSazth7a5ezctILAD/yH37s2kd5qbFR1wWgb8kMJ9VW+2feMPRLdK1pTC/9uAaEtfIXPt",
  "CdK9trTcJmQCqi2ov+VpOdCXqlKgajPmpjiwprag+tIC6h/PhwktOdnL8zZmqjLhbfoO9NQohKnH81z9cAHu/XqdMrNgguSv",
  "91fa/ExXyO2iHtiX0XViqtizTX8MCwjgbI4Lcq7b8CHbXVZpVyQHlwXsptJA9LWSarsxkU+SVgHdI6AJhUN6eyTQDmDvFvXI",
  "U3lsjgJgqifbVxywosTgqKPX0Ep59oW/Kvrc4mrLAQg36Jih5UBvmnXaC/vdw5lU0SXwYQ+yZxKFLgv73F9lKwY/tAb1bVwY",
  "hanG59mBsmqbBdDaqA/k6S6gPwWRDx3PozCzKSHJSgLROqGN5187fOakltiQbzXA9AT3GUNP5k2hoblW/SUBKxa2A5iYlDoq",
  "CEdNT+wJ6cfRDvmVyOozHPAHMx03s/0OjhgqAgqBOUBO4h2GaVUkpJ2jAgSwpNJmOtlLwAJGZ12SKsINCpeW24RoDkU+H5MG",
  "oM+Dn9qC6h71b1CilQbsVpOtw1gYv7XT2c+GXjCP7SO19pgAJf405p9gTpZjjhnZiIkY/8hxVB5ft4R05EJMmv8Cvz3NNPhm",
  "uNMAAAAASUVORK5CYII="
].join("");

// page/shared/art/providers/zai.png
var zai_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAADpUlEQVR42s2YT0jqWRTHv/enTqGBv0W6+Jn9mQjCR4s2LVwF",
  "tYz5s5DqiQlBUNQsok0pFYRkiwIXMTEIEfxKKadZDNg+qEUt2szwKzKSMA17UhI9q9Gfd1ZP3jyeV9Mx31ne+73nfLjn3nMv",
  "B/jGjHw5QCltTSaT1lQqZeI4TlWJoNlsNq1WqyWe532EkIuvAlFKFbe3t79Go9EfRVHUx2IxUsmdEASB2my2Dw0NDX/qdLpR",
  "Qoj8H6B4PP7b9va21ev1at4yRSMjIx8HBgb8er1+BAC4T2mKRqM/vTUMAHi9Xk0kEvmBUtqWA0omk+9FUdRV6yCLoqi7u7uz",
  "5oBSqZQpEomQagFdXV2Rp6end5+nTJXJZKp21WVZBqVUBQBKltBsNqO9vb0opwcHB7i4uMDg4CBqamry6tLpNHw+H2RZ/uo8",
  "E6inpwcWi6UgzOXlJba2tmC32zE5OcnUejyevDC5lJVjz8/PmJmZQUtLCyYmJpjak5MTbGxsMDXMHdrd3cXR0VHeeUopJElC",
  "IpGAz+eDSpW/sD8+PsLhcCCbzZYOJEkSJEkquEsOhwNtbW1MjcvlQiwWK+ir7JSZzWb09/czNcFgEHt7e0X5KwuI53m4XC4Q",
  "kr+ExeNxuN3uon2WBbSwsID6+nrWqw6n04mHh4fKA1ksFnR3dzM16+vrOD4+fpXfkoCMRiOmpqaYmtPTU6ytrb3a96uBFAoF",
  "lpaWoFarmbVpenoa6XS68kDj4+Po6OhgapaXlxEOh0s6Cq8C6uzsxPDwMFNzeHiIQCBQ8kUpGqiurg5utxscl3/J/f09Zmdn",
  "QSmtPJDD4YAgCMxnZG5uDolEoqxCWxRQb28v+vr6mJqdnR3s7++X/TdSFhLo9XrMz88zNeFwGCsrKzAYDDCZTMzKfX19zXwf",
  "mUAcx2FxcRFarTavJpPJwOl0oqmpCaIoora2lgkfCARKB7Lb7ejq6mIGWF1dxfn5Ofx+f0GYslKmUCiQyWTg8XjyLn55eYHf",
  "70drayuCwWBRAc/OzkoDkmUZoigWFSQUCiEUCv0vH34OAAghaaVSiWqZQqEAISSdA1Kr1VJjY2O2WkDNzc1Uo9H8lQPieX7L",
  "ZrMlqgU0NDT0ged53+cpuxQE4Y+xsbHHt4YZHR39KAjC7qe2zJftmNWbm5ufNzc3dZFIhKskiNFozFqt1oTBYPhdp9P9QgjJ",
  "5mtYfZ9MJt+nUql3HMd9V6GG1T8ajeZvrVbrI4SE8S3bv2DFadQ9pNEdAAAAAElFTkSuQmCC"
].join("");

// page/shared/art/providers/kimi.png
var kimi_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACMAAAAkCAYAAAAD3IPhAAAB8UlEQVR42tXXO0gcQRjA8f+sogGFiEFyRLBKlUrEaKz0yoQc",
  "VhohQvARsbILWuQIhGCrportFYEgWORRWAgiRjBNBAshRTrBbS6KRkRxx2aEQ3d3dm/25cI2u/P47cx8O99Ahi6RRqf3PsjW",
  "GhizJDkpWbeLfEEImTgmNysfyQt+Ak0Vjz/bRfEyccz99/IrgsKNKZL0WSksjE63x1LQbqWwZO64Gh3+WBkJpLV9yUot8BGo",
  "rxwxYBo4DNlgP/DM491v4JNqfQPBAzVlZSFZbbzLvD0lnKvOr98PQ0JeAOcebR0DfUEbMsUM+kD+A/kwX2WC0Y1IPuziqRYz",
  "FNXUmGJ0kN5qwyosZgS48Kh3CPSYxHgYzKgP5AB4YvrDCYrRQbqj+PsFwYz5QP4BXVH9inWY8aQgOsxrDeRx1JuUF2YCcDze",
  "l8E9FYgD880HIoG5uLZvWeVdAhqygpHALtCeFYwETlX+YyWFWfOJqsp11hI35p0qlwf2NGVt4GlcmOK1si3AD00dB1gA6qLE",
  "zPicQt8AZxrUFtARBeZtgHrdwN8Ao7QMDAPNcaedTcBSwCBY1DVmGo4HwADwCjgx7SuqQ1xJ7VU7Jo1EeaLcVZneolorqWJQ",
  "UzWp8uDvYVG1wKbL8fbIEPULKABtwHOV92xzm65LEs9vRwINrIEAAAAASUVORK5CYII="
].join("");

// page/shared/art/providers/kimi-dark.png
var kimi_dark_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACMAAAAkCAYAAAAD3IPhAAACCElEQVR42tXXO2gUQRjA8f93BhUUDEowKFhZWQVJTFKZKxWD",
  "lQ9QEI2KlZ3EwiCI2PqoTJtCEMHCR2EhBFFBGwWLgIWd4DUxQQ2i5P42VwS9vdu93Xs45e7MN7+dmW9mB3qoRDc63Xbdnetg",
  "qiSDyovKDPeJsOOYwRvucZVXQP+ax/cqM3Gi45jt13xEMPnPFMlEqQsLY7jeY4OhUheWzMa6xiofSz2SSPNf5FmfegfYsHbE",
  "gOmIWM4STT0MHEx4/S4i7taivyTYUZuyxZDnm7dwq3Ixqli/7M4IOab+Toj1XZ1IGygXRj3aAPJDLWf5qpYxKUakTMYhbgmj",
  "Hi9kavJiUkD2t5RTWTHqaXU1od2yOt5ygmfBqGcaQJbUsVy7TVpMCsho7q0vDUadagD5qu4rZB9uhlHPdgTSDKOeawIZKfSE",
  "SsKo59VqwvtFdbjw4zKhs8cNIKo323J223qZUzf1CkZ1QR3qFYzqT3VaLXUKM98gq9aus4F2Y67W6pXVz03qVtQD7cLM/FV3",
  "QH3apE1Vva2uLxJzOaF+qJfUX01Qb9S9RWCupGg3qn5KMUoP1ZPq1nb/dvarD1ImwWyzeLnSMSKWIuIIcApYydtXIZe4iJgD",
  "hoEPeeIUdqOMiAVgDJgFql3F1EArEXEBGAeeZEX1Aa/rXG+/5US9BSbVXcAhYAR4z/9U/gDr5LJX+I+e9QAAAABJRU5ErkJg",
  "gg=="
].join("");

// page/shared/art/providers/stepfun.svg
var stepfun_default = [
  "data:image/svg+xml,",
  '<?xml version="1.0" encoding="UTF-8"?>%0A<svg id="_%E5%9B%BE%E5%B1%82_1" data-name="%E5%9B%BE%E5',
  '%B1%82 1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">%0A  <defs>%0A    <style>%0A   ',
  '   .cls-1 {%0A        fill: %23fff;%0A      }%0A    </style>%0A  </defs>%0A  <path class="cls-1"',
  ' d="M10,0C4.48,0,0,4.48,0,10s4.48,10,10,10,10-4.48,10-10S15.52,0,10,0ZM7.3,16.34h-3.65v-3.65h3.6',
  "5v3.65ZM11.82,16.34h-3.65v-3.65h3.65v3.65ZM11.82,11.83h-3.65v-3.66h3.65v3.66ZM11.82,7.31h-3.65v-",
  '3.65h3.65v3.65ZM16.34,7.31h-3.65v-3.66h3.65v3.66Z"/>%0A  <rect x="3.65" y="12.69" width="3.65" h',
  'eight="3.65"/>%0A  <rect x="8.17" y="12.69" width="3.65" height="3.65"/>%0A  <rect x="8.17" y="8',
  '.17" width="3.65" height="3.66"/>%0A  <rect x="8.17" y="3.66" width="3.65" height="3.65"/>%0A  <',
  'rect x="12.69" y="3.65" width="3.65" height="3.66"/>%0A</svg>'
].join("");

// page/shared/art/providers/minimax.png
var minimax_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/ollama.png
var ollama_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/arcee.svg
var arcee_default = [
  "data:image/svg+xml,",
  '<svg width="140" height="140" viewBox="0 0 140 140" fill="none" xmlns="http://www.w3.org/2000/sv',
  'g">%0A<rect width="140" height="140" rx="16" fill="url(%23paint0_linear_11734_16342)"/>%0A<path ',
  'd="M69.9184 20L18.4663 110.622H30.3901L75.9619 30.5141L69.9184 20Z" fill="%2317CFCF"/>%0A<path d',
  '="M85.7622 48.0376L36.2703 110.788H49.5008L91.1524 57.8841L85.5989 48.0376H85.7622Z" fill="%2317',
  'CFCF"/>%0A<path d="M106.506 84.42L101.279 75.241L55.2175 110.622H72.3682L106.506 84.42Z" fill="%',
  '2317CFCF"/>%0A<path d="M115.98 101.109L79.5554 110.622H121.534L116.144 101.109H115.98Z" fill="%2',
  '317CFCF"/>%0A<defs>%0A<linearGradient id="paint0_linear_11734_16342" x1="70" y1="0" x2="70" y2="',
  '140" gradientUnits="userSpaceOnUse">%0A<stop stop-color="%23314040"/>%0A<stop offset="1"/>%0A</l',
  "inearGradient>%0A</defs>%0A</svg>%0A"
].join("");

// page/shared/art/providers/gmi.png
var gmi_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAACl0lEQVR42u1WPUskQRSsft06s4KCzi6IoxsIRgYmgqF/QvwP",
  "gqEYCJuY+AsMTMz9SM0FwVAQE8FATWRYVBZlnd3Z7vcuuHPA05lzF+9uuZsHDQPv0VNdVVPTCoCgj4rQZ1UAKgAVgP47QKbn",
  "kxBBKfVhT0TAzD3tq/otqbtiSCkFrTWcc1heXsbS0hKccyCilBUiwsHBAQ4PD9PZbkt6Wdvb25JVOzs7AkCMMV3v2xVDo6Oj",
  "8DwPnU4HnufBWgvnHIwxaDQaiOMYAwMDuLm56VmyXA8REbTWYGZUq1WcnJygVCqBmTEyMpIau9FoYHFxEXd3dzDG4OnpCdZa",
  "KKUgIl0b/lNUTkxMZErUbDZlbGxMepX/l5K9nmxubg6zs7OI4xgzMzOpQZVSuLq6wtnZGTzPQxRFaLfbIPoea1NTU1hYWAAz",
  "p9HAzDDG4PLyEufn5x+yl8kQEQkA2dvbe8dGp9MREZHV1dX3p/th4vX19Uw29/f3cw2fm9Ra62ydJTu+rLVgZiRJ8s4veXtm",
  "5tDry7a2tnB0dIQ4jjE9PY3NzU0QEZgZKysrmJ+fh+/7qNfr2NjYQLvdhlLqzWJm1Go1XF9fw/d9XFxcAEBuPn3KbOPj45ky",
  "xHEsQRCks2tra2kvSRIJw/BrcoiIYIwBM2NoaAhRFMH3fTjnMDw8nLLw/PyMSqWSpnar1cLj4yOUUmg2myiVSjDGgIhSOb8k",
  "qcvlsoRhKEEQyO7urlhrpdVqibVW6vW63N7eShRFUqvVJAgCmZyclHK5/PuS+v7+Pn1+eXmB1jo1aaVSSXthGOLh4eHP/lxP",
  "T09RrVaRJAm01hAROOcwODiI4+PjN7N5X+S/df34ma28C1o3rPQ1Q8UlvwBUACoA/e36BitOKWk7TYLyAAAAAElFTkSuQmCC"
].join("");

// page/shared/art/providers/kilocode.svg
var kilocode_default = [
  "data:image/svg+xml,",
  '<?xml version="1.0" encoding="UTF-8"?>%0A<svg id="Layer_1" xmlns="http://www.w3.org/2000/svg" ve',
  'rsion="1.1" viewBox="0 0 32 32">%0A  <rect width="32" height="32" fill="%23FFDD00"/>%0A  <g fill',
  '="%23000000">%0A    <path d="M23,26v-2h3v-5l-2-2h-4v2h-3v5l2,2h4ZM20,20h3v3h-3v-3Z"/>%0A    <rec',
  't x="12" y="17" width="3" height="3"/>%0A    <polygon points="26 12 23 12 23 9 20 6 17 6 17 9 20',
  ' 9 20 12 17 12 17 15 26 15 26 12"/>%0A    <path d="M0,0v32h32V0H0ZM29,29H3V3h26v26Z"/>%0A    <po',
  'lygon points="15 26 15 23 9 23 9 17 6 17 6 23.1875 8.8125 26 15 26"/>%0A    <rect x="12" y="6" w',
  'idth="3" height="3"/>%0A    <polygon points="9 12 12 12 12 15 15 15 15 12 12 9 9 9 9 6 6 6 6 15 ',
  '9 15 9 12"/>%0A  </g>%0A</svg>%0A'
].join("");

// page/shared/art/providers/opencode.png
var opencode_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAAAo0lEQVR42u3YMQoDIRAF0FFG0+opzF28QtpcKnWuk35Pod1C",
  "MoymCqTLriwhZP/vhIH/ihFBQ2/pvfta652+mBjjwRjzeJ0t/VgAAujvQLxidrLWnkZKWmtXIjpuDZpDCLcRUCllxg4BhGv/",
  "KSLic86XkRIR8c65bUGqykR0HgGp6rQUhB0CCCCAAAJoN689M/uU0jRUwuyXzhp8NmCpAdob6AmLYSsrbN4XNgAAAABJRU5E",
  "rkJggg=="
].join("");

// page/shared/art/providers/opencode-dark.png
var opencode_dark_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAAAp0lEQVR42u3YMQoDIRAF0DGupvEOtgFvY502l0qd66QRBqw9",
  "gywkMpgqkC4bWULI/t8Jwn/FiKiil4QQbK31Rl+Mc27PzPfnekc/FoAA+jvQ9MHe3Hs/jpQopS5EdFgbNJdSriMg7/2MGQII",
  "x/5djDE2pXQeKYkx2tbauiCt9UREpxGQ1jovBWGGAAIIIIAA2sxtLyKWmfNIiYjYxQ8CfDZgqAHaGugBijwvtIzxkAIAAAAA",
  "SUVORK5CYII="
].join("");

// page/shared/art/providers/bedrock.png
var bedrock_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAAE3UlEQVR42u2Yf0zUdRjHX9+T44cgcOBxiUL8UEo4EPAkPEmE",
  "EivQzTVnK3VTtD9sZmvr19pCo9mmuZa2mgq2BihuubLSBJGJJilKzPOEEs/jhx4eIHcg4P2mP5LLC8U7w+XKz1/ffb/P8/m8",
  "9jzvz+fzfB9BKN86xEM0RDxk4xHQ/wMoPjCUwsQ5ZMsiGScI/x5QsNiHT1PmsT9jEUaLiXXTUtDkreYLxbPMDp00JkBeblEL",
  "AvnRcgoT59Bg7CSlogST3cbW3+sJFHuzMDyWfco8In/Y5fRRhMj4KDED3c1+3mw4htFqHpsITZsg4fT8l8kMi2CDupbWgT5M",
  "dpvze5/VQllrE6K/pW532gI+b27AYDHx1vRZY5eyReExHNRpWXbqEFdv9rs9sYCAAAgeaswtDd24Q7hfjU1ipkR2V5+VdYfZ",
  "mjKP2IBgtjSdeTCi1t0c4FdDJwCpkjDC/fzvanu2R0+1vo0ijcpt/bgt6uFRb9BTb9A/0HNoVCB50ERejIgDoPJaK+d7uwFI",
  "CAplrnQKJS2NTluZrz+XcvNd/Md7ebnY3DdQqLcvhUkZZEqn8J7qBADlyjxquq6gG7zBiugE1tVXc7Jb5/TRmwaYerD4ngvK",
  "fMdjtJgxO+zuAxXIlQzarKRUlCAWiRiwWTnc0cKmpAxyJkWhqCylz2rxOB0b5UpWRMUjEgTyjn/rjPg9gbxFImo623kjLpU1",
  "sYkoKsvotZqp6WwnwEt8Rxipz3jO5LwyKtATE0KQffclK6MTWB4Vz9vnjruvoaK0HEpamkg/sodeqxmJty9LI58kWSIlKViK",
  "ytjlYm+wmFha++OoQDsU89k+MxuFRMaHF055Jup19dWUtjYB8Lh/INVZS9hxSUV522/snZ3LpsbTlN36DmAbcnC5v3dUoMU/",
  "H2BJRBwl2kZquq54BtR729nROtCHsmovetMgAEeuteI3ztVV4u3LPmXeiHmsDgcF6lo0/Ub6bVa+0l7wfJdZHA4ywyKouNaK",
  "5dZu8BJE5MfIKb6sxuywu+ySrLAIBu02dmlUI+aaGhBMuTKXNXWVOGBEqt0C2qiupTApg4YFy3n33HFCvH0pkCvZoK51sZvs",
  "F8CW5ExiAoIw221U6dtGzFWlbyNbFsnX6c//qU3NebY3N3gGdN1iYu3ZKuRBE9k5az4Wh52nj5Y7L1exSMT6uFTWTk3m48bT",
  "LDulpmfxa7xz261usJjZeStiMl9/8usqANg8Y67nQMND3dvN/vaLAE6YrLAIPkvN4mS3DkVlKT0WEwAOhjBY/tJdYeIcJ9A3",
  "7RcpTluAAM53Y3KXLQyP4f2EdFbVVXC2x/VOG7RZXRb7ICHd+by9uYFjne0AdzwM7xvop44WDnZocQyN/m+5Pi6VUB8/Xo9L",
  "YdvFBrdAPCo/Joh9nGfNMMyskMf4JDlzhG1ysJRVMXKePlrO6phEZgRLx7ZA+153mdzwaErTX2CyXwCBYm+2pWZTnJbDgauX",
  "Rtg7bqsYgXtG0+OUNd8w8NSRPeRHyznxzEv4iMaxW6tGUVmGxWF3FvnDC6uMXRRpzrM5eS47NCq3U+UsfT1pNgSLfSiQz+a5",
  "SdEUaVRkSKeQIgnjUIeWEu0Ffrne8Y8LNOF+uh/xgaEsi5pOlb6Nms527ENj10ARHrVjHgH914D+AMyf6Qfa+31XAAAAAElF",
  "TkSuQmCC"
].join("");

// page/shared/art/providers/azurefoundry.png
var azurefoundry_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAADSklEQVR42u2YTWgVVxTH/+e+ecl7JppgKSJKYgJV/CBqWwwk",
  "GEVBSyUgra3iM4hiC0p3Iq0bFbOui9qt1J0gdONCwQ+eKLQSibGKGlrUhyboI6J5H7kzmXn3nC40NbbGN1+hGy/cxcyce/jN",
  "Oeee+d8B3o93Dwq78MSJwZmplPlFBJsBJP79/MkTPfjTsTstrKhteHjnn379WmFgslmx0mnvHIDOqWz6rt1qSKiaWmHvAoBm",
  "v75VuPg439u26bRtg6nmw4fFmUpZqLHSTR3tlzZMW4TOni19qLU5WM0u/9RJKZUEALiuHAZwflqAtDYHIFRXzW6sTAl6BWQ7",
  "5pNpSdnp04/TWvM32jaoMivGECllQSkLFVdqv919e0PsEXrxIv01xDRWsxOhAlHyA5q0hwtl/s5P2qxg6fL2QKp3CmZ4E/Uz",
  "MZ4/q3TFGqHe3uFFWnOnH1tjmJV603U+7zb8/OPQwu4t80Ym329qQpGITGAg1zF7xGcjrVSYReSf6xl1luzd15prXlDX/+C+",
  "rp9s++A+7gBYFgjoyJGsVSyYHr/wpsIi8vKllYLsP7Awl0onWkpl523mSwOnLJ+ftxFSmeMfSDABtGbd7JzrmRbXM/E1RnuM",
  "eyRA8bNhiDAAoPWjhlSh5CK2Tp3J/DVLa7c7yG405nWEbMerd8YpPqDiqPOVQGYEAWIWI/wSqFh0QRQj0Jiu9FBwUWMzj3tE",
  "yWSp7AXSOO8E6ui40WxrszqMHvCMezeZUMvtMVMtQsY3kC57O8JKFMPer5ZKLndsrqYDh4KkLBNWUSaS7nE2NUd1matEiM74",
  "Ampr+/1jAIvDAuVyu0bnzz054miTwtRAQ8ryen0BJURlJLTifvUJ4fHLtpbPgLd2sd8Uq8zla10jPoBECfVtjXqCqK+pPejY",
  "/FxkUhEJHkPxlesDXVcBEl+njpVtfesFcjECy72bt9qXhFmoplBY2/+vc9l/gNYuyKaE8EVEvyY2oMKs9CYAjRGBRmMDEqFM",
  "5LgT3Y0FaMWKgUYQPo/MI5yNBYjY/RJAbUSevEpaZ2IBEsi2yOkS+qG//1MdUw1RewQUJqJDN2+vOhnftic6BaAURGUAeATg",
  "FJhWD/yxqvf9H67pHn8DjTCGevdDfW4AAAAASUVORK5CYII="
].join("");

// page/shared/art/providers/vercel.svg
var vercel_default = [
  "data:image/svg+xml,",
  '<svg xmlns="http://www.w3.org/2000/svg" width="115" height="100" fill="none" viewBox="0 0 115 10',
  '0"><path fill="black" fill-rule="evenodd" d="M57.5 0 115 100H0z" clip-rule="evenodd" style="fill',
  ':black;fill-opacity:1;"/></svg>'
].join("");

// page/shared/art/providers/vercel-dark.svg
var vercel_dark_default = [
  "data:image/svg+xml,",
  '<svg xmlns="http://www.w3.org/2000/svg" width="115" height="100" fill="none" viewBox="0 0 115 10',
  '0"><path fill="white" fill-rule="evenodd" d="M57.5 0 115 100H0z" clip-rule="evenodd" style="fill',
  ':white;fill-opacity:1;"/></svg>'
].join("");

// page/shared/art/providers/actual.png
var actual_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAADlElEQVR42u2YQUgqXRTHj2mI1RRuAhdFJrmrTfbCyFVJEEEE",
  "kpvaBEEQCdImc2GLolWLhIgg3AVRuBAiTASNAkEiqaDQRWkEkmGFlZqS/7er5ht9jV/5fS7egbO4M+cefjPzP+feOwIAoDKy",
  "Cioz+wv0FyifBYNB2tvbKx+g5eVl8ng85QGUzWZpa2uLIpFIeQA5nU6Kx+O8gQgltLe3N3R2doKIIBaLkUgkvpxTUiCHwwEi",
  "eneHw/HlnIpSV9dnOzo6+n811NHRwRpLpdL/TkPBYBAmkwm/fv3C5OQkkskkcrkc+vv7IRAIMDg4iGQyWToNPTw8wOFwYHZ2",
  "FiqViqUVIsLExMR77OPjI++8RQNlMhnMzc1BIpFwID67WCxGNpst+kFFxWji9vaWhoaGyOfzFYxhGIZkMhlptVoSiUTFC48v",
  "udvtRmNjI+dNKJVKrKys4OrqCqlU6tta/BLo4OAAer0eAoGABSIUCjEzM/MjEF8CBQIBGAwGNDc359WHQqHA/v5+SZopB+jk",
  "5ASVlZV5Qaqrq2E2m3mV748BhUIhDgjDMDAYDIhGoyi15f1kAwMDEIlEaG9vx9LSUlF95Lsm+O4xKBaLkd1up0gkQgBIoVCQ",
  "SqWitra20pb9P+3w8BB6vb6g3iQSCVpbW7G+vs4pmLW1NWxubuLi4uJ7nfrs7AwWiwUtLS1/7NKfvb6+npVDo9Gw7vf29iIW",
  "i/EDen19hcvlwtTUFORyOW+Iz97Q0MDKOTo6yonp6elBLpcrDOTz+TA2Noba2lrO5KqqqqKAtFotK7fZbM4b5/V6uRu0+/t7",
  "GhkZIbVaTTabjRKJBEtvRqORXl5eyGg08tYowzCscTqdzhsXCATYG7RwOExqtZo2NjYKJu/q6iIiou7ubt5ANzc3rPHx8XHe",
  "OIFA8AGUSCSor6+PQqHQj+8a/X4/Wa1Wury8JKvVSl6vN2+cUqn8KPvV1VVeetje3gYA2O3292s6nQ6pVAoulws6na5gG/iT",
  "MwyDp6enD1F7PJ731VwkEmF6ehqxWAzPz8+Yn59/n7izs8MBcjqdLNFGo1EsLCygqamJN5DJZOKWvdvtxuLiIs7PzzlVZ7PZ",
  "YLFYkE6nAQB+vx9CoRBSqRTxeLzgmWx3dxfDw8Ooq6vLC1JRUYHx8XHWzvJfLx13d3dUU1NDEomE13H69PSUwuEwXV9fUyaT",
  "IZlMRhqNhuRyOVvc5fZL7zeyVkucJxIGGAAAAABJRU5ErkJggg=="
].join("");

// page/shared/art/providers/actual-dark.png
var actual_dark_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAADl0lEQVR42u2YTUgyXRTHz0SaklkYWotQCbKCkIqKoOgDkWrj",
  "os9FqwoiWhi0CgpyYbUKMYQgahMtDDdBtChbVWihK1cp2dcm2vRpJjX5fzYv9czr2GOW7+viOTCLO3Pm8Lv3/s+Zc4chIlAa",
  "WQalmf0F+gvEZ6WlpdTW1pY+QGNjY9Ta2poeQAKBgHp7e0mlUqUHUHt7O+Xn5ycMRP8UxpRcGRkZODw8BABEIhHk5OQk8l7q",
  "gAwGA343g8Hw50mkOrt+t5qamv9XQx6PhzO+vb397zSk0WgwOzuLo6Mj2Gw2iMViMAyDra0tRKNRbGxsQCwWp05DeXl5MBgM",
  "mJmZgcfjwb9tcXHx3Tc3N/crsb8GIhAIMD09jXA4jM8sEokgMzMzmckm7lxQUACXy/UpyMPDA/x+P2w2W7Lbn5ijTqfDxcVF",
  "DIDf78fo6CjUajVEItFP6PFzh8bGRtjtdkSjUQ4Iy7KYm5v7KYjPgSorK2G1WhEMBnm35eTkBE1NTakqqNwbWq0WLy8vvCCh",
  "UAhmsznR9P0ZoJKSEl6hWq1WFBYWphIk/pZtbm7i9fUVXq8X4+PjX60j37qY7x6DFAoFdXV1kUqlIoZhKBgMktfrJZ/PRyzL",
  "JhUzqZk0NDTAbrfH1Vs4HIbP58PQ0FBMwgwPD6Ovrw9lZWXfK4wVFRUwmUwIBAJI1K6vrzkx9vb2OM+dTifkcnliQEKhEHq9",
  "HgsLCzg9PUUydnl5yYm5uroa47O7uwuGYeID1dfXY2VlBff39zEvPz09fQloZ2eHE9tsNvP6NTc3xzZoMpmM1tbWyO120+Dg",
  "IEmlUo7YLBYLZWdnk8ViSVigj4+PnLFIJOL1q6qq4jZoarWa3G439ff3xw3ucrmIiOjg4CBhoKKiIs64urqaP7OADyCpVErb",
  "29uk0Wh+vGusq6sjo9FIxcXFZDQaqaWlhdcvEAh8wI2MjCSkh+7ubhAROjs73+85HA6IRCLo9Xo4HI64ZeBPLYtEIvnQ0PHx",
  "8fuSsSxL8/PzpFAoSCKR0NTU1Dv58/NzzMyWl5cpEomQ0+mknp4eUiqVNDk5Sefn5wmvos1mo1AoxC2MOp0OExMTKC8vj8m6",
  "gYEBmEwmZGVlgYhQW1sLlmVxc3MDmUwW90zW0dGB9fV13N3d8a7M29sblpaWOJ1l0p8OuVxOoVCId9X4jtNarZbUajUplUoS",
  "CoV0dXVF+/v7dHZ2xvFl0u2X3i8S9iHoH7Th8gAAAABJRU5ErkJggg=="
].join("");

// page/shared/art/providers/commandcode.png
var commandcode_default = [
  "data:image/png;base64,",
  "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",
  "sVACZcHr7AAAAABJRU5ErkJggg=="
].join("");

// page/shared/art/providers/deepinfra.png
var deepinfra_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/meta.png
var meta_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/nebius.png
var nebius_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAACWklEQVR42u2Yy08TURTGvzt3hmljQRa2pkIyXTgJKzQSu6AJ",
  "CQs0wVZ84AO3+h9oNHVBdIHuWBlZKJpoWLGAhpr42EB0QaIsaBc1QiA0aJpISZTWEmbmjgsJk4HSB3Y6RHt2d+aem1++87hn",
  "hnzR23TsI+Owz6wGVAP654D4ch3m5igSnzm4D+nw+1VQaiPQ4KADz56L0Dc7l+RjGHqUheRjBf0SCYpk0ghGe0BFvSt/+yOl",
  "NsZYjKLvmmvH8+ZmhkhkDQ5xd98HD50YGanbWo+PZSDL2t5yiDGC6WkesThFf38OHR2q6f3yMofRUbE6Sb20RHG2x4XrNw4g",
  "maS4cnkDQ4+z6Lu6YdoXiQjVAQrfdWJxceeWm7fW4fEwU47Mz3PWAqVXOczO5i8hp0NH70WzShMTddYCraZJQcdg0JxL0VcC",
  "GCPWAelFak+SNLS2GpWSSnH4+Ina26lDQXPYohUI218BdXcrEARDyrfveOTWiX1AjY06AgEjlzIZgqlJwd7LNRRUtlUbby9Q",
  "Z6eChnojbO8/CFhJk8oDkRLPFEWg65ShkqYBb14XC5tu7TwUCm1rktHC1eY5bDFQ2wkG7xHjKonHKWZm8udSoF3FwQaLgThO",
  "R+iMWaV79x348dMc9+PHVAwM/KrsxLibnetRMDzsgLYp1MICRe8lF053KZCPahgfW4Mss+rN1JKP4fwFs0rfvnJ48VKE/6Ra",
  "EkxBhZqaGJ4+yW6tvd7iB4bDOax8J5ic+lNlPA/cuZ0rOuLuaYQt90MglSJoadHgdpd3PKn9bKgB1YD+N6DfCFTBlSkXm/EA",
  "AAAASUVORK5CYII="
].join("");

// page/shared/art/providers/ramp.png
var ramp_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/providers/upstage.png
var upstage_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkCAYAAADhAJiYAAACMUlEQVR42uWXz2sTQRTHv2927bYFoQiCf4BHEUGkB8VfIDZo",
  "q6XgrYpWPKhIrIgXwYCCSKDosUIokosELz1YPShCQQyCZxElWMFLUUSx3TTZma8HIXTbdbMVZ0jxHd8MzIf3fbzvG4HDmH7B",
  "rYZ4vyKtfcGWwQPyBQB8l0A6wvGE9Ozgod8wzoGosR1ELZZUeIhODrHSK9PcWPfQn+HxbyeOypvlOSuShcSwRHzQ7p4h7wGw",
  "D0RtDjND8cWomZU5O01t8BHk/VRogvVFmUWnR6yu5TL3Q5kBJy8bNTU6Ku9SJSOZh5ZjLmYkiWLSQQuoUmFXuMCDjpSpnjot",
  "X1OBGg10Gy1jLmgU8AHrJRKHRWmSe8SYu3YMTebOnFcjfzpOnENsmmED7LRksdW0Uz95pCMHWsIBn6wZKPLUbls9Mj+P73/t",
  "9pMF9uoAgQ2weoD6+LiEa/Iy3cNHAHM2gIImzwIoZQaaKrB70Zh9tpZHpb2nmXsIAH762CYGb63QUGoXrsvn9TsYCwWqPqNH",
  "nNiIMnOXCl2vUyXr081dpKo4+Rpp7wqAdCCtJSd0I5Hy1OP2Td2UTxTecYAT5m+vXtI6u6mL+egIBUPtTVtq1ya8f17FVZIZ",
  "g4sABjL8YYo2KhQDmrjMnqWG3puxtjPWgX4swQvITEv+Ju2/xP8Qsmxxkltj0SuBbI7NJPDcjdKG566AWpLdPNncAS39jK+K",
  "Ya/2qy4r1AKikaGEtfXZ1bIsuAT6BWjLzQUZUjTlAAAAAElFTkSuQmCC"
].join("");

// page/shared/art/providers/index.js
var LOGOS = {
  nous: { name: "Nous Research", light: nous_default, dark: nous_dark_default, source: "https://nousresearch.com/ (its header badge, the girl’s head only, as the owner asked: black, white on dark)" },
  fireworks: { name: "Fireworks AI", light: fireworks_default, dark: fireworks_default, source: "https://fireworks.ai/icon.svg" },
  openrouter: { name: "OpenRouter", light: openrouter_default, dark: openrouter_dark_default, source: "https://openrouter.ai/brand" },
  novita: { name: "Novita AI", light: novita_default, dark: novita_default, plate: "dark", source: "https://novita.ai/logo/logo_small.svg" },
  lmstudio: { name: "LM Studio", light: lmstudio_default, dark: lmstudio_default, source: "https://lmstudio.ai/brand" },
  anthropic: { name: "Anthropic", light: anthropic_default, dark: anthropic_dark_default, source: "https://www.anthropic.com/press-kit" },
  claude: { name: "Claude", light: claude_default, dark: claude_default, source: "https://www.anthropic.com/press-kit" },
  openai: { name: "OpenAI", light: openai_default, dark: openai_dark_default, source: "https://openai.com/brand/" },
  xai: { name: "xAI (Grok)", light: xai_default, dark: xai_dark_default, source: "https://x.ai/legal/brand-guidelines" },
  qwen: { name: "Qwen", light: qwen_default, dark: qwen_default, plate: "dark", source: "https://github.com/QwenLM/qwen-code" },
  alibabacloud: { name: "Alibaba Cloud", light: alibabacloud_default, dark: alibabacloud_default, source: "https://www.alibabacloud.com/" },
  xiaomimimo: { name: "Xiaomi MiMo", light: xiaomimimo_default, dark: xiaomimimo_default, source: "https://platform.xiaomimimo.com/" },
  tencentcloud: { name: "Tencent Cloud", light: tencentcloud_default, dark: tencentcloud_default, source: "https://cloud.tencent.com/" },
  nvidia: { name: "NVIDIA", light: nvidia_default, dark: nvidia_default, source: "https://www.nvidia.com/" },
  huggingface: { name: "Hugging Face", light: huggingface_default, dark: huggingface_default, source: "https://huggingface.co/brand" },
  gemini: { name: "Google AI Studio", light: gemini_default, dark: gemini_default, source: "https://aistudio.google.com/" },
  vertexai: { name: "Google Cloud Vertex AI", light: vertexai_default, dark: vertexai_default, source: "https://cloud.google.com/icons" },
  deepseek: { name: "DeepSeek", light: deepseek_default, dark: deepseek_default, source: "https://github.com/deepseek-ai/awesome-deepseek-integration/tree/main/docs/_logo%20svg" },
  zai: { name: "Z.AI", light: zai_default, dark: zai_default, source: "https://z.ai/" },
  kimi: { name: "Kimi (Moonshot AI)", light: kimi_default, dark: kimi_dark_default, source: "https://moonshotai.github.io/Branding-Guide/scenarios/04-k-only/" },
  stepfun: { name: "StepFun", light: stepfun_default, dark: stepfun_default, plate: "light", source: "https://www.stepfun.com/" },
  minimax: { name: "MiniMax", light: minimax_default, dark: minimax_default, source: "https://agent.minimax.io/" },
  ollama: { name: "Ollama", light: ollama_default, dark: ollama_default, source: "https://ollama.com/" },
  arcee: { name: "Arcee AI", light: arcee_default, dark: arcee_default, source: "https://www.arcee.ai/" },
  gmi: { name: "GMI Cloud", light: gmi_default, dark: gmi_default, source: "https://www.gmicloud.ai/" },
  kilocode: { name: "Kilo Code", light: kilocode_default, dark: kilocode_default, source: "https://kilo.ai/" },
  opencode: { name: "OpenCode", light: opencode_default, dark: opencode_dark_default, source: "https://opencode.ai/brand" },
  bedrock: { name: "Amazon Bedrock", light: bedrock_default, dark: bedrock_default, source: "https://aws.amazon.com/architecture/icons/" },
  azurefoundry: { name: "Microsoft Foundry", light: azurefoundry_default, dark: azurefoundry_default, source: "https://learn.microsoft.com/en-us/azure/architecture/icons/" },
  vercel: { name: "Vercel", light: vercel_default, dark: vercel_dark_default, source: "https://vercel.com/geist/brands" },
  actual: { name: "Actual", light: actual_default, dark: actual_dark_default, source: "https://actual.inc/favicon.svg" },
  commandcode: { name: "Command Code", light: commandcode_default, dark: commandcode_default, source: "https://commandcode.ai/brand" },
  deepinfra: { name: "DeepInfra", light: deepinfra_default, dark: deepinfra_default, source: "https://deepinfra.com/media-center" },
  meta: { name: "Meta", light: meta_default, dark: meta_default, source: "https://dev.meta.ai/" },
  nebius: { name: "Nebius", light: nebius_default, dark: nebius_default, source: "https://nebius.com/" },
  ramp: { name: "Ramp", light: ramp_default, dark: ramp_default, source: "https://router.com/" },
  upstage: { name: "Upstage", light: upstage_default, dark: upstage_default, source: "https://www.upstage.ai/resources/brand-resource-center" }
};
var PROVIDER_BRANDS = {
  nous: ["nous"],
  fireworks: ["fireworks", "fireworks-ai", "fw"],
  openrouter: ["openrouter"],
  novita: ["novita", "novita-ai", "novitaai"],
  lmstudio: ["lmstudio"],
  anthropic: ["anthropic"],
  claude: ["claude-subscription-directsdk-experimental"],
  openai: ["openai-api", "openai-codex"],
  qwen: ["alibaba", "qwen-oauth"],
  xai: ["xai", "xai-oauth"],
  xiaomimimo: ["xiaomi"],
  tencentcloud: ["tencent-tokenhub", "tencent-tokenplan"],
  nvidia: ["nvidia"],
  huggingface: ["huggingface"],
  gemini: ["gemini"],
  vertexai: ["vertex"],
  deepseek: ["deepseek"],
  zai: ["zai"],
  kimi: ["kimi-coding", "kimi-coding-cn"],
  stepfun: ["stepfun"],
  minimax: ["minimax", "minimax-cn", "minimax-oauth"],
  ollama: ["ollama-cloud"],
  arcee: ["arcee"],
  gmi: ["gmi"],
  kilocode: ["kilocode"],
  opencode: ["opencode-go", "opencode-zen"],
  bedrock: ["bedrock"],
  azurefoundry: ["azure-foundry"],
  vercel: ["ai-gateway"],
  actual: ["actual"],
  alibabacloud: ["alibaba-cloud-cn", "alibaba-cn", "alibaba-coding-cn", "alibaba-coding-plan", "alibaba-coding-plan-cn", "alibaba-token-plan", "alibaba-token-plan-cn", "dashscope-cn", "dashscope-coding-cn", "dashscope-token-plan", "dashscope-token-plan-cn"],
  commandcode: ["commandcode", "commandcode-anthropic", "commandcode-chat", "commandcode-claude"],
  deepinfra: ["deep-infra", "deepinfra", "deepinfra-ai"],
  meta: ["meta", "meta-ai", "model-api", "msl", "muse", "muse-spark"],
  nebius: ["nebius", "nebius-tf", "nebius-token-factory", "nebius-tokenfactory", "token-factory", "tokenfactory"],
  ramp: ["ramp", "ramp-router", "router", "router.com"],
  upstage: ["solar", "upstage"]
};
var BRAND_OF = new Map(Object.entries(PROVIDER_BRANDS).flatMap(([brand, slugs]) => slugs.map((slug) => [slug, brand])));
var providerLogo = (slug) => LOGOS[BRAND_OF.get(String(slug ?? "").toLowerCase())] ?? null;

// page/pages/build/composer/provider-logo.js
function ProviderMark({ slug, letters, className }) {
  const logo = providerLogo(slug);
  const dark = useTheme().renderedMode === "dark";
  if (!logo) {
    return jsx("span", { "aria-hidden": true, className, children: letters });
  }
  return jsx("span", {
    "aria-hidden": true,
    // A mark with no version for this theme sits on a plate in the text colour (light on dark, dark on light).
    className: `${className} cs-b-logo${logo.plate === (dark ? "dark" : "light") ? " plate" : ""}`,
    "data-brand": logo.name,
    children: jsx("img", { alt: "", draggable: false, src: dark ? logo.dark : logo.light })
  });
}

// page/pages/build/composer/model-list.js
var STARRED = "*starred";
var starKey = (provider, model) => `${provider}:${model}`;
function useModelRows(providers, tab, needle, stars) {
  return useMemo(() => {
    const row = (item2, model) => ({ model, provider: item2.slug, providerName: item2.name, caps: item2.capabilities?.[model] ?? null });
    if (needle) {
      return providers.map((item2) => ({
        name: item2.name,
        rows: item2.models.filter((model) => model.toLowerCase().includes(needle) || modelName(model).name.toLowerCase().includes(needle)).map((model) => row(item2, model))
      })).filter((group) => group.rows.length);
    }
    if (tab === STARRED) {
      return [{ name: null, rows: providers.flatMap((item2) => item2.models.filter((model) => stars.has(starKey(item2.slug, model))).map((model) => row(item2, model))) }];
    }
    const item = providers.find((provider) => provider.slug === tab);
    return item ? [{ name: null, rows: item.models.map((model) => row(item, model)) }] : [];
  }, [providers, tab, needle, stars]);
}
function ProviderRail({ providers, marks, tab, onTab, onConnect }) {
  const tile = (key, label, mark, extra = {}) => jsxs(
    "button",
    {
      "aria-label": label,
      "aria-pressed": tab === key,
      className: `cs-b-mp-tile${extra.className ? ` ${extra.className}` : ""}`,
      onClick: () => onTab(key),
      title: label,
      type: "button",
      children: [mark, jsx("span", { className: "cs-sr cs-b-mp-pname", children: label })]
    },
    key
  );
  return jsxs("div", {
    "aria-label": "Providers",
    className: "cs-b-mp-rail",
    role: "group",
    children: [
      tile(STARRED, "Starred", jsx(Codicon, { name: "star-full", size: 14 }), { className: "cs-b-mp-starred" }),
      jsx("span", { "aria-hidden": true, className: "cs-b-mp-sep" }),
      ...providers.map((item) => tile(item.slug, item.name, jsx(ProviderMark, { className: "cs-b-mp-pmark", letters: marks.get(item.slug), slug: item.slug }), { className: "cs-b-mp-prov" })),
      jsx("span", { className: "cs-grow" }),
      jsx("button", {
        "aria-label": "Connect another provider",
        className: "cs-b-mp-tile",
        onClick: onConnect,
        title: "Connect another provider",
        type: "button",
        children: jsx(Codicon, { name: "add", size: 14 })
      })
    ]
  });
}
function ModelRow({ row, mark, on, starred, withProvider, onChoose, onStar }) {
  const label = modelName(row.model);
  return jsxs("div", {
    className: `cs-b-mp-item${on ? " on" : ""}${starred ? " starred" : ""}`,
    children: [
      jsxs("button", {
        "aria-selected": on,
        className: "cs-b-mp-row",
        onClick: () => onChoose(row),
        role: "option",
        title: `${row.model} · ${row.providerName}`,
        type: "button",
        children: [
          jsx(ProviderMark, { className: "cs-b-mp-glyph", letters: mark, slug: row.provider }),
          // The starred list mixes providers: each row names its own under the model.
          withProvider ? jsxs("span", { className: "cs-b-mp-label two", children: [jsx("span", { children: label.name }), jsx("small", { className: "cs-b-mp-from", children: row.providerName })] }) : jsx("span", { className: "cs-b-mp-label", children: label.name }),
          ...label.tags.map((tag) => jsx("span", { className: "cs-b-mp-tag", children: tag }, tag)),
          on ? jsx("span", { className: "cs-b-mp-check", children: jsx(Codicon, { name: "check", size: 12 }) }) : null
        ]
      }),
      jsx("button", {
        "aria-label": starred ? `Unstar ${label.name}` : `Star ${label.name}`,
        "aria-pressed": starred,
        className: "cs-b-mp-star",
        onClick: () => onStar(row),
        title: starred ? "Unstar" : "Star",
        type: "button",
        children: jsx(Codicon, { name: starred ? "star-full" : "star-empty", size: 12 })
      })
    ]
  });
}
function ModelList({ groups, marks, head, search, query, setQuery, placeholder, shown, stars, onChoose, onStar, empty, withProvider }) {
  const first = groups[0]?.rows[0];
  return jsxs("div", {
    className: "cs-b-mp-models",
    children: [
      jsxs("label", {
        className: "cs-b-mp-search",
        children: [
          jsx(Codicon, { name: "search", size: 12 }),
          jsx("input", {
            "aria-label": "Search models",
            onChange: (event) => setQuery(event.target.value),
            onKeyDown: (event) => {
              if (event.key === "Enter" && first) {
                event.preventDefault();
                onChoose(first);
              }
            },
            placeholder,
            ref: search,
            value: query
          })
        ]
      }),
      head ? jsx("div", { className: "cs-b-mp-head", children: head }) : null,
      jsx("div", {
        className: "cs-b-mp-list",
        role: "listbox",
        children: groups.some((group) => group.rows.length) ? groups.flatMap((group) => [
          group.name ? jsx("div", { className: "cs-b-mp-group", children: group.name }, `g:${group.name}`) : null,
          ...group.rows.map(
            (row) => jsx(
              ModelRow,
              {
                mark: marks.get(row.provider),
                on: row.model === shown.model && row.provider === shown.provider,
                onChoose,
                onStar,
                row,
                starred: stars.has(starKey(row.provider, row.model)),
                withProvider
              },
              starKey(row.provider, row.model)
            )
          )
        ]) : jsx("p", { className: "cs-faint", children: empty })
      })
    ]
  });
}
var connectProvider = (close) => () => {
  close();
  host.navigate?.("/settings?tab=providers");
};

// page/pages/build/composer/model-settings.js
var FAST_HINT = "Quicker replies. Uses more of your plan";
var ARROWS = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 };
function radioProps(keys, current, index, pick, disabled) {
  return {
    "data-key": keys[index],
    tabIndex: (keys.includes(current) ? keys[index] === current : index === 0) ? 0 : -1,
    onKeyDown: (event) => {
      const step = ARROWS[event.key];
      if (!step || disabled) {
        return;
      }
      event.preventDefault();
      const next = keys[(index + step + keys.length) % keys.length];
      pick(next);
      event.currentTarget.parentElement?.querySelector(`[data-key="${next}"]`)?.focus?.();
    }
  };
}
function EffortColumn({ caps, shown, disabled, narrow, onEffort }) {
  const fixed = caps ? caps.reasoning === false : false;
  const levels = EFFORTS.filter(([key]) => key !== "none" || caps?.can_disable_reasoning !== false);
  const picked = EFFORTS.find(([key]) => key === shown.effort);
  return jsxs("div", {
    className: "cs-b-mp-effort",
    children: [
      jsxs("div", {
        className: "cs-b-mp-ehead",
        children: [
          jsx("span", { children: "Effort" }),
          shown.model ? jsx("span", { className: "cs-b-mp-emodel", title: shown.model, children: modelName(shown.model).name }) : null
        ]
      }),
      jsx("div", {
        "aria-label": "Effort",
        className: "cs-b-mp-levels",
        role: "radiogroup",
        children: levels.map(
          ([key, label, hint], index) => jsxs(
            "button",
            {
              ...radioProps(levels.map(([level]) => level), shown.effort, index, (next) => next !== shown.effort && onEffort(next), disabled || fixed),
              "aria-checked": shown.effort === key,
              disabled: disabled || fixed,
              onClick: () => key !== shown.effort && onEffort(key),
              role: "radio",
              title: hint,
              type: "button",
              children: [label, shown.effort === key ? jsx(Codicon, { name: "check", size: 12 }, "check") : null]
            },
            key
          )
        )
      }),
      narrow ? null : jsxs("div", {
        className: "cs-b-mp-enote",
        children: fixed ? [jsx("b", { children: "Fixed" }, "b"), "This model has a fixed effort"] : picked ? [jsx("b", { children: picked[1] }, "b"), picked[2]] : [jsx("b", { children: "Default" }, "b"), "The model’s own effort"]
      })
    ]
  });
}
function SpeedBar({ speed, fast, held, narrow, disabled, onFast, onManage }) {
  return jsxs("div", {
    className: "cs-b-mp-bar",
    children: [
      speed ? jsx("div", {
        "aria-label": "Speed",
        className: "cs-b-seg cs-b-mp-speed",
        role: "radiogroup",
        children: [
          ["normal", false, "Standard", "Standard speed"],
          ["fast", true, [jsx(Codicon, { name: "zap", size: 11 }, "zap"), "Fast"], FAST_HINT]
        ].map(
          ([key, on, label, title], index) => jsx(
            "button",
            {
              ...radioProps(["normal", "fast"], fast ? "fast" : "normal", index, (next) => next === "fast" !== fast && onFast(next === "fast"), disabled),
              "aria-checked": fast === on,
              className: on ? "cs-b-mp-fast" : void 0,
              disabled,
              onClick: () => on !== fast && onFast(on),
              role: "radio",
              title,
              type: "button",
              children: label
            },
            key
          )
        )
      }) : null,
      jsx("span", { className: "cs-grow" }),
      held ? jsx("span", { className: "cs-b-mp-held", children: narrow ? "Switches after this turn" : `Switches when ${AGENT} finishes this turn` }) : jsxs("button", {
        className: "cs-b-mp-manage",
        onClick: onManage,
        type: "button",
        children: [narrow ? "Providers" : "Manage providers", jsx(Codicon, { name: "chevron-right", size: 11 }, "go")]
      })
    ]
  });
}

// page/pages/build/composer/model-picker.js
var PANEL = 560;
var NARROW = 500;
var TINY = 440;
function useModelOptions(runtime, needed = true) {
  const gateway = useValue(host.state.gateway);
  return useQuery({
    queryKey: [ID, "models", runtime ?? "profile"],
    queryFn: () => chatRequest("model.options", runtime ? { session_id: runtime } : {}, 3e4),
    enabled: needed && gateway === "open",
    staleTime: 5 * 6e4,
    refetchOnWindowFocus: false,
    retry: 1
  });
}
function panelArea(node) {
  let start = 0;
  let end = window.innerWidth || 1200;
  let clip = null;
  for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
    const rect = parent.getBoundingClientRect();
    if (rect.width > 0 && getComputedStyle(parent).overflowX !== "visible") {
      start = Math.max(start, rect.left);
      end = Math.min(end, rect.right);
      clip = parent;
      break;
    }
  }
  return { start, end, clip };
}
function useStars(ctx) {
  const [stars, setStars] = useState(() => {
    try {
      const saved = ctx?.storage?.get?.("buildModelStars", []);
      return new Set(Array.isArray(saved) ? saved : []);
    } catch {
      return /* @__PURE__ */ new Set();
    }
  });
  const toggle = (key) => {
    const next = new Set(stars);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setStars(next);
    try {
      ctx?.storage?.set?.("buildModelStars", [...next]);
    } catch {
    }
  };
  return [stars, toggle];
}
function ModelPicker({ ctx, value, pending = null, waiting = false, confirm = null, options, onPick, onEffort, onFast, onConfirm, onCancelConfirm, disabled = false, up = true, draft = false }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState(null);
  const [query, setQuery] = useState("");
  const [stars, toggleStar] = useStars(ctx);
  const box = useRef(null);
  const search = useRef(null);
  const data = options?.data;
  const providers = useMemo(() => Array.isArray(data?.providers) ? data.providers.filter((item) => item?.authenticated && Array.isArray(item.models) && item.models.length) : [], [data]);
  const fallback = draft ? null : data;
  const shown = { model: pending?.model ?? value?.model ?? fallback?.model ?? null, provider: pending?.provider ?? value?.provider ?? fallback?.provider ?? null, effort: pending?.effort ?? value?.effort ?? "", fast: pending?.fast ?? value?.fast ?? false };
  const marks = useMemo(() => providerMarks(providers), [providers]);
  const current = providers.find((item) => item.slug === shown.provider) ?? null;
  const signedOut = Boolean(data && shown.provider && !current && Array.isArray(data.providers));
  const caps = current?.capabilities?.[shown.model] ?? null;
  const activeTab = tab === STARRED || providers.find((item) => item.slug === tab) ? tab : current?.slug ?? providers[0]?.slug ?? null;
  const activeProvider = providers.find((item) => item.slug === activeTab) ?? null;
  const needle = query.trim().toLowerCase();
  const speed = !needle && activeTab === shown.provider && hasFastMode(shown.provider, caps);
  const groups = useModelRows(providers, activeTab, needle, stars);
  const name = shown.model ? modelName(shown.model).name : "Default model";
  const [place, setPlace] = useState(null);
  const narrow = Boolean(place && place.width < NARROW);
  const tiny = Boolean(place && place.width < TINY);
  useLayoutEffect(() => {
    if (!open || !box.current?.getBoundingClientRect) {
      setPlace(null);
      return void 0;
    }
    const measure = () => {
      if (!box.current) {
        return null;
      }
      const left = box.current.getBoundingClientRect().left;
      const { start, end, clip: clip2 } = panelArea(box.current);
      const width = Math.min(PANEL, end - start - 24);
      const shift = Math.max(start + 12 - left, Math.min(0, end - 12 - left - width));
      setPlace((last) => last && last.left === shift && last.width === width ? last : { left: shift, width });
      return clip2;
    };
    const clip = measure();
    const watch = typeof ResizeObserver === "function" && clip ? new ResizeObserver(() => measure()) : null;
    watch?.observe(clip);
    window.addEventListener("resize", measure);
    return () => {
      watch?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [open]);
  useEffect(() => {
    if (!open) {
      return void 0;
    }
    setQuery("");
    setTab(null);
    const focus = () => search.current?.focus?.();
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(focus);
    } else {
      focus();
    }
    const away = (event) => {
      if (box.current && !box.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const key = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", away);
    window.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", away);
      window.removeEventListener("keydown", key);
    };
  }, [open]);
  useEffect(() => {
    if (confirm) {
      setOpen(true);
    }
  }, [confirm?.message]);
  const choose = (row) => {
    setOpen(false);
    if (!disabled && (draft || row.model !== shown.model || row.provider !== shown.provider)) {
      onPick({ model: row.model, provider: row.provider, ...shown.fast && !hasFastMode(row.provider, row.caps) ? { fast: false } : {} }, row);
    }
  };
  const close = () => setOpen(false);
  const count = activeProvider ? activeProvider.total_models ?? activeProvider.models.length : 0;
  const head = needle ? null : activeTab === STARRED ? [jsx("b", { children: "Starred" }, "b"), narrow ? null : jsx("span", { children: "· from every provider" }, "n")] : activeProvider ? [jsx("b", { title: activeProvider.name, children: activeProvider.name }, "b"), jsx("span", { children: narrow ? `· ${count}` : `· ${count} ${count === 1 ? "model" : "models"}` }, "n")] : null;
  const empty = needle ? "No model matches." : activeTab === STARRED ? "Star a model with its ☆ to keep it here." : !data && !options?.isError ? "Loading…" : options?.isError ? "Could not list the models." : "No provider is connected.";
  return jsxs("div", {
    className: "cs-b-mp",
    ref: box,
    children: [
      jsxs("button", {
        "aria-expanded": open,
        "aria-haspopup": "dialog",
        className: `cs-b-mp-chip${open ? " open" : ""}${signedOut ? " warn" : ""}`,
        disabled,
        onClick: () => setOpen(!open),
        title: shown.model ? `${shown.model} · ${current?.name ?? shown.provider ?? ""}` : "Model and effort",
        type: "button",
        children: [
          signedOut ? jsx(Codicon, { name: "warning", size: 12 }) : jsx(ProviderMark, { className: "cs-b-mp-mark", letters: marks.get(current?.slug) ?? providerMark(shown.provider), slug: shown.provider }),
          jsx("span", { className: "cs-b-mp-name", children: signedOut ? `${shown.provider} is signed out` : name }),
          !signedOut ? jsx("span", { className: "cs-b-mp-dot", children: "·" }) : null,
          !signedOut ? jsx("span", { className: "cs-b-mp-effortname", children: effortLabel(shown.effort) }) : null,
          !signedOut && shown.fast ? jsx("span", { "aria-label": "Fast mode", className: "cs-b-mp-bolt", role: "img", title: "Fast mode", children: jsx(Codicon, { name: "zap", size: 11 }) }) : null,
          waiting ? jsx("span", { className: "cs-b-mp-next", title: `Switches when ${AGENT} finishes this turn`, children: "next message" }) : null,
          jsx(Codicon, { name: "chevron-down", size: 11 })
        ]
      }),
      open ? jsxs("div", {
        "aria-label": "Model and effort",
        className: `cs-b-mp-pop${up ? " up" : ""}${narrow ? " narrow" : ""}${tiny ? " tiny" : ""}`,
        role: "dialog",
        style: place ? { left: place.left, width: place.width } : void 0,
        children: [
          confirm ? jsxs("div", {
            className: "cs-b-mp-confirm",
            children: [
              jsx("span", { className: "cs-grow", children: confirm.message }),
              jsx(Button, { onClick: onConfirm, size: "sm", children: "Use it" }),
              jsx(Button, { onClick: onCancelConfirm, size: "sm", variant: "ghost", children: "Cancel" })
            ]
          }) : null,
          jsxs("div", {
            className: "cs-b-mp-body",
            children: [
              jsx(ProviderRail, {
                marks,
                onConnect: connectProvider(close),
                onTab: (key) => {
                  setTab(key);
                  setQuery("");
                },
                providers,
                tab: needle ? null : activeTab
              }),
              jsx(ModelList, {
                empty,
                groups,
                head,
                marks,
                onChoose: choose,
                onStar: (row) => toggleStar(starKey(row.provider, row.model)),
                placeholder: "Search models",
                query,
                search,
                setQuery,
                shown,
                stars,
                withProvider: !needle && activeTab === STARRED
              }),
              jsx(EffortColumn, { caps, disabled, narrow, onEffort, shown })
            ]
          }),
          jsx(SpeedBar, { disabled: disabled || Boolean(confirm), fast: shown.fast, held: waiting, narrow, onFast: (on) => onFast(on, { model: shown.model, provider: shown.provider }), onManage: connectProvider(close), speed })
        ]
      }) : null
    ]
  });
}
function ChatModelPicker({ ctx, stored, chat, disabled }) {
  const options = useModelOptions(chat?.runtime ?? null);
  return jsx(ModelPicker, {
    ctx,
    confirm: chat?.pickConfirm ?? null,
    disabled,
    // A model that asks first is not on its way until Use it: until then the panel keeps the model in use.
    pending: chat?.pickConfirm ? null : chat?.heldPick ?? null,
    waiting: Boolean(chat?.busy && chat?.heldPick),
    onCancelConfirm: () => cancelBuildPick(stored),
    onConfirm: () => void applyBuildPick(stored, { confirmed: true }),
    onEffort: (effort) => void pickBuildModel(stored, { effort }),
    onFast: (fast) => void pickBuildModel(stored, { fast }),
    // A model pick says whether that model has fast mode, so a Fast picked before it is applied is checked against it.
    onPick: (pick, row) => void pickBuildModel(stored, { ...pick, fastOk: hasFastMode(row.provider, row.caps) }),
    options,
    value: chat?.info ?? null
  });
}
function DraftModelPicker({ ctx, pick, onPick, options, up = true, disabled = false }) {
  return jsx(ModelPicker, {
    ctx,
    draft: true,
    disabled,
    up,
    onEffort: (effort) => onPick({ ...pick, effort }),
    onFast: (fast) => onPick({ ...pick, fast }),
    onPick: (choice) => onPick({ ...pick, ...choice }),
    options,
    value: pick
  });
}
function useDraftPick(ctx, needed) {
  const options = useModelOptions(null, needed);
  const [pick, setPick] = useState(() => {
    try {
      const saved = ctx.storage.get("buildModel", null);
      return saved && typeof saved === "object" ? saved : {};
    } catch {
      return {};
    }
  });
  const update = (next) => {
    setPick(next);
    try {
      ctx.storage.set("buildModel", next);
    } catch {
    }
  };
  const route = [pick, options.data].find((value) => value?.model && value?.provider && value.provider !== "auto");
  return [{ ...pick, model: route?.model, provider: route?.provider }, update, options];
}

// page/shared/ui/background.js
function backgroundOf(el, getStyle) {
  for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
    const css = getStyle(node).backgroundColor, nums = (css.match(/[\d.]+/g) || []).map(Number);
    const unit = css.startsWith("color(") ? 255 : 1;
    if (nums.length >= 3 && (nums.length < 4 || nums[3] > 0.5)) return { css, rgb: nums.slice(0, 3).map((v) => v * unit) };
  }
  return { css: "rgb(16 18 24)", rgb: [16, 18, 24] };
}

// page/shared/player/frame-values.js
var PNG = /^data:image\/png;base64,[A-Za-z0-9+/=]+$/;
var COLOR = /^#[0-9a-f]{6}$/i;
var MAX_MARKS = 20;
var MAX_IMAGE = 4e6;
var text = (value, max = 300) => typeof value === "string" ? value.slice(0, max) : "";
var cleanImage = (value) => typeof value === "string" && value.length <= MAX_IMAGE && PNG.test(value) ? value : "";
var cleanColors = (value) => Array.isArray(value) ? value.slice(0, 4).filter((color) => typeof color === "string" && COLOR.test(color)) : null;
function cleanMetadata(value) {
  if (!value || typeof value !== "object") {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value).slice(0, 12).map(([key, entry]) => [text(key, 40), Number.isFinite(entry) || typeof entry === "boolean" ? entry : text(entry, 600)])
  );
}
function cleanMark(mark, index) {
  const colors = cleanColors(mark?.colors);
  const original = cleanColors(mark?.original);
  return {
    n: Number.isInteger(mark?.n) && mark.n > 0 && mark.n <= MAX_MARKS ? mark.n : index + 1,
    id: text(mark?.id, 200),
    name: text(mark?.name, 120),
    role: text(mark?.role, 40),
    metadata: cleanMetadata(mark?.metadata),
    colors,
    original: colors && original?.length === colors.length ? original : colors,
    image: cleanImage(mark?.image)
  };
}
var cleanMarks = (value) => Array.isArray(value) ? value.slice(0, MAX_MARKS).map(cleanMark).filter((mark) => mark.id) : [];
function cleanNote(data) {
  return {
    target: { name: text(data?.target?.name, 120), role: text(data?.target?.role, 40), metadata: cleanMetadata(data?.target?.metadata) },
    note: text(data?.note, 2e3),
    image: cleanImage(data?.image)
  };
}

// page/shared/player/protocol.js
var TO_FRAME = "cmd";
var CMD = Object.freeze({
  KEY: "key",
  // { key, code, down }: a key the page caught while the game is armed
  SNAP: "snap",
  // { id }: answer FROM_FRAME.SNAP with the current frame as a PNG data URL
  HOLD: "hold",
  // pause the game and its sound while the surface is hidden
  RELEASE: "release",
  // undo HOLD
  THEME: "theme",
  // { css }: the app's colours: our overlay's accent, and the player page's background and text
  VIEW: "view",
  // { view }: one of VIEWS (inline UI only)
  PRESS: "press",
  // { action }: press one of the player's own buttons (PRESSABLE)
  FINISH: "finish",
  // { id }: show the handheld in this finish (a DEVICE_COLORS id)
  ANNOTATE: "annotate",
  // { on }: enter or leave annotate mode
  MARK_COLOR: "mark-color",
  // { id, index, value }: preview a colour on a marked object (value null resets it)
  MARK_REMOVE: "mark-remove",
  // { id }: drop one mark
  MARKS_TAKE: "marks-take"
  // { id }: answer FROM_FRAME.TAKEN with the marks and their close-ups, then leave annotate
});
var FROM_FRAME = Object.freeze({
  LOG: "log",
  // { level, text }
  FOCUS: "focus",
  // { value }: the frame's window gained or lost focus
  SNAP: "snap",
  // { id, url }
  NOTE: "annotate",
  // { target, note, image }: one object and a note, from the in-frame note card
  STATE: "state",
  // { ready, paused, muted, annotating, recording }
  MARKS: "marks",
  // { marks }: the marked objects while annotating (inline UI)
  TAKEN: "marks-taken"
  // { id, image, marks }: the marks with close-ups, answering MARKS_TAKE
});
var VIEWS = Object.freeze(["full", "screen", "device"]);
var PRESSABLE = Object.freeze(["play", "sound", "restart", "history", "screenshot", "record-video", "annotate"]);
var SCREEN_W = 160;
var SCREEN_H = 144;
var DEVICE_RATIO = 850 / 1440;
var DEVICE_SCREEN_SHARE = 0.621177;

// page/shared/player/bridge.js
var GAME_KEYS = /* @__PURE__ */ new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "z", "Z", "x", "X", "Enter", "Shift", "p", "P"]);
var TYPING = "input, textarea, select, [contenteditable]";
var CONTROL = "button, a[href], [role=button], [role=tab], [role=radio], [role=menuitem], [role=menuitemradio]";
var ARROW_GROUP = "[role=tab], [role=radio], [role=menuitem], [role=menuitemradio]";
var IDLE = Object.freeze({ ready: false, paused: false, muted: false, annotating: false, recording: false });
var REPLY_MS = 2500;
function appColours(frame) {
  const style = getComputedStyle(frame);
  return { accent: style.getPropertyValue("--ui-accent").trim() || "#3d7bff", background: backgroundOf(frame.parentElement, getComputedStyle).css, ink: style.color };
}
function themeCss({ accent, background, ink }) {
  return `:root{--hr-accent:${accent}}body.codex-game-view-mounted{--cgv-background:${background}!important;--cgv-ink:${ink}!important}`;
}
function keepsKey(event) {
  const target = event.target;
  if (typeof target?.closest !== "function") {
    return false;
  }
  if (target.closest(TYPING)) {
    return true;
  }
  return event.key === "Enter" ? Boolean(target.closest(CONTROL)) : event.key.startsWith("Arrow") && Boolean(target.closest(ARROW_GROUP));
}
function usePlayerBridge({ ctx, frameRef, visible, onAnnotate = null, scopeRef = null, frameKey = null }) {
  const [focused, setFocused] = useState(false);
  const [state, setState] = useState(IDLE);
  const [marks, setMarks] = useState([]);
  const replies = useRef(/* @__PURE__ */ new Map());
  const sequence = useRef(0);
  const latest = useRef({});
  const armed = useRef(!scopeRef);
  const held = useRef(/* @__PURE__ */ new Map());
  latest.current = { onAnnotate };
  const post = useCallback((message) => {
    try {
      frameRef.current?.contentWindow?.postMessage(message, "*");
    } catch {
    }
  }, []);
  const send = useCallback((type, payload = {}) => post({ cs: TO_FRAME, ...payload, type }), []);
  const painted = useRef("");
  const paint = useCallback((changedOnly) => {
    const css = frameRef.current ? themeCss(appColours(frameRef.current)) : "";
    if (css && !(changedOnly && css === painted.current)) {
      painted.current = css;
      send(CMD.THEME, { css });
    }
  }, []);
  const releaseKeys = useCallback(() => {
    for (const [key, code] of held.current) {
      send(CMD.KEY, { key, code, down: false });
    }
    held.current.clear();
  }, []);
  useEffect(() => {
    setState(IDLE);
    setMarks([]);
    held.current.clear();
  }, [frameKey]);
  useEffect(() => {
    if (!scopeRef) {
      return void 0;
    }
    const arm = (event) => {
      armed.current = Boolean(scopeRef.current && event.target && scopeRef.current.contains(event.target));
      if (!armed.current) {
        releaseKeys();
      }
    };
    window.addEventListener("pointerdown", arm, true);
    window.addEventListener("focusin", arm, true);
    return () => {
      window.removeEventListener("pointerdown", arm, true);
      window.removeEventListener("focusin", arm, true);
    };
  }, []);
  const ask = useCallback(
    (type, fallback, wait = REPLY_MS) => new Promise((resolve) => {
      const id = ++sequence.current;
      replies.current.set(id, resolve);
      send(type, { id });
      ctx.setTimeout(() => {
        if (replies.current.has(id)) {
          replies.current.delete(id);
          resolve(fallback);
        }
      }, wait);
    }),
    []
  );
  useEffect(() => {
    const answer = (id, value) => {
      const resolve = replies.current.get(id);
      if (resolve) {
        replies.current.delete(id);
        resolve(value);
      }
    };
    const handlers = {
      [FROM_FRAME.FOCUS]: (data) => setFocused(Boolean(data.value)),
      [FROM_FRAME.SNAP]: (data) => answer(data.id, cleanImage(data.url)),
      [FROM_FRAME.STATE]: (data) => {
        paint(false);
        setState({ ready: true, paused: Boolean(data.paused), muted: Boolean(data.muted), annotating: Boolean(data.annotating), recording: Boolean(data.recording) });
      },
      [FROM_FRAME.MARKS]: (data) => setMarks(cleanMarks(data.marks)),
      [FROM_FRAME.TAKEN]: (data) => answer(data.id, { image: cleanImage(data.image), marks: cleanMarks(data.marks) }),
      [FROM_FRAME.NOTE]: (data) => void latest.current.onAnnotate?.(cleanNote(data)),
      [FROM_FRAME.LOG]: (data) => data.level === "error" && console.warn("[Chromatic player]", String(data.text ?? "").slice(0, 500))
    };
    const onMessage = (event) => {
      const frame = frameRef.current;
      const data = event.data;
      if (frame && event.source === frame.contentWindow && data && typeof data === "object") {
        handlers[data.cs]?.(data);
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);
  useEffect(() => {
    if (!visible) {
      return void 0;
    }
    const forward = (event) => {
      const down = event.type === "keydown";
      if (!down && held.current.has(event.key)) {
        held.current.delete(event.key);
        send(CMD.KEY, { key: event.key, code: event.code, down: false });
        return;
      }
      if (!GAME_KEYS.has(event.key) || event.metaKey || event.ctrlKey || event.altKey || !frameRef.current || !armed.current || keepsKey(event)) {
        return;
      }
      event.preventDefault();
      if (!event.repeat) {
        if (down) {
          held.current.set(event.key, event.code);
        }
        send(CMD.KEY, { key: event.key, code: event.code, down });
      }
    };
    window.addEventListener("keydown", forward);
    window.addEventListener("keyup", forward);
    window.addEventListener("blur", releaseKeys);
    return () => {
      window.removeEventListener("keydown", forward);
      window.removeEventListener("keyup", forward);
      window.removeEventListener("blur", releaseKeys);
      releaseKeys();
    };
  }, [visible]);
  useEffect(() => {
    if (typeof MutationObserver !== "function") {
      return void 0;
    }
    const observer = new MutationObserver(() => paint(true));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style", "data-hermes-mode", "data-hermes-theme"] });
    return () => observer.disconnect();
  }, []);
  const shown = useRef(visible);
  useEffect(() => {
    if (shown.current !== visible) {
      shown.current = visible;
      send(visible ? CMD.RELEASE : CMD.HOLD);
    }
  }, [visible]);
  const press = useCallback((action) => send(CMD.PRESS, { action }), []);
  const snap = useCallback(() => ask(CMD.SNAP, ""), []);
  const takeMarks = useCallback(() => ask(CMD.MARKS_TAKE, null, 1e4), []);
  return { focused, frame: { ...state, press }, marks, snap, send, press, takeMarks };
}

// page/shared/player/live.js
var LIVE_PLAYER = atom(null);
var claimLive = (surface) => {
  if (LIVE_PLAYER.get() !== surface) {
    LIVE_PLAYER.set(surface);
  }
};
var releaseLive = (surface) => {
  if (LIVE_PLAYER.get() === surface) {
    LIVE_PLAYER.set(null);
  }
};

// page/app/chat-insert.js
async function insertText(target, text2) {
  try {
    return await host.composer.insertText(target, text2, { mode: "block" }) === true;
  } catch {
    return false;
  }
}
async function insertWhenMounted(ctx, target, text2) {
  const sleep = (ms) => new Promise((resolve) => ctx.setTimeout(resolve, ms));
  for (const delay of [150, 250, 400, 600, 900]) {
    await sleep(delay);
    if (await insertText(target, text2)) {
      return true;
    }
  }
  return false;
}
var promptAdded = () => host.notify({ kind: "success", message: "Prompt added to the composer" });
async function sendPromptToChat(ctx, prompt, { fresh = false } = {}) {
  const target = studioTarget();
  if (!target) {
    const copied2 = await ctx.os.writeClipboard(prompt).catch(() => false);
    host.notify({
      kind: "warning",
      message: `The hermretro profile is not set up yet, so no chat can use this prompt. Create it on Setup (Profile step), then ask Hermes there${copied2 ? "; the prompt is copied" : ""}.`
    });
    return;
  }
  const profile = target.profile;
  if (!profile && !fresh) {
    if (await insertText(null, prompt)) {
      promptAdded();
      return;
    }
    const focused = host.state.focusedSessionId.get();
    if (focused && await insertText(focused, prompt)) {
      promptAdded();
      return;
    }
  }
  if (typeof host.newChat === "function") {
    try {
      profile ? host.newChat(profile) : host.newChat();
      if (await insertWhenMounted(ctx, "new", prompt)) {
        promptAdded();
        return;
      }
    } catch {
    }
  }
  const copied = await ctx.os.writeClipboard(prompt).catch(() => false);
  host.notify(
    copied ? { kind: "info", message: "Prompt copied — paste it into a chat to use it." } : { kind: "warning", message: "Could not reach a chat composer or the clipboard. Copy the prompt from the page." }
  );
}
function gameConversation(game) {
  const session = game?.session;
  if (session?.storedId && session.thisProfile !== false && session.exists !== false) {
    return { stored: session.storedId, profile: session.profileName ?? null };
  }
  return game?.chat?.sessionId ? { stored: game.chat.sessionId, profile: game.chat.profile ?? null } : null;
}
async function openGameChat(game) {
  const conversation = gameConversation(game);
  const target = studioTarget();
  const inStudio = conversation?.profile ? conversation.profile === STUDIO_PROFILE : true;
  const stored = conversation?.stored;
  if (!stored || !target || !inStudio || typeof host.openSession !== "function") {
    return null;
  }
  try {
    await host.openSession(stored, target.profile ? { profile: target.profile } : {});
    return stored;
  } catch {
    return null;
  }
}
async function sendToGameChat(ctx, game, text2) {
  const stored = await openGameChat(game);
  if (stored && await insertWhenMounted(ctx, stored, text2)) {
    promptAdded();
    return;
  }
  await sendPromptToChat(ctx, text2, { fresh: true });
}

// page/app/game-prompts.js
var gameLabel = (game) => `"${game.title}"${game.projectRoot ? ` (${game.projectRoot})` : ""}`;
function buildPrompt(game) {
  return `Build ${gameLabel(game)} and its playable web player, so I can play it on the Emulator page of hermretro.`;
}

// page/shared/ui/links.js
var LINKS = {
  node: "https://nodejs.org/",
  firmware: "https://support.modretro.com/en_us/articles/chromatic-firmware-updater-ryhoYnzCx",
  quickstart: "https://support.modretro.com/en_us/chromatic-codex-edition-quickstart-guide-By1iOlcMg",
  releases: "https://github.com/ThePickle31/hermretro/releases"
};
function ExternalLink({ ctx, href, children, variant = "link" }) {
  return jsxs(Button, {
    onClick: () => void ctx.os.openExternal(href),
    size: variant === "link" ? "inline" : "sm",
    variant,
    children: [children, jsx(Codicon, { name: "link-external", size: 12 })]
  });
}
function CommandLine({ command }) {
  return jsxs("div", {
    style: { ...S.row, gap: 4 },
    children: [
      jsx("code", { className: "font-mono", style: S.code, children: command }),
      jsx(CopyButton, { appearance: "icon", label: "Copy command", text: command })
    ]
  });
}

// page/shared/ui/text.js
function Lede({ children }) {
  return jsx("p", { className: "cs-lede", children });
}
function Small({ children, tone }) {
  return jsx("p", { className: tone === "warn" ? "cs-small cs-warn" : "cs-small", children });
}
function Facts({ rows }) {
  return jsx("dl", {
    className: "cs-facts",
    children: rows.flatMap(([term, text2]) => [jsx("dt", { children: term }, `t-${term}`), jsx("dd", { children: text2 }, `d-${term}`)])
  });
}

// page/shared/ui/page.js
function Footer({ ctx }) {
  return jsxs("footer", {
    className: "cs-foot",
    children: [
      jsxs("div", {
        className: "cs-row",
        style: { gap: 16 },
        children: [
          jsx(ExternalLink, { ctx, href: LINKS.quickstart, children: "ModRetro Chromatic quickstart" })
        ]
      }),
      jsx("p", {
        className: "cs-faint",
        children: "For original, user-created ROMs only. Do not use it for piracy or commercial games. Developer Mode is at your own risk. hermretro is an independent plugin and is not made or endorsed by ModRetro."
      })
    ]
  });
}
function PageHead({ number, label, title, lede, children }) {
  return jsxs("div", {
    className: "cs-page-head",
    children: [
      jsxs("div", {
        className: "cs-col",
        children: [
          label ? jsxs("p", { className: "cs-eyebrow", children: [jsx("span", { className: "cs-accent", children: number }), label] }) : null,
          jsx("h2", { className: "cs-word cs-title", children: title }),
          lede ? jsx(Lede, { children: lede }) : null
        ]
      }),
      children ? jsx("div", { className: "cs-row", children }) : null
    ]
  });
}
function AsyncButton({ run, disabled, icon, title, variant = "outline", children }) {
  const [pending, setPending] = useState(false);
  return jsx(Tip, {
    label: title ?? children,
    children: jsx("span", {
      style: { display: "inline-flex" },
      children: jsxs(Button, {
        disabled: disabled || pending,
        onClick: async () => {
          setPending(true);
          try {
            await run();
          } finally {
            setPending(false);
          }
        },
        size: "sm",
        variant,
        "aria-label": icon && typeof children === "string" ? children : void 0,
        children: [icon ? jsx(Codicon, { name: pending ? "loading" : icon, size: 14, spinning: pending }) : null, icon ? jsx("span", { className: "cs-lbl", children }) : children]
      })
    })
  });
}

// page/shared/ui/working.js
var LEMNISCATE = "M0 0C.35-.6 1.15-.6 1.15 0S.35.6 0 0-1.15-.6-1.15 0-.35.6 0 0Z";
function Working({ children, quiet = false }) {
  return jsxs("div", {
    className: quiet ? "cs-watch quiet" : "cs-watch",
    role: "status",
    children: [
      jsxs("svg", {
        "aria-hidden": true,
        className: "cs-lem",
        viewBox: "-1.25 -0.62 2.5 1.24",
        children: [
          jsx("path", { className: "track", d: LEMNISCATE, pathLength: 100 }),
          jsx("path", { className: "run", d: LEMNISCATE, pathLength: 100 })
        ]
      }),
      jsx("span", { children })
    ]
  });
}

// page/app/player/stage.js
function playableSha(game) {
  return game?.web?.sha256 ?? game?.rom?.sha256 ?? null;
}
function playerFailure(game, player) {
  if (player?.isError) {
    return describeRequestError(player.error).notLoaded ? "This profile is running an older copy of the hermretro backend. Reload the plugin (Capabilities › Plugins, switch it off and on) and press Refresh." : studioError(player.error, "run the player");
  }
  return game?.id === DEMO_ID && player?.data?.error ? String(player.data.error) : null;
}
function PlayerNotice({ game, player, onRefresh, refreshing }) {
  const reason = playerFailure(game, player);
  if (!reason) {
    return null;
  }
  return jsxs("div", {
    className: "cs-rp-note",
    role: "alert",
    children: [
      jsxs("div", { children: [jsx("b", { children: "The player could not start" }), jsx("span", { children: reason })] }),
      jsxs(Button, { disabled: refreshing, onClick: onRefresh, size: "sm", variant: "outline", children: [jsx(Codicon, { name: "refresh", size: 14 }), "Refresh"] })
    ]
  });
}
function PlayerStage({ game, player, visible, frameRef, stageRef, frameKey, onLoad, ctx, query = "" }) {
  let inner = null;
  if (game) {
    const data = player?.data;
    if (playerFailure(game, player)) {
      inner = jsx("div", { "aria-hidden": true, className: "cs-rp-void" });
    } else if (data?.error) {
      inner = jsxs("div", {
        className: "cs-rp-msg",
        children: [
          jsx("p", { className: "cs-eyebrow", children: "The player could not start" }),
          jsx(Lede, { children: data.error }),
          jsx(AsyncButton, { icon: "comment-discussion", run: () => sendToGameChat(ctx, game, buildPrompt(game)), variant: "default", children: "Build it in chat" })
        ]
      });
    } else if (data?.url) {
      inner = jsx(
        SandboxedFrame,
        { onLoad, ref: frameRef, sandbox: "allow-scripts allow-downloads", src: query ? `${data.url}?${query}` : data.url, title: `${game.title} in ModRetro's Chromatic player` },
        frameKey
      );
    } else {
      inner = jsx("div", { className: "cs-rp-msg", children: jsx(Working, { children: `Starting the player for ${game.title}…` }) });
    }
  } else {
    inner = jsx("div", { className: "cs-rp-msg", children: jsx(Working, { quiet: true, children: "Reading your games…" }) });
  }
  return jsx("div", { "aria-hidden": visible ? void 0 : true, className: visible ? "cs-rp-stage" : "cs-rp-stage off", ref: stageRef, children: inner });
}
function PlayerAway({ where, onBring }) {
  return jsx("div", {
    className: "cs-rp-stage",
    children: jsxs("div", {
      className: "cs-rp-msg cs-rp-away",
      children: [
        jsx("p", { className: "cs-eyebrow", children: where }),
        jsx(Lede, { children: "The game runs in one place at a time. Bringing it here starts it again from the title screen." }),
        jsxs(Button, { onClick: onBring, size: "sm", variant: "default", children: [jsx(Codicon, { name: "arrow-swap", size: 14 }), "Bring it here"] })
      ]
    })
  });
}

// page/shared/player/targets.js
var KIND_WORDS = { sprite: "Sprite", background: "Background tile", window: "Window tile", frame: "Whole screen" };
function targetKind(role) {
  return String(role ?? "").replace(/^game-/, "") || "frame";
}
function targetLabel(name, role) {
  const kind = targetKind(role);
  const group = /group;\s*(\d+)\s*parts/i.exec(String(name ?? ""));
  if (kind === "sprite") {
    return group ? `Sprite · ${group[1]} parts` : "Sprite part";
  }
  return KIND_WORDS[kind] ?? "Part of the screen";
}
function targetRect(metadata) {
  const found = /^(-?\d+),(-?\d+)\s+(\d+)x(\d+)px/.exec(String(metadata?.Hardware ?? ""));
  return found ? { x: Number(found[1]), y: Number(found[2]), w: Number(found[3]), h: Number(found[4]) } : null;
}

// page/app/player/capture.js
async function saveCapture(game, png) {
  if (!png) {
    return { path: null, failure: "the frame could not be captured" };
  }
  try {
    const result = await callStudio(RPC_CAPTURE_IMAGE, { id: game.id, png });
    return result?.path ? { path: result.path, failure: null } : { path: null, failure: result?.error || "no path returned" };
  } catch (error) {
    return { path: null, failure: studioError(error, "save screenshots") };
  }
}
function annotationText(game, data, path) {
  const target = data.target ?? {};
  const role = String(target.role ?? "").replace(/^game-/, "");
  const lines = [`In ${game.title}, I marked ${target.name || "part of the screen"}${role ? ` (${role})` : ""}.`];
  if (data.note) {
    lines.push(String(data.note));
  }
  if (target.metadata && typeof target.metadata === "object" && Object.keys(target.metadata).length) {
    lines.push(`Details: ${JSON.stringify(target.metadata).slice(0, 800)}`);
  }
  if (path) {
    lines.push(`Screenshot: ${path}`);
  }
  return lines.join("\n");
}
async function annotateGame(ctx, game, data) {
  if (!game) {
    return;
  }
  const { path, failure } = await saveCapture(game, typeof data.image === "string" ? data.image : "");
  await sendToGameChat(ctx, game, annotationText(game, data, path));
  if (failure) {
    host.notify({ kind: "warning", message: `The screenshot was not saved: ${failure}` });
  }
}
async function askAboutGame(ctx, game, snap) {
  if (!game) {
    return;
  }
  const { path, failure } = await saveCapture(game, await snap());
  await sendToGameChat(ctx, game, [`Here is what ${game.title} shows right now.`, path ? `Screenshot: ${path}` : null].filter(Boolean).join("\n") + "\n");
  if (failure) {
    host.notify({ kind: "warning", message: `The screenshot was not saved: ${failure}` });
  }
}

// page/pages/build/player/annotate.js
function useAnnotate(bridge) {
  const [notes, setNotes] = useState({});
  const active = bridge.frame.annotating;
  useEffect(() => {
    if (!active) {
      setNotes({});
    }
  }, [active]);
  return {
    active,
    marks: active ? bridge.marks : [],
    notes,
    setNote: useCallback((id, text2) => setNotes((current) => ({ ...current, [id]: text2 })), []),
    start: () => bridge.send(CMD.ANNOTATE, { on: true }),
    cancel: () => bridge.send(CMD.ANNOTATE, { on: false }),
    setColor: (id, index, value) => bridge.send(CMD.MARK_COLOR, { id, index, value }),
    remove: (id) => bridge.send(CMD.MARK_REMOVE, { id })
  };
}
function markPosition(metadata) {
  const rect = targetRect(metadata);
  return rect ? `at ${rect.x}, ${rect.y} · ${rect.w} × ${rect.h}` : "";
}
function markDetail(mark, framePath, build) {
  const changed2 = (mark.colors ?? []).some((color, index) => color !== mark.original?.[index]);
  const parts = [
    `Marked ${mark.n}: ${mark.name} (${targetKind(mark.role)})${framePath ? ` on the frame ${framePath}` : ""}${build ? `, build #${build}` : ""}.`,
    mark.metadata?.Hardware ? `Hardware: ${mark.metadata.Hardware}.` : null,
    mark.metadata?.Build ? `${mark.metadata.Build}.` : null,
    changed2 ? `The user previewed new colours for it: ${mark.original.join(" ")} → ${mark.colors.join(" ")}.` : null
  ];
  return parts.filter(Boolean).join(" ");
}
async function sendMarks({ bridge, game, stored, build, notes }) {
  const taken = await bridge.takeMarks();
  if (!taken) {
    host.notify({ kind: "warning", message: "The game did not hand over the marks in time. Mark them again, then Add to message." });
    return;
  }
  if (!taken.marks.length) {
    return;
  }
  const { path, failure } = await saveCapture(game, taken.image);
  const take = path || String(Date.now());
  const attachments = taken.marks.map((mark) => ({
    key: `mark:${take}:${mark.n}`,
    path: path ?? "",
    name: `${mark.n} · ${targetLabel(mark.name, mark.role)}`,
    image: mark.image,
    detail: markDetail(mark, path, build)
  }));
  const text2 = taken.marks.map((mark) => `${mark.n}. ${(notes[mark.id] ?? "").trim()}`).join("\n");
  attachToBuild(stored, attachments, text2);
  if (failure) {
    host.notify({ kind: "warning", message: `The frame was not saved: ${failure}` });
  }
}

// page/pages/build/player/arrow-keys.js
var NEXT = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
function moveFocus(event, container, selector) {
  const items = [...container?.querySelectorAll(selector) ?? []].filter((item) => !item.disabled);
  const at = items.indexOf(event.target);
  const target = event.key === "Home" ? items[0] : event.key === "End" ? items.at(-1) : NEXT[event.key] && items.length ? items[(at + NEXT[event.key] + items.length) % items.length] : null;
  if (!target) {
    return null;
  }
  event.preventDefault();
  target.focus();
  return target;
}

// page/pages/build/player/menu.js
var ITEM = "[role^=menuitem]";
function BarMenu({ label, icon, text: text2 = null, items, onPick, disabled = false }) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  const trigger = useRef(null);
  const close = (refocus = true) => {
    setOpen(false);
    if (refocus) {
      trigger.current?.focus();
    }
  };
  useEffect(() => {
    if (!open) {
      return void 0;
    }
    const away = (event) => {
      if (!root.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    const escape = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close();
      }
    };
    root.current?.querySelector(ITEM)?.focus();
    window.addEventListener("pointerdown", away, true);
    window.addEventListener("keydown", escape, true);
    return () => {
      window.removeEventListener("pointerdown", away, true);
      window.removeEventListener("keydown", escape, true);
    };
  }, [open]);
  return jsxs("span", {
    className: "cs-ip-menu",
    ref: root,
    children: [
      jsxs("button", {
        "aria-expanded": open,
        "aria-haspopup": "menu",
        "aria-label": label,
        className: "cs-ip-btn",
        disabled,
        onClick: () => setOpen(!open),
        ref: trigger,
        title: label,
        type: "button",
        children: [jsx(Codicon, { name: icon, size: 14 }), text2 ? jsx("span", { className: "cs-ip-lbl", children: text2 }) : null]
      }),
      open ? jsx("div", {
        className: "cs-ip-pop",
        onKeyDown: (event) => event.key === "Tab" ? close(false) : moveFocus(event, event.currentTarget, ITEM),
        role: "menu",
        children: items.map(
          (item) => jsxs(
            "button",
            {
              "aria-checked": item.checked ?? void 0,
              className: "cs-ip-pop-row",
              disabled: item.disabled,
              onClick: () => {
                close();
                onPick(item.id);
              },
              role: item.checked === void 0 ? "menuitem" : "menuitemradio",
              type: "button",
              children: [
                item.swatch ? jsx("i", { className: "cs-ip-swatch", style: { background: item.swatch } }) : item.icon ? jsx(Codicon, { name: item.icon, size: 13 }) : null,
                jsx("span", { children: item.label }),
                item.checked ? jsx(Codicon, { name: "check", size: 12 }) : null
              ]
            },
            item.id
          )
        )
      }) : null
    ]
  });
}

// page/pages/build/player/scale.js
var SCALES = Object.freeze(["fit", 2, 3, 4]);
var screenAt = (step) => ({ width: SCREEN_W * step, height: SCREEN_H * step });
var deviceAt = (step) => {
  const width = SCREEN_W * step / DEVICE_SCREEN_SHARE;
  return { width, height: width / DEVICE_RATIO };
};
function largestStep(sizeAt, box) {
  let step = 1;
  while (step < 12) {
    const next = sizeAt(step + 1);
    if (next.width > box.width || next.height > box.height) {
      break;
    }
    step += 1;
  }
  return step;
}
function playerSize(view, scale, box) {
  const sizeAt = view === "device" ? deviceAt : screenAt;
  const most = largestStep(sizeAt, box);
  const step = scale === "fit" || view === "device" ? most : Math.min(Number(scale) || most, most);
  return { ...sizeAt(step), step, fits: SCALES.filter((entry) => entry === "fit" || entry <= most) };
}

// page/pages/build/player/control-bar.js
var scaleLabel = (scale) => scale === "fit" ? "Fit" : `${scale}×`;
function BarButton({ icon, label, text: text2 = null, onClick, pressed, disabled = false, primary = false }) {
  return jsxs("button", {
    "aria-label": label,
    "aria-pressed": pressed,
    className: `cs-ip-btn${primary ? " primary" : ""}`,
    disabled,
    onClick,
    title: label,
    type: "button",
    children: [jsx(Codicon, { name: icon, size: 14 }), text2 ? jsx("span", { className: "cs-ip-lbl", children: text2 }) : null]
  });
}
function ScalePicker({ scale, fits, onScale }) {
  const pick = (event) => {
    const target = moveFocus(event, event.currentTarget, "[role=radio]");
    if (target) {
      onScale(SCALES[Number(target.dataset.index)]);
    }
  };
  return jsx("span", {
    "aria-label": "Size",
    className: "cs-ip-seg",
    onKeyDown: pick,
    role: "radiogroup",
    children: SCALES.map(
      (entry, index) => jsx(
        "button",
        {
          "aria-checked": entry === scale,
          "data-index": index,
          disabled: !fits.includes(entry),
          onClick: () => onScale(entry),
          role: "radio",
          tabIndex: entry === scale ? 0 : -1,
          title: entry === "fit" ? "As big as fits, in whole steps" : `${entry} times the Game Boy screen`,
          type: "button",
          children: scaleLabel(entry)
        },
        String(entry)
      )
    )
  });
}
function ControlBar({ title, hint, prefs, setPrefs, skins, finish, fits, frame, ready, panelToggle, onAnnotate, onShot, onMore, onFull, onClose }) {
  const skin = skins.find((entry) => entry.id === finish);
  return jsxs("div", {
    className: "cs-ip-bar",
    children: [
      jsx("span", { className: ready && !frame.paused ? "cs-b-live on" : "cs-b-live" }),
      jsx("b", { className: "cs-ip-title", children: `Playing ${title}` }),
      jsx("span", { className: "cs-faint cs-ip-hint", children: hint }),
      jsx("span", { className: "cs-grow" }),
      prefs.view === "device" ? skin ? jsx(BarMenu, {
        icon: "symbol-color",
        items: skins.map((entry) => ({ id: entry.id, label: entry.name, swatch: entry.swatch, checked: entry.id === skin.id })),
        label: "Chromatic finish",
        onPick: (id) => setPrefs({ finish: id }),
        text: skin.name
      }) : null : jsx(ScalePicker, { fits, onScale: (scale) => setPrefs({ scale }), scale: prefs.scale }),
      jsx(BarButton, { icon: "device-mobile", label: "Show the Chromatic around the game", onClick: () => setPrefs({ view: prefs.view === "device" ? "screen" : "device" }), pressed: prefs.view === "device", text: "Chromatic" }),
      panelToggle,
      jsx("span", { className: "cs-ip-sep" }),
      jsx(BarButton, { disabled: !ready, icon: "inspect", label: `Annotate: point at things in the game for ${AGENT}`, onClick: onAnnotate, text: "Annotate" }),
      jsx(BarButton, { disabled: !ready, icon: frame.muted ? "mute" : "unmute", label: frame.muted ? "Turn the sound on" : "Mute", onClick: () => frame.press("sound") }),
      jsx(BarButton, { disabled: !ready, icon: frame.paused ? "play" : "debug-pause", label: frame.paused ? "Resume" : "Pause", onClick: () => frame.press("play") }),
      jsx(BarButton, { disabled: !ready, icon: "device-camera", label: "Screenshot into the game's captures", onClick: onShot }),
      jsx(BarMenu, {
        disabled: !ready,
        icon: "ellipsis",
        items: [
          { id: "restart", icon: "debug-restart", label: "Restart the game" },
          { id: "record", icon: frame.recording ? "debug-stop" : "record", label: frame.recording ? "Stop recording" : "Record a video" }
        ],
        label: "More",
        onPick: onMore
      }),
      jsx(BarButton, { disabled: !ready, icon: "screen-full", label: "Full screen", onClick: onFull }),
      jsx(BarButton, { icon: "close", label: "Close the game", onClick: onClose })
    ]
  });
}

// page/pages/build/player/annotate-panel.js
function AnnotateBar({ title, count, busy, onCancel, onDone }) {
  return jsxs("div", {
    className: "cs-ip-bar annotating",
    children: [
      jsx("span", { className: "cs-ip-ann-ic", children: jsx(Codicon, { name: "inspect", size: 14 }) }),
      jsx("b", { className: "cs-ip-title", children: `Annotating ${title}` }),
      jsx("span", { className: count ? "cs-ip-hint marked" : "cs-faint cs-ip-hint", children: count ? `${count} marked` : "click a sprite or tile · Esc to finish" }),
      jsx("span", { className: "cs-grow" }),
      jsx(BarButton, { icon: "close", label: "Cancel and let the game run", onClick: onCancel, text: "Cancel" }),
      jsx(BarButton, { disabled: !count || busy, icon: "arrow-right", label: "Add the marks to your message", onClick: onDone, primary: true, text: "Add to message" })
    ]
  });
}
function Colors({ mark, onColor }) {
  const pending = useRef(null);
  const preview = (index, value) => {
    const first = pending.current === null;
    pending.current = { index, value };
    if (first) {
      requestAnimationFrame(() => {
        const { index: at, value: color } = pending.current;
        pending.current = null;
        onColor(mark.id, at, color);
      });
    }
  };
  const changed2 = (mark.colors ?? []).some((color, index) => color !== mark.original?.[index]);
  return jsxs("div", {
    className: "cs-ip-colors",
    children: [
      ...(mark.colors ?? []).map(
        (color, index) => jsxs(
          "label",
          {
            className: color !== mark.original?.[index] ? "cs-ip-swatch-in changed" : "cs-ip-swatch-in",
            title: `Colour ${index + 1}: ${color}`,
            children: [jsx("i", { style: { background: color } }), jsx("input", { "aria-label": `Colour ${index + 1}`, onChange: (event) => preview(index, event.target.value), type: "color", value: color })]
          },
          index
        )
      ),
      changed2 ? jsx("button", {
        className: "cs-b-link",
        onClick: () => mark.colors.forEach((color, index) => color !== mark.original[index] && onColor(mark.id, index, null)),
        type: "button",
        children: "Reset"
      }) : null
    ]
  });
}
function MarkCard({ mark, note, onNote, onColor, onRemove }) {
  return jsxs("li", {
    className: "cs-ip-mark",
    children: [
      jsxs("div", {
        className: "cs-ip-mark-head",
        children: [
          jsx("span", { className: "cs-ip-n", children: mark.n }),
          mark.image ? jsx("img", { alt: "", className: "cs-ip-crop", src: mark.image }) : null,
          jsxs("div", { className: "cs-ip-mark-name", children: [jsx("b", { children: targetLabel(mark.name, mark.role) }), jsx("span", { className: "cs-faint", children: markPosition(mark.metadata) })] }),
          jsx("button", { "aria-label": `Remove mark ${mark.n}`, className: "cs-b-x", onClick: () => onRemove(mark.id), type: "button", children: jsx(Codicon, { name: "close", size: 12 }) })
        ]
      }),
      mark.colors?.length ? jsx(Colors, { mark, onColor }) : null,
      jsx("textarea", {
        "aria-label": `What should change about mark ${mark.n}`,
        className: "cs-ip-mark-note",
        onChange: (event) => onNote(mark.id, event.target.value),
        // Keys typed here are the note's, not the game's.
        onKeyDown: (event) => event.stopPropagation(),
        placeholder: "What should change here?",
        rows: 2,
        value: note ?? ""
      })
    ]
  });
}
function AnnotatePanel({ layout, annotate }) {
  return jsxs("aside", {
    "aria-label": "Marked in the game",
    className: layout === "side" ? "cs-ip-panel" : "cs-ip-panel tabs",
    children: [
      jsx("div", { className: "cs-ip-sh", children: jsx("span", { children: annotate.marks.length ? `Marked ${annotate.marks.length}` : "Annotate" }) }),
      annotate.marks.length ? jsx("ol", {
        className: "cs-ip-marks",
        children: annotate.marks.map(
          (mark) => jsx(MarkCard, { mark, note: annotate.notes[mark.id], onColor: annotate.setColor, onNote: annotate.setNote, onRemove: annotate.remove }, mark.id)
        )
      }) : jsx("p", { className: "cs-ip-note", children: `The game is frozen. Click a sprite or a tile to mark it; each one gets a number and a note for ${AGENT}. Change its colours here to try them on the frozen frame.` })
    ]
  });
}

// page/pages/build/player/playtest-panel.js
var KEYS = [
  ["← ↑ ↓ →", "move"],
  ["Z", "A"],
  ["X", "B"],
  ["Enter", "Start"],
  ["Shift", "Select"]
];
function KeyHints({ className = "cs-ip-keys" }) {
  return jsx("div", {
    className,
    children: KEYS.map(([key, word]) => jsxs("span", { children: [jsx("kbd", { children: key }), ` ${word}`] }, word))
  });
}
var STATE_NOTE = {
  untested: `${AGENT} didn’t test this`,
  reported: `Reported · ${AGENT} is on it`
};
function CheckItem({ item, build, asking, onToggle, onWorked, onWrong }) {
  const note = item.state === "fixed" ? `Fixed in #${build} · check it again` : STATE_NOTE[item.state];
  return jsxs("li", {
    className: "cs-ip-check",
    "data-state": item.state,
    children: [
      jsxs("label", {
        children: [
          jsx("input", { checked: item.state === "done", disabled: item.state === "reported", onChange: (event) => onToggle(item, event.target.checked), type: "checkbox" }),
          jsxs("span", { children: [jsx("span", { className: "cs-ip-check-text", children: item.text }), note ? jsx("em", { children: note }) : null] })
        ]
      }),
      asking ? jsxs("div", {
        className: "cs-ip-ask",
        role: "group",
        "aria-label": `What happened with ${item.text}`,
        children: [
          jsx("span", { children: "What happened?" }),
          jsxs("div", {
            className: "cs-row",
            children: [
              jsx(BarButton, { icon: "check", label: "It worked", onClick: () => onWorked(item), text: "It worked" }),
              jsx(BarButton, { icon: "comment-discussion", label: `Something's wrong: tell ${AGENT}`, onClick: () => onWrong(item), primary: true, text: "Something’s wrong" })
            ]
          })
        ]
      }) : null
    ]
  });
}
function Checklist({ playtest, build, onWrong }) {
  const [asking, setAsking] = useState(null);
  const toggle = (item, on) => {
    if (on && (item.state === "untested" || item.state === "fixed")) {
      setAsking(asking === item.key ? null : item.key);
    } else {
      playtest.tick(item.key, on);
    }
  };
  return jsx("ul", {
    className: "cs-ip-checks",
    children: playtest.items.map(
      (item) => jsx(
        CheckItem,
        {
          asking: asking === item.key,
          build,
          item,
          onToggle: toggle,
          onWorked: (entry) => {
            setAsking(null);
            playtest.tick(entry.key, true);
          },
          onWrong: (entry) => {
            setAsking(null);
            onWrong(entry);
          }
        },
        item.key
      )
    )
  });
}
function Moment({ ready, onAsk, onAnnotate, onShot }) {
  return jsxs("div", {
    className: "cs-row cs-ip-moment",
    children: [
      jsx(BarButton, { disabled: !ready, icon: "comment-discussion", label: `Ask ${AGENT} about what the game shows now`, onClick: onAsk, primary: true, text: `Ask ${AGENT}` }),
      jsx(BarButton, { disabled: !ready, icon: "inspect", label: "Annotate", onClick: onAnnotate, text: "Annotate" }),
      jsx(BarButton, { disabled: !ready, icon: "device-camera", label: "Screenshot", onClick: onShot })
    ]
  });
}
var Heading = ({ children, extra = null }) => jsxs("div", { className: "cs-ip-sh", children: [jsx("span", { children }), extra] });
function PlaytestPanel({ layout, note, playtest, build, ready, onWrong, onAsk, onAnnotate, onShot }) {
  const [tab, setTab] = useState(playtest.items.length ? "try" : note ? "note" : "controls");
  const ids = useId();
  const { done, total } = playtest.counts;
  const sections = {
    note: note ? jsxs("div", { className: "cs-ip-sec", children: [layout === "side" ? jsx(Heading, { children: `${AGENT}’s note` }) : null, jsx("p", { className: "cs-ip-note", children: note })] }) : null,
    try: total ? jsxs("div", {
      className: "cs-ip-sec",
      children: [
        layout === "side" ? jsx(Heading, { extra: jsx("b", { className: "cs-ip-count", children: `${done}/${total}` }), children: "Try this" }) : null,
        jsx(Checklist, { build, onWrong, playtest })
      ]
    }) : null,
    controls: jsxs("div", { className: "cs-ip-sec", children: [layout === "side" ? jsx(Heading, { children: "Controls" }) : null, jsx(KeyHints, { className: "cs-ip-keys stacked" })] })
  };
  const moment = jsxs("div", { className: "cs-ip-sec", children: [layout === "side" ? jsx(Heading, { children: "This moment" }) : null, jsx(Moment, { onAnnotate, onAsk, onShot, ready })] });
  if (layout === "side") {
    return jsxs("aside", { "aria-label": "Play-test", className: "cs-ip-panel", children: [sections.note, sections.try, sections.controls, moment] });
  }
  const tabs = [
    ["try", total ? `Try this · ${done}/${total}` : null],
    ["note", note ? "Note" : null],
    ["controls", "Controls"]
  ].filter(([, label]) => label);
  const current = sections[tab] ? tab : tabs[0][0];
  return jsxs("div", {
    "aria-label": "Play-test",
    className: "cs-ip-panel tabs",
    children: [
      jsx("div", {
        "aria-label": "Play-test",
        className: "cs-ip-tabs",
        onKeyDown: (event) => {
          const target = moveFocus(event, event.currentTarget, "[role=tab]");
          if (target) {
            setTab(target.dataset.tab);
          }
        },
        role: "tablist",
        children: tabs.map(
          ([id, label]) => jsx(
            "button",
            {
              "aria-controls": `${ids}-panel`,
              "aria-selected": id === current,
              "data-tab": id,
              id: `${ids}-${id}`,
              onClick: () => setTab(id),
              role: "tab",
              tabIndex: id === current ? 0 : -1,
              type: "button",
              children: label
            },
            id
          )
        )
      }),
      jsx("div", { "aria-labelledby": `${ids}-${current}`, id: `${ids}-panel`, role: "tabpanel", children: sections[current] }),
      moment
    ]
  });
}
function FoldedPanel({ counts, onOpen }) {
  const allDone = counts.complete;
  return jsxs("button", {
    "aria-label": "Open the play-test panel",
    className: "cs-ip-fold",
    onClick: onOpen,
    type: "button",
    children: [
      jsx(Codicon, { name: "checklist", size: 14 }),
      counts.total ? jsx("span", { className: allDone ? "cs-ip-pill ok" : "cs-ip-pill", children: allDone ? "✓" : String(counts.left) }) : null,
      jsx("span", { className: "cs-ip-vt", children: allDone ? "All checked" : counts.total ? `Play-test · ${counts.left} left` : "Play-test" })
    ]
  });
}

// page/pages/build/player/prefs.js
var KEY = "inlinePlayer";
var DEFAULTS = { view: "screen", scale: "fit", finish: "", panel: true };
function clean(saved) {
  const value = { ...DEFAULTS, ...saved && typeof saved === "object" ? saved : {} };
  return {
    view: value.view === "device" ? "device" : "screen",
    scale: SCALES.includes(value.scale) ? value.scale : "fit",
    finish: /^[a-z0-9-]{1,40}$/.test(String(value.finish)) ? value.finish : DEFAULTS.finish,
    panel: value.panel !== false
  };
}
function usePlayerPrefs(ctx) {
  const [prefs, setPrefs] = useState(() => clean(ctx.storage.get(KEY, null)));
  const update = useCallback(
    (partial) => setPrefs((current) => {
      const next = clean({ ...current, ...partial });
      ctx.storage.set(KEY, next);
      return next;
    }),
    []
  );
  return [prefs, update];
}

// page/pages/build/player/report-flow.js
async function attachFrame({ game, stored, image, text: text2 }) {
  if (!stored) {
    return;
  }
  const { path, failure } = await saveCapture(game, image);
  if (path) {
    attachToBuild(stored, [{ key: path, path, name: "this frame" }], text2);
  } else {
    injectBuildDraft(stored, text2);
    host.notify({ kind: "warning", message: `The screenshot was not saved: ${failure}` });
  }
}
async function reportCheck({ bridge, game, stored, playtest, item }) {
  playtest.report(item.key, item.text);
  await attachFrame({ game, stored, image: await bridge.snap(), text: `When I tried “${item.text}”, ` });
}
async function askAboutMoment({ bridge, game, stored }) {
  await attachFrame({ game, stored, image: await bridge.snap(), text: `About what ${game.title} shows here: ` });
}

// page/pages/build/player/checks.js
var KEPT_BUILDS = 12;
var keyOf = (text2) => String(text2).trim().toLowerCase();
function reportChecks(report) {
  const untested = (report?.untested ?? []).map((text2) => ({ key: keyOf(text2), text: text2, untested: true }));
  const tested = (report?.tested ?? []).map((text2) => ({ key: keyOf(text2), text: text2, untested: false }));
  const seen = /* @__PURE__ */ new Set();
  return [...untested, ...tested].filter((item) => item.key && !seen.has(item.key) && seen.add(item.key));
}
var emptyBuild = () => ({ ticks: {}, reported: {} });
function checklist(report, n, saved = {}) {
  const own = saved[n] ?? emptyBuild();
  const items = [];
  const keys = /* @__PURE__ */ new Set();
  for (const [from, entry] of Object.entries(saved)) {
    if (Number(from) >= n) {
      continue;
    }
    for (const [key, text2] of Object.entries(entry.reported ?? {})) {
      const settled = Object.entries(saved).some(([later2, value]) => Number(later2) >= Number(from) && Number(later2) < n && value.ticks?.[key]);
      if (!settled && !keys.has(key)) {
        keys.add(key);
        items.push({ key, text: text2, state: own.ticks[key] ? "done" : "fixed", from: Number(from) });
      }
    }
  }
  for (const check of reportChecks(report)) {
    if (keys.has(check.key)) {
      continue;
    }
    keys.add(check.key);
    const state = own.ticks[check.key] ? "done" : own.reported[check.key] ? "reported" : check.untested ? "untested" : "todo";
    items.push({ key: check.key, text: check.text, state });
  }
  return items;
}
function withTick(saved, n, key, ticked) {
  const own = saved[n] ?? emptyBuild();
  const ticks = { ...own.ticks };
  if (ticked) {
    ticks[key] = true;
  } else {
    delete ticks[key];
  }
  return trim({ ...saved, [n]: { ...own, ticks } });
}
function withReport(saved, n, key, text2) {
  const own = saved[n] ?? emptyBuild();
  const ticks = { ...own.ticks };
  delete ticks[key];
  return trim({ ...saved, [n]: { ticks, reported: { ...own.reported, [key]: text2 } } });
}
function trim(saved) {
  const builds = Object.keys(saved).map(Number).sort((a, b) => b - a);
  return Object.fromEntries(builds.slice(0, KEPT_BUILDS).map((n) => [n, saved[n]]));
}
function progress(items) {
  const done = items.filter((item) => item.state === "done").length;
  const left = items.filter((item) => item.state !== "done" && item.state !== "reported").length;
  return { done, total: items.length, left, complete: items.length > 0 && done === items.length };
}

// page/pages/build/player/use-playtest.js
var KEY2 = "playtest";
var KEPT_GAMES = 40;
var readAll = (ctx) => {
  const value = ctx.storage.get(KEY2, null);
  return value && typeof value === "object" ? value : {};
};
function usePlaytest(ctx, gameId, n, report) {
  const [saved, setSaved] = useState(() => readAll(ctx)[gameId] ?? {});
  const write = useCallback(
    (change) => {
      const all = readAll(ctx);
      const next = change(all[gameId] ?? {});
      const others = Object.entries(all).filter(([id]) => id !== gameId);
      ctx.storage.set(KEY2, Object.fromEntries([...others.slice(-(KEPT_GAMES - 1)), [gameId, next]]));
      setSaved(next);
    },
    [gameId]
  );
  const items = useMemo(() => n ? checklist(report, n, saved) : [], [report, n, saved]);
  return {
    items,
    counts: progress(items),
    tick: useCallback((key, on) => write((current) => withTick(current, n, key, on)), [write, n]),
    report: useCallback((key, text2) => write((current) => withReport(current, n, key, text2)), [write, n])
  };
}

// page/pages/build/player/inline-player.js
var PANEL_WIDTH = 300;
var FOLD_WIDTH = 34;
var STAGE_PAD = 16;
var NARROW2 = 760;
var HEIGHT_SHARE = 0.74;
function useRoom(ref) {
  const [room, setRoom] = useState({ width: 0, height: typeof window === "undefined" ? 800 : window.innerHeight });
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) {
      return void 0;
    }
    const measure = () => setRoom({ width: element.clientWidth, height: window.innerHeight });
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(measure) : null;
    observer?.observe(element);
    window.addEventListener("resize", measure);
    measure();
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);
  return room;
}
function useFullScreen(ref) {
  const [full, setFull] = useState(false);
  useEffect(() => {
    const change = () => setFull(Boolean(ref.current) && document.fullscreenElement === ref.current);
    document.addEventListener("fullscreenchange", change);
    return () => document.removeEventListener("fullscreenchange", change);
  }, []);
  return full;
}
function InlinePlayer({ ctx, game, stored, note, report, build, onClose }) {
  const surface = `build:${game.id}`;
  const owner = useValue(LIVE_PLAYER);
  const live = owner === surface;
  useEffect(() => {
    if (owner === null || owner === "page") {
      claimLive(surface);
    }
  }, [owner, surface]);
  useEffect(() => () => releaseLive(surface), [surface]);
  const sha = playableSha(game);
  const [reload, setReload] = useState(0);
  const [prefs, setPrefs] = usePlayerPrefs(ctx);
  const player = useQuery({
    queryKey: [ID, "player", "build", game.id, sha, reload],
    queryFn: () => callStudio(RPC_PLAYER, { id: game.id }, 3e4),
    enabled: live,
    staleTime: Infinity,
    // asked again each time the player opens, so its finish menu lists the skins there are now
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false
  });
  const rootRef = useRef(null);
  const frameRef = useRef(null);
  const screenRef = useRef(null);
  const frameKey = `${game.id}:${sha}:${reload}`;
  const frameId = live && player.data?.url ? `${frameKey}:${player.data.url}` : null;
  const bridge = usePlayerBridge({ ctx, frameKey: frameId, frameRef, scopeRef: rootRef, visible: live });
  const annotate = useAnnotate(bridge);
  const playtest = usePlaytest(ctx, game.id, build?.n ?? null, report);
  const [panelOpen, setPanelOpen] = useState(() => playtest.counts.left > 0 || prefs.panel && !playtest.counts.complete);
  const [sending, setSending] = useState(false);
  const room = useRoom(rootRef);
  const full = useFullScreen(screenRef);
  const narrow = room.width > 0 && room.width < NARROW2;
  const showPanel = annotate.active || panelOpen;
  const complete = playtest.counts.complete;
  useEffect(() => {
    if (complete) {
      setPanelOpen(false);
    }
  }, [complete]);
  useEffect(() => {
    if (!annotate.active) {
      return void 0;
    }
    const escape = (event) => {
      if (event.key === "Escape" && !event.target?.closest?.("textarea, input")) {
        annotate.cancel();
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [annotate.active]);
  const skins = player.data?.skins ?? [];
  const finish = skins.some((skin) => skin.id === prefs.finish) ? prefs.finish : player.data?.skin ?? "";
  const query = useMemo(() => `view=${prefs.view}&color=${finish}`, [frameId]);
  const ready = Boolean(player.data?.url) && bridge.frame.ready;
  const sync = () => {
    bridge.send(CMD.VIEW, { view: prefs.view });
    bridge.send(CMD.FINISH, { id: finish });
  };
  useEffect(() => {
    if (ready) {
      sync();
    }
  }, [ready, prefs.view, finish]);
  const side = narrow ? 0 : showPanel ? PANEL_WIDTH : FOLD_WIDTH;
  const box = full ? { width: screen.width, height: screen.height } : { width: Math.max(160, room.width - side - 2 * STAGE_PAD), height: Math.max(144, Math.round(room.height * HEIGHT_SHARE)) };
  const size = playerSize(prefs.view, prefs.scale, box);
  const togglePanel = () => {
    setPanelOpen(!panelOpen);
    setPrefs({ panel: !panelOpen });
  };
  const actions = {
    onAsk: () => void askAboutMoment({ bridge, game, stored }),
    onAnnotate: annotate.start,
    onShot: () => bridge.press("screenshot")
  };
  const done = async () => {
    setSending(true);
    try {
      await sendMarks({ bridge, build: build?.n ?? null, game, notes: annotate.notes, stored });
    } finally {
      setSending(false);
    }
  };
  const panel = annotate.active ? jsx(AnnotatePanel, { annotate, layout: narrow ? "tabs" : "side" }) : panelOpen ? jsx(PlaytestPanel, {
    ...actions,
    build: build?.n ?? null,
    layout: narrow ? "tabs" : "side",
    note,
    onWrong: (item) => void reportCheck({ bridge, game, item, playtest, stored }),
    playtest,
    ready
  }) : narrow ? null : jsx(FoldedPanel, { counts: playtest.counts, onOpen: togglePanel });
  const bar = annotate.active ? jsx(AnnotateBar, { busy: sending, count: annotate.marks.length, onCancel: annotate.cancel, onDone: () => void done(), title: game.title }) : jsx(ControlBar, {
    ...actions,
    fits: size.fits,
    finish,
    frame: bridge.frame,
    hint: bridge.focused ? "keys go to the game" : "click the game to play",
    onClose,
    onFull: () => void screenRef.current?.requestFullscreen?.()?.catch?.(() => {
    }),
    onMore: (id) => id === "restart" ? bridge.press("restart") : bridge.press("record-video"),
    panelToggle: jsx(BarButton, { icon: "checklist", label: "Play-test panel", onClick: togglePanel, pressed: panelOpen, text: "Play-test" }),
    prefs,
    ready,
    setPrefs,
    skins,
    title: game.title
  });
  const stage = live ? jsxs("div", {
    className: "cs-ip-stage",
    children: [
      jsx(PlayerNotice, { game, onRefresh: () => setReload((value) => value + 1), player, refreshing: player.isFetching }),
      // The screen element goes full screen; the game inside it keeps a whole-number size.
      jsx("div", {
        className: "cs-ip-screen",
        "data-view": prefs.view,
        ref: screenRef,
        children: jsx("div", {
          className: "cs-ip-fit",
          style: { width: `${size.width}px`, height: `${size.height}px` },
          children: jsx(PlayerStage, { ctx, frameKey, frameRef, game, player, query, visible: true })
        })
      })
    ]
  }) : jsx(PlayerAway, { onBring: () => claimLive(surface), where: "Playing beside the chat" });
  return jsxs("div", {
    "aria-label": `Play ${game.title}`,
    className: narrow ? "cs-ip narrow" : "cs-ip",
    ref: rootRef,
    children: [
      bar,
      jsxs("div", { className: "cs-ip-body", children: [stage, narrow ? null : panel] }),
      narrow ? panel : null,
      showPanel ? null : jsx(KeyHints, {})
    ]
  });
}

// page/shared/ui/screen.js
function Screen({ game, className = "cs-screen" }) {
  return game?.thumb ? jsx("img", { alt: `${game.title} title screen`, className, src: game.thumb }) : jsx("span", { "aria-hidden": true, className: `${className} ph`, children: game?.title ?? "" });
}

// page/pages/build/player/play-card.js
function playsBuild(game, build) {
  const madeAt = (game?.web ?? game?.rom)?.builtAt;
  return Boolean(build?.startAt && madeAt && madeAt * 1e3 >= build.startAt - 2e3);
}
function PlayCard({ game, frame, state, note, build = null, onPlay }) {
  const ready = state === "ready";
  const picture = frame ? jsx(AssetImage, { asset: frame, className: "cs-b-pc-img", fallback: jsx(Screen, { className: "cs-b-pc-img", game }) }) : jsx(Screen, { className: "cs-b-pc-img", game });
  return jsxs("div", {
    className: `cs-b-pc ${state}`,
    children: [
      jsxs("div", {
        className: "cs-b-pc-stage",
        children: [
          jsx("button", {
            "aria-label": ready ? `Play ${game?.title ?? "the game"}` : void 0,
            className: "cs-b-pc-screen",
            disabled: !ready,
            onClick: onPlay,
            tabIndex: -1,
            type: "button",
            children: picture
          }),
          ready ? jsxs("button", {
            className: "cs-b-pc-go",
            onClick: onPlay,
            type: "button",
            children: [jsx(Codicon, { name: "play", size: 13 }), build ? `Play build #${build}` : "Play"]
          }) : jsx("span", {
            className: "cs-b-pc-wait",
            children: state === "busy" ? `Playable again when ${AGENT} finishes` : "The playable copy is not ready yet"
          })
        ]
      }),
      note && ready ? jsx("p", { className: "cs-b-pc-note", children: note }) : null
    ]
  });
}

// page/shared/ui/time.js
function ago(seconds, now) {
  const elapsed = Math.max(0, Math.round(now / 1e3 - seconds));
  if (elapsed < 5) {
    return "just now";
  }
  if (elapsed < 60) {
    return `${elapsed}s ago`;
  }
  if (elapsed < 3600) {
    return `${Math.round(elapsed / 60)} min ago`;
  }
  return `${Math.round(elapsed / 3600)} h ago`;
}
function useNow(active, every = 1e3) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) {
      return void 0;
    }
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), every);
    return () => clearInterval(id);
  }, [active, every]);
  return now;
}
function spanWords(ms) {
  const seconds = Math.max(0, Math.round(ms / 1e3));
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  return minutes < 60 ? `${minutes}m ${String(seconds % 60).padStart(2, "0")}s` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}
function clock(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1e3));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
function timeOfDay(at) {
  if (!at) {
    return "";
  }
  try {
    return new Date(at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

// page/pages/build/transcript/step-words.js
var guideName = (args) => String(args?.name ?? "a").replace(/^hermretro:/, "").replace(/[-_]/g, " ");
var fileWords = (running, done, fallback = "a file") => (args) => {
  const name = baseName(args?.path ?? args?.file_path) || fallback;
  return [`${running} ${name}`, `${done} ${name}`];
};
var STEP_WORDS = {
  project_create: ["Creating the project", "Created the project"],
  project_create_blank: ["Creating the project", "Created the project"],
  project_select: ["Opening the project", "Opened the project"],
  project_inspect: ["Reading the project", "Read the project"],
  project_inventory: ["Listing what’s in the game", "Listed what’s in the game"],
  project_discover: ["Looking for the project", "Found the project"],
  project_refresh: ["Checking the project", "Checked the project"],
  scene_create: ["Adding a scene", "Added a scene"],
  scene_update: ["Editing a scene", "Edited a scene"],
  scene_apply: ["Editing the scene", "Edited the scene"],
  scene_inspect: ["Looking at a scene", "Looked at a scene"],
  scene_delete: ["Removing a scene", "Removed a scene"],
  actor_create: ["Adding a character", "Added a character"],
  actor_update: ["Editing a character", "Edited a character"],
  actor_inspect: ["Looking at a character", "Looked at a character"],
  actor_delete: ["Removing a character", "Removed a character"],
  trigger_create: ["Adding a trigger", "Added a trigger"],
  trigger_update: ["Editing a trigger", "Edited a trigger"],
  trigger_inspect: ["Looking at a trigger", "Looked at a trigger"],
  trigger_delete: ["Removing a trigger", "Removed a trigger"],
  script_edit: ["Writing a script", "Wrote a script"],
  script_inspect: ["Reading a script", "Read a script"],
  script_transition: ["Linking two scenes", "Linked two scenes"],
  dialogue_update: ["Writing dialogue", "Wrote dialogue"],
  dialogue_analyze: ["Checking the dialogue fits", "Checked the dialogue fits"],
  dialogue_preview: ["Previewing dialogue", "Previewed dialogue"],
  asset_import: ["Adding art to the game", "Added art to the game"],
  asset_inspect: ["Looking at the art", "Looked at the art"],
  asset_update: ["Updating the art", "Updated the art"],
  asset_delete: ["Removing art", "Removed art"],
  sprite_edit: ["Tuning a sprite", "Tuned a sprite"],
  sprite_inspect: ["Looking at a sprite", "Looked at a sprite"],
  sprite_preview: ["Previewing a sprite", "Previewed a sprite"],
  sprite_contact_sheet: ["Laying out the animation", "Laid out the animation"],
  palette_create: ["Making a palette", "Made a palette"],
  palette_update: ["Changing a palette", "Changed a palette"],
  palette_assign: ["Colouring the scene", "Coloured the scene"],
  palette_paint: ["Painting colours", "Painted colours"],
  palette_inspect: ["Looking at the palettes", "Looked at the palettes"],
  graphics_analyze: ["Checking the graphics limits", "Checked the graphics limits"],
  graphics_analyze_scene: ["Checking the scene’s graphics", "Checked the scene’s graphics"],
  graphics_preview_scene: ["Rendering the scene", "Rendered the scene"],
  native_graphics_update: ["Updating the title art", "Updated the title art"],
  collision_edit: ["Drawing walls", "Drew walls"],
  collision_inspect: ["Checking walls", "Checked walls"],
  variable_set: ["Setting a variable", "Set a variable"],
  variable_inspect: ["Reading a variable", "Read a variable"],
  variable_delete: ["Removing a variable", "Removed a variable"],
  settings_update: ["Changing game settings", "Changed game settings"],
  engine_field_update: ["Tuning the engine", "Tuned the engine"],
  engine_field_inspect: ["Reading engine settings", "Read engine settings"],
  tilemap_atlas_create: ["Making a tile set", "Made a tile set"],
  tilemap_create: ["Building the map", "Built the map"],
  tilemap_edit: ["Editing the map", "Edited the map"],
  tilemap_compile: ["Compiling the map", "Compiled the map"],
  tilemap_inspect: ["Checking the map", "Checked the map"],
  world_dependencies: ["Tracing how scenes connect", "Traced how scenes connect"],
  rom_build: ["Building the game", "Built the game"],
  rom_inspect: ["Checking the ROM", "Checked the ROM"],
  web_build: ["Building the playable copy", "Built the playable copy"],
  web_preview: ["Getting the player ready", "Got the player ready"],
  web_preview_close: ["Closing the player", "Closed the player"],
  present_game: ["Handing you the game", "Handed you the game"],
  emulator_run: ["Starting the emulator", "Started the emulator"],
  emulator_step: ["Playing the game", "Played the game"],
  emulator_observe: ["Looking at the screen", "Looked at the screen"],
  emulator_inspect: ["Reading the game’s memory", "Read the game’s memory"],
  emulator_debug: ["Checking the game state", "Checked the game state"],
  emulator_checkpoint: ["Saving a checkpoint", "Saved a checkpoint"],
  emulator_clip: ["Recording a clip", "Recorded a clip"],
  emulator_review: ["Reviewing the playtest", "Reviewed the playtest"],
  emulator_recording: ["Saving the recording", "Saved the recording"],
  emulator_status: ["Checking the emulator", "Checked the emulator"],
  emulator_close: ["Closing the emulator", "Closed the emulator"],
  toolchain_prepare: ["Installing the toolchain", "Installed the toolchain"],
  toolchain_doctor: ["Checking the toolchain", "Checked the toolchain"],
  studio_device_cli: ["Setting up the Chromatic tools", "Set up the Chromatic tools"],
  game_info: ["Writing the game card", "Wrote the game card"],
  device: ["Checking the Chromatic", "Checked the Chromatic"],
  device_capture: ["Opening the Chromatic feed", "Opened the Chromatic feed"],
  play: ["Streaming to the Chromatic", "Streamed to the Chromatic"],
  flash: ["Writing the cartridge", "Wrote the cartridge"],
  setup: ["Setting up the Chromatic", "Set up the Chromatic"],
  skill_view: (args) => [`Reading the ${guideName(args)} guide`, `Read the ${guideName(args)} guide`],
  terminal: ["Running a command", "Ran a command"],
  execute_code: ["Running some code", "Ran some code"],
  write_file: fileWords("Writing", "Wrote"),
  patch: fileWords("Editing", "Edited"),
  read_file: fileWords("Reading", "Read"),
  search_files: ["Searching the files", "Searched the files"],
  vision_analyze: (args) => {
    const name = baseName(args?.image_url) || "an image";
    return [`Looking at ${name}`, `Looked at ${name}`];
  },
  web_search: ["Searching the web", "Searched the web"],
  web_extract: ["Reading a web page", "Read a web page"],
  browser_exec: ["Using the browser", "Used the browser"],
  delegate_task: ["Handing a task to a helper", "A helper finished a task"],
  image_generate: ["Generating an image", "Generated an image"],
  desktop_preview: ["Opening a preview", "Opened a preview"],
  clarify: (args) => {
    const count = Array.isArray(args?.questions) ? args.questions.length : 1;
    return ["Asking you", `Asked you ${count === 1 ? "a question" : `${count} questions`}`];
  }
};
var HIDDEN_STEPS = /* @__PURE__ */ new Set(["tool_describe", "tool_search", "todo", "memory", "skill_manage", "skills_list", "session_search", "tool_call", "session_status", "build_report"]);
var BUILD_STEPS = /* @__PURE__ */ new Set(["rom_build", "web_build", "web_preview", "present_game"]);
var shortTool = (name) => String(name ?? "").replace(/^chromatic_/, "");
function stepWords(tool) {
  const short = shortTool(tool.name);
  const words = STEP_WORDS[short];
  const pair2 = typeof words === "function" ? words(tool.args ?? {}) : words;
  if (pair2) {
    return pair2;
  }
  const plain = short.replace(/[_.]/g, " ");
  return [`Using ${plain}`, `Used ${plain}`];
}
function stepDetail(tool) {
  if (tool.state === "failed" && tool.info?.error) {
    return tool.info.error;
  }
  if (tool.progress?.message) {
    return tool.progress.message;
  }
  if (shortTool(tool.name) === "terminal" && tool.args?.command) {
    return tool.args.command.split("\n")[0];
  }
  const text2 = tool.summary ?? tool.preview ?? "";
  return typeof text2 === "string" ? text2 : "";
}
function stepImages(tool, root) {
  const found = [];
  const add = (value) => {
    if (typeof value !== "string" || !/\.(png|gif|jpe?g|webp)$/i.test(value)) {
      return;
    }
    const path = isAbsolute(value) ? value.replace(/^file:\/\//, "") : joinPath(root, value);
    if (path && !found.includes(path)) {
      found.push(path);
    }
  };
  add(tool.image);
  for (const image of tool.info?.images ?? []) {
    add(image);
  }
  add(tool.args?.image_url);
  add(tool.info?.assetPath ?? tool.args?.assetPath);
  add(tool.info?.outputPath ?? tool.args?.outputPath);
  return tool.state === "failed" ? [] : found;
}
function assetKind(path) {
  const value = String(path ?? "");
  if (/[\\/]assets[\\/]sprites[\\/]/.test(value)) {
    return "Sprite";
  }
  if (/[\\/]assets[\\/]backgrounds[\\/]/.test(value)) {
    return "Background";
  }
  if (/[\\/]assets[\\/](ui|fonts)[\\/]/.test(value)) {
    return "Interface";
  }
  if (/[\\/](playtests|frames)[\\/]/.test(value)) {
    return "Playtest frame";
  }
  return "Image";
}

// page/pages/build/transcript/status.js
function BuildStatus({ chat, onStop }) {
  const now = useNow(Boolean(chat?.busy));
  if (!chat?.busy) {
    return null;
  }
  const quietFor = now - (chat.lastEventAt ?? now);
  const running = [...chat.items].reverse().find((item) => item.kind === "tools" && item.tools.some((tool2) => tool2.state === "running"));
  const tool = running ? [...running.tools].reverse().find((entry) => entry.state === "running") : null;
  const waiting = chat.waiting || chat.items.some((item) => (item.kind === "clarify" || item.kind === "approval") && !item.answered);
  const slow = tool && /rom_build|web_build|toolchain_prepare|emulator_step|flash/.test(tool.name);
  let tone = "";
  let headline;
  let detail = null;
  if (waiting) {
    tone = "wait";
    headline = `${AGENT} is waiting for your answer`;
  } else if ((chat.unreachable ?? 0) >= 3) {
    tone = "warn";
    headline = "Reconnecting to Hermes…";
    detail = "The work carries on; this page catches up when it reconnects.";
  } else {
    headline = tool ? `${AGENT} is ${stepWords(tool)[0].replace(/^./, (letter) => letter.toLowerCase())}` : chat.activity === "writing" ? `${AGENT} is writing` : chat.activity === "compacting" ? `${AGENT} is tidying up the conversation` : chat.activity === "preparing" ? `${AGENT} is getting the next step ready` : `${AGENT} is thinking`;
    if (quietFor >= (slow ? 6e5 : 18e4)) {
      tone = "stuck";
      headline = `${AGENT} has been quiet for ${Math.floor(quietFor / 6e4)} minutes`;
      detail = "It may be stuck. Look in the full chat, or stop it.";
    } else if (quietFor >= 45e3) {
      detail = slow ? `Nothing new for ${Math.round(quietFor / 1e3)}s. That is normal for this step.` : `Nothing new for ${Math.round(quietFor / 1e3)}s. Still working.`;
    } else {
      detail = quietFor < 3e3 ? "just now" : `last update ${Math.round(quietFor / 1e3)}s ago`;
    }
  }
  return jsxs("div", {
    "aria-live": "polite",
    className: `cs-b-status ${tone}`,
    role: "status",
    children: [
      jsx("span", { className: tone === "wait" ? "cs-b-pulse wait" : tone === "stuck" || tone === "warn" ? "cs-b-pulse off" : "cs-b-pulse" }),
      jsx("b", { children: headline }),
      detail ? jsx("span", { className: "cs-faint", children: detail }) : null,
      jsx("span", { className: "cs-grow" }),
      chat.turnStartedAt ? jsx("span", { className: "cs-b-dur", children: clock(now - chat.turnStartedAt) }) : null,
      tone === "stuck" && chat.stored ? jsx(Button, { onClick: () => openInFullChat(chat.stored), size: "sm", variant: "ghost", children: "Open full chat" }) : null,
      tone === "stuck" ? jsx(Button, { onClick: onStop, size: "sm", variant: "outline", children: "Stop" }) : null
    ]
  });
}

// page/pages/build/transcript/groups.js
var PLAN_STEPS = /* @__PURE__ */ new Set(["skill_view", "project_select", "project_inspect", "project_inventory", "project_discover", "project_refresh", "toolchain_doctor", "toolchain_prepare", "web_search", "web_extract", "clarify", "read_file", "search_files"]);
var PROJECT_STEPS = /* @__PURE__ */ new Set(["project_create", "project_create_blank", "project_select"]);
var MINOR_STEPS = /^(skill_view|read_file|search_files|project_inventory|project_inspect|toolchain_doctor|world_dependencies|.+_inspect|.+_status|.+_analyze)$/;
var WORK_GROUPS = [
  ["plan", "Planning", "Planned it"],
  ["art", "Drawing the art", "Drew the art", "Worked on the art"],
  ["level", "Setting up the level", "Set up the level"],
  ["build", "Building it", "Built it"],
  ["test", "Play-testing it", "Play-tested it"],
  ["other", "Working on it", "Worked on it"]
];
var GROUP_MIN_STEPS = 8;
var GIST_WORDS = { plan: "planned", art: "drew the art", level: "set up the level", build: "built it", test: "played it" };
var ART_HINT = /\.(png|gif|aseprite)\b|art-src|sprite|background|cover|palette/i;
function phaseOf(tool) {
  const short = shortTool(tool.name);
  if (PLAN_STEPS.has(short)) {
    return "plan";
  }
  if (/^(sprite_|asset_|palette_|graphics_|native_graphics_|tilemap_|image_generate$|game_info$)/.test(short)) {
    return "art";
  }
  if (/^(project_create|scene_|actor_|trigger_|script_|dialogue_|collision_|variable_|settings_|engine_field_|world_dependencies$)/.test(short)) {
    return "level";
  }
  if (/^(rom_|web_build|web_preview|present_game$)/.test(short)) {
    return "build";
  }
  if (/^emulator_/.test(short)) {
    return "test";
  }
  if (/^(terminal|execute_code|write_file|patch)$/.test(short) && ART_HINT.test(JSON.stringify(tool.args ?? {}))) {
    return "art";
  }
  return null;
}
function workGroups(entries) {
  const groups = /* @__PURE__ */ new Map();
  const before = [];
  let current = null;
  for (const entry of entries) {
    const kind = entry.type === "step" ? phaseOf(entry.tool) : null;
    if (kind) {
      current = kind;
      if (!groups.has(kind)) {
        groups.set(kind, []);
      }
      groups.get(kind).push(...before.splice(0), entry);
    } else if (current) {
      groups.get(current).push(entry);
    } else {
      before.push(entry);
    }
  }
  if (before.length) {
    groups.set("other", before);
    current = current ?? "other";
  }
  return {
    groups: WORK_GROUPS.filter(([kind]) => groups.has(kind)).map(([kind]) => ({ kind, entries: groups.get(kind) })),
    last: current
  };
}
function groupTitle(group, live, made) {
  const words = WORK_GROUPS.find(([kind]) => kind === group.kind) ?? WORK_GROUPS[WORK_GROUPS.length - 1];
  return live ? words[1] : group.kind === "art" && !made && words[3] ? words[3] : words[2];
}
function rootOf(game, items) {
  if (game?.projectRoot) {
    return game.projectRoot;
  }
  for (const item of items) {
    for (const tool of item.kind === "tools" ? item.tools : []) {
      if (PROJECT_STEPS.has(shortTool(tool.name)) && tool.info?.projectRoot) {
        return tool.info.projectRoot;
      }
    }
  }
  return null;
}

// page/pages/build/transcript/reply.js
var MEDIA_IMAGE_LINE = /^[ \t]*MEDIA:[ \t]*([`"']?)(.+?\.(?:png|gif|jpe?g|webp))\1[ \t]*$/gim;
function replySegments(text2, root) {
  const segments = [];
  let from = 0;
  for (const match of String(text2 ?? "").matchAll(MEDIA_IMAGE_LINE)) {
    const raw = match[2].trim().replace(/^file:\/\//, "");
    const path = isAbsolute(raw) ? raw : joinPath(root, raw);
    if (!path) {
      continue;
    }
    segments.push({ type: "text", text: text2.slice(from, match.index) });
    segments.push({ type: "image", path, line: match[0] });
    from = match.index + match[0].length;
  }
  segments.push({ type: "text", text: String(text2 ?? "").slice(from) });
  return segments.filter((segment) => segment.type === "image" || segment.text.trim());
}
function replyAssets(items, root) {
  return items.flatMap(
    (item) => replySegments(item.text, root).filter((segment) => segment.type === "image").map((segment) => ({ path: segment.path, version: `reply:${item.at ?? ""}`, kind: assetKind(segment.path), step: "In the reply", at: item.at ?? null }))
  );
}
function ReplyImage({ asset, line, onOpen }) {
  const { state, code, asset: loaded } = useAsset(asset.path, asset.version);
  if (state === "none") {
    return MessageTextContent ? jsx(MessageTextContent, code === "OTHER_GAME" ? { media: false, previewOnly: true, text: line } : { text: line }) : null;
  }
  if (state === "loading") {
    return jsx("span", { "aria-hidden": true, className: "cs-b-rchip loading" });
  }
  const kind = loaded.kind === "sprite" ? "Sprite" : loaded.kind === "background" ? "Background" : /(^|[\\/])cover\.png$/i.test(asset.path) ? "Game cover" : asset.kind;
  return jsxs("button", {
    "aria-label": `Look closer at ${loaded.name}`,
    className: "cs-b-rchip",
    onClick: (event) => {
      event.stopPropagation();
      onOpen?.(asset);
    },
    title: `${loaded.name} · ${loaded.width}×${loaded.height}`,
    type: "button",
    children: [
      jsx("span", { className: "cs-b-th sm", children: jsx(SheetFrame, { loaded }) }),
      jsxs("span", {
        className: "cs-col",
        children: [jsx("b", { children: loaded.sprite?.name || loaded.name }), jsx("span", { children: `${kind} · ${loaded.width}×${loaded.height}` })]
      })
    ]
  });
}
var AgentText = memo(
  ({ item, root, onOpenAsset }) => {
    const segments = replySegments(item.text, root);
    const media = replyAssets([item], root);
    const blocks = [];
    segments.forEach((segment, index) => {
      if (segment.type === "image") {
        const asset = media.find((entry) => entry.path === segment.path);
        const chip = jsx(ReplyImage, { asset, line: segment.line, onOpen: onOpenAsset }, `m${index}`);
        const last = blocks[blocks.length - 1];
        if (last?.images) {
          last.images.push(chip);
        } else {
          blocks.push({ images: [chip], key: `r${index}` });
        }
      } else {
        blocks.push(MessageTextContent ? jsx(MessageTextContent, { text: segment.text }, `t${index}`) : jsx("span", { children: segment.text }, `t${index}`));
      }
    });
    return jsx("div", {
      className: "cs-b-agent",
      children: blocks.map((block) => block?.images ? jsx("div", { className: "cs-b-rimgs", children: block.images }, block.key) : block)
    });
  },
  (previous, next) => previous.item.text === next.item.text && previous.root === next.root && previous.onOpenAsset === next.onOpenAsset
);

// page/pages/build/transcript/turns.js
function deriveTurns(items) {
  const turns = [];
  let current = null;
  items.forEach((item, index) => {
    if (item.kind === "user" || !current || current.ended && item.kind !== "end") {
      current = { key: `t${index}`, user: item.kind === "user" ? item : null, items: item.kind === "user" ? [] : [item], ended: false };
      turns.push(current);
    } else {
      current.items.push(item);
    }
    if (item.kind === "end") {
      current.ended = true;
    }
  });
  return turns;
}
function turnParts(turn, root) {
  const tokens = [];
  const prompts = [];
  const errors = [];
  let end = null;
  let report = null;
  const hasCard = turn.items.some((item) => item.kind === "clarify");
  for (const item of turn.items) {
    if (item.kind === "assistant" && item.text.trim()) {
      tokens.push({ type: "text", item });
    } else if (item.kind === "tools") {
      for (const tool of item.tools) {
        const short = shortTool(tool.name);
        if (short === "build_report" && tool.state !== "failed") {
          report = tool.info?.report ?? tool.report ?? report;
        }
        if (!HIDDEN_STEPS.has(short) && !(short === "clarify" && hasCard)) {
          tokens.push({ type: "step", tool });
        }
      }
    } else if (item.kind === "clarify" || item.kind === "approval") {
      if (item.answered) {
        tokens.push({ type: "asked", item });
      } else {
        prompts.push(item);
      }
    } else if (item.kind === "error") {
      errors.push(item);
    } else if (item.kind === "end") {
      end = item;
    }
  }
  const first = tokens.findIndex((token) => token.type !== "text");
  const last = tokens.length - 1 - [...tokens].reverse().findIndex((token) => token.type !== "text");
  const intro = first === -1 ? tokens : tokens.slice(0, first);
  const outro = first === -1 ? [] : tokens.slice(last + 1);
  const entries = first === -1 ? [] : tokens.slice(first, last + 1).map((token) => token.type === "text" ? { type: "note", item: token.item } : token);
  const steps = entries.filter((entry) => entry.type === "step").map((entry) => entry.tool);
  const assets = [];
  for (const tool of steps) {
    for (const path of stepImages(tool, root)) {
      const known = assets.findIndex((asset) => asset.path === path);
      const looked = LOOK_STEPS.test(shortTool(tool.name)) && (known === -1 || assets[known].looked);
      if (known !== -1) {
        assets.splice(known, 1);
      }
      assets.push({ path, version: tool.id, kind: assetKind(path), step: stepWords(tool)[1], at: tool.startedAt ?? null, looked });
    }
  }
  const builds = steps.filter((tool) => BUILD_STEPS.has(shortTool(tool.name)));
  const lastBuild = builds[builds.length - 1] ?? null;
  const presented = [...steps].reverse().find((tool) => shortTool(tool.name) === "present_game" && tool.state === "done") ?? null;
  return {
    intro: intro.map((token) => token.item),
    outro: outro.map((token) => token.item),
    entries,
    steps,
    prompts,
    errors,
    end,
    assets,
    built: builds.some((tool) => tool.state === "done"),
    buildFailed: lastBuild?.state === "failed" ? lastBuild.info?.error ?? "The build failed." : null,
    buildState: turnBuildState(turn),
    report,
    note: presented?.info?.note ?? null,
    running: steps.find((tool) => tool.state === "running") ?? null
  };
}
var COMPILE_STEPS = /* @__PURE__ */ new Set(["rom_build", "web_build"]);
function turnBuildState(turn) {
  let state = null;
  for (const item of turn.items) {
    if (item.kind === "tools") {
      for (const tool of item.tools) {
        if (COMPILE_STEPS.has(shortTool(tool.name)) && (tool.state === "done" || tool.state === "failed")) {
          state = tool.state === "done" ? "built" : "failed";
        }
      }
    }
  }
  return state;
}
function buildHistory(turns) {
  const builds = [];
  turns.forEach((turn, index) => {
    const state = turnBuildState(turn);
    if (!state) {
      return;
    }
    let report = null;
    let endAt = null;
    let startAt = turn.user?.at ?? null;
    let thumb = null;
    for (const item of turn.items) {
      if (item.kind === "end") {
        endAt = item.at ?? endAt;
        startAt = startAt ?? item.startedAt ?? null;
      } else if (item.kind === "tools") {
        for (const tool of item.tools) {
          if (shortTool(tool.name) === "build_report" && tool.state !== "failed") {
            report = tool.info?.report ?? tool.report ?? report;
          }
          for (const path of tool.state === "failed" ? [] : tool.info?.images ?? []) {
            if (assetKind(path) === "Playtest frame") {
              thumb = { path, version: tool.id, kind: "Playtest frame" };
            }
          }
          startAt = startAt ?? tool.startedAt ?? null;
        }
      }
    }
    const asked2 = String(turn.user?.text ?? "").trim().split("\n")[0];
    builds.push({
      n: builds.length + 1,
      key: turn.key,
      index,
      state,
      title: report?.title ?? (asked2 ? asked2.length > 48 ? `${asked2.slice(0, 47)}…` : asked2 : `Build ${builds.length + 1}`),
      startAt,
      endAt,
      thumb
    });
  });
  return builds;
}
function turnBuilt(turn) {
  return turnBuildState(turn) !== "failed" && turn.items.some((item) => item.kind === "tools" && item.tools.some((tool) => tool.state === "done" && BUILD_STEPS.has(shortTool(tool.name))));
}
var LOOK_STEPS = /^(vision_analyze|read_file|search_files|browser_exec|.+_inspect|.+_analyze|graphics_analyze_scene)$/;
function madeAssets(parts, root) {
  const made = parts.assets.filter((asset) => !asset.looked && asset.kind !== "Playtest frame");
  for (const asset of replyAssets([...parts.intro, ...parts.outro], root)) {
    if (asset.kind !== "Playtest frame" && !made.some((entry) => entry.path === asset.path)) {
      made.push(asset);
    }
  }
  return made;
}

// page/pages/build/viewer/checks.js
function artChecks(image, kind, info) {
  if (!image) {
    return [];
  }
  const width = image.naturalWidth;
  const height = image.naturalHeight;
  const checks = [];
  try {
    const canvas2 = document.createElement("canvas");
    canvas2.width = width;
    canvas2.height = height;
    const context = canvas2.getContext("2d");
    context.drawImage(image, 0, 0);
    const { data } = context.getImageData(0, 0, width, height);
    const colour = (x, y) => {
      const index = (y * width + x) * 4;
      return data[index + 3] < 128 ? -1 : data[index] << 16 | data[index + 1] << 8 | data[index + 2];
    };
    const tileColours = (tileWidth, tileHeight, skip) => {
      let worst = 0;
      let over = 0;
      const unique = /* @__PURE__ */ new Set();
      for (let top = 0; top + tileHeight <= height; top += tileHeight) {
        for (let left = 0; left + tileWidth <= width; left += tileWidth) {
          const seen = /* @__PURE__ */ new Set();
          let signature = "";
          for (let y = top; y < top + tileHeight; y += 1) {
            for (let x = left; x < left + tileWidth; x += 1) {
              const value = colour(x, y);
              signature += `${value},`;
              if (!skip(value)) {
                seen.add(value);
              }
            }
          }
          unique.add(signature);
          worst = Math.max(worst, seen.size);
          over += seen.size > (skip === noSkip ? 4 : 3) ? 1 : 0;
        }
      }
      return { worst, over, unique: unique.size };
    };
    const noSkip = () => false;
    if (kind === "sprite") {
      const result = tileColours(8, 16, (value) => value === -1 || value === 6684416 || value >> 16 < 130 && (value >> 8 & 255) > 215 && (value & 255) < 80);
      checks.push(result.over ? { ok: false, text: `${result.over} ${result.over === 1 ? "tile uses" : "tiles use"} more than 3 colours (the hardware shows 3 + transparent)` } : { ok: true, text: `At most ${result.worst} colours per 8×16 tile` });
      const sprite2 = info?.sprite;
      if (sprite2) {
        const fits = sprite2.canvasWidth % 8 === 0 && sprite2.canvasHeight % 16 === 0;
        const objects = sprite2.canvasWidth / 8 * Math.max(1, sprite2.canvasHeight / 16);
        checks.push(fits ? { ok: true, text: `${objects} hardware ${objects === 1 ? "object" : "objects"} per frame (8×16 mode)` } : { ok: false, text: `Frame is ${sprite2.canvasWidth}×${sprite2.canvasHeight}: not a multiple of 8×16` });
        if (sprite2.numTiles != null) {
          checks.push({ ok: true, text: `${sprite2.numTiles} tiles in video memory` });
        }
      }
    } else if (kind === "background") {
      const result = tileColours(8, 8, noSkip);
      checks.push(result.over ? { ok: false, text: `${result.over} ${result.over === 1 ? "tile uses" : "tiles use"} more than 4 colours` } : { ok: true, text: `At most ${result.worst} colours per 8×8 tile` });
      checks.push(result.unique > 192 ? { ok: false, text: `${result.unique} unique tiles (keep it at 192 or fewer)` } : { ok: true, text: `${result.unique} unique tiles of 192` });
    } else if (kind === "cover") {
      const colours = /* @__PURE__ */ new Set();
      let transparent = false;
      for (let y = 0; y < height; y += 1) {
        for (let x = 0; x < width; x += 1) {
          const value = colour(x, y);
          if (value === -1) {
            transparent = true;
          } else {
            colours.add(value);
          }
        }
      }
      checks.push(width === 160 && height === 144 ? { ok: true, text: "160×144, the Chromatic screen size" } : { ok: false, text: `${width}×${height}: covers are 160×144` });
      checks.push(colours.size <= 32 ? { ok: true, text: `${colours.size} colours (32 at most)` } : { ok: false, text: `${colours.size} colours: covers use 32 at most` });
      checks.push(transparent ? { ok: false, text: "Has transparent pixels: covers are opaque" } : { ok: true, text: "Opaque" });
    }
  } catch {
    return [];
  }
  return checks;
}

// page/pages/build/viewer/in-game.js
function SceneCanvas({ scene, images, scale, highlight, refresh }) {
  const ref = useRef(null);
  const width = (Number(scene.width) || 20) * 8;
  const height = (Number(scene.height) || 18) * 8;
  useLayoutEffect(() => {
    const canvas2 = ref.current;
    const context = canvas2?.getContext?.("2d");
    if (!context) {
      return;
    }
    canvas2.width = width * scale;
    canvas2.height = height * scale;
    context.imageSmoothingEnabled = false;
    context.fillStyle = "#111";
    context.fillRect(0, 0, canvas2.width, canvas2.height);
    const background = scene.background ? images[scene.background] : null;
    if (background) {
      context.drawImage(background, 0, 0, background.naturalWidth * scale, background.naturalHeight * scale);
    }
    for (const actor of scene.actors ?? []) {
      const sheet = images[actor.sprite];
      if (!sheet) {
        continue;
      }
      const left = (Number(actor.x) || 0) * 8;
      const top = ((Number(actor.y) || 0) + 1) * 8 - actor.canvasHeight;
      drawSpriteFrame(context, paintSheet(sheet, actor.palette?.colors), actor.tiles, {
        flip: actor.flip,
        height: actor.canvasHeight,
        left: left * scale,
        scale,
        top: top * scale,
        width: actor.canvasWidth
      });
      if (highlight && actor.spriteId === highlight) {
        context.save();
        context.strokeStyle = "#fbbf24";
        context.lineWidth = 2;
        context.setLineDash([5, 4]);
        context.strokeRect(left * scale - 3, top * scale - 3, actor.canvasWidth * scale + 6, actor.canvasHeight * scale + 6);
        context.restore();
      }
    }
  }, [scene, images, scale, highlight, refresh, width, height]);
  return jsx("canvas", { className: "cs-v-px", ref });
}
function CoverInGame({ image, game }) {
  const card = game?.card ?? null;
  const title = card?.title || game?.title || "Your game";
  const src = image?.src ?? null;
  return jsxs("div", {
    className: "cs-v-ingame",
    children: [
      jsxs("figure", {
        children: [
          jsxs("div", {
            className: "cs-v-gcard",
            children: [
              src ? jsx("img", { alt: "", src }) : jsx("span", { className: "cs-v-ver-ph" }),
              jsxs("div", {
                className: "cs-col",
                style: { gap: 3, padding: "9px 11px" },
                children: [
                  jsx("b", { children: title }),
                  card?.tagline ? jsx("span", { className: "cs-faint", children: card.tagline }) : null,
                  card?.genres?.length ? jsx("span", { className: "cs-row", style: { gap: 5 }, children: card.genres.map((genre) => jsx("span", { className: "cs-tag", children: genre }, genre)) }) : null
                ]
              })
            ]
          }),
          jsx("figcaption", { children: "Games page" })
        ]
      }),
      jsxs("figure", {
        children: [
          jsxs("div", {
            className: "cs-v-device",
            children: [
              jsx("div", { className: "cs-v-device-screen", children: src ? jsx("img", { alt: "", src }) : null }),
              jsx("span", { className: "cs-v-device-name", children: "CHROMATIC" }),
              jsxs("div", { "aria-hidden": true, className: "cs-v-device-pad", children: [jsx("i", { className: "dpad" }), jsxs("span", { children: [jsx("i", {}), jsx("i", {})] })] })
            ]
          }),
          jsx("figcaption", { children: "On a Chromatic" })
        ]
      })
    ]
  });
}

// page/pages/build/viewer/info.js
var VIEWER_KIND = { cover: "Game cover", sprite: "Sprite", background: "Background", ui: "Interface", frame: "Playtest frame", capture: "Capture", image: "Image" };
function useAssetInfo(path, refresh) {
  const root = useContext(AssetGame);
  const [info, setInfo] = useState(null);
  useEffect(() => {
    if (!path) {
      setInfo(null);
      return void 0;
    }
    let live = true;
    callStudioOnly(RPC_ASSET_INFO, { path, root }, 2e4).then((answer) => live && setInfo(answer?.ok ? answer : null)).catch(() => live && setInfo(null));
    return () => {
      live = false;
    };
  }, [path, root, refresh]);
  return info;
}
function useImages(paths, version) {
  const root = useContext(AssetGame);
  const putBack = usePutBack();
  const [images, setImages] = useState({});
  const key = paths.join("\n");
  useEffect(() => {
    let live = true;
    setImages({});
    for (const path of paths) {
      void assetEntry(path, version, root).promise.then((answer) => {
        if (!live || !answer?.dataUrl) {
          return;
        }
        const element = document.createElement("img");
        element.onload = () => live && setImages((current) => ({ ...current, [path]: element }));
        element.src = answer.dataUrl;
      });
    }
    return () => {
      live = false;
    };
  }, [key, version, root, putBack]);
  return images;
}

// page/pages/build/viewer/sprite-canvas.js
function SpriteFrameCanvas({ image, sprite: sprite2, tiles, flip, scale, colors, under = null }) {
  const ref = useRef(null);
  const width = sprite2?.canvasWidth ?? 16;
  const height = sprite2?.canvasHeight ?? 16;
  useLayoutEffect(() => {
    const canvas2 = ref.current;
    const context = canvas2?.getContext?.("2d");
    if (!context || !image) {
      return;
    }
    canvas2.width = width * scale;
    canvas2.height = height * scale;
    context.imageSmoothingEnabled = false;
    context.clearRect(0, 0, canvas2.width, canvas2.height);
    const sheet = paintSheet(image, colors);
    if (under) {
      context.globalAlpha = 0.28;
      drawSpriteFrame(context, sheet, under, { flip, height, left: 0, scale, top: 0, width });
      context.globalAlpha = 1;
    }
    drawSpriteFrame(context, sheet, tiles, { flip, height, left: 0, scale, top: 0, width });
  }, [image, tiles, under, flip, scale, colors?.join(","), width, height]);
  return jsx("canvas", { className: "cs-v-px", ref });
}

// page/pages/build/viewer/stage.js
var ZOOM_STEPS = [1, 2, 3, 4, 6, 8, 12, 16];
function versionTime(entry) {
  return entry?.at ? timeOfDay(entry.at) : "";
}
function VersionThumb({ path, entry, number, selected, onPick }) {
  const { state, asset: loaded } = useAsset(path, `kept:${entry.id}`);
  return jsxs("button", {
    "aria-label": `Version ${number}${entry.current ? ", in the game now" : ""}`,
    "aria-pressed": selected,
    className: `cs-v-ver${selected ? " on" : ""}`,
    onClick: () => onPick(entry.id),
    title: `v${number} · ${versionTime(entry)}${entry.current ? " · in the game now" : ""}`,
    type: "button",
    children: [
      state === "ok" ? jsx(SheetFrame, { loaded }) : jsx("span", { className: "cs-v-ver-ph" }),
      jsx("b", { children: `v${number}` }),
      entry.current ? jsx("i", { "aria-hidden": true, className: "cs-v-now" }) : null
    ]
  });
}
function useBoxSize(ref) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) {
      return void 0;
    }
    const measure = () => setSize({ width: element.clientWidth, height: element.clientHeight });
    measure();
    if (typeof ResizeObserver === "undefined") {
      return void 0;
    }
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return size;
}
function fitScale(box, width, height, pad = 48) {
  if (!box.width || !box.height || !width || !height) {
    return 1;
  }
  const fit = Math.min((box.width - pad) / width, (box.height - pad) / height);
  return fit >= 1 ? Math.min(16, Math.floor(fit)) : Math.max(0.1, fit);
}
function ImageStage({ image, scale, grid, gridSize = [8, 8], area, onArea, picking }) {
  const drag = useRef(null);
  const width = image ? image.naturalWidth : 0;
  const height = image ? image.naturalHeight : 0;
  const point = (event) => {
    const box = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(width, Math.round((event.clientX - box.left) / scale))),
      y: Math.max(0, Math.min(height, Math.round((event.clientY - box.top) / scale)))
    };
  };
  return jsxs("div", {
    className: `cs-v-canvas${picking ? " picking" : ""}`,
    onPointerDown: picking ? (event) => {
      event.currentTarget.setPointerCapture?.(event.pointerId);
      drag.current = point(event);
      onArea({ x: drag.current.x, y: drag.current.y, w: 0, h: 0 });
    } : void 0,
    onPointerMove: picking ? (event) => {
      if (!drag.current) {
        return;
      }
      const now = point(event);
      onArea({ x: Math.min(now.x, drag.current.x), y: Math.min(now.y, drag.current.y), w: Math.abs(now.x - drag.current.x), h: Math.abs(now.y - drag.current.y) });
    } : void 0,
    onPointerUp: picking ? () => {
      drag.current = null;
      onArea((current) => current && current.w >= 2 && current.h >= 2 ? current : null);
    } : void 0,
    style: { height: `${height * scale}px`, width: `${width * scale}px` },
    children: [
      image ? jsx(FrameCanvas, { frame: { x: 0, y: 0, w: width, h: height }, image, scale }) : null,
      grid && scale >= 2 ? jsx("span", { "aria-hidden": true, className: "cs-v-grid", style: { backgroundSize: `${gridSize[0] * scale}px ${gridSize[1] * scale}px` } }) : null,
      area ? jsx("span", {
        "aria-hidden": true,
        className: "cs-v-area",
        style: { height: `${area.h * scale}px`, left: `${area.x * scale}px`, top: `${area.y * scale}px`, width: `${area.w * scale}px` },
        children: jsx("em", { children: `${area.w}×${area.h} at ${area.x}, ${area.y}` })
      }) : null
    ]
  });
}

// page/pages/build/viewer/asset-viewer.js
function AssetViewer({ ctx, assets, index, onIndex, onClose, onSend, chat, root, game }) {
  const asset = assets[index];
  const path = asset?.path ?? null;
  const [refresh, setRefresh] = useState(0);
  const info = useAssetInfo(path, refresh);
  const opened = useAsset(path, asset?.version);
  const [picked, setPicked] = useState(null);
  const shownVersion = picked ? `kept:${picked}` : asset?.version;
  const { state, asset: loaded } = useAsset(path, shownVersion);
  const image = useImage(loaded?.dataUrl);
  const kind = info?.kind ?? (loaded?.sprite ? "sprite" : opened.asset?.kind) ?? "image";
  const sprite2 = info?.sprite ?? null;
  const animations = useMemo(() => spriteAnimations(sprite2), [sprite2]);
  const scenes = info?.scenes ?? [];
  const views = kind === "cover" ? ["Image", "In game"] : kind === "sprite" ? [...animations.length ? ["Animation"] : [], "Sheet", ...scenes.length ? ["In game"] : []] : kind === "background" && scenes.length ? ["Image", "In game"] : ["Image"];
  const [view, setView] = useState(null);
  const shownView = views.includes(view) ? view : views[0];
  const [side, setSide] = useState("Details");
  const [zoom, setZoom] = useState("fit");
  const [grid, setGrid] = useState(false);
  const [area, setArea] = useState(null);
  const [request, setRequest] = useState("");
  const [rebuild, setRebuild] = useState(true);
  const [gameColours, setGameColours] = useState(true);
  const [animationIndex, setAnimationIndex] = useState(0);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [onion, setOnion] = useState(false);
  const [sceneIndex, setSceneIndex] = useState(0);
  const [sentAt, setSentAt] = useState(null);
  const [restoring, setRestoring] = useState(false);
  const stageRef = useRef(null);
  const box = useBoxSize(stageRef);
  const dialog = useRef(null);
  const input = useRef(null);
  const palette = useMemo(() => image ? imagePalette(image, 32) : [], [image]);
  const checks = useMemo(() => artChecks(image, kind, info), [image, kind, info]);
  const sceneImages = useImages(
    useMemo(() => [...new Set(scenes.flatMap((scene2) => [scene2.background, ...(scene2.actors ?? []).map((actor) => actor.sprite)]).filter(Boolean))], [scenes]),
    `scene:${refresh}`
  );
  const versions = info?.versions ?? [];
  const currentId = versions.find((entry) => entry.current)?.id ?? null;
  const shownId = picked ?? loaded?.versionId ?? null;
  const shownEntry = versions.find((entry) => entry.id === shownId) ?? null;
  const shownNumber = shownEntry ? versions.indexOf(shownEntry) + 1 : null;
  const older = Boolean(shownEntry && currentId && shownEntry.id !== currentId);
  const name = sprite2?.name || loaded?.sprite?.name || loaded?.name || baseName(path ?? "");
  const animation = animations[Math.min(animationIndex, Math.max(0, animations.length - 1))] ?? null;
  const frames = animation?.frames ?? [];
  const frameMs = spriteFrameMs(sprite2?.animSpeed);
  const colors = gameColours ? info?.palette?.colors : null;
  const working = Boolean(sentAt && chat?.busy);
  const asks = [...new Set(assets.filter((entry) => entry.path === path && entry.ask).map((entry) => entry.ask))];
  useEffect(() => {
    setPicked(null);
    setView(null);
    setArea(null);
    setFrame(0);
    setAnimationIndex(0);
    setSceneIndex(0);
    setZoom("fit");
  }, [path, asset?.version]);
  useEffect(() => setFrame(0), [animationIndex]);
  useEffect(() => {
    if (!animations.length) {
      return;
    }
    const walking = animations.findIndex((entry) => /walk|run|moving/i.test(entry.name) && entry.frames.length > 1);
    setAnimationIndex(walking === -1 ? Math.max(0, animations.findIndex((entry) => entry.frames.length > 1)) : walking);
  }, [animations]);
  useEffect(() => {
    if (shownView !== "Animation" || !playing || frames.length < 2) {
      return void 0;
    }
    const id = setInterval(() => setFrame((value) => (value + 1) % frames.length), frameMs);
    return () => clearInterval(id);
  }, [shownView, playing, frames.length, frameMs]);
  const wasWorking = useRef(false);
  useEffect(() => {
    if (working) {
      wasWorking.current = true;
    } else if (sentAt && wasWorking.current) {
      wasWorking.current = false;
      setSentAt(null);
      setPicked(null);
      setRefresh((value) => value + 1);
    }
  }, [working, sentAt]);
  useEffect(() => {
    if (refresh && currentId) {
      setPicked(currentId);
    }
  }, [refresh, currentId]);
  useEffect(() => {
    if (side === "Change") {
      input.current?.focus?.();
    } else {
      setArea(null);
    }
  }, [side]);
  useEffect(() => {
    dialog.current?.focus?.();
    const onKey = (event) => {
      const typing = /^(TEXTAREA|INPUT|SELECT)$/.test(event.target?.tagName ?? "");
      if (event.key === "Escape") {
        event.preventDefault();
        if (area) {
          setArea(null);
        } else {
          onClose();
        }
      } else if (typing) {
        return;
      } else if (event.key === "ArrowRight" && assets.length > 1) {
        event.preventDefault();
        onIndex((index + 1) % assets.length);
      } else if (event.key === "ArrowLeft" && assets.length > 1) {
        event.preventDefault();
        onIndex((index - 1 + assets.length) % assets.length);
      } else if ((event.key === "," || event.key === ".") && shownView === "Animation" && frames.length > 1) {
        event.preventDefault();
        setPlaying(false);
        setFrame((value) => (value + (event.key === "." ? 1 : frames.length - 1)) % frames.length);
      } else if (event.key === " " && shownView === "Animation") {
        event.preventDefault();
        setPlaying((value) => !value);
      } else if (event.key === "+" || event.key === "=") {
        setZoom((value) => ZOOM_STEPS.find((step) => step > (value === "fit" ? currentScale : value)) ?? 16);
      } else if (event.key === "-") {
        setZoom((value) => [...ZOOM_STEPS].reverse().find((step) => step < (value === "fit" ? currentScale : value)) ?? 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  const scene = scenes[Math.min(sceneIndex, Math.max(0, scenes.length - 1))] ?? null;
  let contentWidth = image?.naturalWidth ?? 0;
  let contentHeight = image?.naturalHeight ?? 0;
  if (shownView === "Animation" && sprite2) {
    contentWidth = sprite2.canvasWidth;
    contentHeight = sprite2.canvasHeight;
  } else if (shownView === "In game" && scene) {
    contentWidth = (Number(scene.width) || 20) * 8;
    contentHeight = (Number(scene.height) || 18) * 8;
  }
  const fit = fitScale(box, contentWidth, contentHeight, shownView === "Animation" ? 140 : 48);
  const currentScale = zoom === "fit" ? fit : zoom;
  const zoomable = shownView !== "In game" || kind !== "cover";
  useEffect(() => {
    const element = stageRef.current;
    if (!element || !zoomable) {
      return void 0;
    }
    const onWheel = (event) => {
      event.preventDefault();
      setZoom((value) => {
        const now = value === "fit" ? currentScale : value;
        return event.deltaY < 0 ? ZOOM_STEPS.find((step) => step > now) ?? 16 : [...ZOOM_STEPS].reverse().find((step) => step < now) ?? 1;
      });
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, [zoomable, currentScale]);
  const pan = useRef(null);
  if (!asset) {
    return null;
  }
  const reveal = async () => {
    const shown = await ctx.os?.revealPath?.(path).catch(() => false);
    if (!shown) {
      const copied = await ctx.os?.writeClipboard?.(path).catch(() => false);
      host.notify({ kind: "info", message: copied ? "The file is on the computer running Hermes. Its path is copied." : path });
    }
  };
  const copyImage = async () => {
    try {
      const blob = await (await fetch(loaded.dataUrl)).blob();
      await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
      host.notify({ kind: "success", message: "Image copied" });
    } catch {
      const copied = await ctx.os?.writeClipboard?.(path).catch(() => false);
      host.notify({ kind: "info", message: copied ? "The image could not be copied, so its path was." : "The image could not be copied." });
    }
  };
  const copyColour = async (color) => {
    const copied = await ctx.os?.writeClipboard?.(color).catch(() => false);
    host.notify({ kind: copied ? "success" : "info", message: copied ? `${color} copied` : color });
  };
  const restore = async () => {
    if (!shownEntry || restoring) {
      return;
    }
    setRestoring(true);
    try {
      const answer = await callStudioOnly(RPC_ASSET_RESTORE, { path, root, version: shownEntry.id }, 2e4);
      if (!answer?.ok) {
        throw new Error(answer?.error ?? "It could not be restored.");
      }
      forgetAsset(path, answer.path);
      host.notify({ kind: "success", message: `v${shownNumber} is back in the game. Build again to play it.` });
      setRefresh((value) => value + 1);
    } catch (error) {
      host.notify({ kind: "error", message: error instanceof Error ? error.message : String(error) });
    } finally {
      setRestoring(false);
    }
  };
  const send = () => {
    const words = request.trim();
    if (!words || !onSend || working) {
      return;
    }
    const notes = [];
    if (area && image) {
      notes.push(`Only change the area from (${area.x}, ${area.y}) to (${area.x + area.w - 1}, ${area.y + area.h - 1}), in pixels of the ${image.naturalWidth}×${image.naturalHeight} image. Keep everything outside it exactly as it is.`);
    }
    if (older && shownEntry) {
      notes.push(`Start from version ${shownNumber} (from ${versionTime(shownEntry)}), kept at ${shownEntry.file}. The file in the game is a newer version.`);
    }
    if (rebuild && (kind === "sprite" || kind === "background")) {
      notes.push("When it is done, build the game and show it to me with chromatic_present_game.");
    }
    const text2 = notes.length ? `${words}

${notes.map((note) => `- ${note}`).join("\n")}` : words;
    onSend(text2, area ? `${words} (the marked area)` : words, [{ path, name: loaded?.name ?? baseName(path) }]);
    setRequest("");
    setArea(null);
    setSentAt(Date.now());
  };
  let progress2 = [];
  if (sentAt && chat?.items?.length) {
    const turns = deriveTurns(chat.items);
    const last = turns[turns.length - 1];
    progress2 = last ? turnParts(last, root).steps.slice(-6) : [];
  }
  const running = progress2.find((tool) => tool.state === "running") ?? null;
  const picking = side === "Change" && (shownView === "Image" || shownView === "Sheet") && !working;
  let stage;
  if (state === "loading" || !image && state !== "none") {
    stage = jsx("span", { className: "cs-b-th lg loading" });
  } else if (!image) {
    stage = jsx("p", { className: "cs-small", children: "This picture could not be loaded." });
  } else if (shownView === "Animation" && animation) {
    const tiles = frames[Math.min(frame, frames.length - 1)] ?? [];
    const before = onion && frames.length > 1 ? frames[(frame + frames.length - 1) % frames.length] : null;
    stage = jsx(SpriteFrameCanvas, { colors, flip: animation.flip, image, scale: currentScale, sprite: sprite2, tiles, under: before });
  } else if (shownView === "In game" && kind === "cover") {
    stage = jsx(CoverInGame, { game, image });
  } else if (shownView === "In game" && scene) {
    stage = jsx(SceneCanvas, { highlight: kind === "sprite" ? sprite2?.id : null, images: sceneImages, refresh, scale: currentScale, scene });
  } else {
    const sheetColours = kind === "sprite" && colors ? paintSheet(image, colors) : null;
    stage = jsx(ImageStage, {
      area,
      grid,
      gridSize: kind === "sprite" ? [8, 16] : [8, 8],
      image: sheetColours && sheetColours !== image ? canvasImage(sheetColours, image) : image,
      onArea: setArea,
      picking,
      scale: currentScale
    });
  }
  const chips = [];
  if (shownView === "Animation" && animations.length) {
    chips.push(
      jsx("div", {
        className: "cs-v-float tl",
        children: animations.map(
          (entry, position) => jsx("button", { "aria-pressed": entry === animation, className: `cs-v-chip${entry === animation ? " on" : ""}`, onClick: () => setAnimationIndex(position), type: "button", children: entry.name }, entry.slot)
        )
      }, "anims"),
      jsxs("div", {
        className: "cs-v-float tr",
        children: [
          jsx("button", { "aria-label": playing ? "Pause" : "Play", className: "cs-v-chip", onClick: () => setPlaying((value) => !value), type: "button", children: jsx(Codicon, { name: playing ? "debug-pause" : "play", size: 12 }) }),
          jsx("span", { className: "cs-v-chip quiet", title: "The speed the game plays it at", children: sprite2?.animSpeed != null && Number(sprite2.animSpeed) < 255 ? `${Math.round(60 / (Number(sprite2.animSpeed) + 1) * 10) / 10} fps` : "Not animated in game" }),
          jsx("button", { "aria-pressed": onion, className: `cs-v-chip${onion ? " on" : ""}`, onClick: () => setOnion((value) => !value), type: "button", children: "Onion skin" })
        ]
      }, "play"),
      frames.length > 1 ? jsx("div", {
        className: "cs-v-float bottom",
        children: frames.map(
          (tiles, position) => jsx("button", {
            "aria-label": `Frame ${position + 1}`,
            "aria-pressed": position === frame,
            className: `cs-v-frame${position === frame ? " on" : ""}`,
            onClick: () => {
              setPlaying(false);
              setFrame(position);
            },
            type: "button",
            children: jsx(SpriteFrameCanvas, { colors, flip: animation.flip, image, scale: Math.max(1, Math.floor(36 / Math.max(sprite2.canvasWidth, sprite2.canvasHeight))), sprite: sprite2, tiles })
          }, position)
        )
      }, "frames") : null
    );
  }
  if (shownView === "In game" && kind !== "cover" && scenes.length) {
    chips.push(
      jsxs("div", {
        className: "cs-v-float tl",
        children: [
          ...scenes.map(
            (entry, position) => jsx("button", { "aria-pressed": entry === scene, className: `cs-v-chip${entry === scene ? " on" : ""}`, onClick: () => setSceneIndex(position), type: "button", children: entry.name }, entry.id ?? position)
          )
        ]
      }, "scenes"),
      jsx("span", { className: "cs-v-float br cs-v-chip quiet", children: "As the scene starts, from the project files" }, "note")
    );
  }
  if (picking && !area) {
    chips.push(jsx("span", { className: "cs-v-float bottom cs-v-chip quiet", children: "Drag on the picture to mark the area to change" }, "hint"));
  }
  if (working) {
    chips.push(
      jsxs("div", {
        className: "cs-v-working",
        children: [jsx("span", { className: "cs-b-spin" }), jsx("span", { children: running ? `${AGENT}: ${stepWords(running)[0]}` : `${AGENT} is working on it` })]
      }, "working")
    );
  }
  const madeBy = asset.step || asset.at ? jsxs("div", {
    className: "cs-col cs-v-sec",
    children: [
      jsx("span", { className: "cs-eyebrow", children: asset.step === "In the reply" ? `Shown by ${AGENT}` : `Made by ${AGENT}` }),
      asset.ask ? jsx("span", { className: "cs-v-quote", children: `“${asset.ask.length > 140 ? `${asset.ask.slice(0, 140)}…` : asset.ask}”` }) : null,
      jsx("span", { className: "cs-faint", children: [asset.at ? timeOfDay(asset.at) : "", asset.step && asset.step !== "In the reply" ? asset.step : ""].filter(Boolean).join(" · ") })
    ]
  }) : null;
  const details = [
    older ? jsxs("div", {
      className: "cs-v-note",
      children: [
        jsx("span", { children: `This is v${shownNumber} from ${versionTime(shownEntry)}. The game uses v${versions.findIndex((entry) => entry.current) + 1}.` }),
        jsxs("div", {
          className: "cs-row",
          style: { gap: 6 },
          children: [
            jsx(Button, { disabled: restoring || working, onClick: () => void restore(), size: "sm", children: restoring ? "Restoring…" : `Restore v${shownNumber}` }),
            jsx(Button, { onClick: () => setPicked(currentId), size: "sm", variant: "ghost", children: "Show the current one" })
          ]
        })
      ]
    }, "older") : null,
    madeBy ? jsx("div", { children: madeBy }, "made") : null,
    kind === "sprite" && info?.palette ? jsxs("div", {
      className: "cs-col cs-v-sec",
      children: [
        jsx("span", { className: "cs-eyebrow", children: "In-game palette" }),
        jsxs("div", {
          className: "cs-row",
          style: { gap: 8 },
          children: [
            jsx("div", { className: "cs-v-pal", children: info.palette.colors.map((color, position) => jsx("button", { onClick: () => void copyColour(color), style: { background: color }, title: `${color}${position === 2 ? " (not used by sprites)" : ""}`, type: "button" }, position)) }),
            info.palette.name ? jsx("span", { className: "cs-tag", children: info.palette.name }) : null
          ]
        }),
        jsxs("label", { className: "cs-v-toggle", children: [jsx("input", { checked: gameColours, onChange: (event) => setGameColours(event.target.checked), type: "checkbox" }), "Show it in these colours"] })
      ]
    }, "palette") : null,
    palette.length ? jsxs("div", {
      className: "cs-col cs-v-sec",
      children: [
        jsx("span", { className: "cs-eyebrow", children: `Colours in the file · ${palette.length}${palette.length >= 32 ? "+" : ""}` }),
        jsx("div", { className: "cs-v-sw", children: palette.map((color) => jsx("button", { onClick: () => void copyColour(color), style: { background: color }, title: `${color} · click to copy`, type: "button" }, color)) })
      ]
    }, "colours") : null,
    checks.length ? jsxs("div", {
      className: "cs-col cs-v-sec",
      children: [
        jsx("span", { className: "cs-eyebrow", children: "Checks" }),
        ...checks.map((check, position) => jsxs("span", { className: `cs-v-check${check.ok ? "" : " bad"}`, children: [jsx(Codicon, { name: check.ok ? "check" : "warning", size: 12 }), check.text] }, position))
      ]
    }, "checks") : null,
    kind === "cover" ? jsxs("div", { className: "cs-col cs-v-sec", children: [jsx("span", { className: "cs-eyebrow", children: "Shown on" }), jsx("span", { className: "cs-v-text", children: "Its Games page card and the Build page" })] }, "shown") : info?.usedIn ? jsxs("div", {
      className: "cs-col cs-v-sec",
      children: [
        jsx("span", { className: "cs-eyebrow", children: "Used in" }),
        ...info.usedIn.length ? info.usedIn.map((use) => jsxs("span", { className: "cs-v-text", children: [jsx("b", { children: use.scene }), ` · ${use.count > 1 ? `${use.count}: ` : ""}${use.as.join(", ")}`] }, use.sceneId)) : [jsx("span", { className: "cs-faint", children: "Not placed in any scene yet" }, "none")]
      ]
    }, "used") : null
  ];
  const change = working || sentAt && progress2.length ? [
    jsxs("div", {
      className: "cs-v-card",
      children: [jsx("span", { className: "cs-faint", children: "You asked" }), jsx("span", { className: "cs-v-text", children: chat?.items?.findLast?.((item) => item.kind === "user")?.text ?? "" })]
    }, "asked"),
    jsxs("div", {
      className: "cs-col cs-v-sec",
      children: [
        jsx("span", { className: "cs-eyebrow", children: "Progress" }),
        ...(progress2.length ? progress2 : []).map(
          (tool) => jsxs("span", {
            className: `cs-v-step ${tool.state}`,
            children: [tool.state === "running" ? jsx("span", { className: "cs-b-spin" }) : jsx(Codicon, { name: tool.state === "failed" ? "error" : "check", size: 12 }), stepWords(tool)[tool.state === "running" ? 0 : 1]]
          }, tool.id)
        ),
        !progress2.length ? jsx("span", { className: "cs-faint", children: "Starting…" }) : null
      ]
    }, "progress"),
    jsx("span", { className: "cs-grow" }, "grow"),
    jsx("span", { className: "cs-faint", children: "You can close this. The new version shows up here and in the chat." }, "close")
  ] : [
    jsx("textarea", {
      className: "cs-v-input",
      disabled: !onSend,
      onChange: (event) => setRequest(event.target.value),
      onKeyDown: (event) => {
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent?.isComposing) {
          event.preventDefault();
          send();
        }
      },
      placeholder: onSend ? `What should ${AGENT} change in ${name}?` : "Open this game’s conversation to ask for changes.",
      ref: input,
      rows: 4,
      value: request
    }, "input"),
    area ? jsxs("div", {
      className: "cs-row cs-v-sec",
      style: { gap: 6 },
      children: [jsx("span", { className: "cs-v-text", children: `Only the marked area · ${area.w}×${area.h}` }), jsx("span", { className: "cs-grow" }), jsx(Button, { onClick: () => setArea(null), size: "sm", variant: "ghost", children: "Clear" })]
    }, "area") : shownView === "Image" || shownView === "Sheet" ? jsx("span", { className: "cs-faint", children: "Drag on the picture to change just one area." }, "area") : null,
    older ? jsx("span", { className: "cs-faint", children: `It starts from v${shownNumber}, the version shown.` }, "from") : null,
    kind === "sprite" || kind === "background" ? jsxs("label", { className: "cs-v-toggle", children: [jsx("input", { checked: rebuild, onChange: (event) => setRebuild(event.target.checked), type: "checkbox" }), "Build and show the game after"] }, "rebuild") : null,
    jsxs(Button, { disabled: !onSend || !request.trim(), onClick: send, size: "sm", children: [`Send to ${AGENT}`, jsx("span", { className: "cs-v-kbd", children: "↵" })] }, "send"),
    jsx("span", { className: "cs-grow" }, "grow"),
    asks.length ? jsxs("div", {
      className: "cs-col cs-v-sec",
      children: [jsx("span", { className: "cs-eyebrow", children: "Asked before" }), ...asks.slice(-4).map((ask, position) => jsx("span", { className: "cs-faint", title: ask, children: `“${ask.length > 80 ? `${ask.slice(0, 80)}…` : ask}”` }, position))]
    }, "asks") : null
  ];
  return jsx("div", {
    className: "cs-b-dim",
    onClick: onClose,
    children: jsxs("div", {
      "aria-label": `${name}, ${VIEWER_KIND[kind] ?? "Image"}`,
      "aria-modal": "true",
      className: "cs-v",
      onClick: (event) => event.stopPropagation(),
      ref: dialog,
      role: "dialog",
      tabIndex: -1,
      children: [
        jsxs("div", {
          className: "cs-v-top",
          children: [
            jsx("span", { className: "cs-eyebrow", children: VIEWER_KIND[kind] ?? "Image" }),
            jsx("b", { className: "cs-v-name", title: path, children: name }),
            jsx("span", {
              className: "cs-faint cs-b-ell",
              title: path,
              children: [
                info?.relative ?? loaded?.relative ?? loaded?.name ?? "",
                loaded ? `${loaded.width}×${loaded.height}` : "",
                kind === "sprite" && sprite2 ? `${animations.length} ${animations.length === 1 ? "animation" : "animations"} of ${sprite2.canvasWidth}×${sprite2.canvasHeight}` : "",
                shownNumber ? `v${shownNumber}` : ""
              ].filter(Boolean).join(" · ")
            }),
            jsx("span", { className: "cs-grow" }),
            views.length > 1 ? jsx("div", { className: "cs-v-seg", role: "tablist", children: views.map((entry) => jsx("button", { "aria-selected": entry === shownView, className: entry === shownView ? "on" : "", onClick: () => setView(entry), role: "tab", type: "button", children: entry }, entry)) }) : null,
            zoomable ? jsxs("div", {
              className: "cs-v-zoom",
              children: [
                jsx("button", { className: `cs-v-chip${zoom === "fit" ? " on" : ""}`, onClick: () => setZoom("fit"), title: "Fit (the biggest whole zoom that fits)", type: "button", children: "Fit" }),
                ...[1, 2, 3, 4, 8].map((step) => jsx("button", { className: `cs-v-chip${zoom === step ? " on" : ""}`, onClick: () => setZoom(step), type: "button", children: `${step}×` }, step)),
                shownView === "Image" || shownView === "Sheet" ? jsx("button", { "aria-pressed": grid, className: `cs-v-chip${grid ? " on" : ""}`, onClick: () => setGrid((value) => !value), title: kind === "sprite" ? "8×16 tile grid" : "8×8 tile grid", type: "button", children: jsx(Codicon, { name: "symbol-numeric", size: 12 }) }) : null
              ]
            }) : null,
            jsx("button", { "aria-label": "Close", className: "cs-b-x", onClick: onClose, type: "button", children: jsx(Codicon, { name: "close", size: 14 }) })
          ]
        }),
        jsxs("div", {
          className: "cs-v-body",
          children: [
            jsxs("div", {
              className: `cs-v-stage${kind === "sprite" && shownView !== "In game" ? " checker" : ""}`,
              children: [
                jsx("div", {
                  className: `cs-v-scroll${picking ? "" : " pannable"}`,
                  onPointerDown: (event) => {
                    const element = stageRef.current;
                    if (picking || event.button !== 0 || !element || element.scrollWidth <= element.clientWidth && element.scrollHeight <= element.clientHeight) {
                      return;
                    }
                    pan.current = { x: event.clientX, y: event.clientY, left: element.scrollLeft, top: element.scrollTop };
                    element.setPointerCapture?.(event.pointerId);
                  },
                  onPointerMove: (event) => {
                    const element = stageRef.current;
                    if (pan.current && element) {
                      element.scrollLeft = pan.current.left - (event.clientX - pan.current.x);
                      element.scrollTop = pan.current.top - (event.clientY - pan.current.y);
                    }
                  },
                  onPointerUp: () => {
                    pan.current = null;
                  },
                  ref: stageRef,
                  children: jsx("div", { className: "cs-v-stage-in", children: stage })
                }),
                ...chips
              ]
            }),
            jsxs("div", {
              className: "cs-v-side",
              children: [
                jsx("div", {
                  className: "cs-v-tabs",
                  role: "tablist",
                  children: ["Details", "Change"].map((entry) => jsxs("button", { "aria-selected": side === entry, className: side === entry ? "on" : "", onClick: () => setSide(entry), role: "tab", type: "button", children: [entry, entry === "Change" && working ? jsx("span", { className: "cs-b-spin" }) : null] }, entry))
                }),
                jsx("div", { className: "cs-v-pane", children: side === "Details" ? details : change })
              ]
            })
          ]
        }),
        jsxs("div", {
          className: "cs-v-foot",
          children: [
            versions.length ? jsxs("div", {
              className: "cs-v-vers",
              children: [
                jsx("span", { className: "cs-eyebrow", children: "Versions" }),
                ...versions.map((entry, position) => jsx(VersionThumb, { entry, number: position + 1, onPick: setPicked, path, selected: entry.id === shownId }, entry.id)),
                working ? jsxs("span", { className: "cs-v-ver pending", title: "Being made now", children: [jsx("span", { className: "cs-b-spin" }), jsx("b", { children: `v${versions.length + 1}` })] }) : null
              ]
            }) : null,
            jsx("span", { className: "cs-grow" }),
            assets.length > 1 ? jsx("span", { className: "cs-faint cs-v-nav", children: `← → other pictures · ${index + 1} of ${assets.length}` }) : null,
            jsxs(Button, { onClick: () => void reveal(), size: "sm", variant: "ghost", children: [jsx(Codicon, { name: "folder-opened", size: 13 }), "Show in folder"] }),
            loaded ? jsxs(Button, { onClick: () => void copyImage(), size: "sm", variant: "ghost", children: [jsx(Codicon, { name: "copy", size: 13 }), "Copy image"] }) : null
          ]
        })
      ]
    })
  });
}

// page/pages/build/transcript/build-card.js
var CHANGE_MARK = { added: "+", changed: "~", removed: "−" };
function BeforeAfter({ path, from, to, actions, onOpen, onSend }) {
  const before = useAsset(path, `reply:${from}`);
  const after = useAsset(path, to ? `reply:${to}` : null);
  const root = useContext(AssetGame);
  const [state, setState] = useState(null);
  if (before.state !== "ok" || !before.asset.earlier || after.state !== "ok") {
    return null;
  }
  const name = after.asset.sprite?.name || after.asset.name;
  const undo = async () => {
    setState("busy");
    try {
      const answer = await callStudioOnly(RPC_ASSET_RESTORE, { path, root, version: before.asset.versionId }, 2e4);
      if (!answer?.ok) {
        throw new Error(answer?.error ?? "It could not be put back.");
      }
      forgetAsset(path, answer.path);
      setState("undone");
    } catch (error) {
      setState(null);
      host.notify({ kind: "error", message: `Could not undo ${name}: ${describeRequestError(error).message}` });
    }
  };
  const side = (loaded, label, now) => jsxs("button", {
    "aria-label": `Look closer at ${label.toLowerCase()} version of ${name}`,
    className: now ? "cs-b-ba-side now" : "cs-b-ba-side",
    onClick: () => onOpen?.({ path, version: now ? to ? `reply:${to}` : null : `reply:${from}`, kind: assetKind(path), step: label }),
    type: "button",
    children: [jsx("span", { className: "cs-b-ba-img", children: jsx(SheetFrame, { loaded }) }), jsx("span", { className: "cs-b-ba-cap", children: label })]
  });
  return jsxs("div", {
    className: "cs-b-ba",
    children: [
      jsxs("div", {
        className: "cs-b-ba-pair",
        children: [side(before.asset, "Before", false), jsx("span", { "aria-hidden": true, className: "cs-b-ba-arrow", children: "→" }), side(after.asset, "After", true)]
      }),
      actions && state !== "kept" ? jsxs("div", {
        className: "cs-row cs-b-ba-acts",
        children: state === "undone" ? [
          jsx("span", { className: "cs-small cs-grow", children: `Put back the earlier ${name}. Rebuild to see it in the game.` }, "t"),
          jsx(Button, { onClick: () => onSend?.(`I put back the earlier version of ${baseName(path)}. Please build the game again.`), size: "sm", children: "Rebuild" }, "r")
        ] : [
          jsx("span", { className: "cs-faint cs-small cs-grow", children: name }, "t"),
          jsx(Button, { disabled: state === "busy", onClick: () => setState("kept"), size: "sm", variant: "outline", children: "Keep" }, "k"),
          jsx(Button, { disabled: state === "busy", onClick: () => void undo(), size: "sm", variant: "ghost", children: state === "busy" ? "Undoing…" : "Undo" }, "u")
        ]
      }) : null
    ]
  });
}
function ChangeList({ changes, root, onOpen }) {
  return jsx("ul", {
    className: "cs-b-bc-changes",
    children: changes.map((change, index) => {
      const path = change.asset ? isAbsolute(change.asset) ? change.asset.replace(/^file:\/\//, "") : joinPath(root, change.asset) : null;
      return jsxs(
        "li",
        {
          "data-kind": change.kind,
          children: [
            jsx("span", { "aria-hidden": true, className: "cs-b-bc-mark", children: CHANGE_MARK[change.kind] ?? "~" }),
            path ? jsx(AssetThumb, { asset: { path, version: "card", kind: assetKind(path), step: change.text }, onOpen, size: "xs" }) : null,
            jsx("span", { children: change.text })
          ]
        },
        index
      );
    })
  });
}
function BuildCard({ build, parts, report, root, took, at, live, isLast, chatBusy, onOpenAsset, onSend, playLabel }) {
  const [details, setDetails] = useState(false);
  const failed = build?.state === "failed";
  const made = madeAssets(parts, root).filter((asset) => asset.kind !== "Image" || /cover\.png$/i.test(asset.path));
  const changes = report?.changes?.length ? report.changes : made.slice(0, 6).map((asset) => ({ kind: "changed", text: baseName(asset.path), asset: asset.path, made: true }));
  const edited = [.../* @__PURE__ */ new Set([...(report?.changes ?? []).filter((change) => change.kind === "changed" && change.asset).map((change) => isAbsolute(change.asset) ? change.asset : joinPath(root, change.asset)), ...made.map((asset) => asset.path)])].filter(Boolean).slice(0, 2);
  const tested = report?.tested ?? [];
  const untested = report?.untested ?? [];
  const notes = report?.notes ?? [];
  const title = report?.title ?? (failed ? "The build didn’t finish" : build?.title ?? "Done");
  const summary = report?.summary ?? (failed ? parts.buildFailed : null);
  const hasFoot = tested.length || untested.length || notes.length || failed;
  return jsxs("div", {
    className: `cs-b-bc${failed ? " bad" : ""}${live ? " live" : ""}`,
    "data-build": build?.n ?? void 0,
    children: [
      jsxs("div", {
        className: "cs-b-bc-head",
        children: [
          build ? jsx("span", { className: `cs-b-bn${failed ? " bad" : live ? " live" : ""}`, children: `#${build.n}` }) : null,
          jsx("b", { className: "cs-b-bc-title", children: title }),
          jsx("span", { className: "cs-faint cs-b-bc-meta", children: [took, at ? timeOfDay(at) : null].filter(Boolean).join(" · ") }),
          jsx("span", { className: "cs-grow" }),
          playLabel
        ]
      }),
      summary ? jsx("p", { className: "cs-b-bc-sum", children: summary }) : null,
      ...edited.map((path) => jsx(BeforeAfter, { actions: isLast && !chatBusy, from: parts.startedAt, onOpen: onOpenAsset, onSend, path, to: parts.endedAt }, `ba:${path}`)),
      changes.length ? jsx(ChangeList, { changes, onOpen: onOpenAsset, root }) : null,
      hasFoot ? jsxs("div", {
        className: "cs-b-bc-foot",
        children: [
          tested.length ? jsxs("span", { children: [jsx("span", { className: "cs-b-ok", children: "✓" }), ` ${tested.length} play-tested`] }) : null,
          untested.length ? jsx("span", { className: "cs-faint", children: `○ ${untested.length} not tested` }) : null,
          notes.length ? jsx("span", { className: "cs-faint", children: `⚠ ${notes.length} ${notes.length === 1 ? "note" : "notes"}` }) : null,
          failed && isLast && !chatBusy ? jsx(Button, { onClick: () => onSend?.("The build failed. Please fix it and build again."), size: "sm", variant: "outline", children: `Ask ${AGENT} to fix it` }) : null,
          jsx("span", { className: "cs-grow" }),
          jsxs("button", {
            "aria-expanded": details,
            className: "cs-b-link",
            onClick: () => setDetails(!details),
            type: "button",
            children: [failed && !tested.length ? "What went wrong" : "Details", jsx(Codicon, { name: details ? "chevron-down" : "chevron-right", size: 11 })]
          })
        ]
      }) : null,
      details ? jsxs("div", {
        className: "cs-b-bc-details",
        children: [
          tested.length ? jsxs("div", { children: [jsx("span", { className: "cs-eyebrow", children: "Play-tested" }), ...tested.map((line, index) => jsxs("p", { children: [jsx("span", { className: "cs-b-ok", children: "✓ " }), line] }, index))] }) : null,
          untested.length ? jsxs("div", { children: [jsx("span", { className: "cs-eyebrow", children: "Not tested" }), ...untested.map((line, index) => jsx("p", { className: "cs-faint", children: `○ ${line}` }, index))] }) : null,
          notes.length ? jsxs("div", { children: [jsx("span", { className: "cs-eyebrow", children: "You might notice" }), ...notes.map((line, index) => jsx("p", { children: line }, index))] }) : null,
          failed && parts.buildFailed ? jsxs("div", { children: [jsx("span", { className: "cs-eyebrow", children: "What went wrong" }), jsx("pre", { className: "cs-b-cmd", children: parts.buildFailed })] }) : null
        ]
      }) : null
    ]
  });
}
function NextSteps({ stored, suggestions }) {
  if (!stored || !suggestions?.length) {
    return null;
  }
  return jsx("div", {
    className: "cs-b-next-steps",
    children: suggestions.map(
      (text2) => jsxs("button", { className: "cs-b-sugg-chip", onClick: () => injectBuildDraft(stored, text2), type: "button", children: [jsx(Codicon, { name: "arrow-small-right", size: 12 }), text2] }, text2)
    )
  });
}

// page/shared/ui/elapsed.js
function Elapsed({ since }) {
  const now = useNow(Boolean(since));
  return since ? clock(now - since) : "";
}

// page/pages/build/transcript/questions.js
var SUGGESTED = /\s*\((recommended|suggested)\)\s*$/i;
function BuildQuestions({ stored, item }) {
  const payload = item.payload ?? {};
  const questions = Array.isArray(payload.questions) && payload.questions.length ? payload.questions : [{ qid: "q0", question: payload.question ?? "", choices: payload.choices ?? [] }];
  const [answers, setAnswers] = useState({});
  const [own, setOwn] = useState({});
  const [sending, setSending] = useState(false);
  const complete = questions.every((question) => answers[question.qid]);
  const pick = (qid, value) => setAnswers((current) => ({ ...current, [qid]: value }));
  const box = useRef(null);
  useEffect(() => {
    const onKey = (event) => {
      const target = event.target;
      if (event.metaKey || event.ctrlKey || event.altKey || target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName ?? "") || target?.isContentEditable) {
        return;
      }
      const number = Number(event.key);
      const open = questions.find((question) => !answers[question.qid]) ?? questions[questions.length - 1];
      const choices = Array.isArray(open?.choices) ? open.choices : [];
      if (number >= 1 && number <= choices.length) {
        event.preventDefault();
        pick(open.qid, choices[number - 1]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [answers]);
  const send = async () => {
    setSending(true);
    try {
      await answerBuildPrompt(stored, item, answers);
    } finally {
      setSending(false);
    }
  };
  return jsxs("div", {
    className: "cs-b-qs",
    ref: box,
    children: [
      ...questions.map(
        (question, number) => jsxs(
          "div",
          {
            className: "cs-b-q",
            children: [
              jsxs("p", {
                className: "cs-b-qt",
                children: [questions.length > 1 ? jsx("span", { className: "cs-faint", children: `${number + 1} of ${questions.length} · ` }) : null, question.question]
              }),
              jsx("div", {
                className: "cs-b-choices",
                children: (Array.isArray(question.choices) ? question.choices : []).map((choice, index) => {
                  const suggested = SUGGESTED.test(choice);
                  const label = choice.replace(SUGGESTED, "");
                  return jsxs(
                    "button",
                    {
                      "aria-pressed": answers[question.qid] === choice,
                      className: "cs-b-choice",
                      onClick: () => pick(question.qid, choice),
                      type: "button",
                      children: [
                        jsx("kbd", { children: index + 1 }),
                        jsx("span", { className: "cs-grow", children: label }),
                        suggested ? jsx("span", { className: "cs-b-sugg", children: "Suggested" }) : null
                      ]
                    },
                    choice
                  );
                })
              }),
              jsx("input", {
                "aria-label": "Your own answer",
                className: "cs-b-own",
                onChange: (event) => {
                  const value = event.target.value;
                  setOwn((current) => ({ ...current, [question.qid]: value }));
                  pick(question.qid, value.trim() ? value : void 0);
                },
                placeholder: "Or type your own answer",
                value: own[question.qid] ?? ""
              })
            ]
          },
          question.qid
        )
      ),
      jsxs("div", {
        className: "cs-row",
        children: [
          jsx(Button, { disabled: !complete || sending, onClick: () => void send(), size: "sm", variant: "outline", children: sending ? "Sending…" : "Send answer" }),
          jsx("span", { className: "cs-faint cs-grow", children: `${AGENT} is waiting for you` }),
          jsx(Button, { onClick: () => openInFullChat(stored), size: "sm", variant: "ghost", children: "Answer in full chat" })
        ]
      })
    ]
  });
}
function BuildPromptCard({ stored, item }) {
  const payload = item.payload ?? {};
  const approval = item.kind === "approval";
  const choices = (Array.isArray(payload.choices) && payload.choices.length ? payload.choices : ["once", "deny"]).filter((choice) => APPROVAL_LABELS[choice]);
  return jsxs("div", {
    className: `cs-b-card ${approval ? "warn" : "ask"}`,
    "data-prompt": "open",
    children: [
      jsxs("div", {
        className: "cs-row",
        children: [
          jsx(Codicon, { name: approval ? "shield" : "comment-discussion", size: 14 }),
          jsx("b", { children: approval ? `${AGENT} needs your OK` : `${AGENT} is asking` })
        ]
      }),
      approval ? jsx("p", { className: "cs-small", children: payload.description || payload.tool_name || "A protected action" }) : null,
      approval && payload.command ? jsx("pre", { className: "cs-b-cmd", children: payload.command }) : null,
      approval ? jsxs("div", {
        className: "cs-row",
        children: [
          ...choices.map(
            (choice) => jsx(Button, { onClick: () => void answerBuildPrompt(stored, item, choice), size: "sm", variant: choice === "deny" ? "ghost" : "outline", children: APPROVAL_LABELS[choice] }, choice)
          ),
          jsx("span", { className: "cs-grow" }),
          jsx(Button, { onClick: () => openInFullChat(stored), size: "sm", variant: "ghost", children: "Answer in full chat" })
        ]
      }) : jsx(BuildQuestions, { item, stored })
    ]
  });
}

// page/pages/build/transcript/worked.js
function StepRow({ tool, assets, onOpenAsset, freshFrom }) {
  const [running, done] = stepWords(tool);
  const live = tool.state === "running";
  const detail = stepDetail(tool);
  const percent = typeof tool.progress?.percent === "number" ? Math.max(0, Math.min(100, tool.progress.percent)) : null;
  return jsxs("div", {
    className: "cs-b-tool",
    "data-state": tool.state,
    children: [
      jsxs("div", {
        className: "cs-b-tool-line",
        children: [
          jsx("span", {
            className: "cs-b-ico",
            children: live ? jsx("i", { className: "cs-b-spin" }) : jsx(Codicon, { name: tool.state === "failed" ? "error" : tool.state === "stopped" ? "debug-stop" : "check", size: 12 })
          }),
          jsx("span", { className: live ? "cs-b-tool-name cs-b-shimmer" : "cs-b-tool-name", children: live ? running : tool.state === "failed" ? `${running} failed` : done }),
          detail ? jsx("span", { className: "cs-b-tool-detail", title: detail, children: detail }) : null,
          jsx("span", { className: "cs-grow" }),
          live ? null : typeof tool.duration === "number" && tool.duration >= 1 ? jsx("span", { className: "cs-b-dur", children: spanWords(tool.duration * 1e3) }) : null
        ]
      }),
      percent != null && live ? jsx("div", { className: "cs-b-bar", children: jsx("i", { style: { width: `${percent}%` } }) }) : null,
      assets.length ? jsx("div", { className: "cs-b-tool-assets", children: jsx(AssetStrip, { assets, freshFrom, onOpen: onOpenAsset }) }) : null
    ]
  });
}
function workedEntry(entry, index, assetsByStep, freshFrom, onOpenAsset) {
  if (entry.type === "step") {
    return jsx(StepRow, { assets: assetsByStep.get(entry.tool.id) ?? [], freshFrom, onOpenAsset, tool: entry.tool }, entry.tool.id ?? `s${index}`);
  }
  if (entry.type === "asked") {
    const answers = entry.item.answers ?? (entry.item.answered && entry.item.answered !== "answered" && entry.item.answered !== "answered elsewhere" ? [entry.item.answered] : []);
    return jsxs(
      "div",
      {
        className: "cs-b-tool",
        "data-state": "done",
        children: [
          jsxs("div", {
            className: "cs-b-tool-line",
            children: [
              jsx("span", { className: "cs-b-ico", children: jsx(Codicon, { name: "check", size: 12 }) }),
              jsx("span", { className: "cs-b-tool-name", children: entry.item.kind === "approval" ? "You answered an approval" : "You answered" })
            ]
          }),
          answers.length ? jsx("div", { className: "cs-b-chips", children: answers.map((answer, position) => jsx("span", { className: "cs-b-chip", children: String(answer).replace(SUGGESTED, "") }, position)) }) : null
        ]
      },
      `a${index}`
    );
  }
  return jsx("p", { className: "cs-b-note", children: entry.item.text }, `n${index}`);
}
function AssetStack({ assets, max = 4 }) {
  const shown = assets.slice(-max);
  return jsx("span", {
    "aria-hidden": true,
    className: "cs-b-stack",
    children: shown.map((asset) => jsx("span", { className: "cs-b-stack-i", children: jsx(AssetImage, { asset }) }, `${asset.path}#${asset.version}`))
  });
}
function SimpleStep({ tool, assets, onOpenAsset, freshFrom }) {
  const [running, done] = stepWords(tool);
  const live = tool.state === "running";
  const failed = tool.state === "failed";
  return jsxs("div", {
    className: "cs-b-tool",
    "data-state": tool.state,
    children: [
      jsxs("div", {
        className: "cs-b-tool-line",
        children: [
          jsx("span", {
            className: "cs-b-ico",
            children: live ? jsx("i", { className: "cs-b-spin" }) : jsx(Codicon, { name: failed ? "error" : tool.state === "stopped" ? "debug-stop" : "check", size: 12 })
          }),
          jsx("span", { className: live ? "cs-b-tool-name cs-b-shimmer" : "cs-b-tool-name", children: live ? `${running}…` : failed ? `${running} failed` : done }),
          failed && tool.info?.error ? jsx("span", { className: "cs-b-tool-detail", title: tool.info.error, children: tool.info.error }) : null
        ]
      }),
      assets.length ? jsx("div", { className: "cs-b-tool-assets", children: jsx(AssetStrip, { assets, freshFrom, onOpen: onOpenAsset }) }) : null
    ]
  });
}
function WorkGroup({ group, live, open, onToggle, assetsByStep, freshFrom, onOpenAsset }) {
  const steps = group.entries.filter((entry) => entry.type === "step").map((entry) => entry.tool);
  const running = steps.some((tool) => tool.state === "running");
  const failed = !running && steps.length > 0 && steps[steps.length - 1].state === "failed";
  const made = steps.flatMap((tool) => (assetsByStep.get(tool.id) ?? []).filter((asset) => !asset.looked && asset.kind !== "Playtest frame"));
  const seconds = steps.reduce((sum, tool) => sum + (typeof tool.duration === "number" ? tool.duration : 0), 0);
  const shown = group.entries.filter((entry) => !(entry.type === "step" && entry.tool.state === "done" && MINOR_STEPS.test(shortTool(entry.tool.name)) && !assetsByStep.get(entry.tool.id)?.length));
  const icon = running ? jsx("i", { className: "cs-b-spin" }) : jsx(Codicon, { name: failed ? "error" : "check", size: 12 });
  return jsxs("div", {
    className: "cs-b-ph",
    "data-group": group.kind,
    "data-open": open ? "true" : "false",
    "data-state": running ? "running" : failed ? "failed" : "done",
    children: [
      jsxs("button", {
        "aria-expanded": open,
        className: "cs-b-ph-head",
        onClick: onToggle,
        type: "button",
        children: [
          jsx("span", { className: "cs-b-ico", children: icon }),
          jsx("span", { className: running && live ? "cs-b-ph-name cs-b-shimmer" : "cs-b-ph-name", children: groupTitle(group, running && live, made.length > 0) }),
          jsx("span", { className: "cs-grow" }),
          made.length && !open ? jsx(AssetStack, { assets: made, max: 3 }) : null,
          jsx("span", { className: "cs-b-ph-meta", children: `${steps.length} ${steps.length === 1 ? "step" : "steps"}${seconds >= 1 ? ` · ${spanWords(seconds * 1e3)}` : ""}` }),
          jsx(Codicon, { name: open ? "chevron-down" : "chevron-right", size: 12 })
        ]
      }),
      open ? jsx("div", {
        className: "cs-b-ph-body",
        children: shown.length ? shown.map(
          (entry, position) => entry.type === "step" ? jsx(SimpleStep, { assets: assetsByStep.get(entry.tool.id) ?? [], freshFrom, onOpenAsset, tool: entry.tool }, entry.tool.id ?? `s${position}`) : workedEntry(entry, `${group.kind}.${position}`, assetsByStep, freshFrom, onOpenAsset)
        ) : jsx("span", { className: "cs-faint cs-small", children: "Only small checks here. Technical shows them." })
      }) : null
    ]
  });
}
var WORKED_MODE = atom("simple");
function Worked({ parts, live, startedAt, endedAt, status, root, onOpenAsset }) {
  const [open, setOpen] = useState(null);
  const [openGroups, setOpenGroups] = useState({});
  const mode = useValue(WORKED_MODE);
  const shown = open ?? live;
  const count = parts.steps.length;
  const freshFrom = live ? Date.now() - 4e3 : null;
  const icon = live ? jsx("i", { className: "cs-b-spin" }) : jsx(Codicon, { name: status === "interrupted" ? "debug-stop" : status === "error" ? "error" : "check", size: 12 });
  const took = startedAt && endedAt ? spanWords(endedAt - startedAt) : null;
  const { groups: allGroups, last } = workGroups(parts.entries);
  const groups = count >= GROUP_MIN_STEPS ? allGroups : [];
  const headline = live ? jsxs("span", { className: "cs-b-shimmer", children: ["Working for ", jsx(Elapsed, { since: startedAt ?? Date.now() })] }) : status === "interrupted" ? `Stopped${took ? ` after ${took}` : ""}` : took ? `Worked for ${took}` : "Worked on it";
  const assetsByStep = /* @__PURE__ */ new Map();
  for (const asset of parts.assets) {
    const list = assetsByStep.get(asset.version) ?? [];
    list.push(asset);
    assetsByStep.set(asset.version, list);
  }
  const made = madeAssets(parts, root);
  const latest = live ? parts.assets[parts.assets.length - 1] : null;
  const gist = !live && allGroups.length > 1 ? allGroups.filter((group) => GIST_WORDS[group.kind]).map((group) => GIST_WORDS[group.kind]) : [];
  const groupOpen = (group, index) => openGroups[group.kind] ?? (live && group.kind === last);
  return jsxs("div", {
    className: `cs-b-wk${live ? " live" : ""}`,
    "data-open": shown ? "true" : "false",
    children: [
      jsxs("div", {
        className: "cs-b-wk-row",
        children: [
          jsxs("button", {
            "aria-expanded": shown,
            className: "cs-b-wk-head",
            onClick: () => setOpen(!shown),
            type: "button",
            children: [
              jsx("span", { className: `cs-b-ico ${status ?? ""}`, children: icon }),
              jsx("b", { children: headline }),
              gist.length ? jsx("span", { className: "cs-faint cs-b-gist", children: `· ${gist.join(", ")}` }) : count ? jsx("span", { className: "cs-faint", children: `· ${count} ${count === 1 ? "step" : "steps"}` }) : null,
              jsx(Codicon, { name: shown ? "chevron-down" : "chevron-right", size: 12 })
            ]
          }),
          made.length && !shown ? jsxs("button", {
            "aria-label": `See the ${made.length === 1 ? "picture" : `${made.length} pictures`} this made`,
            className: "cs-b-wk-assets",
            onClick: () => onOpenAsset?.(made[0]),
            type: "button",
            children: [jsx(AssetStack, { assets: made }), jsx("span", { children: `${made.length} ${made.length === 1 ? "asset" : "assets"}` })]
          }) : null
        ]
      }),
      jsx("div", {
        className: "cs-b-wk-body",
        children: jsxs("div", {
          className: `cs-b-wk-inner${mode === "simple" && groups.length > 1 ? " phased" : ""}`,
          children: [
            shown && count ? jsx("div", {
              className: "cs-b-wk-mode",
              children: jsx("div", {
                "aria-label": "How much detail",
                className: "cs-v-seg",
                role: "tablist",
                children: [
                  ["simple", "Simple"],
                  ["technical", "Technical"]
                ].map(
                  ([key, label]) => jsx("button", { "aria-selected": mode === key, className: mode === key ? "on" : "", onClick: () => WORKED_MODE.set(key), role: "tab", type: "button", children: label }, key)
                )
              })
            }, "mode") : null,
            ...mode === "simple" && groups.length > 1 ? [jsx("div", { className: "cs-b-phases", children: groups.map(
              (group, index) => jsx(
                WorkGroup,
                {
                  assetsByStep,
                  freshFrom,
                  group,
                  live,
                  onOpenAsset,
                  onToggle: () => setOpenGroups((current) => ({ ...current, [group.kind]: !groupOpen(group, index) })),
                  open: groupOpen(group, index)
                },
                group.kind
              )
            ) }, "groups")] : mode === "simple" ? parts.entries.map(
              (entry, index) => entry.type === "step" ? jsx(SimpleStep, { assets: assetsByStep.get(entry.tool.id) ?? [], freshFrom, onOpenAsset, tool: entry.tool }, entry.tool.id ?? `s${index}`) : workedEntry(entry, index, assetsByStep, freshFrom, onOpenAsset)
            ) : parts.entries.map((entry, index) => workedEntry(entry, index, assetsByStep, freshFrom, onOpenAsset)),
            live && !parts.running && !parts.prompts.length ? jsx("div", { className: "cs-b-tool cs-b-next", children: jsx("span", { className: "cs-b-shimmer", children: "Thinking about the next step…" }) }, "next") : null,
            latest ? jsx(LatestAsset, { asset: latest, onOpen: onOpenAsset }, "latest") : null
          ]
        })
      })
    ]
  });
}

// page/pages/build/transcript/turn-view.js
function TurnView({ turn, live, turnStartedAt = null, previousModel = null, chatBusy, latestBuild, build = null, game, root, ctx, stored, playerOpen, onPlay, onClosePlayer, onOpenAsset, onSend, isLast }) {
  const parts = turnParts(turn, root);
  const user = turn.user;
  const end = parts.end;
  const agentAt = end?.at ?? null;
  const hasAgent = live || turn.items.length > 0;
  const startedAt = user?.at ?? end?.startedAt ?? null;
  const showWorked = parts.entries.length > 0 || live && !parts.intro.length;
  const viewerAssets = [...parts.assets];
  for (const asset of replyAssets([...parts.intro, ...parts.outro], root)) {
    if (!viewerAssets.some((entry) => entry.path === asset.path && entry.version === asset.version)) {
      viewerAssets.push(asset);
    }
  }
  if (user?.text) {
    viewerAssets.forEach((asset, position) => {
      viewerAssets[position] = { ...asset, ask: user.text };
    });
  }
  const viewerRef = useRef(viewerAssets);
  viewerRef.current = viewerAssets;
  const openAsset = useCallback((asset) => onOpenAsset(viewerRef.current, asset), [onOpenAsset]);
  const playable = Boolean(game && game.webExport && playableSha(game));
  const frame = [...parts.assets].reverse().find((asset) => asset.kind === "Playtest frame") ?? null;
  const report = parts.report;
  const carded = !live && (build || report);
  let play = null;
  let playLabel = null;
  if (latestBuild && game) {
    if (chatBusy) {
      playLabel = carded ? jsx("span", { className: "cs-faint cs-small", children: `Playable again when ${AGENT} finishes` }) : null;
    } else if (!playable) {
      play = jsx(PlayCard, { frame, game, state: "unplayable" });
    } else if (playerOpen) {
      play = jsx(InlinePlayer, { build, ctx, game, note: parts.note, onClose: onClosePlayer, report, stored }, `player:${game.id}`);
    } else {
      play = jsx(PlayCard, { build: playsBuild(game, build) ? build.n : null, frame, game, note: parts.note, onPlay, state: "ready" });
    }
  } else if (build?.state === "built" && !live) {
    playLabel = jsx("span", { className: "cs-faint cs-small", children: "Earlier build" });
  }
  const took = startedAt && end?.at ? spanWords(end.at - startedAt) : null;
  const card = carded ? jsx(BuildCard, {
    at: agentAt,
    build,
    chatBusy,
    isLast,
    onOpenAsset: openAsset,
    onSend,
    parts: { ...parts, startedAt: startedAt ?? null, endedAt: end?.at ?? null },
    playLabel,
    report,
    root,
    took
  }) : null;
  const outro = parts.outro.map((item, index) => jsx(AgentText, { item, onOpenAsset: openAsset, root }, `o${index}`));
  return jsxs("section", {
    className: "cs-b-turn",
    "data-live": live ? "true" : void 0,
    "data-turn": turn.key,
    children: [
      user ? jsxs("div", {
        className: "cs-b-user",
        children: [
          user.attachments?.length ? jsx("div", { className: "cs-b-chips", children: user.attachments.map((item) => jsx(AttachmentChip, { item }, attachmentKey(item))) }) : null,
          jsx("span", { children: user.text })
        ]
      }) : null,
      hasAgent ? jsxs("div", {
        className: "cs-b-her",
        children: [
          // No name over the reply (it is the agent's thread); a line only where the model changed.
          user?.model && previousModel && (user.model !== previousModel.model || (user.effort ?? "") !== (previousModel.effort ?? "")) ? jsx("div", { className: "cs-b-who", children: `${modelName(user.model).name}${user.effort ? ` · ${effortLabel(user.effort)}` : ""}` }) : null,
          ...parts.intro.map((item, index) => jsx(AgentText, { item, onOpenAsset: openAsset, root }, `i${index}`)),
          showWorked ? jsx(Worked, { endedAt: end?.at ?? null, live, onOpenAsset: openAsset, parts, root, startedAt: live ? turnStartedAt ?? startedAt ?? Date.now() : startedAt, status: end?.status ?? null }, "worked") : null,
          // With a report the card says it all and the reply is a line after it; without one the reply
          // is the words, and the card (a build) follows them.
          // Questions and approvals are asked in the message box, not here.
          ...report ? [card, carded ? play : null, ...outro] : [...outro, card, carded ? play : null],
          ...parts.errors.map(
            (item, index) => jsxs(
              "div",
              {
                className: "cs-b-card bad",
                children: [
                  jsxs("div", { className: "cs-row", children: [jsx(Codicon, { name: "error", size: 14 }), jsx("b", { children: "Something went wrong" })] }),
                  jsx("p", { className: "cs-small", children: item.text }),
                  isLast && !chatBusy && item.resend ? jsx("div", { className: "cs-row", children: jsx(Button, { onClick: () => onSend(item.resend.text, item.resend.shown, item.resend.attachments ?? []), size: "sm", variant: "outline", children: "Try again" }) }) : null
                ]
              },
              `e${index}`
            )
          ),
          parts.buildFailed && !live && !carded ? jsxs("div", {
            className: "cs-b-card bad",
            children: [
              jsxs("div", { className: "cs-row", children: [jsx(Codicon, { name: "error", size: 14 }), jsx("b", { children: "The build failed" })] }),
              jsx("p", { className: "cs-small", children: parts.buildFailed }),
              isLast && !chatBusy ? jsx("div", { className: "cs-row", children: jsx(Button, { onClick: () => onSend("The build failed. Please fix it and build again."), size: "sm", variant: "outline", children: `Ask ${AGENT} to fix it` }) }) : null
            ]
          }) : null,
          end?.status === "interrupted" && isLast && !chatBusy ? jsxs("div", {
            className: "cs-b-stopped",
            children: [
              jsx("span", { children: "You stopped it here. Nothing is lost, and the last build still plays." }),
              jsx(Button, { onClick: () => onSend("Please carry on where you left off."), size: "sm", variant: "outline", children: "Carry on" })
            ]
          }) : null,
          carded ? null : play,
          isLast && !chatBusy && !live ? jsx(NextSteps, { stored, suggestions: report?.suggestions }) : null
        ]
      }) : null
    ]
  });
}
var sameItems = (a, b) => a.length === b.length && a.every((item, index) => item === b[index]);
var TurnMemo = memo(
  TurnView,
  (previous, next) => sameItems(previous.turn.items, next.turn.items) && previous.turn.user === next.turn.user && previous.live === next.live && previous.turnStartedAt === next.turnStartedAt && previous.previousModel?.model === next.previousModel?.model && previous.previousModel?.effort === next.previousModel?.effort && previous.chatBusy === next.chatBusy && previous.latestBuild === next.latestBuild && previous.build === next.build && previous.isLast === next.isLast && previous.playerOpen === next.playerOpen && previous.root === next.root && previous.stored === next.stored && (!next.latestBuild || previous.game === next.game) && previous.onOpenAsset === next.onOpenAsset
);

// page/pages/build/transcript/transcript.js
var TURN_PAGE = 40;
function Transcript({ ctx, chat, stored, game, playerOpen, onPlay, onClosePlayer, onSend, empty, focusTurn = null }) {
  const items = chat?.items ?? [];
  const turns = useMemo(() => deriveTurns(items), [items]);
  const buildCache = useRef(/* @__PURE__ */ new Map());
  const builds = useMemo(() => {
    const byIndex = /* @__PURE__ */ new Map();
    for (const build of buildHistory(turns)) {
      const sig = JSON.stringify(build);
      const known = buildCache.current.get(build.key);
      const kept = known && known.sig === sig ? known.build : build;
      buildCache.current.set(build.key, { sig, build: kept });
      byIndex.set(build.index, kept);
    }
    return byIndex;
  }, [turns]);
  const root = useContext(AssetGame);
  const scroller = useRef(null);
  const stuck = useRef(true);
  const [behind, setBehind] = useState(false);
  const [limit, setLimit] = useState(TURN_PAGE);
  const [viewer, setViewer] = useState(null);
  const busy = Boolean(chat?.busy);
  useLayoutEffect(() => {
    stuck.current = true;
    setLimit(TURN_PAGE);
    setBehind(false);
    setViewer(null);
  }, [stored]);
  const keepFromBottom = useRef(null);
  useLayoutEffect(() => {
    const element = scroller.current;
    if (!element) {
      return;
    }
    if (keepFromBottom.current != null) {
      element.scrollTop = element.scrollHeight - keepFromBottom.current;
      keepFromBottom.current = null;
    } else if (stuck.current) {
      element.scrollTop = element.scrollHeight;
    } else {
      setBehind(true);
    }
  });
  useEffect(() => {
    const element = scroller.current;
    const column = element?.firstElementChild;
    if (!column || typeof ResizeObserver !== "function") {
      return void 0;
    }
    const observer = new ResizeObserver(() => {
      if (stuck.current && keepFromBottom.current == null) {
        element.scrollTop = element.scrollHeight;
      }
    });
    observer.observe(column);
    return () => observer.disconnect();
  }, [stored]);
  const onScroll = () => {
    const element = scroller.current;
    if (!element) {
      return;
    }
    const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 64;
    stuck.current = atBottom;
    if (atBottom && behind) {
      setBehind(false);
    }
  };
  const jump = () => {
    const element = scroller.current;
    stuck.current = true;
    setBehind(false);
    element?.scrollTo?.({ behavior: "smooth", top: element.scrollHeight });
  };
  const focused = useRef(null);
  useEffect(() => {
    if (!focusTurn || focused.current === focusTurn.seq) {
      return void 0;
    }
    const index = turns.findIndex((turn) => turn.key === focusTurn.key);
    if (index === -1) {
      return void 0;
    }
    if (index < turns.length - limit) {
      setLimit(turns.length - index);
      return void 0;
    }
    const node = scroller.current?.querySelector?.(`[data-turn="${focusTurn.key}"]`);
    if (!node) {
      return void 0;
    }
    focused.current = focusTurn.seq;
    stuck.current = false;
    node.scrollIntoView?.({ behavior: "smooth", block: "start" });
    node.setAttribute("data-flash", "true");
    const id = setTimeout(() => node.removeAttribute("data-flash"), 1600);
    return () => clearTimeout(id);
  }, [focusTurn?.seq, limit]);
  const openAsset = useCallback(
    (assets, asset) => setViewer({ assets, index: Math.max(0, assets.findIndex((entry) => entry === asset || entry.path === asset.path && entry.version === asset.version)) }),
    []
  );
  const latestBuild = useMemo(() => {
    for (let index = turns.length - 1; index >= 0; index -= 1) {
      if (turnBuilt(turns[index])) {
        return index;
      }
    }
    return -1;
  }, [turns]);
  const first = Math.max(0, turns.length - limit);
  const lastIndex = turns.length - 1;
  const modelBefore = useMemo(() => {
    const result = [];
    let seen = null;
    turns.forEach((turn, index) => {
      result[index] = seen;
      if (turn.user?.model) {
        seen = { model: turn.user.model, effort: turn.user.effort ?? "" };
      }
    });
    return result;
  }, [turns]);
  const playableGame = Boolean(game && game.webExport && playableSha(game));
  return jsxs("div", {
    className: "cs-b-txwrap",
    children: [
      jsx("div", {
        className: "cs-b-tx",
        onScroll,
        ref: scroller,
        children: jsxs("div", {
          className: "cs-b-col",
          children: [
            first > 0 ? jsx("div", { className: "cs-b-earlier", children: jsx(Button, {
              onClick: () => {
                const element = scroller.current;
                keepFromBottom.current = element ? element.scrollHeight - element.scrollTop : null;
                setLimit((value) => value + TURN_PAGE);
              },
              size: "sm",
              variant: "ghost",
              children: `Show ${Math.min(first, TURN_PAGE)} earlier messages`
            }) }, "earlier") : null,
            !turns.length ? empty : null,
            ...turns.slice(first).map((turn, offset) => {
              const index = first + offset;
              return jsx(
                TurnMemo,
                {
                  build: builds.get(index) ?? null,
                  chatBusy: busy,
                  ctx,
                  game: index === latestBuild ? game : null,
                  isLast: index === lastIndex,
                  latestBuild: index === latestBuild,
                  live: busy && index === lastIndex,
                  turnStartedAt: busy && index === lastIndex ? chat?.turnStartedAt ?? null : null,
                  previousModel: modelBefore[index] ?? null,
                  onClosePlayer,
                  onOpenAsset: openAsset,
                  onPlay,
                  onSend,
                  playerOpen: index === latestBuild && playerOpen,
                  root,
                  stored,
                  turn
                },
                turn.key
              );
            }),
            ...(chat?.queued ?? []).map(
              (item, index) => jsxs(
                "div",
                {
                  className: "cs-b-user queued",
                  children: [
                    jsx("span", { className: "cs-b-qlabel", children: chat.lost?.length ? "Waiting · sent when you continue" : `Queued · ${AGENT} reads this when it finishes` }),
                    jsx("span", { children: item.text })
                  ]
                },
                `q${index}`
              )
            ),
            chat?.lost?.length && !busy ? jsx(LostTurnCard, { chat, stored }, "lost") : null,
            // A playable game whose conversation has not built it (it was built elsewhere): play it here, once the
            // agent is not working.
            latestBuild === -1 && playableGame && turns.length && !busy ? jsx("div", {
              className: "cs-b-her",
              children: playerOpen ? jsx(InlinePlayer, { ctx, game, note: null, onClose: onClosePlayer, stored }, `player:${game.id}`) : jsx(PlayCard, { game, onPlay, state: "ready" })
            }) : null
          ]
        })
      }),
      behind ? jsxs("button", { className: "cs-b-jump", onClick: jump, type: "button", children: [jsx(Codicon, { name: "arrow-down", size: 12 }), "Latest"] }) : null,
      viewer ? jsx(AssetViewer, {
        assets: viewer.assets,
        chat,
        ctx,
        game,
        index: viewer.index,
        onClose: () => setViewer(null),
        onIndex: (index) => setViewer((current) => ({ ...current, index })),
        onSend: stored ? onSend : null,
        root
      }) : null
    ]
  });
}
function LostTurnCard({ chat, stored }) {
  const waiting = chat.queued?.length ?? 0;
  const updating = useUpdating();
  return jsxs("div", {
    className: "cs-b-card warn",
    children: [
      jsxs("div", { className: "cs-row", children: [jsx(Codicon, { name: "debug-pause", size: 14 }), jsx("b", { children: `${AGENT} stopped partway through` })] }),
      jsx("p", {
        className: "cs-small",
        children: `Hermes restarted while ${AGENT} was working, so its last turn did not finish. What it already made is kept. ${waiting ? `Continue to send your ${waiting === 1 ? "waiting message" : `${waiting} waiting messages`}.` : `Continue to have ${AGENT} pick up where it stopped.`}`
      }),
      chat.lostFailure ? jsx("p", { className: "cs-small", children: chat.lostFailure }) : null,
      jsx("div", {
        className: "cs-row",
        children: jsx(Button, { disabled: Boolean(chat.resuming || updating), onClick: () => void resumeBuildChat(stored), size: "sm", children: chat.resuming ? "Continuing…" : "Continue" })
      })
    ]
  });
}

// page/pages/build/binding.js
async function buildRpc(params) {
  try {
    const answer = await callStudioOnly(RPC_BUILD, params);
    if (answer && answer.ok === false) {
      throw Object.assign(new Error(answer.error || "The backend refused."), { code: answer.code });
    }
    return answer;
  } catch (error) {
    if (describeRequestError(error).notLoaded) {
      return null;
    }
    throw error;
  }
}
function newGamePrompt({ name, idea, plan }) {
  const what = idea.trim() || "a small game";
  const title = name.trim();
  return plan ? `Use hermretro to help me plan a new Game Boy Color game${title ? ` called "${title}"` : ""}: ${what}. Interview me briefly, then create the project, and write the game brief, backlog and test plan into it before building anything.` : `Use hermretro to make a new Game Boy Color game${title ? ` called "${title}"` : ""}: ${what}. Ask me a few quick questions first, then show me a list of what you will make and wait for my approval. Once I approve it, create the project, save the list in it as docs/game/FIRST-BUILD.md, build the whole game and show it to me in the emulator.`;
}

// page/pages/build/builds-menu.js
function BuildPill({ builds, chat, game }) {
  const last = builds[builds.length - 1] ?? null;
  const good = [...builds].reverse().find((build) => build.state === "built") ?? null;
  let tone = "quiet";
  let label;
  if (chat?.busy) {
    return jsxs("span", {
      className: "cs-b-pill busy",
      children: [jsx("i", { className: "cs-b-spin" }), "Working · ", jsx(Elapsed, { since: chat.turnStartedAt ?? Date.now() })]
    });
  }
  if (!game) {
    label = "Setting up";
  } else if (last?.state === "failed") {
    tone = "bad";
    label = `Build #${last.n} didn’t finish`;
  } else if (game.state === "changed") {
    tone = "warn";
    label = good ? `Edited since build #${good.n}` : "Edited since the last build";
  } else if (good) {
    tone = "good";
    label = `Build #${good.n} · up to date`;
  } else if (game.state === "ready") {
    tone = "good";
    label = "Built · up to date";
  } else if (game.state === "failed") {
    tone = "bad";
    label = "The last build failed";
  } else {
    label = "No builds yet";
  }
  return jsxs("span", { className: `cs-b-pill ${tone}`, children: [tone === "quiet" ? null : jsx("i", { className: "cs-b-pill-dot" }), label] });
}
function snapshotFor(build, snapshots) {
  if (!build.endAt || !Array.isArray(snapshots)) {
    return null;
  }
  const from = (build.startAt ?? build.endAt - 36e5) - 2e3;
  const to = build.endAt + 5e3;
  let found = null;
  for (const snap of snapshots) {
    const times = [snap.at, ...Array.isArray(snap.builds) ? snap.builds : []].filter((value) => typeof value === "number");
    for (const time of times) {
      if (time >= from && time <= to && (!found || time > found.time)) {
        found = { id: String(snap.id), time };
      }
    }
  }
  return found?.id ?? null;
}
function BuildsMenu({ builds, busy, game, onShow, onRestore }) {
  const [open, setOpen] = useState(false);
  const [snapshots, setSnapshots] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [working, setWorking] = useState(false);
  const wrap = useRef(null);
  useEffect(() => {
    if (!open) {
      setConfirm(null);
      return void 0;
    }
    let live = true;
    callStudioOnly(RPC_BUILDS, { game: game.id }, 2e4).then((answer) => live && setSnapshots(answer?.ok && Array.isArray(answer.builds) ? answer.builds : false)).catch(() => live && setSnapshots(false));
    const onDown = (event) => {
      if (wrap.current && !wrap.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      live = false;
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, game.id]);
  const newest = builds[builds.length - 1] ?? null;
  const playingBuild = [...builds].reverse().find((build) => build.state === "built") ?? null;
  const rows = [...builds].reverse();
  return jsxs("div", {
    className: "cs-b-swwrap",
    ref: wrap,
    children: [
      jsxs(Button, {
        "aria-expanded": open,
        "aria-haspopup": "menu",
        onClick: () => setOpen(!open),
        size: "sm",
        variant: open ? "secondary" : "ghost",
        children: [jsx(Codicon, { name: "history", size: 13 }), jsx("span", { className: "cs-lbl", children: "Builds" }), builds.length ? jsx("span", { className: "cs-faint", children: builds.length }) : null, jsx(Codicon, { name: "chevron-down", size: 11 })]
      }),
      open ? jsxs("div", {
        className: "cs-b-sw-pop cs-b-builds",
        role: "menu",
        children: [
          jsx("span", { className: "cs-eyebrow", children: "Builds" }),
          rows.length ? jsx("div", {
            className: "cs-b-sw-list",
            children: rows.map((build) => {
              const current = build === newest;
              const playing = build === playingBuild;
              const snapshot = snapshotFor(build, snapshots);
              const restorable = build.state === "built" && !(playing && current && game.state !== "changed");
              return jsxs(
                "div",
                {
                  className: current ? "cs-b-brow on" : "cs-b-brow",
                  children: [
                    jsx("span", { className: `cs-b-bn${build.state === "failed" ? " bad" : current ? "" : " old"}`, children: `#${build.n}` }),
                    jsxs("span", {
                      className: "cs-col cs-grow",
                      children: [
                        jsx("b", { children: build.title }),
                        jsx("small", {
                          children: [build.endAt ? timeOfDay(build.endAt) : null, build.state === "failed" ? "didn’t finish" : playing ? game.state === "changed" ? "playing now · edited since" : "playing now" : null].filter(Boolean).join(" · ")
                        })
                      ]
                    }),
                    confirm === build.key ? jsxs("span", {
                      className: "cs-b-brow-acts",
                      children: [
                        jsx(Button, {
                          disabled: working,
                          onClick: async () => {
                            setWorking(true);
                            const done = await onRestore(build, snapshot);
                            setWorking(false);
                            if (done) {
                              setOpen(false);
                            }
                          },
                          size: "sm",
                          children: working ? "Restoring…" : `Restore #${build.n}`
                        }),
                        jsx(Button, { disabled: working, onClick: () => setConfirm(null), size: "sm", variant: "ghost", children: "Cancel" })
                      ]
                    }) : jsxs("span", {
                      className: "cs-b-brow-acts",
                      children: [
                        jsx(Button, {
                          onClick: () => {
                            setOpen(false);
                            onShow(build.key);
                          },
                          size: "sm",
                          variant: "ghost",
                          children: "Show"
                        }),
                        restorable ? jsx(Tip, {
                          label: busy ? `Wait until ${AGENT} finishes` : snapshot ? `Put the game back to build #${build.n}` : snapshots === null ? "Looking for this build’s files…" : "This build’s files were not kept",
                          children: jsx("span", {
                            style: { display: "inline-flex" },
                            children: jsx(Button, { disabled: busy || !snapshot, onClick: () => setConfirm(build.key), size: "sm", variant: "outline", children: "Restore" })
                          })
                        }) : null
                      ]
                    })
                  ]
                },
                build.key
              );
            })
          }) : jsx("p", { className: "cs-b-sw-empty cs-small cs-faint", children: `No builds in this conversation yet. ${AGENT} builds the game after each change.` }),
          jsx("p", {
            className: "cs-b-sw-foot",
            children: confirm ? "The game as it is now is saved first, then HermRetro builds the restored files as a new build." : "Restore makes a new build from an earlier one. Nothing is deleted."
          })
        ]
      }) : null
    ]
  });
}

// page/pages/build/composer/provider-notice.js
var PROVIDERS_HREF = "/settings?tab=providers";
function noProviderReady(data) {
  return Boolean(data && Array.isArray(data.providers) && !data.providers.some((item) => item?.authenticated && Array.isArray(item.models) && item.models.length));
}
function ProviderNotice() {
  const gateway = useValue(host.state.gateway);
  const options = useQuery({
    queryKey: [ID, "models", "profile"],
    queryFn: () => chatRequest("model.options", {}, 3e4),
    enabled: gateway === "open",
    staleTime: 5 * 6e4,
    // Asked again each time New Game shows (coming back from Settings after signing in), and silent until it answers:
    // the answer from before the sign-in is not shown again.
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
    retry: 1
  });
  if (options.isFetching || !noProviderReady(options.data)) {
    return null;
  }
  return jsxs("div", {
    className: "cs-b-provider",
    role: "status",
    children: [
      jsx(Codicon, { name: "warning", size: 14 }),
      jsxs("span", {
        className: "cs-grow",
        children: [
          jsx("b", { children: `No model provider is signed in for the ${STUDIO_PROFILE} profile yet.` }),
          ` ${AGENT} needs one to answer. Your idea stays here until you send it.`,
          // Settings keep the last "Applies to" choice, whichever profile the app is on.
          ` In Settings › Providers, check that “Applies to” is ${STUDIO_PROFILE}.`
        ]
      }),
      jsxs(Button, {
        onClick: () => host.navigate?.(PROVIDERS_HREF),
        size: "sm",
        variant: "outline",
        children: [jsx(Codicon, { name: "settings-gear", size: 14 }), "Open provider settings"]
      })
    ]
  });
}

// page/pages/build/new-game-draft.js
var NEW_GAME_DRAFT = atom({ idea: "", plan: false, seq: 0, rev: 0 });
var NEW_GAME_STARTING = atom(false);
var KEY3 = "buildNewGame";
var storage = null;
var clean2 = (value) => ({
  idea: typeof value?.idea === "string" ? value.idea : "",
  plan: value?.plan === true,
  seq: Number.isFinite(value?.seq) ? value.seq : 0,
  rev: Number.isFinite(value?.rev) ? value.rev : 0
});
function save(draft) {
  try {
    storage?.set(KEY3, draft.idea || draft.plan ? { idea: draft.idea, plan: draft.plan } : null);
  } catch {
  }
}
function restoreNewGameDraft(ctx) {
  storage = ctx?.storage ?? null;
  try {
    const saved = storage?.get(KEY3, null);
    if (saved && typeof saved === "object") {
      NEW_GAME_DRAFT.set({ ...clean2(saved), seq: NEW_GAME_DRAFT.get().seq, rev: NEW_GAME_DRAFT.get().rev });
    }
  } catch {
  }
}
function editNewGameDraft(change) {
  const current = NEW_GAME_DRAFT.get();
  const next = { ...current, ...change, rev: current.rev + 1 };
  NEW_GAME_DRAFT.set(next);
  save(next);
}
function clearNewGameDraft(rev) {
  if (NEW_GAME_DRAFT.get().rev === rev) {
    editNewGameDraft({ idea: "", plan: false });
  }
}
function takeFirstIdea({ idea = "", plan = false } = {}, ctx) {
  const words = String(idea ?? "").trim();
  const current = NEW_GAME_DRAFT.get();
  const kept = current.idea.trim();
  const merged = !words || kept.includes(words) ? current.idea : kept ? `${kept}

${words}` : words;
  storage ??= ctx?.storage ?? null;
  try {
    ctx?.storage?.set("buildSelected", "new");
  } catch {
  }
  const next = { idea: merged, plan: plan === true, seq: current.seq + 1, rev: current.rev + 1 };
  NEW_GAME_DRAFT.set(next);
  save(next);
}

// page/pages/build/new-game.js
var NEW_GAME_MODES = [
  { id: "build", title: "Build it", text: `A few quick questions, then ${AGENT} makes the game and shows it to you in the emulator.`, ends: "Ends with a game you can play" },
  { id: "plan", title: "Plan first", text: "A short interview, then a brief, backlog and test plan. Nothing is built until you say so.", ends: "Ends with a plan to review" }
];
var focusedSeq = 0;
function BuildNewGame({ onStart, picker = null, updating = false }) {
  const draft = useValue(NEW_GAME_DRAFT);
  const idea = draft.idea;
  const mode = draft.plan ? "plan" : "build";
  const setIdea = (value) => editNewGameDraft({ idea: value });
  const setMode = (value) => editNewGameDraft({ plan: value === "plan" });
  const busy = useValue(NEW_GAME_STARTING);
  const box = useRef(null);
  useEffect(() => {
    const element = box.current;
    if (draft.seq && draft.seq !== focusedSeq && element) {
      focusedSeq = draft.seq;
      element.focus?.();
      element.setSelectionRange?.(element.value.length, element.value.length);
    }
  }, [draft.seq]);
  useLayoutEffect(() => {
    const element = box.current;
    if (element) {
      element.style.height = "auto";
      element.style.height = `${Math.min(Math.max(element.scrollHeight, 66), 220)}px`;
    }
  }, [idea]);
  const start = async () => {
    if (NEW_GAME_STARTING.get() || !idea.trim() || updating) {
      return;
    }
    const { rev } = NEW_GAME_DRAFT.get();
    NEW_GAME_STARTING.set(true);
    try {
      if (await onStart({ idea, name: "", plan: mode === "plan" }) === true) {
        clearNewGameDraft(rev);
      }
    } finally {
      NEW_GAME_STARTING.set(false);
    }
  };
  const onModeKey = (event) => {
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      const next = mode === "build" ? "plan" : "build";
      setMode(next);
      event.currentTarget.parentElement?.querySelector(`[data-mode="${next}"]`)?.focus?.();
    }
  };
  return jsxs("section", {
    className: "cs-b-new",
    children: [
      jsxs("h1", { className: "cs-word cs-title", children: ["What are we ", jsx("span", { className: "cs-accent", children: "making?" })] }),
      jsxs("div", {
        className: "cs-b-comp",
        children: [
          jsx("textarea", {
            "aria-label": "Your game idea",
            disabled: busy,
            onChange: (event) => setIdea(event.target.value),
            onKeyDown: (event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent?.isComposing) {
                event.preventDefault();
                void start();
              }
            },
            placeholder: "A lighthouse keeper who has to keep the lamp lit through one stormy night…",
            ref: box,
            rows: 3,
            value: idea
          }),
          jsxs("div", {
            className: "cs-b-comp-row",
            children: [
              picker,
              jsx("span", { className: "cs-grow" }),
              jsx("button", {
                "aria-label": mode === "plan" ? "Start planning" : "Start building",
                className: "cs-b-send",
                disabled: busy || updating || !idea.trim(),
                onClick: () => void start(),
                title: updating ? "hermretro is updating. You can start in a moment." : mode === "plan" ? "Start planning" : "Start building",
                type: "button",
                children: [jsx(Codicon, { name: "arrow-up", size: 14 }, "icon"), jsx("span", { className: "cs-sr", children: busy ? "Starting…" : "Start" }, "label")]
              })
            ]
          })
        ]
      }),
      // Right under the box, where it is seen before sending (not under the cards, where the shelf can cover it).
      jsx(ProviderNotice, {}, "providers"),
      jsx("div", {
        "aria-label": "How to start",
        className: "cs-b-opts",
        role: "radiogroup",
        children: NEW_GAME_MODES.map(
          (item) => jsxs(
            "button",
            {
              "aria-checked": mode === item.id,
              className: mode === item.id ? "cs-b-opt on" : "cs-b-opt",
              "data-mode": item.id,
              onClick: () => setMode(item.id),
              onKeyDown: onModeKey,
              role: "radio",
              tabIndex: mode === item.id ? 0 : -1,
              type: "button",
              children: [
                jsx("i", { "aria-hidden": true, className: "cs-b-opt-dot" }),
                jsxs("span", {
                  children: [
                    jsx("b", { children: item.title }),
                    jsx("span", { children: item.text }),
                    jsx("em", { children: item.ends })
                  ]
                })
              ]
            },
            item.id
          )
        )
      })
    ]
  });
}

// page/app/background.js
var asked = [];
var listeners = /* @__PURE__ */ new Set();
var changed = () => {
  for (const listener of listeners) listener();
};
function wantedBackground() {
  return asked.length ? asked[asked.length - 1].id : null;
}
function onBackgroundChange(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
function Background({ id }) {
  useLayoutEffect(() => {
    const entry = { id };
    asked.push(entry);
    changed();
    return () => {
      asked.splice(asked.indexOf(entry), 1);
      changed();
    };
  }, [id]);
  return null;
}

// page/pages/games/games.css.js
var GAMES_CSS = `
/* games: Shelf of real cartridges */
.cs-dev { align-items: center; background: var(--ui-bg-quaternary); display: flex; flex-wrap: wrap; gap: 8px 14px; padding: 11px 14px; }
.cs-dev .dot { background: var(--ui-text-quaternary); flex: none; height: 8px; width: 8px; }
.cs-dev.on .dot { background: var(--ui-green); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-green) 22%, transparent); }
.cs-dev .nm { color: var(--ui-text-primary); font-weight: 600; }
.cs-shelf { display: grid; gap: clamp(18px, 2.2cqi, 36px) clamp(16px, 2cqi, 30px); grid-template-columns: repeat(auto-fill, minmax(min(100%, clamp(200px, 15cqi, 300px)), 1fr)); }
.cs-gcard { display: grid; gap: 10px; grid-template-rows: auto 1fr auto; min-width: 0; }
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
.cs-gtag { color: var(--ui-text-secondary); font-size: 12px; line-height: 1.4; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-meta { color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font: 11px ${MONO}; gap: 4px 12px; }
.cs-gtag.none { color: var(--ui-text-quaternary); font-style: italic; }
.cs-gtag.bad { color: var(--ui-red); }
.cs-gline { align-items: center; color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font: 11px ${MONO}; gap: 4px 12px; min-height: 18px; }
.cs-gst { align-items: center; display: inline-flex; font: 700 10px/1 ${MONO}; gap: 6px; letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; }
.cs-gst i { background: currentColor; border-radius: 50%; height: 7px; width: 7px; }
.cs-gst.good { color: var(--ui-green); } .cs-gst.warn { color: var(--ui-yellow); } .cs-gst.bad { color: var(--ui-red); } .cs-gst.quiet { color: var(--ui-text-tertiary); }
.cs-cart .nocover { align-items: center; background: color-mix(in srgb, black 72%, transparent); border-radius: 1cqw; bottom: 17.5%; color: white; display: inline-flex; font: 700 3.4cqw/1 ${MONO}; gap: 1.4cqw; letter-spacing: .08em; padding: 1.4cqw 2.2cqw; position: absolute; right: 16%; text-transform: uppercase; }
.cs-split { display: inline-flex; position: relative; }
.cs-split > button, .cs-split > span > button { align-items: center; appearance: none; border: 1px solid transparent; cursor: pointer; display: inline-flex; font: 500 12.5px/1 inherit; gap: 6px; height: 30px; padding: 0 12px; white-space: nowrap; }
.cs-split .main { border-radius: 6px 0 0 6px; }
.cs-split .caret { border-radius: 0 6px 6px 0; padding: 0 8px; }
.cs-split .solid { background: var(--ui-accent); color: var(--ui-bg-editor); }
.cs-split .caret.solid { border-left-color: color-mix(in srgb, var(--ui-bg-editor) 35%, transparent); }
.cs-split .solid:hover:not(:disabled) { filter: brightness(1.08); }
.cs-split .outline { background: transparent; border-color: var(--ui-stroke-secondary); color: var(--ui-text-primary); }
.cs-split .caret.outline { border-left-width: 0; }
.cs-split .outline:hover:not(:disabled) { background: var(--ui-bg-quaternary); }
.cs-split button:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-split button:disabled { cursor: default; opacity: .6; }
.cs-gmenu { animation: cs-b-in .1s ease-out; background: linear-gradient(var(--ui-bg-tertiary, var(--ui-bg-secondary)), var(--ui-bg-tertiary, var(--ui-bg-secondary))), var(--ui-bg-editor); border-radius: 8px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 12px 30px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; gap: 1px; left: 0; min-width: 230px; padding: 4px; position: absolute; top: calc(100% + 6px); z-index: 40; }
.cs-gmenu button { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 5px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; font-size: 12.5px; gap: 9px; outline: none; padding: 7px 9px; text-align: left; white-space: nowrap; }
.cs-gmenu button:hover:not(:disabled), .cs-gmenu button:focus-visible { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-gmenu button:disabled { color: var(--ui-text-quaternary); cursor: default; }
.cs-gmenu em { color: var(--ui-text-quaternary); font-size: 11px; font-style: normal; margin-left: auto; padding-left: 12px; }
.cs-hwchip { align-items: center; appearance: none; background: transparent; border: 1px solid var(--ui-stroke-tertiary); border-radius: 999px; color: var(--ui-text-secondary); display: inline-flex; font: 700 10.5px/1 ${MONO}; gap: 8px; letter-spacing: .08em; padding: 7px 11px; text-transform: uppercase; white-space: nowrap; }
button.cs-hwchip { cursor: pointer; }
button.cs-hwchip:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-hwchip i { background: var(--ui-text-quaternary); border-radius: 50%; height: 7px; width: 7px; }
.cs-hwchip.on i { background: var(--ui-green); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-green) 22%, transparent); }
.cs-empty { align-items: start; display: grid; gap: 48px; grid-template-columns: minmax(0, 560px) minmax(0, 1fr); }
.cs-empty > .cs-col { gap: 16px; }
.cs-empty > .cs-art { max-width: 340px; }
.cs-gfolder { align-items: center; display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 8px; min-width: 0; }
.cs-gfolder > .cs-mono { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
`;

// page/app/events.js
function createEvents() {
  const declared = /* @__PURE__ */ new Map();
  const listeners2 = /* @__PURE__ */ new Map();
  const known = (name) => {
    if (!declared.has(name)) {
      throw new Error(`unknown page event "${name}": declare it in the owning page's index.js (events: { '${name}': '...' })`);
    }
  };
  return {
    declare(name, owner, doc) {
      if (declared.has(name)) {
        throw new Error(`page event "${name}" is declared by both ${declared.get(name).owner} and ${owner}: one page owns each event`);
      }
      declared.set(name, { owner, doc });
    },
    declared: () => new Map(declared),
    on(name, fn) {
      known(name);
      const set = listeners2.get(name) ?? /* @__PURE__ */ new Set();
      listeners2.set(name, set);
      set.add(fn);
      return () => set.delete(fn);
    },
    emit(name, payload) {
      known(name);
      for (const fn of [...listeners2.get(name) ?? []]) {
        try {
          fn(payload);
        } catch (error) {
          console.error(`[hermretro] a listener of "${name}" failed:`, error);
        }
      }
    }
  };
}
var PAGE_EVENTS = createEvents();
var emit = (name, payload) => PAGE_EVENTS.emit(name, payload);

// page/shared/ui/art.js
function Art() {
  return jsx("div", { "aria-hidden": true, className: "cs-art" });
}
function Flyer() {
  const wing = (side) => jsx("div", { className: `wing ${side}`, children: jsx("div", { className: "ink" }) }, side);
  return jsxs("div", {
    "aria-hidden": true,
    className: "cs-flyer",
    children: [
      jsx("div", {
        className: "drift",
        children: jsx("div", {
          className: "lift",
          children: jsxs("div", {
            className: "tilt",
            children: [wing("l"), wing("r"), jsx("div", { className: "body", children: jsx("div", { className: "ink" }) }, "body")]
          })
        })
      }),
      jsx("div", { className: "shadow" })
    ]
  });
}

// page/pages/games/games-folder.js
async function openFolder(ctx, path) {
  const shown = await ctx.os?.revealPath?.(path).catch(() => false);
  if (!shown) {
    const copied = await ctx.os?.writeClipboard?.(path).catch(() => false);
    host.notify({ kind: "info", message: copied ? "The games folder is on the computer running Hermes. Its path is copied." : path });
  }
}
function GamesFolder({ ctx, path }) {
  if (typeof path !== "string" || !path) {
    return null;
  }
  return jsxs("div", {
    className: "cs-gfolder",
    children: [
      jsx("span", { className: "cs-faint", children: "Games folder" }),
      jsx("span", { className: "cs-mono", title: path, children: path }),
      jsxs(Button, {
        onClick: () => void openFolder(ctx, path),
        size: "sm",
        variant: "ghost",
        children: [jsx(Codicon, { name: "folder-opened", size: 14 }), "Open games folder"]
      })
    ]
  });
}

// page/app/slots.js
function createSlots() {
  const declared = /* @__PURE__ */ new Map();
  const filled = /* @__PURE__ */ new Map();
  const known = (name) => {
    if (!declared.has(name)) {
      throw new Error(`unknown UI slot "${name}": declare it in the host page's index.js (slots: { '${name}': '...' })`);
    }
  };
  return {
    declare(name, owner, doc) {
      if (declared.has(name)) {
        throw new Error(`UI slot "${name}" is declared by both ${declared.get(name).owner} and ${owner}: one page hosts each slot`);
      }
      declared.set(name, { owner, doc });
      filled.set(name, []);
    },
    declared: () => new Map(declared),
    fill(name, Component, from) {
      known(name);
      if (typeof Component !== "function") {
        throw new Error(`${from} contributes something that is not a component to the UI slot "${name}"`);
      }
      filled.get(name).push(Component);
    },
    contributions(name) {
      known(name);
      return filled.get(name);
    }
  };
}
var PAGE_SLOTS = createSlots();
function Slot({ name, props = {}, slots = PAGE_SLOTS }) {
  const list = slots.contributions(name);
  return list.length ? list.map((Component, index) => jsx(Component, { ...props }, `${name}:${index}`)) : null;
}

// page/pages/games/cartridge.js
function Cartridge({ game, title, note = null, label, disabled = false, play = false, onClick, className = "" }) {
  const thumb = game?.thumb ?? null;
  return jsxs("button", {
    "aria-label": label ?? title,
    className: className ? `cs-cart ${className}` : "cs-cart",
    disabled,
    onClick,
    type: "button",
    children: [
      jsx(
        "span",
        {
          className: "slot",
          children: thumb ? jsx("img", { alt: game.cover ? `${title} cover art` : `${title} title screen`, draggable: false, src: thumb }) : jsxs("span", { className: "ph", children: [title, note ? jsx("small", { children: note }, "note") : null] })
        },
        "slot"
      ),
      thumb && !game.cover ? jsxs("span", { className: "nocover", children: [jsx(Codicon, { name: "sparkle", size: 9 }), "No cover"] }, "nocover") : null,
      play ? jsx("span", { className: "hov", children: jsx("span", { children: jsx(Codicon, { name: "play", size: 22 }) }) }, "hov") : null
    ]
  });
}

// page/app/format.js
function formatBytes(bytes, { approx = false, unit = null } = {}) {
  if (unit === "MB") {
    bytes = bytes || 0;
  }
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "";
  }
  const mb = bytes / 1e6;
  const text2 = unit === "MB" ? `${Math.round(mb).toLocaleString()} MB` : unit === "KB" ? `${Math.max(1, Math.round(bytes / 1024))} KB` : mb >= 1e3 ? `${(mb / 1e3).toFixed(1)} GB` : mb >= 100 ? `${Math.round(mb)} MB` : `${mb.toFixed(1)} MB`;
  return approx ? `≈ ${text2}` : text2;
}
function shortPath(path, keep = 4) {
  if (!path) {
    return null;
  }
  const parts = String(path).split(/[\\/]/).filter(Boolean);
  return parts.length > keep ? `…/${parts.slice(-keep).join("/")}` : path;
}

// page/pages/games/model.js
var KIND_LABELS = { gbstudio: "GB Studio", gbdk: "GBDK" };
var GAME_STATES = {
  ready: ["good", "Ready"],
  changed: ["warn", "Changed since last build"],
  failed: ["bad", "Build failed"],
  unbuilt: ["quiet", "Not built yet"]
};
function gameMeta(game, { kind = true, now = Date.now() } = {}) {
  return [
    kind ? KIND_LABELS[game.kind] ?? game.kind ?? null : null,
    game.rom?.size ? formatBytes(game.rom.size, { unit: "KB" }) : null,
    game.rom?.builtAt ? `built ${ago(game.rom.builtAt, now)}` : "never built"
  ].filter(Boolean);
}
function installPrompt(game) {
  return `Flash the built ROM of ${gameLabel(game)} to the connected Chromatic cartridge, then guide me through manual boot, gameplay, and audio checks.`;
}
function fixPrompt(game) {
  return `The last build of ${gameLabel(game)} failed${game.error ? `:
${game.error}
` : ". "}Find the cause, fix it, rebuild, and show me the result.`;
}

// page/pages/games/game-card.js
var COVER_PROMPT = "Make this game’s card: draw a 160x144 pixel-art cover in the game’s own palette and write its tagline, description and genres, with chromatic_game_info.";
var GAME_STATUS = {
  ready: ["good", "Ready"],
  changed: ["warn", "Changed"],
  failed: ["bad", "Build failed"],
  unbuilt: ["quiet", "Not built"]
};
function primaryAction(ctx, game, onPlay) {
  if (game.state === "failed") {
    return { icon: "tools", label: "Fix in chat", tone: "outline", title: "Puts the build error in its chat, not sent", run: () => sendToGameChat(ctx, game, fixPrompt(game)) };
  }
  if (game.state === "unbuilt") {
    return { icon: "play", label: "Build in chat", title: "Puts a build prompt in its chat, not sent", run: () => sendToGameChat(ctx, game, buildPrompt(game)) };
  }
  if (game.state === "changed") {
    return { icon: "play", label: "Build & play", title: `Edited since its last build: puts a build prompt in its chat, not sent. ${AGENT} shows it beside the chat when it is built.`, run: () => sendToGameChat(ctx, game, buildPrompt(game)) };
  }
  return { icon: "play", label: "Play", title: `Play ${game.displayTitle || game.title} on the Emulator page`, run: () => onPlay(game.id) };
}
async function revealGame(ctx, game) {
  const path = game.projectRoot;
  const shown = await ctx.os?.revealPath?.(path).catch(() => false);
  if (!shown) {
    const copied = await ctx.os?.writeClipboard?.(path).catch(() => false);
    host.notify({ kind: "info", message: copied ? "The game is on the computer running Hermes. Its folder path is copied." : path });
  }
}
function GameActions({ ctx, game, hardwareOn, onPlay, onMakeCover }) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const wrap = useRef(null);
  const title = game.displayTitle || game.title;
  const action = primaryAction(ctx, game, onPlay);
  const built = game.state !== "failed" && game.state !== "unbuilt";
  const card = game.card ?? null;
  useEffect(() => {
    if (!open) {
      return void 0;
    }
    const items = () => [...wrap.current?.querySelectorAll?.(".cs-gmenu button:not(:disabled)") ?? []];
    const onDown = (event) => {
      if (wrap.current && !wrap.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
        wrap.current?.querySelector(".cs-split .caret")?.focus?.();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        const list = items();
        const at = list.indexOf(document.activeElement);
        event.preventDefault();
        list[(at + (event.key === "ArrowDown" ? 1 : list.length - 1)) % list.length]?.focus?.();
      }
    };
    items()[0]?.focus?.();
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);
  const run = async (fn) => {
    setOpen(false);
    setPending(true);
    try {
      await fn();
    } finally {
      setPending(false);
    }
  };
  const item = (icon, label, fn, { disabled = false, why } = {}) => jsxs(
    "button",
    {
      disabled,
      onClick: () => void run(fn),
      role: "menuitem",
      title: why,
      type: "button",
      children: [jsx(Codicon, { name: icon, size: 13 }), jsx("span", { children: label }), why && disabled ? jsx("em", { children: why }) : null]
    },
    label
  );
  const rows = [
    game.state === "changed" && game.webExport ? item("play", "Play last build", () => onPlay(game.id)) : null,
    built ? item("desktop-download", "Install on Chromatic", () => sendToGameChat(ctx, game, installPrompt(game)), {
      disabled: !hardwareOn || !game.rom,
      why: !hardwareOn ? "Needs your Chromatic" : !game.rom ? "Build it first" : "Puts the flash prompt in its chat; Hermes asks before writing"
    }) : null,
    item("comment-discussion", "Open its chat", () => openGameChat(game), { disabled: !game.chat && !game.session, why: game.chat ? game.chat.title || void 0 : game.session ? void 0 : "No chat recorded" }),
    !card?.complete && onMakeCover ? item("sparkle", game.cover ? "Finish card" : "Make cover art", () => onMakeCover(game)) : null,
    game.projectRoot ? item("folder-opened", "Show in folder", () => revealGame(ctx, game)) : null,
    // What other pages add to this menu (games/index.js declares the slot).
    jsx(Slot, { name: "games.cardMenu", props: { ctx, game, hardwareOn, item } }, "more")
  ].filter(Boolean);
  return jsxs("div", {
    className: "cs-split",
    ref: wrap,
    children: [
      jsx(Tip, {
        label: action.title,
        children: jsxs("button", {
          className: `main ${action.tone ?? "solid"}`,
          disabled: pending,
          onClick: () => void run(action.run),
          type: "button",
          children: [jsx(Codicon, { name: action.icon, size: 13 }), action.label]
        })
      }),
      jsx("button", {
        "aria-expanded": open,
        "aria-haspopup": "menu",
        "aria-label": `More for ${title}`,
        className: `caret ${action.tone ?? "solid"}`,
        onClick: () => setOpen(!open),
        type: "button",
        children: jsx(Codicon, { name: "chevron-down", size: 12 })
      }),
      open ? jsx("div", { "aria-label": `${title} actions`, className: "cs-gmenu", role: "menu", children: rows }) : null
    ]
  });
}
function GameCard({ ctx, game, hardwareOn, onPlay, onMakeCover }) {
  const title = game.displayTitle || game.title;
  const card = game.card ?? null;
  const playable = game.state !== "unbuilt" && game.state !== "failed";
  const [tone, status] = GAME_STATUS[game.state] ?? GAME_STATUS.unbuilt;
  const meta = gameMeta(game, { kind: false });
  const built = meta[meta.length - 1];
  return jsxs("article", {
    className: "cs-gcard",
    children: [
      jsx(Cartridge, {
        disabled: !playable,
        game,
        label: playable ? `Play ${title}` : title,
        note: playable ? "Title screen after first play" : "No build yet",
        onClick: () => onPlay(game.id),
        play: playable,
        title
      }),
      jsxs("div", {
        className: "info",
        children: [
          jsx("h3", { title, children: title }),
          game.state === "failed" && game.error ? jsx("p", { className: "cs-gtag bad", title: game.error, children: game.error }) : card?.tagline ? jsx("p", { className: "cs-gtag", title: [card.description || card.tagline, card.genres?.length ? card.genres.join(" · ") : null].filter(Boolean).join("\n"), children: card.tagline }) : jsx("p", { className: "cs-gtag none", children: "No description yet" }),
          jsxs("div", {
            className: "cs-gline",
            title: meta.join(" · "),
            children: [jsxs("span", { className: `cs-gst ${tone}`, children: [jsx("i", {}), status] }), jsx("span", { children: built })]
          })
        ]
      }),
      jsx(GameActions, { ctx, game, hardwareOn, onMakeCover, onPlay })
    ]
  });
}

// page/pages/games/games-page.js
function DeviceStrip({ hardwareOn, onSetUpDevice }) {
  return hardwareOn ? jsxs("div", {
    className: "cs-dev on",
    children: [
      jsx("span", { className: "dot" }),
      jsx("span", { className: "nm", children: "Chromatic hardware tools are on" }),
      jsx(Small, { children: "Install puts the flash prompt in the game's chat. Hermes asks before it writes the cartridge, unless Approvals are off." })
    ]
  }) : jsxs("div", {
    className: "cs-dev",
    children: [
      jsx("span", { className: "dot" }),
      jsx("span", { className: "nm", children: "Playing in the emulator." }),
      jsx(Small, { children: "Set up a Chromatic to install games on a real cartridge." }),
      jsx("span", { className: "cs-grow" }),
      jsx(Button, { onClick: onSetUpDevice, size: "sm", variant: "outline", children: "Set up my Chromatic" })
    ]
  });
}
function InstallButton({ ctx, game, hardwareOn, label = "Install" }) {
  return jsx(AsyncButton, {
    disabled: !hardwareOn || !game.rom,
    icon: "desktop-download",
    run: () => sendToGameChat(ctx, game, installPrompt(game)),
    title: !hardwareOn ? "Needs your Chromatic" : !game.rom ? "Build it first" : "Puts the flash prompt in this game's chat; Hermes asks before writing",
    variant: "outline",
    children: label
  });
}
function DeviceChip({ hardwareOn, onSetUpDevice }) {
  return hardwareOn ? jsx(Tip, {
    label: "Install puts the flash prompt in the game's chat. Hermes asks before it writes the cartridge, unless Approvals are off.",
    children: jsxs("span", { className: "cs-hwchip on", children: [jsx("i", {}), "Chromatic tools on"] })
  }) : jsx(Tip, {
    label: "Set up a Chromatic to install games on a real cartridge.",
    children: jsxs("button", { className: "cs-hwchip", onClick: onSetUpDevice, type: "button", children: [jsx("i", {}), "Emulator only · Set up my Chromatic"] })
  });
}
function GamesPage({ ctx, games, hardwareOn, onPlay, onNewGame, onSetUpDevice, onMakeCover }) {
  const list = games.data?.games;
  const folder = jsx(GamesFolder, { ctx, path: games.data?.gamesDir }, "folder");
  const newGame = jsxs(Button, { onClick: onNewGame, size: "sm", variant: "default", children: [jsx(Codicon, { name: "add", size: 14 }), "New game"] });
  if (games.isError || games.data && !Array.isArray(list)) {
    return [
      jsx(PageHead, { title: "Your games" }, "head"),
      jsxs("div", {
        className: "cs-col",
        style: { gap: 12, maxWidth: "72ch" },
        children: [
          jsx(Lede, { children: games.isError ? studioError(games.error, "list your games") : games.data?.error || "The games list could not be read." }),
          jsx("div", { children: newGame })
        ]
      }, "err")
    ];
  }
  if (!list) {
    return [jsx(PageHead, { title: "Your games" }, "head"), jsx(Working, { quiet: true, children: "Reading your games…" }, "wait")];
  }
  if (!list.length) {
    return [
      jsx(DeviceStrip, { hardwareOn, onSetUpDevice }, "dev"),
      jsxs(
        "div",
        {
          className: "cs-empty",
          children: [
            jsxs("div", {
              className: "cs-col",
              children: [
                jsx("h2", { className: "cs-word cs-title", children: "No games yet" }),
                jsx(Lede, {
                  children: "Games you make with Hermes land here, ready to play in the emulator or install on your Chromatic."
                }),
                jsx("div", {
                  className: "cs-actions",
                  children: jsx(Button, { onClick: onNewGame, size: "sm", variant: "default", children: "Create a new game" })
                }),
                jsx("p", { className: "cs-faint", children: "Already have a GB Studio project? Ask Hermes to select it and it shows up here." }),
                folder
              ]
            }),
            jsx(Art, {})
          ]
        },
        "empty"
      )
    ];
  }
  return [
    jsx(PageHead, { title: "Your games", children: [jsx(DeviceChip, { hardwareOn, onSetUpDevice }, "hw"), jsx("span", { style: { display: "contents" }, children: newGame }, "new")] }, "head"),
    jsxs(
      "div",
      {
        className: "cs-shelf",
        children: [
          ...list.map((game) => jsx(GameCard, { ctx, game, hardwareOn, onMakeCover, onPlay }, game.id)),
          jsxs(
            "article",
            {
              className: "cs-gcard",
              children: [
                jsx("button", {
                  "aria-label": "New game",
                  className: "cs-cart ghost",
                  onClick: onNewGame,
                  type: "button",
                  children: jsx("span", {
                    className: "slot",
                    children: jsxs("span", {
                      className: "cs-col",
                      style: { alignItems: "center", gap: 8 },
                      children: [jsx(Codicon, { name: "add", size: 26 }), jsx("span", { className: "cs-eyebrow", children: "New game" })]
                    })
                  })
                }),
                jsxs("div", {
                  className: "info",
                  children: [
                    jsx("h3", { style: { color: "var(--ui-text-tertiary)" }, children: "Blank cartridge" }),
                    jsx("p", { className: "cs-gtag none", children: "Make a new game with Hermes" })
                  ]
                })
              ]
            },
            "new"
          )
        ]
      },
      "shelf"
    ),
    folder
  ];
}
function Games({ shell }) {
  return jsx(GamesPage, {
    ctx: shell.ctx,
    games: shell.games,
    hardwareOn: shell.hardwareOn,
    // Make cover art: the request goes into that game's Build conversation (Build listens), not sent.
    onMakeCover: (game) => {
      emit("games.coverRequested", { game, prompt: COVER_PROMPT });
      shell.go("build", game.id);
    },
    onNewGame: () => shell.go("build", "new"),
    onPlay: shell.play,
    onSetUpDevice: shell.setUpDevice
  });
}

// page/pages/games/index.js
var GAMES_PAGE = {
  id: "games",
  label: "Games",
  Page: Games,
  css: [GAMES_CSS],
  events: {
    "games.coverRequested": "Make cover art (or Finish card) was picked for a game: { game, prompt }. The game opens on Build with the prompt in its message box, not sent."
  },
  slots: {
    "games.cardMenu": "Extra items at the end of a game's arrow menu on the shelf. Props: { ctx, game, hardwareOn, item(icon, label, run, { disabled, why }) }; return item(...) for a menu button. icon is a Codicon name, e.g. 'folder-opened', 'copy'."
  },
  contributes: {
    "emulator.barActions": [InstallButton]
  }
};

// page/pages/build/switcher.js
function switcherEntries(games, pending, states, selected) {
  const sub = (state, fallback) => state?.waiting ? "Needs your answer" : state?.busy ? `${AGENT} is working…` : state?.unread ? "New reply" : fallback;
  return [
    ...pending.map((item) => {
      const state = states[item.storedId] ?? null;
      return { key: `pending:${item.storedId}`, title: item.name || "New game", sub: sub(state, "Setting up…"), state, game: null, pending: item, stored: item.storedId };
    }),
    ...games.filter((game) => game.buildSession || game.id === selected).map((game) => {
      const state = game.buildSession ? states[game.buildSession] ?? null : null;
      const mine = Boolean(game.buildSession) && game.session?.thisProfile !== false;
      return {
        key: game.id,
        title: game.title,
        sub: game.buildSession ? sub(state, (GAME_STATES[game.state] ?? GAME_STATES.unbuilt)[1]) : "New editing chat",
        state,
        game,
        stored: mine ? game.buildSession : null
      };
    })
  ];
}
var statusMark = (state) => state?.waiting ? jsx("i", { "aria-label": "Needs your answer", className: "dot wait" }) : state?.busy ? jsx("i", { "aria-label": `${AGENT} is working`, className: "cs-b-spin" }) : state?.unread ? jsx("i", { "aria-label": "New reply", className: "dot new" }) : null;
var libraryWhen = (game) => (GAME_STATES[game.state] ?? GAME_STATES.unbuilt)[1];
function BuildSwitcher({ entries, library, selected, title, onSelect, onOpenChat, onStop, onDiscard, request = null, onRequestSeen = () => {
} }) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState("menu");
  useEffect(() => {
    if (request) {
      setView(request.view === "library" && library.length ? "library" : "menu");
      setOpen(true);
      onRequestSeen();
    }
  }, [request?.seq]);
  const [query, setQuery] = useState("");
  const [ctxMenu, setCtxMenu] = useState(null);
  const box = useRef(null);
  const pop = useRef(null);
  const others = entries.filter((entry) => entry.key !== selected);
  const waiting = others.filter((entry) => entry.state?.waiting).length;
  const working = others.filter((entry) => entry.state?.busy && !entry.state?.waiting).length;
  const unread = others.some((entry) => entry.state?.unread);
  const needle = query.trim().toLowerCase();
  const shelf = needle ? library.filter((game) => game.title.toLowerCase().includes(needle)) : library;
  const close = () => {
    setOpen(false);
    setView("menu");
    setQuery("");
    setCtxMenu(null);
  };
  useEffect(() => {
    if (!open) {
      return void 0;
    }
    const items = () => [...box.current?.querySelectorAll?.(ctxMenu ? ".cs-b-ctx button:not(:disabled)" : ".cs-b-sw-pop button") ?? []];
    const away = (event) => {
      if (box.current && !box.current.contains(event.target)) {
        close();
      } else if (ctxMenu && !event.target.closest?.(".cs-b-ctx")) {
        setCtxMenu(null);
      }
    };
    const key = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (ctxMenu) {
          setCtxMenu(null);
        } else if (view === "library") {
          setView("menu");
          setQuery("");
        } else {
          close();
          box.current?.querySelector?.(".cs-b-sw")?.focus?.();
        }
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        const list = items();
        const at = list.indexOf(document.activeElement);
        event.preventDefault();
        list[(at + (event.key === "ArrowDown" ? 1 : -1) + list.length) % list.length]?.focus?.();
      }
    };
    document.addEventListener("mousedown", away);
    window.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", away);
      window.removeEventListener("keydown", key);
    };
  }, [open, view, Boolean(ctxMenu)]);
  useEffect(() => {
    if (!open) {
      return;
    }
    if (ctxMenu) {
      box.current?.querySelector?.(".cs-b-ctx button:not(:disabled)")?.focus?.();
    } else if (view === "library") {
      box.current?.querySelector?.(".cs-b-sw-search input")?.focus?.();
    } else {
      const list = [...box.current?.querySelectorAll?.(".cs-b-sw-pop button") ?? []];
      (list.find((item) => item.getAttribute("aria-current") === "true") ?? list[0])?.focus?.();
    }
  }, [open, view, ctxMenu?.key]);
  const pick = (key) => {
    close();
    onSelect(key);
  };
  const openMenuAt = (entry, x, y) => {
    if (!entry.stored) {
      return;
    }
    const frame = pop.current?.getBoundingClientRect?.();
    setCtxMenu({ key: entry.key, x: frame ? x - frame.left : 16, y: frame ? y - frame.top : 16 });
  };
  const thumb = (game) => game?.thumb ? jsx("img", { alt: "", className: "cs-b-sw-thumb", draggable: false, src: game.thumb }) : jsx("span", { "aria-hidden": true, className: "cs-b-sw-thumb ph", children: jsx(Codicon, { name: game ? "game" : "sparkle", size: 12 }) });
  const ctxEntry = ctxMenu ? entries.find((entry) => entry.key === ctxMenu.key) : null;
  const ctx = ctxEntry ? jsxs("div", {
    "aria-label": `${ctxEntry.title} options`,
    className: "cs-b-ctx",
    role: "menu",
    style: { left: Math.min(ctxMenu.x, 200), top: ctxMenu.y },
    children: [
      jsxs("button", {
        onClick: () => {
          close();
          onOpenChat(ctxEntry.stored);
        },
        role: "menuitem",
        type: "button",
        children: [jsx(Codicon, { name: "link-external", size: 12 }), "Open in full chat"]
      }),
      jsx("hr", {}),
      jsxs("button", {
        className: "danger",
        disabled: Boolean(ctxEntry.state?.busy),
        onClick: () => {
          close();
          void (ctxEntry.pending ? onDiscard(ctxEntry.pending) : onStop(ctxEntry.game));
        },
        role: "menuitem",
        title: ctxEntry.state?.busy ? `Wait for ${AGENT} to finish first` : void 0,
        type: "button",
        children: [jsx(Codicon, { name: "close", size: 12 }), ctxEntry.pending ? "Discard" : "Stop editing"]
      })
    ]
  }) : null;
  const editing = entries.filter((entry) => entry.game);
  const openNames = editing.map((entry) => entry.title);
  const openNote = !openNames.length ? null : openNames.length === 1 ? `${openNames[0]} is already open above.` : openNames.length === 2 ? `${openNames[0]} and ${openNames[1]} are already open above.` : `${openNames.length} games you’re editing are already open above.`;
  const menuView = [
    jsxs(
      "button",
      {
        "aria-current": selected === "new" ? "true" : void 0,
        className: "cs-b-game cs-b-sw-new",
        onClick: () => pick("new"),
        role: "menuitem",
        type: "button",
        children: [jsx("span", { className: "cs-b-sw-thumb add", children: jsx(Codicon, { name: "add", size: 14 }) }), jsx("b", { children: "New game" })]
      },
      "new"
    ),
    library.length ? jsxs(
      "button",
      {
        "aria-haspopup": "menu",
        className: "cs-b-game cs-b-sw-new",
        onClick: () => setView("library"),
        role: "menuitem",
        type: "button",
        children: [
          jsx("span", { className: "cs-b-sw-thumb edit", children: jsx(Codicon, { name: "edit", size: 12 }) }),
          jsxs("span", { className: "nm", children: [jsx("b", { children: "Edit a game" }), jsx("small", { children: "Open one from your library" })] }),
          jsx("span", { className: "cs-b-sw-go", children: jsx(Codicon, { name: "chevron-right", size: 13 }) })
        ]
      },
      "edit"
    ) : null,
    entries.length ? jsx("p", { className: "cs-eyebrow", children: "Editing now" }, "eyebrow") : null,
    jsx(
      "div",
      {
        className: "cs-b-sw-list",
        children: entries.map(
          (entry, index) => jsxs(
            "button",
            {
              "aria-current": selected === entry.key ? "true" : void 0,
              className: `cs-b-game${entry.state?.waiting ? " wait" : ""}`,
              onClick: () => pick(entry.key),
              onContextMenu: (event) => {
                if (entry.stored) {
                  event.preventDefault();
                  openMenuAt(entry, event.clientX, event.clientY);
                }
              },
              onKeyDown: (event) => {
                if (entry.stored && (event.key === "ContextMenu" || event.shiftKey && event.key === "F10")) {
                  event.preventDefault();
                  const rect = event.currentTarget.getBoundingClientRect();
                  openMenuAt(entry, rect.left + 40, rect.bottom - 4);
                }
              },
              role: "menuitem",
              type: "button",
              children: [
                thumb(entry.game),
                jsxs("span", { className: "nm", children: [jsx("b", { children: entry.title }), jsx("small", { children: entry.sub })] }),
                statusMark(entry.state),
                index < 9 ? jsxs("span", { className: "cs-b-sw-key", children: ["Ctrl ", index + 1] }) : null
              ]
            },
            entry.key
          )
        )
      },
      "list"
    ),
    entries.length || library.length ? null : jsx("p", { className: "cs-faint cs-b-sw-empty", children: "Games you make here show up in this list." }, "empty")
  ];
  const libraryView = [
    jsxs(
      "button",
      {
        className: "cs-b-sw-back",
        onClick: () => {
          setView("menu");
          setQuery("");
        },
        type: "button",
        children: [jsx(Codicon, { name: "chevron-left", size: 13 }), "Edit a game"]
      },
      "back"
    ),
    jsxs(
      "label",
      {
        className: "cs-b-sw-search",
        children: [
          jsx(Codicon, { name: "search", size: 12 }),
          jsx("input", {
            "aria-label": "Search your games",
            onChange: (event) => setQuery(event.target.value),
            onKeyDown: (event) => {
              if (event.key === "Enter" && shelf[0]) {
                event.preventDefault();
                pick(shelf[0].id);
              }
            },
            placeholder: "Search your games",
            value: query
          })
        ]
      },
      "search"
    ),
    jsx(
      "div",
      {
        className: "cs-b-sw-list",
        children: shelf.map(
          (game) => jsxs(
            "button",
            {
              className: "cs-b-game",
              onClick: () => pick(game.id),
              role: "menuitem",
              type: "button",
              children: [
                thumb(game),
                jsxs("span", { className: "nm", children: [jsx("b", { children: game.title }), jsx("small", { children: libraryWhen(game) })] }),
                jsx("span", { className: "go", children: "Start editing" })
              ]
            },
            game.id
          )
        )
      },
      "shelf"
    ),
    shelf.length ? null : jsx("p", { className: "cs-faint cs-b-sw-empty", children: needle ? "No game by that name." : "Every game is already open above." }, "none"),
    openNote ? jsx("p", { className: "cs-b-sw-foot", children: openNote }, "foot") : null
  ];
  return jsxs("div", {
    className: "cs-b-swwrap",
    ref: box,
    children: [
      jsxs("button", {
        "aria-expanded": open,
        "aria-haspopup": "menu",
        "aria-label": `${title}: switch game`,
        className: `cs-b-sw${open ? " open" : ""}`,
        onClick: () => open ? close() : setOpen(true),
        type: "button",
        children: [jsx("h2", { className: "cs-word", children: title }), jsx(Codicon, { name: "chevron-down", size: 14 })]
      }),
      waiting ? jsx("button", {
        className: "cs-b-needs",
        onClick: () => setOpen(true),
        title: others.filter((entry) => entry.state?.waiting).map((entry) => entry.title).join(", "),
        type: "button",
        children: `${waiting} needs you`
      }) : working ? jsxs("span", { className: "cs-b-others", children: [jsx("i", { className: "cs-b-spin" }), `${working} working`] }) : unread ? jsx("i", { "aria-label": "Another game has a new reply", className: "cs-b-otherdot" }) : null,
      open ? jsxs("div", {
        "aria-label": view === "library" ? "Edit a game" : "Your games",
        className: `cs-b-sw-pop${view === "library" ? " lib" : ""}`,
        ref: pop,
        role: "menu",
        children: [...view === "library" ? libraryView : menuView, ctx]
      }) : null
    ]
  });
}

// page/pages/build/cart-shelf.js
var SLOT = 126;
var MIN_HEIGHT = 560;
function shelfOrder(entries) {
  const rank = (entry) => entry.state?.waiting ? 0 : entry.pending ? 1 : 2;
  const started2 = (entry) => entry.pending ? entry.pending.createdAt ?? Infinity : 0;
  return entries.map((entry, index) => ({ entry, index })).sort((a, b) => rank(a.entry) - rank(b.entry) || started2(b.entry) - started2(a.entry) || a.index - b.index).map((item) => item.entry);
}
function labelNote(game) {
  if (!game) {
    return "Being set up";
  }
  return game.state === "unbuilt" || game.state === "failed" ? "No build yet" : "Title screen after first play";
}
function shelfFit(width, count, more) {
  const slots = Math.max(1, Math.floor((width + 26) / SLOT));
  return count + (more ? 1 : 0) <= slots ? count : Math.max(0, slots - 1);
}
function CartShelf({ entries, others, onSelect, onAll }) {
  const box = useRef(null);
  const [room, setRoom] = useState({ width: 5 * SLOT, height: MIN_HEIGHT });
  useEffect(() => {
    const area = box.current?.parentElement;
    if (!area || typeof ResizeObserver !== "function") {
      return void 0;
    }
    const measure = () => setRoom({ width: Math.min(area.clientWidth - 48, 8 * SLOT), height: area.clientHeight });
    const watch = new ResizeObserver(measure);
    watch.observe(area);
    measure();
    return () => watch.disconnect();
  }, []);
  const order = shelfOrder(entries);
  if (!order.length || room.height < MIN_HEIGHT) {
    return jsx("div", { "aria-hidden": true, className: "cs-b-shelf-probe", ref: box });
  }
  const shown = order.slice(0, shelfFit(room.width, order.length, others.length > 0));
  const left = order.length - shown.length + others.length;
  return jsxs("nav", {
    "aria-label": "Your games",
    className: "cs-b-shelf",
    "data-at-flat": "",
    ref: box,
    children: [
      ...shown.map(
        (entry) => jsxs(
          "div",
          {
            className: `cs-b-shelf-cart${entry.state?.waiting ? " wait" : ""}`,
            children: [
              jsx(Cartridge, {
                game: entry.game,
                label: `${entry.title}, ${entry.sub}`,
                note: labelNote(entry.game),
                onClick: () => onSelect(entry.key),
                title: entry.title
              }),
              jsxs("span", { className: "cap", children: [jsx("b", { title: entry.title, children: entry.title }), jsxs("small", { children: [statusMark(entry.state), entry.sub] })] })
            ]
          },
          entry.key
        )
      ),
      left ? jsxs(
        "div",
        {
          className: "cs-b-shelf-cart all",
          children: [
            jsx("button", {
              "aria-label": `All games: ${left} more`,
              className: "cs-b-shelf-more",
              onClick: () => onAll(order.length > shown.length ? "menu" : "library"),
              type: "button",
              children: `+${left}`
            }),
            jsxs("span", { className: "cap", children: [jsx("b", { children: "All games" }), jsx("small", { children: others.length ? "With your library" : "Being worked on" })] })
          ]
        },
        "all"
      ) : null
    ]
  });
}

// page/pages/build/build-page.js
function rememberSelection(ctx, selection) {
  try {
    ctx.storage.set("buildSelected", selection);
  } catch {
  }
}
function BuildPage({ ctx, games, selection, onSelect: select, pendingGames, localPending, changePending, loaded = true, onLibraryChanged, updating = false }) {
  const chats = useValue(BUILD_CHATS);
  const startingGames = useValue(BUILD_STARTING);
  const [local, setLocal] = useState({ bound: {}, released: {} });
  const [rememberedSelection] = useState(() => {
    if (selection !== null) {
      return selection;
    }
    try {
      return ctx.storage.get("buildSelected", "new") || "new";
    } catch {
      return "new";
    }
  });
  const selected = selection ?? rememberedSelection;
  useEffect(() => {
    if (selection === null) {
      select(selected);
    } else {
      rememberSelection(ctx, selection);
    }
  }, [ctx, select, selected, selection]);
  const rail = useMemo(
    () => games.map((game2) => {
      const session = game2.session && local.released[game2.id] !== game2.session.storedId ? game2.session : null;
      const bound = local.bound[game2.id];
      const linked = session?.storedId;
      const buildSession = (!linked || linked === bound?.replaces ? bound?.stored : null) ?? linked ?? null;
      return { ...game2, session, title: game2.displayTitle || game2.title, buildSession };
    }),
    [games, local.bound, local.released]
  );
  const pending = useMemo(
    () => [
      ...Array.isArray(pendingGames) ? pendingGames : [],
      ...localPending.filter((item) => !(pendingGames ?? []).some((known) => known.storedId === item.storedId))
    ].filter((item) => !rail.some((game2) => game2.buildSession === item.storedId)),
    [pendingGames, localPending, rail]
  );
  const pendingId = selected.startsWith("pending:") ? selected.slice("pending:".length) : null;
  const made = pendingId ? rail.find((game2) => game2.buildSession === pendingId) : null;
  useEffect(() => {
    if (made) {
      select(made.id);
    }
  }, [made?.id]);
  useEffect(() => {
    if (pending.some((item) => chats[item.storedId]?.busy === false)) {
      onLibraryChanged();
    }
  }, [pending.map((item) => chats[item.storedId]?.busy).join(",")]);
  const game = made ?? rail.find((item) => item.id === selected) ?? null;
  const pendingItem = pending.find((item) => item.storedId === pendingId) ?? null;
  useEffect(() => {
    if (loaded && selected !== "new" && !game && !pendingItem && !(pendingId && chats[pendingId]?.busy)) {
      select("new");
    }
  }, [loaded, selected, Boolean(game), Boolean(pendingItem)]);
  useEffect(() => {
    BUILD_VIEWING.set(game?.id ?? null);
    return () => BUILD_VIEWING.set(null);
  }, [game?.id]);
  const elsewhere = Boolean(game?.session && game.session.thisProfile === false);
  const stored = elsewhere ? null : game?.buildSession ?? pendingItem?.storedId ?? null;
  const chat = stored ? chats[stored] : null;
  const [restartIds, setRestartIds] = useState({});
  const replaces = game && stored && restartIds[game.id] === stored ? stored : null;
  const fresh = Boolean(game && !elsewhere && (!stored || replaces));
  useEffect(() => {
    setRestartIds((current) => {
      const kept = Object.entries(current).filter(([id, expected]) => rail.some((item) => item.id === id && item.buildSession === expected));
      return kept.length === Object.keys(current).length ? current : Object.fromEntries(kept);
    });
  }, [rail]);
  const [draftPick, setDraftPick, draftOptions] = useDraftPick(ctx, selected === "new" || fresh);
  const startingGame = startingGames.has(game?.id);
  useEffect(() => {
    if (!stored || chat?.runtime || chat?.opening || chat?.failure) {
      return;
    }
    if (game?.session?.storedId === stored && game.session.exists === false) {
      patchChat(stored, (current) => current.missing ? current : { ...current, missing: true });
    } else {
      void openBuildChat(stored);
    }
  }, [stored, chat?.runtime]);
  useEffect(() => {
    if (stored && chat && !chat.busy && (chat.lastCompleteAt ?? 0) > (chat.seenAt ?? 0)) {
      patchChat(stored, (current) => ({ ...current, seenAt: Date.now() }));
    }
  }, [stored, chat?.lastCompleteAt, chat?.busy]);
  const [playerFor, setPlayerFor] = useState(null);
  const presented = useValue(BUILD_PRESENTED)[game?.id ?? ""] ?? null;
  const seenPresent = useRef(presented?.seq ?? 0);
  const openWhenDone = useRef(false);
  useEffect(() => {
    const seq = presented?.seq ?? 0;
    if (seq !== seenPresent.current) {
      seenPresent.current = seq;
      openWhenDone.current = true;
    }
  }, [presented?.seq]);
  useEffect(() => {
    if (game && openWhenDone.current && !chat?.busy && !chat?.opening) {
      openWhenDone.current = false;
      setPlayerFor(game.id);
    }
  }, [chat?.busy, chat?.opening, presented?.seq, game?.id]);
  useEffect(() => {
    openWhenDone.current = false;
  }, [game?.id]);
  const refuseWhileUpdating = () => {
    if (!isUpdating()) {
      return false;
    }
    host.notify({ kind: "warning", message: UPDATING_MESSAGE });
    return true;
  };
  const startGame = async ({ idea, name, plan }) => {
    if (refuseWhileUpdating()) {
      return false;
    }
    let id = null;
    try {
      id = await createBuildChat(name.trim() || "New game", draftPick);
      const recorded = await buildRpc({ action: "start", stored: id, name: name.trim() || null, plan });
      const first = recorded ? idea.trim() : newGamePrompt({ idea, name, plan });
      if (!await sendBuildChat(id, first, idea.trim(), [], { mustLand: true })) {
        void buildRpc({ action: "cancel", stored: id }).catch(() => {
        });
        if (!isUpdating()) {
          host.notify({ kind: "error", message: "Could not start the conversation: Hermes did not take the first message." });
        }
        return false;
      }
      const created = { storedId: id, name: name.trim() || null, createdAt: Date.now() / 1e3 };
      changePending((current) => [...current, created]);
      select(`pending:${id}`);
      onLibraryChanged();
      return true;
    } catch (error) {
      host.notify({ kind: "error", message: `Could not start the conversation: ${describeRequestError(error).message}` });
      if (id) {
        void buildRpc({ action: "cancel", stored: id }).catch(() => {
        });
      }
      return false;
    }
  };
  const discard = async (item) => {
    try {
      await buildRpc({ action: "cancel", stored: item.storedId });
    } catch (error) {
      host.notify({ kind: "error", message: `Could not discard it: ${describeRequestError(error).message}` });
      return;
    }
    changePending((current) => current.filter((entry) => entry.storedId !== item.storedId));
    select("new");
    onLibraryChanged();
  };
  const shownStored = fresh ? null : stored;
  const shownChat = shownStored ? chat : null;
  const shownItems = shownChat?.items ?? null;
  const binding = local.bound[game?.id];
  const composerKey = binding && binding.stored === stored ? binding.replaces ?? game.id : stored ?? game?.id ?? "";
  const [focusTurn, setFocusTurn] = useState(null);
  const [switcherRequest, setSwitcherRequest] = useState(null);
  const settledItems = useRef(null);
  if (!shownChat?.busy) {
    settledItems.current = shownItems;
  }
  const builds = useMemo(() => buildHistory(deriveTurns(settledItems.current ?? [])), [settledItems.current]);
  const send = async (text2, attachments = [], shown = text2) => {
    if (refuseWhileUpdating()) {
      return false;
    }
    if (!fresh) {
      return stored ? sendBuildChat(stored, text2, shown, attachments) : false;
    }
    const { id, title: title2, projectRoot } = game;
    if (BUILD_STARTING.get().has(id)) {
      return false;
    }
    BUILD_STARTING.set(/* @__PURE__ */ new Set([...BUILD_STARTING.get(), id]));
    try {
      const target = await createBuildChat(title2, draftPick);
      if (refuseWhileUpdating()) {
        return false;
      }
      const recorded = await buildRpc({ action: "bind", game: id, stored: target, ...replaces ? { replace: replaces } : {} });
      setLocal((current) => ({ ...current, bound: { ...current.bound, [id]: { stored: target, replaces: stored } } }));
      onLibraryChanged();
      return await sendBuildChat(
        target,
        recorded ? text2 : `Work on my existing hermretro game "${title2}" at ${projectRoot} (select that project first). ${text2}`,
        shown,
        attachments
      );
    } catch (error) {
      host.notify({ kind: "error", message: `Could not start the conversation: ${describeRequestError(error).message}` });
      return false;
    } finally {
      BUILD_STARTING.set(new Set([...BUILD_STARTING.get()].filter((gameId) => gameId !== id)));
    }
  };
  const startOver = () => {
    if (game && stored && chat?.missing && !BUILD_STARTING.get().has(game.id)) {
      setRestartIds((current) => ({ ...current, [game.id]: stored }));
    }
  };
  const stopEditing = async (target) => {
    const storedId = target?.buildSession;
    if (!storedId) {
      return;
    }
    try {
      await buildRpc({ action: "unbind", game: target.id, stored: storedId });
    } catch (error) {
      host.notify({ kind: "error", message: `Could not stop editing ${target.title}: ${describeRequestError(error).message}` });
      return;
    }
    void chatRequest("session.set_hidden", { session_id: storedId, hidden: false }).catch(
      (error) => console.warn("[hermretro] could not show the old conversation in the sidebar:", describeRequestError(error).message)
    );
    setLocal((current) => {
      const bound = { ...current.bound };
      delete bound[target.id];
      return { ...current, bound, released: { ...current.released, [target.id]: storedId } };
    });
    if (selected === target.id) {
      select("new");
    }
    onLibraryChanged();
  };
  const restoreBuild = async (build, snapshot) => {
    if (!game || !shownStored || refuseWhileUpdating()) {
      return false;
    }
    try {
      const answer = await callStudioOnly(RPC_BUILD_RESTORE, { game: game.id, id: snapshot }, 6e4);
      if (!answer?.ok) {
        throw new Error(answer?.error ?? "The build could not be restored.");
      }
    } catch (error) {
      host.notify({ kind: "error", message: `Could not restore build #${build.n}: ${describeRequestError(error).message}` });
      return false;
    }
    onLibraryChanged();
    await send(
      `I restored the game to build #${build.n} ("${build.title}") from the hermretro Builds menu: its files are back as they were then (the version before this is saved). Please build it again and check that it still works.`,
      [],
      `Restore build #${build.n} · ${build.title}`
    );
    return true;
  };
  const statesRef = useRef({ key: "", value: {} });
  const states = useMemo(() => {
    const result = {};
    for (const [key2, value] of Object.entries(chats)) {
      result[key2] = {
        busy: Boolean(value?.busy),
        waiting: Boolean(value?.items?.some((item) => (item.kind === "clarify" || item.kind === "approval") && !item.answered)),
        unread: key2 !== stored && (value?.lastCompleteAt ?? 0) > (value?.seenAt ?? 0)
      };
    }
    const key = JSON.stringify(result);
    if (key !== statesRef.current.key) {
      statesRef.current = { key, value: result };
    }
    return statesRef.current.value;
  }, [chats, stored]);
  const title = game?.title ?? pendingItem?.name ?? "New game";
  const entries = useMemo(() => switcherEntries(rail, pending, states, selected), [rail, pending, states, selected]);
  const library = useMemo(() => rail.filter((item) => !item.buildSession && item.id !== selected), [rail, selected]);
  useEffect(() => {
    const onKey = (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey || !/^[1-9]$/.test(event.key)) {
        return;
      }
      const entry = entries[Number(event.key) - 1];
      if (entry) {
        event.preventDefault();
        select(entry.key);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [entries]);
  const switcher = jsx(BuildSwitcher, {
    entries,
    library,
    onRequestSeen: () => setSwitcherRequest(null),
    request: switcherRequest,
    onDiscard: (item) => discard(item),
    onOpenChat: openInFullChat,
    onSelect: select,
    onStop: stopEditing,
    selected,
    title
  });
  const header = selected === "new" ? jsx("header", { className: "cs-b-head", children: switcher }) : jsxs("header", {
    className: "cs-b-head",
    children: [
      switcher,
      jsx(BuildPill, { builds, chat: shownChat, game }),
      jsx("span", { className: "cs-grow" }),
      game && (builds.length || shownStored) ? jsx(BuildsMenu, {
        builds,
        busy: Boolean(shownChat?.busy || updating),
        game,
        onRestore: restoreBuild,
        onShow: (key) => setFocusTurn((current) => ({ key, seq: (current?.seq ?? 0) + 1 }))
      }) : null,
      pendingItem && !shownChat?.busy ? jsx(Button, { onClick: () => void discard(pendingItem), size: "sm", variant: "ghost", children: "Discard" }) : null
    ]
  });
  const openPrompt = shownChat?.busy ? shownChat.items?.find((item) => (item.kind === "clarify" || item.kind === "approval") && !item.answered) ?? null : null;
  const playable = Boolean(game && game.webExport && playableSha(game));
  const emptyState = jsx("div", {
    className: "cs-b-hello",
    children: jsxs("div", {
      className: "cs-col",
      children: [
        jsx("p", { className: "cs-small", children: chat?.opening ? "Opening the conversation…" : `Tell ${AGENT} what to make or change in ${title}.` }),
        chat?.opening ? jsx("div", { className: "cs-b-skel", children: [jsx("i", {}, "a"), jsx("i", {}, "b"), jsx("i", {}, "c")] }) : null
      ]
    })
  });
  let body2;
  if (elsewhere) {
    body2 = jsx("div", {
      className: "cs-b-empty",
      children: jsx("p", {
        className: "cs-small",
        children: `This game’s conversation is in the ${game.session.profileName ? `“${game.session.profileName}”` : "other"} Hermes profile. Switch to that profile to keep working on it here.`
      })
    });
  } else if (shownChat?.missing) {
    body2 = jsxs("div", {
      className: "cs-b-empty",
      children: [
        jsx("p", { className: "cs-small", children: "This game’s conversation was removed from Hermes. The game itself is fine." }),
        game ? jsx(Button, { disabled: startingGame, onClick: startOver, size: "sm", children: "Start a new conversation" }) : null
      ]
    });
  } else if (shownChat?.failure) {
    body2 = jsxs("div", {
      className: "cs-b-empty",
      children: [
        jsx("p", { className: "cs-error", children: `Could not open this conversation: ${shownChat.failure}` }),
        jsx(Button, { onClick: () => void reopenBuildChat(shownStored), size: "sm", variant: "outline", children: "Try again" })
      ]
    });
  } else if (!shownChat?.items?.length && !shownChat?.busy) {
    body2 = jsx("div", {
      className: "cs-b-tx",
      children: jsxs("div", {
        className: "cs-b-col",
        children: [
          emptyState,
          playable && !chat?.opening ? jsx("div", {
            className: "cs-b-her",
            children: playerFor === game.id ? jsx(InlinePlayer, { ctx, game, note: null, onClose: () => setPlayerFor(null), stored: shownStored }, `player:${game.id}`) : jsx(PlayCard, { game, onPlay: () => setPlayerFor(game.id), state: "ready" })
          }) : null
        ]
      })
    });
  } else {
    body2 = jsx(Transcript, {
      chat: shownChat,
      ctx,
      empty: emptyState,
      game,
      onClosePlayer: () => setPlayerFor(null),
      onPlay: () => game && setPlayerFor(game.id),
      onSend: (text2, shown, attachments) => void send(text2, attachments ?? [], shown ?? text2),
      focusTurn,
      playerOpen: Boolean(game && playerFor === game.id),
      stored: shownStored
    }, shownStored ?? "none");
  }
  const main = selected === "new" ? jsxs("div", {
    className: "cs-b-chat cs-b-attract",
    children: [
      jsx(Background, { id: "platformer" }, "level"),
      header,
      jsx(BuildNewGame, { onStart: startGame, updating, picker: jsx(DraftModelPicker, { ctx, onPick: setDraftPick, options: draftOptions, pick: draftPick, up: false }) }, "new"),
      jsx(CartShelf, { entries, onAll: (view) => setSwitcherRequest((current) => ({ view, seq: (current?.seq ?? 0) + 1 })), onSelect: select, others: library }, "shelf")
    ]
  }) : jsxs("div", {
    className: "cs-b-chat",
    children: [
      header,
      body2,
      jsx(BuildComposer, {
        busy: Boolean(shownChat?.busy),
        game,
        fresh,
        disabled: Boolean(updating || startingGame || elsewhere || shownChat?.opening || shownChat?.missing || shownChat?.failure || !fresh && !shownChat?.runtime),
        onSend: send,
        onStop: () => void stopBuildChat(shownStored),
        picker: elsewhere || shownChat?.missing ? null : fresh ? jsx(DraftModelPicker, { ctx, disabled: startingGame || updating, onPick: setDraftPick, options: draftOptions, pick: draftPick }) : shownStored ? jsx(ChatModelPicker, { chat: shownChat, ctx, disabled: !shownChat?.runtime, stored: shownStored }) : null,
        placeholder: updating ? "hermretro is updating. You can send again in a moment." : startingGame ? "Starting the conversation…" : shownChat?.busy ? `Reply to ${AGENT}…` : `Tell ${AGENT} what to change in ${title}…`,
        status: shownChat ? jsx(BuildStatus, { chat: { ...shownChat, stored: shownStored }, onStop: () => void stopBuildChat(shownStored) }) : null,
        ask: openPrompt && shownStored ? jsx(BuildPromptCard, { item: openPrompt, stored: shownStored }, openPrompt.requestId ?? "prompt") : null,
        stored: shownStored
      }, `composer:${composerKey}`)
    ]
  });
  return jsx(AssetGame.Provider, { value: rootOf(game, shownChat?.items ?? []), children: jsx("div", { className: "cs-b", children: main }) });
}

// page/pages/setup/onboarding/onboarding.css.js
var ONBOARDING_CSS = `
/* first-run onboarding: welcome, what gets downloaded / installing, Chromatic?, first game */
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
`;

// page/pages/setup/setup.css.js
var SETUP_CSS = `
/* setup: the install's stage, for screen readers only */
.cs-onb .cs-sr, .cs-setup .cs-sr { clip: rect(0 0 0 0); height: 1px; overflow: hidden; position: absolute; white-space: nowrap; width: 1px; }
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
`;

// page/shared/ui/glyph.js
var INDICATOR = {
  done: { icon: "pass-filled", color: C.good, label: "Done" },
  todo: { icon: "circle-large-outline", color: C.warn, label: "To do" },
  optional: { icon: "circle-large-outline", color: C.quaternary, label: "Optional" },
  waiting: { icon: "circle-large-outline", color: C.quaternary, label: "Waiting" },
  checking: { icon: "loading", color: C.tertiary, label: "Checking", spinning: true },
  error: { icon: "error", color: C.bad, label: "Problem" },
  skipped: { icon: "dash", color: C.quaternary, label: "Skipped" },
  blocked: { icon: "circle-slash", color: C.warn, label: "Not available" }
};
function Glyph({ state }) {
  const label = (INDICATOR[state] ?? INDICATOR.waiting).label;
  const ink = "var(--background, var(--ui-bg-editor))";
  let shape;
  if (state === "done") {
    shape = [
      jsx("rect", { fill: C.good, height: 12, width: 12, x: 1, y: 1 }, "box"),
      jsx("path", { d: "M4 7.2l2 2 4-4.4", fill: "none", stroke: ink, strokeWidth: 1.6 }, "tick")
    ];
  } else if (state === "error") {
    shape = [
      jsx("rect", { fill: C.bad, height: 12, width: 12, x: 1, y: 1 }, "box"),
      jsx("path", { d: "M7 4v4M7 9.6v.8", stroke: ink, strokeWidth: 1.6 }, "mark")
    ];
  } else if (state === "checking") {
    shape = jsx("rect", {
      className: "cs-dash",
      fill: "none",
      height: 11,
      stroke: "var(--ui-accent)",
      strokeDasharray: "3 2",
      strokeWidth: 1.4,
      width: 11,
      x: 1.5,
      y: 1.5
    });
  } else if (state === "skipped") {
    shape = jsx("path", { d: "M3 7h8", stroke: C.quaternary, strokeWidth: 1.4 });
  } else {
    shape = [
      jsx("rect", {
        fill: "none",
        height: 11,
        stroke: state === "blocked" ? C.warn : state === "todo" ? C.tertiary : C.quaternary,
        strokeWidth: 1.2,
        width: 11,
        x: 1.5,
        y: 1.5
      }, "box"),
      state === "blocked" ? jsx("path", { d: "M4 10l6-6", stroke: C.warn, strokeWidth: 1.2 }, "slash") : null
    ];
  }
  return jsx("svg", { "aria-label": label, className: "cs-glyph", height: 14, role: "img", viewBox: "0 0 14 14", width: 14, children: shape });
}
function Chip({ tone = "", children }) {
  return jsxs("span", { className: `cs-chip ${tone}`, children: [jsx("i", {}), children] });
}

// page/app/prompt-block.js
function PromptActions({ ctx, prompt, primaryLabel = "Use in chat", primaryVariant = "secondary" }) {
  const [pending, setPending] = useState(false);
  const run = async () => {
    if (pending) {
      return;
    }
    setPending(true);
    try {
      await sendPromptToChat(ctx, prompt);
    } finally {
      setPending(false);
    }
  };
  return jsxs("div", {
    className: "cs-actions",
    children: [
      jsxs(Button, {
        disabled: pending,
        onClick: () => void run(),
        size: "sm",
        variant: primaryVariant,
        children: [jsx(Codicon, { name: pending ? "loading" : "comment-discussion", size: 14, spinning: pending }), primaryLabel]
      }),
      jsx(CopyButton, { buttonSize: "sm", buttonVariant: "outline", label: "Copy", text: prompt })
    ]
  });
}
function PromptBlock({ ctx, prompt, label }) {
  return jsxs("div", {
    className: "cs-col",
    style: { gap: 10 },
    children: [jsx("p", { className: "cs-prompt", children: prompt }), jsx(PromptActions, { ctx, primaryLabel: label, primaryVariant: "default", prompt })]
  });
}

// page/pages/setup/steps.js
var HARDWARE_STEPS = ["firmware", "devmode", "devicecli", "hardware"];
var STEP_ORDER = ["profile", "toolchain", ...HARDWARE_STEPS];
var STEP_TITLES = {
  profile: "Create the hermretro profile",
  toolchain: "Install the game toolchain",
  firmware: "Update your Chromatic",
  devmode: "Activate Developer Mode",
  devicecli: "Install ModRetro's device software",
  hardware: "Turn on hardware tools"
};
var MANUAL_STEPS = { firmware: "firmwareDone", devmode: "devmodeDone" };
function useSetupMemory(ctx) {
  const [memory, setMemory] = useState(() => {
    try {
      return { ...ctx.storage.get("setup", {}) ?? {} };
    } catch {
      return {};
    }
  });
  const update = (patch) => setMemory((previous) => {
    const next = { ...previous, ...patch };
    try {
      ctx.storage.set("setup", next);
    } catch {
    }
    return next;
  });
  return [memory, update];
}
function toolchainStateKnown(status, doctor) {
  return Boolean(status.data?.ok) && (Boolean(doctor.data) || doctor.isError);
}
function toolchainState(data, doctor) {
  const report = doctor.data;
  const engine = data.engine ?? {};
  if (doctor.isError || report && !report.ok) {
    return "error";
  }
  if (!report) {
    return "checking";
  }
  return (report.missing_required ?? []).length || !engine.present || engine.verified === false ? "todo" : "done";
}
function computeSteps({ backend, status, doctor, memory }) {
  const data = backend === "ok" ? status.data : null;
  const cli = data?.deps?.device_cli;
  const states = {
    // A backend that says nothing about profiles predates this step and cannot make one.
    profile: !data ? "waiting" : !data.profile || data.profile.is_studio ? "done" : "todo",
    toolchain: !data ? "waiting" : nodeState(data.node).ok ? toolchainState(data, doctor) : "blocked",
    firmware: memory.firmwareDone ? "done" : "todo",
    devmode: memory.devmodeDone ? "done" : "todo",
    devicecli: !cli ? "waiting" : cli.state === "installed" || cli.state === "bundled" ? "done" : cli.state === "unsupported" ? "blocked" : "todo",
    hardware: !data ? "waiting" : data.hardware_enabled ? "done" : "todo"
  };
  return STEP_ORDER.map((id) => {
    const hardware = HARDWARE_STEPS.includes(id);
    const state = hardware && memory.hardwareSkipped && states[id] !== "done" ? "skipped" : states[id];
    return {
      id,
      title: STEP_TITLES[id],
      hardware,
      manual: id in MANUAL_STEPS,
      state,
      complete: state === "done" || state === "skipped"
    };
  });
}
var STEP_SHORT = {
  profile: "Studio profile",
  toolchain: "Game toolchain",
  firmware: "Firmware",
  devmode: "Developer Mode",
  devicecli: "Device software",
  hardware: "Hardware tools"
};

// page/pages/setup/hardware-steps.js
var DEVICE_CLI_PROMPT = "Install ModRetro's Chromatic device software for hermretro so I can use my physical Chromatic.";
function Confirm({ step, update }) {
  return step.state === "done" ? jsx(Button, { onClick: () => update({ [MANUAL_STEPS[step.id]]: false }), size: "sm", variant: "ghost", children: "Mark as not done" }) : jsxs(Button, {
    onClick: () => update({ [MANUAL_STEPS[step.id]]: true }),
    size: "sm",
    variant: "default",
    children: [jsx(Codicon, { name: "check", size: 14 }), "I've done this"]
  });
}
function FirmwareBody({ ctx, step, update }) {
  return jsxs("div", {
    className: "cs-content",
    children: [
      jsx(Lede, {
        children: "Install the latest firmware with ModRetro's Chromatic Firmware Updater. This happens in ModRetro's app, not in Hermes, so confirm here when it is done."
      }),
      jsxs("div", {
        className: "cs-actions",
        children: [
          jsx(ExternalLink, { ctx, href: LINKS.firmware, variant: "outline", children: "Open the Firmware Updater guide" }),
          jsx(Confirm, { step, update })
        ]
      })
    ]
  });
}
function Keys({ keys }) {
  return jsxs("span", {
    className: "cs-row",
    style: { gap: 6 },
    children: keys.flatMap((key, index) => [
      index ? jsx("span", { className: "cs-faint", children: "+" }, `p${index}`) : null,
      jsx("kbd", { className: "cs-kbd", children: key }, key)
    ])
  });
}
function DevModeBody({ step, update }) {
  return jsxs("div", {
    className: "cs-content",
    children: [
      jsx(Lede, {
        children: "Developer Mode lets this computer write your games to the cartridge. In ModRetro's Chromatic Firmware Updater press"
      }),
      jsxs("div", {
        className: "cs-row",
        style: { gap: 10 },
        children: [
          jsx(Keys, { keys: ["Ctrl", "I"] }),
          jsx("span", { className: "cs-faint", children: "or, on macOS," }),
          jsx(Keys, { keys: ["⌘", "I"] })
        ]
      }),
      jsx(Small, { children: "then enter the activation code included with the Chromatic: Codex Edition." }),
      jsxs("div", {
        className: "cs-warnline",
        children: [
          jsx("span", { children: jsx(Codicon, { name: "warning", size: 14 }) }),
          jsx("span", { children: "Activation happens only in ModRetro's Updater. Never type the code into a chat." })
        ]
      }),
      jsx("div", { className: "cs-actions", children: jsx(Confirm, { step, update }) })
    ]
  });
}
function DeviceSoftwareBody({ ctx, step, status }) {
  const cli = status.data?.deps?.device_cli;
  if (!cli) {
    return jsx(Small, {
      children: status.data?.ok ? "Not reported yet. Start a new chat to finish loading the plugin." : "Checked once the plugin is on."
    });
  }
  if (step.state === "done") {
    return jsx(Lede, { children: `ModRetro Chromatic CLI${cli.version ? ` ${cli.version}` : ""} is installed in hermretro's folder.` });
  }
  if (cli.state === "unsupported") {
    return jsx(Small, { tone: "warn", children: cli.detail || "ModRetro does not publish its device software for this computer." });
  }
  return jsxs("div", {
    className: "cs-content",
    children: [
      jsx(Lede, {
        children: "hermretro talks to the device through ModRetro's own Chromatic CLI. It is ModRetro's software, so it is not included: Hermes downloads it from ModRetro, checks it, and keeps it in hermretro's folder."
      }),
      jsx(Facts, {
        rows: [
          [
            "Source",
            jsxs("span", {
              children: [
                "ModRetro's npm package, checked against pinned hashes. ",
                cli.terms ? jsx(ExternalLink, { ctx, href: cli.terms, children: "ModRetro's terms" }) : null
              ]
            })
          ],
          ["Approval", "Hermes asks for your approval before downloading, unless Approvals are turned off."]
        ]
      }),
      jsx(PromptBlock, { ctx, label: "Install in chat", prompt: DEVICE_CLI_PROMPT })
    ]
  });
}
var HARDWARE_ABILITIES = ["Detect the device", "Stream", "Flash a cartridge", "Capture"];
function HardwareBody({ step }) {
  const on = step.state === "done";
  return jsxs("div", {
    className: "cs-content",
    children: [
      jsx(Lede, {
        children: on ? "Hardware tools are on for this profile: device detection, streaming, flashing and capture are available." : 'Device detection, streaming, flashing and capture are off until you allow them. Turn on "Chromatic hardware tools" in the plugin settings; this page continues once it is on.'
      }),
      jsx("div", {
        className: "cs-row",
        style: { gap: 6 },
        children: HARDWARE_ABILITIES.map((label) => jsx(Chip, { tone: on ? "good" : "", children: label }, label))
      }),
      jsx(Small, {
        children: "Writing a cartridge, streaming and driver setup ask for your approval first, unless Approvals are turned off in Hermes."
      }),
      jsx("div", {
        className: "cs-actions",
        children: jsxs(Button, {
          onClick: () => host.navigate(AGENT_SETTINGS_HREF),
          size: "sm",
          variant: on ? "outline" : "default",
          children: [jsx(Codicon, { name: "settings-gear", size: 14 }), "Open plugin settings"]
        })
      })
    ]
  });
}
function HardwareChoice({ steps, update }) {
  const remaining = steps.filter((step) => step.hardware && step.state !== "done").length;
  return jsxs("section", {
    "aria-live": "polite",
    className: "cs-stage",
    children: [
      jsxs("div", {
        className: "cs-stage",
        style: { display: "contents" },
        children: [
          jsxs("div", {
            className: "cs-stage-head",
            children: [
              jsxs("p", {
                className: "cs-eyebrow",
                children: [jsx("span", { className: "cs-accent", children: "Steps 1–2 done" }), jsx("span", { children: "The emulator is ready" })]
              }),
              jsx("h2", { className: "cs-word cs-title", children: "Ready to make games" })
            ]
          }),
          jsx(Lede, {
            children: "Hermes can now create, build and playtest your games, and you play them on the Emulator page, with sound. A physical Chromatic is optional: set it up now, or any time later."
          }),
          jsxs("div", {
            className: "cs-choice",
            children: [
              jsxs("div", {
                children: [
                  jsx("p", { className: "cs-eyebrow", children: "Emulator" }),
                  jsx("h3", { children: "Start making games" }),
                  jsx(Small, { children: "Build and play everything inside Hermes. Nothing else to install." }),
                  jsx("div", {
                    className: "cs-actions",
                    children: jsxs(Button, {
                      onClick: () => update({ hardwareSkipped: true, hardwareWanted: false }),
                      size: "sm",
                      variant: "default",
                      children: ["Start making games", jsx(Codicon, { name: "arrow-right", size: 14 })]
                    })
                  })
                ]
              }),
              jsxs("div", {
                children: [
                  jsx("p", { className: "cs-eyebrow", children: "ModRetro Chromatic" }),
                  jsx("h3", { children: "I have a Chromatic" }),
                  jsx(Small, {
                    children: `${remaining} more ${remaining === 1 ? "step" : "steps"} to stream your games to the handheld and write them to a cartridge: firmware, Developer Mode, ModRetro's device software and hardware tools.`
                  }),
                  jsx("div", {
                    className: "cs-actions",
                    children: jsx(Button, {
                      onClick: () => update({ hardwareSkipped: false, hardwareWanted: true }),
                      size: "sm",
                      variant: "outline",
                      children: "Set up my Chromatic"
                    })
                  })
                ]
              })
            ]
          }),
          jsx("span", { className: "cs-faint", children: "You can change this any time: the Chromatic steps stay in the setup list." })
        ]
      })
    ]
  });
}

// page/pages/setup/setup-complete.js
function versionFact(data, update) {
  const version = data.plugin?.version ?? "?";
  if (!update) {
    return version;
  }
  if (update.ready && update.phase === "idle") {
    return jsxs("span", {
      className: "cs-note",
      children: [
        `${version} · a new version is ready`,
        jsx(Button, { disabled: Boolean(update.blocked), onClick: update.start, size: "sm", variant: "default", children: "Update" }),
        jsxs(Button, { onClick: update.whatsNew, size: "sm", variant: "link", children: ["What's new", jsx(Codicon, { name: "link-external", size: 12 })] }),
        update.blocked ? jsx("span", { role: "status", children: update.blocked }) : null
      ]
    });
  }
  if (update.phase === "partial") {
    return jsxs("span", {
      className: "cs-note",
      children: [
        `${version} · the update is not finished`,
        jsx(Button, { disabled: Boolean(update.blocked), onClick: update.start, size: "sm", variant: "default", children: "Finish update" }),
        update.blocked ? jsx("span", { role: "status", children: update.blocked }) : null
      ]
    });
  }
  if (update.phase === "updating") {
    return `${version} · updating…`;
  }
  const standing = {
    failed: "the update did not go through: see the update in the header",
    review: "the update waits for your answer in the header",
    restart: `updated: ${update.restartAdvice.toLowerCase()} to finish`
  }[update.phase];
  if (standing) {
    return `${version} · ${standing}`;
  }
  return update.linked ? `${version} · a linked checkout: update it with git` : update.checked && !update.ready ? `${version} · up to date` : version;
}
function SetupComplete({ steps, status, doctor, emulatorOnly, onRecheck, rechecking, onSetUpDevice, onGo, pluginUpdate = null }) {
  const data = status.data ?? {};
  const report = doctor.data?.ok ? doctor.data : null;
  const tools = (report?.components ?? []).filter((component) => component.status === "ready" && !component.optional && component.id !== "node" && component.id !== "runtime").map((component) => `${component.label ?? component.id} ${component.detected ?? ""}`.trim());
  const cli = data.deps?.device_cli;
  return jsxs("section", {
    "aria-live": "polite",
    className: "cs-stage",
    children: [
      jsxs("div", {
        className: "cs-stage-head",
        children: [
          jsxs("p", {
            className: "cs-eyebrow",
            children: [
              jsx("span", { className: "cs-accent", children: "●" }),
              emulatorOnly ? `Steps 1–2 done · emulator only` : `All ${steps.length} steps done`
            ]
          }),
          jsx("h2", { className: "cs-word cs-title", children: "Setup is complete" })
        ]
      }),
      jsx(Lede, {
        children: emulatorOnly ? "Everything the emulator needs is installed and verified. A Chromatic is optional: set it up any time to stream games to it and write cartridges. Open any step to review it." : "Everything is installed and verified, including your Chromatic. Open any step to review it."
      }),
      jsx(Facts, {
        rows: [
          ["hermretro", versionFact(data, pluginUpdate)],
          ["Profile", data.profile?.name ?? data.via_profile ?? "this profile"],
          ["Toolchain", [tools.join(" · "), data.engine?.version ? `engine ${data.engine.version}` : ""].filter(Boolean).join(" · ") || "Ready"],
          [
            "Chromatic",
            data.hardware_enabled ? `Device software${cli?.version ? ` ${cli.version}` : ""} · hardware tools on` : "Not set up: streaming and flashing are off"
          ]
        ]
      }),
      jsxs("div", {
        className: "cs-actions",
        children: [
          jsx(Button, { onClick: () => onGo("build"), size: "sm", variant: "default", children: "Go to the studio" }),
          jsxs(Button, {
            disabled: rechecking,
            onClick: onRecheck,
            size: "sm",
            variant: "ghost",
            children: [jsx(Codicon, { name: "refresh", size: 14, spinning: rechecking }), "Check everything again"]
          }),
          emulatorOnly ? jsx(Button, { onClick: onSetUpDevice, size: "sm", variant: "outline", children: "Set up my Chromatic" }) : null
        ]
      })
    ]
  });
}

// page/pages/setup/install/installer.js
var SETUP_PROMPT = "Set up hermretro so I can create games, build ROMs, and run automated playtests. Check what is already installed and prepare the missing dependencies.";
var INSTALL_QUERY = [ID, "install"];
async function fetchInstall(queryClient) {
  const checkedAt = performance.now();
  const { data } = await callBackend(RPC_INSTALL, { action: "status" }, 3e4);
  if (data?.code === "UNAVAILABLE") {
    const previous = queryClient.getQueryData(INSTALL_QUERY);
    return { ...previous, ...data, install: previous?.install };
  }
  return data?.ok && data.install ? { ...data, checkedAt } : data;
}
function useInstall({ enabled, polling }) {
  const queryClient = useQueryClient();
  const [starting, setStarting] = useState(false);
  const [unconfirmed, setUnconfirmed] = useState(null);
  const query = useQuery({
    queryKey: INSTALL_QUERY,
    queryFn: () => fetchInstall(queryClient),
    enabled,
    refetchInterval: enabled ? (arg) => {
      const data = arg?.state ? arg.state.data : arg;
      if (unconfirmed || data?.code === "UNAVAILABLE" || data?.install?.state === "running") {
        return 1500;
      }
      return polling ? 5e3 : false;
    } : false,
    staleTime: 1e3,
    retry: false
  });
  const resolved = unconfirmed && query.data?.checkedAt > unconfirmed.after;
  const statusError = query.data?.code === "UNAVAILABLE" ? query.data.error : null;
  const unavailable = (resolved ? null : unconfirmed?.error) || statusError;
  useEffect(() => {
    if (resolved) {
      setUnconfirmed(null);
    }
  }, [resolved]);
  const start = async () => {
    setStarting(true);
    try {
      let answer;
      try {
        const result = await callBackend(RPC_INSTALL, { action: "start" }, 6e4);
        answer = result.data;
      } catch (error) {
        const { message, notLoaded } = describeRequestError(error);
        if (notLoaded) {
          throw error;
        }
        answer = { code: "UNAVAILABLE", error: message };
      }
      if (answer?.code === "UNAVAILABLE") {
        setUnconfirmed({ after: performance.now(), error: answer.error });
      } else if (answer?.ok && answer.install) {
        queryClient.setQueryData(INSTALL_QUERY, answer);
      }
      if (answer?.ok || answer?.code === "UNAVAILABLE") {
        await query.refetch?.();
      }
      return answer;
    } finally {
      setStarting(false);
    }
  };
  return { ...query, start, starting, unavailable };
}
async function createStudioProfile(profile) {
  if (isUpdating()) {
    throw new Error(UPDATING_MESSAGE);
  }
  if (!profile.studio?.exists) {
    await host.request("profiles.create", profile.create);
  }
  const { data } = await callBackend(RPC_STUDIO_PROFILE, {}, 24e4);
  if (!data?.ok) {
    throw new Error(data?.error || "The profile could not be set up.");
  }
}
var profileCreation = null;
function createStudioProfileOnce(profile) {
  profileCreation ??= createStudioProfile(profile).finally(() => {
    profileCreation = null;
  });
  return profileCreation;
}
var STOPPED = ["failed", "cancelled", "interrupted"];
function checkedSince(doctor, finishedAt) {
  if (!doctor || doctor.isFetching || !(doctor.data || doctor.isError)) {
    return false;
  }
  const at = Math.max(doctor.dataUpdatedAt ?? 0, doctor.errorUpdatedAt ?? 0);
  return !at || !finishedAt || at >= finishedAt * 1e3;
}
function useInstaller({ ctx, status, install, toolchainDone, doctor }) {
  const [failure, setFailure] = useState(null);
  const [cancelError, setCancelError] = useState(null);
  const [profileWork, setProfileWork] = useState({ state: "idle", error: null });
  const [elsewhere, setElsewhere] = useState(false);
  const { data, starting, unavailable } = install;
  const unsupported = install.isError && describeRequestError(install.error).notLoaded;
  const state = data?.install?.state ?? "idle";
  const profile = status.data?.profile;
  const needsProfile = Boolean(profile && !profile.is_studio && !profile.studio?.installed);
  const conflict = Boolean(needsProfile && profile.studio?.conflict);
  const node = nodeState(status.data?.node);
  const manifestReady = Boolean(data?.manifest?.items?.length) && Number(data?.manifest?.bytes) > 0;
  const noSpace = data?.space?.enough === false;
  const backendElsewhere = data?.install?.elsewhere;
  const waitingElsewhere = backendElsewhere === true || elsewhere && backendElsewhere === void 0;
  const elsewhereEnded = elsewhere && backendElsewhere === false && !toolchainDone;
  const updating = useUpdating();
  const makeProfile = () => {
    if (!needsProfile || conflict) {
      return;
    }
    setProfileWork({ state: "running", error: null });
    createStudioProfileOnce(profile).then(
      () => {
        setProfileWork({ state: "done", error: null });
        status.refetch?.();
      },
      (error) => setProfileWork({ state: "failed", error: String(error?.message ?? error) })
    );
  };
  const repairProfile = async () => {
    if (!profile) {
      return;
    }
    setProfileWork({ state: "running", error: null });
    try {
      await createStudioProfileOnce(profile);
      routing.scannedAt = 0;
      forgetRoute();
      setProfileWork({ state: "done", error: null });
      await status.refetch?.();
    } catch (error) {
      setProfileWork({ state: "failed", error: String(error?.message ?? error) });
    }
  };
  const start = async () => {
    if (starting || unavailable || state === "running" || !manifestReady || conflict || noSpace) {
      return;
    }
    if (isUpdating()) {
      setFailure(UPDATING_MESSAGE);
      return;
    }
    setFailure(null);
    makeProfile();
    try {
      const answer = await install.start();
      if (answer?.code === "OPERATION_IN_PROGRESS") {
        setElsewhere(true);
        await install.refetch?.();
        return;
      }
      if (answer?.code === "UNAVAILABLE") {
        return;
      }
      if (!answer?.ok) {
        throw new Error(answer?.error || "The install could not start.");
      }
      setElsewhere(false);
    } catch (error) {
      setFailure(describeRequestError(error).message || String(error?.message ?? error));
    }
  };
  const cancel = async () => {
    setCancelError(null);
    try {
      const { data: answer } = await callBackend(RPC_INSTALL, { action: "cancel", run_id: data?.install?.run_id ?? null }, 3e4);
      if (!answer?.ok) {
        setCancelError(answer?.error || "The install could not be cancelled.");
      }
    } catch (error) {
      setCancelError(describeRequestError(error).message || String(error?.message ?? error));
    }
    await install.refetch?.();
  };
  const recheck = async () => {
    setFailure(null);
    await Promise.all([install.refetch?.(), status.refetch?.(), doctor?.refetch?.()]);
  };
  const ask = () => sendPromptToChat(
    ctx,
    `${SETUP_PROMPT}

The install on the hermretro page stopped with this error:
${failure ?? data?.install?.error ?? "unknown error"}`,
    { fresh: true }
  );
  const unverified = state === "done" && !toolchainDone && checkedSince(doctor, data?.install?.finished_at);
  const verifying = (state === "done" && !unverified || waitingElsewhere) && !toolchainDone;
  const phase = toolchainDone ? "done" : starting || state === "running" || verifying ? "running" : failure || unverified || STOPPED.includes(state) ? "failed" : "review";
  const missing = doctor?.data?.ok ? doctor.data.missing_required ?? [] : [];
  return {
    ask,
    cancel,
    cancelError: state === "running" ? cancelError : null,
    cancelling: Boolean(data?.install?.cancelling),
    conflict,
    data,
    doctor,
    elsewhere: waitingElsewhere,
    elsewhereEnded,
    failure: failure ?? data?.install?.error ?? null,
    hint: failure ? null : data?.install?.hint ?? null,
    makeProfile,
    manifestReady,
    missing,
    needsProfile,
    node,
    noSpace,
    phase,
    spaceWarning: data?.space?.warning ?? null,
    profile,
    profileWork,
    recheck,
    repairProfile,
    start,
    starting,
    state,
    unavailable,
    unsupported,
    unverified,
    updating,
    verifying
  };
}

// page/pages/setup/profile-step.js
var PROFILE_FACTS = [
  [
    "Sign-in",
    "It starts with the sign-ins and keys Hermes can share from the profile the plugin is installed in. Some accounts may not carry over: Build says so if no model provider is ready there, and where to connect one."
  ],
  ["Skills", "hermretro and its six skills are turned on there, with a game-developer persona."],
  ["Tools", "Text-to-speech, app connections, computer use and scheduled jobs are turned off there. Everything else keeps the Hermes defaults."],
  ["Approvals", "Kept on (smart mode), so installing device software and anything that touches your Chromatic goes through an approval check."]
];
function ProfileBody({ status }) {
  const profile = status.data?.profile;
  const [working, setWorking] = useState(false);
  const [failure, setFailure] = useState(null);
  const updating = useUpdating();
  if (!status.data?.ok || !profile) {
    return jsx(Small, { children: "Checked once the plugin is on." });
  }
  if (profile.is_studio) {
    return jsx(Lede, { children: `hermretro has its own profile, "${profile.name}". Its chats open there.` });
  }
  const create = async () => {
    if (working) {
      return;
    }
    setWorking(true);
    setFailure(null);
    try {
      await createStudioProfileOnce(profile);
      host.notify({ kind: "success", message: "hermretro profile created" });
      status.refetch?.();
    } catch (error) {
      setFailure(String(error?.message ?? error));
    } finally {
      setWorking(false);
    }
  };
  const starting = profile.studio?.installed && !working;
  return jsxs("div", {
    className: "cs-content",
    children: [
      jsx(Lede, {
        children: "hermretro works in its own Hermes profile, so it has exactly the tools and skills game development needs, and your other chats stay as they are."
      }),
      jsx(Facts, { rows: PROFILE_FACTS }),
      starting ? jsxs("div", {
        className: "cs-col",
        children: [
          jsx(Working, { children: "The profile is created. Waiting for Hermes to start it…" }),
          jsx("div", {
            children: jsx(Button, { disabled: working || updating, onClick: create, size: "sm", variant: "ghost", children: "Set it up again" })
          })
        ]
      }) : working ? jsx(Working, { children: "Creating the profile…" }) : jsxs("div", {
        className: "cs-actions",
        children: [
          jsx(Button, { disabled: updating, onClick: create, size: "sm", variant: "default", children: "Create the hermretro profile" }),
          jsx("span", { className: "cs-faint", children: `The "${profile.name}" profile, where the plugin is installed, is not changed.` })
        ]
      }),
      failure ? jsx("p", { className: "cs-error", children: failure }) : null
    ]
  });
}

// page/pages/setup/install/install-actions.js
var STAGE = { gbdk: "GBDK", cli: "GB Studio and its packages", uv: "uv", emulator: "Python, PyBoy and Pillow" };
var QUIET_NOTE_SECONDS = 90;
function clock2(seconds) {
  const total = Math.max(0, Math.round(seconds ?? 0));
  const minutes = Math.floor(total / 60);
  return `${minutes}:${String(total % 60).padStart(2, "0")}`;
}
function stageText(install, verifying) {
  if (verifying) {
    return "Checking the installed tools";
  }
  if (install?.cancelling) {
    return "Stopping safely";
  }
  return install?.current ? `Installing ${STAGE[install.current] ?? install.current}` : "Preparing the install";
}
function StageAnnouncer({ text: text2 }) {
  const [spoken, setSpoken] = useState(text2);
  const last = useRef(text2);
  useEffect(() => {
    if (last.current !== text2) {
      last.current = text2;
      setSpoken(text2);
    }
  }, [text2]);
  return jsx("span", { "aria-live": "polite", className: "cs-sr", role: "status", children: spoken });
}
function InstallProgress({ install, phase, verifying, elsewhere }) {
  if (phase !== "running") {
    return null;
  }
  if (elsewhere && install?.state !== "running") {
    return jsx(Working, { children: "The tools are being installed from a chat. This page moves on when they are verified." });
  }
  const fraction = Math.max(0.02, Math.min(1, install?.fraction ?? 0));
  const downloaded = install?.downloaded_bytes ?? 0;
  const percent = Math.round(fraction * 100);
  const stage = stageText(install, verifying);
  const quiet = !verifying && install?.state === "running" && (install?.quiet_seconds ?? 0) >= QUIET_NOTE_SECONDS;
  return jsxs("div", {
    className: "cs-col",
    style: { gap: 8 },
    children: [
      jsxs("div", {
        className: "cs-row cs-mono",
        style: { justifyContent: "space-between", fontSize: 11.5 },
        children: [
          jsx("span", {
            "aria-hidden": true,
            children: verifying ? "Checking the installed tools…" : `${percent}% · ${stage}${install?.elapsed_seconds != null ? ` · ${clock2(install.elapsed_seconds)}` : ""}`
          }),
          jsx("span", { className: "cs-faint", children: downloaded > 0 ? `${formatBytes(downloaded)} downloaded` : install?.seeded ? "Using files already on this computer" : "" })
        ]
      }),
      jsx("div", {
        "aria-label": "Game tools install",
        "aria-valuemax": 100,
        "aria-valuemin": 0,
        "aria-valuenow": percent,
        "aria-valuetext": verifying ? stage : `${percent}%, ${stage}`,
        className: "cs-progress",
        role: "progressbar",
        children: jsx("b", { style: { width: `${fraction * 100}%` } })
      }),
      jsx(StageAnnouncer, { text: stage }),
      quiet ? jsx(Small, {
        children: `Still working: nothing new on disk for ${clock2(install.quiet_seconds)}. Building GB Studio can stay at one percentage for several minutes.`
      }) : null
    ]
  });
}
var recheckButton = (installer, label = "Check again") => jsx(AsyncButton, { icon: "refresh", run: installer.recheck, variant: "default", children: label }, "recheck");
function InstallActions({ installer, compact = false }) {
  const { phase, start, starting, ask, node, unsupported } = installer;
  const size = compact ? "sm" : "lg";
  if (unsupported) {
    return jsxs("div", {
      className: "cs-col",
      style: { gap: 10 },
      children: [
        jsx(Small, { tone: "warn", children: "This hermretro backend cannot install from the page yet. Update the plugin, or let Hermes do it in a chat." }),
        jsx("div", { className: "cs-actions", children: jsx(AsyncButton, { icon: "comment-discussion", run: ask, variant: "default", children: "Set up in chat" }) })
      ]
    });
  }
  if (!node.ok) {
    return jsxs("div", {
      className: "cs-col",
      style: { gap: 10 },
      children: [
        jsx(Small, {
          tone: "warn",
          children: node.version ? `Found Node.js ${node.version}, which is too old (hermretro needs ${node.required} or newer). Update Hermes, then check again.` : `Node.js was not found. Hermes normally installs it; run "hermes update", restart Hermes, then check again.`
        }),
        jsx("div", { className: "cs-actions", children: recheckButton(installer) })
      ]
    });
  }
  if (phase === "done" && installer.needsProfile) {
    return installer.profileWork.state === "running" ? jsx(Working, { children: "Creating the hermretro profile…" }) : jsx("div", {
      className: "cs-actions",
      children: jsx(Button, { disabled: installer.updating || installer.conflict, onClick: installer.makeProfile, size, variant: "default", children: "Create the hermretro profile" })
    });
  }
  if (phase === "done" && installer.profileWork.state !== "failed") {
    return jsxs("div", {
      className: "cs-col",
      style: { gap: 10 },
      children: [
        jsx(Working, { quiet: true, children: installer.profileWork.state === "running" ? "Repairing the hermretro profile…" : "Tools verified. Waiting for Hermes to start the hermretro profile…" }),
        jsx("div", {
          className: "cs-actions",
          children: jsx(AsyncButton, { disabled: installer.updating || installer.profileWork.state === "running", icon: "tools", run: installer.repairProfile, children: "Repair the profile" })
        })
      ]
    });
  }
  if (phase === "done") {
    return jsx("div", {
      className: "cs-actions",
      children: jsx(AsyncButton, { disabled: installer.updating, icon: "tools", run: installer.repairProfile, variant: "default", children: "Repair the profile" })
    });
  }
  if (phase === "running") {
    if (installer.elsewhere && installer.state !== "running") {
      return jsx("div", { className: "cs-actions", children: recheckButton(installer) });
    }
    if (installer.state !== "running" || installer.verifying) {
      return null;
    }
    return installer.cancelling ? jsx(Working, { quiet: true, children: "Stopping safely: waiting for the installer to finish its current step…" }) : jsx("div", {
      className: "cs-actions",
      children: jsx(AsyncButton, { icon: "debug-stop", run: installer.cancel, title: "Stops after the current step; finished parts are kept", children: "Cancel" })
    });
  }
  if (phase === "review") {
    const blocked = installer.unavailable || !installer.manifestReady || installer.conflict || installer.noSpace;
    return jsxs("div", {
      className: "cs-actions",
      children: [
        jsxs(Button, {
          disabled: starting || installer.updating || blocked,
          onClick: () => void start(),
          size,
          variant: "default",
          children: [jsx(Codicon, { name: "cloud-download", size: 14 }), "Download and install"]
        }),
        blocked ? recheckButton(installer) : null
      ]
    });
  }
  if (phase === "failed" && installer.unavailable) {
    return jsx("div", { className: "cs-actions", children: recheckButton(installer) });
  }
  if (phase === "failed" && installer.unverified) {
    return jsxs("div", {
      className: "cs-actions",
      children: [
        recheckButton(installer),
        installer.missing.length ? jsxs(Button, {
          disabled: starting || installer.updating,
          onClick: () => void start(),
          size,
          variant: "outline",
          children: [jsx(Codicon, { name: "refresh", size: 14 }), "Retry install"]
        }) : null,
        jsx(AsyncButton, { icon: "comment-discussion", run: ask, title: "Opens a chat with the error in it, not sent", children: "Ask Hermes to fix it" })
      ]
    });
  }
  if (phase === "failed") {
    return jsxs("div", {
      className: "cs-actions",
      children: [
        jsxs(Button, {
          disabled: starting || installer.updating || !installer.manifestReady || installer.conflict || installer.noSpace,
          onClick: () => void start(),
          size,
          variant: "default",
          children: [jsx(Codicon, { name: "refresh", size: 14 }), installer.state === "cancelled" ? "Install again" : "Try again"]
        }),
        jsx(AsyncButton, { icon: "comment-discussion", run: ask, title: "Opens a chat with the error in it, not sent", children: "Ask Hermes to fix it" })
      ]
    });
  }
  return null;
}
function InstallError({ installer }) {
  const { failure, phase, profileWork, hint } = installer;
  const profileName = installer.profile?.studio?.name ?? "hermretro";
  const doctor = installer.doctor;
  const before = phase === "review" || phase === "failed";
  const note = (key, text2, tone = "cs-error") => jsx("p", { className: tone, children: text2 }, key);
  return [
    installer.conflict && phase !== "running" ? note("conflict", `A Hermes profile named "${profileName}" already exists and was not made by hermretro, so nothing was downloaded. Rename or remove that profile in Hermes, then check again.`) : null,
    before && !installer.manifestReady && !installer.unsupported ? note("manifest", "The download list could not be read, so nothing can be reviewed or installed yet. Check again; if it stays empty, update or reinstall hermretro.") : null,
    before && installer.noSpace ? note("space", `Not enough free disk space: the game tools need about ${formatBytes(installer.data?.space?.needed_bytes)} and ${formatBytes(installer.data?.space?.free_bytes)} is free. Free some space, then check again.`) : null,
    before && !installer.noSpace && installer.spaceWarning ? note("space-warning", installer.spaceWarning, "cs-small") : null,
    installer.unavailable ? note("status", installer.unavailable) : null,
    phase === "running" && installer.cancelError ? note("cancel", installer.cancelError) : null,
    phase === "review" && installer.elsewhereEnded ? note("elsewhere", "The install that was running in a chat stopped before the tools were ready. Install them here instead.", "cs-small") : null,
    phase === "failed" && installer.unverified ? note(
      "unverified",
      doctor?.isError || doctor?.data?.ok === false ? `The install finished, but the tools check failed: ${doctor?.data?.error || String(doctor?.error?.message ?? doctor?.error ?? "unknown error")}` : `The install finished, but the tools check still reports missing: ${installer.missing.join(", ") || "unknown"}.`
    ) : null,
    phase === "failed" && !installer.unverified && failure ? note("error", failure) : null,
    phase === "failed" && !installer.unverified && hint ? note("hint", hint, "cs-small") : null,
    profileWork.state === "failed" ? note("profile", `The hermretro profile could not be created: ${profileWork.error}`) : null
  ];
}

// page/pages/setup/install/install-panel.js
var ROW_LABEL = { done: "verified", running: "installing", failed: "failed", pending: "" };
function DownloadTable({ manifest, install, phase, profileRow }) {
  const components = install?.run?.components ?? {};
  const current = install?.current;
  const rows = (manifest?.items ?? []).map((item) => {
    const component = components[item.component];
    const state = phase === "done" || install?.state === "done" ? "done" : component?.state ?? (phase === "review" ? null : "pending");
    return { ...item, state, running: state === "running" && current === item.component };
  });
  const row = (item) => jsxs(
    "tr",
    {
      "data-state": item.state ?? void 0,
      children: [
        item.state ? jsx("td", { className: "g", children: jsx(Glyph, { state: { done: "done", running: "checking", failed: "error", pending: "waiting" }[item.state] }) }) : null,
        jsxs("td", { className: "n", children: [item.name, jsx("span", { className: "p", children: item.purpose })] }),
        jsx("td", { className: "v", children: item.version }),
        jsx("td", { className: "s", children: item.source }),
        jsx("td", {
          className: `z ${item.state ?? ""}`,
          children: item.state && item.state !== "pending" ? ROW_LABEL[item.state] : item.bytes ? formatBytes(item.bytes, { approx: item.approx }) : "no download"
        })
      ]
    },
    item.id
  );
  const live = phase !== "review";
  return jsxs("table", {
    className: "cs-dl",
    children: [
      jsx("thead", {
        children: jsxs("tr", {
          children: [
            live ? jsx("th", { className: "g" }) : null,
            jsx("th", { children: "Component" }),
            jsx("th", { children: "Version" }),
            jsx("th", { className: "s", children: "From" }),
            jsx("th", { className: "z", children: live ? "Status" : "Download" })
          ]
        })
      }),
      jsx("tbody", {
        children: [
          profileRow ? row({
            id: "profile",
            name: "Your hermretro profile",
            purpose: "A Hermes profile with just the game tools and skills",
            version: "",
            source: "this computer",
            bytes: 0,
            state: live ? profileRow : null
          }) : null,
          ...rows.map((item) => row({ ...item, state: live ? item.state : null }))
        ]
      })
    ]
  });
}
function InstallLog({ install, phase }) {
  const components = install?.run?.components ?? {};
  const lines = [];
  for (const id of ["gbdk", "cli", "uv", "emulator"]) {
    const component = components[id];
    for (const check of component?.checks ?? []) {
      lines.push(
        jsxs("div", {
          children: [
            jsx("span", { className: "ok", children: "✓ " }),
            `${check.file}  sha256 ${String(check.sha256).slice(0, 8)}…  ${check.reused ? "verified (cached)" : "verified"}`
          ]
        }, `${id}:${check.file}`)
      );
    }
    if (component?.state === "done" && !component.checks?.length) {
      lines.push(jsxs("div", { children: [jsx("span", { className: "ok", children: "✓ " }), `${id} ${component.version ?? ""} already installed, checked`] }, `${id}:reused`));
    }
    if (component?.state === "failed") {
      lines.push(jsxs("div", { className: "bad", children: ["✗ ", `${id}: ${component.error ?? "failed"}`] }, `${id}:failed`));
    }
  }
  if (phase === "running" && install?.current) {
    const label = (install.current === "cli" ? "GB Studio and its packages" : { gbdk: "GBDK", uv: "uv", emulator: "Python, PyBoy and Pillow" }[install.current]) ?? install.current;
    lines.push(jsxs("div", { className: "w", children: [jsx("span", { className: "run", children: "↓ " }), `Installing ${label}…`] }, "now"));
  }
  return lines.length ? jsx("div", { "aria-live": "polite", className: "cs-log", role: "log", children: lines }) : null;
}
function InstallFacts({ manifest, status, root }) {
  const node = nodeState(status.data?.node);
  return jsxs("dl", {
    className: "cs-onb-facts",
    children: [
      jsx("dt", { children: "Download" }),
      jsx("dd", { children: formatBytes(manifest?.bytes ?? 0, { approx: true }) }),
      jsx("dt", { children: "On disk" }),
      jsx("dd", { children: formatBytes(manifest?.disk_bytes ?? 0, { approx: true }) }),
      jsx("dt", { children: "Installs to" }),
      jsx("dd", { className: "path", title: root ?? "", children: shortPath(root) ?? "the plugin's deps folder" }),
      jsx("dt", { children: "Already here" }),
      jsx("dd", { className: node.ok ? "good" : "bad", children: node.ok ? `Node.js ${node.version} (from Hermes)` : "Node.js not found" })
    ]
  });
}
function profileRowState(installer, profileStep, status) {
  const profile = status.data?.profile;
  if (!profile) {
    return null;
  }
  if (profileStep?.state === "done") {
    return "done";
  }
  if (installer.profileWork.state === "failed") {
    return "failed";
  }
  return installer.profileWork.state !== "idle" || profile.studio?.installed ? "running" : "pending";
}
function InstallPanel({ ctx, status, install, step, profileStep, doctor }) {
  const installer = useInstaller({ ctx, doctor, install, status, toolchainDone: step.state === "done" });
  const data = install.data;
  return jsxs("div", {
    className: "cs-content",
    children: [
      jsx(InstallFacts, { manifest: data?.manifest, root: data?.root, status }),
      jsx(InstallProgress, { elsewhere: installer.elsewhere, install: data?.install, phase: installer.phase, verifying: installer.verifying }),
      data?.manifest ? jsx(DownloadTable, { install: data.install, manifest: data.manifest, phase: installer.phase, profileRow: profileRowState(installer, profileStep, status) }) : install.isError ? null : jsx(Working, { quiet: true, children: "Reading the download list…" }),
      jsx(InstallLog, { install: data?.install, phase: installer.phase }),
      ...InstallError({ installer }),
      jsx(InstallActions, { compact: true, installer })
    ]
  });
}

// page/pages/setup/remove-tools.js
function RemoveTools({ status, doctor }) {
  const [state, setState] = useState("idle");
  const [failure, setFailure] = useState(null);
  const updating = useUpdating();
  const remove = async () => {
    if (isUpdating()) {
      setFailure(UPDATING_MESSAGE);
      setState("idle");
      return;
    }
    setState("working");
    setFailure(null);
    try {
      const { data } = await callBackend(RPC_REMOVE_TOOLS, {}, 12e4);
      if (!data?.ok) {
        throw new Error(data?.error || "The tools could not be removed.");
      }
      host.notify({ kind: "success", message: `Downloaded tools removed (${formatBytes(data.removed_bytes, { unit: "MB" })}). Your games are untouched.` });
      status.refetch?.();
      doctor.refetch?.();
      setState("idle");
    } catch (error) {
      const { message, notLoaded } = describeRequestError(error);
      setFailure(notLoaded ? "This hermretro backend cannot remove the tools yet. Restart Hermes, then try again." : message || String(error));
      setState("idle");
    }
  };
  return jsxs("div", {
    className: "cs-col",
    style: { gap: 8 },
    children: [
      state === "confirm" ? jsxs("div", {
        className: "cs-actions",
        children: [
          jsx("span", { children: "Delete the downloaded tools? Your games stay. Building again needs a new install (about a minute)." }),
          jsx(Button, { disabled: updating, onClick: () => void remove(), size: "sm", variant: "destructive", children: "Remove" }),
          jsx(Button, { onClick: () => setState("idle"), size: "sm", variant: "ghost", children: "Cancel" })
        ]
      }) : jsx("div", {
        children: jsx(Button, {
          disabled: state === "working" || updating,
          onClick: () => setState("confirm"),
          size: "sm",
          variant: "ghost",
          children: state === "working" ? "Removing…" : "Remove downloaded tools"
        })
      }),
      failure ? jsx("p", { className: "cs-error", children: failure }) : null
    ]
  });
}

// page/pages/setup/toolchain-step.js
var COMPONENT_STATUS = { ready: "Ready", missing: "Missing", incompatible: "Incompatible", unknown: "Unknown" };
function ComponentRow({ component }) {
  const status = component.optional && component.status !== "ready" ? "optional" : component.status ?? "unknown";
  const versions = [
    component.required ? `needs ${component.required}` : null,
    component.detected ? `found ${component.detected}` : component.status === "missing" ? "not found" : null
  ].filter(Boolean).join(" · ");
  return jsxs("div", {
    className: "cs-comp",
    children: [
      jsx(Glyph, { state: component.status === "ready" ? "done" : component.status === "incompatible" ? "error" : "todo" }),
      jsxs("span", {
        className: "name",
        children: [component.label ?? component.id, component.optional ? jsx("small", { children: "optional" }) : null]
      }),
      jsx("span", { className: "ver", children: versions }),
      jsx("span", { className: `st ${status}`, children: status === "optional" ? "Optional" : COMPONENT_STATUS[status] ?? "Unknown" }),
      component.detail ? jsx("span", { className: "detail", children: component.detail }) : null
    ]
  });
}
function ToolchainBody({ ctx, step, status, doctor, install, steps }) {
  if (!status.data?.ok) {
    return jsx(Small, { children: "Checked once the plugin is on." });
  }
  const platform = status.data.platform;
  const engine = status.data.engine ?? {};
  const deps = status.data.deps ?? {};
  const report = doctor.data;
  const rows = (report?.ok ? report.components ?? [] : []).filter((component) => component.id !== "node" && component.id !== "runtime").map((component) => jsx(ComponentRow, { component }, component.id ?? component.label));
  return jsxs("div", {
    className: "cs-content",
    children: [
      jsx(Lede, {
        children: "The compilers and emulator that turn a project into a real Game Boy Color ROM and let Hermes playtest it: GB Studio, GBDK and PyBoy."
      }),
      step.state === "error" ? jsxs("div", {
        className: "cs-col",
        style: { gap: 10 },
        children: [
          jsx("p", {
            className: "cs-error",
            children: `Toolchain check failed: ${report?.error || describeRequestError(doctor.error).message || "unknown error"}`
          }),
          jsx("div", {
            className: "cs-actions",
            children: jsxs(Button, {
              disabled: doctor.isFetching,
              onClick: () => void doctor.refetch?.(),
              size: "sm",
              variant: "default",
              children: [jsx(Codicon, { name: "refresh", size: 14, spinning: doctor.isFetching }), "Check again"]
            })
          })
        ]
      }) : null,
      platform && platform.qualified === false ? jsx(Small, {
        tone: "warn",
        children: platform.rosetta ? "Hermes is running under Rosetta (Intel emulation). It works, but builds are slower: install the Apple Silicon version of Hermes." : platform.node_arch && platform.machine && platform.node_arch !== platform.machine ? `The Node.js hermretro found is built for ${platform.node_arch}, but this computer is ${platform.machine}. It works, but slower: install the ${platform.machine === "arm64" ? "Apple Silicon" : platform.machine} version of Node.js (for example with Homebrew in /opt/homebrew).` : `${platform.system ?? "This system"} ${platform.machine ?? ""} has not been tested yet; some steps may not work.`
      }) : null,
      (step.state === "todo" || step.state === "blocked") && install ? jsx(InstallPanel, { ctx, doctor, install, profileStep: steps?.find((item) => item.id === "profile"), status, step }) : null,
      step.state === "done" || step.state === "error" ? jsx("div", {
        className: "cs-comps",
        children: [
          jsx(ComponentRow, {
            component: {
              id: "engine",
              label: "Chromatic engine",
              status: engine.present ? engine.verified === false ? "incompatible" : "ready" : "missing",
              detected: engine.present ? engine.version : "",
              detail: engine.detail || (engine.present && engine.verified === false ? "Engine could not be verified." : "")
            }
          }, "engine"),
          ...rows
        ]
      }) : null,
      !report && step.state === "checking" ? jsx(Working, { quiet: true, children: "Checking installed tools…" }) : null,
      deps.toolchain_root && step.state === "done" ? jsxs("span", {
        className: "cs-faint",
        children: [
          "Install folder: ",
          jsx("span", { className: "cs-mono", children: deps.toolchain_root }),
          deps.toolchain_cache_reused_from ? ". Downloads were reused from an existing ModRetro install on this computer." : ""
        ]
      }) : null,
      step.state === "done" ? jsx(RemoveTools, { doctor, status }) : null
    ]
  });
}

// page/pages/setup/wizard.js
function stepBody(step, props) {
  switch (step.id) {
    case "profile":
      return jsx(ProfileBody, props);
    case "toolchain":
      return jsx(ToolchainBody, { ...props, step });
    case "firmware":
      return jsx(FirmwareBody, { ...props, step });
    case "devmode":
      return jsx(DevModeBody, { ...props, step });
    case "devicecli":
      return jsx(DeviceSoftwareBody, { ...props, step });
    default:
      return jsx(HardwareBody, { ...props, step });
  }
}
function StepRail({ steps, shownId, autoId, onPick, skipped }) {
  const done = steps.filter((step) => step.state === "done").length;
  const item = (step, position) => jsxs(
    "button",
    {
      "aria-current": step.id === shownId ? "step" : void 0,
      className: "cs-rail-item",
      "data-auto": step.id === autoId ? "" : void 0,
      "data-state": step.state,
      onClick: () => onPick(step.id),
      type: "button",
      children: [
        jsx("span", { className: "n", children: String(position + 1).padStart(2, "0") }),
        jsx("span", { className: "l", children: STEP_SHORT[step.id] }),
        jsx(Glyph, { state: step.state })
      ]
    },
    step.id
  );
  return jsxs("nav", {
    "aria-label": "Setup steps",
    className: "cs-rail",
    children: [
      jsx("span", { className: "cs-rail-group", children: "Make games" }),
      ...steps.filter((step) => !step.hardware).map((step) => item(step, steps.indexOf(step))),
      jsxs("span", { className: "cs-rail-group second", children: [jsx("span", { children: "Your Chromatic" }), jsx("span", { children: "optional" })] }),
      ...steps.filter((step) => step.hardware).map((step) => item(step, steps.indexOf(step))),
      jsx("div", {
        className: "cs-meter",
        children: steps.map(
          (step, position) => jsx(
            "button",
            {
              "aria-label": `Step ${position + 1}: ${step.title} (${(INDICATOR[step.state] ?? INDICATOR.waiting).label})`,
              className: step.id === HARDWARE_STEPS[0] ? "gap" : void 0,
              "data-auto": step.id === autoId ? "" : void 0,
              "data-state": step.state,
              onClick: () => onPick(step.id),
              type: "button",
              children: jsx("i", {})
            },
            step.id
          )
        )
      }),
      jsx("span", { className: "cs-faint cs-mono", children: `${done} / ${steps.length} done${skipped ? " · emulator only" : ""}` })
    ]
  });
}
function StepStage({ step, number, total, children, footer }) {
  const tag = step.state === "done" ? jsx("span", { className: "cs-tag good", children: "Done" }) : step.state === "error" ? jsx("span", { className: "cs-tag bad", children: "Problem" }) : step.state === "skipped" ? jsx("span", { className: "cs-tag quiet", children: "Skipped" }) : step.hardware ? jsx("span", { className: "cs-tag quiet", children: "Only for a physical Chromatic" }) : null;
  return jsxs("section", {
    "aria-live": "polite",
    className: "cs-stage",
    children: [
      jsxs("div", {
        className: "cs-stage-head",
        children: [
          jsxs("p", {
            className: "cs-eyebrow",
            children: [
              jsx("span", { className: "cs-accent", children: `Step ${number} of ${total}` }),
              jsx("span", { children: step.hardware ? "Your Chromatic" : "Make games" }),
              tag
            ]
          }),
          jsx("h2", { className: "cs-word cs-title", children: step.title })
        ]
      }),
      children,
      footer
    ]
  });
}
function SetupWizard({ ctx, steps, shown, autoId, backend, status, doctor, gateway, install, update, onPick, onContinue }) {
  const position = steps.indexOf(shown);
  const reviewing = shown.id !== autoId;
  const waiting = !reviewing && !shown.manual && !shown.complete && shown.state !== "blocked";
  const left = [];
  const right = [];
  if (position > 0) {
    left.push(
      jsxs(
        Button,
        {
          onClick: () => onPick(steps[position - 1].id),
          size: "sm",
          variant: "ghost",
          children: [jsx(Codicon, { name: "arrow-left", size: 14 }), "Back"]
        },
        "back"
      )
    );
  }
  if (waiting) {
    left.push(jsx(Working, { quiet: true, children: "Checking automatically; this page moves on when the step is done." }, "waiting"));
  }
  if (shown.hardware && !shown.complete) {
    right.push(
      jsx(Button, { onClick: () => update({ hardwareSkipped: true }), size: "sm", variant: "ghost", children: "Skip, I'll use the emulator" }, "skip")
    );
  }
  if (shown.state === "skipped") {
    right.push(
      jsx(
        Button,
        { onClick: () => update({ hardwareSkipped: false, hardwareWanted: true }), size: "sm", variant: "outline", children: "Set up my Chromatic" },
        "unskip"
      )
    );
  }
  if (reviewing) {
    right.push(
      jsxs(
        Button,
        { onClick: onContinue, size: "sm", variant: "default", children: ["Continue", jsx(Codicon, { name: "arrow-right", size: 14 })] },
        "continue"
      )
    );
  }
  const footer = left.length || right.length ? jsxs("div", {
    className: "cs-stage-foot",
    children: [jsx("div", { className: "cs-row", style: { flex: "1 1 auto" }, children: left }), jsx("div", { className: "cs-row", children: right })]
  }) : null;
  return jsx(StepStage, {
    step: shown,
    number: position + 1,
    total: steps.length,
    footer,
    children: jsxs("div", {
      className: "cs-content",
      children: [
        shown.state === "skipped" ? jsx(Small, { children: "Skipped: you are using the emulator. Streaming and flashing stay off until your Chromatic is set up." }) : null,
        stepBody(shown, { backend, ctx, doctor, gateway, install, status, steps, update })
      ]
    })
  });
}

// page/pages/setup/setup-page.js
function SetupPage({ shell }) {
  const { autoId, backend, choosing, ctx, doctor, gateway, install, memory, pick, shown, status, steps, update } = shell;
  return jsxs("div", {
    className: "cs-setup",
    children: [
      jsx(StepRail, { autoId, onPick: pick, shownId: shown?.id ?? null, skipped: Boolean(memory.hardwareSkipped), steps }, "rail"),
      shown ? jsx(SetupWizard, { autoId, backend, ctx, doctor, gateway, install, onContinue: shell.unpin, onPick: pick, shown, status, steps, update }, "wizard") : choosing ? jsx(HardwareChoice, { steps, update }, "choice") : jsx(
        SetupComplete,
        {
          doctor,
          emulatorOnly: shell.emulatorOnly,
          onGo: shell.go,
          onRecheck: shell.refresh,
          onSetUpDevice: shell.setUpDevice,
          pluginUpdate: shell.pluginUpdate,
          rechecking: shell.refreshing,
          status,
          steps
        },
        "complete"
      ),
      jsx(Flyer, {}, "flyer")
    ]
  });
}

// page/pages/setup/onboarding/onboarding.js
var ONBOARD_STAGES = [
  ["install", "Install"],
  ["chromatic", "Your hardware"],
  ["make", "First game"]
];
function OnboardHeader({ stage, end = null }) {
  const index = ONBOARD_STAGES.findIndex(([id]) => id === stage);
  return jsxs("header", {
    className: "cs-top",
    children: [
      jsxs("span", { className: "cs-brand", style: { cursor: "default" }, children: ["herm", jsx("span", { children: "retro" })] }),
      index >= 0 ? jsxs("div", {
        "aria-label": `Setup, step ${index + 1} of ${ONBOARD_STAGES.length}: ${ONBOARD_STAGES[index][1]}`,
        className: "cs-onb-steps",
        role: "img",
        children: [
          ...ONBOARD_STAGES.map(([id], position) => jsx("i", { className: position < index ? "done" : position === index ? "cur" : "" }, id)),
          jsx("span", { children: `${index + 1} / ${ONBOARD_STAGES.length} · ${ONBOARD_STAGES[index][1]}` })
        ]
      }) : jsx("span", { className: "cs-onb-steps", children: jsx("span", { children: "First-time setup" }) }),
      end ? jsx("div", { className: "cs-top-end", children: end }) : null
    ]
  });
}
function OnboardWelcome({ manifest, onStart }) {
  return jsxs("div", {
    className: "cs-onb-hero",
    children: [
      jsxs("div", {
        className: "cs-col",
        style: { gap: 24 },
        children: [
          jsxs("p", {
            className: "cs-eyebrow",
            children: [jsx("span", { className: "cs-accent", children: "● Welcome" }), jsx("span", { children: "First-time setup · a few minutes" })]
          }),
          jsxs("h1", { className: "cs-word", children: ["Make a game.", jsx("br", {}), jsx("span", { className: "cs-accent", children: "Play it tonight." })] }),
          jsx(Lede, {
            children: "hermretro turns a chat with Hermes into a real Game Boy Color game. Before your first game it needs the tools that build and playtest ROMs. Everything goes into the plugin's own folder."
          }),
          jsxs("div", {
            className: "cs-actions",
            style: { gap: 16 },
            children: [
              jsxs(Button, { onClick: onStart, size: "lg", variant: "default", children: ["Get started", jsx(Codicon, { name: "arrow-right", size: 14 })] }),
              manifest ? jsx("span", { className: "cs-faint cs-mono", children: `${formatBytes(manifest.bytes, { approx: true })} download · ${formatBytes(manifest.disk_bytes, { approx: true })} on disk` }) : null
            ]
          })
        ]
      }),
      jsx(Art, {})
    ]
  });
}
function TryDemo() {
  if (typeof host.openWorkspace !== "function") {
    return null;
  }
  return jsxs(Button, {
    onClick: () => emit("setup.demoRequested", {}),
    size: "sm",
    variant: "ghost",
    children: [jsx(Codicon, { name: "play", size: 14 }), "Try the demo while you wait"]
  });
}
function OnboardInstall({ ctx, status, install, toolchainDone, profileStep, doctor }) {
  const installer = useInstaller({ ctx, doctor, install, status, toolchainDone });
  const data = install.data;
  const { phase } = installer;
  const title = phase === "failed" ? ["One part ", jsx("span", { className: "cs-bad", children: "didn't finish" }, "a")] : phase === "review" ? ["Here's what gets ", jsx("span", { className: "cs-accent", children: "downloaded" }, "a")] : ["Setting up the ", jsx("span", { className: "cs-accent", children: "studio" }, "a")];
  const lede = phase === "failed" ? "Nothing is broken, and the parts that finished are kept. Try again, or ask Hermes to look at the error." : phase === "review" ? "Every file is pinned to an exact version and checked against its SHA-256 before it is used. Nothing is installed system-wide: it all goes into hermretro's folder in your Hermes home, where your games live too." : "You can leave this page: the install keeps running, and this page moves on when the tools are verified.";
  return jsxs("div", {
    className: "cs-onb-split",
    children: [
      jsxs("div", {
        className: "cs-col",
        style: { gap: 22 },
        children: [
          jsxs("p", {
            className: "cs-eyebrow",
            children: [
              jsx("span", { className: phase === "failed" ? "cs-bad" : "cs-accent", children: "Step 1 of 3" }),
              jsx("span", { children: { review: "Install", running: "Installing", failed: "Stopped", done: "Installed" }[phase] })
            ]
          }),
          jsx("h2", { className: "cs-word cs-title", children: title }),
          jsx(Lede, { children: lede }),
          jsx(InstallFacts, { manifest: data?.manifest, root: data?.root, status }),
          jsx(InstallProgress, { elsewhere: installer.elsewhere, install: data?.install, phase, verifying: installer.verifying }),
          ...InstallError({ installer }),
          jsx(InstallActions, { installer }),
          phase === "running" ? jsx(TryDemo, {}) : null
        ]
      }),
      jsxs("div", {
        className: "cs-col",
        style: { gap: 18 },
        children: [
          data?.manifest ? jsx(DownloadTable, { install: data.install, manifest: data.manifest, phase, profileRow: profileRowState(installer, profileStep, status) }) : install.isError && !installer.unsupported ? jsx("p", { className: "cs-error", children: describeRequestError(install.error).message }) : installer.unsupported ? null : jsx(Working, { quiet: true, children: "Reading the download list…" }),
          jsx(InstallLog, { install: data?.install, phase }),
          data?.manifest && !data.manifest.exact ? jsx("span", { className: "cs-faint", children: `Sizes were measured on ${data.manifest.measured_on} and are approximate here.` }) : null
        ]
      })
    ]
  });
}
function OnboardChromatic({ onEmulator, onDevice }) {
  const card = ({ tag, tone, title, text: text2, onClick, art, primary }) => jsxs("button", {
    className: primary ? "cs-hwcard primary" : "cs-hwcard",
    onClick,
    type: "button",
    children: [
      art,
      jsxs("span", {
        className: "cs-col",
        style: { gap: 8 },
        children: [
          jsx("span", { className: `cs-tag ${tone}`, style: { alignSelf: "flex-start" }, children: tag }),
          jsx("span", { className: "cs-word t", children: title }),
          jsx("span", { className: "cs-small", children: text2 })
        ]
      })
    ]
  });
  return jsxs("div", {
    className: "cs-col",
    style: { gap: 28 },
    children: [
      jsxs("p", { className: "cs-eyebrow", children: [jsx("span", { className: "cs-accent", children: "Step 2 of 3" }), jsx("span", { children: "Your hardware" })] }),
      jsxs("h2", { className: "cs-word cs-onb-title", children: ["Do you have a ", jsx("span", { className: "cs-accent", children: "Chromatic?" })] }),
      jsx(Lede, { children: "Every game plays in the emulator here, with sound. With a ModRetro Chromatic you can also stream games to it and write them to a cartridge." }),
      jsxs("div", {
        className: "cs-hwcards",
        children: [
          card({
            art: jsx("span", { "aria-hidden": true, className: "cs-hwart screen", children: jsx(Codicon, { name: "play", size: 22 }) }),
            onClick: onEmulator,
            primary: true,
            tag: "Ready now",
            text: "Make and play games in the emulator. You can add a Chromatic later from Setup.",
            title: "Start making games",
            tone: "good"
          }),
          card({
            art: jsx("span", { "aria-hidden": true, className: "cs-hwart device" }),
            onClick: onDevice,
            tag: "Optional · 4 more steps",
            text: "Update its firmware, turn on Developer Mode and install ModRetro's device software.",
            title: "Set up my Chromatic",
            tone: "quiet"
          })
        ]
      })
    ]
  });
}
var IDEAS = [
  ["Tiny platformer", "a tiny platformer where a frog hops across lily pads to reach home"],
  ["Top-down adventure", "a top-down adventure where a gardener collects three seeds to open a gate"],
  ["Puzzle game", "a short puzzle game about pushing crates onto switches"],
  ["Spooky story", "a spooky little story game set in an abandoned lighthouse"]
];
function OnboardMake({ onDone, onDevice }) {
  const [idea, setIdea] = useState("");
  const handOff = (plan) => {
    if (idea.trim() || plan) {
      emit("setup.firstIdea", { idea: idea.trim(), plan });
    }
  };
  const go = (plan) => {
    handOff(plan);
    onDone();
  };
  return jsxs("div", {
    className: "cs-onb-hero",
    children: [
      jsxs("div", {
        className: "cs-col",
        style: { gap: 22 },
        children: [
          jsxs("p", {
            className: "cs-eyebrow",
            children: [jsx("span", { className: "cs-good", children: "● Studio ready" }), jsx("span", { children: "Step 3 of 3" })]
          }),
          jsxs("h2", { className: "cs-word cs-onb-title", children: ["What do you", jsx("br", {}), "want to ", jsx("span", { className: "cs-accent", children: "make?" })] }),
          jsxs("div", {
            className: "cs-idea",
            children: [
              jsx("textarea", {
                "aria-label": "Your game idea",
                onChange: (event) => setIdea(event.target.value),
                onKeyDown: (event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault();
                    go(false);
                  }
                },
                placeholder: "A frog who delivers mail across a flooded town…",
                rows: 3,
                value: idea
              }),
              jsxs("div", {
                className: "cs-row",
                style: { justifyContent: "space-between" },
                children: [
                  jsx("span", { className: "cs-faint", children: "It goes into the New Game box on Build. Nothing is sent until you press send there." }),
                  jsxs("div", {
                    className: "cs-row",
                    style: { gap: 8 },
                    children: [
                      jsx(Button, { onClick: () => go(true), size: "sm", variant: "outline", children: "Plan it first" }),
                      jsxs(Button, {
                        onClick: () => go(false),
                        size: "sm",
                        variant: "default",
                        children: ["Continue in Build", jsx(Codicon, { name: "arrow-right", size: 14 })]
                      })
                    ]
                  })
                ]
              })
            ]
          }),
          jsx("div", {
            "aria-label": "Ideas",
            className: "cs-ideas",
            role: "group",
            children: IDEAS.map(([label, text2]) => jsx("button", { onClick: () => setIdea(text2), type: "button", children: label }, label))
          }),
          jsxs("div", {
            className: "cs-row",
            style: { gap: 8 },
            children: [
              jsx(Button, { onClick: () => go(false), size: "sm", variant: "ghost", children: "Skip, take me to the studio" }),
              onDevice ? jsx(Button, {
                onClick: () => {
                  handOff(false);
                  onDevice();
                },
                size: "sm",
                variant: "ghost",
                children: "Set up my Chromatic first"
              }) : null
            ]
          })
        ]
      }),
      jsx(Art, {})
    ]
  });
}
function Onboarding({ ctx, screen: screen2, status, install, steps, update, onFinish, onDevice, doctor }) {
  const toolchain = steps.find((step) => step.id === "toolchain");
  const profileStep = steps.find((step) => step.id === "profile");
  let body2;
  if (screen2 === "checking") {
    body2 = jsx(Working, { children: "Checking what is already installed…" });
  } else if (screen2 === "welcome") {
    body2 = jsx(OnboardWelcome, { manifest: install.data?.manifest, onStart: () => update({ onboardStarted: true }) });
  } else if (screen2 === "install") {
    body2 = jsx(OnboardInstall, { ctx, doctor, install, profileStep, status, toolchainDone: toolchain?.state === "done" });
  } else if (screen2 === "chromatic") {
    body2 = jsx(OnboardChromatic, { onDevice, onEmulator: () => update({ hardwareSkipped: true, hardwareWanted: false }) });
  } else {
    body2 = jsx(OnboardMake, { onDevice, onDone: onFinish });
  }
  const section = useRef(null);
  const shown = useRef(screen2);
  useEffect(() => {
    if (shown.current === screen2) {
      return;
    }
    shown.current = screen2;
    const title = section.current?.querySelector("h1, h2");
    if (title) {
      title.tabIndex = -1;
      title.focus?.({ preventScroll: true });
    }
  }, [screen2]);
  return jsx("section", { className: "cs-onb", "data-screen": screen2, ref: section, children: body2 });
}

// page/pages/setup/index.js
function SetupBadge({ nav }) {
  return nav.setupPending ? jsx("i", { "aria-label": "setup is not finished", className: "pip", role: "img" }) : null;
}
var SETUP_PAGE = {
  id: "setup",
  label: "Setup",
  Page: SetupPage,
  Badge: SetupBadge,
  css: [SETUP_CSS, ONBOARDING_CSS],
  events: {
    "setup.firstIdea": "Onboarding's last screen handed its idea on: { idea, plan }. Build opens New Game with the idea in its box and Build it (plan false) or Plan first (plan true) chosen, not sent.",
    "setup.demoRequested": "Try the demo was picked during setup: {}. The Emulator page opens the bundled demo beside the chat; it needs neither the toolchain nor a model."
  }
};

// page/pages/build/studio-needed.js
function StudioNeeded({ status }) {
  const profile = status.data?.profile;
  const [working, setWorking] = useState(false);
  const [failure, setFailure] = useState(null);
  const exists = Boolean(profile?.studio?.exists);
  const starting = Boolean(profile?.studio?.installed) && !working;
  const repair = async () => {
    if (working || !profile) {
      return;
    }
    setWorking(true);
    setFailure(null);
    try {
      await createStudioProfileOnce(profile);
      host.notify({ kind: "success", message: "hermretro profile ready" });
      status.refetch?.();
    } catch (error) {
      setFailure(String(error?.message ?? error));
    } finally {
      setWorking(false);
    }
  };
  return jsxs("section", {
    className: "cs-studio-needed cs-content",
    role: "status",
    children: [
      jsx("h2", { children: exists ? "The hermretro profile needs repair" : "The hermretro profile is not set up" }),
      jsx(Lede, {
        children: "Build chats run only in the hermretro profile, where the game-making tools and skills live. " + (exists ? "It exists but is not answering as it should." : "It has not been created yet.")
      }),
      working ? jsx(Working, { children: exists ? "Repairing the profile…" : "Creating the profile…" }) : jsxs("div", {
        className: "cs-col",
        children: [
          // Finished but not answering yet: usually Hermes is still starting it; Repair stays offered,
          // because a profile whose plugin was turned off never answers.
          starting ? jsx(Working, { children: "The profile is set up. Waiting for Hermes to start it…" }) : null,
          jsx("div", {
            className: "cs-actions",
            children: jsx(Button, {
              disabled: !profile,
              onClick: repair,
              size: "sm",
              variant: starting ? "ghost" : "default",
              children: exists ? "Repair" : "Set up the profile"
            })
          })
        ]
      }),
      failure ? jsx("p", { className: "cs-error", children: failure }) : null
    ]
  });
}

// page/pages/build/build-entry.js
function Build({ shell }) {
  if (!studioTarget()) {
    return jsx(StudioNeeded, { status: shell.status }, "studio-needed");
  }
  return jsx(BuildPage, {
    ctx: shell.ctx,
    games: shell.gameList,
    loaded: Boolean(shell.games.data),
    localPending: shell.buildPending,
    changePending: shell.changeBuildPending,
    onLibraryChanged: shell.gamesChanged,
    onSelect: shell.selectBuild,
    pendingGames: shell.games.data?.pending ?? [],
    selection: shell.buildSelection,
    updating: shell.pluginUpdate?.phase === "updating"
  }, "build");
}

// page/pages/build/chat/events.js
var queuedEvents = /* @__PURE__ */ new Map();
var queuedFlush = null;
var STREAM_EVENTS = /* @__PURE__ */ new Set(["message.delta", "reasoning.delta", "thinking.delta", "tool.progress"]);
function flushChatEvents() {
  queuedFlush = null;
  const batches = [...queuedEvents];
  queuedEvents.clear();
  for (const [stored, events] of batches) {
    patchChat(stored, (chat2) => events.reduce(reduceChat, chat2));
    const chat = BUILD_CHATS.get()[stored];
    if (chat && !chat.busy && chat.heldPick) {
      void applyBuildPick(stored);
    }
    if (events.some((event) => event.type === "message.start" || event.type === "tool.start" || event.type === "tool.generating")) {
      schedulePromptCheck(stored);
    }
  }
}
function queueChatEvent(stored, event) {
  const list = queuedEvents.get(stored);
  if (list) {
    list.push(event);
  } else {
    queuedEvents.set(stored, [event]);
  }
  if (!STREAM_EVENTS.has(event.type)) {
    if (queuedFlush) {
      queuedFlush.cancel();
    }
    flushChatEvents();
    return;
  }
  if (!queuedFlush) {
    const visible = typeof document === "undefined" || document.visibilityState !== "hidden";
    if (visible && typeof requestAnimationFrame === "function") {
      const id = requestAnimationFrame(flushChatEvents);
      queuedFlush = { cancel: () => cancelAnimationFrame(id) };
    } else {
      const id = setTimeout(flushChatEvents, 50);
      queuedFlush = { cancel: () => clearTimeout(id) };
    }
  }
}
var buildChatListeners = [];
function watchBuildChats(ctx) {
  const listen = typeof ctx.onEvent === "function" ? ctx.onEvent : typeof host.onEvent === "function" ? host.onEvent : null;
  for (const stop of buildChatListeners) {
    try {
      stop?.();
    } catch {
    }
  }
  buildChatListeners = [];
  if (!listen) {
    return;
  }
  for (const type of BUILD_EVENTS) {
    buildChatListeners.push(listen(type, (event) => {
      const stored = buildRuntime.get(event?.session_id);
      if (!stored) {
        return;
      }
      if (event.type === "session.replay_gap") {
        void reopenBuildChat(stored);
        return;
      }
      queueChatEvent(stored, event);
    }));
  }
}

// page/pages/build/composer/composer.css.js
var COMPOSER_CSS = `
/* status and the message box */
.cs-b-comp { align-self: center; background: var(--ui-bg-secondary); border-radius: 16px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); box-sizing: border-box; display: flex; flex-direction: column; gap: 8px; margin: 0 clamp(14px, 3cqi, 28px) 16px; max-width: var(--cs-b-width); padding: 9px 9px 9px 14px; width: calc(100% - 2 * clamp(14px, 3cqi, 28px)); }
.cs-b-comp.asking { gap: 4px; padding: 10px 10px 8px 12px; }
.cs-b-comp:focus-within { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 60%, var(--ui-stroke-secondary)); }
.cs-b-comp textarea { background: transparent; border: 0; color: var(--ui-text-primary); font: inherit; font-size: 13.5px; line-height: 1.5; max-height: 200px; min-height: 22px; outline: none; padding: 4px 0; resize: none; }
.cs-b-send, .cs-b-stop { align-items: center; appearance: none; border: 0; border-radius: 50%; cursor: pointer; display: inline-flex; flex: none; height: 30px; justify-content: center; transition: opacity .15s ease, transform .1s ease; width: 30px; }
.cs-b-send { background: var(--ui-accent); color: white; }
.cs-b-send:disabled { background: var(--ui-bg-quaternary); color: var(--ui-text-quaternary); cursor: default; }
.cs-b-send:not(:disabled):active, .cs-b-stop:active { transform: scale(.94); }
.cs-b-stop { background: var(--ui-text-primary); }
.cs-b-stop i { background: var(--ui-bg-editor); border-radius: 2px; height: 10px; width: 10px; }
.cs-b-status { align-items: center; animation: cs-b-in .18s ease-out; border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; font-size: 12px; gap: 8px; margin: -1px -1px 0 -6px; padding: 0 0 8px; }
.cs-b-status b { color: var(--ui-text-primary); font-weight: 600; }
.cs-b-status.wait b { color: var(--ui-yellow); }
.cs-b-status.stuck b { color: var(--ui-red); }
.cs-b-pulse { animation: cs-b-pulse 1.6s infinite; background: var(--ui-green); border-radius: 50%; flex: none; height: 7px; width: 7px; }
.cs-b-pulse.wait { animation-name: cs-b-pulse-y; background: var(--ui-yellow); }
.cs-b-pulse.off { animation: none; background: var(--ui-text-quaternary); }
@keyframes cs-b-pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--ui-green) 55%, transparent); } 70%, 100% { box-shadow: 0 0 0 7px transparent; } }
@keyframes cs-b-pulse-y { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--ui-yellow) 55%, transparent); } 70%, 100% { box-shadow: 0 0 0 7px transparent; } }
`;

// page/pages/build/composer/mentions.css.js
var MENTIONS_CSS = `
/* @ assets */
.cs-b-comp { position: relative; }
.cs-b-chip.mention { background: color-mix(in srgb, var(--ui-accent) 15%, transparent); box-shadow: none; color: var(--ui-accent); }
.cs-b-mention { animation: cs-b-in .12s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 12px; bottom: calc(100% + 6px); box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 18px 48px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; gap: 1px; left: 0; max-height: min(50svh, 380px); overflow-y: auto; padding: 6px; position: absolute; width: min(340px, 100%); z-index: 30; }
.cs-b-mention-head { align-items: center; display: flex; font-size: 11px; justify-content: space-between; padding: 4px 6px 6px; }
.cs-b-mention-row { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 7px; color: inherit; cursor: pointer; display: flex; font: inherit; font-size: 12.5px; gap: 9px; padding: 5px 6px; text-align: left; }
.cs-b-mention-row b { flex: 1; font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-mention-row span.cs-faint { font-size: 11px; }
.cs-b-mention-row[aria-selected='true'] { background: color-mix(in srgb, var(--ui-accent) 14%, transparent); }
.cs-b-mention-row .cs-b-th { cursor: inherit; height: 28px; width: 28px; }
.cs-b-mention p { margin: 6px; }
`;

// page/pages/build/composer/model-picker.css.js
var MODEL_PICKER_CSS = `
/* model and effort: the button under the message box */
.cs-b-mp { position: relative; min-width: 0; }
.cs-b-mp-chip { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 8px; color: var(--ui-text-secondary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 6px; max-width: 100%; min-width: 0; padding: 4px 8px 4px 5px; transition: background .12s ease, color .12s ease; white-space: nowrap; }
.cs-b-mp-chip:hover, .cs-b-mp-chip.open { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-mp-chip.open { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); }
.cs-b-mp-chip:disabled { cursor: default; opacity: .55; }
.cs-b-mp-chip.warn { color: var(--ui-yellow); }
.cs-b-mp-name { overflow: hidden; text-overflow: ellipsis; }
.cs-b-mp-dot { color: var(--ui-text-quaternary); }
.cs-b-mp-next { border: 1px solid color-mix(in srgb, var(--ui-accent) 50%, transparent); border-radius: 4px; color: var(--ui-accent); font-size: 10px; line-height: 15px; padding: 0 5px; }
.cs-b-mp-mark { align-items: center; background: color-mix(in srgb, var(--ui-accent) 22%, var(--ui-bg-quaternary)); border-radius: 4px; color: var(--ui-text-primary); display: inline-flex; flex: none; font: 800 9px/1 var(--dt-font-sans, inherit); height: 16px; justify-content: center; width: 16px; }
.cs-b-logo { align-items: center; background: none; display: inline-flex; justify-content: center; }
.cs-b-logo img { display: block; max-height: 100%; max-width: 100%; object-fit: contain; }
.cs-b-logo.plate { background: var(--ui-text-primary); border-radius: 4px; padding: 2px; }
.cs-b-mp-pmark { display: inline-flex; }
.cs-b-mp-pmark.cs-b-logo { height: 18px; width: 18px; }
.cs-b-mp-glyph.cs-b-logo { height: 14px; }
.cs-b-mp-bolt { align-items: center; color: var(--ui-yellow); display: inline-flex; flex: none; }
/* the panel: provider rail | models | effort, and the speed bar along the bottom */
.cs-b-mp-pop { animation: cs-b-in .14s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 12px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 18px 48px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; left: 0; max-width: calc(100vw - 24px); overflow: hidden; position: absolute; top: calc(100% + 6px); width: 560px; z-index: 30; }
.cs-b-mp-pop.up { bottom: calc(100% + 8px); top: auto; }
.cs-b-mp-body { display: flex; height: 304px; min-height: 0; }
.cs-b-mp-rail { align-items: center; border-right: 1px solid var(--ui-stroke-tertiary); display: flex; flex: none; flex-direction: column; gap: 4px; overflow-y: auto; padding: 8px 0; scrollbar-width: none; width: 46px; }
.cs-b-mp-tile { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 7px; color: var(--ui-text-tertiary); cursor: pointer; display: flex; flex: none; font: 800 12px/1 var(--dt-font-sans, inherit); height: 30px; justify-content: center; position: relative; width: 30px; }
.cs-b-mp-tile:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-mp-tile[aria-pressed='true'] { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-mp-tile[aria-pressed='true']::before { background: var(--ui-accent); border-radius: 0 2px 2px 0; content: ''; height: 18px; left: -8px; position: absolute; top: 6px; width: 2px; }
.cs-b-mp-sep { background: var(--ui-stroke-tertiary); flex: none; height: 1px; margin: 2px 0; width: 22px; }
.cs-b-mp-models { display: flex; flex: 1; flex-direction: column; min-width: 0; }
.cs-b-mp-search { align-items: center; border-bottom: 1px solid var(--ui-stroke-secondary); color: var(--ui-text-quaternary); display: flex; gap: 8px; margin: 8px 10px 2px; padding: 5px 6px; }
.cs-b-mp-search:focus-within { border-bottom-color: var(--ui-accent); }
.cs-b-mp-search input { background: transparent; border: 0; color: var(--ui-text-primary); flex: 1; font: inherit; font-size: 13px; min-width: 0; outline: none; }
.cs-b-mp-head { color: var(--ui-text-quaternary); display: flex; flex-wrap: wrap; font-size: 11px; gap: 0 5px; min-width: 0; padding: 6px 16px 2px; }
.cs-b-mp-head b { color: var(--ui-text-secondary); font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
.cs-b-mp-head span { white-space: nowrap; }
.cs-b-mp-list { display: flex; flex: 1; flex-direction: column; gap: 1px; min-height: 0; -webkit-mask-image: linear-gradient(black calc(100% - 28px), transparent); mask-image: linear-gradient(black calc(100% - 28px), transparent); overflow-y: auto; overscroll-behavior: contain; padding: 4px 8px 24px; }
.cs-b-mp-list > .cs-faint { margin: 0; padding: 10px 8px; }
.cs-b-mp-group { color: var(--ui-text-quaternary); flex: none; font: 700 9.5px/1.3 var(--dt-font-mono, ui-monospace, monospace); letter-spacing: .12em; padding: 8px 8px 3px; text-transform: uppercase; }
.cs-b-mp-item { align-items: center; border-radius: 7px; display: flex; flex: none; min-width: 0; }
.cs-b-mp-item:hover { background: var(--ui-bg-quaternary); }
.cs-b-mp-item.on { background: color-mix(in srgb, var(--ui-accent) 12%, transparent); }
.cs-b-mp-row { align-items: center; appearance: none; background: transparent; border: 0; color: var(--ui-text-primary); cursor: pointer; display: flex; flex: 1; font: inherit; font-size: 13px; gap: 8px; min-width: 0; padding: 6px 4px 6px 8px; text-align: left; }
.cs-b-mp-glyph { color: var(--ui-text-quaternary); flex: none; font: 800 10px/1 var(--dt-font-sans, inherit); text-align: center; width: 16px; }
.cs-b-mp-label { min-width: 0; overflow-wrap: anywhere; }
.cs-b-mp-tag { border: 1px solid var(--ui-stroke-secondary); border-radius: 4px; color: var(--ui-text-tertiary); flex: none; font-size: 10px; line-height: 15px; padding: 0 5px; }
.cs-b-mp-check { color: var(--ui-text-secondary); display: inline-flex; flex: none; }
.cs-b-mp-label.two { display: flex; flex-direction: column; white-space: normal; }
.cs-b-mp-label.two > span { overflow-wrap: anywhere; }
.cs-b-mp-from { color: var(--ui-text-quaternary); font-size: 11px; line-height: 1.3; }
.cs-b-mp-star { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 5px; color: var(--ui-text-quaternary); cursor: pointer; display: inline-flex; flex: none; height: 24px; justify-content: center; margin-right: 4px; opacity: 0; width: 24px; }
.cs-b-mp-item:hover .cs-b-mp-star, .cs-b-mp-item.on .cs-b-mp-star, .cs-b-mp-star:focus-visible, .cs-b-mp-item.starred .cs-b-mp-star { opacity: 1; }
.cs-b-mp-star:hover { color: var(--ui-text-primary); }
.cs-b-mp-item.starred .cs-b-mp-star { color: var(--ui-yellow); }
.cs-b-mp-effort { border-left: 1px solid var(--ui-stroke-tertiary); display: flex; flex: none; flex-direction: column; min-height: 0; padding: 8px 0 0; width: 172px; }
.cs-b-mp-ehead { align-items: baseline; color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font-size: 12px; gap: 0 8px; padding: 5px 14px 6px; }
.cs-b-mp-emodel { color: var(--ui-text-quaternary); font-size: 11px; margin-left: auto; min-width: 0; overflow-wrap: anywhere; text-align: right; }
.cs-b-mp-levels { display: flex; flex-direction: column; }
.cs-b-mp-levels button { align-items: center; appearance: none; background: transparent; border: 0; color: var(--ui-text-primary); cursor: pointer; display: flex; font: inherit; font-size: 13px; justify-content: space-between; padding: 5px 14px; text-align: left; white-space: nowrap; }
.cs-b-mp-levels button:hover:not(:disabled) { background: var(--ui-bg-quaternary); }
.cs-b-mp-levels button[aria-checked='true'] { background: color-mix(in srgb, var(--ui-accent) 10%, transparent); }
.cs-b-mp-levels button:disabled { color: var(--ui-text-quaternary); cursor: default; }
.cs-b-mp-enote { border-top: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-tertiary); font-size: 11px; line-height: 1.35; margin-top: auto; padding: 8px 14px 10px; }
.cs-b-mp-enote b { color: var(--ui-text-primary); display: block; font-size: 12px; font-weight: 500; }
.cs-b-mp-bar { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 10px; min-height: 44px; padding: 7px 10px; }
.cs-b-seg { background: var(--ui-bg-quaternary); border-radius: 8px; display: flex; gap: 2px; padding: 2px; }
.cs-b-seg button { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 4px; padding: 4px 10px; transition: background .12s ease, color .12s ease; white-space: nowrap; }
.cs-b-seg button:hover:not(:disabled) { color: var(--ui-text-primary); }
.cs-b-seg button[aria-checked='true'] { background: var(--ui-bg-secondary); box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-primary); }
.cs-b-seg button.cs-b-mp-fast[aria-checked='true'] { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 55%, transparent); color: var(--ui-yellow); }
.cs-b-seg button:disabled { cursor: default; opacity: .5; }
.cs-b-mp-manage { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 4px; padding: 4px 6px; white-space: nowrap; }
.cs-b-mp-manage:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-mp-held { color: var(--ui-text-tertiary); font-size: 11.5px; white-space: nowrap; }
.cs-b-mp-confirm { align-items: center; background: color-mix(in srgb, var(--ui-yellow) 10%, var(--ui-bg-secondary)); border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; font-size: 12px; gap: 8px; padding: 8px 12px; }
.cs-b-mp-pop.narrow .cs-b-mp-effort { width: 120px; }
.cs-b-mp-pop.narrow .cs-b-mp-emodel { display: none; }
/* too narrow for three columns: Effort moves under the models as a wrapping row */
.cs-b-mp-pop.tiny .cs-b-mp-body { flex-wrap: wrap; height: auto; }
.cs-b-mp-pop.tiny .cs-b-mp-rail, .cs-b-mp-pop.tiny .cs-b-mp-models { height: 250px; }
.cs-b-mp-pop.tiny .cs-b-mp-effort { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); flex-basis: 100%; padding: 4px 8px 8px; width: auto; }
.cs-b-mp-pop.tiny .cs-b-mp-ehead { padding: 4px 6px; }
.cs-b-mp-pop.tiny .cs-b-mp-levels { flex-direction: row; flex-wrap: wrap; gap: 2px; }
.cs-b-mp-pop.tiny .cs-b-mp-levels button { border-radius: 6px; gap: 4px; justify-content: center; padding: 4px 8px; }
.cs-b-comp-row { align-items: center; display: flex; gap: 8px; min-width: 0; }
@container (max-width: 560px) { .cs-b-mp-name, .cs-b-mp-dot { display: none; } }
.cs-sr { clip: rect(0 0 0 0); height: 1px; overflow: hidden; position: absolute; white-space: nowrap; width: 1px; }
.cs-b-link { appearance: none; background: none; border: 0; color: var(--ui-accent); cursor: pointer; font: inherit; font-size: 12px; padding: 0; }
`;

// page/pages/build/header.css.js
var HEADER_CSS = `
/* the header: the game title and switcher (switcher.js), status pill and Builds menu (builds-menu.js) */
.cs-b-swwrap { align-items: center; display: flex; gap: 10px; min-width: 0; position: relative; }
.cs-b-sw { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 8px; color: var(--ui-text-primary); cursor: pointer; display: inline-flex; gap: 8px; margin-left: -8px; min-width: 0; padding: 3px 8px; transition: background .12s ease; }
.cs-b-sw:hover, .cs-b-sw.open { background: var(--ui-bg-quaternary); }
.cs-b-sw h2 { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-sw > i { color: var(--ui-text-tertiary); }
.cs-b-sw-pop { animation: cs-b-in .14s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 12px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 18px 48px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; gap: 2px; left: -8px; max-width: calc(100vw - 24px); padding: 6px; position: absolute; top: calc(100% + 6px); width: 340px; z-index: 30; }
.cs-b-sw-pop > .cs-eyebrow { padding: 8px 8px 2px; }
.cs-b-sw-list { display: flex; flex-direction: column; gap: 2px; max-height: min(60svh, 460px); overflow-y: auto; overscroll-behavior: contain; }
.cs-b-sw-pop .cs-b-game { outline: none; width: 100%; }
.cs-b-sw-new { color: var(--ui-accent); }
.cs-b-sw-thumb { align-items: center; aspect-ratio: 160 / 144; background: var(--ui-bg-quaternary); border-radius: 4px; color: var(--ui-text-tertiary); display: inline-flex; flex: none; font-size: 0; height: 28px; image-rendering: pixelated; justify-content: center; object-fit: cover; overflow: hidden; width: auto; }
.cs-b-sw-thumb.add { background: transparent; border: 1px dashed var(--ui-stroke-secondary); color: var(--ui-accent); }
.cs-b-sw-key { color: var(--ui-text-quaternary); flex: none; font: 600 10px var(--dt-font-mono, ui-monospace, monospace); margin-left: 4px; }
.cs-b-sw-empty { margin: 0; padding: 8px; }
.cs-b-sw-pop.lib { width: 400px; }
.cs-b-sw-thumb.edit { background: transparent; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-accent); }
.cs-b-sw-go { color: var(--ui-text-tertiary); flex: none; }
.cs-b-sw-back { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-primary); cursor: pointer; display: flex; font: inherit; font-weight: 600; gap: 8px; outline: none; padding: 6px 8px; text-align: left; }
.cs-b-sw-back > i { color: var(--ui-text-tertiary); }
.cs-b-sw-back:hover, .cs-b-sw-back:focus-visible { background: var(--ui-bg-quaternary); }
.cs-b-sw-search { align-items: center; background: var(--ui-bg-editor); border-radius: 7px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-quaternary); display: flex; gap: 8px; margin: 2px 2px 4px; padding: 6px 9px; }
.cs-b-sw-search:focus-within { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-sw-search input { background: transparent; border: 0; color: var(--ui-text-primary); flex: 1; font: inherit; font-size: 12.5px; min-width: 0; outline: none; }
.cs-b-sw-pop .cs-b-game .go { color: var(--ui-accent); flex: none; font-size: 11.5px; opacity: 0; }
.cs-b-sw-pop .cs-b-game:hover .go, .cs-b-sw-pop .cs-b-game:focus-visible .go { opacity: 1; }
.cs-b-sw-foot { border-top: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-quaternary); font-size: 11px; margin: 4px 0 0; padding: 7px 8px 3px; }
.cs-b-needs { appearance: none; background: var(--ui-yellow); border: 0; border-radius: 999px; color: var(--ui-bg-editor); cursor: pointer; flex: none; font: 700 11px/18px inherit; padding: 0 9px; white-space: nowrap; }
.cs-b-others { align-items: center; color: var(--ui-text-tertiary); display: inline-flex; flex: none; font-size: 11.5px; gap: 6px; white-space: nowrap; }
.cs-b-otherdot { background: var(--ui-accent); border-radius: 50%; box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-accent) 25%, transparent); flex: none; height: 7px; width: 7px; }
.cs-b-ctx { animation: cs-b-in .1s ease-out; background: linear-gradient(var(--ui-bg-tertiary, var(--ui-bg-secondary)), var(--ui-bg-tertiary, var(--ui-bg-secondary))), var(--ui-bg-editor); border-radius: 8px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 12px 30px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; gap: 1px; min-width: 180px; padding: 4px; position: absolute; z-index: 40; }
.cs-b-ctx button { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 5px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; font-size: 12px; gap: 8px; outline: none; padding: 6px 9px; text-align: left; }
.cs-b-ctx button:hover:not(:disabled), .cs-b-ctx button:focus-visible { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-ctx button.danger { color: var(--ui-red); }
.cs-b-ctx button:disabled { cursor: default; opacity: .45; }
.cs-b-ctx hr { border: 0; border-top: 1px solid var(--ui-stroke-tertiary); margin: 3px 2px; }
.cs-b-pill { align-items: center; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-tertiary); display: inline-flex; flex: none; font-size: 11.5px; gap: 6px; padding: 2px 10px; white-space: nowrap; }
.cs-b-pill-dot { background: currentColor; border-radius: 50%; flex: none; height: 7px; width: 7px; }
.cs-b-pill.good { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-green) 35%, transparent); color: var(--ui-green); }
.cs-b-pill.warn { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 35%, transparent); color: var(--ui-yellow); }
.cs-b-pill.bad { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-red) 40%, transparent); color: var(--ui-red); }
.cs-b-pill.busy { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 40%, transparent); color: var(--ui-accent); font-variant-numeric: tabular-nums; }
.cs-b-pill .cs-b-spin { height: 8px; width: 8px; }
.cs-b-sw-pop.cs-b-builds { left: auto; right: 0; width: 420px; }
.cs-b-brow { align-items: center; border-radius: 8px; display: flex; gap: 10px; padding: 7px 8px; }
.cs-b-brow.on { background: var(--ui-bg-quaternary); }
.cs-b-brow .cs-col { gap: 0; min-width: 0; }
.cs-b-brow b { font-size: 12.5px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-brow small { color: var(--ui-text-quaternary); font-size: 11px; }
.cs-b-brow-acts { display: flex; flex: none; gap: 4px; }
`;

// page/pages/build/new-game.css.js
var NEW_GAME_CSS = `
/* New Game: the Build page's composer, centred, with the two ways to start under it (centred only while it fits:
   "safe" starts it at the top when it is taller than the area, so scrolling reaches the title) */
.cs-b-new { box-sizing: border-box; display: flex; flex: 1; flex-direction: column; gap: 18px; justify-content: safe center; margin: 0 auto; max-width: 680px; min-height: 0; overflow: auto; padding: 24px clamp(14px, 3cqi, 28px); width: 100%; }
.cs-b-new .cs-title { margin: 0; text-align: center; }
.cs-b-new .cs-b-comp { margin: 0; max-width: none; width: 100%; }
.cs-b-new .cs-b-comp textarea { max-height: 220px; min-height: 66px; }
.cs-b-opts { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }
@container (max-width: 560px) { .cs-b-opts { grid-template-columns: 1fr; } }
.cs-b-opt { align-items: flex-start; background: transparent; border: 0; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: inherit; cursor: pointer; display: flex; font: inherit; gap: 10px; padding: 12px 14px; text-align: left; }
.cs-b-opt:hover { box-shadow: inset 0 0 0 1px var(--ui-stroke-primary, var(--ui-text-tertiary)); }
.cs-b-opt:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-b-opt.on { background: color-mix(in srgb, var(--ui-accent) 8%, transparent); box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-opt-dot { border-radius: 50%; box-shadow: inset 0 0 0 1px var(--ui-text-tertiary); flex: none; height: 12px; margin-top: 3px; width: 12px; }
.cs-b-opt.on .cs-b-opt-dot { background: radial-gradient(var(--ui-accent) 42%, transparent 48%); box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-opt b { color: var(--ui-text-primary); display: block; font-size: 13.5px; font-weight: 600; }
.cs-b-opt span span { color: var(--ui-text-tertiary); display: block; font-size: 12.5px; line-height: 1.45; margin-top: 2px; }
.cs-b-opt em { color: var(--ui-text-quaternary, var(--ui-text-tertiary)); display: block; font: 700 10px/1.3 ${MONO}; font-style: normal; letter-spacing: .1em; margin-top: 7px; text-transform: uppercase; }
/* No signed-in model provider in the studio profile: one frosted line with the way to fix it */
.cs-b-provider { align-items: center; -webkit-backdrop-filter: blur(10px) saturate(.8); backdrop-filter: blur(10px) saturate(.8); background: var(--cs-at-glass, var(--ui-bg-tertiary)); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 55%, transparent); color: var(--ui-text-secondary); display: flex; flex-wrap: wrap; font-size: 12.5px; gap: 10px; line-height: 1.45; padding: 10px 12px; position: relative; z-index: 1; }
.cs-b-provider > span { flex: 1 1 260px; min-width: 0; }
.cs-b-provider > i { flex: none; }
.cs-b-provider b { color: var(--ui-text-primary); font-weight: 600; }
.cs-b-provider > i:first-child { color: var(--ui-yellow); }
`;

// page/pages/build/player/inline-player.css.js
var INLINE_PLAYER_CSS = `
/* the game, resting under the newest build: its screen at twice its size in a dark frame, Play at the corner */
.cs-b-pc { animation: cs-b-in .2s ease-out; display: flex; flex-direction: column; gap: 6px; max-width: 560px; transition: opacity .2s ease; }
.cs-b-pc-stage { align-items: center; background: color-mix(in srgb, var(--ui-bg-editor) 55%, black); border-radius: 12px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); display: flex; justify-content: center; padding: 16px; position: relative; }
.cs-b-pc.busy .cs-b-pc-stage, .cs-b-pc.unplayable .cs-b-pc-stage { opacity: .62; }
.cs-b-pc-screen { appearance: none; background: none; border: 0; cursor: pointer; display: block; padding: 0; width: min(320px, 100%); }
.cs-b-pc-screen:disabled { cursor: default; }
.cs-b-pc-img { aspect-ratio: 160 / 144; border-radius: 3px; display: block; image-rendering: pixelated; object-fit: cover; width: 100%; }
.cs-b-pc-go { align-items: center; appearance: none; backdrop-filter: blur(6px); background: color-mix(in srgb, white 14%, transparent); border: 0; border-radius: 999px; bottom: 12px; color: white; cursor: pointer; display: inline-flex; font: inherit; font-size: 12.5px; gap: 6px; padding: 6px 13px; position: absolute; right: 12px; transition: background .12s ease; }
.cs-b-pc-go:hover { background: color-mix(in srgb, white 24%, transparent); }
.cs-b-pc-wait { bottom: 12px; color: var(--ui-text-tertiary); font-size: 12px; position: absolute; right: 14px; }
.cs-b-pc-note { border-left: 2px solid var(--ui-stroke-secondary); color: var(--ui-text-secondary); font-size: 12.5px; line-height: 1.45; margin: 0; padding-left: 10px; }
.cs-b-old { color: var(--ui-text-quaternary); font-size: 11.5px; margin: 0; }
.cs-b-live { background: var(--ui-text-quaternary); border-radius: 50%; flex: none; height: 7px; transition: background .2s ease; width: 7px; }
.cs-b-live.on { animation: cs-b-pulse 1.6s infinite; background: var(--ui-green); }

/* the inline player */
.cs-ip { animation: cs-b-in .22s ease-out; background: color-mix(in srgb, var(--ui-bg-editor) 70%, black); border-radius: 12px; box-shadow: 0 0 0 1px color-mix(in srgb, var(--ui-accent) 55%, transparent), 0 14px 36px color-mix(in srgb, black 35%, transparent); container-type: inline-size; display: flex; flex-direction: column; overflow: hidden; }
.cs-ip-bar { align-items: center; background: var(--ui-bg-secondary); border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 4px; min-height: 40px; padding: 5px 8px 5px 12px; white-space: nowrap; }
.cs-ip-bar.annotating { background: color-mix(in srgb, var(--ui-accent) 14%, var(--ui-bg-secondary)); }
.cs-ip-title { font-size: 12.5px; margin-left: 4px; overflow: hidden; text-overflow: ellipsis; }
.cs-ip-hint { font-size: 12px; margin-left: 6px; overflow: hidden; text-overflow: ellipsis; }
.cs-ip-hint.marked { color: var(--ui-accent); font-weight: 600; }
.cs-ip-ann-ic { color: var(--ui-accent); display: inline-flex; }
.cs-ip-sep { background: var(--ui-stroke-secondary); height: 16px; margin: 0 4px; width: 1px; }
.cs-ip-btn { align-items: center; background: none; border: 0; border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; display: inline-flex; flex: none; font: inherit; font-size: 12px; gap: 5px; height: 28px; padding: 0 7px; }
.cs-ip-btn:hover:not(:disabled) { background: var(--ui-bg-tertiary); color: var(--ui-text-primary); }
.cs-ip-btn:disabled { cursor: default; opacity: .45; }
.cs-ip-btn[aria-pressed=true] { background: color-mix(in srgb, var(--ui-accent) 18%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 55%, transparent); color: var(--ui-text-primary); }
.cs-ip-btn.primary { background: var(--ui-accent); color: white; }
.cs-ip-btn.primary:hover:not(:disabled) { background: color-mix(in srgb, var(--ui-accent) 85%, white); color: white; }
.cs-ip-seg { border: 1px solid var(--ui-stroke-secondary); border-radius: 7px; display: inline-flex; flex: none; overflow: hidden; }
.cs-ip-seg button { background: none; border: 0; color: var(--ui-text-secondary); cursor: pointer; font: 600 11px ${MONO}; height: 24px; padding: 0 7px; }
.cs-ip-seg button[aria-checked=true] { background: var(--ui-accent); color: white; }
.cs-ip-seg button:disabled { cursor: default; opacity: .4; }
.cs-ip-menu { flex: none; position: relative; }
.cs-ip-pop { background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 9px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 12px 30px color-mix(in srgb, black 35%, transparent); display: flex; flex-direction: column; max-height: 300px; min-width: 170px; overflow-y: auto; padding: 4px; position: absolute; right: 0; top: calc(100% + 6px); z-index: 20; }
.cs-ip-pop-row { align-items: center; background: none; border: 0; border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; font-size: 12.5px; gap: 8px; padding: 6px 8px; text-align: left; }
.cs-ip-pop-row:hover { background: var(--ui-bg-tertiary); color: var(--ui-text-primary); }
.cs-ip-pop-row > span { flex: 1; }
.cs-ip-swatch { border-radius: 4px; box-shadow: inset 0 0 0 1px color-mix(in srgb, white 25%, transparent); display: block; height: 14px; width: 14px; }
.cs-ip-body { display: flex; min-height: 0; }
.cs-ip-stage { align-items: center; background: radial-gradient(ellipse at center, color-mix(in srgb, var(--ui-bg-editor) 85%, black), color-mix(in srgb, var(--ui-bg-editor) 55%, black) 75%); display: flex; flex: 1; flex-direction: column; justify-content: center; min-width: 0; padding: 16px; }
.cs-ip-screen { flex: none; max-width: 100%; position: relative; }
.cs-ip-screen[data-view=screen] { border-radius: 4px; box-shadow: 0 0 0 1px color-mix(in srgb, white 8%, transparent), 0 20px 50px color-mix(in srgb, black 55%, transparent); overflow: hidden; }
.cs-ip-screen:fullscreen { align-items: center; background: black; border-radius: 0; display: flex; height: 100%; justify-content: center; width: 100%; }
.cs-ip-fit { flex: none; max-width: 100%; }
.cs-ip-fit .cs-rp-stage, .cs-ip-fit .cs-rp-stage:not(.off) { height: 100%; width: 100%; }
.cs-ip-panel { background: var(--ui-bg-secondary); border-left: 1px solid var(--ui-stroke-tertiary); display: flex; flex: none; flex-direction: column; gap: 4px; font-size: 12.5px; overflow-y: auto; padding: 12px 14px; width: 300px; }
.cs-ip-panel.tabs { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); padding-top: 0; width: auto; }
.cs-ip-sec { display: flex; flex-direction: column; gap: 6px; }
.cs-ip-sh { align-items: center; color: var(--ui-text-quaternary); display: flex; font: 700 10px ${MONO}; justify-content: space-between; letter-spacing: .08em; margin-top: 10px; text-transform: uppercase; }
.cs-ip-sec:first-child .cs-ip-sh, .cs-ip-panel > .cs-ip-sh:first-child { margin-top: 0; }
.cs-ip-count { color: var(--ui-green); }
.cs-ip-note { color: var(--ui-text-secondary); line-height: 1.45; margin: 0; }
.cs-ip-checks, .cs-ip-marks { display: flex; flex-direction: column; gap: 8px; list-style: none; margin: 0; padding: 0; }
.cs-ip-check label { align-items: flex-start; color: var(--ui-text-secondary); cursor: pointer; display: flex; gap: 8px; }
.cs-ip-check input { accent-color: var(--ui-accent); flex: none; margin: 2px 0 0; }
.cs-ip-check label > span { display: flex; flex-direction: column; gap: 1px; }
.cs-ip-check em { font-size: 11px; font-style: normal; }
.cs-ip-check[data-state=done] .cs-ip-check-text { color: var(--ui-text-quaternary); text-decoration: line-through; }
.cs-ip-check[data-state=untested] em { color: var(--ui-yellow); }
.cs-ip-check[data-state=reported] em { color: var(--ui-accent); }
.cs-ip-check[data-state=fixed] em { color: var(--ui-green); }
.cs-ip-ask { background: color-mix(in srgb, var(--ui-yellow) 7%, transparent); border-radius: 8px; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 40%, transparent); color: var(--ui-text-secondary); display: flex; flex-direction: column; gap: 6px; margin: 6px 0 0 22px; padding: 8px; }
.cs-ip-keys { background: var(--ui-bg-secondary); border-top: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-quaternary); display: flex; flex-wrap: wrap; font-size: 11px; gap: 14px; padding: 6px 12px; }
.cs-ip-keys.stacked { background: none; border: 0; flex-direction: column; gap: 5px; padding: 0; }
.cs-ip-keys kbd { border: 1px solid var(--ui-stroke-secondary); border-bottom-width: 2px; border-radius: 3px; color: var(--ui-text-tertiary); font: 600 10px ${MONO}; padding: 0 4px; }
.cs-ip-moment { flex-wrap: wrap; gap: 4px; }
.cs-ip-tabs { border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; margin: 0 -14px 8px; padding: 0 6px; }
.cs-ip-tabs button { background: none; border: 0; color: var(--ui-text-secondary); cursor: pointer; font: inherit; font-size: 12px; padding: 8px 10px; }
.cs-ip-tabs button[aria-selected=true] { box-shadow: inset 0 -2px var(--ui-accent); color: var(--ui-text-primary); }
.cs-ip-fold { align-items: center; background: var(--ui-bg-secondary); border: 0; border-left: 1px solid var(--ui-stroke-tertiary); color: var(--ui-text-secondary); cursor: pointer; display: flex; flex: none; flex-direction: column; gap: 10px; padding: 12px 0; width: 34px; }
.cs-ip-fold:hover { color: var(--ui-text-primary); }
.cs-ip-pill { background: var(--ui-yellow); border-radius: 999px; color: black; font: 700 10px ${MONO}; padding: 2px 5px; }
.cs-ip-pill.ok { background: var(--ui-green); }
.cs-ip-vt { font-size: 12px; writing-mode: vertical-rl; }
.cs-ip-mark { border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: flex; flex-direction: column; gap: 8px; padding: 8px; }
.cs-ip-mark-head { align-items: center; display: flex; gap: 8px; }
.cs-ip-n { background: var(--ui-accent); border-radius: 50%; color: white; display: grid; flex: none; font: 700 10.5px ${MONO}; height: 18px; place-items: center; width: 18px; }
.cs-ip-crop { border-radius: 5px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary); flex: none; height: 44px; image-rendering: pixelated; object-fit: contain; width: 44px; }
.cs-ip-mark-name { display: flex; flex: 1; flex-direction: column; min-width: 0; }
.cs-ip-mark-name span { font-size: 11px; }
.cs-ip-colors { align-items: center; display: flex; gap: 6px; }
.cs-ip-swatch-in { border-radius: 6px; cursor: pointer; display: block; height: 24px; position: relative; width: 24px; }
.cs-ip-swatch-in i { border-radius: 6px; box-shadow: inset 0 0 0 1px color-mix(in srgb, white 22%, transparent); display: block; height: 100%; width: 100%; }
.cs-ip-swatch-in.changed { outline: 2px solid var(--ui-accent); outline-offset: 1px; }
.cs-ip-swatch-in input { cursor: pointer; height: 100%; inset: 0; opacity: 0; position: absolute; width: 100%; }
.cs-ip-mark-note { background: var(--ui-bg-editor); border: 1px solid var(--ui-stroke-secondary); border-radius: 7px; color: var(--ui-text-primary); font: inherit; font-size: 12.5px; padding: 6px 8px; resize: vertical; }
.cs-ip-mark-note:focus { border-color: var(--ui-accent); outline: none; }
.cs-b-bc > .cs-ip, .cs-b-bc > .cs-b-pc { margin: 0 12px 12px; }
@container (max-width: 640px) { .cs-ip-lbl, .cs-ip-hint { display: none; } }
@media (prefers-reduced-motion: reduce) { .cs-ip, .cs-b-pc, .cs-b-live.on { animation: none; } }
`;

// page/pages/build/transcript/build-card.css.js
var BUILD_CARD_CSS = `
/* a build: one quiet line (number, title, time), what changed under it, what was tested; no box around it */
.cs-b-bc { animation: cs-b-in .2s ease-out; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.cs-b-bc-head { align-items: center; display: flex; flex-wrap: wrap; gap: 4px 10px; min-height: 26px; }
.cs-b-bc-title { color: var(--ui-text-primary); font-size: 13.5px; font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
.cs-b-bc-meta { font-size: 11.5px; white-space: nowrap; }
.cs-b-bn { border-radius: 5px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); flex: none; font: 700 10.5px/1 ${MONO}; padding: 4px 6px; }
.cs-b-bn.old { color: var(--ui-text-tertiary); }
.cs-b-bn.bad { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-red) 55%, transparent); color: var(--ui-red); }
.cs-b-bn.live { box-shadow: inset 0 0 0 1px var(--ui-accent); color: var(--ui-accent); }
.cs-b-bc.bad .cs-b-bc-title { color: var(--ui-red); }
.cs-b-bc-sum { color: var(--ui-text-secondary); line-height: 1.55; margin: 0; }
.cs-b-bc-changes { display: flex; flex-direction: column; font-size: 12.5px; gap: 5px; list-style: none; margin: 0; padding: 0 0 0 2px; }
.cs-b-bc-changes li { align-items: center; color: var(--ui-text-tertiary); display: flex; gap: 8px; min-width: 0; }
.cs-b-bc-mark { color: var(--ui-yellow); flex: none; font: 700 12px ${MONO}; text-align: center; width: 10px; }
.cs-b-bc-changes li[data-kind='added'] .cs-b-bc-mark { color: var(--ui-green); }
.cs-b-bc-changes li[data-kind='removed'] .cs-b-bc-mark { color: var(--ui-red); }
.cs-b-bc-foot { align-items: center; color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font-size: 12px; gap: 6px 14px; padding-left: 2px; }
.cs-b-bc-foot .cs-b-link { align-items: center; display: inline-flex; gap: 3px; }
.cs-b-ok { color: var(--ui-green); font-weight: 700; }
.cs-b-bc-details { border-left: 2px solid var(--ui-stroke-tertiary); display: grid; font-size: 12.5px; gap: 12px 20px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-left: 2px; padding: 2px 0 4px 12px; }
.cs-b-bc-details p { line-height: 1.45; margin: 5px 0 0; }
.cs-b-bc-details pre { margin: 6px 0 0; white-space: pre-wrap; }
.cs-b-ba { display: flex; flex-direction: column; gap: 8px; padding: 2px 0; }
.cs-b-ba-pair { align-items: center; display: flex; gap: 12px; }
.cs-b-ba-side { align-items: center; appearance: none; background: none; border: 0; color: inherit; cursor: zoom-in; display: flex; flex-direction: column; font: inherit; gap: 4px; min-width: 0; padding: 0; }
.cs-b-ba-img { align-items: center; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 10px 10px; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); box-sizing: border-box; display: flex; height: 72px; justify-content: center; padding: 6px; width: 72px; }
.cs-b-ba-side:not(.now) .cs-b-ba-img { opacity: .72; }
.cs-b-ba-img img, .cs-b-ba-img .cs-b-spr { height: 100%; image-rendering: pixelated; max-height: 100%; max-width: 100%; object-fit: contain; width: auto; }
.cs-b-ba-cap { color: var(--ui-text-quaternary); font-size: 11px; }
.cs-b-ba-side.now .cs-b-ba-cap { color: var(--ui-text-secondary); }
.cs-b-ba-arrow { color: var(--ui-text-quaternary); flex: none; font-size: 16px; }
.cs-b-ba-acts { gap: 8px; }
/* next steps (a reply's suggestions) */
.cs-b-next-steps { display: flex; flex-wrap: wrap; gap: 8px; }
.cs-b-sugg-chip { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12.5px; gap: 5px; padding: 5px 12px; transition: box-shadow .12s ease, color .12s ease; }
.cs-b-sugg-chip:hover:not(:disabled) { box-shadow: inset 0 0 0 1px var(--ui-accent); color: var(--ui-text-primary); }
.cs-b-sugg-chip:disabled { cursor: default; opacity: .5; }
.cs-b-sugg-chip > i { color: var(--ui-accent); }
`;

// page/pages/build/transcript/cards.css.js
var CARDS_CSS = `
/* cards */
.cs-b-card { animation: cs-b-in .2s ease-out; border-radius: 12px; display: flex; flex-direction: column; gap: 10px; padding: 12px 14px; }
/* a question or an approval, asked in the message box: no box of its own */
.cs-b-comp .cs-b-card.ask, .cs-b-comp .cs-b-card.warn { animation: none; gap: 8px; padding: 2px 0; }
.cs-b-comp .cs-b-card > .cs-row:first-child { color: var(--ui-text-tertiary); font-size: 12px; }
.cs-b-comp .cs-b-card > .cs-row:first-child b { font-weight: 500; }
.cs-b-card.warn > .cs-row:first-child > i { color: var(--ui-yellow); }
/* in the thread (something went wrong, a turn that stopped): a rule beside it, no fill */
.cs-b-card.bad, .cs-b-tx .cs-b-card.warn { border-left: 2px solid color-mix(in srgb, var(--ui-red) 70%, transparent); border-radius: 0; gap: 6px; padding: 2px 0 2px 12px; }
.cs-b-tx .cs-b-card.warn { border-left-color: color-mix(in srgb, var(--ui-yellow) 70%, transparent); }
.cs-b-card.bad > .cs-row > i { color: var(--ui-red); }
.cs-b-card p { margin: 0; }
.cs-b-qs { display: flex; flex-direction: column; gap: 14px; }
.cs-b-q { display: flex; flex-direction: column; gap: 7px; }
.cs-b-qt { font-weight: 600; margin: 0; }
.cs-b-choices { display: flex; flex-direction: column; gap: 2px; }
.cs-b-choice { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 8px; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; gap: 10px; padding: 6px 8px; text-align: left; transition: background .12s ease, color .12s ease; }
.cs-b-choice:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-choice kbd { border: 1px solid var(--ui-stroke-secondary); border-bottom-width: 2px; border-radius: 3px; color: var(--ui-text-tertiary); font: 600 10px ${MONO}; padding: 0 4px; }
.cs-b-choice[aria-pressed='true'] { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-b-choice[aria-pressed='true'] kbd { border-color: var(--ui-text-secondary); color: var(--ui-text-primary); }
.cs-b-sugg { color: var(--ui-text-quaternary); flex: none; font-size: 11.5px; }
.cs-b-own { background: transparent; border: 0; color: var(--ui-text-primary); font: inherit; outline: none; padding: 6px 8px 2px 36px; }
.cs-b-own::placeholder { color: var(--ui-text-quaternary); }
.cs-b-own:focus-visible { border-radius: 6px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); }
.cs-b-cmd { background: var(--ui-bg-quaternary); border-radius: 6px; font: 11px/1.5 ${MONO}; margin: 0; overflow: auto; padding: 8px 10px; white-space: pre-wrap; }
.cs-b-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.cs-b-chip { align-items: center; background: var(--ui-bg-secondary); border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); display: inline-flex; font-size: 11.5px; gap: 5px; max-width: 100%; overflow: hidden; padding: 2px 9px; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-chip.pic { padding-left: 3px; }
.cs-b-chip.pic img { border-radius: 4px; display: block; flex: none; height: 20px; image-rendering: pixelated; object-fit: contain; width: 20px; }
.cs-b-tool .cs-b-chips { padding-left: 22px; }
.cs-b-stopped { align-items: center; color: var(--ui-text-tertiary); display: flex; flex-wrap: wrap; font-size: 12px; gap: 10px; }

/* empty and loading */
.cs-b-empty { align-content: center; display: grid; flex: 1; gap: 12px; justify-items: start; padding: 24px; }
.cs-b-hello { padding: 30px 0 4px; }
.cs-b-skel { display: flex; flex-direction: column; gap: 10px; margin-top: 18px; }
.cs-b-skel i { animation: cs-b-skel 1.2s ease-in-out infinite; background: var(--ui-bg-quaternary); border-radius: 8px; display: block; height: 14px; }
.cs-b-skel i:nth-child(1) { align-self: flex-end; height: 34px; width: 46%; } .cs-b-skel i:nth-child(2) { width: 82%; } .cs-b-skel i:nth-child(3) { width: 64%; }
.cs-b-jump { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 999px; bottom: 12px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary), 0 6px 18px color-mix(in srgb, black 30%, transparent); color: var(--ui-text-primary); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 6px; left: 50%; padding: 5px 12px; position: absolute; transform: translateX(-50%); }
`;

// page/pages/build/transcript/transcript.css.js
var TRANSCRIPT_CSS = `
/* the conversation */
.cs-b-chat { display: flex; flex-direction: column; min-height: 0; min-width: 0; position: relative; }
.cs-b-head { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); box-sizing: border-box; display: flex; gap: 10px; min-height: 50px; padding: 8px clamp(14px, 3cqi, 28px); width: 100%; }
.cs-b-head .cs-word { font-size: 22px; }
.cs-top-profile { align-items: center; border-radius: 999px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-tertiary); cursor: default; display: inline-flex; font-size: 11px; gap: 5px; margin-left: 10px; padding: 1px 9px 1px 7px; white-space: nowrap; }
.cs-b-txwrap { display: flex; flex: 1; flex-direction: column; min-height: 0; position: relative; }
.cs-b-tx { flex: 1; -webkit-mask-image: linear-gradient(transparent, black 18px); mask-image: linear-gradient(transparent, black 18px); min-height: 0; overflow-anchor: none; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.cs-b-chat { --cs-b-width: clamp(720px, 62cqi, 1280px); }
.cs-b-col { box-sizing: border-box; display: flex; flex-direction: column; gap: 22px; margin: 0 auto; max-width: var(--cs-b-width); padding: 22px clamp(14px, 3cqi, 28px) 18px; width: 100%; }
.cs-b-earlier { display: flex; justify-content: center; }
.cs-b-turn { display: flex; flex-direction: column; gap: 14px; }
.cs-b-turn:not([data-live]) { contain: layout style; }
.cs-b-user { align-self: flex-end; animation: cs-b-in .18s ease-out; background: var(--ui-bg-quaternary); border-radius: 16px 16px 4px 16px; display: flex; flex-direction: column; gap: 6px; line-height: 1.55; max-width: min(78%, 640px); overflow-wrap: anywhere; padding: 9px 14px; white-space: pre-wrap; }
.cs-b-user.queued { background: transparent; border: 1px dashed var(--ui-stroke-secondary); color: var(--ui-text-secondary); }
.cs-b-qlabel { color: var(--ui-text-quaternary); font-size: 11px; }
.cs-b-her { animation: cs-b-in .2s ease-out; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.cs-b-who { color: var(--ui-text-quaternary); font-size: 11.5px; }
.cs-b-agent { color: var(--ui-text-primary); line-height: 1.65; min-width: 0; overflow-wrap: anywhere; }
/* The app un-does Typography's margins only inside its own chat ([data-slot='aui_assistant-message-content']).
   Here its \`.prose :where(img) { margin: 2em 0 }\` would slide a MEDIA: image down out of its reserved frame,
   over the next paragraph, and \`.prose :where(p)\` would space paragraphs looser than the chat. */
.cs-b-agent .aui-md :where(p, [data-tool-media-paragraph]) { margin-block: var(--paragraph-gap, 0.7rem) 0; }
.cs-b-agent .aui-md > :first-child { margin-top: 0; }
.cs-b-agent .aui-md [data-slot='aui_markdown-image'] img { margin: 0; }
.cs-b-note { border-left: 2px solid var(--ui-stroke-secondary); color: var(--ui-text-secondary); font-size: 12.5px; line-height: 1.5; margin: 2px 0; padding: 1px 0 1px 10px; white-space: pre-wrap; }
@keyframes cs-b-in { from { opacity: 0; transform: translateY(4px); } }
`;

// page/pages/build/transcript/worked-mode.css.js
var WORKED_MODE_CSS = `
/* Worked for…: Simple / Technical, and what it did in words */
.cs-b-wk-mode { display: flex; justify-content: flex-end; margin: 2px 0 4px; max-width: 680px; }
.cs-b-wk-mode .cs-v-seg button { font-size: 11px; padding: 2px 9px; }
.cs-b-gist { max-width: 56ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
`;

// page/pages/build/transcript/worked.css.js
var WORKED_CSS = `
/* Worked for… */
.cs-b-wk { display: flex; flex-direction: column; }
.cs-b-wk-row { align-items: center; display: flex; flex-wrap: wrap; gap: 4px 8px; }
.cs-b-wk-head { align-items: center; align-self: flex-start; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; flex-wrap: wrap; font: inherit; font-size: 12px; gap: 7px; margin-left: -6px; max-width: 100%; padding: 4px 8px 4px 6px; transition: background .12s ease, color .12s ease; }
.cs-b-wk-head:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-secondary); }
.cs-b-wk-head b { color: var(--ui-text-secondary); font-weight: 600; }
.cs-b-ico { align-items: center; color: var(--ui-green); display: inline-flex; flex: none; height: 14px; justify-content: center; width: 14px; }
.cs-b-ico.interrupted { color: var(--ui-text-tertiary); } .cs-b-ico.error { color: var(--ui-red); }
.cs-b-wk-body { display: grid; grid-template-rows: 0fr; transition: grid-template-rows .22s ease; }
.cs-b-wk[data-open='true'] > .cs-b-wk-body { grid-template-rows: 1fr; }
.cs-b-wk-inner { border-left: 2px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; gap: 3px; margin: 6px 0 2px 6px; min-height: 0; overflow: hidden; padding-left: 12px; }
.cs-b-wk[data-open='false'] .cs-b-wk-inner { margin-top: 0; }
.cs-b-wk.live .cs-b-wk-inner { border-left-color: color-mix(in srgb, var(--ui-accent) 55%, transparent); }
.cs-b-tool { animation: cs-b-in .16s ease-out; color: var(--ui-text-tertiary); display: flex; flex-direction: column; font-size: 12.5px; gap: 5px; padding: 3px 0; }
.cs-b-tool-line { align-items: center; display: flex; gap: 8px; min-width: 0; }
.cs-b-tool[data-state='running'] { color: var(--ui-text-primary); }
.cs-b-tool[data-state='running'] .cs-b-ico { color: var(--ui-accent); }
.cs-b-tool[data-state='failed'] .cs-b-ico { color: var(--ui-red); }
.cs-b-tool[data-state='stopped'] .cs-b-ico { color: var(--ui-text-quaternary); }
.cs-b-tool-name { flex: none; }
.cs-b-tool-detail { color: var(--ui-text-quaternary); flex: 0 1 auto; font-size: 11.5px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-tool[data-state='failed'] .cs-b-tool-detail { color: var(--ui-red); white-space: normal; }
.cs-b-tool-assets { padding-left: 22px; }
.cs-b-next { color: var(--ui-text-quaternary); font-size: 12px; padding-left: 22px; }
.cs-b-dur { color: var(--ui-text-quaternary); flex: none; font: 600 10.5px ${MONO}; font-variant-numeric: tabular-nums; }
.cs-b-bar { background: var(--ui-bg-quaternary); border-radius: 2px; height: 3px; margin-left: 22px; max-width: 220px; overflow: hidden; }
.cs-b-bar i { background: var(--ui-accent); display: block; height: 100%; transition: width .3s ease; }
.cs-b-shimmer { animation: cs-b-sheen 2.2s linear infinite; background: linear-gradient(90deg, var(--ui-text-secondary) 0%, var(--ui-text-primary) 40%, var(--ui-text-secondary) 60%) 0 0 / 200% 100%; -webkit-background-clip: text; background-clip: text; color: transparent; }
@keyframes cs-b-sheen { to { background-position: -200% 0; } }
.cs-b-wk-assets { align-items: center; appearance: none; background: transparent; border: 0; border-radius: 6px; color: var(--ui-accent); cursor: pointer; display: inline-flex; font: inherit; font-size: 12px; gap: 7px; padding: 3px 7px 3px 4px; transition: background .12s ease; }
.cs-b-wk-assets:hover { background: var(--ui-bg-quaternary); }
.cs-b-stack { align-items: center; display: inline-flex; }
.cs-b-stack-i { background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-secondary) 0 50%) 0 0 / 6px 6px; border-radius: 4px; box-shadow: 0 0 0 1.5px var(--ui-bg-editor); display: inline-flex; height: 20px; overflow: hidden; width: 20px; }
.cs-b-stack-i + .cs-b-stack-i { margin-left: -6px; }
.cs-b-stack-i img { height: 100%; image-rendering: pixelated; object-fit: cover; width: 100%; }
.cs-b-wk-inner.phased { border-left: 0; gap: 0; margin-left: 0; padding-left: 0; }
.cs-b-phases { background: var(--ui-bg-secondary); border-radius: 9px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); margin: 4px 0 2px; max-width: 680px; overflow: hidden; }
.cs-b-ph + .cs-b-ph { border-top: 1px solid var(--ui-stroke-tertiary); }
.cs-b-ph-head { align-items: center; appearance: none; background: transparent; border: 0; border-radius: inherit; color: var(--ui-text-secondary); cursor: pointer; display: flex; font: inherit; font-size: 12.5px; gap: 8px; padding: 7px 10px; text-align: left; width: 100%; }
.cs-b-ph-head:hover { background: var(--ui-bg-quaternary); }
.cs-b-ph[data-state='running'] .cs-b-ico { color: var(--ui-accent); } .cs-b-ph[data-state='failed'] .cs-b-ico { color: var(--ui-red); }
.cs-b-ph-name { font-weight: 600; }
.cs-b-ph-meta { color: var(--ui-text-quaternary); flex: none; font-size: 11.5px; }
.cs-b-ph-head > i { color: var(--ui-text-tertiary); }
.cs-b-ph-body { display: flex; flex-direction: column; gap: 3px; padding: 0 12px 9px 32px; }
.cs-b-ph-more { align-self: flex-start; appearance: none; background: none; border: 0; border-radius: 4px; color: var(--ui-text-quaternary); cursor: pointer; font: inherit; font-size: 11.5px; padding: 2px 4px; margin-left: -4px; }
.cs-b-ph-more:hover { color: var(--ui-accent); }
.cs-b-rimgs { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 4px; }
.cs-b-rchip { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: inherit; cursor: zoom-in; display: inline-flex; font: inherit; gap: 9px; max-width: 280px; min-width: 0; padding: 5px 12px 5px 5px; text-align: left; transition: box-shadow .15s ease; }
.cs-b-rchip:hover { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-b-rchip .cs-col { gap: 0; line-height: 1.35; min-width: 0; }
.cs-b-rchip b { font-size: 12.5px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-rchip .cs-col > span { color: var(--ui-text-tertiary); font-size: 11px; }
.cs-b-rchip.loading { animation: cs-b-skel 1.2s ease-in-out infinite; background: var(--ui-bg-quaternary); height: 50px; width: 180px; }
.cs-b-rchip .cs-b-th { pointer-events: none; }
.cs-b-turn[data-flash] .cs-b-her { animation: cs-b-flash 1.6s ease-out; border-radius: 10px; }
@keyframes cs-b-flash { 0%, 40% { box-shadow: 0 0 0 6px color-mix(in srgb, var(--ui-accent) 16%, transparent); background: color-mix(in srgb, var(--ui-accent) 6%, transparent); } }
.cs-b-badge { background: var(--ui-accent); border-radius: 999px; color: var(--ui-bg-editor); font-size: 10px; font-weight: 700; line-height: 16px; padding: 0 6px; }
.cs-b-latest { align-items: center; animation: cs-b-in .22s ease-out; background: var(--ui-bg-secondary); border-radius: 10px; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 35%, transparent); display: flex; gap: 12px; margin: 6px 0 2px; padding: 8px; }
.cs-b-latest .cs-col { gap: 2px; min-width: 0; }
.cs-b-latest b { font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
`;

// page/pages/build/viewer/viewer.css.js
var VIEWER_CSS = `
/* the asset viewer */
.cs-b-dim { align-items: center; animation: cs-b-fade .15s ease-out; background: color-mix(in srgb, var(--ui-bg-editor) 78%, transparent); backdrop-filter: blur(3px); display: flex; inset: 0; justify-content: center; padding: 20px; position: absolute; z-index: 20; }
@keyframes cs-b-fade { from { opacity: 0; } }
.cs-b-lb { animation: cs-b-in .18s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 14px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 24px 60px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; max-height: 100%; max-width: 640px; outline: none; overflow: hidden; width: 100%; }
.cs-b-lb-top { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 10px; min-width: 0; padding: 10px 14px; }
.cs-b-ell { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-b-lb-body { display: flex; flex-wrap: wrap; gap: 16px; overflow: auto; padding: 16px; }
.cs-b-stage { align-items: center; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 16px 16px; border-radius: 10px; display: flex; flex: none; height: 240px; justify-content: center; width: 240px; }
.cs-b-stage canvas { image-rendering: pixelated; max-height: 228px; max-width: 228px; }
.cs-b-lb-side { display: flex; flex: 1; flex-direction: column; gap: 12px; min-width: 200px; }
.cs-b-frames { display: grid; gap: 6px; grid-template-columns: repeat(auto-fill, minmax(44px, 1fr)); }
.cs-b-frames button { align-items: center; appearance: none; aspect-ratio: 1; background: var(--ui-bg-quaternary); border: 0; border-radius: 6px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); cursor: pointer; display: flex; justify-content: center; padding: 2px; }
.cs-b-frames button[aria-pressed='true'] { box-shadow: inset 0 0 0 2px var(--ui-accent); }
.cs-b-frames canvas { image-rendering: pixelated; max-height: 100%; max-width: 100%; }
.cs-b-pal { display: flex; flex-wrap: wrap; gap: 4px; }
.cs-b-pal i { border-radius: 4px; box-shadow: inset 0 0 0 1px color-mix(in srgb, black 25%, transparent); height: 22px; width: 22px; }
.cs-b-lb-foot { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 14px; }
.cs-b-x { align-items: center; appearance: none; background: none; border: 0; border-radius: 4px; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; padding: 3px; }
.cs-b-x:hover { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); }
.cs-v { animation: cs-b-in .18s ease-out; background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 14px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 24px 60px color-mix(in srgb, black 45%, transparent); display: flex; flex-direction: column; height: min(760px, 100%); max-width: 1180px; outline: none; overflow: hidden; width: 100%; }
.cs-v-top { align-items: center; border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; flex-wrap: wrap; gap: 8px 10px; min-width: 0; padding: 9px 12px 9px 14px; }
.cs-v-name { flex: none; max-width: 28ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cs-v-top .cs-b-ell { flex: 1 1 120px; min-width: 0; }
.cs-v-seg { background: var(--ui-bg-editor); border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-tertiary); display: inline-flex; gap: 2px; padding: 2px; }
.cs-v-seg button { appearance: none; background: none; border: 0; border-radius: 6px; color: var(--ui-text-secondary); cursor: pointer; font: inherit; font-size: 12px; padding: 3px 11px; white-space: nowrap; }
.cs-v-seg button:hover { color: var(--ui-text-primary); }
.cs-v-seg button.on { background: var(--ui-bg-quaternary); color: var(--ui-text-primary); font-weight: 600; }
.cs-v-zoom { align-items: center; display: inline-flex; gap: 4px; }
.cs-v-chip { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 99px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-secondary); cursor: pointer; display: inline-flex; font: inherit; font-size: 11.5px; gap: 4px; line-height: 1.5; padding: 1px 9px; white-space: nowrap; }
.cs-v-chip:hover { color: var(--ui-text-primary); }
.cs-v-chip.on { background: var(--ui-accent); box-shadow: none; color: var(--ui-bg-editor); }
.cs-v-chip.quiet { cursor: default; }
.cs-v-body { display: grid; flex: 1; grid-template-columns: minmax(0, 1fr) 300px; min-height: 0; }
.cs-v-stage { background: var(--ui-bg-editor); min-height: 0; min-width: 0; overflow: hidden; position: relative; }
.cs-v-stage.checker { background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 16px 16px; }
.cs-v-scroll { inset: 0; overflow: auto; position: absolute; }
.cs-v-scroll.pannable { cursor: grab; }
.cs-v-scroll.pannable:active { cursor: grabbing; }
.cs-v-stage-in { align-items: center; box-sizing: border-box; display: flex; justify-content: center; min-height: 100%; min-width: 100%; padding: 44px 24px 64px; width: max-content; }
.cs-v-canvas { flex: none; position: relative; }
.cs-v-canvas canvas, .cs-v-px { display: block; image-rendering: pixelated; }
.cs-v-canvas.picking { cursor: crosshair; touch-action: none; }
.cs-v-grid { background-image: linear-gradient(color-mix(in srgb, white 22%, transparent) 1px, transparent 1px), linear-gradient(90deg, color-mix(in srgb, white 22%, transparent) 1px, transparent 1px); inset: 0; mix-blend-mode: difference; pointer-events: none; position: absolute; }
.cs-v-area { background: color-mix(in srgb, var(--ui-yellow) 10%, transparent); border: 2px dashed var(--ui-yellow); border-radius: 3px; box-sizing: border-box; pointer-events: none; position: absolute; }
.cs-v-area em { background: var(--ui-yellow); border-radius: 99px; color: black; font-size: 11px; font-style: normal; left: -2px; padding: 1px 8px; position: absolute; top: -24px; white-space: nowrap; }
.cs-v-float { align-items: center; display: flex; flex-wrap: wrap; gap: 5px; max-width: calc(100% - 24px); position: absolute; z-index: 1; }
.cs-v-float.tl { left: 12px; top: 10px; }
.cs-v-float.tr { right: 12px; top: 10px; }
.cs-v-float.br { bottom: 10px; right: 12px; }
.cs-v-float.bottom { bottom: 12px; justify-content: center; left: 50%; transform: translateX(-50%); }
.cs-v-tl-wide .cs-v-float.tl { max-width: 60%; }
.cs-v-frame { align-items: center; appearance: none; background: var(--ui-bg-secondary); border: 0; border-radius: 6px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); cursor: pointer; display: inline-flex; justify-content: center; min-height: 40px; min-width: 40px; padding: 2px; }
.cs-v-frame.on { box-shadow: inset 0 0 0 2px var(--ui-accent); }
.cs-v-working { align-items: center; background: var(--ui-bg-secondary); border-radius: 10px; bottom: 16px; box-shadow: 0 0 0 1px var(--ui-accent), 0 8px 24px color-mix(in srgb, black 35%, transparent); display: flex; gap: 10px; left: 50%; padding: 8px 14px; position: absolute; transform: translateX(-50%); white-space: nowrap; z-index: 2; }
.cs-v-side { border-left: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; min-height: 0; }
.cs-v-tabs { border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; flex: none; }
.cs-v-tabs button { align-items: center; appearance: none; background: none; border: 0; color: var(--ui-text-tertiary); cursor: pointer; display: inline-flex; flex: 1; font: inherit; font-size: 12.5px; gap: 6px; justify-content: center; padding: 9px 0; }
.cs-v-tabs button:hover { color: var(--ui-text-primary); }
.cs-v-tabs button.on { box-shadow: inset 0 -2px 0 var(--ui-accent); color: var(--ui-text-primary); font-weight: 600; }
.cs-v-pane { display: flex; flex: 1; flex-direction: column; gap: 14px; min-height: 0; overflow: auto; padding: 14px; }
.cs-v-sec { gap: 6px; }
.cs-v-text { color: var(--ui-text-primary); font-size: 12.5px; line-height: 1.5; overflow-wrap: anywhere; }
.cs-v-quote { color: var(--ui-text-primary); font-size: 12.5px; line-height: 1.5; }
.cs-v-note { background: color-mix(in srgb, var(--ui-yellow) 12%, transparent); border-radius: 8px; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-yellow) 35%, transparent); color: var(--ui-text-primary); display: flex; flex-direction: column; font-size: 12px; gap: 8px; padding: 9px 10px; }
.cs-v-card { background: var(--ui-bg-quaternary); border-radius: 8px; display: flex; flex-direction: column; gap: 3px; padding: 9px 10px; }
.cs-v-pal { display: inline-flex; }
.cs-v-pal button, .cs-v-sw button { appearance: none; border: 0; box-shadow: inset 0 0 0 1px color-mix(in srgb, black 25%, transparent); cursor: copy; height: 22px; padding: 0; width: 22px; }
.cs-v-pal button:first-child { border-radius: 5px 0 0 5px; }
.cs-v-pal button:last-child { border-radius: 0 5px 5px 0; }
.cs-v-sw { display: flex; flex-wrap: wrap; gap: 4px; }
.cs-v-sw button { border-radius: 4px; height: 19px; width: 19px; }
.cs-v-sw button:hover, .cs-v-pal button:hover { outline: 2px solid var(--ui-accent); outline-offset: 1px; position: relative; }
.cs-v-check { align-items: flex-start; color: var(--ui-text-primary); display: flex; font-size: 12px; gap: 6px; line-height: 1.45; }
.cs-v-check > :first-child { color: var(--ui-green); flex: none; margin-top: 2px; }
.cs-v-check.bad > :first-child { color: var(--ui-yellow); }
.cs-v-step { align-items: center; color: var(--ui-text-primary); display: flex; font-size: 12px; gap: 7px; }
.cs-v-step > :first-child { color: var(--ui-green); flex: none; }
.cs-v-step.failed > :first-child { color: var(--ui-red); }
.cs-v-toggle { align-items: center; color: var(--ui-text-secondary); cursor: pointer; display: flex; font-size: 12px; gap: 7px; }
.cs-v-toggle input { accent-color: var(--ui-accent); margin: 0; }
.cs-v-input { background: var(--ui-bg-editor); border: 0; border-radius: 8px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); color: var(--ui-text-primary); font: inherit; font-size: 13px; line-height: 1.5; min-height: 96px; outline: none; padding: 9px 10px; resize: vertical; }
.cs-v-input:focus { box-shadow: inset 0 0 0 1px var(--ui-accent); }
.cs-v-kbd { margin-left: 6px; opacity: .7; }
.cs-v-foot { align-items: center; border-top: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 10px; min-height: 62px; padding: 7px 14px; }
.cs-v-vers { align-items: center; display: flex; gap: 8px; min-width: 0; overflow-x: auto; padding: 3px; }
.cs-v-ver { align-items: center; appearance: none; background: repeating-conic-gradient(var(--ui-bg-quaternary) 0 25%, var(--ui-bg-editor) 0 50%) 0 0 / 8px 8px; border: 0; border-radius: 5px; box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); cursor: pointer; display: inline-flex; flex: none; height: 44px; justify-content: center; opacity: .6; overflow: hidden; padding: 0; position: relative; transition: opacity .15s ease; width: 50px; }
.cs-v-ver:hover { opacity: .9; }
.cs-v-ver.on { box-shadow: 0 0 0 2px var(--ui-accent); opacity: 1; }
.cs-v-ver img { height: 100%; image-rendering: pixelated; object-fit: contain; width: 100%; }
.cs-v-ver b { background: color-mix(in srgb, black 70%, transparent); border-radius: 3px; bottom: 2px; color: white; font-size: 9.5px; left: 2px; line-height: 1.3; padding: 0 4px; position: absolute; }
.cs-v-ver .cs-v-now { background: var(--ui-green); border-radius: 50%; box-shadow: 0 0 0 2px var(--ui-bg-secondary); height: 7px; position: absolute; right: 3px; top: 3px; width: 7px; }
.cs-v-ver.pending { background: none; box-shadow: inset 0 0 0 1px var(--ui-accent); cursor: default; opacity: 1; }
.cs-v-ver-ph { background: var(--ui-bg-quaternary); display: block; height: 100%; width: 100%; }
.cs-v-ingame { align-items: center; display: flex; flex-wrap: wrap; gap: 36px; justify-content: center; }
.cs-v-ingame figure { align-items: center; display: flex; flex-direction: column; gap: 8px; margin: 0; }
.cs-v-ingame figcaption { color: var(--ui-text-tertiary); font-size: 12px; }
.cs-v-gcard { background: var(--ui-bg-secondary); border-radius: 12px; box-shadow: 0 0 0 1px var(--ui-stroke-secondary); overflow: hidden; width: 230px; }
.cs-v-gcard img, .cs-v-gcard .cs-v-ver-ph { aspect-ratio: 160 / 144; display: block; height: auto; image-rendering: pixelated; width: 100%; }
.cs-v-device { background: linear-gradient(color-mix(in srgb, var(--ui-accent) 62%, black), color-mix(in srgb, var(--ui-accent) 40%, black)); border-radius: 20px 20px 52px 20px; box-shadow: inset 0 0 0 3px color-mix(in srgb, white 8%, transparent); display: flex; flex-direction: column; height: 350px; padding: 24px 26px; width: 240px; }
.cs-v-device-screen { aspect-ratio: 160 / 144; background: color-mix(in srgb, black 88%, white); border-radius: 9px; box-sizing: content-box; padding: 12px; }
.cs-v-device-screen img { display: block; height: 100%; image-rendering: pixelated; width: 100%; }
.cs-v-device-name { color: color-mix(in srgb, white 82%, var(--ui-accent)); font: 700 12px/1 system-ui, sans-serif; letter-spacing: .18em; margin-top: 12px; text-align: center; }
.cs-v-device-pad { align-items: center; display: flex; justify-content: space-between; margin-top: auto; padding: 0 4px 6px; }
.cs-v-device-pad .dpad { background: linear-gradient(var(--cs-v-dpad), var(--cs-v-dpad)) center / 20px 62px no-repeat, linear-gradient(var(--cs-v-dpad), var(--cs-v-dpad)) center / 62px 20px no-repeat; --cs-v-dpad: color-mix(in srgb, black 86%, white); display: block; height: 62px; width: 62px; }
.cs-v-device-pad span { display: flex; gap: 9px; }
.cs-v-device-pad span i { background: var(--ui-red); border-radius: 50%; display: block; height: 27px; width: 27px; }
.cs-v-device-pad span i:last-child { margin-top: -24px; }
@container (max-width: 820px) {
  .cs-v-body { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(260px, 1fr) minmax(0, auto); }
  .cs-v-side { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); max-height: 46%; }
  .cs-v-zoom, .cs-v-nav { display: none; }
}
@media (prefers-reduced-motion: reduce) { .cs-v { animation: none; } }
`;

// page/pages/build/index.js
function coverRequested({ game, prompt }) {
  const own = game.session && game.session.thisProfile !== false && game.session.exists !== false;
  injectBuildDraft(own ? game.session.storedId : "", prompt);
}
var BUILD_PAGE = {
  id: "build",
  label: "Build",
  Page: Build,
  pad: "build",
  css: [
    BUILD_CSS,
    NEW_GAME_CSS,
    TRANSCRIPT_CSS,
    WORKED_CSS,
    ASSETS_CSS,
    VIEWER_CSS,
    INLINE_PLAYER_CSS,
    CARDS_CSS,
    COMPOSER_CSS,
    MODEL_PICKER_CSS,
    BUILD_CARD_CSS,
    HEADER_CSS,
    WORKED_MODE_CSS,
    MENTIONS_CSS,
    NEW_GAME_GLASS_CSS,
    CART_SHELF_CSS,
    BUILD_RESPONSIVE_CSS
  ],
  // After every other page's rules: the inline player overrides the Emulator page's stage rules.
  cssLast: true,
  register: (ctx) => {
    watchBuildChats(ctx);
    restoreNewGameDraft(ctx);
  },
  listens: {
    "games.coverRequested": coverRequested,
    "setup.firstIdea": takeFirstIdea,
    "emulator.presented": (presentation) => notePresented(presentation)
  }
};

// page/pages/emulator/emulator-bar.js
function Captures({ game, open }) {
  const captures = useQuery({
    queryKey: [ID, "captures", game?.id ?? null],
    queryFn: () => callStudio(RPC_CAPTURES, { id: game.id }),
    enabled: Boolean(open && game),
    refetchInterval: open ? 5e3 : false,
    retry: false
  });
  if (!open) {
    return null;
  }
  const list = captures.data?.captures ?? [];
  return jsx("div", {
    className: "cs-rp-caps",
    children: captures.isError ? jsx(Small, { children: studioError(captures.error, "list captures") }) : list.length ? list.map(
      (capture) => jsxs(
        "figure",
        {
          children: [
            capture.kind === "screenshot" || /\.png$/i.test(capture.path ?? "") ? jsx("img", { alt: "", src: capture.url }) : jsx("video", { controls: true, src: capture.url }),
            jsx("figcaption", { title: capture.path, children: String(capture.path ?? "").split("/").pop() })
          ]
        },
        capture.path ?? capture.url
      )
    ) : jsx(Small, {
      children: "Screenshots and videos you take with the camera and video buttons beside the device land here and in the game's captures folder."
    })
  });
}
function EmulatorBar({ ctx, game, go, player, focused, hardwareOn, rebuilt, capturesOpen, onAsk, onToggleCaptures, onFull, onReload, onLater }) {
  const onDemo = game?.id === DEMO_ID;
  return [
    rebuilt ? jsxs(
      "div",
      {
        className: "cs-reload",
        role: "status",
        children: [
          jsx("span", { className: "dot" }),
          jsxs("span", { children: [jsx("b", { children: `Hermes rebuilt ${game.title}` }), jsx("span", { className: "cs-small", children: " · the player is still running the earlier build" })] }),
          jsx("span", { className: "cs-grow" }),
          jsxs(Button, { onClick: onReload, size: "sm", variant: "default", children: [jsx(Codicon, { name: "refresh", size: 14 }), "Load the new build"] }),
          jsx(Button, { onClick: onLater, size: "sm", variant: "ghost", children: "Later" })
        ]
      },
      "reload"
    ) : null,
    jsxs(
      "div",
      {
        className: "cs-rp-bar",
        children: [
          jsx("span", { className: "cs-grow" }),
          jsx(Tip, {
            label: "Lit while the player has keyboard focus. Keys typed on this page also reach the game.",
            children: jsxs("span", { className: focused ? "cs-rp-focus on" : "cs-rp-focus", children: [jsx("i", {}), jsx("span", { className: "cs-lbl", children: "Keyboard" })] })
          }),
          game && !onDemo ? jsx(Slot, { name: "emulator.barActions", props: go ? { ctx, game, go, hardwareOn } : { ctx, game, hardwareOn } }) : null,
          jsx(AsyncButton, { disabled: !player?.data?.url, icon: "comment-discussion", run: onAsk, title: "Puts this frame and a note into the game's chat, not sent", variant: "ghost", children: "Ask Hermes" }),
          jsx(Tip, {
            label: "Screenshots and videos of this game",
            children: jsx("span", {
              style: { display: "inline-flex" },
              children: jsxs(Button, {
                "aria-label": "Captures",
                disabled: !game,
                onClick: onToggleCaptures,
                size: "sm",
                variant: capturesOpen ? "secondary" : "ghost",
                children: [jsx(Codicon, { name: "device-camera", size: 14 }), jsx("span", { className: "cs-lbl", children: "Captures" })]
              })
            })
          }),
          jsx(Tip, {
            label: "Full screen",
            children: jsx("span", {
              style: { display: "inline-flex" },
              children: jsx(Button, { "aria-label": "Full screen", disabled: !player?.data?.url, onClick: onFull, size: "sm", variant: "ghost", children: jsx(Codicon, { name: "screen-full", size: 14 }) })
            })
          })
        ]
      },
      "bar"
    ),
    jsx(Captures, { game, open: capturesOpen }, "caps")
  ];
}

// page/backgrounds/platformer/platformer.css.js
var PLATFORMER_CSS = `
.cs-bg[data-bg=platformer] canvas { bottom: 0; filter: saturate(.78); image-rendering: pixelated; image-rendering: crisp-edges; left: 0; opacity: .4; position: absolute; }
`;

// page/backgrounds/platformer/run.js
var SCALE = 2;
var STEP = 1e3 / 60;
var LOOK_EVERY = 30;
var skyFor = ([r, g, b]) => 0.2126 * r + 0.7152 * g + 0.0722 * b > 140 ? "day" : "night";
function flatSpans(root, canvasEl) {
  const origin = canvasEl.getBoundingClientRect(), out = [];
  for (const el of root.querySelectorAll("[data-at-flat]")) {
    const r = el.getBoundingClientRect();
    if (r.width >= 4) out.push([Math.floor((r.left - origin.left) / SCALE), Math.ceil((r.right - origin.left) / SCALE)]);
  }
  return out;
}
function runAttract({ host: host2, canvasEl, makeWorld, env, seed }) {
  const { raf, caf, setTimer, clearTimer, getStyle, observe, motion, isHidden } = env;
  let world = null, flat = "[]", sky = "", bgCss = "", frameId = 0, timer = 0, last = 0, acc = 0, ticks = 0, alive = true;
  let waiting = false, force = false;
  const still = () => !!motion?.matches;
  const look = () => {
    const bg = backgroundOf(host2, getStyle), name = skyFor(bg.rgb), changed2 = name !== sky || bg.css !== bgCss;
    host2.style.setProperty("--cs-at-bg", bg.css);
    if (world && name !== sky) world.setPalette(name);
    sky = name;
    bgCss = bg.css;
    return changed2;
  };
  const build = () => {
    timer = 0;
    if (!alive) return;
    if (world && isHidden()) {
      waiting = true;
      return;
    }
    const area = host2.getBoundingClientRect();
    if (area.width < 40 || area.height < 40) return;
    const W = Math.ceil(area.width / SCALE), H = Math.ceil(area.height / SCALE);
    canvasEl.style.width = `${W * SCALE}px`;
    canvasEl.style.height = `${H * SCALE}px`;
    const spans = flatSpans(host2, canvasEl);
    if (world && !force && world.W === W && world.H === H && JSON.stringify(spans) === flat) return;
    force = false;
    const keep = world ? { score: world.score, coinsGot: world.coinsGot } : null;
    look();
    flat = JSON.stringify(spans);
    world = makeWorld(seed);
    world.build(W, H, { flat: spans });
    if (world.L) host2.style.setProperty("--cs-at-ground", `${(H - world.L.groundY) * SCALE}px`);
    if (keep) Object.assign(world, keep);
    world.attach(canvasEl, sky);
    if (still()) for (let i = 0; i < 90; i++) world.step();
    world.render();
  };
  const later2 = () => {
    if (!timer) timer = setTimer(build, 150);
  };
  const motionChanged = () => {
    force = true;
    later2();
  };
  const frame = (now) => {
    frameId = raf(frame);
    if (!world || isHidden()) {
      last = now;
      return;
    }
    if (waiting) {
      waiting = false;
      build();
    }
    if (++ticks % LOOK_EVERY === 0) {
      if (look() && still()) world.render();
      if (JSON.stringify(flatSpans(host2, canvasEl)) !== flat) later2();
    }
    if (still()) {
      last = now;
      return;
    }
    acc += Math.min(100, now - (last || now));
    last = now;
    let n = 0;
    while (acc >= STEP && n < 4) {
      world.step();
      acc -= STEP;
      n++;
    }
    if (n) world.render();
  };
  const unobserve = observe([host2], later2);
  motion?.addEventListener?.("change", motionChanged);
  build();
  frameId = raf(frame);
  return () => {
    alive = false;
    caf(frameId);
    clearTimer(timer);
    unobserve();
    host2.style.removeProperty("--cs-at-bg");
    host2.style.removeProperty("--cs-at-ground");
    motion?.removeEventListener?.("change", motionChanged);
  };
}

// page/backgrounds/platformer/physics.js
var T = 24;
var GRAV = 0.25;
var MAXFALL = 5;
var JUMPV = 6.6;
var SPEED = 1.4;
var DJUMPV = 5.2;
var GW = 10;
var GH = 28;
function rngOf(seed) {
  let a = seed >>> 0;
  return () => {
    a = a + 1831565813 >>> 0;
    let t = a;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
var overlap = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
var CELL = 32;
function indexColliders(L) {
  const gw = Math.ceil(L.W / CELL) + 1, gh = Math.ceil((L.H + 64) / CELL) + 2;
  const mk = () => Array.from({ length: gw * gh }, () => []);
  const put = (grid, r) => {
    const c0 = Math.max(0, Math.floor(r.x / CELL)), c1 = Math.min(gw - 1, Math.floor((r.x + r.w) / CELL));
    const r0 = Math.max(0, Math.floor((r.y + 64) / CELL)), r1 = Math.min(gh - 1, Math.floor((r.y + r.h + 64) / CELL));
    for (let j = r0; j <= r1; j++) for (let i = c0; i <= c1; i++) grid[j * gw + i].push(r);
  };
  L.gw = gw;
  L.gh = gh;
  L.sGrid = mk();
  L.oGrid = mk();
  for (const r of L.solids) put(L.sGrid, r);
  for (const o of L.oneways) if (!o.mover) put(L.oGrid, o);
  L.stamp = 0;
}
function near(L, grid, b, extra) {
  const out = [];
  const st = ++L.stamp;
  const c0 = Math.max(0, Math.floor((b.x - 8) / CELL)), c1 = Math.min(L.gw - 1, Math.floor((b.x + b.w + 8) / CELL));
  const r0 = Math.max(0, Math.floor((b.y - 8 + 64) / CELL)), r1 = Math.min(L.gh - 1, Math.floor((b.y + b.h + 8 + 64) / CELL));
  for (let j = r0; j <= r1; j++) for (let i = c0; i <= c1; i++) for (const r of grid[j * L.gw + i]) if (r._st !== st) {
    r._st = st;
    out.push(r);
  }
  if (extra) for (const r of extra) out.push(r);
  return out;
}
function physStep(L, b, ignoreOneway, gravity = GRAV) {
  let ground = null, bumped = null, wall = false;
  b.vy = Math.min(b.vy + gravity, MAXFALL);
  const solids = L.sGrid ? near(L, L.sGrid, { x: b.x + Math.min(0, b.vx), y: b.y + Math.min(0, b.vy), w: b.w + Math.abs(b.vx), h: b.h + Math.abs(b.vy) }) : L.solids;
  const oneways = L.oGrid ? near(L, L.oGrid, { x: b.x + Math.min(0, b.vx), y: b.y, w: b.w + Math.abs(b.vx), h: b.h + Math.abs(b.vy) + 2 }, L.movers) : L.oneways;
  const px = b.x;
  b.x += b.vx;
  if (b.vx !== 0) {
    for (const r of solids) {
      if (!overlap(b, r)) continue;
      if (b.vx > 0 && px + b.w <= r.x + 0.01) {
        b.x = r.x - b.w;
        wall = true;
      } else if (b.vx < 0 && px >= r.x + r.w - 0.01) {
        b.x = r.x + r.w;
        wall = true;
      }
    }
    if (b.x < 0) {
      b.x = 0;
      wall = true;
    }
    if (b.x + b.w > L.W) {
      b.x = L.W - b.w;
      wall = true;
    }
  }
  const prevBottom = b.y + b.h, prevTop = b.y;
  b.y += b.vy;
  for (const r of solids) {
    if (!overlap(b, r)) continue;
    if (b.vy > 0 && prevBottom <= r.y + 0.01) {
      b.y = r.y - b.h;
      b.vy = 0;
      ground = r;
    } else if (b.vy < 0 && prevTop >= r.y + r.h - 0.01) {
      b.y = r.y + r.h;
      b.vy = 0;
      bumped = r;
    }
  }
  if (!ignoreOneway && b.vy >= 0) {
    for (const o of oneways) {
      const top = o.y;
      if (b.x + b.w > o.x && b.x < o.x + o.w && prevBottom <= top + 0.01 + Math.max(0, o.dy || 0) + (o.dy < 0 ? -o.dy : 0) && b.y + b.h >= top) {
        b.y = top - b.h;
        b.vy = 0;
        ground = o;
      }
    }
  }
  return { ground, bumped, wall };
}
function solidAt(L, x, y) {
  const p = { x, y, w: 1, h: 1 };
  for (const r of near(L, L.sGrid, p)) if (x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h) return true;
  for (const o of near(L, L.oGrid, p)) if (x >= o.x && x < o.x + o.w && y >= o.y && y < o.y + 4) return true;
  return false;
}

// page/backgrounds/platformer/paths.js
function buildSurfaces(L) {
  const S2 = [];
  const isTop = (v) => v >= 1 && v <= 8;
  for (let r = 0; r < L.rows; r++) {
    let c = 0;
    while (c < L.cols) {
      const v = L.at(c, r);
      if (isTop(v) && !isTop(L.at(c, r - 1))) {
        let e = c;
        while (e + 1 < L.cols && isTop(L.at(e + 1, r)) && !isTop(L.at(e + 1, r - 1))) e++;
        S2.push({ x0: c * T, x1: (e + 1) * T, y: L.oy + r * T });
        c = e + 1;
      } else c++;
    }
  }
  const out = [];
  for (const s of S2) {
    const a = Math.max(0, s.x0), b = Math.min(L.W, s.x1);
    if (b - a >= 12) out.push({ ...s, x0: a, x1: b });
  }
  const kept = [];
  for (const s of out) for (const part of standRuns(L, s)) {
    part.id = kept.length;
    kept.push(part);
  }
  L.surfaces = kept;
}
function standRuns(L, s) {
  const standFree = (cx) => {
    const b = { x: cx - GW / 2, y: s.y - GH, w: GW, h: GH - 0.5 };
    for (const r of near(L, L.sGrid, b)) if (overlap(b, r)) return false;
    return true;
  };
  const lo = Math.max(s.x0 + 4, GW / 2 + 1), hi = Math.min(s.x1 - 4, L.W - GW / 2 - 1);
  const runs = [];
  let start = null;
  for (let x = Math.ceil(lo); x <= hi + 1; x++) {
    const ok = x <= hi && standFree(x);
    if (ok && start === null) start = x;
    if (!ok && start !== null) {
      if (x - 1 - start >= 2) runs.push({ ...s, x0: Math.max(s.x0, start - 4), x1: Math.min(s.x1, x - 1 + 4), l: start, r: x - 1 });
      start = null;
    }
  }
  if (!runs.length && hi < lo && standFree((s.x0 + s.x1) / 2)) runs.push({ ...s, l: (s.x0 + s.x1) / 2, r: (s.x0 + s.x1) / 2 });
  return runs;
}
function trimSpan(L, s) {
  const standFree = (cx, y) => {
    const b = { x: cx - GW / 2, y: y - GH, w: GW, h: GH - 0.5 };
    for (const r2 of near(L, L.sGrid, b)) if (overlap(b, r2)) return false;
    return true;
  };
  let l = Math.max(s.x0 + 4, GW / 2 + 1), r = Math.min(s.x1 - 4, L.W - GW / 2 - 1);
  if (r < l) l = r = (s.x0 + s.x1) / 2;
  while (l <= r && !standFree(l, s.y)) l++;
  while (r >= l && !standFree(r, s.y)) r--;
  s.l = l;
  s.r = r;
  return r >= l;
}
function surfaceAt(L, cx, feet) {
  let best = null;
  for (const s of L.surfaces) if (Math.abs(s.y - feet) < 0.6 && cx >= s.x0 - GW / 2 && cx <= s.x1 + GW / 2) {
    if (!best || cx >= s.x0 && cx <= s.x1) best = s;
  }
  return best;
}
function simulate(L, cx, feet, mode, targetX) {
  const b = { x: cx - GW / 2, y: feet - GH, w: GW, h: GH, vx: 0, vy: mode === "jump" || mode === "djump" ? -JUMPV : 0 };
  let left = mode !== "walk", through = mode === "through" ? 14 : 0, top = feet, dj = mode !== "djump";
  for (let f = 0; f < 200; f++) {
    top = Math.min(top, b.y + GH);
    if (!dj && f > 0 && b.vy >= -0.5) {
      b.vy = -DJUMPV;
      dj = true;
    }
    const c = b.x + GW / 2;
    const input = Math.abs(targetX - c) > 1.2 ? Math.sign(targetX - c) : 0;
    b.vx = input * SPEED;
    const res = physStep(L, b, through > 0 || false, GRAV);
    if (through > 0) through--;
    if (b.y > L.H + 10) return null;
    if (res.ground) {
      if (res.ground.mover) return null;
      if (!left) {
        if (input === 0) return null;
        continue;
      }
      if (f === 0) continue;
      return { s: surfaceAt(L, b.x + GW / 2, b.y + GH), frames: f, rise: feet - top };
    }
    left = true;
  }
  return null;
}
function trail(L, cx, feet, targetX) {
  const b = { x: cx - GW / 2, y: feet - GH, w: GW, h: GH, vx: 0, vy: -JUMPV }, pts = [];
  for (let f = 0; f < 200; f++) {
    const c = b.x + GW / 2;
    b.vx = Math.abs(targetX - c) > 1.2 ? Math.sign(targetX - c) * SPEED : 0;
    const res = physStep(L, b, false, GRAV);
    if (b.y > L.groundY + 10) return null;
    pts.push({ x: b.x + GW / 2, y: b.y + GH * 0.45 });
    if (res.ground && f > 0) return res.ground.mover ? null : pts;
  }
  return null;
}
function landsFrom(L, b0, targetX) {
  const b = { x: b0.x, y: b0.y, w: GW, h: GH, vx: 0, vy: b0.vy };
  for (let f = 0; f < 200; f++) {
    const c = b.x + GW / 2;
    b.vx = Math.abs(targetX - c) > 1.2 ? Math.sign(targetX - c) * SPEED : 0;
    const res = physStep(L, b, false, GRAV);
    if (b.y > L.groundY + 10) return null;
    if (res.ground) return res.ground.mover ? null : surfaceAt(L, b.x + GW / 2, b.y + GH);
  }
  return null;
}
var OFFS = [-120, -84, -60, -42, -27, -14, 0, 14, 27, 42, 60, 84, 120];
function edgesFor(L, A) {
  const best = /* @__PURE__ */ new Map();
  const keep = (res, tx, lx, mode) => {
    if (!res || !res.s || res.s === A) return;
    const cost = res.frames + 24 + (mode === "walk" ? 0 : mode === "djump" ? 16 : 6);
    const cur = best.get(res.s.id);
    if (!cur || cost < cur.cost) best.set(res.s.id, { to: res.s.id, tx, lx, mode, cost });
  };
  const txs = /* @__PURE__ */ new Set([Math.round(A.l), Math.round(A.r)]);
  const stepX = Math.max(16, (A.r - A.l) / 9);
  for (let x = A.l + stepX; x < A.r - 6; x += stepX) txs.add(Math.round(x));
  const isOneway = L.oneways.some((o) => !o.mover && Math.abs(o.y - A.y) < 0.5 && o.x <= A.x0 + 1 && o.x + o.w >= A.x1 - 1);
  for (const tx of txs) {
    for (const d of OFFS) keep(simulate(L, tx, A.y, "jump", tx + d), tx, tx + d, "jump");
    for (const d of OFFS) keep(simulate(L, tx, A.y, "djump", tx + d), tx, tx + d, "djump");
    if (isOneway) for (const d of [-21, 0, 21]) keep(simulate(L, tx, A.y, "through", tx + d), tx, tx + d, "through");
  }
  for (const [tx, dir] of [[Math.round(A.l), -1], [Math.round(A.r), 1]]) {
    for (const d of [18, 36, 60, 90]) keep(simulate(L, tx, A.y, "walk", tx + dir * d), tx, tx + dir * d, "walk");
  }
  return [...best.values()];
}
function withoutMovers(L, fn) {
  const save2 = L.oneways, saveM = L.movers;
  L.oneways = L.oneways.filter((o) => !o.mover);
  L.movers = [];
  try {
    return fn();
  } finally {
    L.oneways = save2;
    L.movers = saveM;
  }
}
function buildEdges(L) {
  withoutMovers(L, () => {
    for (const A of L.surfaces) L.edges.set(A.id, edgesFor(L, A));
  });
}
function connect(L, free) {
  const ground = L.surfaces.filter((s) => Math.abs(s.y - L.groundY) < 1);
  const reach = () => {
    const all = /* @__PURE__ */ new Set();
    for (const g of ground) if (!all.has(g.id)) for (const k of shortest(L, g.id).dist.keys()) all.add(k);
    return all;
  };
  const rowOf = (y) => Math.round((y - L.oy) / T);
  const skip = /* @__PURE__ */ new Set();
  let added = 0;
  for (let it = 0; it < 90; it++) {
    const ok = reach();
    const lost = L.surfaces.filter((s) => !ok.has(s.id) && !skip.has(s.id)).sort((a, b) => b.y - a.y);
    if (!lost.length) break;
    const U = lost[0], rU = rowOf(U.y);
    const c0U = Math.floor(U.x0 / T), c1U = Math.ceil(U.x1 / T) - 1;
    let placed = null;
    const tryAt = (r2, c2) => {
      if (r2 >= L.gTop - 1 || c2 < 0 || c2 + 2 >= L.cols) return false;
      for (let k = c2; k < c2 + 3; k++) {
        if (!free(k, r2) || L.at(k, r2) !== 0 || L.at(k, r2 - 1) !== 0 || L.at(k, r2 - 2) !== 0 || L.at(k, r2 + 1) !== 0) return false;
        if (k > 0 && L.at(k - 1, r2) !== 0 && k === c2) return false;
        if (L.at(k + 1, r2) !== 0 && k === c2 + 2) return false;
      }
      return true;
    };
    for (const dr of [3, 2]) {
      for (const c2 of [c0U - 1, c1U - 1, c0U - 3, c1U + 1, Math.floor((c0U + c1U) / 2) - 1, c0U - 4, c1U + 2]) if (tryAt(rU + dr, c2)) {
        placed = { r: rU + dr, c: c2 };
        break;
      }
      if (placed) break;
    }
    if (!placed) {
      skip.add(U.id);
      continue;
    }
    const { r, c } = placed;
    for (let k = c; k < c + 3; k++) L.grid[r * L.cols + k] = 5;
    const o = { x: c * T, y: L.oy + r * T, w: 3 * T, h: 8, kind: "ledge", step: true };
    L.oneways.push(o);
    const gw = L.gw;
    for (let j = Math.max(0, Math.floor((o.y + 64) / CELL)); j <= Math.min(L.gh - 1, Math.floor((o.y + o.h + 64) / CELL)); j++) for (let i = Math.max(0, Math.floor(o.x / CELL)); i <= Math.min(gw - 1, Math.floor((o.x + o.w) / CELL)); i++) L.oGrid[j * gw + i].push(o);
    const S2 = { x0: o.x, x1: o.x + o.w, y: o.y, id: L.surfaces.length };
    if (!trimSpan(L, S2)) {
      skip.add(U.id);
      continue;
    }
    L.surfaces.push(S2);
    withoutMovers(L, () => {
      for (const A of L.surfaces) if (A === S2 || Math.abs(A.y - S2.y) < 160 && A.x1 > S2.x0 - 160 && A.x0 < S2.x1 + 160) L.edges.set(A.id, edgesFor(L, A));
    });
    added++;
  }
  return added;
}
function shortest(L, fromId) {
  const dist = /* @__PURE__ */ new Map([[fromId, 0]]), prev = /* @__PURE__ */ new Map(), done = /* @__PURE__ */ new Set();
  for (; ; ) {
    let u = null, best = Infinity;
    for (const [k, v] of dist) if (!done.has(k) && v < best) {
      best = v;
      u = k;
    }
    if (u === null) break;
    done.add(u);
    for (const e of L.edges.get(u) || []) {
      const nd = best + e.cost;
      if (nd < (dist.get(e.to) ?? Infinity)) {
        dist.set(e.to, nd);
        prev.set(e.to, { from: u, e });
      }
    }
  }
  return { dist, prev };
}
function firstEdge(paths, fromId, toId) {
  let cur = toId, step = null, guard = 0;
  while (cur !== fromId && guard++ < 200) {
    const p = paths.prev.get(cur);
    if (!p) return null;
    step = p.e;
    cur = p.from;
  }
  return step;
}

// page/backgrounds/platformer/coins.js
function placeCoins(L, rng) {
  const W = L.W, H = L.H, cols = L.cols;
  L.coinSpots = [];
  L.arcs = [];
  const blocked = (box) => {
    for (const r of L.solids) if (overlap({ x: box.x - 2, y: box.y - 2, w: box.w + 4, h: box.h + 4 }, r)) return true;
    for (const o of L.oneways) if (!o.mover && overlap({ x: box.x - 1, y: box.y, w: box.w + 2, h: box.h + 3 }, o)) return true;
    return box.x < 2 || box.x + box.w > W - 2 || box.y < 14;
  };
  const apart = W * H > 38e4 ? 56 : 42;
  const crowded = (box) => L.coinSpots.some((c) => Math.hypot(c.x - box.x, c.y - box.y) < apart);
  const add = (list, arc) => {
    const out = [];
    for (const c of list) {
      const box = { x: c.x, y: c.y, w: 12, h: 16 };
      if (blocked(box) || crowded(box)) return null;
      out.push(c);
    }
    for (const c of out) {
      if (arc) c.arc = arc;
      L.coinSpots.push(c);
    }
    return out;
  };
  const ids = L.surfaces.map((s) => s.id).sort(() => rng() - 0.5);
  const wantArcs = Math.max(3, Math.round(cols / 5));
  withoutMovers(L, () => {
    for (const id of ids) {
      if (L.arcs.length >= wantArcs) break;
      const A = L.surfaces[id];
      const es = (L.edges.get(id) || []).filter((e) => e.mode === "jump" && Math.abs(e.lx - e.tx) >= 40 && L.surfaces[e.to].y <= A.y + 4).sort(() => rng() - 0.5);
      for (const e of es) {
        const pts = trail(L, e.tx, A.y, e.lx);
        if (!pts) continue;
        const spots = [];
        let last = null;
        for (const q of pts) if (!last || Math.hypot(q.x - last.x, q.y - last.y) >= 30) {
          spots.push({ x: Math.round(q.x) - 6, y: Math.round(q.y) - 8 });
          last = q;
        }
        const mid = spots.slice(1, -1).filter((c) => !blocked({ x: c.x, y: c.y, w: 12, h: 16 }));
        if (mid.length < 3) continue;
        const k0 = Math.floor((mid.length - Math.min(4, mid.length)) / 2);
        const arc = { from: id, to: e.to, tx: e.tx, lx: e.lx, coins: [] };
        const got = add(mid.slice(k0, k0 + Math.min(4, mid.length)), arc);
        if (got) {
          arc.coins = got;
          L.arcs.push(arc);
          break;
        }
      }
    }
  });
  const wantCoins = Math.max(30, Math.round(W * H / 9e3));
  const bands = [[], [], [], []];
  for (const s of L.surfaces) if (s.r - s.l >= 34) bands[Math.min(3, Math.floor(s.y / (L.groundY / 4 + 0.01)))].push(s);
  for (const b of bands) b.sort(() => rng() - 0.5);
  const order = [];
  for (let k = 0; bands.some((b) => b.length); k++) {
    const b = bands[k % 4];
    if (b.length) order.push(b.shift());
  }
  for (const s of order) {
    if (L.coinSpots.length >= wantCoins) break;
    if (L.arcs.some((a) => a.from === s.id || a.to === s.id) && rng() < (apart < 50 ? 0.2 : 0.6)) continue;
    const parts = Math.max(1, Math.floor((s.r - s.l) / 200)), seg = (s.r - s.l) / parts;
    for (let j = 0; j < parts && L.coinSpots.length < wantCoins; j++) {
      const l = s.l + j * seg, r = l + seg;
      const n = r - l >= 90 && rng() < 0.6 ? 3 : 2, gap = 30;
      const hi = rng() < 0.25 ? 52 : 0;
      const span = (n - 1) * gap, cx = l + span / 2 + rng() * Math.max(0, r - l - span);
      add(Array.from({ length: n }, (_, k) => ({ x: Math.round(cx + (k - (n - 1) / 2) * gap) - 6, y: s.y - 22 - hi })));
    }
  }
  L.coinSpots = L.coinSpots.filter((c) => {
    if (c.arc) return true;
    const box = { x: c.x, y: c.y, w: 12, h: 16 };
    let s = null;
    for (const t of L.surfaces) if (c.x + 6 >= t.l - 1 && c.x + 6 <= t.r + 1 && t.y >= c.y + 16 && (!s || t.y < s.y)) s = t;
    if (!s) return false;
    const b = { x: c.x + 6 - GW / 2, y: s.y - GH, w: GW, h: GH, vx: 0, vy: 0 };
    if (overlap(b, box)) return true;
    const j = { ...b, vy: -JUMPV };
    for (let f = 0; f < 90; f++) {
      physStep(L, j, false);
      if (overlap(j, box)) return true;
      if (j.vy === 0 && f > 2) break;
    }
    return false;
  });
}

// page/backgrounds/platformer/level.js
function buildLevel(W, H, seed, { flat = [] } = {}) {
  const rng = rngOf(seed);
  const cols = Math.ceil(W / T), rows = Math.max(4, Math.floor(H / T)), oy = H - rows * T;
  const grid = new Uint8Array(cols * rows);
  const at = (c, r) => c < 0 || c >= cols || r < 0 || r >= rows ? 0 : grid[r * cols + c];
  const set = (c, r, v) => {
    if (c >= 0 && c < cols && r >= 0 && r < rows) grid[r * cols + c] = v;
  };
  const cellY = (r) => oy + r * T;
  const free = (c, r) => r >= 1;
  const gTop = rows - 2;
  for (let c = 0; c < cols; c++) {
    set(c, gTop, 1);
    set(c, gTop + 1, 2);
  }
  const taken = new Uint8Array(cols);
  const claim = (c0, c1) => {
    for (let c = Math.max(0, c0); c <= Math.min(cols - 1, c1); c++) taken[c] = 1;
  };
  const open = (c0, c1) => {
    for (let c = c0; c <= c1; c++) if (c < 2 || c > cols - 3 || taken[c]) return false;
    return true;
  };
  const pipes = [];
  const pipe = (c, dir, h) => {
    for (let k = 1; k <= h; k++) {
      set(c, gTop - k, 6);
      set(c + 1, gTop - k, 6);
    }
    pipes.push({ c, dir, h, x: c * T, y: cellY(gTop - h), timer: 60 + Math.floor(rng() * 300) });
    claim(c - 1, c + 2);
  };
  for (const [x0, x1] of flat) claim(Math.floor(x0 / T) - 1, Math.ceil(x1 / T));
  if (cols >= 10 && rows >= 6) {
    if (!taken[1] && !taken[2]) {
      pipe(1, 1, 2);
      claim(0, 4);
    }
    if (!taken[cols - 3] && !taken[cols - 2]) {
      pipe(cols - 3, -1, 2);
      claim(cols - 5, cols - 1);
    }
    const extra = Math.floor(cols / 26);
    for (let i = 0; i < extra * 3 && pipes.length < 2 + extra; i++) {
      const c = 4 + Math.floor(rng() * (cols - 8));
      if (open(c - 1, c + 2)) pipe(c, rng() < 0.5 ? -1 : 1, 2);
    }
  }
  const pits = [];
  if (cols >= 14) {
    const want = Math.max(1, Math.round(cols / 18));
    for (let i = 0; i < want * 6 && pits.length < want; i++) {
      const w = 2, c0 = 3 + Math.floor(rng() * (cols - 6 - w));
      if (!open(c0 - 2, c0 + w + 1)) continue;
      for (let c = c0; c < c0 + w; c++) {
        set(c, gTop, 0);
        set(c, gTop + 1, 0);
      }
      pits.push({ c0, c1: c0 + w - 1 });
      claim(c0 - 2, c0 + w + 1);
    }
  }
  if (rows >= 9) {
    const want = Math.floor(cols / 22);
    for (let i = 0, made = 0; i < want * 6 && made < want; i++) {
      const h = 2 + Math.floor(rng() * 2), c0 = 3 + Math.floor(rng() * (cols - 6 - 2 * h));
      if (!open(c0 - 1, c0 + 2 * h)) continue;
      for (let k = 0; k < h; k++) for (let j = 0; j <= k; j++) {
        set(c0 + k, gTop - 1 - j, 8);
        set(c0 + 2 * h - 1 - k, gTop - 1 - j, 8);
      }
      claim(c0 - 1, c0 + 2 * h);
      made++;
    }
  }
  if (rows >= 18) {
    const want = Math.floor(cols / 30);
    for (let i = 0, made = 0; i < want * 8 && made < want; i++) {
      const h = 4 + Math.floor(rng() * Math.min(6, rows / 4)), c0 = 4 + Math.floor(rng() * (cols - 9));
      let ok = open(c0 - 1, c0 + 2);
      for (let k = 1; k <= h + 2 && ok; k++) for (let j = c0 - 1; j <= c0 + 2; j++) if (!free(j, gTop - k) || at(j, gTop - k) !== 0) ok = false;
      if (!ok) continue;
      for (let k = 1; k <= h; k++) {
        set(c0, gTop - k, 8);
        set(c0 + 1, gTop - k, 8);
      }
      set(c0 - 1, gTop - h, 5);
      set(c0 + 2, gTop - h, 5);
      claim(c0 - 1, c0 + 2);
      made++;
    }
  }
  const blocks = [];
  const clear = (c, r, h = 3) => {
    for (let k = 0; k <= h; k++) if (at(c, r + k) !== 0 && k > 0) return false;
    return at(c, r) === 0;
  };
  {
    const latRows = [];
    for (let r = gTop - 3; r >= 1; r -= 3) latRows.push(r);
    if (latRows[latRows.length - 1] > 1) latRows.push(1);
    latRows.forEach((r, i) => {
      const top = i === latRows.length - 1;
      let c = (i % 2 ? 0 : 3) + Math.floor(rng() * 2);
      let lastKind = "";
      while (c < cols) {
        const w = top ? 3 + Math.floor(rng() * 3) : 3 + Math.floor(rng() * 2);
        const cells = [];
        for (let k = c; k < Math.min(cols, c + w); k++) cells.push(k);
        const head = (k) => at(k, r - 1) === 0 && (r < 2 || at(k, r - 2) === 0);
        const okL = cells.filter((k) => free(k, r) && at(k, r) === 0 && head(k) && clear(k, r, 2));
        const okS = cells.filter((k) => free(k, r) && at(k, r) === 0 && head(k) && clear(k, r, 2));
        let kind = rng();
        if (top || i === 0) kind = 0;
        let kindName = kind < 0.52 ? "ledge" : kind < 0.84 ? "brick" : "qline";
        if (kindName === lastKind && kindName !== "ledge") kindName = "ledge";
        if (kindName === "island" && (r > gTop - 4 || okS.length < 3 || okS.some((k) => !free(k, r + 1) || at(k, r + 1) !== 0))) kindName = "ledge";
        if ((kindName === "brick" || kindName === "qline") && okS.length < 3) kindName = "ledge";
        let made = false;
        if (kindName === "ledge") {
          for (const k of okL) {
            set(k, r, 5);
            made = true;
          }
        } else if (kindName === "brick") {
          for (const k of okS) set(k, r, 3);
          const q = okS[1 + Math.floor(rng() * (okS.length - 2))];
          set(q, r, 4);
          made = true;
        } else if (kindName === "island") {
          for (const k of okS) {
            set(k, r, 1);
            set(k, r + 1, 2);
          }
          made = true;
        } else {
          for (let j = 0; j < okS.length; j += 2) set(okS[j], r, 4);
          made = true;
        }
        if (made) lastKind = kindName;
        c += w + (made ? 2 + Math.floor(rng() * 2) : 1);
      }
    });
  }
  const cannons = [];
  if (W >= 300 && rows >= 8) {
    for (const side of [1, -1]) {
      const span = Math.max(4, Math.floor(cols / 4));
      const cands = [];
      for (let r2 = 3; r2 < gTop - 3; r2++) for (let k = 0; k < span; k++) {
        const c2 = side > 0 ? cols - 1 - k : k;
        if ((at(c2, r2) === 5 || at(c2, r2) === 3) && at(c2, r2 - 1) === 0 && at(c2 - side, r2 - 1) === 0 && free(c2, r2 - 1)) cands.push([c2, r2]);
      }
      if (!cands.length) continue;
      const [c, r] = cands[Math.floor(rng() * cands.length)];
      set(c, r - 1, 7);
      cannons.push({ c, r: r - 1, x: c * T, y: cellY(r - 1), timer: 100 + Math.floor(rng() * 200), dir: -side });
    }
  }
  let flag = null;
  if (cols >= 18) {
    for (let c = cols - 5; c > cols - 11; c--) if (at(c, gTop) === 1 && at(c, gTop - 1) === 0 && at(c + 1, gTop - 1) === 0) {
      flag = { x: c * T + 11, y: cellY(gTop), h: Math.min(5, gTop - 2) * T };
      break;
    }
  }
  for (const p of pits) {
    const r = gTop - 3, x0 = p.c0 * T - 40, x1 = (p.c1 + 1) * T - 8 + 48;
    for (let c = Math.floor(x0 / T) - 1; c <= Math.ceil(x1 / T); c++) for (const rr of [r, r - 1]) if (at(c, rr) === 5) set(c, rr, 0);
    for (let c = Math.floor(x0 / T) - 2; c <= Math.ceil(x1 / T) + 1; c++) for (const rr of [r - 2, r - 3]) if (at(c, rr) === 3 || at(c, rr) === 4) set(c, rr, 5);
  }
  const solids = [], oneways = [];
  for (let r = 0; r < rows; r++) {
    let c = 0;
    while (c < cols) {
      const v = at(c, r);
      if (v === 1 || v === 2 || v === 3 || v === 6 || v === 7 || v === 8) {
        let e = c;
        while (e + 1 < cols && [1, 2, 3, 6, 7, 8].includes(at(e + 1, r))) e++;
        solids.push({ x: c * T, y: cellY(r), w: (e - c + 1) * T, h: T, kind: "tile" });
        c = e + 1;
      } else if (v === 4) {
        const blk = { c, r, x: c * T, y: cellY(r), active: true, bump: 0, reset: 0 };
        blocks.push(blk);
        solids.push({ x: blk.x, y: blk.y, w: T, h: T, kind: "block", ref: blk });
        c++;
      } else if (v === 5) {
        let e = c;
        while (e + 1 < cols && at(e + 1, r) === 5) e++;
        oneways.push({ x: c * T, y: cellY(r), w: (e - c + 1) * T, h: 8, kind: "ledge" });
        c = e + 1;
      } else c++;
    }
  }
  const movers = [];
  for (const p of pits) {
    const y = cellY(gTop - 3);
    if (y < T * 2) continue;
    const x0 = p.c0 * T - 40, x1 = (p.c1 + 1) * T - 8;
    const m = { x: x0, y, w: 48, h: 8, x0, x1, vx: 0.5, dx: 0, dy: 0, mover: true, kind: "mover" };
    movers.push(m);
    oneways.push(m);
  }
  const L = { W, H, cols, rows, oy, gTop, grid, at, solids, oneways, surfaces: [], edges: /* @__PURE__ */ new Map(), blocks, pipes, pits, movers, cannons, flag, rng, groundY: cellY(gTop) };
  indexColliders(L);
  buildSurfaces(L);
  buildEdges(L);
  L.steps = connect(L, free);
  placeCoins(L, rng);
  L.decos = [];
  for (let c = 0; c < cols; c++) {
    if (at(c, gTop) !== 1 || at(c, gTop - 1) !== 0) continue;
    const v = rng();
    if (v < 0.22) L.decos.push({ type: "bush", x: c * T, y: L.groundY });
    else if (v < 0.36) L.decos.push({ type: "flower", x: c * T + 4, y: L.groundY, ph: Math.floor(rng() * 60) });
    else if (v < 0.42) L.decos.push({ type: "tree", x: c * T, y: L.groundY });
  }
  return L;
}

// page/backgrounds/platformer/pilot.js
var PILOT = {
  pickGoal(s) {
    const L = this.L, g = this.girl;
    const paths = shortest(L, s.id);
    const cands = [];
    const below = (x, y, reach) => {
      let best2 = null;
      for (const t of L.surfaces) if (x >= t.x0 - 2 && x <= t.x1 + 2 && t.y >= y && t.y - y <= reach && (!best2 || t.y < best2.y)) best2 = t;
      return best2;
    };
    const left = this.coinsLeft(), hunt = left.all ? 1 - left.n / left.all : 0;
    for (const c of this.coins) {
      if (!c.on || c.arc || c.loose && !c.rest || c.skipUntil > this.frame) continue;
      const t = below(c.x + 6, c.y + 16, 70);
      if (!t) continue;
      const cost = paths.dist.get(t.id);
      if (cost === void 0) continue;
      cands.push({ kind: "coin", ref: c, s: t, x: c.x + 6, jump: c.y + 16 < t.y - GH + 2, w: (c.loose ? 2.2 : 1 + this.rng() * 0.5) * (1 + 2 * hunt), cost, far: hunt > 0.5 });
    }
    for (const a of L.arcs) {
      const n = a.live.filter((c) => c.on).length;
      if (!n || a.skipUntil > this.frame) continue;
      const cost = paths.dist.get(a.from);
      if (cost === void 0) continue;
      cands.push({ kind: "arc", ref: a, s: L.surfaces[a.from], x: a.tx, jump: false, w: (0.5 + 0.35 * n) * (1 + 2 * hunt), cost, far: hunt > 0.5 });
    }
    for (const b of L.blocks) {
      if (!b.active || b.skipUntil > this.frame) continue;
      const t = below(b.x + T / 2, b.y + T, 70);
      if (!t) continue;
      const cost = paths.dist.get(t.id);
      if (cost === void 0) continue;
      cands.push({ kind: "block", ref: b, s: t, x: b.x + T / 2, jump: true, w: 1.3, cost });
    }
    for (const it of this.items) {
      const t = below(it.x + 11, it.y + it.h - 1, 40);
      if (!t) continue;
      const cost = paths.dist.get(t.id);
      if (cost !== void 0) cands.push({ kind: "item", ref: it, s: t, x: it.x + 11, jump: false, w: 4, cost });
    }
    const sx = L.surfaces.filter((t) => t !== s && paths.dist.has(t.id));
    for (const t of sx) {
      const ago2 = this.frame - (g.seen.get(t.id) ?? -1e9), stale = Math.min(1, ago2 / 2400);
      if (stale < 0.25) continue;
      const ground = Math.abs(t.y - L.groundY) < 1, height = (L.groundY - t.y) / L.groundY;
      cands.push({ kind: "wander", s: t, x: t.l + this.rng() * (t.r - t.l), jump: false, w: stale * (ground ? 1.5 : 1 + 0.35 * height), cost: paths.dist.get(t.id), far: true });
    }
    let best = null, bestScore = -1;
    for (const c of cands) {
      if ((c.kind === "block" || c.kind === "coin") && Math.abs(Math.max(c.s.l, Math.min(c.s.r, c.x)) - c.x) > (c.kind === "block" ? 6 : 8)) continue;
      const sc = c.w * (0.6 + this.rng() * 0.8) / (1 + c.cost / (c.far ? 520 : 140));
      if (sc > bestScore) {
        bestScore = sc;
        best = c;
      }
    }
    if (best) best.x = Math.max(best.s.l, Math.min(best.s.r, best.x));
    g.goalTries = 0;
    g.goal = best;
    g.goalT = 720;
    g.paths = paths;
    g.pathsFrom = s.id;
  },
  goalValid(goal) {
    if (!goal) return false;
    if (goal.kind === "coin") return goal.ref.on;
    if (goal.kind === "block") return goal.ref.active;
    if (goal.kind === "item") return this.items.includes(goal.ref);
    if (goal.kind === "arc") return goal.ref.live.some((c) => c.on);
    return true;
  },
  // Play a jump out frame by frame against where the threat will be: safe if she never touches it, or only
  // lands on top of it.
  safeJump(cx, feet, tx, box, mode = "jump") {
    const L = this.L, b = { x: cx - GW / 2, y: feet - GH, w: GW, h: GH, vx: 0, vy: -JUMPV };
    let dj = mode !== "djump", stomped = false;
    const e = { x: box.x - 2, y: box.y, w: box.w + 4, h: box.h };
    for (let f = 0; f < 160; f++) {
      if (!dj && f > 0 && b.vy >= -0.5) {
        b.vy = -DJUMPV;
        dj = true;
      }
      const c = b.x + GW / 2;
      b.vx = Math.abs(tx - c) > 1.2 ? Math.sign(tx - c) * SPEED : 0;
      const prevFeet = b.y + GH;
      const res = physStep(L, b, false);
      if (box.path) {
        const q = box.path(f + 1);
        e.x = q.x - 2;
        e.y = q.y;
      } else e.x += box.vx;
      if (!stomped && overlap(b, e)) {
        if (!(box.stompable && b.vy > 0 && prevFeet <= e.y + 3)) return false;
        stomped = true;
      }
      if (res.ground && f > 0) {
        const q = box.path ? box.path(f + 10) : null;
        const ahead = q ? { x: q.x - 2, y: q.y, w: e.w, h: e.h } : { x: e.x + box.vx * 10, y: e.y, w: e.w, h: e.h };
        return (stomped || !overlap(b, ahead)) && !!surfaceAt(L, b.x + GW / 2, b.y + GH);
      }
      if (b.y > L.H) return false;
    }
    return false;
  },
  // every jump she plans is checked against the bugs and bullets close to her
  jumpSafe(tx, mode = "jump") {
    const g = this.girl, cx = g.x + GW / 2, feet = g.y + GH;
    for (const e of this.enemies) if (e.state === "walk" && Math.abs(e.x + e.w / 2 - cx) < 110 && Math.abs(e.y + e.h - feet) < 64 && !this.safeJump(cx, feet, tx, { x: e.x, y: e.y, w: e.w, h: e.h, vx: e.vx, path: this.enemyPath(e), stompable: e.kind !== "spiny" }, mode)) return false;
    for (const b of this.bullets) if (Math.abs(b.x + 8 - cx) < 120 && Math.abs(b.y - feet) < 140 && !this.safeJump(cx, feet, tx, { x: b.x, y: b.y, w: b.w, h: b.h, vx: b.vx, stompable: true }, mode)) return false;
    for (const bt of this.bats) {
      if (bt.dead) continue;
      const path = (f) => ({ x: bt.x + 1 + bt.vx * f, y: bt.baseY + Math.sin((bt.t + f) * 0.045) * 20 });
      const now = path(0);
      if (Math.abs(now.x + 10 - cx) < 160 && now.y > feet - 170 && now.y < feet + 20 && !this.safeJump(cx, feet, tx, { ...now, w: 20, h: 12, path, stompable: false }, mode)) return false;
    }
    return true;
  },
  // a bullet that will cross the air above her soon: wait for it before jumping
  airBusy() {
    const g = this.girl, gx = g.x + GW / 2, feet = g.y + GH;
    for (const b of this.bullets) {
      const dx = gx - (b.x + 8);
      if (Math.sign(dx) === Math.sign(b.vx) && Math.abs(dx) < 120 && b.y > feet - 110 && b.y < feet - 6) return true;
    }
    return false;
  },
  // after a bounce in the air, steer to somewhere she will land on
  replanAir() {
    const g = this.girl, cx = g.x + GW / 2, base = g.exec ? g.exec.target : cx;
    if (!g.exec) g.exec = { mode: "jump", target: cx, left: true, t: 0, dj: true };
    for (const d of [0, 14, -14, 28, -28, 42, -42, 60, -60, 84, -84]) if (landsFrom(this.L, g, base + d)) {
      g.exec.target = base + d;
      return;
    }
    for (const d of [0, 20, -20, 40, -40, 70, -70, 100, -100]) if (landsFrom(this.L, g, cx + d)) {
      g.exec.target = cx + d;
      return;
    }
  },
  startExec(mode, target) {
    const g = this.girl;
    g.exec = { mode, target, left: mode !== "walk", t: 0, dj: mode !== "djump" };
    if (mode === "jump" || mode === "djump") {
      g.vy = -JUMPV;
      g.ground = null;
    }
    if (mode === "through") {
      g.through = 14;
      g.ground = null;
    }
  },
  threat() {
    const g = this.girl, gx = g.x + GW / 2, feet = g.y + GH;
    for (const e of this.enemies) {
      if (e.state !== "walk") continue;
      const ex = e.x + e.w / 2;
      if (Math.abs(e.y + e.h - feet) >= (e.kind === "blob" ? 40 : 6)) continue;
      const toward = Math.sign(gx - ex) === Math.sign((e.kind === "blob" ? e.dir : e.vx) || 1);
      const chasing = !toward && Math.sign(ex - gx) === Math.sign(g.vx) && g.vx !== 0;
      if (toward && Math.abs(ex - gx) < 64 || chasing && Math.abs(ex - gx) < 32) {
        const over = Math.sign(ex - gx || 1) * 42;
        const stomp = e.kind !== "spiny" && this.rng() < 0.3;
        return { x: stomp ? ex + e.vx * 22 : ex + over, alt: [ex + over, ex + e.vx * 22, ex + over * 1.6, gx], stomp, from: ex, need: e.kind === "blob" ? 30 : 20, box: { x: e.x, y: e.y, w: e.w, h: e.h, vx: e.vx, path: this.enemyPath(e), stompable: e.kind !== "spiny" } };
      }
    }
    for (const b of this.bullets) {
      const bx = b.x + 8;
      if (b.y + 11 > g.y && b.y < feet && Math.abs(bx - gx) < 64 && Math.sign(gx - bx) === Math.sign(b.vx)) return { x: gx, alt: [gx, gx - Math.sign(b.vx) * 20, gx + Math.sign(b.vx) * 20], stomp: false, from: bx, need: feet - b.y + 2, box: { x: b.x, y: b.y, w: b.w, h: b.h, vx: b.vx, stompable: true } };
    }
    for (const bt of this.bats) {
      if (bt.dead) continue;
      const bx = bt.x + 11, by = bt.baseY + Math.sin(bt.t * 0.045) * 20;
      if (by + 12 > g.y - 4 && by < feet && Math.abs(bx - gx) < 64 && Math.sign(gx - bx) === Math.sign(bt.vx)) return { x: gx - Math.sign(bt.vx) * 6, stomp: false, from: bx, need: Infinity };
    }
    return null;
  },
  // A watchdog for anything the planner gets wrong: if her feet stay inside one small box for 6 s, she drops
  // her goal (and avoids it for a while), and heads for a platform far from here.
  watchdog() {
    const g = this.girl, cx = g.x + GW / 2, feet = g.y + GH;
    if (g.ground) {
      const s2 = g.ground.mover ? null : surfaceAt(this.L, cx, feet), key = g.ground.mover ? "mover" : s2 ? s2.id : null;
      if (key !== null && key !== g.pace?.key) g.pace = { key, t: this.frame };
    }
    const pacing = g.pace && this.frame - g.pace.t > 1200;
    if (!pacing && (!g.wd || Math.abs(cx - g.wd.x) > 40 || Math.abs(feet - g.wd.y) > 40 || g.stun > 0)) {
      g.wd = { x: cx, y: feet, t: this.frame };
      return;
    }
    if (!pacing && this.frame - g.wd.t < 360) return;
    if (!g.ground) return;
    g.wd = { x: cx, y: feet, t: this.frame };
    if (g.pace) g.pace.t = this.frame;
    this.stats.unsticks++;
    if (g.goal) {
      if (g.goal.ref) g.goal.ref.skipUntil = this.frame + 2400;
      g.seen.set(g.goal.s.id, this.frame);
    }
    g.goal = null;
    g.exec = null;
    g.retreat = 0;
    g.wait = 0;
    const s = g.ground && !g.ground.mover ? surfaceAt(this.L, cx, feet) : null;
    if (!s) {
      for (const mode of ["jump", "djump", "walk"]) for (const dx of [56, -56, 84, -84, 28, -28, 40, -40]) {
        const sim = simulate(this.L, cx, feet, mode, cx + dx);
        if (sim && sim.s) {
          this.startExec(mode, cx + dx);
          return;
        }
      }
      return;
    }
    const paths = shortest(this.L, s.id);
    const far = this.L.surfaces.filter((t) => paths.dist.has(t.id) && Math.hypot((t.l + t.r) / 2 - cx, t.y - feet) > 160);
    if (far.length) {
      const t = far[Math.floor(this.rng() * far.length)];
      g.goal = { kind: "wander", s: t, x: (t.l + t.r) / 2, jump: false, w: 1, cost: paths.dist.get(t.id) };
      g.goalT = 900;
      g.paths = paths;
      g.pathsFrom = s.id;
    }
  },
  updateGirl() {
    const g = this.girl, L = this.L;
    this.watchdog();
    if (g.inv > 0) g.inv--;
    if (g.power > 0) {
      g.power--;
      if (this.frame % 3 === 0) this.parts.push({ type: "spark", x: g.x + GW / 2 - 3 + (this.rng() - 0.5) * 8, y: g.y + 6 + this.rng() * 14, t: 0, life: 14 });
    }
    if (g.ground && g.ground.mover) {
      g.x += g.ground.dx;
    }
    let input = 0;
    const cx = g.x + GW / 2, feet = g.y + GH;
    if (g.stun > 0) {
      g.stun--;
      input = 0;
      g.vx *= 0.92;
      if (g.stun === 0 && !g.ground) this.replanAir();
    } else if (g.exec) {
      const e = g.exec;
      e.t++;
      if (!e.dj && !g.ground && g.vy >= -0.5) {
        e.dj = true;
        g.vy = -DJUMPV;
        g.spin = 16;
        this.puff(cx, feet);
      }
      input = Math.abs(e.target - cx) > 1.2 ? Math.sign(e.target - cx) : 0;
      if (!g.ground) e.left = true;
      if (g.ground && e.left && e.t > 1 || e.t > 200) {
        g.exec = null;
        if (g.ground) this.dust(cx, feet);
      }
    } else if (g.ground) {
      const s = g.ground.mover ? null : surfaceAt(L, cx, feet);
      const th = this.threat();
      let dodge = null;
      if (th && g.inv === 0) {
        const tries = th.box ? [th.x, ...th.alt || []] : [th.x, cx, cx - Math.sign(th.x - cx) * 42];
        for (const tx of tries) {
          if (th.box ? this.safeJump(cx, feet, tx, th.box) : (() => {
            const sim = simulate(L, cx, feet, "jump", tx);
            return sim && sim.s && sim.rise >= th.need;
          })()) {
            dodge = tx;
            break;
          }
        }
        if (dodge === null && !g.retreat) {
          const away = Math.max(s ? s.l : cx, Math.min(s ? s.r : cx, cx + Math.sign(cx - th.from || 1) * 60));
          if (Math.abs(away - cx) > 8) {
            g.retreat = 50;
            g.retreatTo = away;
          }
        }
      }
      if (g.retreat > 0) {
        g.retreat--;
        input = Math.abs(g.retreatTo - cx) > 1.2 ? Math.sign(g.retreatTo - cx) : 0;
        if (input === 0 || g.retreat === 0) g.retreat = 0;
      } else if (dodge !== null) {
        this.startExec("jump", dodge);
        input = Math.abs(dodge - cx) > 1.2 ? Math.sign(dodge - cx) : 0;
      } else if (!s) {
        const tx = g.goal ? g.goal.x : this.W / 2;
        const dir = Math.sign(tx - cx) || 1;
        g.ride = (g.ride || 0) + 1;
        if (this.frame % 6 === 0) {
          const tries = g.ride > 240 ? [dir * 56, dir * 28, 0, -dir * 28, -dir * 56, dir * 84, -dir * 84] : [dir * 56, dir * 34];
          let done = false;
          for (const d of tries) {
            const sim = simulate(L, cx, feet, "jump", cx + d);
            if (sim && sim.s) {
              this.startExec("jump", cx + d);
              g.ride = 0;
              done = true;
              break;
            }
          }
          if (!done && g.ride > 120) for (const d of [dir * 40, -dir * 40, dir * 70, -dir * 70]) {
            const sim = simulate(L, cx, feet, "walk", cx + d);
            if (sim && sim.s) {
              this.startExec("walk", cx + d);
              g.ride = 0;
              break;
            }
          }
        }
      } else {
        g.seen.set(s.id, this.frame);
        if (g.goal && g.goalT <= 1 && g.goal.ref) g.goal.ref.skipUntil = this.frame + 2400;
        if (!this.goalValid(g.goal) || --g.goalT <= 0) this.pickGoal(s);
        const goal = g.goal;
        if (goal) {
          if (goal.s.id === s.id) {
            const d = goal.x - cx;
            if (Math.abs(d) <= SPEED) {
              g.x = goal.x - GW / 2;
              if (goal.jump) {
                if (g.wait > 0) g.wait--;
                else if (this.airBusy() || !this.jumpSafe(goal.x)) g.wait = 6;
                else if (++g.goalTries > 3) {
                  if (goal.ref) goal.ref.skipUntil = this.frame + 2400;
                  g.goal = null;
                } else {
                  this.startExec("jump", goal.x);
                  g.wait = 4 + Math.floor(this.rng() * 10);
                }
              } else if (goal.kind === "arc") {
                if (g.wait > 0) g.wait--;
                else if (this.airBusy() || !this.jumpSafe(goal.ref.lx)) g.wait = 6;
                else if (++g.goalTries > 3) {
                  goal.ref.skipUntil = this.frame + 2400;
                  g.goal = null;
                } else {
                  this.startExec("jump", goal.ref.lx);
                  g.goal = null;
                }
              } else if (goal.kind === "wander") {
                g.idle++;
                if (g.idle > 40 + this.rng() * 60) {
                  g.goal = null;
                  g.idle = 0;
                }
              } else g.goal = null;
            } else input = Math.sign(d);
          } else {
            if (g.pathsFrom !== s.id) {
              g.paths = shortest(L, s.id);
              g.pathsFrom = s.id;
            }
            const e = firstEdge(g.paths, s.id, goal.s.id);
            if (!e) g.goal = null;
            else if (Math.abs(e.tx - cx) <= SPEED) {
              g.x = e.tx - GW / 2;
              if (g.wait > 0) g.wait--;
              else if (e.mode !== "walk" && (this.airBusy() || !this.jumpSafe(e.lx, e.mode))) g.wait = 6;
              else {
                this.startExec(e.mode, e.lx);
                input = Math.abs(e.lx - cx) > 1.2 ? Math.sign(e.lx - cx) : 0;
                g.wait = this.rng() < 0.3 ? 4 + Math.floor(this.rng() * 14) : 0;
              }
            } else input = Math.sign(e.tx - cx);
          }
        }
      }
    }
    if (g.stun <= 0) g.vx = input * SPEED * (g.power > 0 ? 1 : 1);
    if (input) g.face = input;
    const res = physStep(L, g, g.through > 0);
    if (g.through > 0) g.through--;
    const wasAir = !g.ground;
    g.ground = res.ground;
    g.dist = (g.dist || 0) + Math.abs(g.vx);
    if (res.ground && wasAir) g.landT = g.vy === 0 && g.fallFrom && g.y - g.fallFrom > 36 ? 8 : 4;
    if (!res.ground) {
      if (!wasAir) g.fallFrom = g.y;
      g.fallFrom = Math.min(g.fallFrom ?? g.y, g.y);
    } else g.fallFrom = null;
    if (g.landT > 0) g.landT--;
    if (g.skidT > 0) g.skidT--;
    if (g.cheerT > 0) g.cheerT--;
    if (g.spin > 0) g.spin--;
    if (res.ground && input && g.lastInput && input !== g.lastInput) g.skidT = 7;
    if (input) g.lastInput = input;
    if (--g.blinkT <= 0 || g.blinkT === void 0 || isNaN(g.blinkT)) g.blinkT = 150 + Math.floor(this.rng() * 200);
    if (res.ground && wasAir && !g.exec) this.dust(g.x + GW / 2, g.y + GH);
    if (res.bumped && res.bumped.kind === "block") this.bumpBlock(res.bumped.ref);
    g.anim = g.ground ? input ? g.anim + 1 : 0 : g.anim;
    for (const c of this.coins) if (c.on && overlap(g, c)) {
      c.on = false;
      this.coinsGot++;
      this.score += 100;
      this.sparkle(c.x, c.y);
      this.lastCoin = this.frame;
    }
    if (!this.coins.some((c) => c.pending)) {
      const { n, all } = this.coinsLeft();
      if (all && n <= all * 0.1) {
        this.stats.waves90++;
        this.coinWave();
      } else if (this.frame - this.lastCoin > 60 * 75) this.coinWave();
    }
    for (const it of this.items) if (overlap(g, it)) {
      it.got = true;
      g.power = 480;
      g.cheerT = 32;
      this.addScore(1e3, it.x, it.y - 6);
      this.sparkle(it.x + 4, it.y, 5);
    }
    if (g.y > L.groundY + 20) {
      this.parts.push({ type: "splash", x: g.x + 5, y: L.groundY + 14, t: 0, life: 22 });
      this.hit(true);
    }
  }
};

// page/backgrounds/platformer/actors.js
var ACTORS = {
  hit(fell, by) {
    const g = this.girl;
    if (fell) this.stats.falls++;
    else this.stats.hits[by] = (this.stats.hits[by] || 0) + 1;
    this.hearts--;
    if (this.hearts <= 0) {
      this.hearts = 3;
      this.sparkle(g.x, g.y, 6);
    }
    if (fell) {
      this.respawn();
      return;
    }
    g.inv = 120;
    g.stun = 16;
    g.vy = -2.6;
    g.vx = -g.face * 1.3;
    g.exec = null;
    g.ground = null;
  },
  bumpBlock(b) {
    if (!b.active) return;
    b.active = false;
    b.bump = 8;
    this.lastCoin = this.frame;
    if (this.rng() < 0.22 && this.items.length === 0) {
      this.items.push({ x: b.x + 1, y: b.y, w: 22, h: 15, rise: 18, got: false, t: 0 });
    } else {
      this.coinsGot++;
      this.score += 100;
      this.parts.push({ type: "coinpop", x: b.x + 6, y: b.y - 12, vy: -3, g: 0.16, t: 0, life: 30 });
      this.parts.push({ type: "text", s: "100", x: b.x + 4, y: b.y - 20, vy: -0.4, t: -18, life: 50 });
    }
    for (const e of this.enemies) if (e.state === "walk" && Math.abs(e.y + e.h - b.y) < 2 && e.x + e.w > b.x && e.x < b.x + T) this.kill(e, true);
  },
  kill(e, flip) {
    if (flip) {
      e.state = "flip";
      e.vy = -2.5;
      e.vx = 0.6 * Math.sign(e.vx || 1);
      e.t = 0;
    } else {
      e.state = "squish";
      e.t = 0;
    }
    this.addScore(200, e.x, e.y - 6);
  },
  updateItems() {
    for (const it of this.items) {
      it.t++;
      if (it.rise > 0) {
        it.y -= 1;
        it.rise--;
        continue;
      }
      it.y += Math.sin(it.t * 0.08) * 0.15;
      if (it.t > 900) it.got = true;
    }
    this.items = this.items.filter((i) => !i.got);
  },
  // A blob sits still, squashes, then hops a short arc forward; before a hop it checks the landing and turns
  // round if the hop would take it off its platform. Pure function of its state, so the planner can play it out.
  blobStep(e, L = this.L) {
    if (e.ground && e.vy === 0) {
      e.vx = 0;
      if (--e.hopT <= 0) {
        const dir = e.dir || 1;
        const probe = { x: e.x, y: e.y, w: e.w, h: e.h, vx: 0.9 * dir, vy: -3.4 };
        let ok = false;
        for (let f = 0; f < 80; f++) {
          const r = physStep(L, probe, false);
          if (r.wall) break;
          if (r.ground) {
            ok = Math.abs(probe.y - e.y) < 30;
            break;
          }
        }
        if (!ok) e.dir = -dir;
        e.vx = 0.9 * (e.dir || 1);
        e.vy = -3.4;
        e.hopT = 70 + (e.x * 7 | 0) % 40;
        e.ground = null;
      }
    }
    const res = physStep(L, e, false);
    if (res.wall) {
      e.dir = -(e.dir || 1);
      e.vx = -e.vx;
    }
    if (res.ground) {
      if (!e.ground) e.landT = 8;
      e.ground = res.ground;
    } else e.ground = null;
    if (e.landT > 0) e.landT--;
    e.res = res;
  },
  // where an enemy will be for the next n frames (blobs hop, so they are played out; walkers go straight)
  enemyPath(e, n = 160) {
    if (e.kind !== "blob") return null;
    if (e.pathF === this.frame && e.pathC) return e.pathC;
    const c = { ...e, res: null }, out = [];
    for (let f = 0; f < n; f++) {
      this.blobStep(c);
      out.push({ x: c.x, y: c.y });
    }
    e.pathF = this.frame;
    e.pathC = (f) => out[Math.min(out.length - 1, Math.max(0, f - 1))];
    return e.pathC;
  },
  updateEnemies() {
    const L = this.L, g = this.girl, rng = this.rng;
    const maxE = this.H < 160 ? 1 : Math.max(1, Math.min(8, Math.round(this.W * this.H / 6e4)));
    for (const p of L.pipes) {
      if (--p.timer > 0) continue;
      p.timer = Math.round((320 + rng() * 380) * Math.max(1, L.pipes.length / 3));
      if (this.enemies.length < maxE && !this.enemies.some((e) => Math.abs(e.x - p.x - 14) < 40 && Math.abs(e.y - p.y) < 28)) {
        const k = rng(), kind = k < 0.5 ? "bug" : k < 0.75 ? "spiny" : "blob";
        const sz = { bug: [20, 15], spiny: [20, 14], blob: [18, 13] }[kind];
        this.enemies.push({ kind, x: p.x + 24 - sz[0] / 2, y: p.y + 6, w: sz[0], h: sz[1], vx: (kind === "spiny" ? 0.4 : 0.5) * p.dir, vy: 0, state: "emerge", t: 0, edgeTurn: kind === "blob" || rng() < 0.55, ground: null, pipeY: p.y, hopT: 40 + Math.floor(rng() * 60), dir: p.dir });
      }
    }
    const wide = L.surfaces.filter((s) => s.x1 - s.x0 >= 72 && s.y < L.groundY - 1);
    if (this.frame % 600 === 300 && this.enemies.length < maxE && wide.length && !this.enemies.some((e) => e.dropped)) {
      const top = wide[Math.floor(rng() * wide.length)], d = { x: top.x0, w: top.x1 - top.x0 };
      this.enemies.push({ kind: "bug", x: d.x + 24 + rng() * (d.w - 48), y: -18, w: 20, h: 15, vx: rng() < 0.5 ? -0.5 : 0.5, vy: 0, state: "walk", t: 0, edgeTurn: true, ground: null, dropped: true });
    }
    for (const e of this.enemies) {
      e.t++;
      if (e.state === "emerge") {
        e.y -= 0.35;
        if (e.y + e.h <= e.pipeY) {
          e.y = e.pipeY - e.h;
          e.state = "walk";
          e.noTurn = 90;
        }
        continue;
      }
      if (e.noTurn > 0) e.noTurn--;
      if (e.state === "squish") {
        if (e.t > 30) e.dead = true;
        continue;
      }
      if (e.state === "flip") {
        e.vy += GRAV;
        e.y += e.vy;
        e.x += e.vx;
        if (e.y > this.H + 20) e.dead = true;
        continue;
      }
      if (e.state === "leave") {
        e.x += e.vx;
        if (++e.leaveT > 50) e.dead = true;
        continue;
      }
      if (e.kind === "blob") {
        this.blobStep(e);
        if (e.dead) continue;
      }
      const res = e.kind === "blob" ? e.res : physStep(L, e, false);
      if (res.wall && e.t > 500 && L.pipes.some((pp) => e.y + e.h > pp.y && e.y < pp.y + pp.h * T && (e.vx > 0 ? Math.abs(e.x + e.w - pp.x) < 3 : Math.abs(e.x - pp.x - 2 * T) < 3))) {
        e.state = "leave";
        e.leaveT = 0;
        continue;
      }
      if (res.wall && e.kind !== "blob") e.vx = -e.vx;
      if (L.tunnel && res.ground && Math.abs(e.y + e.h - L.groundY) < 1) {
        const nx = e.vx > 0 ? e.x + e.w : e.x;
        if (nx > L.tunnel.x0 && nx < L.tunnel.x1 && !(e.x + e.w > L.tunnel.x0 && e.x < L.tunnel.x1 && e.inTunnel)) {
          e.vx = -e.vx;
          e.x += e.vx * 2;
          if (e.kind === "blob") e.dir = -(e.dir || 1);
        }
        e.inTunnel = e.x + e.w > L.tunnel.x0 && e.x < L.tunnel.x1;
      }
      if (res.ground && e.edgeTurn && !(e.noTurn > 0) && e.kind !== "blob") {
        const probe = e.vx > 0 ? e.x + e.w + 1 : e.x - 1;
        if (!solidAt(L, probe, e.y + e.h + 1)) e.vx = -e.vx;
      }
      if (e.y > L.groundY + 16) {
        e.dead = true;
        this.parts.push({ type: "splash", x: e.x + 10, y: L.groundY + 14, t: 0, life: 22 });
      }
      if (overlap(g, e)) {
        if (e.kind !== "spiny" && g.vy > 0 && g.y + GH - e.y < 11) {
          this.kill(e, false);
          g.vy = -4.2;
          this.sparkle(e.x + 7, e.y);
          this.replanAir();
        } else if (g.power > 0) this.kill(e, true);
        else if (g.inv === 0) this.hit(false, e.kind);
      }
    }
    for (let i = 0; i < this.enemies.length; i++) for (let j = i + 1; j < this.enemies.length; j++) {
      const a = this.enemies[i], b = this.enemies[j];
      if (a.state !== "walk" || b.state !== "walk" || !overlap(a, b) || Math.abs(a.y - b.y) > 3) continue;
      const dir = Math.sign(a.x - b.x) || 1;
      a.vx = Math.abs(a.vx) * dir;
      b.vx = -Math.abs(b.vx) * dir;
    }
    this.enemies = this.enemies.filter((e) => !e.dead);
    for (const b of this.bats) {
      if (b.dead) {
        if (--b.dead === 0) {
          b.x = b.vx > 0 ? -16 : this.W + 2;
          b.t = 0;
        }
        continue;
      }
      b.t++;
      b.x += b.vx;
      if (b.x > this.W + 20) b.x = -20;
      if (b.x < -20) b.x = this.W + 20;
      const box = { x: b.x + 1, y: b.baseY + Math.sin(b.t * 0.045) * 20, w: 20, h: 12 };
      if (overlap(g, box)) {
        if (g.vy > 0 && g.y + GH - box.y < 10) {
          b.dead = 240;
          g.vy = -4.2;
          this.addScore(200, box.x, box.y);
          this.sparkle(box.x + 4, box.y, 3);
          this.replanAir();
        } else if (g.power > 0) {
          b.dead = 240;
          this.addScore(200, box.x, box.y);
        } else if (g.inv === 0) this.hit(false, "bat");
      }
    }
    for (const c of L.cannons) {
      if (--c.timer > 0) continue;
      c.timer = 200 + Math.floor(rng() * 220);
      this.bullets.push({ x: c.dir < 0 ? c.x - 17 : c.x + 27, y: c.y + 5, vx: 1 * c.dir, w: 16, h: 11 });
      this.parts.push({ type: "dust", x: c.dir < 0 ? c.x - 4 : c.x + 28, y: c.y + 10, vx: 0.3 * c.dir, vy: -0.2, t: 0, life: 14 });
    }
    for (const b of this.bullets) {
      b.x += b.vx;
      if (overlap(g, b)) {
        if (g.vy > 0 && g.y + GH - b.y < 9) {
          b.dead = true;
          g.vy = -4.2;
          this.addScore(200, b.x, b.y);
          this.replanAir();
        } else if (g.power > 0) {
          b.dead = true;
        } else if (g.inv === 0) {
          this.hit(false, "bullet");
        }
      }
      if (b.x < -20 || b.x > this.W + 20) b.dead = true;
    }
    this.bullets = this.bullets.filter((b) => !b.dead);
  },
  addScore(n, x, y) {
    this.score += n;
    this.parts.push({ type: "text", s: String(n), x, y, vy: -0.5, t: 0, life: 45 });
  },
  sparkle(x, y, n = 1) {
    for (let i = 0; i < n; i++) this.parts.push({ type: "spark", x: x + (this.rng() - 0.5) * 10 * (n > 1), y: y + (this.rng() - 0.5) * 10 * (n > 1), t: -i * 4, life: 18 });
  },
  dust(x, y) {
    for (const s of [-1, 1]) this.parts.push({ type: "dust", x, y, vx: s * 0.4, vy: -0.15, t: 0, life: 14 });
  },
  // a ring of puffs under her feet for the double jump
  puff(x, y) {
    for (const [vx, vy] of [[-1, 0.2], [1, 0.2], [-0.5, 0.6], [0.5, 0.6], [0, 0.8]]) this.parts.push({ type: "dust", x, y, vx, vy, t: 0, life: 16 });
  }
};

// page/backgrounds/platformer/palettes.js
var GOLD = { K: "#5a3214", Y: "#f7c548", W: "#fff6c0", y: "#c08a1e" };
var PAL = {
  day: {
    sky: ["#7cc8ff", "#a6dbff", "#d2efff"],
    stars: false,
    cloud: ["#ffffff", "#cbe6f7"],
    hill: ["#a8dcc4", "#7cc79a"],
    grass: ["#a6ec6e", "#5cb24a", "#2f7a3a"],
    dirt: ["#c98a4b", "#9a5f2e", "#6b3d1d"],
    brick: ["#d0703c", "#7a3318", "#f2a272"],
    block: ["#f7c548", "#c08a1e", "#fff2a8", "#5a3214"],
    used: ["#a0693a", "#5a3214"],
    ledge: ["#f0e0b8", "#c09a62", "#6b4f2a"],
    pipe: ["#5ec46a", "#2f7f3c", "#bdf2a4", "#123a1a"],
    water: ["#3a8fd8", "#8fd0f8"],
    deco: ["#3c9a4e", "#1f6b33", "#ff8fb0", "#fff36a"],
    hud: ["#10131c", "#f4f4f0", "#ff5a6e", "#f7c548", "#3a3f4e"],
    girl: { K: "#000000", W: "#ffffff" },
    girlLine: null,
    bug: { K: "#16131f", E: "#d84a4a", e: "#ff9a8a", d: "#7a2430", W: "#ffffff" },
    spiny: { K: "#1a1a24", S: "#6a4fb5", s: "#a890e8", P: "#ffffff", F: "#ffd8a8" },
    blob: { K: "#1a1a24", G: "#5ccf7a", g: "#2f8a4e", W: "#ffffff" },
    bat: { K: "#16131f", B: "#7a4fb5", W: "#ffe27a" },
    cannon: { K: "#1a1a24", B: "#3a3f4e", b: "#9aa2b4", R: "#626a7e", W: "#c98a4b", w: "#6b3d1d" },
    coin: GOLD,
    bullet: { K: "#1a1a24", W: "#ffffff" },
    wing: { W: "#ffffff", K: "#16131f", Y: "#f7c548", y: "#c08a1e" },
    spark: "#ffffff",
    moon: null
  },
  night: {
    sky: ["#070b22", "#0e1640", "#18245c", "#243474"],
    stars: true,
    cloud: ["#2c3c7a", "#1f2c62"],
    hill: ["#18244e", "#121c40"],
    grass: ["#4ad0a0", "#23907a", "#124a46"],
    dirt: ["#34305e", "#252248", "#17142e"],
    brick: ["#5a4a92", "#221c44", "#8e7ec8"],
    block: ["#4a84fe", "#2448b0", "#b0ccff", "#070b22"],
    used: ["#34305e", "#17142e"],
    ledge: ["#a8b8f0", "#5a6aa8", "#202a5a"],
    pipe: ["#3fb0c4", "#1f6a82", "#a6f0fa", "#08283a"],
    water: ["#1c3ea8", "#4a84fe"],
    deco: ["#23907a", "#124a46", "#ff6ad5", "#fff36a"],
    hud: ["#04060e", "#e6edf3", "#ff5a6e", "#f7c548", "#283050"],
    girl: { K: "#000000", W: "#ffffff" },
    girlLine: "#ffffff",
    bug: { K: "#05060c", E: "#e05a7a", e: "#ffa0b8", d: "#702040", W: "#ffffff" },
    spiny: { K: "#05060c", S: "#e08a3a", s: "#ffc070", P: "#f4f1ea", F: "#ffe0b8" },
    blob: { K: "#05060c", G: "#5ad8e0", g: "#2a8aa0", W: "#ffffff" },
    bat: { K: "#05060c", B: "#8a6ad8", W: "#ffe27a" },
    cannon: { K: "#05060c", B: "#3a4262", b: "#9aa6cc", R: "#66729a", W: "#8a5a34", w: "#4a2c18" },
    coin: GOLD,
    bullet: { K: "#05060c", W: "#e6edf3" },
    wing: { W: "#ffffff", K: "#05060c", Y: "#f7c548", y: "#c08a1e" },
    spark: "#ffffff",
    moon: "#f4f0d8"
  }
};

// page/backgrounds/platformer/girl.js
var NG_W = 30;
var NG_H = 40;
var NG_HEAD_L = [
  "........KWWWKKK.......",
  "......KKKKKWWWKKK.....",
  "....KKKKKKKKKWWKKKK...",
  "...KKKKKKKKKKKWWKKKK..",
  "..KKWWKKKWWWKKWWKKWKK.",
  "..KWWKKKWWKWKKKWWKKKK.",
  ".KKKKKKKKKKKKKKKWWKKK.",
  ".KKKKKKWKKKKKKKWKKWKK.",
  ".KKKKKKKKKKKKKWKWWKWK.",
  ".KKKWWWWWWWWWKWKKKKWK.",
  "..KKWKKWWKKKWKKWKKWKK.",
  "...KWKKWWKKWWKKKWWKKK.",
  "...KWKKWWKKWWKKKKKKKK.",
  "...KWWWWWWWWWKKKKKKKK.",
  "....KWWKWWWWKKKKKKKKKK",
  "....KKWWWWWKKKKKKKKKKK",
  "K....KKWWWKKKKKKKKKWKK",
  "KWKKKKKWWKKKKKKKKKKKWK",
  ".KWWKKKKKKKKKKKKKKKKKK",
  "...KKK..KKKKK.....KKK."
];
var NG_HEAD = NG_HEAD_L.map((r) => [...r].reverse().join(""));
var NG_HW = 22;
var NG_NECK = 12;
var NG_LOWER = 15;
var ngM = ([x, y]) => [NG_HW - 1 - x, y];
var NG_EYE = {
  open: [[5, 10], [6, 10], [9, 10], [10, 10], [11, 10], [5, 12], [6, 12], [9, 12], [10, 12]].map(ngM),
  hurtK: [[9, 10], [11, 10], [10, 11], [9, 12], [11, 12]].map(ngM),
  hurtW: [[10, 10], [9, 11], [11, 11], [10, 12]].map(ngM)
};
var NG_TOP = ["...KKWKK...", ".KKWWWWWKK.", ".KKKKKKKKK.", ".KWWWWWWWK.", "..KKKKKKK.."];
var NG_SKIRT = {
  still: ["..KKKKKKKKK..", ".KKKKKKKKKKK.", ".KKKKKKKKKKK."],
  sway: [".KKKKKKKKKK..", "KKKKKKKKKKK..", "KKKKKKKKKKK.."],
  lift: ["..KKKKKKKKK..", ".KKKKKKKKKKK.", "K.KKKKKKKK.K."]
};
function ngGrid() {
  return Array.from({ length: NG_H }, () => Array(NG_W).fill("."));
}
function ngPut(g, x, y, ch) {
  x = Math.round(x);
  y = Math.round(y);
  if (x >= 0 && y >= 0 && x < NG_W && y < NG_H) g[y][x] = ch;
}
function ngStamp(g, rows, x0, y0) {
  rows.forEach((r, j) => {
    for (let i = 0; i < r.length; i++) if (r[i] !== ".") ngPut(g, x0 + i, y0 + j, r[i]);
  });
}
function ngLine(g, x0, y0, x1, y1, ch) {
  x0 = Math.round(x0);
  y0 = Math.round(y0);
  x1 = Math.round(x1);
  y1 = Math.round(y1);
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let e = dx + dy;
  for (; ; ) {
    ngPut(g, x0, y0, ch);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * e;
    if (e2 >= dy) {
      e += dy;
      x0 += sx;
    }
    if (e2 <= dx) {
      e += dx;
      y0 += sy;
    }
  }
}
function ngThick(g, x0, y0, x1, y1, ch) {
  ngLine(g, x0, y0, x1, y1, ch);
  ngLine(g, x0 + 1, y0, x1 + 1, y1, ch);
}
var ngRad = (d) => d * Math.PI / 180;
function ngLimb(x, y, a, b, l1, l2) {
  const kx = x + Math.sin(ngRad(a)) * l1, ky = y + Math.cos(ngRad(a)) * l1;
  const c = a + b;
  return { kx, ky, ex: kx + Math.sin(ngRad(c)) * l2, ey: ky + Math.cos(ngRad(c)) * l2 };
}
function ngOutline(g) {
  const add = [];
  for (let y = 0; y < NG_H; y++) for (let x = 0; x < NG_W; x++) {
    if (g[y][x] !== ".") continue;
    if ([[1, 0], [-1, 0], [0, 1], [0, -1]].some(([a, b]) => g[y + b] && g[y + b][x + a] === "W")) add.push([x, y]);
  }
  for (const [x, y] of add) g[y][x] = "K";
}
function ngLayer(g, draw, keep = () => true) {
  const l = ngGrid();
  draw(l);
  ngOutline(l);
  for (let y = 0; y < NG_H; y++) for (let x = 0; x < NG_W; x++) if (l[y][x] !== "." && keep(x, y, l[y][x])) g[y][x] = l[y][x];
}
var NG_ARM = { thick: false, upper: 2, fore: 2, dx: 3, ink: "K", hand: true };
function ngDraw(p) {
  const g = ngGrid();
  const cx = 14, THIGH = 3, SHIN = 4;
  let hipY = NG_H - 2 - THIGH - SHIN + (p.bob || 0);
  const legs = ["b", "f"].map((k) => {
    const [t, kn] = p.legs[k];
    return { k, ...ngLimb(cx + (k === "f" ? 1 : -2), hipY, t, -kn, THIGH, SHIN) };
  });
  const dy = p.lift == null ? NG_H - 2 - Math.max(...legs.map((l) => l.ey)) : -p.lift;
  hipY += dy;
  for (const l of legs) {
    l.ky += dy;
    l.ey += dy;
  }
  const lean = p.lean || 0;
  const skirtY = hipY - 2;
  const topY = skirtY - NG_TOP.length;
  const shY = topY + 1;
  const hx = cx - NG_NECK + lean, hy = topY - NG_HEAD.length + 1 + (p.lag || 0);
  const arm = (k) => {
    const sx = cx + lean + (k === "f" ? NG_ARM.dx : -NG_ARM.dx);
    const [u, e] = p.arms[k];
    return { sx, ...ngLimb(sx, shY + 1, u, e, NG_ARM.upper, NG_ARM.fore) };
  };
  const drawArm = (l, a) => {
    const line = NG_ARM.thick ? ngThick : ngLine, ink = NG_ARM.ink || "W";
    line(l, a.sx, shY + 1, a.kx, a.ky, ink);
    line(l, a.kx, a.ky, a.ex, a.ey, ink);
    if (NG_ARM.hand) ngPut(l, a.ex, a.ey + 1, "W");
  };
  const shoe = (gg, l, front2) => {
    const x = Math.round(l.ex), y = Math.round(l.ey) + 1;
    for (let i = -1; i <= (front2 ? 2 : 1); i++) ngPut(gg, x + i, y, "K");
    ngPut(gg, x, y - 1, "K");
    ngPut(gg, x + 1, y - 1, "K");
  };
  const lower = NG_HEAD.slice(NG_LOWER);
  const back = lower.map((r) => r.slice(0, NG_NECK - 1));
  const front = lower.map((r) => ".".repeat(NG_NECK - 1) + r.slice(NG_NECK - 1));
  ngStamp(g, back, hx, hy + NG_LOWER);
  const ab = arm("b");
  ngLayer(g, (l) => drawArm(l, ab));
  const lb = legs[0];
  ngLayer(g, (l) => {
    ngThick(l, cx - 2, hipY, lb.kx, lb.ky, "W");
    ngThick(l, lb.kx, lb.ky, lb.ex, lb.ey, "W");
  });
  shoe(g, lb, false);
  ngStamp(g, NG_SKIRT[p.skirt || "still"], cx - 6, skirtY);
  ngStamp(g, NG_TOP, cx - 5 + lean, topY);
  const lf = legs[1];
  ngLayer(g, (l) => {
    ngThick(l, cx + 1, hipY + 1, lf.kx, lf.ky, "W");
    ngThick(l, lf.kx, lf.ky, lf.ex, lf.ey, "W");
  }, (x, y, ch) => !(ch === "K" && y < hipY + 1));
  shoe(g, lf, true);
  ngStamp(g, NG_HEAD.slice(0, NG_LOWER), hx, hy);
  ngStamp(g, front, hx, hy + NG_LOWER);
  if (p.blink) for (const [x, y] of NG_EYE.open) ngPut(g, hx + x, hy + y, "W");
  if (p.eyes === "x") {
    for (const [x, y] of NG_EYE.hurtW) ngPut(g, hx + x, hy + y, "W");
    for (const [x, y] of NG_EYE.hurtK) ngPut(g, hx + x, hy + y, "K");
  }
  const af = arm("f");
  ngLayer(g, (l) => drawArm(l, af));
  ngOutline(g);
  return g.map((r) => r.join(""));
}
var NG_POSES = (() => {
  const P = {};
  const still = { f: [4, 2], b: [-4, 2] };
  P.idle = [0, 0, 1, 1].map((b) => ({ legs: still, arms: { f: [8, 6], b: [-8, 6] }, bob: b, lag: b, hair: "still" }));
  P.blink = { ...P.idle[0], blink: true };
  P.run = [];
  for (let i = 0; i < 8; i++) {
    const t = i / 8 * Math.PI * 2;
    const leg = (ph) => [38 * Math.sin(ph), 12 + 62 * Math.max(0, Math.cos(ph)) * (0.6 + 0.4 * Math.max(0, Math.sin(ph) + 0.4))];
    P.run.push({
      legs: { f: leg(t), b: leg(t + Math.PI) },
      // arms pump opposite the legs, elbows bent about 90 degrees, fists coming up to chest height in front
      // arms hang by her sides and swing a little, opposite the legs (arms jutting forward or out behind the
      // hip did not look natural)
      arms: { f: [-18 * Math.sin(t), 12], b: [10 * Math.sin(t), 8] },
      lean: 1,
      skirt: i % 4 < 2 ? "sway" : "still"
    });
  }
  P.jumpUp = { legs: { f: [62, 95], b: [-10, 35] }, arms: { f: [160, 10], b: [-50, 30] }, lift: 3, hair: "still", skirt: "still" };
  P.jumpTop = { legs: { f: [35, 60], b: [5, 45] }, arms: { f: [115, 20], b: [-95, 20] }, lift: 3, hair: "lift", skirt: "lift" };
  P.fall = [
    { legs: { f: [18, 22], b: [-12, 40] }, arms: { f: [125, 10], b: [-120, 10] }, lift: 2, hair: "lift", skirt: "lift", lag: -1 },
    { legs: { f: [8, 34], b: [-4, 24] }, arms: { f: [135, 10], b: [-130, 10] }, lift: 2, hair: "lift", skirt: "lift", lag: -1 }
  ];
  P.land = { legs: { f: [38, 78], b: [-34, 70] }, arms: { f: [40, 30], b: [-40, 30] }, bob: 2, lag: 3, hair: "still", lean: 1 };
  P.skid = { legs: { f: [42, 4], b: [-8, 45] }, arms: { f: [70, 30], b: [-30, 60] }, lean: -1, hair: "lift", skirt: "sway" };
  P.hurt = { legs: { f: [25, 30], b: [-25, 30] }, arms: { f: [150, 20], b: [-150, 20] }, lift: 1, lean: -1, eyes: "x", hair: "lift", skirt: "lift" };
  P.cheer = [
    { legs: still, arms: { f: [170, 0], b: [-170, 0] }, hair: "still" },
    { legs: { f: [10, 30], b: [-10, 30] }, arms: { f: [165, 0], b: [-165, 0] }, lift: 2, hair: "lift", skirt: "lift" }
  ];
  return P;
})();
function ngFrames() {
  const F = {};
  for (const [k, v] of Object.entries(NG_POSES)) F[k] = Array.isArray(v) ? v.map(ngDraw) : ngDraw(v);
  return F;
}

// page/backgrounds/platformer/art.js
var COIN = [
  [
    "....KKKK....",
    "...KYYYYK...",
    "..KYYYYyyK..",
    ".KYYYYYYyyK.",
    "KYYWYYYYYyyK",
    "KYYWYYyYYyyK",
    "KYYWYYyYYyyK",
    "YYYWYYyYYyyy",
    "YYYWYYyYYyyy",
    "KYYWYYyYYyyK",
    "KYYWYYyYYyyK",
    "KYYWYYYYyyyK",
    ".KYYYYYyyyK.",
    "..KYYyyyyK..",
    "...KYYyyK...",
    "....KKKK...."
  ],
  [
    ".....KK.....",
    "....KYYK....",
    "...KYYYyK...",
    "..KYYYYyyK..",
    "..KYWYYYyK..",
    "..KYWYYYyK..",
    ".KYYWYYYyyK.",
    ".KYYWYYYyyK.",
    ".KYYWYYYyyK.",
    ".KYYWYYYyyK.",
    "..KYWYYYyK..",
    "..KYWYYyyK..",
    "..KYYYYyyK..",
    "...KYyyyK...",
    "....KYyK....",
    ".....KK....."
  ],
  [
    ".....KK.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....Ky.....",
    ".....KK....."
  ],
  [
    ".....KK.....",
    "....KYYK....",
    "...KYYYyK...",
    "..KYYYYyyK..",
    "..KYWYYYyK..",
    "..KYWYYYyK..",
    ".KYYWYYYyyK.",
    ".KYYWYYYyyK.",
    ".KYYWYYYyyK.",
    ".KYYWYYYyyK.",
    "..KYWYYYyK..",
    "..KYWYYyyK..",
    "..KYYYYyyK..",
    "...KYyyyK...",
    "....KYyK....",
    ".....KK....."
  ]
];
var BULLET = [
  ".....KK...........",
  "..KKKKKKKKKKKKKWK.",
  ".KKKKKKKKKKKKKKWK.",
  ".KKKWWKKKKKKKKKWK.",
  "KKKKWKKKKKKKKKKWK.",
  "KKKKKKKKKKKKKKKWK.",
  "KKKKKKKKKKKKKKKWK.",
  "KKKKKKKKKKKKKKKWK.",
  ".KKKKKKKKKKKKKKWK.",
  ".KKKKKKKKKKKKKKWK.",
  "..KKKKKKKKKKKKKWK.",
  ".....KK..........."
];
var WING = [
  "........KKK...........",
  "......KKWWWK..........",
  "....KKWWWWWK..........",
  "..KKWWWWWWWK..........",
  ".KWWWWWWWWWKKKK.......",
  "KWWWWWWWWWKYYYYKKK....",
  ".KKWWWWWWYYYYYYYYYK...",
  "...KKWWWYYYYYYYYYYYK..",
  ".....KYYYYYYYYYYYYyYK.",
  ".....KYYYYYYYYYYYYYyK.",
  ".....KYYYYYYYYYYYYyyK.",
  ".....KYYYYYYYYYYYyyyK.",
  "......KYyyYYYYYyyyyK..",
  ".......KYyyyyyyyyyK...",
  "........KKKYyyyKKK...."
];
var QMARK = [
  "..KKKKKK..",
  ".KKKKKKKK.",
  "KKK....KKK",
  "KKK....KKK",
  ".......KKK",
  "......KKK.",
  "....KKKK..",
  "...KKK....",
  "...KKK....",
  "..........",
  "..........",
  "...KKK....",
  "...KKK....",
  "...KKK...."
];
var CANNON = [
  "..........................",
  "..........................",
  "..........................",
  ".KKK......................",
  "KRRRK..........KKKKKKKK...",
  "KRRRKKKKKKKKKKKBBBBBBBBK..",
  "KRRRBBBBBBBBBBBBRRBBBBBBK.",
  ".KRRBbbbbbbbbbbBRRBbbBBBK.",
  ".KRRBBBBBBBBBBBBRRBBBBBBK.",
  ".KRRBBBBBBBBBBBBRRBBBBBBBK",
  ".KRRBBBBBBBBBBBBRRBBBBBBBB",
  ".KRRBBBBBBBBBBBBRRBBBBBBBK",
  ".KRRBBBBBBBBBBBBRRBBBBBBK.",
  ".KRRBBBBBBBBBBBBRRBBBBBBK.",
  "KRRRBBBBBBBBBBwwRRBBBBBBK.",
  "KRRRKKKKKKKKwwwwwwWWWWWK..",
  "KRRRK.....KwwWWwWwwWWWWK..",
  ".KKK......KwWWWwWWwWWWWK..",
  ".........KwwWWWwWWwwWWWK..",
  ".........KwwwwwbwwwwWWWK..",
  "........KWwwWWWwWWwwwwwK..",
  ".........KKwwWWwWwwKKKK...",
  "...........KwwwwwwK.......",
  "............KKwwKK........"
];
var COIN_SMALL = ["..KKKK..", ".KYYYYK.", "KYWYYYyK", "KYWYYYyK", "KYWYYYyK", "KYWYYYyK", ".KyyyyK.", "..KKKK.."];
var HEART = [".KK.KK.", "KRRKRRK", "KRRRRRK", ".KRRRK.", "..KRK..", "...K..."];
var SPARK = [
  [".......", ".......", "...W...", "..WWW..", "...W...", ".......", "......."],
  ["...W...", "...W...", ".......", "WW.W.WW", ".......", "...W...", "...W..."],
  ["W.....W", ".......", "..W.W..", ".......", "..W.W..", ".......", "W.....W"]
];

// page/backgrounds/platformer/art-enemies.js
var BUG = [
  [
    "......................",
    ".....KKKKK.KKK......KK",
    "....KEEEEEKEEEK....K..",
    "...KEEEEEEKEEEEK..K...",
    "..KEEeeEEEKEddEEKKKK..",
    ".KEEeeEEEEKEdEEEEEEEK.",
    "KEEEeEEEEEKEEEEEEEWWEK",
    "KEEEEEEEdEKEEEdEEEWKWK",
    "KEEEEEEEEEKEEEEEEEEEEK",
    "KEEEEEEEEEKEEEEEEEEEEK",
    "KEddddddddddddddEEEEK.",
    ".KKKKKKKKKKKKKKKKKKK..",
    ".....K....K....K......",
    "....K.....K...K.......",
    "....KK.....KK.KK......",
    "......................"
  ],
  [
    "......................",
    ".....KKKKK.KKK......KK",
    "....KEEEEEKEEEK....K..",
    "...KEEEEEEKEEEEK..K...",
    "..KEEeeEEEKEddEEKKKK..",
    ".KEEeeEEEEKEdEEEEEEEK.",
    "KEEEeEEEEEKEEEEEEEWWEK",
    "KEEEEEEEdEKEEEdEEEWKWK",
    "KEEEEEEEEEKEEEEEEEEEEK",
    "KEEEEEEEEEKEEEEEEEEEEK",
    "KEddddddddddddddEEEEK.",
    ".KKKKKKKKKKKKKKKKKKK..",
    ".....K....K....K......",
    ".....K....K....K......",
    ".....KK...KK...KK.....",
    "......................"
  ],
  [
    "......................",
    ".....KKKKK.KKK......KK",
    "....KEEEEEKEEEK....K..",
    "...KEEEEEEKEEEEK..K...",
    "..KEEeeEEEKEddEEKKKK..",
    ".KEEeeEEEEKEdEEEEEEEK.",
    "KEEEeEEEEEKEEEEEEEWWEK",
    "KEEEEEEEdEKEEEdEEEWKWK",
    "KEEEEEEEEEKEEEEEEEEEEK",
    "KEEEEEEEEEKEEEEEEEEEEK",
    "KEddddddddddddddEEEEK.",
    ".KKKKKKKKKKKKKKKKKKK..",
    ".....K....K....K......",
    ".....K...K.....K......",
    "......KK.KK.....KK....",
    "......................"
  ],
  [
    "......................",
    ".....KKKKK.KKK......KK",
    "....KEEEEEKEEEK....K..",
    "...KEEEEEEKEEEEK..K...",
    "..KEEeeEEEKEddEEKKKK..",
    ".KEEeeEEEEKEdEEEEEEEK.",
    "KEEEeEEEEEKEEEEEEEWWEK",
    "KEEEEEEEdEKEEEdEEEWKWK",
    "KEEEEEEEEEKEEEEEEEEEEK",
    "KEEEEEEEEEKEEEEEEEEEEK",
    "KEddddddddddddddEEEEK.",
    ".KKKKKKKKKKKKKKKKKKK..",
    ".....K....K....K......",
    ".....K....K....K......",
    ".....KK...KK...KK.....",
    "......................"
  ]
];
var BUG_FLAT = [
  ".......................",
  ".........KKKK..........",
  "...KKKKKKEEEEKKKKKK....",
  ".KKEEEEEEEEEEEEEEEEKK..",
  "KEEEEEeeeEEEEEEEEEEEEK.",
  "KEdddddddddddddddddddK.",
  "KEEEEEEEEEEEEEEEEEEEEK.",
  "KEEEEEEEEEEEEEEEEEEEEK."
];
var SPINY = [
  [
    "....K...K...K...K.....",
    "...KPK.KPK.KPK.KPK....",
    "..KPPPKPPPKPPPKPPPK...",
    "..KPPPKPPPKPPPKPPPK...",
    ".KPPPPSSSSSSSSPPPPPK..",
    "..KKSSSSSSSSSSSSKKK...",
    "..KSSssSSSSSSSSSFFFKK.",
    ".KSSSsSSSSSSSSSFFFKFFK",
    ".KSSSSSSSSSSSSFFFFKKFK",
    "KSSSSSSSSSSSSSFFFFFFFK",
    ".KSSSSSSSSSSSSSFFFFFK.",
    ".KSSSSSSSSSSSSSSFFFK..",
    "..KKKKKKKKKKKKKKKKK...",
    ".....KFK......KFK.....",
    ".....KKK......KKK.....",
    "......................"
  ],
  [
    "....K...K...K...K.....",
    "...KPK.KPK.KPK.KPK....",
    "..KPPPKPPPKPPPKPPPK...",
    "..KPPPKPPPKPPPKPPPK...",
    ".KPPPPSSSSSSSSPPPPPK..",
    "..KKSSSSSSSSSSSSKKK...",
    "..KSSssSSSSSSSSSFFFKK.",
    ".KSSSsSSSSSSSSSFFFKFFK",
    ".KSSSSSSSSSSSSFFFFKKFK",
    "KSSSSSSSSSSSSSFFFFFFFK",
    ".KSSSSSSSSSSSSSFFFFFK.",
    ".KSSSSSSSSSSSSSSFFFK..",
    "..KKKKKKKKKKKKKKKKK...",
    "......KFK....KFK......",
    "......KKK....KKK......",
    "......................"
  ]
];
var BLOB = [
  [
    "....................",
    "....................",
    ".......KKKKKK.......",
    ".....KKGGGGGGKK.....",
    "...KKGGGGGGGGGGKK...",
    "..KGGGWWGGGGGGGGGK..",
    ".KGGGGWGGGGGGGGGGGK.",
    ".KGGGGGGGGGGGGGGGGK.",
    "KGGGGGGGGGWGGGWGgGGK",
    "KGGGGGGGGGKGGGKGggGK",
    ".KGGGGGGGGGGKGGgggK.",
    ".KGGgGGGGGGGGGgggGK.",
    "..KGGgggGGGggggggK..",
    "...KKGgggggggggKK...",
    ".....KKGGgggGKK.....",
    ".......KKKKKK......."
  ],
  [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    ".......KKKKKK.......",
    "...KKKKGGGGGGKKKK...",
    "..KGGGGGGGGGGGGGGK..",
    ".KGGGGWWGGGGGGGGGGK.",
    "KGGGGGWGGGGGGGGGGGGK",
    "GGGGGGGGGGWGGGWGGgGG",
    "KGGGGGGGGGKGGGKGgggK",
    "KGGggggGGGGGKgggggGK",
    ".KKGgggggggggggggKK.",
    "...KKKGGggggggKKK...",
    "......KKKKKKKK......"
  ],
  [
    ".......KKKKKK.......",
    ".....KKGGGGGGKK.....",
    "....KGWWGGGGGGGK....",
    "...KGGWGGGGGGGGGK...",
    "...KGGGGGGGGGGGGK...",
    "...KGGGGGGGGGGgGK...",
    "..KGGGGGGGWGGGWGGK..",
    "..KGGGGGGGKGGGKgGK..",
    "..KGGGGGGGGGGGggGK..",
    "..KGGGGGGGGGGGggGK..",
    "...KGGGGGGGGGgggK...",
    "...KGGgGGGGGgggGK...",
    "....KGGggggggggK....",
    ".....KGGgggggGK.....",
    "......KKKGGKKK......",
    ".........KK........."
  ]
];
var BLOB_FLAT = [
  "....................",
  "....................",
  "....KKKKKKKKKKKK....",
  ".KKKGGGGGGGGGGGGKKK.",
  "KGGGGGGGGGGGGGGGGGGK",
  "GGGGGGGGGGGGGGGGGGGG",
  "KGGGGGGGGGGGGGGGGGGK",
  ".KKKGGGGGGGGGGGGKKK."
];
var BAT = [
  [
    "..KK.....K...K....KK..",
    ".KBBKKK.KBK.KBKKKKBBK.",
    "KBKBBBBKKBK.KBKBBBBKBK",
    ".KBBBBBBKBKKKBBBBBBBK.",
    "..KBKBBBBBBBBBBBBKBK..",
    "...KKBBBBBBBBBBBBKK...",
    ".....KKBBBWBWBBKK.....",
    "......KBBBBBBBBK......",
    ".......KBBBBBBK.......",
    ".......KBBWBWBK.......",
    "........KBBBBK........",
    ".........KKKK.........",
    "......................",
    "......................"
  ],
  [
    ".........K...K........",
    "........KBK.KBK.......",
    "........KBK.KBK.......",
    ".KK.....KBKKKBK....KK.",
    "KBBKKKKKKBBBBKKKKKKBBK",
    "KBKBBBBBBBBBBBBBBBBKBK",
    ".KBBBBBBBBWBWBBBBBBBK.",
    "..KBKBBBBBBBBBBBBKBK..",
    "...KKBBBBBBBBBBBBKK...",
    ".....KKKBBWBWBKKK.....",
    "........KBBBBK........",
    ".........KKKK.........",
    "......................",
    "......................"
  ],
  [
    ".........K...K........",
    "........KBK.KBK.......",
    "........KBK.KBK.......",
    "........KBKKKBK.......",
    "........KBBBBK........",
    ".......KBBBBBBK.......",
    ".....KKKBBWBWBKKK.....",
    "...KKBBBBBBBBBBBBKK...",
    "..KBKBBBBBBBBBBBBKBK..",
    ".KBBBBBBBBWBWBBBBBBBK.",
    "KBKBBBKKKBBBBKKKBBBKBK",
    "KBBBKK...KKKK...KKBBBK",
    "KBKK..............KKBK",
    ".K..................K."
  ],
  [
    ".........K...K........",
    "........KBK.KBK.......",
    "........KBK.KBK.......",
    ".KK.....KBKKKBK....KK.",
    "KBBKKKKKKBBBBKKKKKKBBK",
    "KBKBBBBBBBBBBBBBBBBKBK",
    ".KBBBBBBBBWBWBBBBBBBK.",
    "..KBKBBBBBBBBBBBBKBK..",
    "...KKBBBBBBBBBBBBKK...",
    ".....KKKBBWBWBKKK.....",
    "........KBBBBK........",
    ".........KKKK.........",
    "......................",
    "......................"
  ]
];

// page/backgrounds/platformer/sprites.js
function canvas(w, h) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return c;
}
function sprite(rows, map) {
  const c = canvas(rows[0].length, rows.length), x = c.getContext("2d");
  rows.forEach((row, y) => {
    for (let i = 0; i < row.length; i++) {
      const ch = row[i];
      if (ch !== "." && map[ch]) {
        x.fillStyle = map[ch];
        x.fillRect(i, y, 1, 1);
      }
    }
  });
  return c;
}
function outlined(c, color) {
  const x = c.getContext("2d"), d = x.getImageData(0, 0, c.width, c.height), w = c.width, h = c.height;
  const on = (i, j) => i >= 0 && j >= 0 && i < w && j < h && d.data[(j * w + i) * 4 + 3] > 0;
  const add = [];
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) if (!on(i, j) && (on(i - 1, j) || on(i + 1, j) || on(i, j - 1) || on(i, j + 1))) add.push([i, j]);
  x.fillStyle = color;
  for (const [i, j] of add) x.fillRect(i, j, 1, 1);
  return c;
}
function pair(rows, map) {
  const r = sprite(rows, map);
  return [r, flipped(r)];
}
function flipped(c) {
  const f = canvas(c.width, c.height), x = f.getContext("2d");
  x.translate(c.width, 0);
  x.scale(-1, 1);
  x.drawImage(c, 0, 0);
  return f;
}
var NG_FRAMES = ngFrames();
function makeSprites(name) {
  const p = PAL[name];
  const pairO = (rows, map) => {
    const w = rows[0].length + 2;
    const r = sprite([".".repeat(w), ...rows.map((row) => "." + row + "."), ".".repeat(w)], map);
    if (p.girlLine) outlined(r, p.girlLine);
    return [r, flipped(r)];
  };
  const set = (map) => Object.fromEntries(Object.entries(NG_FRAMES).map(([k, v]) => [k, Array.isArray(v[0]) ? v.map((f) => pairO(f, map)) : pairO(v, map)]));
  const girl = set(p.girl);
  girl.inv = set({ K: "#ffffff", W: "#000000" });
  return {
    girl,
    bug: BUG.map((f) => pair(f, p.bug)),
    bugFlat: pair(BUG_FLAT, p.bug),
    spiny: SPINY.map((f) => pair(f, p.spiny)),
    blob: BLOB.map((f) => pair(f, p.blob)),
    blobFlat: pair(BLOB_FLAT, p.blob),
    bat: BAT.map((f) => pair(f, p.bat)),
    bullet: pair(BULLET, p.bullet),
    cannon: pair(CANNON, p.cannon),
    coin: COIN.map((f) => sprite(f, p.coin)),
    coinHud: sprite(COIN_SMALL, p.coin),
    wing: pair(WING, p.wing),
    heart: sprite(HEART, { K: p.hud[0], R: p.hud[2] }),
    heartOff: sprite(HEART, { K: p.hud[0], R: p.hud[4] }),
    spark: SPARK.map((f) => sprite(f, { W: p.spark })),
    q: sprite(QMARK, { K: p.block[3] }),
    qHi: sprite(QMARK, { K: p.block[2] })
  };
}

// page/backgrounds/platformer/hud.js
var FONT = {
  0: "01110 10001 10011 10101 11001 10001 01110",
  1: "00100 01100 00100 00100 00100 00100 01110",
  2: "01110 10001 00001 00010 00100 01000 11111",
  3: "11110 00001 00001 01110 00001 00001 11110",
  4: "00010 00110 01010 10010 11111 00010 00010",
  5: "11111 10000 11110 00001 00001 10001 01110",
  6: "00110 01000 10000 11110 10001 10001 01110",
  7: "11111 00001 00010 00100 01000 01000 01000",
  8: "01110 10001 10001 01110 10001 10001 01110",
  9: "01110 10001 10001 01111 00001 00010 01100",
  A: "01110 10001 10001 11111 10001 10001 10001",
  C: "01110 10001 10000 10000 10000 10001 01110",
  D: "11110 10001 10001 10001 10001 10001 11110",
  E: "11111 10000 10000 11110 10000 10000 11111",
  L: "10000 10000 10000 10000 10000 10000 11111",
  M: "10001 11011 10101 10101 10001 10001 10001",
  O: "01110 10001 10001 10001 10001 10001 01110",
  P: "11110 10001 10001 11110 10000 10000 10000",
  R: "11110 10001 10001 11110 10100 10010 10001",
  S: "01111 10000 10000 01110 00001 00001 11110",
  W: "10001 10001 10001 10101 10101 10101 01010",
  Y: "10001 10001 01010 00100 00100 00100 00100",
  x: "00000 00000 10001 01010 00100 01010 10001",
  "-": "00000 00000 00000 11111 00000 00000 00000"
};
var DIGITS = { 0: "111101101101111", 1: "010110010010111", 2: "111001111100111", 3: "111001111001111", 4: "101101111001001", 5: "111100111001111", 6: "111100111101111", 7: "111001001001001", 8: "111101111101111", 9: "111101111001111" };
var cache = /* @__PURE__ */ new Map();
function remember(key, make) {
  if (!cache.has(key)) {
    if (cache.size > 300) cache.clear();
    cache.set(key, make());
  }
  return cache.get(key);
}
function pixelText(str, color) {
  return remember(`t|${str}|${color}`, () => {
    const c = canvas(str.length * 6, 7), x = c.getContext("2d");
    x.fillStyle = color;
    [...str].forEach((ch, i) => {
      const rows = FONT[ch]?.split(" ") || [];
      rows.forEach((row, y) => {
        for (let k = 0; k < 5; k++) if (row[k] === "1") x.fillRect(i * 6 + k, y, 1, 1);
      });
    });
    return c;
  });
}
function smallText(str, color) {
  return remember(`s|${str}|${color}`, () => {
    const c = canvas(str.length * 4 + 2, 7), t = c.getContext("2d");
    for (let i = 0; i < str.length; i++) {
      const m = DIGITS[str[i]];
      if (!m) continue;
      for (let k = 0; k < 15; k++) {
        if (m[k] !== "1") continue;
        const xx = i * 4 + k % 3 + 1, yy = Math.floor(k / 3) + 1;
        t.fillStyle = "#000";
        t.fillRect(xx + 1, yy + 1, 1, 1);
        t.fillStyle = color;
        t.fillRect(xx, yy, 1, 1);
      }
    }
    return c;
  });
}
function drawHud(world, x) {
  const p = world.p, W = world.W, y = world.H - 10, spr = world.spr;
  x.fillStyle = p.hud[0];
  x.fillRect(0, y, W, 10);
  x.fillStyle = p.hud[4];
  x.fillRect(0, y, W, 1);
  let cx = 6;
  for (let i = 0; i < 3; i++) {
    x.drawImage(i < world.hearts ? spr.heart : spr.heartOff, cx, y + 2);
    cx += 9;
  }
  cx += 6;
  x.drawImage(spr.coinHud, cx, y + 1);
  cx += 10;
  const coins = pixelText("x" + String(world.coinsGot % 100).padStart(2, "0"), p.hud[3]);
  x.drawImage(coins, cx, y + 2);
  cx += coins.width + 6;
  const score = pixelText("SCORE " + String(world.score % 1e6).padStart(6, "0"), p.hud[1]);
  const demo = pixelText("DEMO PLAY", p.hud[3]);
  const stage = pixelText("WORLD 1-1", p.hud[1]);
  const right = W - 6 - demo.width;
  if (world.frame % 70 < 48) x.drawImage(demo, right, y + 2);
  const sx = Math.round(W / 2 - score.width / 2);
  if (sx > cx + 8 && sx + score.width < right - 8) x.drawImage(score, sx, y + 2);
  if (W > 420 && cx + 14 + stage.width < sx - 12) x.drawImage(stage, cx + 14, y + 2);
}

// page/backgrounds/platformer/draw.js
var hexRgb = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
var DRAW = {
  /** Draw on `cv` (a canvas element), with the sky named `name` ('day' or 'night'). */
  attach(cv, name) {
    this.cv = cv;
    this.ctx = cv.getContext("2d");
    this.setPalette(name);
  },
  setPalette(name) {
    this.palName = name;
    this.p = PAL[name];
    this.spr = makeSprites(name);
    for (const c of this.clouds || []) c.c = null;
    if (this.L && this.cv) this.prerender();
  },
  // a cloud: two tones, the lower edge in the darker one
  cloudCanvas(cl) {
    const { w, h, circles } = cl;
    const c = canvas(w, h + 2), x2 = c.getContext("2d");
    for (let py = 0; py < h + 2; py++) for (let px = 0; px < w; px++) {
      const inside = circles.some((k) => (px - k.cx) ** 2 + (py - k.cy) ** 2 <= k.r * k.r) && py <= h;
      if (!inside) continue;
      const lower = !circles.some((k) => (px - k.cx) ** 2 + (py - 2 - k.cy) ** 2 <= k.r * k.r);
      x2.fillStyle = lower || py > h - 3 ? this.p.cloud[1] : this.p.cloud[0];
      x2.fillRect(px, py, 1, 1);
    }
    return c;
  },
  prerender() {
    const L = this.L, p = this.p, W = this.W, H = this.H;
    this.cv.width = W;
    this.cv.height = H;
    const bg = this.bg = canvas(W, H), b = bg.getContext("2d");
    {
      const n = p.sky.length, img = b.createImageData(W, H), rgb = p.sky.map(hexRgb);
      for (let y = 0; y < H; y++) {
        const f = y / H * n, i = Math.min(n - 1, Math.floor(f)), frac = f - i;
        for (let x = 0; x < W; x++) {
          let ci = i;
          if (i < n - 1 && frac > 0.78) ci = (x + y) % 2 === 0 ? i + 1 : i;
          if (i < n - 1 && frac > 0.9) ci = i + 1 - ((x + y * 3) % 4 === 0 ? 1 : 0);
          const o = (y * W + x) * 4, c = rgb[ci];
          img.data[o] = c[0];
          img.data[o + 1] = c[1];
          img.data[o + 2] = c[2];
          img.data[o + 3] = 255;
        }
      }
      b.putImageData(img, 0, 0);
      if (p.dither) for (let y = 0; y < H * 0.6; y += 4) for (let x = y / 4 % 2 * 2; x < W; x += 4) {
        b.fillStyle = p.dither;
        b.fillRect(x, y, 1, 1);
      }
      if (p.moon) {
        const mx = Math.round(W * 0.84), my = Math.round(Math.min(40, H * 0.14));
        b.fillStyle = p.moon;
        for (let y = -9; y <= 9; y++) for (let x = -9; x <= 9; x++) if (x * x + y * y <= 81 && (x + 4) ** 2 + (y - 2) ** 2 > 40) b.fillRect(mx + x, my + y, 1, 1);
      }
    }
    this.stars = [];
    if (p.stars) {
      const n = Math.round(W * H / 1500);
      for (let i = 0; i < n; i++) {
        const r = this.rng();
        this.stars.push({ x: Math.floor(this.rng() * W), y: Math.floor(this.rng() * H * 0.6), lvl: r < 0.7 ? 0 : 1, tw: this.rng() < 0.12, per: 420 + Math.floor(this.rng() * 480), ph: Math.floor(this.rng() * 900), glint: r > 0.96 });
      }
    }
    const gy = L.groundY;
    const hill = (amp, base, f1, f2, ph, col) => {
      b.fillStyle = col;
      for (let x = 0; x < W; x++) {
        const h = Math.round(base + amp * (0.5 + 0.5 * Math.sin(x * f1 + ph)) + amp * 0.35 * Math.sin(x * f2 + ph * 2));
        b.fillRect(x, gy - h, 1, h);
      }
    };
    hill(Math.min(40, H * 0.16), 18, 0.017, 0.053, 1.3, p.hill[0]);
    hill(Math.min(22, H * 0.09), 6, 0.031, 0.081, 4.1, p.hill[1]);
    const tl = this.tiles = canvas(W, H), t = tl.getContext("2d");
    const isSolidTop = (v) => v === 1 || v === 2 || v === 3 || v === 4 || v === 6 || v === 7 || v === 8;
    for (const d of L.decos) if (d.type === "tree") this.drawTree(t, d.x, d.y);
    for (let r = 0; r < L.rows; r++) for (let c = 0; c < L.cols; c++) {
      const v = L.at(c, r), x = c * T, y = L.oy + r * T;
      if (v === 1) this.drawGround(t, x, y, !isSolidTop(L.at(c, r - 1)), L.at(c - 1, r) === 0, L.at(c + 1, r) === 0);
      else if (v === 2) this.drawDirt(t, x, y, L.at(c - 1, r) === 0, L.at(c + 1, r) === 0, r < L.gTop && L.at(c, r + 1) === 0);
      else if (v === 3) this.drawBrick(t, x, y);
      else if (v === 5) this.drawLedge(t, x, y, L.at(c - 1, r) !== 5, L.at(c + 1, r) !== 5);
      else if (v === 8) this.drawStone(t, x, y);
    }
    for (const pp of L.pipes) this.drawPipe(t, pp.x, pp.y, pp.h);
    for (const cn of L.cannons) this.drawCannon(t, cn.x, cn.y, cn.dir);
    if (L.flag) this.drawPole(t, L.flag);
    for (const d of L.decos) if (d.type === "bush") this.drawBush(t, d.x, d.y);
  },
  render() {
    const x = this.ctx, L = this.L, p = this.p, sp = this.spr, f = this.frame;
    x.imageSmoothingEnabled = false;
    x.clearRect(0, 0, this.W, this.H);
    x.drawImage(this.bg, 0, 0);
    for (const s of this.stars) {
      const ph = s.tw ? (f + s.ph) % s.per : 999, up = ph < 48;
      x.fillStyle = up ? ph > 16 && ph < 32 ? "#ffffff" : p.cloud[0] : s.lvl ? p.cloud[1] : p.sky[Math.min(p.sky.length - 1, 1)];
      x.fillRect(s.x, s.y, 1, 1);
      if (up && s.glint && ph > 20 && ph < 28) {
        x.fillStyle = p.cloud[1];
        x.fillRect(s.x - 1, s.y, 1, 1);
        x.fillRect(s.x + 1, s.y, 1, 1);
        x.fillRect(s.x, s.y - 1, 1, 1);
        x.fillRect(s.x, s.y + 1, 1, 1);
      }
    }
    for (const c of this.clouds) x.drawImage(c.c || (c.c = this.cloudCanvas(c)), Math.round(c.x), Math.round(c.y));
    for (const e of this.enemies) if (e.state === "emerge" || e.state === "leave") this.drawEnemy(x, e);
    x.drawImage(this.tiles, 0, 0);
    if (L.flag) {
      const fx = L.flag.x + 2, fy = L.flag.y - L.flag.h + 2;
      for (let i = 0; i < 24; i++) {
        const wv = Math.round(Math.sin(f * 0.12 - i * 0.5) * 1.5 * (i / 18));
        this.px(x, i < 1 ? p.hud[0] : p.block[0], fx + i, fy + wv, 1, 18 - Math.floor(i / 2));
        this.px(x, p.hud[0], fx + i, fy + wv + 18 - Math.floor(i / 2), 1, 1);
        this.px(x, p.hud[0], fx + i, fy + wv - 1, 1, 1);
      }
      x.drawImage(this.spr.q, fx + 5, fy + 2);
    }
    for (const m of L.movers) {
      this.drawLedgeLive(x, Math.round(m.x), m.y, m.w);
      x.fillStyle = p.ledge[2];
      for (let i = m.x0; i < m.x1 + m.w; i += 6) x.fillRect(Math.round(i), m.y + 12, 2, 1);
    }
    for (const b of L.blocks) {
      const by = b.y - (b.bump > 0 ? Math.round(Math.sin((8 - b.bump) / 8 * Math.PI) * 4) : 0);
      if (b.active) {
        this.px(x, p.block[3], b.x, by, T, T);
        this.px(x, p.block[0], b.x + 1, by + 1, T - 2, T - 2);
        this.px(x, p.block[2], b.x + 1, by + 1, T - 2, 1);
        this.px(x, p.block[2], b.x + 1, by + 1, 1, T - 2);
        this.px(x, p.block[1], b.x + 1, by + T - 2, T - 2, 1);
        this.px(x, p.block[1], b.x + T - 2, by + 1, 1, T - 2);
        for (const [a, c] of [[3, 3], [T - 4, 3], [3, T - 4], [T - 4, T - 4]]) this.px(x, p.block[3], b.x + a, by + c, 1, 1);
        const shimmer = (f >> 4) % 6 === 0;
        x.drawImage(shimmer ? sp.qHi : sp.q, b.x + 7, by + 5);
      } else {
        this.px(x, p.used[1], b.x, by, T, T);
        this.px(x, p.used[0], b.x + 1, by + 1, T - 2, T - 2);
        for (const [a, c] of [[4, 4], [T - 5, 4], [4, T - 5], [T - 5, T - 5]]) this.px(x, p.used[1], b.x + a, by + c, 2, 2);
      }
    }
    for (const pit of L.pits) {
      const x0 = pit.c0 * T, w = (pit.c1 - pit.c0 + 1) * T, y0 = L.groundY + 14;
      this.px(x, p.water[0], x0, y0, w, this.H - y0);
      for (let i = 0; i < w; i++) if ((i + (f >> 3)) % 6 < 2) this.px(x, p.water[1], x0 + i, y0, 1, 1);
      for (let i = 0; i < w; i += 1) if ((i * 3 + (f >> 4)) % 11 === 0) this.px(x, p.water[1], x0 + i, y0 + 4, 2, 1);
    }
    for (const d of L.decos) if (d.type === "flower") {
      const sway = f + d.ph >> 5 & 1;
      this.px(x, p.deco[1], d.x + 4, d.y - 6, 1, 6);
      this.px(x, p.deco[1], d.x + 5, d.y - 3, 2, 1);
      this.px(x, p.deco[2], d.x + 2 + sway, d.y - 10, 5, 4);
      this.px(x, p.deco[2], d.x + 3 + sway, d.y - 11, 3, 6);
      this.px(x, p.deco[3], d.x + 4 + sway, d.y - 9, 1, 2);
    }
    for (const it of this.items) {
      const flap = f >> 3 & 1;
      x.drawImage(sp.wing[0], Math.round(it.x), Math.round(it.y) - flap);
    }
    for (const c of this.coins) {
      if (!c.on) continue;
      if (c.loose && c.life < 120 && f & 4) continue;
      const fr = [0, 0, 1, 2, 3][(f + (c.x * 7 + c.y * 3) >> 3) % 5];
      x.drawImage(sp.coin[fr], Math.round(c.x), Math.round(c.y));
    }
    for (const e of this.enemies) {
      if (e.state === "emerge" || e.state === "leave") continue;
      this.drawEnemy(x, e);
    }
    for (const b of this.bats) {
      if (b.dead) continue;
      const y = b.baseY + Math.sin(b.t * 0.045) * 20;
      x.drawImage(sp.bat[(b.t >> 3) % 4][b.vx > 0 ? 0 : 1], Math.round(b.x), Math.round(y));
    }
    for (const b of this.bullets) x.drawImage(sp.bullet[b.vx < 0 ? 0 : 1], Math.round(b.x), Math.round(b.y));
    const g = this.girl;
    if (!(g.inv > 0 && f & 4 && g.power <= 0)) {
      const inv = g.stun > 0 || g.power > 0 && (f >> 2) % 2;
      const S2 = inv ? sp.girl.inv : sp.girl;
      let fr;
      if (g.stun > 0) fr = S2.hurt;
      else if (!g.ground) fr = g.vy < -1.6 ? S2.jumpUp : g.vy < 0.9 ? S2.jumpTop : S2.fall[f >> 3 & 1];
      else if (g.cheerT > 0) fr = S2.cheer[g.cheerT >> 3 & 1];
      else if (g.landT > 0) fr = S2.land;
      else if (g.skidT > 0 && g.vx !== 0) fr = S2.skid;
      else if (g.vx !== 0) fr = S2.run[Math.floor((g.dist || 0) / 3) % 8];
      else fr = g.blinkT < 8 ? S2.blink : S2.idle[(f >> 4) % 4];
      const face = g.spin > 0 && !g.ground ? (g.spin >> 2) % 2 ? -g.face : g.face : g.face;
      if (g.spin > 0 && !g.stun && !g.ground) fr = S2.jumpTop;
      const img = fr[face > 0 ? 0 : 1];
      x.drawImage(img, Math.round(g.x + GW / 2 - img.width / 2), Math.round(g.y + GH - img.height + 1));
    }
    for (const pt of this.parts) {
      if (pt.t < 0) continue;
      if (pt.type === "spark") x.drawImage(sp.spark[Math.min(2, Math.floor(pt.t / 6))], Math.round(pt.x), Math.round(pt.y));
      else if (pt.type === "text") x.drawImage(smallText(pt.s, p.hud[1]), Math.round(pt.x), Math.round(pt.y));
      else if (pt.type === "dust") {
        x.fillStyle = p.cloud[0];
        const s = pt.t < 7 ? 2 : 1;
        x.fillRect(Math.round(pt.x), Math.round(pt.y) - s, s, s);
      } else if (pt.type === "coinpop") x.drawImage(sp.coin[(pt.t >> 2) % 4], Math.round(pt.x), Math.round(pt.y));
      else if (pt.type === "splash") {
        x.fillStyle = p.water[1];
        for (const k of [-6, -2, 2, 6]) x.fillRect(Math.round(pt.x + k * pt.t * 0.15), Math.round(pt.y - 10 * Math.sin(pt.t / pt.life * Math.PI) * (1 - Math.abs(k) / 10)), 1, 2);
      }
    }
    drawHud(this, x);
  },
  px(x, c, X, Y, w = 1, h = 1) {
    x.fillStyle = c;
    x.fillRect(X, Y, w, h);
  },
  drawGround(t, x, y, top, openL, openR) {
    const p = this.p;
    this.drawDirt(t, x, y, openL, openR);
    if (!top) return;
    this.px(t, p.grass[0], x, y, T, 1);
    this.px(t, p.grass[1], x, y + 1, T, 3);
    for (let i = 0; i < T; i++) {
      const dip = (i * 7 + x) % 5 < 2 ? 1 : 0;
      this.px(t, p.grass[1], x + i, y + 4, 1, dip + 1);
      this.px(t, p.grass[2], x + i, y + 5 + dip, 1, 1);
    }
    for (let i = 1; i < T; i += 4) this.px(t, p.grass[0], x + i, y + 2, 1, 1);
    if (openL) this.px(t, p.grass[2], x, y, 1, 6);
    if (openR) this.px(t, p.grass[2], x + T - 1, y, 1, 6);
  },
  drawDirt(t, x, y, openL, openR, openB) {
    const p = this.p;
    this.px(t, p.dirt[0], x, y, T, T);
    if (openB) {
      this.px(t, p.dirt[2], x, y + T - 2, T, 2);
      for (let i = 1; i < T; i += 3) this.px(t, p.dirt[2], x + i, y + T, 1, 1 + i % 2);
    }
    const specks = [[3, 4], [13, 3], [20, 10], [7, 13], [16, 18], [4, 20], [10, 8], [20, 21], [12, 22]];
    for (const [a, b] of specks) {
      this.px(t, p.dirt[1], x + a, y + b, 2, 1);
      this.px(t, p.dirt[2], x + a, y + b + 1, 1, 1);
    }
    if (openL) this.px(t, p.dirt[2], x, y, 1, T);
    if (openR) this.px(t, p.dirt[2], x + T - 1, y, 1, T);
  },
  drawBrick(t, x, y) {
    const p = this.p;
    this.px(t, p.brick[0], x, y, T, T);
    this.px(t, p.brick[1], x, y + 11, T, 1);
    this.px(t, p.brick[1], x, y + 23, T, 1);
    this.px(t, p.brick[1], x + 11, y, 1, 11);
    this.px(t, p.brick[1], x + 23, y, 1, 11);
    this.px(t, p.brick[1], x + 5, y + 12, 1, 11);
    this.px(t, p.brick[1], x + 17, y + 12, 1, 11);
    this.px(t, p.brick[2], x, y, 11, 1);
    this.px(t, p.brick[2], x + 12, y, 11, 1);
    this.px(t, p.brick[2], x, y + 12, 5, 1);
    this.px(t, p.brick[2], x + 6, y + 12, 11, 1);
    this.px(t, p.brick[2], x + 18, y + 12, 5, 1);
  },
  drawLedge(t, x, y, capL, capR) {
    const p = this.p;
    this.px(t, p.ledge[0], x, y, T, 1);
    this.px(t, p.ledge[1], x, y + 1, T, 6);
    this.px(t, p.ledge[2], x, y + 7, T, 1);
    this.px(t, p.ledge[0], x, y + 2, T, 1);
    for (let i = 3; i < T; i += 8) {
      this.px(t, p.ledge[2], x + i, y + 4, 2, 2);
      this.px(t, p.ledge[0], x + i, y + 4, 1, 1);
    }
    if (capL) {
      this.px(t, p.ledge[2], x, y, 1, 8);
      this.px(t, p.ledge[2], x + 3, y + 8, 3, 4);
      this.px(t, p.ledge[2], x + 4, y + 12, 1, 2);
    }
    if (capR) {
      this.px(t, p.ledge[2], x + T - 1, y, 1, 8);
      this.px(t, p.ledge[2], x + T - 6, y + 8, 3, 4);
      this.px(t, p.ledge[2], x + T - 5, y + 12, 1, 2);
    }
  },
  drawPipe(t, x, y, h = 2) {
    const p = this.p, w = 2 * T, cap = 12, body2 = h * T - cap;
    this.px(t, p.pipe[3], x, y, w, cap);
    this.px(t, p.pipe[0], x + 1, y + 1, w - 2, cap - 2);
    this.px(t, p.pipe[2], x + 5, y + 1, 4, cap - 2);
    this.px(t, p.pipe[1], x + w - 9, y + 1, 7, cap - 2);
    this.px(t, p.pipe[3], x + 3, y + cap, w - 6, body2);
    this.px(t, p.pipe[0], x + 4, y + cap, w - 8, body2);
    this.px(t, p.pipe[2], x + 8, y + cap, 4, body2);
    this.px(t, p.pipe[1], x + w - 13, y + cap, 7, body2);
  },
  drawCannon(t, x, y, dir = -1) {
    t.drawImage(this.spr.cannon[dir < 0 ? 0 : 1], dir < 0 ? x - 2 : x, y);
  },
  drawStone(t, x, y) {
    const p = this.p;
    this.px(t, p.dirt[2], x, y, T, T);
    this.px(t, p.ledge[1], x + 1, y + 1, T - 2, T - 2);
    this.px(t, p.ledge[0], x + 1, y + 1, T - 2, 1);
    this.px(t, p.ledge[0], x + 1, y + 1, 1, T - 2);
    this.px(t, p.ledge[2], x + 2, y + T - 2, T - 3, 1);
    this.px(t, p.ledge[2], x + T - 2, y + 2, 1, T - 3);
    this.px(t, p.ledge[0], x + 5, y + 5, 3, 3);
    this.px(t, p.ledge[2], x + 15, y + 14, 3, 3);
  },
  drawPole(t, f) {
    const p = this.p;
    this.px(t, p.dirt[2], f.x - 4, f.y - 8, 10, 8);
    this.px(t, p.ledge[1], f.x - 3, f.y - 7, 8, 6);
    this.px(t, p.hud[0], f.x, f.y - f.h, 2, f.h - 8);
    this.px(t, p.ledge[0], f.x, f.y - f.h, 1, f.h - 8);
    this.px(t, p.hud[0], f.x - 2, f.y - f.h - 5, 6, 6);
    this.px(t, p.block[0], f.x - 1, f.y - f.h - 4, 4, 4);
    this.px(t, p.block[2], f.x - 1, f.y - f.h - 4, 1, 1);
  },
  drawBush(t, x, y) {
    const p = this.p;
    const shape = ["......DDDDD.............", "...DDDLLLDDD....DDD.....", "..DLLLLDDDDDD..DLLLDD...", ".DLLLDDDDDDDDDDLLDDDDDD.", "DLLDDDDDDDDDDDDDDDDDDDDD", "DDDDDDDDDDDDDDDDDDDDDDDD", "DDDDDDDDDDDDDDDDDDDDDDDD"];
    shape.forEach((row, i) => {
      for (let j = 0; j < 24; j++) {
        const ch = row[j];
        if (ch === ".") continue;
        this.px(t, ch === "L" ? p.deco[0] : p.deco[1], x + j, y - 7 + i, 1, 1);
      }
    });
  },
  drawTree(t, x, y) {
    const p = this.p;
    this.px(t, p.dirt[2], x + 6, y - 22, 4, 22);
    for (let yy = -40; yy < -16; yy++) for (let xx = -6; xx < 22; xx++) {
      const dx = xx - 8, dy = yy + 28;
      if (dx * dx / 160 + dy * dy / 120 <= 1) this.px(t, dy > 4 || dx > 6 ? p.deco[1] : p.deco[0], x + xx, y + yy);
    }
  },
  drawEnemy(x, e) {
    const sp = this.spr, kind = e.kind || "bug";
    const dir = (kind === "blob" ? e.dir || 1 : e.vx) > 0 ? 0 : 1;
    const X = Math.round(e.x - 1), bottom = Math.round(e.y + e.h);
    let img;
    if (kind === "bug") img = e.state === "squish" ? sp.bugFlat[dir] : sp.bug[e.state === "flip" ? 0 : (e.t >> 3) % 4][dir];
    else if (kind === "spiny") img = sp.spiny[e.state === "flip" ? 0 : e.t >> 3 & 1][dir];
    else img = e.state === "squish" ? sp.blobFlat[dir] : sp.blob[e.state === "flip" ? 0 : !e.ground ? 2 : e.landT > 0 || e.hopT < 10 ? 1 : 0][dir];
    if (e.state === "flip") {
      x.save();
      x.translate(X, bottom);
      x.scale(1, -1);
      x.drawImage(img, 0, 0);
      x.restore();
      return;
    }
    x.drawImage(img, X, bottom - img.height + (e.state === "squish" ? 0 : kind === "bug" ? 1 : 0));
  },
  drawLedgeLive(x, X, Y, w) {
    const p = this.p;
    this.px(x, p.ledge[0], X, Y, w, 1);
    this.px(x, p.ledge[1], X, Y + 1, w, 6);
    this.px(x, p.ledge[0], X, Y + 2, w, 1);
    this.px(x, p.ledge[2], X, Y + 7, w, 1);
    this.px(x, p.ledge[2], X, Y, 1, 8);
    this.px(x, p.ledge[2], X + w - 1, Y, 1, 8);
    for (let i = 4; i < w - 2; i += 8) this.px(x, p.ledge[2], X + i, Y + 4, 2, 2);
  }
};

// page/backgrounds/platformer/world.js
var World = class {
  /** A new game; `seed` picks the layout and everything random after it. */
  constructor(seed = 1) {
    this.seed = seed;
    this.frame = 0;
    this.score = 0;
    this.coinsGot = 0;
    this.hearts = 3;
    this.rng = rngOf(seed * 7 + 1);
    this.stats = { hits: {}, falls: 0, unsticks: 0, waves: 0, waves90: 0 };
  }
  /** Build the level for a W x H screen (native pixels); `opts.flat` keeps ground spans flat (level.js). */
  build(W, H, opts = {}) {
    this.W = W;
    this.H = H;
    this.L = buildLevel(W, H, this.seed, opts);
    const L = this.L;
    this.coins = L.coinSpots.map((s) => ({ x: s.x, y: s.y, w: 12, h: 16, on: true, t: 0, loose: false, arc: s.arc || null }));
    for (const a of L.arcs) a.live = this.coins.filter((c) => c.arc === a);
    this.lastCoin = this.frame;
    this.enemies = [];
    this.bats = [];
    this.bullets = [];
    this.items = [];
    this.parts = [];
    const batN = Math.max(1, Math.min(3, Math.round(W / 320)));
    for (let i = 0; i < batN; i++) this.bats.push({ x: this.rng() * W, baseY: 30 + this.rng() * Math.max(20, H * 0.5), vx: (this.rng() < 0.5 ? -1 : 1) * (0.5 + this.rng() * 0.3), t: this.rng() * 400, w: 20, h: 12, dead: 0, out: 0 });
    this.clouds = [];
    const n = Math.max(3, Math.round(W / 90));
    for (let i = 0; i < n; i++) this.clouds.push(this.makeCloud(this.rng() * W, 12 + this.rng() * H * 0.45, 0.04 + this.rng() * 0.08));
    const g0 = L.surfaces.filter((s) => Math.abs(s.y - L.groundY) < 1).sort((a, b) => b.x1 - b.x0 - (a.x1 - a.x0))[0] || L.surfaces[0];
    this.spawnSurface = g0;
    const reach = shortest(L, g0.id).dist;
    for (const c of this.coins) {
      if (c.arc) {
        c.counts = reach.has(c.arc.from);
        continue;
      }
      const t = this.surfaceUnder(c);
      c.counts = !!t && reach.has(t.id);
    }
    this.girl = null;
    this.respawn();
  }
  // a cloud's shape (drawn by draw.js)
  makeCloud(x, y, vx) {
    const rng = this.rng, w = 26 + Math.floor(rng() * 26), h = 10 + Math.floor(rng() * 6);
    const circles = [];
    for (let i = 0; i < 4; i++) circles.push({ cx: 6 + rng() * (w - 12), cy: h - 4 - rng() * (h - 8), r: 4 + rng() * (h * 0.55) });
    circles.push({ cx: w / 2, cy: h - 5, r: h * 0.5 });
    return { x, y, vx, circles, w, h, c: null };
  }
  surfaceUnder(c) {
    let best = null;
    for (const t of this.L.surfaces) if (c.x + 6 >= t.x0 - 2 && c.x + 6 <= t.x1 + 2 && t.y >= c.y + 16 && t.y - c.y - 16 <= 70 && (!best || t.y < best.y)) best = t;
    return best;
  }
  coinsLeft() {
    let n = 0, all = 0;
    for (const c of this.coins) if (!c.loose && c.counts) {
      all++;
      if (c.on) n++;
    }
    return { n, all };
  }
  // Coins come back all together, only once she has collected 90% of them (or after a long spell with no coin at
  // all, so a coin she somehow can't reach never stalls the level). ? blocks refill with them.
  coinWave() {
    let k = 0;
    for (const c of this.coins) if (!c.loose && !c.on) {
      c.on = false;
      c.t = 8 + k++ % 40 * 3;
      c.pending = true;
      c.skipUntil = 0;
    }
    for (const b of this.L.blocks) {
      b.active = true;
      b.skipUntil = 0;
    }
    this.stats.waves++;
    this.lastCoin = this.frame;
  }
  respawn() {
    const s = this.spawnSurface;
    this.girl = { seen: this.girl && this.girl.seen || /* @__PURE__ */ new Map(), x: (s.l + s.r) / 2 - GW / 2, y: s.y - GH, w: GW, h: GH, vx: 0, vy: 0, face: 1, ground: null, inv: 90, stun: 0, power: 0, exec: null, goal: null, goalT: 0, wait: 0, anim: 0, alive: true, through: 0, idle: 0 };
  }
  step() {
    this.frame++;
    const L = this.L;
    for (const m of L.movers) {
      const nx = m.x + m.vx;
      if (nx < m.x0 || nx > m.x1) m.vx = -m.vx;
      m.dx = m.vx;
      m.x += m.vx;
    }
    for (const c of this.clouds) {
      c.x += c.vx;
      if (c.x > this.W + 4) c.x = -c.w - 4;
    }
    this.updateGirl();
    this.updateEnemies();
    this.updateItems();
    for (const b of L.blocks) if (b.bump > 0) b.bump--;
    for (const c of this.coins) {
      if (!c.on) {
        if (c.pending && --c.t <= 0) {
          c.on = true;
          c.pending = false;
          this.sparkle(c.x + 2, c.y + 4);
        }
        continue;
      }
      if (c.loose) {
        if (!c.rest) {
          const r = physStep(L, c, false);
          if (r.ground) {
            c.rest = true;
            c.vx = 0;
          }
          c.vx *= 0.96;
        }
        if (--c.life <= 0 || c.y > this.H) c.on = false;
      }
    }
    this.coins = this.coins.filter((c) => c.on || !c.loose);
    this.parts = this.parts.filter((pt) => {
      pt.t++;
      pt.x += pt.vx || 0;
      pt.y += pt.vy || 0;
      if (pt.g) pt.vy += pt.g;
      return pt.t < pt.life;
    });
  }
};
Object.assign(World.prototype, PILOT, ACTORS, DRAW);

// page/backgrounds/platformer/index.js
var PLATFORMER = {
  id: "platformer",
  css: [PLATFORMER_CSS],
  start({ host: host2, layer, env }) {
    if (typeof CanvasRenderingContext2D !== "function") {
      return () => {
      };
    }
    const canvas2 = layer.ownerDocument.createElement("canvas");
    layer.append(canvas2);
    const stop = runAttract({ host: host2, canvasEl: canvas2, makeWorld: (seed) => new World(seed), env, seed: 1 + Math.floor(Math.random() * 1e6) });
    return () => {
      stop();
      canvas2.remove();
    };
  }
};

// page/backgrounds/index.js
var BACKGROUNDS = [PLATFORMER];

// page/shared/styles/base.css.js
var BASE_CSS = `
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
.cs-bad { color: var(--ui-red); }
.cs-good { color: var(--ui-green); }
.cs-foot { border-top: 1px solid var(--ui-stroke-tertiary); display: flex; flex-direction: column; gap: 10px; padding-top: 16px; }
.cs-screen { aspect-ratio: 10 / 9; background: var(--ui-bg-tertiary); display: block; image-rendering: pixelated; object-fit: cover; width: 100%; }
.cs-screen.ph { align-content: center; color: var(--ui-text-quaternary); display: grid; font: 700 10px/1.4 ${MONO}; letter-spacing: .1em; padding: 10px; text-align: center; text-transform: uppercase; }
.cs-link { all: unset; color: var(--ui-accent); cursor: pointer; font: 700 10px ${MONO}; letter-spacing: .12em; text-transform: uppercase; }
.cs-link:hover { text-decoration: underline; text-underline-offset: 3px; }
.cs-link:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
`;

// page/shared/styles/responsive.css.js
var RESPONSIVE_CSS = `
@container (max-width: 1000px) {
  .cs-setup { grid-template-columns: clamp(180px, 13cqi, 240px) minmax(0, 1fr); }
  .cs-setup > .cs-flyer { display: none; }
  .cs-empty { grid-template-columns: 1fr; }
  .cs-empty > .cs-art { display: none; }
}
/* Narrow main pane (an emulator tab docked beside it, a small window): the header stays one row.
   The segments tighten, the update chip keeps only its dot, the wordmark goes and, as
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
  .cs-setup, .cs-page-head { grid-template-columns: 1fr; }
  .cs-rail { position: static; }
  .cs-rail-item, .cs-rail-group { display: none; }
  .cs-meter { margin-top: 0; }
  .cs-choice { grid-template-columns: 1fr; }
  .cs-choice > div + div { border-left: 0; border-top: 1px solid var(--ui-stroke-tertiary); padding-left: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .cs-lem .run, .cs-glyph .cs-dash, .cs-reload .dot, .cs-flyer * { animation: none !important; }
  .cs-flyer .wing.r { transform: rotate(-10deg); }
  .cs-flyer .wing.l { transform: rotate(10deg); }
  .cs-cart { transition: none; }
}
`;

// page/shared/ui/flyer.css.js
var FLYER_CSS = `
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
`;

// page/app/shell.css.js
var SHELL_CSS = `
/* header: wordmark, one segmented control, the update chip */
.cs-top { align-items: center; background: var(--ui-bg-editor); border-bottom: 1px solid var(--ui-stroke-tertiary); display: grid; gap: 24px; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); padding: 14px clamp(16px, 3.5cqi, 64px); position: sticky; top: 0; z-index: 10; }
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
.cs-top-start { align-items: center; display: flex; min-width: 0; }
.cs-top-end { display: flex; justify-content: flex-end; justify-self: end; }
.cs-pad { display: flex; flex: 1; flex-direction: column; gap: 28px; isolation: isolate; padding: 26px clamp(16px, 3.5cqi, 64px) 36px; position: relative; }
/* the page's background (background-layer.js): behind everything in the page area */
.cs-bg { inset: 0; overflow: hidden; pointer-events: none; position: absolute; z-index: -1; }
.cs-bg[hidden] { display: none !important; }
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
/* a page's tab bar (app/page-view.js), for pages that declare tabs */
.cs-tabs { border-bottom: 1px solid var(--ui-stroke-tertiary); display: flex; gap: 4px; margin-top: -10px; }
.cs-tabs button { appearance: none; background: none; border: 0; border-bottom: 2px solid transparent; color: var(--ui-text-tertiary); cursor: pointer; font: 700 10.5px/1 ${MONO}; letter-spacing: .12em; padding: 8px 12px; text-transform: uppercase; }
.cs-tabs button:hover { color: var(--ui-text-primary); }
.cs-tabs button.on { border-bottom-color: var(--ui-accent); color: var(--ui-text-primary); }
.cs-tabs button:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-tab-body { display: contents; }
`;

// page/app/update/update.css.js
var UPDATE_CSS = `
.cs-top-end { align-items: center; gap: 10px; }
.cs-upd { position: relative; }
.cs-upd-chip { appearance: none; border: 0; color: var(--ui-text-primary); cursor: pointer; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.cs-upd-chip.accent { background: color-mix(in srgb, var(--ui-accent) 14%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-accent) 45%, transparent); }
.cs-upd-chip.accent > i { box-shadow: 0 0 0 3px color-mix(in srgb, var(--ui-accent) 25%, transparent); }
.cs-upd-chip.good { background: color-mix(in srgb, var(--ui-green) 13%, transparent); }
.cs-upd-chip.warn { background: color-mix(in srgb, var(--ui-yellow) 12%, transparent); }
.cs-upd-chip.bad { background: color-mix(in srgb, var(--ui-red) 12%, transparent); }
.cs-upd-chip:hover { filter: brightness(1.15); }
.cs-upd-chip:focus-visible { outline: 2px solid var(--ui-accent); outline-offset: 2px; }
.cs-upd-pop { background: linear-gradient(var(--ui-bg-secondary), var(--ui-bg-secondary)), var(--ui-bg-editor); border-radius: 8px;
  box-shadow: 0 0 0 1px var(--ui-stroke-secondary), 0 14px 36px color-mix(in srgb, black 40%, transparent); display: flex; flex-direction: column;
  gap: 8px; padding: 14px 16px; position: absolute; right: 0; top: calc(100% + 8px); width: min(340px, calc(100vw - 32px)); z-index: 30; }
.cs-upd-pop h3 { font-size: 17px; }
.cs-upd-pop p { color: var(--ui-text-secondary); font-size: 13px; line-height: 1.45; margin: 0; }
.cs-upd-pop .cs-eyebrow { color: var(--ui-text-tertiary); }
.cs-upd-kv { align-items: baseline; display: flex; gap: 10px; }
.cs-upd-kv b { color: var(--ui-text-tertiary); font: 700 10px ${MONO}; letter-spacing: .12em; text-transform: uppercase; }
.cs-upd-acts { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.cs-upd-fill { flex: 1; }
.cs-upd-pop p.cs-upd-wait { align-items: flex-start; background: color-mix(in srgb, var(--ui-yellow) 10%, transparent); color: var(--ui-text-primary); display: flex; gap: 8px; padding: 7px 9px; }
.cs-upd-wait > :first-child { color: var(--ui-yellow); flex: none; margin-top: 2px; }
.cs-upd-steps { display: flex; flex-direction: column; gap: 5px; list-style: none; margin: 2px 0; padding: 0; }
.cs-upd-steps li { align-items: center; color: var(--ui-text-tertiary); display: flex; font-size: 13px; gap: 9px; }
.cs-upd-steps li > i { box-shadow: inset 0 0 0 1px var(--ui-stroke-secondary); display: block; height: 12px; width: 12px; }
.cs-upd-steps li[data-state=done] { color: var(--ui-text-secondary); }
.cs-upd-steps li[data-state=done] > :first-child { color: var(--ui-green); }
.cs-upd-steps li[data-state=now] { color: var(--ui-text-primary); font-weight: 600; }
.cs-repair.bad { background: color-mix(in srgb, var(--ui-red) 10%, transparent); box-shadow: inset 2px 0 0 var(--ui-red); }
.cs-repair.bad > i { color: var(--ui-red); }
.cs-repair-wait { align-items: center; color: var(--ui-text-secondary); display: flex; gap: 6px; }
.cs-upd-pre { background: var(--ui-bg-quaternary); font: 11.5px/1.5 ${MONO}; margin: 0; max-height: 160px; overflow: auto; padding: 8px 10px; white-space: pre-wrap; }
`;

// page/app/style.js
var stylesheet = "";
function composeStyles(pages) {
  const chunks = (page) => [...page.css ?? [], ...(page.tabs ?? []).flatMap((tab) => tab.css ?? [])];
  return [
    BASE_CSS,
    SHELL_CSS,
    UPDATE_CSS,
    FLYER_CSS,
    ...BACKGROUNDS.flatMap((background) => background.css ?? []),
    ...pages.filter((page) => !page.cssLast).flatMap(chunks),
    RESPONSIVE_CSS,
    ...pages.filter((page) => page.cssLast).flatMap(chunks)
  ].join("");
}
function installPageStyles(pages) {
  stylesheet = composeStyles(pages);
}
function PageStyle() {
  return jsx("style", { children: stylesheet });
}

// page/pages/emulator/beside-chat/state.js
var ALWAYS_VISIBLE = atom(true);
var BUILD_TICK = atom(0);
var PRESENTED = atom({});
var sideTabs = /* @__PURE__ */ new Map();
var presentationsSeen = /* @__PURE__ */ new Set();
var sideSurface = (id) => `side:${id}`;
var sideKey = (id) => `${ID}.emulator.${id}`;

// page/pages/emulator/beside-chat/tab.js
function openSideEmulator(ctx, game) {
  if (!game || typeof host.openWorkspace !== "function") {
    return false;
  }
  const key = sideKey(game.id);
  const surface = sideSurface(game.id);
  claimLive(surface);
  try {
    const close = host.openWorkspace(key, {
      dock: { pane: "workspace", pos: "right" },
      minWidth: "22rem",
      title: `Emulator · ${game.title}`,
      render: () => jsx(SideEmulator, { ctx, gameId: game.id, paneId: `plugin-workspace:${key}`, title: game.title }),
      onClose: () => {
        sideTabs.delete(game.id);
        releaseLive(surface);
      }
    });
    sideTabs.set(game.id, typeof close === "function" ? close : () => {
    });
    return true;
  } catch (error) {
    releaseLive(surface);
    console.warn("[hermretro] the emulator could not open beside the chat:", String(error?.message ?? error));
    return false;
  }
}
function SideEmulator({ ctx, gameId, title, paneId }) {
  const surface = sideSurface(gameId);
  const owner = useValue(LIVE_PLAYER);
  const tick = useValue(BUILD_TICK);
  const [paneShown] = useState(() => typeof host.paneVisibility === "function" ? host.paneVisibility(paneId) : ALWAYS_VISIBLE);
  const shown = useValue(paneShown) !== false;
  const live = owner === surface;
  useEffect(() => {
    if (owner === null && shown) {
      claimLive(surface);
    }
  }, [owner, shown]);
  useEffect(() => () => releaseLive(surface), []);
  const games = useQuery({
    queryKey: [ID, "games", "side", gameId],
    queryFn: async () => (await callBackend(RPC_GAMES)).data,
    refetchInterval: shown ? 5e3 : 3e4,
    staleTime: 2e3,
    retry: false
  });
  const firstTick = useRef(tick);
  useEffect(() => {
    if (tick !== firstTick.current) {
      void games.refetch?.();
    }
  }, [tick]);
  const list = Array.isArray(games.data?.games) ? games.data.games : [];
  const demo = { ...DEMO_GAME, ...games.data?.demo && typeof games.data.demo === "object" ? games.data.demo : {}, id: DEMO_ID };
  const game = gameId === DEMO_ID ? demo : list.find((item) => item.id === gameId) ?? { id: gameId, title, rom: null, web: null, chat: null };
  const [reload, setReload] = useState(0);
  const [dismissed, setDismissed] = useState(null);
  const [capturesOpen, setCapturesOpen] = useState(false);
  const presentation = useValue(PRESENTED)[gameId] ?? null;
  const seenSeq = useRef(presentation?.seq ?? 0);
  const [noteHidden, setNoteHidden] = useState(null);
  useEffect(() => {
    const seq = presentation?.seq ?? 0;
    if (seq !== seenSeq.current) {
      seenSeq.current = seq;
      setDismissed(null);
      setReload((value) => value + 1);
      void games.refetch?.();
    }
  }, [presentation?.seq]);
  const note = presentation?.note && noteHidden !== presentation.seq ? presentation.note : null;
  const player = useQuery({
    queryKey: [ID, "player", "side", gameId, reload],
    queryFn: async () => (await callBackend(RPC_PLAYER, { id: gameId }, 3e4)).data,
    enabled: live,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false
  });
  const frameRef = useRef(null);
  const stageRef = useRef(null);
  const scopeRef = useRef(null);
  const loadedSha = player.data?.url ? player.data.romSha256 ?? null : null;
  const currentSha = playableSha(game);
  const rebuilt = Boolean(live && loadedSha && currentSha && loadedSha !== currentSha && dismissed !== currentSha);
  const bridge = usePlayerBridge({ ctx, frameRef, onAnnotate: (data) => annotateGame(ctx, game, data), scopeRef, visible: live && shown });
  const hardwareOn = Boolean(games.data?.device?.hardwareEnabled);
  return jsxs("div", {
    className: "cs-page cs-side",
    "data-page": "emulator",
    ref: scopeRef,
    children: [
      jsx(PageStyle, {}, "style"),
      ...live ? [
        jsx(EmulatorBar, {
          capturesOpen,
          ctx,
          focused: bridge.focused,
          game,
          hardwareOn,
          onAsk: () => askAboutGame(ctx, game, bridge.snap),
          onFull: () => void stageRef.current?.requestFullscreen?.()?.catch?.(() => {
          }),
          onLater: () => setDismissed(currentSha),
          onReload: () => setReload((value) => value + 1),
          onToggleCaptures: () => setCapturesOpen((open) => !open),
          player,
          rebuilt
        }, "bar"),
        note ? jsxs("div", {
          className: "cs-side-note",
          role: "note",
          children: [
            jsx(Codicon, { name: "comment", size: 14 }),
            jsx("span", { className: "cs-side-note-text", children: note }),
            jsx("button", {
              "aria-label": "Dismiss note",
              className: "cs-side-note-x",
              onClick: () => setNoteHidden(presentation.seq),
              title: "Dismiss",
              type: "button",
              children: jsx(Codicon, { name: "close", size: 12 })
            })
          ]
        }, "note") : null,
        jsx(PlayerNotice, { game, onRefresh: () => setReload((value) => value + 1), player, refreshing: player.isFetching }, "notice"),
        jsx(PlayerStage, { ctx, frameKey: `${gameId}:${reload}`, frameRef, game, player, stageRef, visible: true }, "player")
      ] : [jsx(PlayerAway, { onBring: () => claimLive(surface), where: "Playing in hermretro" }, "away")]
    ]
  });
}

// page/pages/emulator/beside-chat/row.js
function SideEmulatorRow({ ctx, game }) {
  const canOpen = typeof host.openWorkspace === "function";
  return jsxs("div", {
    className: "cs-rp-foot",
    children: [
      jsx("span", { className: "cs-rp-hint", children: "Hermes shows your game beside the chat when it is ready for you to try." }),
      jsx("span", { className: "cs-grow" }),
      canOpen && game ? jsxs(Button, {
        onClick: () => openSideEmulator(ctx, game),
        size: "sm",
        variant: "ghost",
        children: [jsx(Codicon, { name: "split-horizontal", size: 14 }), "Open beside the chat"]
      }) : null
    ]
  });
}

// page/pages/emulator/beside-chat/present.js
function presentedGame(payload) {
  const name = payload?.name === "tool_call" ? unwrapCalls(null, "tool_call", payload.args)[0]?.name : payload?.name;
  if (!payload || name !== PRESENT_TOOL || payload.error) {
    return null;
  }
  const result = toolResultObject(payload.result);
  const studio = result?.studio;
  if (!result || result.ok !== true || result.error || !studio || typeof studio.gameId !== "string" || !studio.gameId) {
    return null;
  }
  return studio;
}
function presentGame(ctx, { gameId, title, note, presentedAt }, { fromBuild = false } = {}) {
  const mark = `${gameId}:${presentedAt ?? ""}`;
  if (presentedAt != null && presentationsSeen.has(mark)) {
    return false;
  }
  presentationsSeen.add(mark);
  const shown = PRESENTED.get();
  const seq = (shown[gameId]?.seq ?? 0) + 1;
  const presentation = { seq, note: typeof note === "string" && note.trim() ? note.trim() : null, t: presentedAt ?? null };
  PRESENTED.set({ ...shown, [gameId]: presentation });
  emit("emulator.presented", { gameId, ...presentation });
  BUILD_TICK.set(BUILD_TICK.get() + 1);
  if (fromBuild || buildShowing() === gameId) {
    return false;
  }
  return openSideEmulator(ctx, { id: gameId, title: typeof title === "string" && title ? title : "Game" });
}
function watchBuilds(ctx) {
  const listen = typeof ctx.onEvent === "function" ? ctx.onEvent : typeof host.onEvent === "function" ? host.onEvent : null;
  if (!listen) {
    return;
  }
  let since = Date.now() / 1e3 - 5;
  let pending = null;
  listen("tool.complete", (event) => {
    const payload = event?.payload;
    if (!payload || event.replayed) {
      return;
    }
    const inner = payload.name === "tool_call" ? unwrapCalls(payload.tool_id ?? null, "tool_call", payload.args)[0] : null;
    const name = inner?.name ?? payload.name;
    if (BUILD_TOOLS.has(name)) {
      BUILD_TICK.set(BUILD_TICK.get() + 1);
    } else if (name === PRESENT_TOOL) {
      const studio = presentedGame(payload);
      if (studio) {
        presentGame(ctx, studio, { fromBuild: studio.buildConversation === true || isBuildSession(event.session_id) });
      }
    }
  });
  listen("message.complete", (event) => {
    if (event?.replayed) {
      return;
    }
    pending?.();
    const run = async () => {
      BUILD_TICK.set(BUILD_TICK.get() + 1);
      let answer;
      try {
        answer = (await callBackend(RPC_PRESENTATIONS, { since })).data;
      } catch {
        return;
      }
      if (!answer?.ok) {
        return;
      }
      if (typeof answer.now === "number") {
        since = answer.now - 1;
      }
      const list = Array.isArray(answer.presentations) ? answer.presentations : [];
      const newest = /* @__PURE__ */ new Map();
      for (const item of list) {
        if (item && typeof item.gameId === "string" && item.thisProfile !== false) {
          newest.set(item.gameId, item);
        }
      }
      for (const item of newest.values()) {
        const fromBuild = item.buildConversation === true || isBuildSession(item.sessionId) || isBuildSession(item.conversationId);
        presentGame(ctx, { gameId: item.gameId, title: item.title, note: item.note, presentedAt: item.t }, { fromBuild });
      }
    };
    const cancel = ctx.setTimeout?.(() => void run(), 600);
    pending = typeof cancel === "function" ? cancel : null;
  });
  ctx.onDispose?.(() => {
    for (const close of [...sideTabs.values()]) {
      try {
        close();
      } catch {
      }
    }
  });
}

// page/pages/emulator/emulator-page.js
function Emulator({ shell }) {
  const { ctx, go, hardwareOn, player } = shell;
  return [
    jsx(
      EmulatorBar,
      {
        capturesOpen: player.capturesOpen,
        ctx,
        focused: player.focused,
        game: player.game,
        go,
        hardwareOn,
        onAsk: player.ask,
        onFull: player.fullScreen,
        onLater: player.later,
        onReload: player.reload,
        onToggleCaptures: player.toggleCaptures,
        player: player.query,
        rebuilt: player.rebuilt
      },
      "bar"
    ),
    jsx(PlayerNotice, { game: player.game, onRefresh: player.refresh, player: player.query, refreshing: player.query.isFetching }, "notice")
  ];
}

// page/pages/emulator/emulator.css.js
var EMULATOR_CSS = `
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
`;

// page/pages/emulator/index.js
function BelowPlayer({ shell }) {
  return jsx(SideEmulatorRow, { ctx: shell.ctx, game: shell.player.game });
}
function EmulatorBadge({ nav }) {
  return nav.playing && nav.page !== "emulator" ? jsx("i", { "aria-label": "a game is loaded", className: "live", role: "img" }) : null;
}
var EMULATOR_PAGE = {
  id: "emulator",
  label: "Emulator",
  Page: Emulator,
  Badge: EmulatorBadge,
  pad: "flush",
  BelowPlayer,
  css: [EMULATOR_CSS],
  register: watchBuilds,
  // Setup's opt-in demo: the bundled cartridge in its own tab beside the chat, so the setup screen stays as it is.
  listens: {
    "setup.demoRequested": (_payload, ctx) => void openSideEmulator(ctx, { ...DEMO_GAME, id: DEMO_ID })
  },
  events: {
    "emulator.presented": "The agent presented a game (chromatic_present_game): { gameId, seq, note, t }. seq counts presentations of that game; the Build page plays it in its conversation."
  },
  slots: {
    "emulator.barActions": "Buttons in the bar above the player, after the keyboard light, for the user's own game (not the demo). Rendered on the Emulator page and in the emulator tab beside the chat. Props: { ctx, game, hardwareOn }, plus go(pageId) on the Emulator page only (beside the chat there is no shell: check go before using it)."
  }
};

// page/pages/index.js
var PAGES = [BUILD_PAGE, SETUP_PAGE, GAMES_PAGE, EMULATOR_PAGE];

// page/app/registry.js
var PAGE_FIELDS = /* @__PURE__ */ new Set(["id", "label", "Page", "tabs", "Badge", "pad", "BelowPlayer", "css", "cssLast", "events", "listens", "slots", "contributes", "register"]);
var TAB_FIELDS = /* @__PURE__ */ new Set(["id", "label", "Page", "css", "events", "listens", "slots", "contributes"]);
var ID2 = /^[a-z][a-z0-9-]*$/;
var NAME = /^[a-z][a-z0-9-]*\.[a-zA-Z][a-zA-Z0-9]*$/;
var isFunction = (value) => typeof value === "function";
function pageProblems(pages) {
  const problems = [];
  const seen = /* @__PURE__ */ new Set();
  const declared = { events: /* @__PURE__ */ new Set(), slots: /* @__PURE__ */ new Set() };
  const parts = [];
  pages.forEach((page, index) => {
    const where = `page/pages/${page?.id ?? `<#${index}>`}/index.js`;
    if (!page || typeof page !== "object") {
      problems.push(`page/pages/index.js lists something that is not a page descriptor at position ${index + 1}`);
      return;
    }
    if (!ID2.test(page.id ?? "") || seen.has(page.id)) {
      problems.push(`${where}: id must be a unique lowercase name, got ${JSON.stringify(page.id)}`);
    }
    seen.add(page.id);
    parts.push(...describe(page, where, PAGE_FIELDS, problems).map((part) => ({ ...part, owner: page.id })));
    if (!isFunction(page.Page) && !(Array.isArray(page.tabs) && page.tabs.length)) {
      problems.push(`${where}: give the page a Page component, or tabs`);
    }
    const tabIds = /* @__PURE__ */ new Set();
    for (const tab of Array.isArray(page.tabs) ? page.tabs : []) {
      const at = `${where} (tab ${tab?.id})`;
      if (!ID2.test(tab?.id ?? "") || tabIds.has(tab.id)) {
        problems.push(`${at}: tab id must be a unique lowercase name within the page`);
      }
      if (!isFunction(tab?.Page)) {
        problems.push(`${at}: a tab needs a Page component`);
      }
      tabIds.add(tab?.id);
      parts.push(...describe(tab ?? {}, at, TAB_FIELDS, problems).map((part) => ({ ...part, owner: page.id })));
    }
  });
  for (const { kind, name, where, owner } of parts.filter((part) => part.kind === "events" || part.kind === "slots")) {
    if (!NAME.test(name) || !name.startsWith(`${owner}.`)) {
      problems.push(`${where}: ${kind} "${name}" must be named "${owner}.<name>" (the owning page's id, a dot, a camelCase name)`);
    } else if (declared[kind].has(name)) {
      problems.push(`${where}: ${kind} "${name}" is declared twice; one page owns each name`);
    }
    declared[kind].add(name);
  }
  for (const { kind, name, where, value } of parts) {
    if (kind === "listens" && !declared.events.has(name)) {
      problems.push(`${where}: listens to "${name}", which no page declares in events`);
    } else if (kind === "listens" && !isFunction(value)) {
      problems.push(`${where}: listens["${name}"] must be a function (payload, ctx) => ...`);
    } else if (kind === "contributes" && !declared.slots.has(name)) {
      problems.push(`${where}: contributes to "${name}", which no page declares in slots`);
    } else if (kind === "contributes" && !(Array.isArray(value) && value.length && value.every(isFunction))) {
      problems.push(`${where}: contributes["${name}"] must be a list of components`);
    }
  }
  return problems;
}
function describe(item, where, fields, problems) {
  for (const key of Object.keys(item)) {
    if (!fields.has(key)) {
      problems.push(`${where}: unknown field "${key}" (known: ${[...fields].join(", ")})`);
    }
  }
  if (typeof item.label !== "string" || !item.label) {
    problems.push(`${where}: label must be the text its nav segment or tab shows`);
  }
  for (const key of ["Badge", "BelowPlayer", "register"]) {
    if (item[key] != null && !isFunction(item[key])) {
      problems.push(`${where}: ${key} must be a function`);
    }
  }
  if (item.css != null && !(Array.isArray(item.css) && item.css.every((chunk) => typeof chunk === "string"))) {
    problems.push(`${where}: css must be a list of stylesheet strings`);
  }
  const parts = [];
  for (const kind of ["events", "slots", "listens", "contributes"]) {
    for (const [name, value] of Object.entries(item[kind] ?? {})) {
      if ((kind === "events" || kind === "slots") && (typeof value !== "string" || !value)) {
        problems.push(`${where}: ${kind}["${name}"] needs a one-line description (what it is, the payload or props)`);
      }
      parts.push({ kind, name, value, where });
    }
  }
  return parts;
}
function wirePages(pages, { events, slots }) {
  const problems = pageProblems(pages);
  if (problems.length) {
    throw new Error(`the page registry has problems:
  ${problems.join("\n  ")}
FIX: see .agents/skills/hermretro-dev-page/references/adding.md, "Adding to the page"`);
  }
  const items = pages.flatMap((page) => [{ owner: page.id, item: page }, ...(page.tabs ?? []).map((tab) => ({ owner: page.id, item: tab }))]);
  for (const { owner, item } of items) {
    Object.entries(item.events ?? {}).forEach(([name, doc]) => events.declare(name, owner, doc));
    Object.entries(item.slots ?? {}).forEach(([name, doc]) => slots.declare(name, owner, doc));
  }
  for (const { owner, item } of items) {
    Object.entries(item.contributes ?? {}).forEach(([name, list]) => list.forEach((Component) => slots.fill(name, Component, owner)));
  }
  return {
    pages,
    listeners: items.flatMap(({ owner, item }) => Object.entries(item.listens ?? {}).map(([name, fn]) => ({ name, fn, owner }))),
    registers: pages.filter((page) => page.register).map((page) => page.register)
  };
}
var REGISTRY = wirePages(PAGES, { events: PAGE_EVENTS, slots: PAGE_SLOTS });
installPageStyles(PAGES);
var NAV_PAGES = REGISTRY.pages;
var pageById = (id) => NAV_PAGES.find((page) => page.id === id) ?? null;
var started = [];
function startPages(ctx) {
  started.forEach((stop) => stop());
  started = [];
  for (const register of REGISTRY.registers) {
    register(ctx);
  }
  for (const { name, fn } of REGISTRY.listeners) {
    started.push(PAGE_EVENTS.on(name, (payload) => fn(payload, ctx)));
  }
}

// page/shared/art/cart-hermretro.png
var cart_hermretro_default = [
  "data:image/png;base64,",
  "iVBORw0KGgoAAAANSUhEUgAAASsAAAFUCAYAAAB80BqgAACvQUlEQVR4nO39245lS3bm+YVHxN55TmaSTCaTWaoSUI8gQPfq",
  "ggqtrlapBaEBPYAE6CWoC/Vj9AsIaEGFLqABAf0M6vu6KECiwEoeM5knMjN37HBhOP3n/MfYc/khzoc1gAVfvuacNu0w7LNv",
  "DBtmdvFf/9f/x6///d///f/i5z//+X/z6NGjH11cXDy+uLh49Pjx40eXl5dXn/nf3/l88cUXj377298++ta3vvVo5GJ+fPTo",
  "6cXFxY8eP3782Zdffnn1/Hz+4R/+4dHnn38urS8uLi5+cnFx8Wweef78+dPnz5//6MmTJ589f/78i8ePH//kyy+/fPbkyZPL",
  "58+fz/VHT548mb8Xjx8/fvrs2bMfffbZZ5/N+ydNMmnPvdd5uXovmbyMTDpz39OnTx/95je/uSmf+/199uzZC2ldv3/+/eLZ",
  "s2c/efz48bPPP//8ctIYUc6578mTJxd///d//3Tq8Wtf+9qU6So9aahHz8z3ua5enjx58uwfi/OP5Zlr85myyst8pKl91NXI",
  "3Dv1I//q5xvf+MbFb3/726u8PXr06LPWz5MnT754/vz5Ty4vL5/Ny6eO5pl5R+v4us2uPtWPSeMb3/jGvHdU4enl5eXVO9Tr",
  "yOjL17/+9Zv8Vp98plzabvTh8vLySlceP358Odd/97vfPfrss89eaN/IxbNnz670aXRw6mHun7w9ffr0qnxPnz4dvbtUnuuy",
  "3zw7dTPPTvmfPXt2pY9ffPHFs6997WuX9EgbKoN2ffr06cVU3ePHj3/07Nmzz3afmTr+4osvrvTnun88ffr06Y9+97vffTb1",
  "Mm22ynV1/6NHj549fTpV+o/5bX3N/ddpXUxiX3zxxY+eP39+1bbSSn3etNn0ya997Wu9/sWXX355VddTNfRs7tN3rtvx+fSB",
  "3/72t4MVP/nhD3/4229961t//t/9d//33z16C3LxX/6X/7t/+fOf//y//cY3vvG//Pzzz7++lWkUaBTkutGvlG5+GxmworwD",
  "KE+fTlvdVODVc9MInr1u7OejMJP2l19+efH8+fOrZ64b4/kAlfeMss075trvfve7i88+++zxfJ9rU9kaop2WQrUz+U2lTyNo",
  "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",
  "rYCaI8R9fEjSbnhBWYZ0ONEBTTtaAVbYgfdikmYDd10UlJtOG7r1WP/Esu+/cl87v3bpkhoDSp9tZ8b8tKuOWwX1bP0o7egF",
  "2wGtsuaCawHbdQyFLrXOKXCn6aXZwFdtiokelbfpHQFlB5R2zKZVAAUUBT4dmM9MndFNs70d4OlJdXiX5fL6/q4tVac1P9tX",
  "gFsBvPWub1YHN/utYLh1o3TlQO+rfhFlElKi3ypHZ0iv+/rjqzirJ0+e/MvxxNdhaqfIYVg6mwLWXu0UcCk7gOso2EpSuBZi",
  "O4zrfJbmHpFPVUjzceq33VnftWyF2Pl76PX9f0fCo+tbdvp7NN7p3SV35f+hz98ld6X/0Po5lf8OEKc658vktwP1fdK76/5t",
  "xTS/ZaUFxPbdzijXXQBcrYfc2zZt1grk64JqHGQnrK7dOl/+5je/+Y9XkNyMlZb9/Oc/v/oMVd0NU8ZwNMLX7OhuinxORp7K",
  "9v/cJs3PKeAqOPWZjpLvkzw0Pw8Fm7vuf1XwetPg81B5aPq7s285dW33jVPvvy3to8F1///8jvwdvbNyql81/52x3f7ngkwZ",
  "qDx2YmBParFMihkjfuM+qNVRrLl6n4yUEnvRbIE6YDWR5b/3e7/3FdRuRPi+Jp2GHjSAsjNxzVRNiaNKPTJ3ajbe1nAbpI4U",
  "403KXcr6UHB5KPM6eudD7n8ok7vr+Tcle3B6mWe3vG8s/GXkyHWwhdVT/9MelOpTbn882uamPmZEyDNcULCn7prtbrm6v8gJ",
  "0diSDckfP9awrf0ydnJ9HV7AZHStvheFrYyjsT6tI0p7yv9wHwXdDsL3TR4KVm/a7LorvbdtBr5pOTVIvq78bjPxTQ8ulwf3",
  "3+b+ACx8jY2/bFQAEBoRzM1va2a2+3zBgsbsNcwBWYIN/FXbhfO00/KldPxHIzO7Mc7mcbr/0R/90QurzbtERVp8WXuGip/L",
  "fXVgcnybkagzuuB1inG9DmXccpcP41XNnv38BulTDPBl5U37jF7FRLmPvGr6p+rb5y7wvU/7VQzkI9tdclse71tPF4mF3JNK",
  "I9vnu6XO+IZSyOP4nsyGu4efymG6yI3vjfo3CQZ4uHmOgobn//GPi/WED4Dsysxka3bansOsG4nZdXC2a5lE5/+9Ql8FFWwq",
  "KkQGeqBET4ot+/F9OwP7t413H+V62Y7/ppnA9rHdNgq/jLxvTOZNyhEwnHJ+v4rZeJc8xOG+B/T7+BifZBb9vkxX3dQvtGPM",
  "atrpx90TTRwVC8vMJDDSv1lpZVadXe/+WJ3Ew8gEmF+dremiKeM6t+YG08jzv/Pbxo8FkBpQp7LF3jT2qRXazHU6VkMdmXVH",
  "DbcV4XWbd4152Y19nzzdJa+b2bzu9z1UHpq/h97/kPzvTl8Wciofp67fV07FLt12fctt+byt/rauHrHxHTzsN/cjHuqurGg+",
  "WNNMuO09vEb4nLqVUl1CDXHyjmKG/NfCsLvpFSg2tGD7k0SDd1HjANb8nfP6xgFvhwEvqN27xSLaxtgo5NEylCMAOjKTfL+L",
  "9r4sOPh75KDf975Jed0+rHftQ3qTYDWylyK9a5/i6zCjL6L7Ddo+Zcmc+h8oNBaLf7lBnXbMIEy59uN51oLornLxDoSnltt8",
  "H9LjgA/Ehex1j1dg1a142wlFLCuI9UPju5oXDOsaH9YAloIVgIqQI13KYtagEbPs1DKsXdkqRsUXuY9o/6sq131o+33v3Q3d",
  "SPeauq+Sn4eC06s6yF9VXub9zJWHmD1vSh7aHq/DQX+bf/OUP7cEpLN9NckAzdbH6atm/QuG3WNuu1eKJd0/DeGZ9wyGSG8v",
  "++ricCRq5MpnhV3VIdZlGX2RRPmwBh0nrAGV25T7aEW6zrrDGJpBinmfwLcdZdxrb6qz3WYCnlLKAm1Z5Kn8bnlVU/ehYPiu",
  "mdeWbVacys9mwqfkbbDhNykX92zPAhY2BfBr/hWsyrY8I8SgjvSu2pj7/O6ZLvrWd/m4gCZBWGp6Fp9mW+MXnGYcZt22BbrV",
  "cT73ju06MVgDWGMedn3QUQR630Xhtt2tQ96mSEcKe8pkfJ1y3/RO3VdGsJcl3Cf9D71zvQ6hM1t3jnTg6P+Hyl16eN/n7zPQ",
  "PNQnd3HP+7fbpAHZZvXrq3bf3qmibhusqjvG1toR0d7Qpq7RHemaR+/vbhebZT1llnXVcxcH7wIUjOxvNKbhANaYhHPfoOZ8",
  "Zm3hXmcGKY9MuL7rqDHa2Eej5uv2UZySUw72nd8jH0JjSjaY35X/hzLFVzVT3jdw3K6Fo/pv2+w1bQ9dTvM65FX8mq/DR3lx",
  "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",
  "27Sjbv1MZTplMgCoYNl8TZqdhe1n6w992O2xmXoZeydDhM0UzMr+DDY1312Txy4eLjOqm8H7ClRfHuwYq15qIrePKiu3ym4/",
  "Ojt/Z3JEGnSmflXArIyOle8171a/2qeDY5mkuu0mlZVrPfjts2fP/uzrX//6nz39/PPP//zRo0d/+vz58//m0aNH//zRo0c/",
  "nvpTWV9++eXF8+fPb5bl1AGsQuaFY7d2G9dTglobUZqx+n2K0mQrlC04dAR7UmnY/i2tVQ6srMcb1c/iHkqJZchf0zqq7Jbv",
  "yA73zm0qSmtvrwNQujjbKKwslNjZexs8tMFW3vohvLOMcjNJ9V0zQv7Kjgq0u47UbR3FNY2nnNOJ+F/mN+npyBTd75X9vjLd",
  "+T51JJ1Tn7K6fc6gjrddD/Ssg18ZTB392r67EBT86O1FnNpz3cqAzXzcWz1qG3cQtq/b/Fafb9Np3V3n5/k3vvGNy2uXwsWT",
  "J0+udm7ZLLMDnt+ryxucLy8vn19cXFyuPvPb58+f/0+fffbZ//Vb3/rWn1+l/G/+zb/9+pdffvnj58+fD1j96aNHj2ZZ/ZR0",
  "ro+2/uji4uIzyt1o384eqaA9DWmEakMd2amepcidtdl0dY+U0zHFX1FInZnCdKlHR8DdoGSbgR3dqiDbDGyM1M6vvzoJlsQ0",
  "rZJYooI9MpnksU7XmoQ1N7E2Z8lReEyxdVi/i9F7Dx71e9Qd0JF0t1dH1pqBrVO6ROk7i9jBo+Xdu0wc6VOlroUCMsCvDvf+",
  "WguAf+qSmS0PR66N6gv9atyY93Zw3fk9Svsi21UXxCqecZ9npF1da9nrB1xA98Xz589/8vnnnz+7rvshO4MVn3UwPWUGbsaX",
  "/vnFb3/725/85je/efb8+XMFfX55efmTp0+f/un3vve9/+l//B//X//QFn78r//1/+bz58+f/2gyMeUYRnV5eTmZ+dOLi4sf",
  "XV5e3m+O8YQcNeZD5Egh3+b7T+WjCvuQ9x/dv30gtz3/Kvl91TSP3lFge5l0j+qnafaeozrav21mu1nKm6iHj1ieX0/GjQU2",
  "f0eusCHk5u5Evrqjxk26X3zxxU+uGda0zeU3v/nNZ59//vlP/of/4d9fmU//f28B5rINcwryAAAAAElFTkSuQmCC"
].join("");

// page/shared/art/chrom-body.png
var chrom_body_default = [
  "data:image/png;base64,",
  "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",
  "AABJRU5ErkJggg=="
].join("");

// page/shared/art/chrom-wing.png
var chrom_wing_default = [
  "data:image/png;base64,",
  "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",
  "tAAAAABJRU5ErkJggg=="
].join("");

// page/shared/art/hermes.png
var hermes_default = [
  "data:image/png;base64,",
  "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"
].join("");

// page/shared/art/index.js
var ART_DATA = { hermes: hermes_default, cart: cart_hermretro_default, chromBody: chrom_body_default, chromWing: chrom_wing_default };

// page/shared/player/frame-image.js
function shrinkFrame(dataUrl) {
  return new Promise((resolve) => {
    try {
      const image = new Image();
      image.onload = () => {
        try {
          const canvas2 = document.createElement("canvas");
          canvas2.width = 160;
          canvas2.height = 144;
          const g = canvas2.getContext("2d");
          g.imageSmoothingEnabled = false;
          g.drawImage(image, 0, 0, 160, 144);
          const pixels = g.getImageData(0, 0, 160, 144).data;
          let varied = false;
          for (let i = 4; i < pixels.length && !varied; i += 4) {
            varied = pixels[i] !== pixels[0] || pixels[i + 1] !== pixels[1] || pixels[i + 2] !== pixels[2];
          }
          resolve(varied ? canvas2.toDataURL("image/png") : "");
        } catch {
          resolve("");
        }
      };
      image.onerror = () => resolve("");
      image.src = dataUrl;
    } catch {
      resolve("");
    }
  });
}

// page/app/update/flow.js
var UPDATE_STEPS = ["Downloading and checking the new version", "Loading it into the hermretro profile", "Refreshing this page"];
var UPDATE_MARKER = "update";
var UPDATE_TIMEOUT_MS = 3e5;
function requestOn(target, method, params, timeoutMs) {
  return target.route ? host.requestProfile(target.route, method, params, timeoutMs) : host.request(method, params, timeoutMs);
}
async function installTarget(installedIn) {
  const profile = installedIn?.linked ? null : installedIn?.profile ?? null;
  if (!profile) {
    return null;
  }
  let active = null;
  try {
    active = host.state.profile?.get?.() ?? null;
  } catch {
    active = null;
  }
  if (profile === active) {
    return { route: null, profile };
  }
  if (typeof host.profileRoutes !== "function" || typeof host.requestProfile !== "function") {
    return null;
  }
  const routes = await host.profileRoutes().catch(() => []) ?? [];
  const route = routes.find((candidate) => routeProfile(candidate) === profile);
  return route ? { route, profile } : null;
}
async function studioReloadTarget(exists = false) {
  const known = studioTarget();
  if (known) {
    return { route: known.route, profile: STUDIO_PROFILE };
  }
  if (typeof host.profileRoutes !== "function" || typeof host.requestProfile !== "function") {
    if (exists) {
      throw new Error("this Hermes cannot reach the hermretro profile from here");
    }
    return null;
  }
  const routes = await host.profileRoutes() ?? [];
  const route = routes.find((candidate) => routeProfile(candidate) === STUDIO_PROFILE);
  if (route) {
    return { route, profile: STUDIO_PROFILE };
  }
  if (exists) {
    throw new Error("the hermretro profile is not reachable right now");
  }
  return null;
}
var BUSY_STATUSES = /* @__PURE__ */ new Set(["starting", "working", "waiting", "streaming"]);
async function busyChats(studio) {
  if (!studio) {
    return [];
  }
  const answer = await requestOn(studio, "session.active_list", {}, 15e3);
  const sessions = Array.isArray(answer?.sessions) ? answer.sessions : [];
  return sessions.filter((session) => BUSY_STATUSES.has(session?.status)).map((session) => String(session.title || session.preview || "a chat").trim());
}
function busySentence(chats, verb = "update") {
  const names = chats.slice(0, 2).map((name) => `"${name}"`).join(" and ");
  return chats.length === 1 ? `A game is being built in ${names}. You can ${verb} when it finishes.` : `Games are being built in ${chats.length} chats (${names}${chats.length > 2 ? "…" : ""}). You can ${verb} when they finish.`;
}
function pluginRow(list) {
  const rows = Array.isArray(list?.plugins) ? list.plugins : [];
  return rows.find((row) => row?.name === ID || row?.key === ID) ?? null;
}
async function refreshDesktopHalf() {
  const reconcile = globalThis.window?.hermesDesktop?.reconcileDesktopPlugins;
  if (typeof reconcile !== "function") {
    return false;
  }
  try {
    await reconcile();
    return true;
  } catch {
    return false;
  }
}
async function reloadStudio(studio) {
  const toggle = (enable) => requestOn(studio, "plugins.manage", { action: "toggle", name: ID, enable }, 6e4);
  await toggle(false);
  let answer = null;
  for (let attempt = 0; attempt < 2 && !answer?.ok; attempt += 1) {
    answer = await toggle(true).catch(() => null);
  }
  if (!answer?.ok) {
    throw new Error("hermretro could not be switched back on in the hermretro profile.");
  }
  return Boolean(answer.gateway_reloaded) && !answer.restart_required;
}
async function loadIntoStudio({ install, studio, busy, onWaiting = () => {
}, waitMs = 2e3, checkTries = 5 }) {
  if (install && studio.profile === STUDIO_PROFILE && install.profile !== STUDIO_PROFILE) {
    let finished;
    try {
      finished = await requestOn(install, RPC_STUDIO_PROFILE, {}, 24e4);
    } catch (error) {
      finished = { ok: false, error: String(error?.message ?? error) };
    }
    if (!finished?.ok) {
      return { ok: false, error: `the hermretro profile's settings were not updated (${finished?.error ?? "no answer"})` };
    }
  }
  for (let failures = 0; ; ) {
    let chats;
    try {
      chats = await busy();
      failures = 0;
    } catch (error) {
      failures += 1;
      if (failures >= checkTries) {
        return { ok: false, error: `Could not check whether a game is being built (${String(error?.message ?? error)})` };
      }
      chats = null;
    }
    if (chats && !chats.length) {
      break;
    }
    if (chats) {
      onWaiting(chats);
    }
    await new Promise((resolve) => globalThis.setTimeout(resolve, waitMs));
  }
  onWaiting(null);
  try {
    return { ok: true, reloaded: await reloadStudio(studio) };
  } catch (error) {
    return { ok: false, error: String(error?.message ?? error) };
  }
}
async function runUpdate({
  install,
  studio,
  options = {},
  resume = false,
  busy = async () => [],
  onStep = () => {
  },
  onWaiting = () => {
  },
  installed = () => {
  },
  refused = () => {
  },
  remember: remember3 = () => {
  },
  waitMs = 2e3,
  checkTries = 5
}) {
  let building;
  try {
    building = await busy();
  } catch (error) {
    return { kind: "failed", error: `Could not check whether a game is being built (${String(error?.message ?? error)})` };
  }
  if (building.length) {
    return { kind: "busy", chats: building };
  }
  onStep(0);
  installed();
  const refuse = (outcome) => {
    if (!resume) {
      refused();
    }
    return outcome;
  };
  let result;
  try {
    result = await requestOn(install, "plugins.manage", { action: "update", name: ID, ...options }, UPDATE_TIMEOUT_MS);
  } catch (error) {
    const message = String(error?.message ?? error ?? "The update did not finish.");
    return typeof error?.code === "number" ? refuse({ kind: "failed", error: message }) : { kind: "partial", error: `Hermes's answer was lost (${message}), so the update may not have finished` };
  }
  if (result?.scan_blocked) {
    const findings = Array.isArray(result.scan_findings) ? result.scan_findings : [];
    return refuse(
      result.scan_verdict === "caution" && !options.force ? { kind: "review", findings, lines: [], retry: { ...options, force: true } } : { kind: "blocked", error: `Hermes's security check stopped this version (${result.scan_verdict ?? "blocked"}).` }
    );
  }
  if (result?.consent_required) {
    return refuse(
      options.accept_capabilities ? { kind: "failed", error: result.error ?? "Hermes did not apply the update." } : {
        kind: "review",
        findings: [],
        lines: Array.isArray(result.delta_lines) ? result.delta_lines : [],
        retry: { ...options, accept_capabilities: true }
      }
    );
  }
  if (!result?.ok) {
    return refuse({ kind: "failed", error: result?.error ?? "The update did not finish." });
  }
  if (result.unchanged && !resume) {
    return refuse({ kind: "current" });
  }
  let restart = Boolean(result.restart_required);
  onStep(1);
  if (studio && studio.profile !== install.profile) {
    const loaded = await loadIntoStudio({ install, studio, busy, onWaiting, waitMs, checkTries });
    if (!loaded.ok) {
      return { kind: "partial", error: loaded.error };
    }
    restart = !loaded.reloaded || restart;
  }
  onStep(2);
  remember3({ result: "updated", restart, at: Date.now() });
  return { kind: "updated", restart, pageRefreshed: await refreshDesktopHalf() };
}
async function runReload({ install, studio, busy = async () => [], onWaiting, waitMs, checkTries }) {
  let building;
  try {
    building = await busy();
  } catch (error) {
    return { kind: "failed", error: `Could not check whether a game is being built (${String(error?.message ?? error)})` };
  }
  if (building.length) {
    return { kind: "busy", chats: building };
  }
  const loaded = await loadIntoStudio({ install, studio, busy, onWaiting, waitMs, checkTries });
  if (!loaded.ok) {
    return { kind: "failed", error: loaded.error };
  }
  return loaded.reloaded ? { kind: "reloaded", pageRefreshed: await refreshDesktopHalf() } : { kind: "restart" };
}

// page/app/update/chip.js
var CHIP = {
  idle: ["accent", "Update ready"],
  updating: ["accent", "Updating"],
  review: ["warn", "Needs a look"],
  failed: ["bad", "Update failed"],
  restart: ["warn", "Restart to finish"],
  partial: ["bad", "Finish update"],
  done: ["good", "Updated"]
};
function Steps({ step, waiting }) {
  const labels = waiting?.length ? UPDATE_STEPS.map((label, index) => index === 1 ? `Waiting for "${waiting[0]}" to finish building` : label) : UPDATE_STEPS;
  return jsx("ol", {
    className: "cs-upd-steps",
    children: labels.map(
      (label, index) => jsxs(
        "li",
        {
          "data-state": index < step ? "done" : index === step ? "now" : "todo",
          children: [
            index < step ? jsx(Codicon, { name: "check", size: 12 }) : index === step ? jsx(Codicon, { name: "loading", size: 12, spinning: true }) : jsx("i", {}),
            label
          ]
        },
        label
      )
    )
  });
}
function Findings({ review }) {
  const lines = review.findings.length ? review.findings.slice(0, 6).map((f) => `${String(f.severity ?? "").toUpperCase()}  ${f.file ?? ""}:${f.line ?? ""}  ${f.description || f.category || ""}`) : review.lines.slice(0, 8);
  return lines.length ? jsx("pre", { className: "cs-upd-pre", children: lines.join("\n") }) : null;
}
function body(update) {
  const actions = (...children) => jsx("div", { className: "cs-upd-acts", children });
  const whatsNew = jsxs(Button, { onClick: update.whatsNew, size: "sm", variant: "link", children: ["What's new", jsx(Codicon, { name: "link-external", size: 12 })] }, "new");
  switch (update.phase) {
    case "updating":
      return ["Updating…", jsx(Steps, { step: update.step, waiting: update.waiting }, "steps"), jsx("p", { children: "You can keep using Hermes. This page reloads by itself at the end." }, "p")];
    case "review":
      return [
        "Review the new version",
        jsx(
          "p",
          {
            children: update.review?.findings?.length ? "Hermes's security check found something to look at before installing it. Nothing has changed yet." : "The new version adds to what hermretro can do in Hermes. Nothing has changed yet."
          },
          "p"
        ),
        update.review ? jsx(Findings, { review: update.review }, "f") : null,
        actions(
          jsx(Button, { onClick: update.agree, size: "sm", variant: "default", children: "Install anyway" }, "yes"),
          jsx(Button, { onClick: update.cancel, size: "sm", variant: "ghost", children: "Cancel" }, "no")
        )
      ];
    case "failed":
      return [
        "Couldn't update",
        jsx("p", { children: `${update.error ?? "The update did not finish."} Nothing was changed${update.version ? `; you are still on ${update.version}` : ""}.` }, "p"),
        actions(
          jsx(Button, { onClick: update.start, size: "sm", variant: "default", children: "Try again" }, "again"),
          jsx(Button, { onClick: update.openPlugins, size: "sm", variant: "link", children: "Open Capabilities → Plugins" }, "plugins")
        )
      ];
    case "partial":
      return [
        "Almost there",
        jsx(
          "p",
          { children: `The new version is installed, but ${String(update.error ?? "its last steps did not finish").replace(/\.$/, "")}. Finish the update to load it everywhere.` },
          "p"
        ),
        update.blocked ? jsxs("p", { className: "cs-upd-wait", role: "status", children: [jsx(Codicon, { name: "clock", size: 12 }), update.blocked] }, "wait") : null,
        actions(
          jsx(Button, { disabled: Boolean(update.blocked), onClick: update.start, size: "sm", variant: "default", children: "Finish update" }, "finish"),
          jsx(Button, { onClick: update.openPlugins, size: "sm", variant: "link", children: "Open Capabilities → Plugins" }, "plugins")
        )
      ];
    case "restart":
      return [
        "Almost done",
        jsx("p", { children: `The new version is installed. ${update.restartAdvice} to finish loading it; until then hermretro keeps working.` }, "p"),
        actions(jsx(Button, { onClick: () => update.setOpen(false), size: "sm", variant: "outline", children: "Got it" }, "ok"))
      ];
    case "done":
      return ["Up to date", jsx("p", { children: "Your games, library and chats are kept. New chats use the new version." }, "p"), actions(whatsNew)];
    default:
      return [
        "A new version is ready",
        jsx("p", { children: "Your games, library and chats are kept. It takes about a minute." }, "p"),
        update.version ? jsxs("p", { className: "cs-upd-kv", children: [jsx("b", { children: "Installed" }), update.version] }, "kv") : null,
        update.blocked ? jsxs("p", { className: "cs-upd-wait", role: "status", children: [jsx(Codicon, { name: "clock", size: 12 }), update.blocked] }, "wait") : null,
        actions(
          jsx(Button, { disabled: Boolean(update.blocked), onClick: update.start, size: "sm", variant: "default", children: "Update now" }, "go"),
          whatsNew,
          jsx("span", { className: "cs-upd-fill" }, "fill"),
          jsx(Button, { onClick: update.later, size: "sm", variant: "ghost", children: "Later" }, "later")
        )
      ];
  }
}
function UpdateChip({ update }) {
  const root = useRef(null);
  const { open, phase, setOpen } = update;
  useEffect(() => {
    if (!open || phase === "updating") {
      return void 0;
    }
    const away = (event) => {
      if (!root.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    const escape = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("pointerdown", away, true);
    window.addEventListener("keydown", escape, true);
    return () => {
      window.removeEventListener("pointerdown", away, true);
      window.removeEventListener("keydown", escape, true);
    };
  }, [open, phase]);
  if (!update.visible) {
    return null;
  }
  const [tone, label] = CHIP[phase] ?? CHIP.idle;
  const [title, ...rest] = body(update);
  return jsxs("span", {
    className: "cs-upd",
    ref: root,
    children: [
      jsxs("button", {
        "aria-expanded": open,
        "aria-haspopup": "dialog",
        "aria-label": `hermretro: ${label}`,
        className: `cs-chip cs-upd-chip ${tone}`,
        "data-phase": phase,
        onClick: () => setOpen(!open),
        title: label,
        type: "button",
        children: [phase === "updating" ? jsx(Codicon, { name: "loading", size: 11, spinning: true }) : jsx("i", {}), jsx("span", { className: "cs-lbl", children: label })]
      }),
      open ? jsxs("div", {
        "aria-label": "hermretro update",
        className: "cs-upd-pop",
        role: "dialog",
        children: [jsx("p", { className: "cs-eyebrow", children: "hermretro" }), jsx("h3", { className: "cs-word", children: title }), ...rest]
      }) : null
    ]
  });
}

// page/app/nav.js
function StudioNav({ pages, nav, onGo, viaProfile = null, update = null }) {
  const page = nav.page;
  return jsxs("header", {
    className: "cs-top",
    children: [
      jsxs("div", {
        className: "cs-top-start",
        children: [
          jsxs("button", {
            "aria-label": "hermretro: Build",
            className: "cs-brand",
            onClick: () => onGo("build"),
            type: "button",
            children: ["herm", jsx("span", { children: "retro" })]
          }),
          // The profile the studio works in, when it is not the one the app is on: a quiet chip, the
          // explanation in its tooltip.
          viaProfile ? jsx(Tip, {
            label: `Showing the "${viaProfile}" profile, where hermretro is switched on.`,
            children: jsxs("span", {
              "aria-label": `Showing the "${viaProfile}" profile, where hermretro is switched on.`,
              className: "cs-top-profile",
              children: [jsx(Codicon, { name: "account", size: 12 }), viaProfile]
            })
          }) : null
        ]
      }),
      jsx("nav", {
        "aria-label": "Studio pages",
        className: "cs-seg",
        children: pages.map(
          ({ id, label, Badge }) => jsxs(
            "button",
            {
              "aria-current": page === id ? "page" : void 0,
              onClick: () => onGo(id),
              type: "button",
              children: [label, Badge ? jsx(Badge, { nav }) : null]
            },
            id
          )
        )
      }),
      jsx("div", {
        className: "cs-top-end",
        children: update ? jsx(UpdateChip, { update }) : null
      })
    ]
  });
}

// page/app/not-running.js
function NotRunning({ backend, status, gateway, onRefresh, refreshing }) {
  const refresh = jsx("div", {
    className: "cs-actions",
    children: jsxs(Button, {
      disabled: refreshing,
      onClick: onRefresh,
      size: "sm",
      variant: "default",
      children: [jsx(Codicon, { name: "refresh", size: 14, spinning: refreshing }), "Refresh"]
    })
  });
  let title = "Checking hermretro…";
  let body2 = jsx(Working, { children: "Asking the plugin for its status." });
  if (backend === "offline") {
    title = "Waiting for Hermes";
    body2 = jsx(Working, { children: `The connection to Hermes is ${gateway || "idle"}. This page continues by itself.` });
  } else if (backend === "error") {
    title = "hermretro reported a problem";
    body2 = jsxs("div", {
      className: "cs-content",
      children: [jsx("pre", { className: "cs-error", children: status.data?.error || "Unknown error" }), refresh]
    });
  } else if (backend === "failed") {
    title = "Could not read hermretro's status";
    body2 = jsxs("div", {
      className: "cs-content",
      children: [
        jsx(Lede, { children: "The plugin is on, but its status request failed. Press Refresh; if this stays, report the message below." }),
        jsx("pre", { className: "cs-error", children: describeRequestError(status.error).message || "Unknown error" }),
        refresh
      ]
    });
  } else if (backend === "unavailable") {
    const { message, notLoaded } = describeRequestError(status.error);
    title = "hermretro is not switched on in any profile";
    body2 = jsxs("div", {
      className: "cs-content",
      children: [
        jsx(Lede, {
          children: "This page is visible, but the part of the plugin that does the work is off. Switch hermretro on in Capabilities → Plugins for the profile you want to use it in. This page continues by itself once it is on."
        }),
        jsx("div", {
          className: "cs-actions",
          children: jsxs(Button, {
            onClick: () => host.navigate(PLUGINS_HREF),
            size: "sm",
            variant: "default",
            children: [jsx(Codicon, { name: "extensions", size: 14 }), "Open Capabilities → Plugins"]
          })
        }),
        jsxs("div", {
          className: "cs-col",
          style: { gap: 6 },
          children: [jsx("span", { className: "cs-faint", children: "Or, from a terminal:" }), jsx(CommandLine, { command: ENABLE_COMMAND })]
        }),
        !notLoaded && message ? jsx("span", { className: "cs-faint", children: `Details: ${message}` }) : null
      ]
    });
  }
  return jsx("section", {
    "aria-live": "polite",
    className: "cs-stage",
    style: { maxWidth: 860 },
    children: jsxs("div", {
      className: "cs-stage",
      style: { display: "contents" },
      children: [
        jsxs("div", {
          className: "cs-stage-head",
          children: [jsx("p", { className: "cs-eyebrow", children: "Status" }), jsx("h2", { className: "cs-word cs-title", children: title })]
        }),
        body2
      ]
    })
  });
}

// page/app/background-layer.js
var byId = new Map(BACKGROUNDS.map((background) => [background.id, background]));
function browserEnv(layer) {
  const win = layer.ownerDocument.defaultView;
  return {
    raf: (callback) => win.requestAnimationFrame(callback),
    caf: (id) => win.cancelAnimationFrame(id),
    setTimer: (callback, ms) => win.setTimeout(callback, ms),
    clearTimer: (id) => win.clearTimeout(id),
    getStyle: (el) => win.getComputedStyle(el),
    isHidden: () => win.document.hidden || layer.hidden,
    motion: win.matchMedia?.("(prefers-reduced-motion: reduce)"),
    observe: (els, onChange) => {
      const watch = new win.ResizeObserver(onChange);
      for (const el of els) watch.observe(el);
      return () => watch.disconnect();
    }
  };
}
function BackgroundSlot({ background, shown }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const layer = ref.current;
    return background.start({ host: layer.parentElement, layer, env: browserEnv(layer) });
  }, []);
  return jsx("div", { "aria-hidden": true, className: "cs-bg", "data-bg": background.id, hidden: !shown, ref });
}
function BackgroundLayer() {
  const [wanted, setWanted] = useState(wantedBackground);
  const [started2, setStarted] = useState([]);
  useLayoutEffect(() => {
    const update = () => setWanted(wantedBackground());
    update();
    return onBackgroundChange(update);
  }, []);
  if (wanted && !byId.has(wanted)) {
    console.warn(`[hermretro] no background "${wanted}" (page/backgrounds/index.js lists them)`);
  }
  const live = wanted && byId.has(wanted) && !started2.includes(wanted) ? [...started2, wanted] : started2;
  useLayoutEffect(() => {
    if (live !== started2) setStarted(live);
  });
  return live.map((id) => jsx(BackgroundSlot, { background: byId.get(id), shown: id === wanted }, id));
}

// page/app/page-view.js
function storedTab(ctx, page) {
  try {
    const id = ctx?.storage?.get?.(`tab:${page.id}`, null);
    return page.tabs.some((tab) => tab.id === id) ? id : page.tabs[0].id;
  } catch {
    return page.tabs[0].id;
  }
}
function TabbedPage({ page, shell }) {
  const [chosen, setChosen] = useState(() => storedTab(shell.ctx, page));
  const tab = page.tabs.find((item) => item.id === chosen) ?? page.tabs[0];
  const pick = (id) => {
    setChosen(id);
    try {
      shell.ctx?.storage?.set?.(`tab:${page.id}`, id);
    } catch {
    }
  };
  return [
    jsx(
      "div",
      {
        "aria-label": `${page.label} tabs`,
        className: "cs-tabs",
        role: "tablist",
        children: page.tabs.map(
          (item) => jsx("button", { "aria-selected": item.id === tab.id, className: item.id === tab.id ? "on" : "", onClick: () => pick(item.id), role: "tab", type: "button", children: item.label }, item.id)
        )
      },
      "tabs"
    ),
    page.Page ? jsx(page.Page, { shell, tab: tab.id }, "page") : null,
    jsxs("div", { className: "cs-tab-body", role: "tabpanel", children: [jsx(tab.Page, { shell }, tab.id)] }, "tab")
  ];
}
function PageView({ page, shell }) {
  return page.tabs?.length ? jsx(TabbedPage, { page, shell }) : jsx(page.Page, { shell });
}

// page/app/update/reload-banner.js
function banner(tone, icon, text2, ...actions) {
  return jsxs("div", {
    className: tone ? `cs-repair ${tone}` : "cs-repair",
    role: "status",
    children: [jsx(Codicon, { name: icon, size: 14 }), jsx("span", { children: text2 }), ...actions]
  });
}
function ReloadBanner({ update }) {
  const { reload } = update;
  if (reload.phase === "failed") {
    return banner(
      "bad",
      "warning",
      `Reload did not finish: ${String(reload.error ?? "no answer").replace(/\.$/, "")}.`,
      jsx(Button, { disabled: Boolean(reload.blocked), onClick: reload.start, size: "sm", variant: "outline", children: "Try again" }, "again")
    );
  }
  if (reload.phase === "restart") {
    return banner(null, "refresh", `hermretro was updated. ${reload.advice} to finish loading it.`);
  }
  const reloading = reload.phase === "reloading";
  return banner(
    null,
    "refresh",
    "hermretro was updated, but Hermes is still running the old version.",
    reload.blocked && !reloading ? jsxs("span", { className: "cs-repair-wait", children: [jsx(Codicon, { name: "clock", size: 12 }), reload.blocked] }, "wait") : null,
    jsxs(
      Button,
      {
        disabled: reloading || Boolean(reload.blocked),
        onClick: reload.start,
        size: "sm",
        variant: "outline",
        children: [reloading ? jsx(Codicon, { name: "loading", size: 12, spinning: true }, "spin") : null, reloading ? "Reloading" : "Reload"]
      },
      "reload"
    )
  );
}

// page/app/update/use-update.js
var CHECK_EVERY_MS = 30 * 6e4;
var MARKER_FRESH_MS = 15 * 6e4;
var DONE_SHOWN_MS = 1e4;
var BUSY_EVERY_MS = 5e3;
var installingSentence = (verb) => `The game tools are being installed. You can ${verb} when that finishes.`;
var PENDING = "updatePending";
function pendingUpdate(ctx) {
  try {
    const pending = ctx.storage.get(PENDING, null);
    return pending && typeof pending === "object" ? pending : null;
  } catch {
    return null;
  }
}
function takeMarker(ctx) {
  try {
    const marker = ctx.storage.get(UPDATE_MARKER, null);
    if (marker) {
      ctx.storage.set(UPDATE_MARKER, null);
    }
    return marker && Date.now() - Number(marker.at ?? 0) < MARKER_FRESH_MS ? marker : null;
  } catch {
    return null;
  }
}
function remember2(ctx, key, value) {
  try {
    ctx.storage.set(key, value);
  } catch {
  }
}
var RESTART_ADVICE = { hermes: "Restart Hermes", app: "Quit and reopen Hermes" };
function usePluginUpdate({ ctx, status, running, installing = false, installError = null }) {
  const queryClient = useQueryClient();
  const installedIn = status.data?.plugin?.installed_in ?? null;
  const profile = installedIn && !installedIn.linked ? installedIn.profile ?? null : null;
  const check = useQuery({
    queryKey: [ID, "plugin-update", profile],
    queryFn: async () => {
      const target2 = await installTarget(installedIn);
      return target2 ? { target: target2, row: pluginRow(await requestOn(target2, "plugins.manage", { action: "list" }, 6e4)) } : { target: null, row: null };
    },
    enabled: running && Boolean(profile),
    refetchInterval: CHECK_EVERY_MS,
    staleTime: CHECK_EVERY_MS / 2,
    refetchOnWindowFocus: false,
    retry: false
  });
  const [state, setState] = useState(() => {
    const marker = takeMarker(ctx);
    if (marker) {
      return { phase: marker.restart ? "restart" : "done", step: 0, announce: true, restartFor: "hermes" };
    }
    const pending = pendingUpdate(ctx);
    return pending ? { phase: "partial", step: 0, error: pending.error ?? null } : { phase: "idle", step: 0 };
  });
  const [open, setOpen] = useState(false);
  const [reloadState, setReloadState] = useState({ phase: "idle", error: null });
  const stale = Boolean(status.data?.restart_needed);
  const [dismissed, setDismissed] = useState(() => {
    try {
      return ctx.storage.get("updateLater", null);
    } catch {
      return null;
    }
  });
  const busy = useRef(false);
  const installBlocked = useRef(false);
  installBlocked.current = installing || Boolean(installError);
  const studioExists = Boolean(status.data?.profile?.is_studio || status.data?.profile?.studio?.exists);
  useEffect(() => {
    if (!state.announce) {
      return void 0;
    }
    host.notify(
      state.phase === "restart" ? { kind: "warning", message: `hermretro was updated. ${RESTART_ADVICE.hermes} to finish loading it.` } : { kind: "success", message: "hermretro is up to date. Your games and chats are kept." }
    );
    if (state.phase !== "done") {
      return void 0;
    }
    ctx.setTimeout?.(() => setState((current) => current.phase === "done" ? { phase: "idle", step: 0 } : current), DONE_SHOWN_MS);
    return void 0;
  }, []);
  const row = check.data?.row ?? null;
  const target = check.data?.target ?? null;
  const ready = row?.update_available === true && Boolean(target);
  const later2 = ready && dismissed && dismissed === (row.update_target ?? "ready");
  const building = useQuery({
    queryKey: [ID, "update-busy"],
    queryFn: async () => busyChats(await studioReloadTarget(studioExists)),
    enabled: running && (ready && state.phase === "idle" || state.phase === "partial" || stale),
    refetchInterval: BUSY_EVERY_MS,
    retry: false
  });
  const fresher = state.raced && (building.dataUpdatedAt ?? 0) > state.racedAt;
  const chats = !fresher && state.raced || (Array.isArray(building.data) ? building.data : []);
  useEffect(() => {
    if (fresher) {
      setState((current) => ({ ...current, raced: void 0, racedAt: void 0 }));
    }
  }, [fresher]);
  const blockedFor = (verb) => installing ? installingSentence(verb) : installError || (chats.length ? busySentence(chats, verb) : null);
  const blocked = blockedFor("update");
  const start = async (options = {}) => {
    if (busy.current || !target) {
      return;
    }
    if (blocked) {
      setOpen(true);
      return;
    }
    busy.current = true;
    setUpdating(true);
    setOpen(true);
    setState({ phase: "updating", step: 0 });
    const resume = Boolean(pendingUpdate(ctx));
    let outcome;
    try {
      let studio = null;
      try {
        studio = await studioReloadTarget(studioExists);
      } catch (error) {
        outcome = { kind: "failed", error: `Could not reach the hermretro profile (${String(error?.message ?? error)})` };
      }
      outcome ??= await runUpdate({
        install: target,
        studio,
        options,
        resume,
        busy: () => installBlocked.current ? Promise.resolve(["the game tools install"]) : busyChats(studio),
        onStep: (step) => setState((current) => ({ ...current, step })),
        onWaiting: (waiting) => setState((current) => ({ ...current, waiting })),
        installed: () => remember2(ctx, PENDING, { at: Date.now(), error: null }),
        refused: () => remember2(ctx, PENDING, null),
        remember: (marker) => {
          remember2(ctx, PENDING, null);
          remember2(ctx, UPDATE_MARKER, marker);
        }
      });
    } finally {
      busy.current = false;
      setUpdating(false);
    }
    void queryClient.invalidateQueries({ queryKey: [ID] });
    const half = outcome.kind === "partial" || pendingUpdate(ctx) && ["failed", "blocked"].includes(outcome.kind);
    if (half) {
      remember2(ctx, PENDING, { at: Date.now(), error: outcome.error ?? null });
      setState({ phase: "partial", step: 0, error: outcome.error ?? null });
    } else if (outcome.kind === "updated") {
      setState({ phase: outcome.restart || !outcome.pageRefreshed ? "restart" : "done", step: 2, restartFor: outcome.restart ? "hermes" : "app" });
    } else if (outcome.kind === "current") {
      setState({ phase: "idle", step: 0 });
      setOpen(false);
      host.notify({ kind: "success", message: "hermretro is already up to date." });
    } else if (outcome.kind === "busy") {
      setState((current) => ({
        phase: resume ? "partial" : "idle",
        step: 0,
        error: resume ? current.error ?? null : null,
        raced: outcome.chats,
        racedAt: building.dataUpdatedAt ?? 0
      }));
    } else if (outcome.kind === "review") {
      setState({ phase: "review", step: 0, review: outcome });
    } else {
      setState({ phase: "failed", step: 0, error: outcome.error });
    }
  };
  const reload = async () => {
    if (busy.current || blockedFor("reload")) {
      return;
    }
    busy.current = true;
    setUpdating(true);
    setReloadState({ phase: "reloading", error: null });
    let outcome;
    try {
      let studio = null;
      try {
        studio = await studioReloadTarget(studioExists) ?? { route: routing.route ?? null, profile: routing.profile ?? null };
      } catch (error) {
        outcome = { kind: "failed", error: `Could not reach the hermretro profile (${String(error?.message ?? error)})` };
      }
      const install = await installTarget(installedIn);
      if (!outcome && !install && profile && profile !== STUDIO_PROFILE) {
        outcome = { kind: "failed", error: `Could not reach the ${profile} profile, where hermretro is installed` };
      }
      outcome ??= await runReload({
        install,
        studio,
        busy: () => installBlocked.current ? Promise.resolve(["the game tools install"]) : busyChats(studio)
      });
    } finally {
      busy.current = false;
      setUpdating(false);
    }
    setReloadState(
      outcome.kind === "failed" ? { phase: "failed", error: outcome.error } : outcome.kind === "restart" ? { phase: "restart", error: null, restartFor: "hermes" } : outcome.kind === "reloaded" && !outcome.pageRefreshed ? { phase: "restart", error: null, restartFor: "app" } : { phase: "idle", error: null }
    );
    void queryClient.invalidateQueries({ queryKey: [ID] });
  };
  const phase = state.phase;
  const visible = phase !== "idle" || ready && !later2;
  return {
    visible,
    ready,
    // Hermes answered for this install (so "up to date" can be said), and whether it is a linked checkout
    checked: Boolean(row),
    linked: Boolean(installedIn?.linked),
    phase,
    step: state.step,
    // why Update is refused right now (a build under way, the toolchain installing), or null
    blocked,
    // the chats a running update waits for before it reloads the hermretro profile, or null
    waiting: state.waiting ?? null,
    error: state.error ?? null,
    review: state.review ?? null,
    version: status.data?.plugin?.version ?? null,
    // what the 'restart' phase asks the user to do
    restartAdvice: RESTART_ADVICE[state.restartFor] ?? RESTART_ADVICE.hermes,
    // Hermes runs older code than is on disk (status restart_needed), and the banner's Reload
    stale,
    reload: { ...reloadState, advice: RESTART_ADVICE[reloadState.restartFor] ?? RESTART_ADVICE.hermes, blocked: blockedFor("reload"), start: () => void reload() },
    open,
    setOpen,
    start: () => void start(),
    agree: () => void start(state.review?.retry ?? {}),
    cancel: () => {
      setState({ phase: "idle", step: 0 });
      setOpen(false);
    },
    later: () => {
      const key = row?.update_target ?? "ready";
      setDismissed(key);
      remember2(ctx, "updateLater", key);
      setOpen(false);
    },
    whatsNew: () => void ctx.os?.openExternal?.(LINKS.releases),
    openPlugins: () => host.navigate(PLUGINS_HREF)
  };
}

// page/app/studio-page.js
var EMULATOR_GAME = "emulatorGame";
function pickedGame(ctx) {
  try {
    const id = ctx.storage.get(EMULATOR_GAME, null);
    return typeof id === "string" && id ? id : null;
  } catch {
    return null;
  }
}
function StudioPage({ ctx }) {
  const queryClient = useQueryClient();
  const [memory, update] = useSetupMemory(ctx);
  const [{ page, buildSelection, buildPending, visit }, setNavigation] = useState(() => {
    let stored = "build";
    try {
      stored = ctx.storage.get("page", "build");
    } catch {
    }
    return { page: pageById(stored) ? stored : "build", buildSelection: null, buildPending: [], visit: 0 };
  });
  const changeBuildVisit = useCallback((change) => {
    setNavigation((current) => current.page === "build" && current.visit === visit ? change(current) : current);
  }, [visit]);
  const selectBuild = useCallback((selection) => {
    changeBuildVisit((current) => current.buildSelection === selection ? current : { ...current, buildSelection: selection });
  }, [changeBuildVisit]);
  const changeBuildPending = (change) => {
    changeBuildVisit((current) => ({ ...current, buildPending: change(current.buildPending) }));
  };
  const [pinned, setPinned] = useState(null);
  const [polling, setPolling] = useState({ fast: true, pollDoctor: false });
  const { backend, doctor, gateway, status } = useBackend(polling);
  const refreshing = status.isFetching || doctor.isFetching;
  const running = backend === "ok";
  const steps = computeSteps({ backend, doctor, memory, status });
  const auto = running ? steps.find((step) => !step.complete) ?? null : null;
  const choosing = Boolean(auto?.hardware) && !memory.hardwareWanted && !memory.hardwareSkipped;
  const autoId = !running ? "not-running" : !auto ? "ready" : choosing ? "choice" : auto.id;
  const pinnedStep = running ? steps.find((step) => step.id === pinned) ?? null : null;
  const shown = pinnedStep ?? (choosing ? null : auto);
  const viaProfile = running ? status.data.via_profile ?? null : null;
  if (running) {
    routing.ambientStudio = !viaProfile && Boolean(status.data.profile?.is_studio);
  }
  const hardwareOn = Boolean(status.data?.hardware_enabled);
  const emulatorOnly = Boolean(memory.hardwareSkipped) && !hardwareOn;
  const gameReady = running && steps.filter((step) => !step.hardware).every((step) => step.complete);
  const settled = running && (Boolean(doctor.data) || doctor.isError);
  const lastAuto = useRef(autoId);
  const wasSettled = useRef(false);
  const stepsRef = useRef(steps);
  stepsRef.current = steps;
  useEffect(() => {
    const before = lastAuto.current;
    lastAuto.current = autoId;
    if (before === autoId) {
      return;
    }
    setPinned(null);
    const finished = stepsRef.current.find((step) => step.id === before);
    if (wasSettled.current && finished?.state === "done") {
      host.notify({ kind: "success", message: `${finished.title}: done` });
    }
  }, [autoId]);
  useEffect(() => {
    wasSettled.current = settled;
  }, [settled]);
  const priorSetup = Boolean(memory.hardwareSkipped || memory.hardwareWanted || memory.firmwareDone || memory.devmodeDone);
  const legacyReady = settled && !memory.onboardStarted && (gameReady || priorSetup || Boolean(status.data?.profile?.is_studio && toolchainStateKnown(status, doctor)));
  const onboarding = running && !memory.onboarded && !legacyReady;
  const onboardScreen = !onboarding ? null : !settled ? "checking" : !memory.onboardStarted ? "welcome" : !gameReady ? "install" : !memory.hardwareSkipped && !memory.hardwareWanted ? "chromatic" : "make";
  useEffect(() => {
    if (legacyReady && !memory.onboarded) {
      update({ onboarded: true });
    }
  }, [legacyReady, memory.onboarded]);
  const toolchainStep = steps.find((step) => step.id === "toolchain");
  const wantInstall = running && (onboarding || page === "setup" || toolchainStep?.state === "todo");
  const install = useInstall({ enabled: running, polling: wantInstall });
  const installState = install.data?.install?.state ?? null;
  const installElsewhere = Boolean(install.data?.install?.elsewhere);
  const pluginUpdate = usePluginUpdate({
    ctx,
    installing: install.starting || installState === "running",
    installError: install.unavailable,
    running,
    status
  });
  const lastElsewhere = useRef(installElsewhere);
  const finishedAt = install.data?.install?.finished_at ?? null;
  const doneRun = installState === "done" ? `${install.data?.install?.run_id ?? ""}@${finishedAt ?? ""}` : null;
  const verifiedRun = useRef(null);
  const doctorAsked = useRef({ fetching: false, at: 0, answerAt: 0 });
  useEffect(() => {
    const asked2 = doctorAsked.current;
    if (doctor.isFetching && !asked2.fetching) {
      asked2.at = Date.now();
    } else if (!doctor.isFetching && asked2.fetching) {
      asked2.answerAt = asked2.at;
    }
    asked2.fetching = Boolean(doctor.isFetching);
  }, [doctor.isFetching]);
  useEffect(() => {
    const wasElsewhere = lastElsewhere.current;
    lastElsewhere.current = installElsewhere;
    if (wasElsewhere && !installElsewhere) {
      void doctor.refetch?.();
    }
  }, [installElsewhere]);
  useEffect(() => {
    if (!doneRun || verifiedRun.current === doneRun) {
      return;
    }
    const finishedMs = Number(finishedAt) * 1e3 || 0;
    const asked2 = doctorAsked.current;
    const answeredAt = asked2.answerAt || Math.max(doctor.dataUpdatedAt ?? 0, doctor.errorUpdatedAt ?? 0);
    const current = doctor.isFetching ? asked2.at >= finishedMs : Boolean(doctor.data || doctor.isError) && answeredAt >= finishedMs;
    verifiedRun.current = doneRun;
    if (!finishedMs || !current) {
      void doctor.refetch?.();
    }
  }, [doneRun, doctor.isFetching]);
  const finishOnboarding = () => {
    update({ onboarded: true });
    go("build");
  };
  useEffect(() => {
    const toolchainOpen = toolchainStep && toolchainStep.state !== "done" && toolchainStep.state !== "checking";
    const next = {
      fast: autoId !== "ready",
      // Each check starts an engine worker: never while someone reads the review or waits on the page's own
      // install (its end triggers one check above), only while a chat installs where this page cannot see it.
      pollDoctor: Boolean(toolchainOpen) && installElsewhere
    };
    setPolling((current) => current.fast === next.fast && current.pollDoctor === next.pollDoctor ? current : next);
  }, [autoId, toolchainStep?.state, installElsewhere]);
  const go = (id, selection = null) => {
    setNavigation((current) => id === current.page && selection === null ? current : { page: id, buildSelection: id === "build" ? selection : null, buildPending: [], visit: current.visit + 1 });
    try {
      ctx.storage.set("page", id);
    } catch {
    }
  };
  const refresh = () => {
    routing.scannedAt = 0;
    forgetRoute();
    void queryClient.invalidateQueries({ queryKey: [ID] });
  };
  const pick = (id) => setPinned(id === autoId ? null : id);
  const setUpDevice = () => {
    update({ hardwareSkipped: false, hardwareWanted: true, onboarded: true });
    setPinned(null);
    go("setup");
  };
  const onEmulator = page === "emulator";
  const games = useQuery({
    queryKey: [ID, "games", viaProfile],
    queryFn: () => callStudio(RPC_GAMES),
    enabled: running,
    // While the player is on screen, a rebuild in chat is noticed within seconds.
    refetchInterval: onEmulator ? 5e3 : 3e4,
    staleTime: 2e3,
    retry: false
  });
  const gameList = Array.isArray(games.data?.games) ? games.data.games : [];
  const [emu, setEmu] = useState(() => ({ id: pickedGame(ctx), reload: 0 }));
  const [emuOpened, setEmuOpened] = useState(false);
  const [dismissed, setDismissed] = useState(null);
  const [capturesOpen, setCapturesOpen] = useState(false);
  const demo = { ...DEMO_GAME, ...games.data?.demo && typeof games.data.demo === "object" ? games.data.demo : {}, id: DEMO_ID };
  const libraryRead = Boolean(games.data && games.data.ok !== false && Array.isArray(games.data.games));
  const libraryKnown = Boolean(games.data) || games.isError;
  const picked = emu.id === DEMO_ID ? demo : gameList.find((item) => item.id === emu.id);
  const game = picked ?? ((emu.id ? libraryRead : libraryKnown) ? demo : null);
  useEffect(() => {
    if (libraryRead && emu.id && !picked) {
      setEmu((current) => ({ id: null, reload: current.reload }));
      try {
        ctx.storage.set(EMULATOR_GAME, null);
      } catch {
      }
    }
  }, [libraryRead, emu.id, Boolean(picked)]);
  useEffect(() => {
    if (onEmulator && game) {
      setEmuOpened(true);
    }
  }, [onEmulator, game?.id]);
  const liveOwner = useValue(LIVE_PLAYER);
  const pageLive = liveOwner === "page";
  useEffect(() => {
    if (onEmulator && running && liveOwner === null) {
      claimLive("page");
    }
  }, [onEmulator, running, liveOwner]);
  useEffect(() => () => releaseLive("page"), []);
  const player = useQuery({
    queryKey: [ID, "player", game?.id ?? null, emu.reload],
    queryFn: () => callStudio(RPC_PLAYER, { id: game.id }, 3e4),
    enabled: running && emuOpened && Boolean(game) && pageLive,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false
  });
  const frameRef = useRef(null);
  const stageRef = useRef(null);
  const loadedSha = player.data?.url ? player.data.romSha256 ?? null : null;
  const currentSha = playableSha(game);
  const rebuilt = Boolean(pageLive && loadedSha && currentSha && loadedSha !== currentSha && dismissed !== currentSha);
  const thumbTried = useRef(/* @__PURE__ */ new Set());
  const bridge = usePlayerBridge({ ctx, frameRef, onAnnotate: (data) => annotateGame(ctx, game, data), visible: onEmulator && running && pageLive });
  const ask = () => askAboutGame(ctx, game, bridge.snap);
  const onFrameLoad = () => {
    const target = game;
    if (!target || target.id === DEMO_ID || target.thumb || thumbTried.current.has(target.id)) {
      return;
    }
    thumbTried.current.add(target.id);
    const attempt = async (remaining) => {
      const png = await shrinkFrame(await bridge.snap());
      if (!png) {
        if (remaining > 0) {
          ctx.setTimeout(() => void attempt(remaining - 1), 5e3);
        }
        return;
      }
      try {
        await callStudio(RPC_GAME_THUMB, { id: target.id, png });
        void queryClient.invalidateQueries({ queryKey: [ID, "games"] });
      } catch (error) {
        console.warn("[hermretro] title screen not saved:", describeRequestError(error).message);
      }
    };
    ctx.setTimeout(() => void attempt(3), 3e3);
  };
  const play = (id) => {
    setEmu((current) => ({ id, reload: current.reload }));
    try {
      ctx.storage.set(EMULATOR_GAME, id);
    } catch {
    }
    go("emulator");
  };
  const currentPage = pageById(page) ?? NAV_PAGES[0];
  const shell = {
    ctx,
    page,
    go,
    refresh,
    refreshing,
    backend,
    doctor,
    gateway,
    status,
    // the profile the page's own queries go to when it is not the app's (null when it is the app's)
    viaProfile,
    // setup: the steps, where the user is in them, and first-run memory
    steps,
    memory,
    update,
    auto,
    autoId,
    choosing,
    shown,
    pick,
    unpin: () => setPinned(null),
    install,
    // Hermes's update of hermretro: the header chip, and the version row on the Setup page
    pluginUpdate,
    hardwareOn,
    emulatorOnly,
    setUpDevice,
    // games and the Build visit: selection and locally started games not in the library yet
    buildSelection,
    buildPending,
    changeBuildPending,
    selectBuild,
    games,
    gameList,
    gamesChanged: () => void queryClient.invalidateQueries({ queryKey: [ID, "games"] }),
    play,
    // the one player, kept by the shell so it survives page switches (the Emulator page shows it)
    player: {
      game,
      query: player,
      focused: bridge.focused,
      rebuilt,
      capturesOpen,
      ask,
      fullScreen: () => void stageRef.current?.requestFullscreen?.()?.catch?.(() => {
      }),
      later: () => setDismissed(currentSha),
      reload: () => setEmu((current) => ({ id: game.id, reload: current.reload + 1 })),
      refresh: () => {
        refresh();
        setEmu((current) => ({ id: current.id, reload: current.reload + 1 }));
      },
      toggleCaptures: () => setCapturesOpen((open) => !open)
    }
  };
  let body2;
  if (!running) {
    body2 = [jsx(NotRunning, { backend, gateway, onRefresh: refresh, refreshing, status }, "off")];
  } else if (onboardScreen) {
    body2 = [
      jsx(
        Onboarding,
        { ctx, doctor, install, onDevice: setUpDevice, onFinish: finishOnboarding, screen: onboardScreen, status, steps, update },
        "onboarding"
      )
    ];
  } else {
    body2 = [jsx(PageView, { page: currentPage, shell }, currentPage.id)];
  }
  const pad = running && !onboardScreen ? currentPage.pad ?? null : null;
  const broken = running && settled && !onboardScreen && page !== "setup" ? steps.find((step) => !step.hardware && !step.complete) : null;
  const stage = running && !onboardScreen && (emuOpened || onEmulator) ? pageLive ? jsx(PlayerStage, { ctx, frameKey: `${game?.id ?? "none"}:${emu.reload}`, frameRef, game, onLoad: onFrameLoad, player, stageRef, visible: onEmulator }, "player") : onEmulator ? jsx(PlayerAway, { onBring: () => claimLive("page"), where: "Playing beside the chat" }, "player") : null : null;
  return jsx(ScrollArea, {
    className: "h-full",
    style: { height: "100%" },
    children: jsxs("div", {
      className: "cs-page",
      "data-page": page,
      style: {
        "--cs-hermes": `url("${ART_DATA.hermes}")`,
        "--cs-cart": `url("${ART_DATA.cart}")`,
        "--cs-fly-body": `url("${ART_DATA.chromBody}")`,
        "--cs-fly-wing": `url("${ART_DATA.chromWing}")`
      },
      children: [
        jsx(PageStyle, {}, "style"),
        onboardScreen ? jsx(
          OnboardHeader,
          {
            end: pluginUpdate.visible ? jsx(UpdateChip, { update: pluginUpdate }) : null,
            stage: ONBOARD_STAGES.some(([id]) => id === onboardScreen) ? onboardScreen : null
          },
          "nav"
        ) : jsx(
          StudioNav,
          {
            nav: { page, playing: Boolean(stage && game && player.data?.url), setupPending: running && Boolean(auto) },
            onGo: go,
            pages: NAV_PAGES,
            update: pluginUpdate,
            viaProfile
          },
          "nav"
        ),
        jsxs(
          "div",
          {
            className: pad ? `cs-pad ${pad}` : "cs-pad",
            children: [
              jsx(BackgroundLayer, {}, "background"),
              // Hermes runs older code than is on disk (an update made outside this page). The chip covers its own update.
              // A reload under way or ended stays said even when hermretro stops answering (left switched off).
              (running && pluginUpdate.stale || pluginUpdate.reload.phase !== "idle") && pluginUpdate.phase !== "restart" ? jsx(ReloadBanner, { update: pluginUpdate }, "restart") : null,
              broken ? jsxs(
                "div",
                {
                  className: "cs-repair",
                  role: "status",
                  children: [
                    jsx(Codicon, { name: "warning", size: 14 }),
                    jsx("span", { children: `${STEP_SHORT[broken.id]} needs attention: ${broken.title.toLowerCase()} again to keep building games.` }),
                    jsx(Button, { onClick: () => go("setup"), size: "sm", variant: "outline", children: "Repair" })
                  ]
                },
                "repair"
              ) : null,
              ...body2,
              stage,
              pad && currentPage.BelowPlayer ? jsx(currentPage.BelowPlayer, { shell }, "side") : null,
              pad ? null : jsx(Footer, { ctx }, "foot")
            ]
          },
          "pad"
        )
      ]
    })
  });
}

// page/index.js
var index_default = {
  id: ID,
  name: "hermretro",
  register(ctx) {
    startPages(ctx);
    ctx.registerMany([
      {
        id: "page",
        area: ROUTES_AREA,
        data: { path: ROUTE },
        render: () => jsx(StudioPage, { ctx })
      },
      {
        id: "nav",
        area: SIDEBAR_NAV_AREA,
        order: 60,
        data: { codicon: "game", label: "HermRetro", path: ROUTE }
      },
      {
        id: "open",
        area: PALETTE_AREA,
        data: {
          id: `${ID}.open`,
          label: "hermretro: Open",
          keywords: ["chromatic", "modretro", "game boy", "gbc", "gb studio", "rom", "cartridge"],
          run: () => host.navigate(ROUTE)
        }
      }
    ]);
  }
};
export {
  index_default as default
};
