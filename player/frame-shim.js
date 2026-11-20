/**
 * hermretro — the player frame shim. GENERATED FILE, do not edit.
 * Source: page/frame/. Rebuild: node tools/bundle/bundle.mjs
 * Inlined first in the player frame page by backend/player/server.py; imports nothing.
 * build: esbuild 0.28.2
 * sources: sha256 0a9e1250f15b7c78186a1e1e29946e8bbe05f460aa1ddd33f802b0c17ab560a3
 * body: sha256 95927e7c4af1969f6960a485bc1b138d8055abf5b36c8c9f6bc670d3bc852a0e
 */
(() => {
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
    // { css }: the app's colours for the frame's own UI
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
  var DEVICE_RATIO = 850 / 1440;

  // page/frame/crop.js
  function frameImage(canvas) {
    try {
      return canvas ? canvas.toDataURL("image/png") : "";
    } catch {
      return "";
    }
  }
  function closeUp(canvas, box, { pad = 3, size = 96 } = {}) {
    if (!canvas || !box) {
      return "";
    }
    const unitX = canvas.width / 160;
    const unitY = canvas.height / 144;
    const left = Math.max(0, Math.floor(box.x * canvas.width - pad * unitX));
    const top = Math.max(0, Math.floor(box.y * canvas.height - pad * unitY));
    const width = Math.min(canvas.width - left, Math.ceil(box.w * canvas.width + 2 * pad * unitX));
    const height = Math.min(canvas.height - top, Math.ceil(box.h * canvas.height + 2 * pad * unitY));
    if (width <= 0 || height <= 0) {
      return "";
    }
    const zoom = Math.max(1, Math.floor(size / Math.max(width, height)));
    const out = document.createElement("canvas");
    out.width = width * zoom;
    out.height = height * zoom;
    const context = out.getContext("2d");
    context.imageSmoothingEnabled = false;
    context.drawImage(canvas, left, top, width, height, 0, 0, out.width, out.height);
    try {
      return out.toDataURL("image/png");
    } catch {
      return "";
    }
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

  // page/frame/note-card.js
  function openNoteCard(overlay, target, { onAsk, onCancel }) {
    overlay.root.querySelector(".hr-card")?.remove();
    const bounds = overlay.bounds();
    const card = document.createElement("div");
    const title = document.createElement("b");
    const kind = document.createElement("small");
    const note = document.createElement("textarea");
    const actions = document.createElement("div");
    const cancel = document.createElement("button");
    const ask = document.createElement("button");
    card.className = "hr-card";
    title.textContent = targetLabel(target.name, target.role);
    kind.textContent = target.name || "Part of the screen";
    note.placeholder = "What should HermRetro change or check here?";
    cancel.textContent = "Cancel";
    ask.textContent = "Ask HermRetro";
    ask.dataset.primary = "true";
    actions.append(cancel, ask);
    card.append(title, kind, note, actions);
    const below = bounds.top + (target.box.y + target.box.h) * bounds.height + 10;
    card.style.left = `${Math.min(innerWidth - 300, Math.max(8, bounds.left + target.box.x * bounds.width))}px`;
    card.style.top = `${Math.min(innerHeight - 180, below)}px`;
    cancel.addEventListener("click", () => {
      card.remove();
      onCancel();
    });
    ask.addEventListener("click", () => onAsk(note.value));
    card.addEventListener("pointerdown", (event) => event.stopPropagation());
    card.addEventListener("keydown", (event) => event.stopPropagation());
    overlay.root.append(card);
    note.focus();
  }

  // page/frame/overlay.js
  var element = (className, text) => {
    const node = document.createElement("div");
    node.className = className;
    if (text !== void 0) {
      node.textContent = text;
    }
    return node;
  };
  function boxIn(rect, bounds) {
    return {
      x: (rect.x - bounds.left) / bounds.width,
      y: (rect.y - bounds.top) / bounds.height,
      w: rect.width / bounds.width,
      h: rect.height / bounds.height
    };
  }
  function createOverlay(surfaceElement, { tip = null, onMove, onDown }) {
    const root = element("hr-ann");
    const layer = element("hr-layer");
    root.append(element("hr-veil"), layer, element("hr-frozen", "Frozen"));
    if (tip) {
      root.append(element("hr-tip", tip));
    }
    let bounds = surfaceElement.getBoundingClientRect();
    const place = () => {
      bounds = surfaceElement.getBoundingClientRect();
      Object.assign(root.style, { left: `${bounds.left}px`, top: `${bounds.top}px`, width: `${bounds.width}px`, height: `${bounds.height}px` });
    };
    const boxNode = (className, box) => {
      const node = element(`hr-box ${className}`);
      Object.assign(node.style, {
        left: `${box.x * bounds.width}px`,
        top: `${box.y * bounds.height}px`,
        width: `${box.w * bounds.width}px`,
        height: `${box.h * bounds.height}px`
      });
      return node;
    };
    const draw = ({ hovered, marks, selectedId }) => {
      const nodes = [];
      for (const mark of marks) {
        const node = boxNode(mark.id === selectedId ? "mark on" : "mark", mark.box);
        const badge = element("hr-n", String(mark.n));
        badge.classList.toggle("in-top", mark.box.y * bounds.height < 10);
        badge.classList.toggle("in-right", (mark.box.x + mark.box.w) * bounds.width > bounds.width - 10);
        node.append(badge);
        nodes.push(node);
      }
      if (hovered && !marks.some((mark) => mark.id === hovered.id)) {
        nodes.push(boxNode("hov", hovered.box));
        const label = element("hr-label", targetLabel(hovered.name, hovered.role));
        Object.assign(label.style, { left: `${Math.min(hovered.box.x * bounds.width, bounds.width - 140)}px`, top: `${Math.max(hovered.box.y * bounds.height, 30)}px` });
        nodes.push(label);
      }
      layer.replaceChildren(...nodes);
    };
    root.addEventListener("pointermove", (event) => onMove(event));
    root.addEventListener("pointerdown", (event) => onDown(event));
    addEventListener("resize", place);
    place();
    document.body.append(root);
    return {
      root,
      place,
      draw,
      bounds: () => bounds,
      remove() {
        removeEventListener("resize", place);
        root.remove();
      }
    };
  }

  // page/frame/post.js
  function post(message) {
    try {
      parent.postMessage(message, "*");
    } catch {
    }
  }

  // page/frame/view.css.js
  var FULL = `
.codex-game-view .cgv-color[data-device-color^="hermes-"]{order:-4}
html:not([data-hr-ui=inline]) .codex-game-view .cgv-player,
html:not([data-hr-ui=inline]) .codex-game-view .cgv-mode-views{width:max(220px,min(calc((100svh - 136px)*850/1440),calc(100vw - 112px)));max-width:none}
`;
  var INLINE = `
html[data-hr-ui=inline],html[data-hr-ui=inline] body{margin:0;width:100%;height:100%;overflow:hidden!important;background:transparent!important}
html[data-hr-ui=inline] .codex-game-view{position:fixed;inset:0;display:grid;place-items:center;margin:0;padding:0;gap:0;min-height:0}
html[data-hr-ui=inline] .codex-game-view :is(.cgv-header,.cgv-colors,.cgv-recording,.cgv-source-modes,.cgv-hint-area,.cgv-install-slot,.cgv-device-view){display:none!important}
html[data-hr-ui=inline] .codex-game-view .cgv-mode-views{width:100vw;height:100vh;max-width:none;display:grid;place-items:center}
html[data-hr-ui=inline] .codex-game-view :is(.cgv-views-stage,.cgv-player,.cgv-device-stage){width:100%;height:100%;display:grid;place-items:center;margin:0}
html[data-hr-ui=inline] .codex-game-view .cgv-shared-footer{position:fixed;left:50%;bottom:8px;transform:translateX(-50%);width:min(320px,calc(100vw - 16px));margin:0;z-index:5}
html[data-hr-ui=inline] .codex-game-view .cgv-handheld{width:min(100vw,calc(100vh*850/1440));filter:none;overflow-clip-margin:0}
html[data-hr-ui=inline][data-hr-view=screen] .codex-game-view .cgv-handheld{width:min(100vw,calc(100vh*10/9));aspect-ratio:10/9;overflow:hidden;border-radius:4px}
html[data-hr-ui=inline][data-hr-view=screen] .codex-game-view :is(.cgv-shell,.cgv-title,.cgv-device-controls){display:none!important}
html[data-hr-ui=inline][data-hr-view=screen] .codex-game-view .cgv-screen{inset:0;top:0;left:0;width:100%;height:100%}
`;
  var ENGINE_ANNOTATE = `
body>div[aria-hidden=true][style*="z-index: 999"]{display:none!important}
html[data-hr-ui=inline] .codex-game-view[data-annotating=true] .cgv-status{display:none!important}
`;
  var OVERLAY = `
.hr-ann{position:fixed;z-index:40;cursor:crosshair;--hr-a:var(--hr-accent,#3d7bff);font:600 11.5px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.hr-ann .hr-veil{position:absolute;inset:0;background:#0a0f1950;pointer-events:none;border-radius:2px}
.hr-ann .hr-box{position:absolute;pointer-events:none;border-radius:3px}
.hr-ann .hr-box.hov{outline:2px dashed var(--hr-a);background:color-mix(in srgb,var(--hr-a) 14%,transparent)}
.hr-ann .hr-box.mark{outline:2px solid var(--hr-a);box-shadow:0 0 0 4px color-mix(in srgb,var(--hr-a) 30%,transparent)}
.hr-ann .hr-box.mark.on{outline-width:3px}
.hr-ann .hr-n{position:absolute;top:-9px;right:-9px;display:grid;place-items:center;width:18px;height:18px;border-radius:50%;background:var(--hr-a);color:#fff;font:700 10.5px/1 ui-monospace,monospace}
.hr-ann .hr-n.in-top{top:2px}
.hr-ann .hr-n.in-right{right:2px}
.hr-ann .hr-label{position:absolute;transform:translateY(calc(-100% - 6px));white-space:nowrap;pointer-events:none;background:#141b29ee;color:#e8edf6;border:1px solid #ffffff22;border-radius:7px;padding:3px 8px;box-shadow:0 6px 16px #0006}
.hr-ann .hr-frozen{position:absolute;left:8px;bottom:8px;pointer-events:none;background:#000b;color:#fff;border-radius:6px;padding:3px 8px;font:600 11px/1.2 ui-monospace,monospace}
.hr-ann .hr-tip{position:absolute;left:50%;bottom:8px;transform:translateX(-50%);pointer-events:none;white-space:nowrap;background:#000b;color:#fff;border-radius:999px;padding:4px 10px}
.hr-card{position:fixed;z-index:41;width:min(290px,calc(100vw - 16px));padding:12px;border-radius:12px;background:#141b29;color:#e8edf6;border:1px solid #ffffff22;box-shadow:0 18px 50px #0008;display:flex;flex-direction:column;gap:8px;cursor:default;font:13px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.hr-card small{color:#9aa8c0;margin-top:-6px}
.hr-card textarea{min-height:60px;resize:vertical;border:1px solid var(--hr-accent,#3d7bff);border-radius:8px;padding:7px 9px;font:inherit;color:inherit;background:#0d1320}
.hr-card div{display:flex;justify-content:flex-end;gap:6px}
.hr-card button{min-height:30px;padding:5px 11px;border:0;border-radius:8px;background:transparent;color:#9aa8c0;font:600 12.5px inherit;cursor:pointer}
.hr-card button[data-primary]{background:var(--hr-accent,#3d7bff);color:#fff}
`;
  var FRAME_CSS = FULL + INLINE + ENGINE_ANNOTATE + OVERLAY;

  // page/frame/view.js
  var html = document.documentElement;
  function installStyles() {
    const add = () => {
      const style = document.createElement("style");
      style.id = "hr-frame";
      style.textContent = FRAME_CSS;
      document.head.append(style);
    };
    if (document.head) {
      add();
    } else {
      addEventListener("DOMContentLoaded", add, { once: true });
    }
  }
  function setView(view) {
    if (!VIEWS.includes(view)) {
      return;
    }
    if (view === "full") {
      delete html.dataset.hrUi;
      delete html.dataset.hrView;
    } else {
      html.dataset.hrUi = "inline";
      html.dataset.hrView = view;
    }
    dispatchEvent(new Event("resize"));
  }
  var inlineUi = () => html.dataset.hrUi === "inline";

  // page/frame/annotate-host.js
  var SURFACE_ID = "hermretro";
  var clone = (value) => {
    try {
      return JSON.parse(JSON.stringify(value ?? null));
    } catch {
      return null;
    }
  };
  function installAnnotateHost() {
    let surface = null;
    let active = false;
    let overlay = null;
    let hovered = null;
    let marks = [];
    let selectedId = null;
    const announce = (on) => document.dispatchEvent(new CustomEvent("oaiannotationmodechange", { detail: { active: on } }));
    const describeMarks = () => marks.map(({ n, id, name, role, metadata, colors, original, box }) => ({ n, id, name, role, metadata, colors, original, image: closeUp(surface?.element, box) }));
    const publish = () => post({ cs: FROM_FRAME.MARKS, marks: describeMarks() });
    const draw = () => overlay?.draw({ hovered, marks, selectedId });
    const select = (id) => {
      selectedId = id;
      try {
        surface?.renderSelection?.({ selectedId: id, hoveredId: null });
      } catch {
      }
      draw();
    };
    const hit = (event) => {
      try {
        const target = surface?.hitTest({ clientX: event.clientX, clientY: event.clientY });
        return target?.rect ? { ...target, box: boxIn(target.rect, overlay.bounds()) } : null;
      } catch {
        return null;
      }
    };
    const finishWithNote = (target, note) => {
      post({
        cs: FROM_FRAME.NOTE,
        target: { name: target.name, role: target.role, metadata: clone(target.metadata) },
        note,
        image: frameImage(surface?.element)
      });
      setActive(false);
    };
    const onDown = (event) => {
      const target = hit(event);
      if (!target) {
        return;
      }
      hovered = null;
      if (!inlineUi()) {
        const cancel = () => {
          marks = [];
          select(null);
        };
        marks = [{ ...target, n: 1, colors: null, original: null }];
        select(target.id);
        openNoteCard(overlay, target, { onAsk: (note) => finishWithNote(target, note), onCancel: cancel });
        return;
      }
      if (!marks.some((mark) => mark.id === target.id)) {
        marks = [...marks, { ...target, n: marks.length + 1, metadata: clone(target.metadata), colors: null, original: null }];
      }
      select(target.id);
      publish();
    };
    const onMove = (event) => {
      const next = hit(event);
      if (next?.id !== hovered?.id) {
        hovered = next;
        draw();
      }
    };
    function setActive(on) {
      if (active === on || on && !surface) {
        return;
      }
      active = on;
      hovered = null;
      marks = [];
      selectedId = null;
      overlay?.remove();
      overlay = on ? createOverlay(surface.element, { tip: inlineUi() ? null : "Click a thing in the game · Esc to finish", onDown, onMove }) : null;
      draw();
      if (inlineUi()) {
        publish();
      }
      announce(on);
    }
    const onControls = (controls) => {
      const mark = marks.find((entry) => entry.id === selectedId);
      if (!mark || !Array.isArray(controls)) {
        return;
      }
      mark.colors = controls.map((control) => control.currentValue);
      mark.original ??= [...mark.colors];
      publish();
    };
    const setColor = (id, index, value) => {
      const mark = marks.find((entry) => entry.id === id);
      const original = mark?.original?.[index];
      if (!mark || !original || !surface?.element) {
        return;
      }
      select(id);
      surface.element.dispatchEvent(
        new CustomEvent("oaiannotationcontrolchange", {
          detail: {
            action: value ? "preview" : "reset",
            callback: `palette-${index}`,
            value: value || original,
            virtualTarget: { surfaceId: SURFACE_ID, targetId: id }
          }
        })
      );
    };
    const removeMark = (id) => {
      marks = marks.filter((mark) => mark.id !== id).map((mark, index) => ({ ...mark, n: index + 1 }));
      select(marks.at(-1)?.id ?? null);
      publish();
    };
    const takeMarks = (id) => {
      post({ cs: FROM_FRAME.TAKEN, id, image: frameImage(surface?.element), marks: describeMarks() });
      setActive(false);
    };
    addEventListener(
      "keydown",
      (event) => {
        if (active && event.key === "Escape") {
          event.stopPropagation();
          setActive(false);
        }
      },
      true
    );
    document.oai = Object.assign(document.oai || {}, {
      annotation: {
        registerSurface(options) {
          surface = options;
          return {
            dispose() {
              if (surface === options) {
                setActive(false);
                surface = null;
              }
            },
            invalidate() {
              overlay?.place();
              draw();
            }
          };
        },
        registerControls() {
          return { update: (state) => onControls(state?.controls), dispose() {
          } };
        },
        isActive: () => active,
        toggle(on) {
          if (!surface) {
            return { accepted: false };
          }
          setTimeout(() => setActive(Boolean(on)));
          return { accepted: true };
        },
        request() {
          if (!surface) {
            return { accepted: false };
          }
          setTimeout(() => setActive(true));
          return { accepted: true };
        }
      }
    });
    return { setActive, setColor, removeMark, takeMarks, isActive: () => active };
  }

  // page/frame/engine.js
  var ROOT = ".codex-game-view";
  var playerRoot = () => document.querySelector(ROOT);
  var gameCanvas = () => document.querySelector("#mainCanvas");
  function press(action) {
    if (!PRESSABLE.includes(action)) {
      return false;
    }
    const button = playerRoot()?.querySelector(`[data-action="${action}"]`);
    if (!button || button.disabled) {
      return false;
    }
    button.click();
    return true;
  }
  function chooseFinish(id) {
    const swatch = /^[a-z0-9-]{1,40}$/.test(String(id)) ? playerRoot()?.querySelector(`[data-device-color="${id}"]`) : null;
    swatch?.click();
    return Boolean(swatch);
  }
  function readState(root) {
    const indicator = root.querySelector(".cgv-record-indicator");
    return {
      ready: true,
      paused: root.dataset.paused === "true",
      muted: root.dataset.muted === "true",
      annotating: root.dataset.annotating === "true",
      recording: Boolean(indicator && !indicator.hidden)
    };
  }
  function watchState() {
    let last = "";
    const report = (root) => {
      const state = readState(root);
      const key = JSON.stringify(state);
      if (key !== last) {
        last = key;
        post({ cs: FROM_FRAME.STATE, ...state });
      }
    };
    const watch = (root) => {
      const observer = new MutationObserver(() => report(root));
      observer.observe(root, { subtree: true, attributes: true, attributeFilter: ["data-paused", "data-muted", "data-annotating", "hidden"] });
      report(root);
    };
    const existing = playerRoot();
    if (existing) {
      watch(existing);
      return;
    }
    const waiting = new MutationObserver(() => {
      const root = playerRoot();
      if (root) {
        waiting.disconnect();
        watch(root);
      }
    });
    waiting.observe(document.documentElement, { childList: true, subtree: true });
  }

  // page/frame/commands.js
  var holdGame = (held) => {
    const { vm, Audio: sound } = (
      /** @type {any} */
      globalThis
    );
    try {
      if (held && vm && !vm.paused) {
        vm.paused = true;
        window.__hrHeld = true;
      } else if (!held && vm && window.__hrHeld) {
        vm.paused = false;
        window.__hrHeld = false;
      }
      sound?.ctx?.[held ? "suspend" : "resume"]?.();
    } catch {
    }
  };
  var setTheme = (css) => {
    let style = document.getElementById("hermes-theme");
    if (!style) {
      style = document.createElement("style");
      style.id = "hermes-theme";
      document.head.append(style);
    }
    style.textContent = typeof css === "string" ? css : "";
  };
  function listenForCommands(annotate) {
    const handlers = {
      // Dispatched on the body: the player's handlers call target.closest and ignore keys aimed at its
      // own buttons, and the event still bubbles up to window where the game reads it.
      [CMD.KEY]: ({ key, code, down }) => (document.body || document.documentElement).dispatchEvent(new KeyboardEvent(down ? "keydown" : "keyup", { key, code, bubbles: true, cancelable: true })),
      [CMD.SNAP]: ({ id }) => post({ cs: FROM_FRAME.SNAP, id, url: frameImage(gameCanvas()) }),
      [CMD.HOLD]: () => holdGame(true),
      [CMD.RELEASE]: () => holdGame(false),
      [CMD.THEME]: ({ css }) => setTheme(css),
      [CMD.VIEW]: ({ view }) => setView(view),
      [CMD.PRESS]: ({ action }) => press(action),
      [CMD.FINISH]: ({ id }) => chooseFinish(id),
      // Entering goes through the player's own button, so the engine freezes the frame and tracks it.
      [CMD.ANNOTATE]: ({ on }) => on ? !annotate.isActive() && press("annotate") : annotate.setActive(false),
      [CMD.MARK_COLOR]: ({ id, index, value }) => annotate.setColor(id, index, value),
      [CMD.MARK_REMOVE]: ({ id }) => annotate.removeMark(id),
      [CMD.MARKS_TAKE]: ({ id }) => annotate.takeMarks(id)
    };
    addEventListener("message", (event) => {
      const data = event.data;
      if (event.source === parent && data && data.cs === TO_FRAME) {
        handlers[data.type]?.(data);
      }
    });
    addEventListener("focus", () => post({ cs: FROM_FRAME.FOCUS, value: true }));
    addEventListener("blur", () => post({ cs: FROM_FRAME.FOCUS, value: false }));
  }

  // page/frame/sandbox.js
  var describe = (value) => {
    if (value instanceof Error) {
      return value.stack || value.message;
    }
    if (typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }
    return String(value);
  };
  function forwardLogs() {
    const send = (level, values) => post({ cs: FROM_FRAME.LOG, level, text: values.map(describe).join(" ").slice(0, 2e3) });
    for (const level of ["warn", "error"]) {
      const original = console[level].bind(console);
      console[level] = (...values) => {
        send(level, values);
        original(...values);
      };
    }
    addEventListener("error", (event) => send("error", [`${event.message} @${event.lineno}`]));
    addEventListener("unhandledrejection", (event) => send("error", ["unhandled: ", event.reason]));
  }
  function memoryStorage(seed = {}) {
    const items = new Map(Object.entries(seed));
    return {
      getItem: (key) => items.has(String(key)) ? items.get(String(key)) : null,
      setItem: (key, value) => {
        items.set(String(key), String(value));
      },
      removeItem: (key) => {
        items.delete(String(key));
      },
      clear: () => items.clear(),
      key: (index) => [...items.keys()][index] ?? null,
      get length() {
        return items.size;
      }
    };
  }
  function installStorage(params2, defaultColor, colorKey) {
    const asked = params2.get("color") || "";
    const color = /^[a-z0-9-]{1,40}$/.test(asked) ? asked : defaultColor;
    Object.defineProperty(window, "localStorage", { value: memoryStorage({ [colorKey]: color }), configurable: true });
    Object.defineProperty(window, "sessionStorage", { value: memoryStorage(), configurable: true });
  }
  function installFetch() {
    const realFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      if (init && init.mode === "same-origin") {
        init = { ...init, mode: "cors", credentials: "omit" };
      }
      if (input instanceof Request && input.mode === "same-origin") {
        input = new Request(input, { mode: "cors", credentials: "omit" });
      }
      return realFetch(input, init);
    };
  }

  // page/frame/index.js
  var params = new URLSearchParams(location.search);
  forwardLogs();
  installStorage(params, "__DEFAULT_COLOR__", "__COLOR_KEY__");
  installFetch();
  setView(params.get("view") || "full");
  installStyles();
  listenForCommands(installAnnotateHost());
  watchState();
})();
