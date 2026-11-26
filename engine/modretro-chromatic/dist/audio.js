import { readdir, readFile, open, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { projectRelativePath, resolveProjectPath, projectPathExists, readProjectJson, writeProjectBytesAtomic, writeProjectJsonAtomic, stableResourceId, resourceSlug } from "./project-files.js";
import { GameStudioProjectError, inventoryProject } from "./project.js";
import { RESOURCE_ID, isSystemError, assetError, assertDistributedProject, ensureName } from "./assets.js";

const AUDIO_FORMATS = {
    // The spellings GB Studio's loaders find (loadMusicData, loadSoundData): their globs match an all-lowercase or
    // all-uppercase extension and skip dot names; a .UGE is typed as a module, so it is not importable.
    music: { folder: "music", prefix: "song", extensions: [".uge", ".mod", ".MOD"], discovered: [".uge", ".UGE", ".mod", ".MOD"] },
    sound: {
        folder: "sounds",
        prefix: "sound",
        extensions: [".wav", ".WAV", ".vgm", ".VGM", ".vgz", ".VGZ"],
        discovered: [".wav", ".WAV", ".vgm", ".VGM", ".vgz", ".VGZ", ".sav", ".SAV"]
    }
};
const AUDIO_TYPES = new Map([[".uge", "uge"], [".mod", "mod"], [".wav", "wav"], [".vgm", "vgm"], [".vgz", "vgm"]]);
const MAX_AUDIO_BYTES = 4 * 1024 * 1024;
const MAX_BANK_BYTES = 16384;
const GB_FRAMES_PER_SECOND = 4194304 / 70224;
export const BUNDLED_TRACKS = ["bright-start", "meadow-walk", "cave-echo", "victory-lap"];
const BUNDLED_MUSIC = fileURLToPath(new URL("../assets/music/", import.meta.url));
export function isAudioKind(kind) {
    return kind === "music" || kind === "sound";
}
function audioDestination(root, assetPath, kind) {
    const format = AUDIO_FORMATS[kind];
    if (!assetPath || !format.extensions.includes(path.extname(assetPath))) {
        assetError("INVALID_ASSET_PATH", `A ${kind} destination must name a ${format.extensions.join(", ")} file; GB Studio skips or misreads other spellings.`);
    }
    const folder = path.join(root, "assets", format.folder);
    const destination = path.resolve(root, assetPath);
    const relative = path.relative(folder, destination);
    if (!relative || relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
        assetError("INVALID_ASSET_PATH", `A ${kind} destination must remain inside assets/${format.folder}.`, destination);
    }
    if (relative.split(path.sep).some((part) => part.startsWith("."))) {
        assetError("INVALID_ASSET_PATH", `GB Studio does not load a file or folder whose name starts with a dot (${relative}).`, destination);
    }
    return { folder, destination, type: AUDIO_TYPES.get(path.extname(assetPath).toLowerCase()) };
}
// The destination as the disk spells it. On a case-insensitive disk an existing file or folder answers to any
// spelling, and the sidecar must name the one GB Studio finds on a case-sensitive one.
async function onDiskSpelling(root, folder, destination) {
    const parts = path.relative(folder, destination).split(path.sep);
    let current = folder;
    for (const [index, part] of parts.entries()) {
        const entries = await readdir(current).catch((error) => {
            if (isSystemError(error, "ENOENT"))
                return undefined;
            throw error;
        });
        if (entries === undefined || !entries.includes(part) && !await projectPathExists(root, path.join(current, part))) {
            return path.join(current, ...parts.slice(index));
        }
        const folded = part.normalize("NFC").toLowerCase();
        current = path.join(current, entries.includes(part) ? part : entries.find((entry) => entry.normalize("NFC").toLowerCase() === folded) ?? part);
    }
    return current;
}
async function readBoundedAudio(root, filename) {
    const safePath = await resolveProjectPath(root, filename, { mustExist: true });
    const handle = await open(safePath, "r");
    try {
        const info = await handle.stat();
        if (!info.isFile())
            assetError("INVALID_ASSET", "An audio asset must be a regular file.", safePath);
        if (info.size > MAX_AUDIO_BYTES)
            assetError("ASSET_TOO_LARGE", `Audio files are limited to ${MAX_AUDIO_BYTES} bytes.`, safePath);
        return await handle.readFile();
    } finally {
        await handle.close();
    }
}
function audioFormatError(type, message) {
    assetError("INVALID_AUDIO", `Not a usable ${type} file: ${message}`);
}
const UGE_NOTES = 72;
const UGE_NO_NOTE = 90;
// Compiled sizes from GB Studio's exportToC and hUGEDriver.h: a pattern row is DN(note, instrument, effect), three
// bytes; an instrument is six; a subpattern is 32 rows; the waves are 16 of 16 bytes; the song header is 21 bytes.
const UGE_PATTERN_BYTES = 64 * 3;
const UGE_SUBPATTERN_BYTES = 32 * 3;
const UGE_INSTRUMENT_BYTES = 6;
const UGE_FIXED_BYTES = 16 * 16 + 21 + 1;
// Walks a .uge as GB Studio's loadUGESong reads it and counts the bytes exportToC compiles into the song's one bank.
function inspectUge(bytes) {
    let offset = 0;
    const need = (count) => {
        if (offset + count > bytes.length)
            throw new Error("the file ends early.");
    };
    const u8 = () => (need(1), bytes[offset++]);
    const u32 = () => (need(4), offset += 4, bytes.readUInt32LE(offset - 4));
    const i32 = () => (need(4), offset += 4, bytes.readInt32LE(offset - 4));
    const skip = (count) => (need(count), offset += count);
    const text = () => {
        need(256);
        const value = bytes.subarray(offset + 1, offset + 1 + Math.min(bytes[offset], 255)).toString("utf8");
        offset += 256;
        return value;
    };
    const version = u32();
    if (version > 6)
        throw new Error(`UGE version ${version} is newer than GB Studio reads (6).`);
    const name = text();
    text();
    text();
    const instruments = [];
    for (let index = 0; index < (version < 3 ? 15 : 45); index++) {
        const type = u32();
        if (type > 2)
            throw new Error(`instrument ${index} has an unknown type ${type}.`);
        skip(256 + 4 + 1 + 1 + 4 + 1 + 4 + 4 + 4 + 1 + 4 + 4);
        let subpattern = null;
        if (version >= 6) {
            skip(4);
            const enabled = u8();
            const rows = Array.from({ length: 64 }, () => {
                const note = u32();
                skip(4);
                return [note, u32(), u32(), u8()].join(",");
            });
            subpattern = enabled ? rows.join(";") : null;
        } else {
            skip(12);
            if (version >= 4) {
                need(6);
                subpattern = type === 2 ? `macro:${bytes.subarray(offset, offset + 6).toString("hex")}` : null;
                offset += 6;
            }
        }
        instruments.push({ type, subpattern });
    }
    skip(16 * (version < 3 ? 33 : 32));
    const ticksPerRow = u32();
    if (version >= 6)
        skip(5);
    const patternCount = u32();
    if (offset + patternCount * 13 * 64 > bytes.length)
        throw new Error(`it claims ${patternCount} patterns, more than the file holds.`);
    const patterns = new Map();
    for (let index = 0; index < patternCount; index++) {
        const id = version >= 5 ? u32() : index;
        const rows = [];
        for (let row = 0; row < 64; row++) {
            const note = i32(), instrument = i32();
            if (version >= 6)
                skip(4);
            const effectCode = i32(), effectParam = u8();
            if (note !== UGE_NO_NOTE && (note < 0 || note >= UGE_NOTES))
                throw new Error(`pattern ${id} row ${row} plays note ${note}; GB Studio compiles notes 0–71 (C3–B8) only.`);
            if (instrument < 0 || instrument > 15 || effectCode < 0 || effectCode > 15)
                throw new Error(`pattern ${id} row ${row} names instrument ${instrument} or effect ${effectCode}; both run 0–15.`);
            rows.push({ note, instrument, cell: `${note},${instrument},${effectCode},${effectParam}` });
        }
        // GB Studio 3.0.2 and earlier saved version 5 songs without unique pattern IDs; the loader keeps a repeat in its own slot.
        patterns.set(version === 5 && patterns.has(id) ? index : id, rows);
    }
    const orders = [];
    for (let track = 0; track < 4; track++) {
        const count = u32();
        if (count < 2)
            throw new Error("a channel has no pattern order.");
        need(4 * count);
        orders.push(Array.from({ length: count - 1 }, (_, index) => bytes.readUInt32LE(offset + 4 * index)));
        offset += 4 * count;
    }
    const length = orders[0].length;
    if (orders.some((order) => order.length < length))
        throw new Error("a channel's order is shorter than the first channel's.");
    const slots = patterns.size === 0 ? 0 : Math.max(...patterns.keys()) + 1;
    const sequence = orders.map((order) => order.slice(0, length));
    const missing = sequence.flat().find((pattern) => pattern >= slots);
    if (missing !== undefined)
        throw new Error(`the order names pattern ${missing}, which the file does not hold.`);
    const emptyPattern = Array(64).fill(`${UGE_NO_NOTE},0,0,0`).join(";");
    const compiled = new Set();
    for (const block of new Set(sequence.flat().map((pattern) => Math.floor(pattern / 4)))) {
        for (let id = block * 4; id < Math.min(block * 4 + 4, slots); id++) {
            compiled.add(patterns.get(id)?.map((row) => row.cell).join(";") ?? emptyPattern);
        }
    }
    const types = instruments.map((instrument) => instrument.type);
    const byType = (type, index) => instruments.filter((instrument) => instrument.type === type)[index];
    const subpatterns = new Set();
    sequence.forEach((order, track) => order.forEach((id) => {
        for (const row of patterns.get(id) ?? []) {
            const used = row.note !== UGE_NO_NOTE && row.instrument !== 0 ? byType([0, 0, 1, 2][track], row.instrument - 1) : undefined;
            if (used?.subpattern)
                subpatterns.add(used.subpattern);
        }
    }));
    const romBytes = compiled.size * UGE_PATTERN_BYTES + subpatterns.size * UGE_SUBPATTERN_BYTES + types.length * UGE_INSTRUMENT_BYTES + 4 * length * 2 + UGE_FIXED_BYTES;
    return { title: name, ticksPerRow, patterns: patternCount, orderLength: length, compiledPatterns: compiled.size, romBytes };
}
function songTooLarge(details) {
    return `compiles to ${details.romBytes} bytes (${details.compiledPatterns} distinct patterns); a song plays from one 16 KiB ROM bank (${MAX_BANK_BYTES} bytes). Repeat sections in the order instead of writing new ones.`;
}
function inspectMod(bytes) {
    if (bytes.length < 1084)
        throw new Error("the file ends before its pattern table.");
    const signature = bytes.subarray(1080, 1084).toString("latin1");
    if (!["M.K.", "M!K!", "4CHN", "FLT4"].includes(signature))
        throw new Error("GB Studio converts four-channel ProTracker modules only (M.K.).");
    const songLength = bytes[950];
    if (songLength < 1 || songLength > 128)
        throw new Error("the song length is outside 1–128.");
    const patterns = Math.max(...bytes.subarray(952, 1080)) + 1;
    if (bytes.length < 1084 + patterns * 1024)
        throw new Error("the file ends inside its patterns.");
    return { title: bytes.subarray(0, 20).toString("latin1").replace(/\0.*$/s, "").trim(), patterns, orderLength: songLength };
}
// GB Studio's compileWav (wavefile 11): it decodes PCM of 8 to 53 bits or 32- and 64-bit float with any number of
// channels, resamples a rate outside 8000-8192 Hz to 8000 Hz, mixes to mono and packs whole blocks of 32 samples,
// 18 bytes each, then a 2-byte end marker.
function inspectWav(bytes) {
    if (bytes.length < 12 || bytes.toString("latin1", 0, 4) !== "RIFF" || bytes.toString("latin1", 8, 12) !== "WAVE")
        throw new Error("it has no RIFF WAVE header.");
    let format;
    let dataBytes;
    for (let offset = 12; offset + 8 <= bytes.length; ) {
        const id = bytes.toString("latin1", offset, offset + 4), size = bytes.readUInt32LE(offset + 4);
        if (id === "fmt " && size >= 16 && offset + 24 <= bytes.length) {
            format = { code: bytes.readUInt16LE(offset + 8), channels: bytes.readUInt16LE(offset + 10), sampleRate: bytes.readUInt32LE(offset + 12), bits: bytes.readUInt16LE(offset + 22) };
        } else if (id === "data") {
            dataBytes = Math.min(size, bytes.length - offset - 8);
        }
        offset += 8 + size + size % 2;
    }
    if (!format || dataBytes === undefined)
        throw new Error("it needs a fmt and a data chunk.");
    const { code, channels, sampleRate, bits } = format;
    if (!(code === 1 && bits >= 8 && bits <= 53) && !(code === 3 && (bits === 32 || bits === 64))) {
        throw new Error(`GB Studio reads PCM of 8 bits or more, or 32- or 64-bit float; this is format ${code} with ${bits} bits.`);
    }
    if (channels < 1 || channels * bits / 8 > 65535 || sampleRate < 1)
        throw new Error("its channel count or sample rate is out of range.");
    const frames = Math.floor(Math.floor(dataBytes * 8 / ((bits - 1 | 7) + 1)) / channels);
    const rate = sampleRate >= 8_000 && sampleRate <= 8192 ? sampleRate : 8_000;
    const samples = rate === sampleRate ? frames : Math.trunc(frames * ((rate - sampleRate) / sampleRate + 1));
    const blocks = Math.floor(samples / 32);
    if (blocks === 0)
        throw new Error(`it holds ${samples} samples at ${rate} Hz; GB Studio plays whole blocks of 32, so it would play nothing.`);
    const romBytes = blocks * 18 + 2;
    const seconds = samples / rate;
    if (romBytes > MAX_BANK_BYTES) {
        throw new Error(`it lasts ${seconds.toFixed(2)} s; a sound plays from one 16 KiB ROM bank, about ${(MAX_BANK_BYTES / 18 * 32 / 8_000).toFixed(1)} s at most.`);
    }
    return { seconds: Math.round(seconds * 100) / 100, sampleRate, channels, bits, romBytes };
}
// Where GB Studio's compileVGM keeps a Game Boy register write: [group, slot] by its address.
function vgmRegisterSlot(address) {
    if (address >= 16 && address < 22)
        return [0, address - 16];
    if (address >= 22 && address < 32)
        return [1, address - 21];
    if (address >= 32 && address < 36)
        return [3, address - 31];
    if (address >= 36 && address < 39)
        return [4, address - 36];
    if (address >= 48 && address < 64)
        return [5, address - 48];
    return undefined;
}
// The bytes compileVGM writes for one wait: a count byte, the NR50/NR51 writes, the wave table, and each channel's
// writes when the row triggers it (NRx4).
function vgmRowBytes(row) {
    const has = (group, slot) => row.get(group)?.has(slot) === true;
    let bytes = 1;
    const master = [0, 1].filter((slot) => has(4, slot)).length;
    if (master > 0)
        bytes += 1 + master;
    if (row.has(5))
        bytes += 17;
    for (const group of [0, 1, 2, 3]) {
        if (has(group, 4))
            bytes += 1 + [0, 1, 2, 3, 4].filter((slot) => has(group, slot)).length;
    }
    return bytes;
}
function inspectVgm(bytes, compressed) {
    let data = bytes;
    if (compressed) {
        try {
            data = gunzipSync(bytes, { maxOutputLength: MAX_AUDIO_BYTES });
        } catch {
            throw new Error("the .vgz file does not unpack.");
        }
    }
    if (data.length < 132 || data.toString("latin1", 0, 4) !== "Vgm ")
        throw new Error("it has no Vgm header.");
    const version = data.readUInt32LE(8);
    if (version < 353)
        throw new Error(`VGM ${version.toString(16)} predates Game Boy support (1.61).`);
    if (data.readUInt32LE(128) === 0)
        throw new Error("it holds no Game Boy (DMG) sound data.");
    let offset = 52 + data.readUInt32LE(52);
    if (data.readUInt32LE(52) === 0 || offset >= data.length)
        throw new Error("its data offset lies outside the file.");
    let romBytes = 0;
    let row = new Map();
    for (; ; ) {
        const command = data[offset++];
        if (command === undefined || command === 0)
            throw new Error("its commands stop without the end marker (0x66).");
        if (command === 102) {
            romBytes += 2;
            break;
        }
        if (command === 179) {
            if (offset + 2 > data.length)
                throw new Error("a register write is cut off.");
            const slot = vgmRegisterSlot(data[offset] + 16);
            if (!slot)
                throw new Error(`it writes register 0x${(data[offset] + 65296).toString(16)}, which is not a Game Boy sound register.`);
            offset += 2;
            row.set(slot[0], (row.get(slot[0]) ?? new Set()).add(slot[1]));
        } else if (command === 97 || command === 98 || command >= 112 && command <= 127) {
            offset += command === 97 ? 2 : 0;
            romBytes += vgmRowBytes(row);
            row = new Map();
        } else {
            throw new Error(`it uses command 0x${command.toString(16)}; GB Studio converts Game Boy register writes, waits and the end marker only.`);
        }
    }
    if (romBytes > MAX_BANK_BYTES)
        throw new Error(`it compiles to ${romBytes} bytes; a sound plays from one 16 KiB ROM bank (${MAX_BANK_BYTES} bytes).`);
    return { version: `${(version >> 8).toString(16)}.${(version & 255).toString(16).padStart(2, "0")}`, romBytes };
}
function inspectAudio(type, extension, bytes) {
    try {
        switch (type) {
            case "uge": {
                const details = inspectUge(bytes);
                if (details.romBytes > MAX_BANK_BYTES)
                    throw new Error(`it ${songTooLarge(details)}`);
                return details;
            }
            case "mod":
                return inspectMod(bytes);
            case "wav":
                return inspectWav(bytes);
            default:
                return inspectVgm(bytes, extension === ".vgz");
        }
    } catch (error) {
        if (error instanceof GameStudioProjectError)
            throw error;
        audioFormatError(type, error instanceof Error ? error.message : String(error));
    }
}
// GB Studio's toValidSymbol: the symbol its loader gives a file without a sidecar.
function gbStudioSymbol(value) {
    const symbol = String(value || "symbol").toLowerCase().replace(/[^a-z0-9_]/g, "_").replace(/_+/g, "_").substring(0, 27);
    return /^\d/.test(symbol) ? `_${symbol}` : symbol;
}
// Every audio file the compiler sees, as GB Studio's loaders find them, with the sidecar's ID and symbol, or the
// symbol the loader derives for a file without one (which gets a new random ID on every load).
async function discoveredAudio(root) {
    const found = [];
    for (const format of Object.values(AUDIO_FORMATS)) {
        const folder = path.join(root, "assets", format.folder);
        const walk = async (directory) => {
            const entries = await readdir(directory, { withFileTypes: true }).catch((error) => {
                if (isSystemError(error, "ENOENT") || isSystemError(error, "ENOTDIR"))
                    return [];
                throw error;
            });
            for (const entry of entries) {
                const file = path.join(directory, entry.name);
                if (entry.name.startsWith("."))
                    continue;
                if (entry.isDirectory()) {
                    await walk(file);
                } else if (entry.isFile() && format.discovered.includes(path.extname(entry.name))) {
                    const name = path.relative(folder, file).split(path.sep).join("/");
                    const metadata = await projectPathExists(root, `${file}.gbsres`) ? await readProjectJson(root, `${file}.gbsres`).catch(() => undefined) : undefined;
                    found.push({
                        path: file,
                        id: typeof metadata?.id === "string" ? metadata.id : undefined,
                        symbol: typeof metadata?.symbol === "string" ? metadata.symbol : gbStudioSymbol(`${format.prefix}_${format.folder === "music" ? name.replace(/(.mod|.uge)$/i, "") : name}`),
                        registered: metadata !== undefined
                    });
                }
            }
        };
        await walk(folder);
    }
    return found;
}
async function audioRegistry(root, access) {
    const inventory = access ? await access.legacyInventory() : await inventoryProject(root);
    const registry = {
        ids: new Set(inventory.assets.map((asset) => asset.id).filter((id) => typeof id === "string" && id)),
        symbols: new Set(inventory.assets.map((asset) => asset.symbol).filter((symbol) => typeof symbol === "string")),
        unregistered: new Map()
    };
    for (const file of await discoveredAudio(root)) {
        if (file.id)
            registry.ids.add(file.id);
        if (file.registered)
            registry.symbols.add(file.symbol);
        else
            registry.unregistered.set(file.path, file.symbol);
    }
    return registry;
}
// Claims an ID and a unique song_/sound_ symbol for an audio file against every asset the compiler sees.
async function claimAudio(root, access, context, { kind, destination, id, name }) {
    context.audio ??= await audioRegistry(root, access);
    const { ids, symbols, unregistered } = context.audio;
    if (context.claimedIds.has(id) || ids.has(id)) {
        assetError("DUPLICATE_RESOURCE_ID", `The asset ID ${id} is already used by this native game project.`);
    }
    unregistered.delete(destination);
    const taken = new Set([...symbols, ...unregistered.values()]);
    const base = `${AUDIO_FORMATS[kind].prefix}_${resourceSlug(name, "track")}`.slice(0, 27).replace(/_+$/, "");
    let symbol = base;
    for (let count = 0; taken.has(symbol); count++)
        symbol = `${base}_${count}`;
    symbols.add(symbol);
    ids.add(id);
    context.claimedIds.add(id);
    context.claimedPaths.add(destination);
    return symbol;
}
function audioMetadata(kind, fields) {
    const { id, name, symbol, filename, type } = fields;
    return kind === "music" ? { _resourceType: "music", id, name, symbol, settings: {}, filename, type } : { _resourceType: "sound", id, name, symbol, filename, type };
}
function audioResult(metadata, assetPath, details) {
    const kind = metadata._resourceType;
    return {
        id: metadata.id,
        kind,
        name: metadata.name,
        assetPath,
        metadataPath: `${assetPath}.gbsres`,
        symbol: metadata.symbol,
        type: metadata.type,
        ...details,
        playEvent: kind === "music" ? { command: "EVENT_MUSIC_PLAY", args: { musicId: metadata.id } } : { command: "EVENT_SOUND_PLAY_EFFECT", args: { type: metadata.id, priority: "medium" } }
    };
}
export async function prepareAudioImport(root, input, context, access) {
    if (input.background !== undefined || input.sprite !== undefined) {
        assetError("INVALID_INPUT", "background and sprite options apply only to image assets.");
    }
    if (input.id !== undefined && !RESOURCE_ID.test(input.id)) {
        assetError("INVALID_RESOURCE_ID", "An imported native game asset ID must be a valid UUID.");
    }
    const target = audioDestination(root, input.assetPath, input.kind);
    const destination = await onDiskSpelling(root, target.folder, target.destination);
    const relativeDestination = projectRelativePath(root, destination);
    if (context.claimedPaths.has(destination)) {
        assetError("ASSET_ALREADY_EXISTS", `${relativeDestination} appears twice in this import.`, destination);
    }
    const source = await resolveProjectPath(root, input.sourcePath ?? destination, { mustExist: true });
    if (path.extname(source).toLowerCase() !== path.extname(destination).toLowerCase()) {
        assetError("INVALID_ASSET_PATH", "The source and destination must have the same file extension.", source);
    }
    await resolveProjectPath(root, destination);
    const sidecar = `${destination}.gbsres`;
    await resolveProjectPath(root, sidecar);
    if (input.sourcePath && await projectPathExists(root, destination)) {
        assetError("ASSET_ALREADY_EXISTS", `Refusing to overwrite existing ${relativeDestination}.`, destination);
    }
    if (await projectPathExists(root, sidecar)) {
        assetError("ASSET_ALREADY_EXISTS", `${relativeDestination} is already registered (${relativeDestination}.gbsres).`, sidecar);
    }
    const bytes = await readBoundedAudio(root, source);
    const details = inspectAudio(target.type, path.extname(destination).toLowerCase(), bytes);
    // GB Studio matches a sidecar to its file by the path under assets/music or assets/sounds.
    const filename = path.relative(target.folder, destination).split(path.sep).join("/");
    const name = ensureName(input.name ?? path.basename(filename, path.extname(filename)));
    const id = input.id ?? stableResourceId("asset", input.kind, relativeDestination);
    const symbol = await claimAudio(root, access, context, { kind: input.kind, destination, id, name });
    const metadata = audioMetadata(input.kind, { id, name, symbol, filename, type: target.type });
    return {
        root,
        destination,
        sidecar,
        bytes,
        copiesSource: input.sourcePath !== undefined,
        metadata,
        result: audioResult(metadata, relativeDestination, details)
    };
}
const TRACKER_ROWS = 64;
const NOTE_STEPS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
export const DUTY_INSTRUMENTS = {
    lead: { dutyCycle: 2, initialVolume: 12, volumeSweepChange: -1 },
    soft: { dutyCycle: 1, initialVolume: 8, volumeSweepChange: -1 },
    pluck: { dutyCycle: 1, initialVolume: 13, volumeSweepChange: -5 },
    square: { dutyCycle: 2, initialVolume: 10, volumeSweepChange: 0 },
    thin: { dutyCycle: 0, initialVolume: 10, volumeSweepChange: -2 }
};
const WAVE_SHAPES = {
    triangle: Array.from({ length: 32 }, (_, index) => index < 16 ? index : 31 - index),
    saw: Array.from({ length: 32 }, (_, index) => index >> 1),
    square: Array.from({ length: 32 }, (_, index) => index < 16 ? 15 : 0)
};
export const WAVE_INSTRUMENTS = {
    bass: { shape: "triangle", volume: 1 },
    mellow: { shape: "triangle", volume: 2 },
    saw: { shape: "saw", volume: 2 },
    hollow: { shape: "square", volume: 3 }
};
const DRUMS = {
    kick: { note: 12, initialVolume: 15, volumeSweepChange: -6, length: 24 },
    snare: { note: 36, initialVolume: 12, volumeSweepChange: -4, length: 32 },
    hat: { note: 56, initialVolume: 8, volumeSweepChange: -7, length: 8 }
};
const CHANNELS = ["pulse1", "pulse2", "wave", "noise"];
const DEFAULT_INSTRUMENTS = { pulse1: "lead", pulse2: "soft", wave: "bass" };
function composeError(message) {
    assetError("INVALID_SONG", message);
}
function noteIndex(token, channel, where) {
    const match = /^([A-G])(#|b)?([0-9])$/.exec(token);
    if (!match)
        composeError(`${where}: "${token}" is not a note (C4, F#3, Bb5), a rest (.) or a hold (-).`);
    const pitch = Number(match[3]) * 12 + NOTE_STEPS[match[1]] + (match[2] === "#" ? 1 : match[2] === "b" ? -1 : 0);
    const index = pitch - (channel === "wave" ? 12 : 24);
    if (index < 0 || index > 71) {
        composeError(`${where}: ${token} is outside the ${channel === "wave" ? "wave channel's C1–B6" : "pulse channels' C2–B7"} range.`);
    }
    return index;
}
function channelRows(text, channel, instrument, where) {
    const rows = [];
    for (const word of text.split(/\s+/).filter((item) => item && item !== "|")) {
        const [token, count = "1"] = word.split(":");
        const length = Number(count);
        if (!/^[0-9]+$/.test(count) || length < 1 || length > TRACKER_ROWS * 4) {
            composeError(`${where}: "${word}" needs a length of 1–${TRACKER_ROWS * 4} rows after the colon.`);
        }
        let first;
        if (token === "-")
            first = {};
        else if (token === ".")
            first = { cut: true };
        else if (channel === "noise") {
            if (!Object.hasOwn(DRUMS, token))
                composeError(`${where}: "${token}" is not a drum (kick, snare, hat), a rest (.) or a hold (-).`);
            first = { note: DRUMS[token].note, instrument: Object.keys(DRUMS).indexOf(token) };
        } else {
            first = { note: noteIndex(token, channel, where), instrument };
        }
        rows.push(first, ...Array.from({ length: length - 1 }, () => ({})));
    }
    return rows;
}
function composeSections(spec) {
    const used = { duty: [], wave: [] };
    const instrumentIndex = (channel, preset) => {
        const kind = channel === "wave" ? "wave" : "duty";
        const table = kind === "wave" ? WAVE_INSTRUMENTS : DUTY_INSTRUMENTS;
        if (!Object.hasOwn(table, preset))
            composeError(`${channel} has no instrument "${preset}" (${Object.keys(table).join(", ")}).`);
        if (!used[kind].includes(preset))
            used[kind].push(preset);
        return used[kind].indexOf(preset);
    };
    const sections = new Map();
    for (const section of spec.sections) {
        if (sections.has(section.name))
            composeError(`Two sections are named "${section.name}".`);
        const channels = {};
        for (const channel of CHANNELS) {
            const value = section[channel];
            const where = `section "${section.name}" ${channel}`;
            if (value === undefined) {
                channels[channel] = [{ cut: true }];
                continue;
            }
            const notes = typeof value === "string" ? value : value.notes;
            const preset = (typeof value === "string" ? undefined : value.instrument) ?? spec.instruments?.[channel] ?? DEFAULT_INSTRUMENTS[channel];
            channels[channel] = channelRows(notes, channel, channel === "noise" ? undefined : instrumentIndex(channel, preset), where);
        }
        const length = Math.max(...Object.values(channels).map((rows) => rows.length));
        if (length > TRACKER_ROWS * 4)
            composeError(`Section "${section.name}" runs ${length} rows; a section holds at most ${TRACKER_ROWS * 4}.`);
        sections.set(section.name, { length, channels });
    }
    const order = spec.order ?? spec.sections.map((section) => section.name);
    const streams = Object.fromEntries(CHANNELS.map((channel) => [channel, []]));
    for (const name of order) {
        const section = sections.get(name);
        if (!section)
            composeError(`order names "${name}", which is not a section.`);
        for (const channel of CHANNELS) {
            const rows = section.channels[channel];
            streams[channel].push(...rows, ...Array.from({ length: section.length - rows.length }, () => ({})));
        }
    }
    const rows = streams.pulse1.length;
    if (rows > TRACKER_ROWS * 64)
        composeError(`The song runs ${rows} rows; at most ${TRACKER_ROWS * 64} (64 patterns) fit.`);
    return { streams, rows, used };
}
function emptySubpattern() {
    return Array.from({ length: 64 }, () => ({ note: null, jump: 0, effectCode: 0, effectParam: 0 }));
}
function buildSong(spec) {
    const { streams, rows, used } = composeSections(spec);
    const blocks = Math.ceil(rows / TRACKER_ROWS);
    const cell = (row) => row.cut ? { note: null, instrument: null, effectCode: 14, effectParam: 0 } : { note: row.note ?? null, instrument: row.instrument ?? null, effectCode: null, effectParam: null };
    const patterns = [];
    for (let block = 0; block < blocks; block++) {
        for (const channel of CHANNELS) {
            const slice = streams[channel].slice(block * TRACKER_ROWS, (block + 1) * TRACKER_ROWS);
            patterns.push([...slice, ...Array.from({ length: TRACKER_ROWS - slice.length }, () => ({}))].map(cell));
        }
    }
    // A song that ends mid-pattern breaks to the next order (D01) on its last row. When every channel cuts there, the
    // break goes on the silent row after it, unless that row ends the pattern anyway.
    let played = rows;
    if (rows % TRACKER_ROWS !== 0) {
        const lastBlock = patterns.slice(-4);
        let last = (rows - 1) % TRACKER_ROWS;
        if (lastBlock.every((pattern) => pattern[last].effectCode !== null)) {
            last += 1;
            played += 1;
        }
        if (last < TRACKER_ROWS - 1) {
            const target = [...lastBlock].reverse().find((pattern) => pattern[last].effectCode === null);
            target[last] = { ...target[last], effectCode: 13, effectParam: 1 };
        }
    }
    const blank = { name: "", length: null, dutyCycle: 0, initialVolume: 0, volumeSweepChange: 0, volume: 0, waveIndex: 0, bitCount: 15, subpatternEnabled: false, subpattern: emptySubpattern() };
    const fill = (items) => Array.from({ length: 15 }, (_, index) => ({ ...blank, ...items[index] }));
    const shapes = [...new Set(used.wave.map((preset) => WAVE_INSTRUMENTS[preset].shape))];
    return {
        name: spec.title ?? "",
        ticksPerRow: spec.ticksPerRow ?? 7,
        rows: played,
        duty: fill(used.duty.map((preset) => ({ name: preset, ...DUTY_INSTRUMENTS[preset] }))),
        wave: fill(used.wave.map((preset) => ({ name: preset, volume: WAVE_INSTRUMENTS[preset].volume, waveIndex: shapes.indexOf(WAVE_INSTRUMENTS[preset].shape) }))),
        noise: fill(Object.entries(DRUMS).map(([name, drum]) => ({ name, ...drum }))),
        waves: Array.from({ length: 16 }, (_, index) => WAVE_SHAPES[shapes[index]] ?? Array(32).fill(0)),
        patterns,
        blocks
    };
}
function encodeUge(song) {
    const chunks = [];
    const u8 = (value) => chunks.push(Buffer.from([value & 255]));
    const u32 = (value) => {
        const bytes = Buffer.alloc(4);
        bytes.writeUInt32LE(value >>> 0);
        chunks.push(bytes);
    };
    const text = (value) => {
        const bytes = Buffer.alloc(256);
        const encoded = Buffer.from(value, "utf8").subarray(0, 255);
        bytes[0] = encoded.length;
        encoded.copy(bytes, 1);
        chunks.push(bytes);
    };
    const envelope = (instrument) => {
        u8(instrument.initialVolume);
        u32(instrument.volumeSweepChange < 0 ? 1 : 0);
        u8(instrument.volumeSweepChange ? 8 - Math.abs(instrument.volumeSweepChange) : 0);
    };
    const instrument = (type, item) => {
        u32(type);
        text(item.name);
        u32(item.length === null ? 0 : (type === 1 ? 256 : 64) - item.length);
        u8(item.length === null ? 0 : 1);
        if (type === 1) {
            u8(0);
            u32(0);
            u8(0);
        } else {
            envelope(item);
        }
        u32(0);
        u32(0);
        u32(0);
        u8(type === 0 ? item.dutyCycle : 0);
        u32(type === 1 ? item.volume : 0);
        u32(type === 1 ? item.waveIndex : 0);
        u32(type === 2 && item.bitCount === 7 ? 1 : 0);
        u8(item.subpatternEnabled ? 1 : 0);
        for (const row of item.subpattern) {
            u32(row.note ?? 90);
            u32(0);
            u32(row.jump);
            u32(row.effectCode);
            u8(row.effectParam);
        }
    };
    u32(6);
    text(song.name);
    text("");
    text("");
    song.duty.forEach((item) => instrument(0, item));
    song.wave.forEach((item) => instrument(1, item));
    song.noise.forEach((item) => instrument(2, item));
    song.waves.forEach((wave) => chunks.push(Buffer.from(wave)));
    u32(song.ticksPerRow);
    u8(0);
    u32(0);
    u32(song.patterns.length);
    song.patterns.forEach((pattern, index) => {
        u32(index);
        for (const row of pattern) {
            u32(row.note ?? 90);
            u32(row.instrument === null ? 0 : row.instrument + 1);
            u32(0);
            u32(row.effectCode ?? 0);
            u8(row.effectParam ?? 0);
        }
    });
    for (let track = 0; track < 4; track++) {
        u32(song.blocks + 1);
        for (let block = 0; block < song.blocks; block++)
            u32(block * 4 + track);
        u32(0);
    }
    for (let routine = 0; routine < 16; routine++)
        u32(0);
    return Buffer.concat(chunks);
}
async function bundledTrack(name) {
    if (!BUNDLED_TRACKS.includes(name))
        composeError(`There is no bundled track "${name}" (${BUNDLED_TRACKS.join(", ")}).`);
    return JSON.parse(await readFile(path.join(BUNDLED_MUSIC, `${name}.json`), "utf8"));
}
export async function composeMusic(projectRoot, input, access) {
    const root = await assertDistributedProject(projectRoot, access);
    if (input.bundled !== undefined && (input.sections !== undefined || input.order !== undefined || input.instruments !== undefined || input.ticksPerRow !== undefined)) {
        composeError("bundled writes a finished track; leave out sections, order, instruments and ticksPerRow.");
    }
    if (input.bundled === undefined && input.sections === undefined)
        composeError("Give sections (with an optional order), or a bundled track.");
    const spec = input.bundled === undefined ? input : await bundledTrack(input.bundled);
    const assetPath = input.assetPath ?? (input.bundled ? `assets/music/${input.bundled}.uge` : undefined);
    const target = audioDestination(root, assetPath, "music");
    if (target.type !== "uge")
        assetError("INVALID_ASSET_PATH", "A composed song is written as a .uge file.");
    if (input.id !== undefined && !RESOURCE_ID.test(input.id)) {
        assetError("INVALID_RESOURCE_ID", "A song ID must be a valid UUID.");
    }
    const destination = await onDiskSpelling(root, target.folder, target.destination);
    const relativeDestination = projectRelativePath(root, destination);
    const sidecar = `${destination}.gbsres`;
    await resolveProjectPath(root, sidecar);
    const existing = await projectPathExists(root, destination) || await projectPathExists(root, sidecar);
    if (existing && !input.overwrite) {
        assetError("ASSET_ALREADY_EXISTS", `${relativeDestination} already exists; pass overwrite to replace the song and keep its ID.`, destination);
    }
    const previous = existing && await projectPathExists(root, sidecar) ? await readProjectJson(root, sidecar) : undefined;
    if (previous !== undefined && previous._resourceType !== "music") {
        assetError("UNSUPPORTED_ASSET_KIND", `${relativeDestination}.gbsres is not music metadata.`, sidecar);
    }
    if (previous !== undefined && input.id !== undefined && input.id !== previous.id) {
        assetError("INVALID_INPUT", "overwrite keeps the song's ID; leave id out or give the existing one.");
    }
    const song = buildSong({ ...spec, title: input.name ?? spec.title });
    const bytes = encodeUge(song);
    const compiled = inspectUge(bytes);
    if (compiled.romBytes > MAX_BANK_BYTES)
        composeError(`The song ${songTooLarge(compiled)}`);
    const filename = path.relative(target.folder, destination).split(path.sep).join("/");
    const name = ensureName(input.name ?? previous?.name ?? spec.title ?? path.basename(filename, ".uge"));
    let metadata;
    if (previous !== undefined) {
        metadata = { ...previous, name, filename, type: "uge" };
    } else {
        const id = input.id ?? stableResourceId("asset", "music", relativeDestination);
        const symbol = await claimAudio(root, access, { claimedIds: new Set(), claimedPaths: new Set() }, { kind: "music", destination, id, name });
        metadata = audioMetadata("music", { id, name, symbol, filename, type: "uge" });
    }
    // The song and its sidecar publish together: a song left without its sidecar would refuse the next attempt.
    const before = await projectPathExists(root, destination) ? await readBoundedAudio(root, destination) : undefined;
    await writeProjectBytesAtomic(root, destination, bytes);
    try {
        await writeProjectJsonAtomic(root, sidecar, metadata);
    } catch (error) {
        if (before === undefined)
            await rm(destination, { force: true });
        else
            await writeProjectBytesAtomic(root, destination, before);
        throw error;
    }
    return audioResult(metadata, relativeDestination, {
        ...input.bundled === undefined ? {} : { bundled: input.bundled },
        ...previous === undefined ? {} : { replaced: true },
        ticksPerRow: song.ticksPerRow,
        rows: song.rows,
        patterns: song.blocks * 4,
        romBytes: compiled.romBytes,
        loopSeconds: Math.round(song.rows * song.ticksPerRow / GB_FRAMES_PER_SECOND * 10) / 10
    });
}
export async function inspectAudioAsset(loaded) {
    const extension = path.extname(loaded.assetPath).toLowerCase();
    const type = AUDIO_TYPES.get(extension);
    if (type === undefined)
        assetError("UNSUPPORTED_ASSET_KIND", `${loaded.assetPath} is not a .uge, .mod, .wav, .vgm or .vgz file.`);
    const bytes = await readBoundedAudio(loaded.projectRoot, loaded.assetPath);
    return audioResult(loaded.metadata, loaded.assetPath, inspectAudio(type, extension, bytes));
}
