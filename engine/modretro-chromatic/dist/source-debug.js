import { constants } from "node:fs";
import { lstat, open, realpath } from "node:fs/promises";
import path from "node:path";
import { authenticatedSourceBuild, captureBuildSourceProvenance, LIVE_STATE_LAYOUT, sameBuildSourceProvenance, } from "./build-provenance.js";
import { createDebugManifest, DebugSymbolsError, decodeCurrentScene, hashDebugRom, parseGlobalsDefinitions, parseNoiDefinitions, validateDebugManifest, } from "./debug-symbols.js";
import { MAX_EMULATOR_INSPECTION_BYTES } from "./emulator.js";
import { isPathWithinRoot } from "./platform.js";
import { PROJECT_RESPONSE_LIMITS } from "./project-access.js";
import { loadProjectSnapshot } from "./project-snapshot.js";
import { decodeResourceBytes } from "./resource-codec.js";
import { worldDependencies } from "./world-queries.js";
export const MAX_SOURCE_DEBUG_VARIABLES = 32;
export const MAX_SOURCE_DEBUG_COLLISION_CELLS = 256;
export const MAX_SOURCE_DEBUG_REFERENCES = 64;
const WRAM_BASE = 0xc000;
const SHA256 = /^[a-f0-9]{64}$/;
const SCENE_SYMBOL = /^scene_[A-Za-z0-9_]+$/;
const VARIABLE_SYMBOL = /^var_[A-Za-z0-9_]+$/;
export class SourceDebugError extends Error {
    code;
    constructor(code, message) {
        super(message);
        this.code = code;
        this.name = "SourceDebugError";
    }
}
function fail(code, message) {
    throw new SourceDebugError(code, message);
}
function samePath(left, right) {
    return isPathWithinRoot(left, right) && isPathWithinRoot(right, left);
}
function validSelector(value) {
    return typeof value === "string" && value.length > 0 && value.length <= 256 && !value.includes("\0");
}
function variableSummary(variable, reason) {
    return { id: variable.id, variableId: variable.id, name: variable.name,
        ...(typeof variable.symbol === "string" ? { symbol: variable.symbol } : {}), reason };
}
async function authenticatedFile(root, filename, expectedHash) {
    if (!SHA256.test(expectedHash) || !isPathWithinRoot(root, filename)) {
        fail("SOURCE_DEBUG_ARTIFACT_MISMATCH", "The captured debug artifact is outside its selected project or has an invalid digest.");
    }
    let handle;
    try {
        const metadata = await lstat(filename, { bigint: true });
        if (!metadata.isFile() || metadata.isSymbolicLink() || !samePath(await realpath(filename), filename)) {
            fail("SOURCE_DEBUG_ARTIFACT_MISMATCH", "A captured debug artifact was replaced by a symbolic link or non-file.");
        }
        handle = await open(filename, constants.O_RDONLY | (process.platform === "win32" ? 0 : (constants.O_NOFOLLOW ?? 0)));
        const opened = await handle.stat({ bigint: true });
        if (opened.dev !== metadata.dev || opened.ino !== metadata.ino || opened.size !== metadata.size
            || opened.mtimeNs !== metadata.mtimeNs || opened.ctimeNs !== metadata.ctimeNs) {
            fail("SOURCE_DEBUG_ARTIFACT_MISMATCH", "A captured debug artifact changed while it was opened.");
        }
        const bytes = await handle.readFile();
        const after = await handle.stat({ bigint: true });
        if (after.dev !== opened.dev || after.ino !== opened.ino || after.size !== opened.size
            || after.mtimeNs !== opened.mtimeNs || after.ctimeNs !== opened.ctimeNs) {
            fail("SOURCE_DEBUG_ARTIFACT_MISMATCH", "A captured debug artifact changed while it was read.");
        }
        if (hashDebugRom(bytes) !== expectedHash) {
            fail("SOURCE_DEBUG_ARTIFACT_MISMATCH", "Captured ROM or debug sidecar bytes no longer match this successful build. Rebuild with captureDebugArtifacts:true.");
        }
        return bytes;
    }
    catch (error) {
        if (error instanceof SourceDebugError)
            throw error;
        throw new SourceDebugError("SOURCE_DEBUG_ARTIFACT_MISMATCH", "A captured ROM or debug sidecar is no longer readable. Rebuild with captureDebugArtifacts:true.");
    }
    finally {
        await handle?.close();
    }
}
function sourceScene(scene, symbol) {
    return { id: scene.id, sceneId: scene.id, name: scene.name, symbol, resourcePath: scene.resourcePath,
        type: typeof scene.type === "string" ? scene.type : null,
        width: typeof scene.width === "number" ? scene.width : null,
        height: typeof scene.height === "number" ? scene.height : null };
}
function collisionRegion(scene, region) {
    const width = scene.width;
    const height = scene.height;
    if (typeof width !== "number" || typeof height !== "number" || !Number.isInteger(width) || !Number.isInteger(height)
        || width < 1 || height < 1 || width > 255 || height > 255 || typeof scene.collisions !== "string") {
        fail("SOURCE_DEBUG_COLLISIONS_UNAVAILABLE", "This scene does not have a supported authored collision grid.");
    }
    if (!region || typeof region !== "object" || ![region.x, region.y, region.width, region.height].every(Number.isInteger)
        || region.x < 0 || region.y < 0 || region.width < 1 || region.height < 1
        || region.x + region.width > width || region.y + region.height > height
        || region.width * region.height > MAX_SOURCE_DEBUG_COLLISION_CELLS) {
        fail("SOURCE_DEBUG_INVALID_QUERY", `Collision rectangles must fit inside the current scene and contain at most ${MAX_SOURCE_DEBUG_COLLISION_CELLS} tiles.`);
    }
    const decoded = decodeResourceBytes(scene.collisions, { maximumValues: width * height, allowImplicitZeroGrid: true });
    const cells = [];
    for (let y = region.y; y < region.y + region.height; y++) {
        for (let x = region.x; x < region.x + region.width; x++)
            cells.push(decoded[y * width + x] ?? 0);
    }
    return { source: "authored", sceneId: scene.id, resourcePath: scene.resourcePath, ...region, cells };
}
async function readWramRanges(readWram, ranges) {
    const spans = [];
    for (const range of [...ranges].sort((a, b) => a.address - b.address)) {
        const end = range.address + range.length;
        const span = spans.at(-1);
        if (span && end - span.start <= MAX_EMULATOR_INSPECTION_BYTES)
            span.end = Math.max(span.end, end);
        else
            spans.push({ start: range.address, end });
    }
    for (const span of spans)
        span.bytes = await readWram(span.start, span.end - span.start);
    return (address, length) => {
        const span = spans.find((candidate) => address >= candidate.start && address + length <= candidate.end);
        return span.bytes.subarray(address - span.start, address - span.start + length);
    };
}
function authoredActorsSelected(snapshot, selector) {
    const placed = [...snapshot.scenesById.values()].flatMap((scene) => Array.isArray(scene.actors) ? scene.actors.map((actor) => ({ actor, scene })) : []);
    const exact = placed.filter(({ actor }) => actor.id === selector || actor.symbol === selector || actor.name === selector);
    return exact.length > 0 ? exact : placed.filter(({ actor }) => lowerCase(actor.name) === selector.toLowerCase());
}
function actorIdentity(actor) {
    return { id: actor.id, name: typeof actor.name === "string" ? actor.name : "", symbol: typeof actor.symbol === "string" ? actor.symbol : null };
}
function sceneLabel(scene) {
    return scene.name || scene.symbol || scene.id;
}
function actorElsewhere(selector, placed) {
    if (placed.length === 1) {
        const [{ actor, scene }] = placed;
        return { ...actorIdentity(actor), sceneId: scene.id, unavailable: `not in the current scene (it is in ${sceneLabel(scene)})` };
    }
    return { name: selector,
        unavailable: `not in the current scene; ${placed.length} actors of other scenes match it, so select one by ID`,
        matches: placed.slice(0, MAX_ACTOR_MATCHES).map(({ actor, scene }) => ({ ...actorIdentity(actor), sceneId: scene.id, scene: sceneLabel(scene) })),
        ...(placed.length > MAX_ACTOR_MATCHES ? { moreMatches: placed.length - MAX_ACTOR_MATCHES } : {}) };
}
function variableLabel(variable) {
    return `${variable.name || variable.symbol || variable.id} (ID ${variable.id})`;
}
function boundedList(labels) {
    const shown = labels.slice(0, MAX_SOURCE_DEBUG_VARIABLES).join(", ");
    return labels.length > MAX_SOURCE_DEBUG_VARIABLES ? `${shown} and ${labels.length - MAX_SOURCE_DEBUG_VARIABLES} more` : shown || "none";
}
function lowerCase(value) {
    return typeof value === "string" ? value.toLowerCase() : undefined;
}
function shortVariableSymbol(value) {
    return lowerCase(value)?.replace(/^var_/, "");
}
const WRAM_BANKED_BASE = WRAM_BASE + 0x1000;
const LIVE_ACTOR_BYTES = 56;
const LIVE_ACTOR_SLOTS = 21;
const LIVE_SCENE_ACTORS = 20;
const MAX_ACTOR_MATCHES = 8;
const LIVE_CONTEXT_BYTES = 19;
const LIVE_CONTEXT_SLOTS = 16;
const LIVE_WINDOW_HIDDEN_Y = 144;
const LIVE_DIRECTIONS = ["down", "right", "up", "left"];
const LIVE_DIRECTION_CODES = { down: 0, right: 1, up: 2, left: 3 };
const LIVE_BUTTONS = [["right", 0x01], ["left", 0x02], ["up", 0x04], ["down", 0x08], ["a", 0x10], ["b", 0x20], ["select", 0x40], ["start", 0x80]];
const LIVE_DPAD = 0x0f;
const LIVE_OPCODES = { overlayWait: 0x44, choice: 0x48, inputWait: 0x52 };
const LIVE_UI_WAIT = { window: 1, text: 2 };
const LIVE_UI_WAIT_BUTTONS = [["a", 4, 0x10], ["b", 8, 0x20], ["any", 16, 0xff]];
const LIVE_MENU_CANCEL_B = 2;
const LIVE_SYMBOLS = {
    actors: ["_actors", LIVE_ACTOR_BYTES * LIVE_ACTOR_SLOTS],
    actorsLength: ["_actors_len", 1],
    playerMoving: ["_player_moving", 1],
    contexts: ["_CTXS", LIVE_CONTEXT_BYTES * LIVE_CONTEXT_SLOTS],
    firstContext: ["_first_ctx", 2],
    executingContext: ["_executing_ctx", 2],
    lockState: ["_vm_lock_state", 1],
    exceptionCode: ["_vm_exception_code", 1],
    windowX: ["_win_pos_x", 1],
    windowTargetX: ["_win_dest_pos_x", 1],
    windowY: ["_win_pos_y", 1],
    windowTargetY: ["_win_dest_pos_y", 1],
    textDrawn: ["_text_drawn", 1],
    joyPressed: ["_joy_pressed", 1],
    frameJoy: ["_frame_joy", 1],
    lastJoy: ["_last_joy", 1],
};
const LIVE_PLATFORM_SYMBOLS = { state: ["_plat_state", 1], velocityX: ["_plat_vel_x", 2], velocityY: ["_plat_vel_y", 2] };
const LIVE_PLATFORM_STATES = ["fall", "ground", "jump", "dash", "ladder", "wall", "knockback", "blank", "run", "float"];
function wramAddresses(definitions, symbols) {
    const addresses = {};
    for (const [key, [symbol, length]] of Object.entries(symbols)) {
        const address = definitions.get(symbol);
        if (address === undefined || address < WRAM_BASE || address + length > WRAM_BASE + 0x2000)
            return undefined;
        addresses[key] = address;
    }
    return Object.freeze(addresses);
}
function romOffset(rom, bank, address) {
    const offset = address < 0x4000 ? address : bank * 0x4000 + address - 0x4000;
    return address < 0x8000 && offset >= 0 && offset < rom.length ? offset : undefined;
}
function authoredSubpixels(value, coordinateType) {
    return typeof value === "number" && Number.isFinite(value) ? Math.floor(value * (coordinateType === "pixels" ? 32 : 256)) : undefined;
}
function naturalPathCompare(left, right) {
    const leftParts = String(left).split(/[\\/]/);
    const rightParts = String(right).split(/[\\/]/);
    for (let index = 0; index < Math.min(leftParts.length, rightParts.length); index++) {
        const leftPart = leftParts[index].replace(/\.[^.]*/, "");
        const rightPart = rightParts[index].replace(/\.[^.]*/, "");
        if (leftPart !== rightPart)
            return leftPart.localeCompare(rightPart, undefined, { numeric: true, sensitivity: "base" });
    }
    return leftParts.length - rightParts.length;
}
function compiledActorOrder(a, b) {
    return a._index < b._index ? -1 : a._index > b._index ? 1 : naturalPathCompare(a.resourcePath, b.resourcePath);
}
function compiledSceneActors(snapshot, scene, definitions, rom) {
    const sceneActors = Array.isArray(scene.actors) ? scene.actors : [];
    if (sceneActors.some((actor) => typeof actor.prefabId === "string" && actor.prefabId !== "")) {
        return { reason: `Scene ${scene.symbol} has prefab actors, whose compiled sprites this build does not map.` };
    }
    const authored = [...sceneActors].sort(compiledActorOrder).slice(0, LIVE_SCENE_ACTORS).flatMap((actor) => {
        const sprite = snapshot.assetsById.get(actor.spriteSheetId);
        return sprite?.type === "sprite" ? [{ actor, sprite }] : [];
    });
    if (authored.length === 0)
        return { actors: [] };
    const symbol = `${scene.symbol}_actors`;
    const encoded = definitions.get(`_${symbol}`);
    const bank = definitions.get(`___bank_${symbol}`);
    if (encoded === undefined || bank === undefined || Math.floor(encoded / 0x10000) !== bank) {
        return { reason: `Scene ${scene.symbol} has no compiled actor table in this build's linker sidecar.` };
    }
    const address = encoded % 0x10000;
    const identities = [];
    for (const [index, { actor, sprite }] of authored.entries()) {
        const offset = romOffset(rom, bank, address + index * LIVE_ACTOR_BYTES);
        const spriteAddress = typeof sprite.symbol === "string" ? definitions.get(`_${sprite.symbol}`) : undefined;
        const spriteBank = typeof sprite.symbol === "string" ? definitions.get(`___bank_${sprite.symbol}`) : undefined;
        const x = authoredSubpixels(actor.x, actor.coordinateType);
        const y = authoredSubpixels(actor.y, actor.coordinateType);
        const direction = LIVE_DIRECTION_CODES[actor.direction] ?? LIVE_DIRECTION_CODES.down;
        if (offset === undefined || offset + LIVE_ACTOR_BYTES > rom.length || spriteAddress === undefined || spriteBank === undefined
            || rom.readUInt16LE(offset + 1) !== x || rom.readUInt16LE(offset + 3) !== y || rom[offset + 5] !== direction
            || rom[offset + 38] !== spriteBank || rom.readUInt16LE(offset + 39) !== spriteAddress % 0x10000) {
            return { reason: `Scene ${scene.symbol}'s compiled actors do not match its authored actors in order.` };
        }
        identities.push(`${actor._index}:${x}:${y}:${direction}:${sprite.symbol}`);
    }
    return {
        actors: authored.map(({ actor }, index) => ({
            id: actor.id,
            name: typeof actor.name === "string" ? actor.name : "",
            symbol: typeof actor.symbol === "string" ? actor.symbol : null,
            slot: index + 1,
            ...(identities.indexOf(identities[index]) !== identities.lastIndexOf(identities[index]) ? { ambiguous: true } : {}),
        })),
    };
}
function liveActor(bytes, slot) {
    const offset = slot * LIVE_ACTOR_BYTES;
    const flags = bytes[offset];
    const x = bytes.readUInt16LE(offset + 1);
    const y = bytes.readUInt16LE(offset + 3);
    const animation = bytes[offset + 20];
    return { slot, x: x >> 8, y: y >> 8, pixelX: x >> 5, pixelY: y >> 5,
        direction: LIVE_DIRECTIONS[bytes[offset + 5]] ?? "none",
        moving: animation >= 4 && animation < 8,
        moveSpeed: bytes[offset + 19] / 32,
        active: (flags & 0x20) !== 0,
        hidden: (flags & 0x02) !== 0 };
}
function livePlayer(read, live, actorBytes, sceneType, locked) {
    const player = liveActor(actorBytes, 0);
    if (sceneType !== "PLATFORM")
        return { ...player, moving: player.moving || read(live.addresses.playerMoving, 1)[0] !== 0 };
    if (live.platform === undefined)
        return { ...player, moving: null };
    const state = LIVE_PLATFORM_STATES[read(live.platform.state, 1)[0]] ?? "unknown";
    const velocityX = read(live.platform.velocityX, 2).readInt16LE(0);
    const velocityY = read(live.platform.velocityY, 2).readInt16LE(0);
    const grounded = state === "ground" || state === "run";
    return { ...player,
        moving: !locked && (velocityX !== 0 || (!grounded && velocityY !== 0)),
        platform: { state, velocityX: (velocityX >> 8) / 16, velocityY: (velocityY >> 8) / 16 } };
}
function buttonNames(mask) {
    return LIVE_BUTTONS.filter(([, bit]) => (mask & bit) !== 0).map(([name]) => name);
}
function scriptByte(rom, context, delta) {
    const offset = romOffset(rom, context.bank, context.pc + delta);
    return offset === undefined ? undefined : rom[offset];
}
function modalHandler(rom, context) {
    const at = (delta) => scriptByte(rom, context, delta);
    if (at(-5) === LIVE_OPCODES.choice && at(-4) > 0)
        return { kind: "menu", count: at(-4), cancelB: (at(-3) & LIVE_MENU_CANCEL_B) !== 0 };
    if (at(-3) === LIVE_OPCODES.overlayWait && at(-1) === 1)
        return { kind: "overlay", flags: at(-2), modal: true };
    return undefined;
}
function pendingWait(rom, context) {
    const at = (delta) => scriptByte(rom, context, delta);
    if (at(0) === LIVE_OPCODES.overlayWait && at(2) === 0)
        return { kind: "overlay", flags: at(1), modal: false };
    if (at(0) === LIVE_OPCODES.inputWait)
        return { kind: "input", mask: at(1) };
    return undefined;
}
function liveScripts(read, addresses, rom) {
    const contextBytes = read(addresses.contexts, LIVE_CONTEXT_BYTES * LIVE_CONTEXT_SLOTS);
    const executing = read(addresses.executingContext, 2).readUInt16LE(0);
    const locked = read(addresses.lockState, 1)[0] !== 0;
    const joyPressed = read(addresses.joyPressed, 1)[0];
    const frameJoy = read(addresses.frameJoy, 1)[0];
    const lastJoy = read(addresses.lastJoy, 1)[0];
    const windowY = read(addresses.windowY, 1)[0];
    const overlayOpen = windowY < LIVE_WINDOW_HIDDEN_Y;
    const windowArrived = read(addresses.windowX, 1)[0] === read(addresses.windowTargetX, 1)[0] && windowY === read(addresses.windowTargetY, 1)[0];
    const textDrawn = read(addresses.textDrawn, 1)[0] !== 0;
    const contexts = [];
    for (let pointer = read(addresses.firstContext, 2).readUInt16LE(0); pointer !== 0 && contexts.length < LIVE_CONTEXT_SLOTS;) {
        const index = (pointer - addresses.contexts) / LIVE_CONTEXT_BYTES;
        if (!Number.isInteger(index) || index < 0 || index >= LIVE_CONTEXT_SLOTS)
            break;
        const offset = index * LIVE_CONTEXT_BYTES;
        contexts.push({ pointer, pc: contextBytes.readUInt16LE(offset), bank: contextBytes[offset + 2], waitable: contextBytes[offset + 16] !== 0 });
        pointer = contextBytes.readUInt16LE(offset + 3);
    }
    const active = contexts.find((context) => context.pointer === executing && !context.waitable);
    const modal = active === undefined ? undefined : modalHandler(rom, active);
    let waits;
    if (modal?.kind === "menu") {
        const choosing = (joyPressed & LIVE_DPAD) === 0 && ((joyPressed & 0x10) !== 0 || (modal.cancelB && (joyPressed & 0x20) !== 0));
        waits = choosing ? [] : [modal];
    }
    else if (modal) {
        waits = [modal];
    }
    else if (executing !== 0 && !locked) {
        waits = [];
    }
    else {
        waits = contexts.filter((context) => context.waitable && (!locked || context.pointer === executing)).map((context) => pendingWait(rom, context)).filter(Boolean);
    }
    const buttons = new Set();
    let dialogue;
    let menuOptions;
    for (const wait of waits) {
        if (wait.kind === "menu") {
            dialogue = "menu";
            menuOptions = wait.count;
            buttons.add("a");
            if (wait.cancelB)
                buttons.add("b");
        }
        else if (wait.kind === "input") {
            if (frameJoy === lastJoy || (frameJoy & wait.mask) === 0)
                buttonNames(wait.mask).forEach((button) => buttons.add(button));
        }
        else {
            const waited = LIVE_UI_WAIT_BUTTONS.filter(([, flag]) => (wait.flags & flag) !== 0);
            const ready = (!(wait.flags & LIVE_UI_WAIT.text) || textDrawn) && (!(wait.flags & LIVE_UI_WAIT.window) || windowArrived);
            if (waited.length === 0 || !ready) {
                dialogue ??= "drawing";
            }
            else if (wait.modal || !waited.every(([, , mask]) => (joyPressed & mask) !== 0)) {
                if (dialogue !== "menu")
                    dialogue = "waiting";
                waited.forEach(([button]) => buttons.add(button));
            }
        }
    }
    return { ui: { overlayOpen,
            dialogue: dialogue ?? (!textDrawn ? "drawing" : overlayOpen ? "unknown" : "none"),
            ...(menuOptions === undefined ? {} : { menuOptions }),
            waitingForInput: buttons.size > 0,
            buttons: [...buttons] },
        scripts: { running: contexts.length, locked } };
}
function liveStateMapping(receipt, snapshot, definitions, rom, scenes) {
    if (receipt.artifacts.liveStateLayout !== LIVE_STATE_LAYOUT) {
        return { reason: "Live actor, dialogue and script state is unavailable: this build's engine files differ from the GB Studio engine it is read against." };
    }
    const addresses = wramAddresses(definitions, LIVE_SYMBOLS);
    if (addresses === undefined) {
        return { reason: "Live actor, dialogue and script state is unavailable: this build's linker sidecar lacks the engine symbols it reads." };
    }
    const actorsByScene = new Map(scenes.map(({ id }) => [id, compiledSceneActors(snapshot, snapshot.scenesById.get(id), definitions, rom)]));
    return { rom, addresses, platform: wramAddresses(definitions, LIVE_PLATFORM_SYMBOLS), actorsByScene };
}
export class SourceDebugContext {
    identity;
    projectPath;
    #receipt;
    #snapshot;
    #manifest;
    #variables;
    #unavailable;
    #limitations;
    #access;
    #live;
    constructor(receipt, snapshot, manifest, unavailable, limitations, access, live) {
        this.#receipt = receipt;
        this.#snapshot = snapshot;
        this.#manifest = manifest;
        this.#variables = new Map((manifest.variables ?? []).map((variable) => [variable.variableId, variable]));
        this.#unavailable = unavailable;
        this.#limitations = limitations;
        this.#access = access;
        this.#live = live;
        this.projectPath = receipt.source.projectPath;
        this.identity = Object.freeze({ romSha256: manifest.romSha256, projectRevision: manifest.projectRevision,
            sourceFingerprint: receipt.source.sourceFingerprint, compilerSha256: receipt.source.compilerSha256,
            engineAbiVersion: manifest.engineAbiVersion });
    }
    static async create(options) {
        const receipt = authenticatedSourceBuild(options.build);
        if (!receipt)
            fail("SOURCE_DEBUG_UNAVAILABLE", "Source debugging requires a successful official captureDebugArtifacts build retained by this MCP session. A supplied ROM or copied manifest is ROM-only.");
        if (!receipt.abi)
            fail("SOURCE_DEBUG_ABI_UNSUPPORTED", receipt.artifacts.sourceDebugUnavailableReason ?? "The same-build engine layout is unsupported for source debugging.");
        if (options.projectPath && !samePath(await realpath(path.resolve(path.dirname(receipt.source.projectPath), options.projectPath)), receipt.source.projectPath)) {
            fail("SOURCE_DEBUG_PROJECT_MISMATCH", "The captured build belongs to a different selected project.");
        }
        if (options.access) {
            if (!samePath(options.access.projectPath, receipt.source.projectPath))
                fail("SOURCE_DEBUG_PROJECT_MISMATCH", "The selected world index belongs to a different project.");
            await options.access.strongRefresh();
        }
        const snapshot = await loadProjectSnapshot(receipt.source.projectPath, {}, options.access);
        if (snapshot.inventory.scenes.length !== snapshot.scenesById.size || snapshot.counts.variables !== snapshot.variablesById.size) {
            fail("SOURCE_DEBUG_SYMBOLS_UNAVAILABLE", "Authored scenes or global variables have missing or duplicate IDs; source-debug mappings would be ambiguous.");
        }
        const current = await captureBuildSourceProvenance(receipt.source.projectPath, receipt.compilerPath);
        if (snapshot.revision !== receipt.source.projectRevision || !sameBuildSourceProvenance(receipt.source, current)) {
            fail("SOURCE_DEBUG_STALE_SOURCE", "Authored sources or project plugins changed after this build. Rebuild before enabling source-aware debugging.");
        }
        const root = path.dirname(receipt.source.projectPath);
        const [rom, noi, globals] = await Promise.all([
            authenticatedFile(root, receipt.outputPath, receipt.artifacts.romSha256),
            authenticatedFile(root, receipt.artifacts.noiPath, receipt.artifacts.noiSha256),
            authenticatedFile(root, receipt.artifacts.globalsPath, receipt.artifacts.globalsSha256),
        ]);
        const definitions = parseNoiDefinitions(noi.toString("utf8"));
        const globalDefinitions = parseGlobalsDefinitions(globals.toString("utf8"));
        const scenes = [];
        let unavailableScenes = 0;
        for (const scene of snapshot.scenesById.values()) {
            if (typeof scene.symbol !== "string" || !SCENE_SYMBOL.test(scene.symbol)
                || !definitions.has(`_${scene.symbol}`) || !definitions.has(`___bank_${scene.symbol}`)) {
                unavailableScenes++;
                continue;
            }
            scenes.push({ id: scene.id, symbol: scene.symbol });
        }
        if (scenes.length === 0)
            fail("SOURCE_DEBUG_SYMBOLS_UNAVAILABLE", "No exact authored scene symbols occur in this build's linker sidecar.");
        const variables = [];
        const unavailable = [];
        for (const variable of snapshot.variablesById.values()) {
            if (typeof variable.symbol !== "string" || !VARIABLE_SYMBOL.test(variable.symbol)) {
                unavailable.push(variableSummary(variable, "No supported exact authored variable symbol."));
            }
            else if (!globalDefinitions.has(variable.symbol.toUpperCase())) {
                unavailable.push(variableSummary(variable, "Not allocated in this build's globals.i; it may be unused or optimized out."));
            }
            else
                variables.push({ id: variable.id, symbol: variable.symbol });
        }
        const engineAbiVersion = `${receipt.abi.layout}:${receipt.abi.sha256}`;
        const manifest = createDebugManifest({ rom, noi: noi.toString("utf8"), globals: globals.toString("utf8"),
            scenes, variables, projectRevision: receipt.source.projectRevision, engineAbiVersion, globalHeapWords: receipt.globalHeapWords });
        validateDebugManifest(manifest, rom, { projectRevision: receipt.source.projectRevision, engineAbiVersion, globalHeapWords: receipt.globalHeapWords });
        const limitations = ["Authored collision grids and event references describe source, not the currently executing VM instruction or dynamically modified collision state."];
        if (unavailableScenes)
            limitations.push(`${unavailableScenes} authored scene(s) have no exact compiled mapping in this build.`);
        if (!options.access)
            limitations.push("Authored event links require the selected project's existing world index.");
        return new SourceDebugContext(receipt, snapshot, manifest, unavailable, limitations, options.access, liveStateMapping(receipt, snapshot, definitions, rom, scenes));
    }
    async #validateSource() {
        let current;
        try {
            current = await captureBuildSourceProvenance(this.projectPath, this.#receipt.compilerPath);
        }
        catch {
            fail("SOURCE_DEBUG_STALE_SOURCE", "The source or compiler identity is no longer readable. Rebuild before using source-aware debugging.");
        }
        if (!sameBuildSourceProvenance(this.#receipt.source, current)) {
            fail("SOURCE_DEBUG_STALE_SOURCE", "Authored sources, project plugins, or the compiler changed after this build. Rebuild before using source-aware debugging.");
        }
    }
    /** Called when source mode is explicitly enabled for a worker-authenticated ROM. */
    async assertCompatibleRom(romSha256) {
        if (typeof romSha256 !== "string" || romSha256 !== this.identity.romSha256) {
            fail("SOURCE_DEBUG_ROM_MISMATCH", "The running emulator does not contain the exact ROM bytes from this source-debug build.");
        }
        await this.#validateSource();
        const root = path.dirname(this.projectPath);
        await Promise.all([
            authenticatedFile(root, this.#receipt.outputPath, this.#receipt.artifacts.romSha256),
            authenticatedFile(root, this.#receipt.artifacts.noiPath, this.#receipt.artifacts.noiSha256),
            authenticatedFile(root, this.#receipt.artifacts.globalsPath, this.#receipt.artifacts.globalsSha256),
        ]);
    }
    #selectedVariables(query) {
        const ids = query.variableIds ?? [];
        const names = query.variableNames ?? [];
        if (!Array.isArray(ids) || !Array.isArray(names) || ids.length + names.length > MAX_SOURCE_DEBUG_VARIABLES
            || [...ids, ...names].some((value) => !validSelector(value))) {
            fail("SOURCE_DEBUG_INVALID_QUERY", `Select at most ${MAX_SOURCE_DEBUG_VARIABLES} variables by bounded ID, name or symbol.`);
        }
        if (query.variableIds === undefined && query.variableNames === undefined) {
            const available = [...this.#variables.keys()];
            return { ids: available.slice(0, MAX_SOURCE_DEBUG_VARIABLES), truncated: available.length > MAX_SOURCE_DEBUG_VARIABLES };
        }
        const selected = new Set(ids);
        for (const name of names) {
            const matches = this.#variablesNamed(name);
            if (matches.length > 1)
                fail("SOURCE_DEBUG_VARIABLE_UNAVAILABLE", `Variable name ${JSON.stringify(name)} is ambiguous; select one by ID: ${boundedList(matches.map(variableLabel))}.`);
            if (matches.length === 0)
                fail("SOURCE_DEBUG_VARIABLE_UNAVAILABLE", `No authored variable is named ${JSON.stringify(name)}. Authored variables: ${this.#authoredVariables()}.`);
            selected.add(matches[0].id);
        }
        for (const id of selected) {
            if (!this.#variables.has(id)) {
                const unavailable = this.#unavailable.find((variable) => variable.id === id);
                fail("SOURCE_DEBUG_VARIABLE_UNAVAILABLE", unavailable ? `${unavailable.name || id}: ${unavailable.reason}` : `No authored global variable with ID ${JSON.stringify(id)} exists in this build. Authored variables: ${this.#authoredVariables()}.`);
            }
        }
        return { ids: [...selected], truncated: false };
    }
    #variablesNamed(selector) {
        const variables = [...this.#snapshot.variablesById.values()];
        const folded = selector.toLowerCase();
        const tiers = [
            (variable) => variable.name === selector || variable.symbol === selector,
            (variable) => lowerCase(variable.name) === folded || lowerCase(variable.symbol) === folded,
            (variable) => shortVariableSymbol(variable.symbol) === shortVariableSymbol(selector),
        ];
        for (const matches of tiers) {
            const found = variables.filter(matches);
            if (found.length > 0)
                return found;
        }
        return [];
    }
    #authoredVariables() {
        return boundedList([...this.#snapshot.variablesById.values()].map(variableLabel));
    }
    #liveActorSelection(query, sceneId) {
        if (query.actors === undefined || this.#live.reason !== undefined)
            return undefined;
        const mapping = this.#live.actorsByScene.get(sceneId);
        const unmapped = mapping === undefined || mapping.reason !== undefined ? mapping?.reason ?? "The current scene has no compiled actor mapping in this build." : undefined;
        if (unmapped !== undefined && (sceneId === undefined || query.actors === "all"))
            return { unavailable: unmapped };
        const ambiguous = mapping?.actors.filter((actor) => actor.ambiguous) ?? [];
        const ambiguity = ambiguous.length === 0 ? undefined : `Actors ${boundedList(ambiguous.map(variableLabel))} share an _index, start position, direction and sprite, so their runtime slots cannot be told apart.`;
        if (query.actors === "all")
            return { sceneActors: mapping.actors.length, actors: mapping.actors.filter((actor) => !actor.ambiguous), ...(ambiguity ? { limitation: ambiguity } : {}) };
        const actors = query.actors.map((selector) => this.#selectedActor(selector, sceneId, unmapped === undefined ? mapping : undefined, ambiguity));
        return unmapped === undefined ? { sceneActors: mapping.actors.length, actors } : { unavailable: unmapped, actors };
    }
    /** Finds the actor in the authored project first, so one in another scene is reported even when the current scene's live slots are not mapped (mapping is then undefined). */
    #selectedActor(selector, sceneId, mapping, ambiguity) {
        const placed = authoredActorsSelected(this.#snapshot, selector);
        const here = placed.filter(({ scene }) => scene.id === sceneId);
        if (placed.length === 0) {
            const sceneActors = this.#snapshot.scenesById.get(sceneId)?.actors;
            const known = boundedList((Array.isArray(sceneActors) ? sceneActors : []).map((actor) => variableLabel(actorIdentity(actor))));
            fail("SOURCE_DEBUG_ACTOR_UNAVAILABLE", `No scene has an actor ${JSON.stringify(selector)}. The current scene's actors: ${known}; the player is always reported.`);
        }
        if (here.length === 0)
            return actorElsewhere(selector, placed);
        if (here.length > 1)
            fail("SOURCE_DEBUG_ACTOR_UNAVAILABLE", `Actor name ${JSON.stringify(selector)} is ambiguous in the current scene; select one by ID: ${boundedList(here.map(({ actor }) => variableLabel(actorIdentity(actor))))}.`);
        const authored = actorIdentity(here[0].actor);
        if (mapping === undefined)
            return authored;
        const mapped = mapping.actors.find((actor) => actor.id === authored.id);
        if (mapped === undefined)
            return { ...authored, unavailable: `not read live (only the current scene's first ${LIVE_SCENE_ACTORS} actors with a sprite are)` };
        if (mapped.ambiguous)
            fail("SOURCE_DEBUG_ACTOR_UNAVAILABLE", ambiguity);
        return mapped;
    }
    #readLive(read, selection, sceneType) {
        const { addresses, rom } = this.#live;
        const scripts = liveScripts(read, addresses, rom);
        if (read(addresses.exceptionCode, 1)[0] !== 0 && read(addresses.firstContext, 2).readUInt16LE(0) === 0) {
            return { live: { sceneLoading: true, ...scripts }, limitations: ["The scene is still loading, so the player and actors are withheld; step a few frames and retry."] };
        }
        const actorBytes = read(addresses.actors, LIVE_ACTOR_BYTES * LIVE_ACTOR_SLOTS);
        const player = livePlayer(read, this.#live, actorBytes, sceneType, scripts.scripts.locked);
        let unavailable = selection?.unavailable;
        if (selection !== undefined && unavailable === undefined && read(addresses.actorsLength, 1)[0] !== Math.min(selection.sceneActors + 1, LIVE_ACTOR_SLOTS)) {
            unavailable = "The loaded actors do not match the current scene yet; step a few frames and retry.";
        }
        const reported = unavailable === undefined ? selection?.actors : selection.actors?.filter((actor) => actor.unavailable !== undefined);
        const actors = reported === undefined || (unavailable !== undefined && reported.length === 0) ? undefined
            : reported.map((actor) => actor.unavailable !== undefined ? actor : { id: actor.id, name: actor.name, symbol: actor.symbol, ...liveActor(actorBytes, actor.slot) });
        return { live: { sceneLoading: false, player, ...(actors ? { actors } : {}), ...scripts },
            limitations: [...(unavailable ? [unavailable] : []), ...(selection?.limitation ? [selection.limitation] : [])] };
    }
    async inspect(emulator, query = {}) {
        if (!query || typeof query !== "object" || (query.includeScene !== undefined && typeof query.includeScene !== "boolean")) {
            fail("SOURCE_DEBUG_INVALID_QUERY", "Source debugging requires a bounded query.");
        }
        if (query.actors !== undefined && query.actors !== "all" && (!Array.isArray(query.actors) || query.actors.length < 1
            || query.actors.length > LIVE_SCENE_ACTORS || !query.actors.every(validSelector))) {
            fail("SOURCE_DEBUG_INVALID_QUERY", `Select "all" actors or 1 to ${LIVE_SCENE_ACTORS} by name, ID or symbol.`);
        }
        const full = query.detail === "full";
        const referenceLimit = query.referenceLimit ?? (full ? 16 : 0);
        if (!Number.isInteger(referenceLimit) || referenceLimit < 0 || referenceLimit > MAX_SOURCE_DEBUG_REFERENCES) {
            fail("SOURCE_DEBUG_INVALID_QUERY", `referenceLimit must be between 0 and ${MAX_SOURCE_DEBUG_REFERENCES}.`);
        }
        const selected = this.#selectedVariables(query);
        const initial = await emulator.status();
        await this.assertCompatibleRom(initial.romSha256 ?? "");
        if (initial.paused !== true)
            fail("SOURCE_DEBUG_REQUIRES_PAUSE", "Pause the emulator before reading a coherent source-debug snapshot.");
        const readBank = async (address, length, bank) => {
            const offset = address - (bank === 1 ? WRAM_BANKED_BASE : WRAM_BASE);
            const result = await emulator.inspect({ view: "memory", region: "wram", offset, length, ...(bank === undefined ? {} : { bank }) });
            if (result.frame !== initial.frame)
                fail("SOURCE_DEBUG_FRAME_CHANGED", "The emulator advanced during source inspection; pause and retry.");
            if (result.view !== "memory" || result.region !== "wram" || result.offset !== offset
                || result.length !== length || result.bank !== bank || !new RegExp(`^[a-fA-F0-9]{${length * 2}}$`).test(result.hex)) {
                fail("SOURCE_DEBUG_INVALID_MEMORY", "The emulator did not return the exact bounded WRAM bytes requested by authenticated symbols.");
            }
            return Buffer.from(result.hex, "hex");
        };
        const readWram = async (address, length) => {
            if (initial.cgb !== true)
                return readBank(address, length);
            const split = Math.min(Math.max(address, WRAM_BANKED_BASE), address + length);
            return Buffer.concat([
                ...(split > address ? [await readBank(address, split - address, 0)] : []),
                ...(address + length > split ? [await readBank(split, address + length - split, 1)] : []),
            ]);
        };
        let scene;
        let authoredScene;
        const sceneRequired = query.includeScene !== false || query.collisions || query.actors !== undefined;
        if (sceneRequired || this.#live.reason === undefined) {
            try {
                const mapping = decodeCurrentScene(this.#manifest, await readWram(this.#manifest.currentSceneAddress, 3));
                authoredScene = this.#snapshot.scenesById.get(mapping.sceneId);
                scene = sourceScene(authoredScene, mapping.sceneSymbol);
            }
            catch (error) {
                if (sceneRequired || !(error instanceof DebugSymbolsError))
                    throw error;
            }
        }
        const actorSelection = this.#liveActorSelection(query, scene?.id);
        const mappings = selected.ids.map((id) => this.#variables.get(id));
        const liveSymbols = this.#live.reason !== undefined ? [] : [[LIVE_SYMBOLS, this.#live.addresses], ...(authoredScene?.type === "PLATFORM" && this.#live.platform ? [[LIVE_PLATFORM_SYMBOLS, this.#live.platform]] : [])];
        const liveRanges = liveSymbols.flatMap(([symbols, addresses]) => Object.entries(symbols).map(([key, [, length]]) => ({ address: addresses[key], length })));
        const read = await readWramRanges(readWram, [...mappings.map((mapping) => ({ address: mapping.address, length: 2 })), ...liveRanges]);
        const values = new Map();
        for (const mapping of mappings) {
            const resource = this.#snapshot.variablesById.get(mapping.variableId);
            const bytes = read(mapping.address, 2);
            values.set(resource.id, { id: resource.id, variableId: resource.id, name: resource.name,
                symbol: mapping.variableSymbol, value: bytes.readInt16LE(0), unsignedValue: bytes.readUInt16LE(0),
                resourcePath: resource.resourcePath });
        }
        const live = this.#live.reason === undefined ? this.#readLive(read, actorSelection, authoredScene?.type) : undefined;
        const references = [];
        let referencesTruncated = false;
        if (this.#access && referenceLimit > 0) {
            await this.#access.strongRefresh();
            if (this.#access.revision !== this.identity.projectRevision)
                fail("SOURCE_DEBUG_STALE_SOURCE", "The selected project changed during source inspection.");
            const seen = new Set();
            const nodes = [...selected.ids.map((id) => ({ type: "variable", id })), ...(scene ? [{ type: "scene", id: scene.id }] : [])];
            for (const node of nodes) {
                if (references.length >= referenceLimit) {
                    referencesTruncated = true;
                    break;
                }
                const related = await worldDependencies(this.#access, { node, direction: "both", depth: 1, limit: referenceLimit });
                for (const reference of related.references) {
                    const key = JSON.stringify(reference);
                    if (seen.has(key))
                        continue;
                    seen.add(key);
                    if (references.length >= referenceLimit) {
                        referencesTruncated = true;
                        break;
                    }
                    references.push(reference);
                }
                if (related.nextCursor)
                    referencesTruncated = true;
            }
        }
        const collisions = query.collisions && authoredScene ? collisionRegion(authoredScene, query.collisions) : undefined;
        await this.#validateSource();
        const final = await emulator.status();
        if (final.romSha256 !== this.identity.romSha256)
            fail("SOURCE_DEBUG_ROM_MISMATCH", "The emulator ROM changed during source inspection.");
        if (final.paused !== true || final.frame !== initial.frame)
            fail("SOURCE_DEBUG_FRAME_CHANGED", "The emulator advanced during source inspection; pause and retry.");
        const limitations = [...(full ? this.#limitations : []), ...(live ? live.limitations : [this.#live.reason])];
        const result = { mode: "source", ...(full ? { identity: this.identity } : {}), frame: initial.frame,
            ...(scene && query.includeScene !== false ? { scene } : {}), ...(live ? { live: live.live } : {}), variables: selected.ids.map((id) => values.get(id)),
            variablesTruncated: selected.truncated, unavailableVariables: this.#unavailable.slice(0, MAX_SOURCE_DEBUG_VARIABLES),
            unavailableVariableCount: this.#unavailable.length, ...(collisions ? { collisions } : {}), references, referencesTruncated,
            ...(limitations.length > 0 ? { limitations } : {}) };
        while (Buffer.byteLength(JSON.stringify(result)) > PROJECT_RESPONSE_LIMITS.semanticQueryBytes && result.references.length > 0) {
            result.references.pop();
            result.referencesTruncated = true;
        }
        while (Buffer.byteLength(JSON.stringify(result)) > PROJECT_RESPONSE_LIMITS.semanticQueryBytes && result.unavailableVariables.length > 0) {
            result.unavailableVariables.pop();
        }
        if (Buffer.byteLength(JSON.stringify(result)) > PROJECT_RESPONSE_LIMITS.semanticQueryBytes) {
            fail("SOURCE_DEBUG_RESPONSE_TOO_LARGE", "Source diagnostics exceed the bounded response size; request fewer variables or a smaller collision window.");
        }
        return result;
    }
}
export async function createSourceDebugContext(options) {
    return SourceDebugContext.create(options);
}
