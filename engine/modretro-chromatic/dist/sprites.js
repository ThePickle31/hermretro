import { createHash, randomUUID } from "node:crypto";
import { mkdir, open, readFile } from "node:fs/promises";
import path from "node:path";
import { PNG } from "pngjs";
import { findAssetMetadata } from "./assets.js";
import { pattern } from "./native-sprite-metadata.js";
import { chromaticDisplayColor, paletteProject, requirePalette } from "./palettes.js";
import { projectRelativePath, resolveProjectPath, resourceSlug, stableResourceId, writeProjectJsonAtomic, } from "./project-files.js";
import { GameStudioProjectError } from "./project.js";
import { validColors } from "./scene-graphics.js";
const SOURCE_PREVIEW_LABEL = "Authored sprite source composite; not an emulator framebuffer or gameplay capture.";
const MAX_PREVIEW_FRAMES = 32;
const SPRITE_TILE_WIDTH = 8;
const SPRITE_TILE_HEIGHT = 16;
const CHROMA_RED = 0x65;
const CHROMA_GREEN = 0xff;
const CHROMA_BLUE = 0x00;
const MAX_METASPRITE_FRAME_SIZE = 128;
const MAX_METASPRITE_FRAMES = 32;
const MAX_FRAME_OBJECTS = 40;
const MAX_SCANLINE_SPRITE_OBJECTS = 10;
const MAX_SPRITE_OBJECTS = 96;
const MAX_COLOR_SPRITE_OBJECTS = 192;
const PREVIEW_FRAME_SIDE = 128;
const SHEET_FRAME_SIDE = 64;
function spriteError(code, message) {
    throw new GameStudioProjectError(code, message);
}
function asObject(value, label) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
        spriteError("INVALID_SPRITE_RESOURCE", `Sprite ${label} must be a JSON object.`);
    }
    return value;
}
function asArray(value, label) {
    if (!Array.isArray(value))
        spriteError("INVALID_SPRITE_RESOURCE", `Sprite ${label} must be an array.`);
    return value;
}
function asNumber(value, fallback = 0) {
    return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}
function integer(value, name, minimum, maximum) {
    if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
        spriteError("INVALID_INPUT", `${name} must be an integer between ${minimum} and ${maximum}.`);
    }
    return value;
}
function nestedId(rootId, ...parts) {
    return stableResourceId("sprite", rootId, ...parts.map(String));
}
function objectTile(rootId, animationIndex, frameIndex, tileIndex, placement, paletteIndex) {
    return {
        id: nestedId(rootId, "tile", animationIndex, frameIndex, tileIndex),
        x: placement.x,
        y: placement.y,
        sliceX: placement.sliceX,
        sliceY: placement.sliceY,
        flipX: false,
        flipY: false,
        palette: 0,
        paletteIndex,
        objPalette: "OBP0",
        priority: false,
    };
}
function simpleFrame(sliceX) {
    return sliceX === undefined
        ? []
        : [0, 1].map((tileIndex) => ({ x: tileIndex * SPRITE_TILE_WIDTH, y: 0, sliceX: sliceX + tileIndex * SPRITE_TILE_WIDTH, sliceY: 0 }));
}
function simpleProfile(profile) {
    if (profile === "static" || profile === "static16x16") {
        return { width: 16, animationType: "fixed", flipLeft: false, boundsY: -8, boundsHeight: 16, slices: [[0], [undefined], [undefined], [undefined], [undefined], [undefined], [undefined], [undefined]] };
    }
    if (profile === "directional" || profile === "directional48x16") {
        return { width: 48, animationType: "multi", flipLeft: true, boundsY: -8, boundsHeight: 16, slices: [[32], [undefined], [16], [0], [undefined], [undefined], [undefined], [undefined]] };
    }
    if (profile === "directional_animated" || profile === "directional_animated96x16") {
        return { width: 96, animationType: "multi_movement", flipLeft: true, boundsY: 0, boundsHeight: 8, slices: [[64], [undefined], [32], [0], [80, 64], [undefined], [48, 32], [16, 0]] };
    }
    return spriteError("UNSUPPORTED_SPRITE_PROFILE", `Unsupported or unproven sprite profile ${String(profile)}.`);
}
function simpleLayout(input) {
    const profile = simpleProfile(input.profile);
    if (input.width !== profile.width || input.height !== 16) {
        spriteError("INVALID_SPRITE_DIMENSIONS", `Sprite profile ${input.profile} requires exactly ${profile.width} × 16 source pixels.`);
    }
    const cellBounds = input.gridSize === 16 && input.sceneType === "TOPDOWN";
    return {
        animationType: profile.animationType,
        flipLeft: profile.flipLeft,
        canvasWidth: 16,
        canvasHeight: 16,
        bounds: { x: 0, y: cellBounds ? -8 : profile.boundsY, width: 16, height: cellBounds ? 16 : profile.boundsHeight },
        animations: profile.slices.map((frames) => frames.map(simpleFrame)),
        diagnostics: [],
    };
}
function metaspriteLayout(input) {
    const { frameWidth, frameHeight, image } = input;
    if (frameWidth === undefined || frameHeight === undefined) {
        spriteError("INVALID_INPUT", "The metasprite profile requires sprite.frameWidth and sprite.frameHeight.");
    }
    integer(frameWidth, "frameWidth", SPRITE_TILE_WIDTH, MAX_METASPRITE_FRAME_SIZE);
    integer(frameHeight, "frameHeight", SPRITE_TILE_HEIGHT, MAX_METASPRITE_FRAME_SIZE);
    if (frameWidth % SPRITE_TILE_WIDTH !== 0 || frameHeight % SPRITE_TILE_HEIGHT !== 0) {
        spriteError("INVALID_SPRITE_DIMENSIONS", "Metasprite frames are built from 8 × 16 tiles: frameWidth must be a multiple of 8 and frameHeight a multiple of 16.");
    }
    if (input.height !== frameHeight || input.width % frameWidth !== 0 || input.width / frameWidth > MAX_METASPRITE_FRAMES) {
        spriteError("INVALID_SPRITE_DIMENSIONS", `A metasprite sheet is one row of 1–${MAX_METASPRITE_FRAMES} frames of ${frameWidth} × ${frameHeight}: its height must be ${frameHeight} and its width a multiple of ${frameWidth}.`);
    }
    const originX = Math.max(0, frameWidth / 2 - SPRITE_TILE_WIDTH);
    const frames = [];
    let widestRow = 0;
    for (let frameIndex = 0; frameIndex < input.width / frameWidth; frameIndex += 1) {
        const tiles = [];
        for (let row = 0; row < frameHeight / SPRITE_TILE_HEIGHT; row += 1) {
            let rowObjects = 0;
            for (let column = 0; column < frameWidth / SPRITE_TILE_WIDTH; column += 1) {
                const sliceX = frameIndex * frameWidth + column * SPRITE_TILE_WIDTH;
                const sliceY = row * SPRITE_TILE_HEIGHT;
                if (!/[^0]/.test(pattern(image, sliceX, sliceY)))
                    continue;
                rowObjects += 1;
                tiles.push({ x: column * SPRITE_TILE_WIDTH - originX, y: frameHeight - SPRITE_TILE_HEIGHT - sliceY, sliceX, sliceY });
            }
            widestRow = Math.max(widestRow, rowObjects);
        }
        if (tiles.length > MAX_FRAME_OBJECTS) {
            spriteError("METASPRITE_OBJECT_LIMIT", `Frame ${frameIndex} needs ${tiles.length} hardware objects; one frame can use at most ${MAX_FRAME_OBJECTS}.`);
        }
        frames.push(tiles);
    }
    return {
        animationType: "fixed",
        flipLeft: false,
        canvasWidth: frameWidth,
        canvasHeight: frameHeight,
        bounds: { x: -originX, y: SPRITE_TILE_WIDTH - frameHeight, width: frameWidth, height: frameHeight },
        animations: [frames, ...Array.from({ length: 7 }, () => [[]])],
        diagnostics: widestRow > MAX_SCANLINE_SPRITE_OBJECTS ? [{
                code: "METASPRITE_SCANLINE_WIDTH",
                severity: "warning",
                message: `A frame puts ${widestRow} objects side by side in one row; the hardware draws at most ${MAX_SCANLINE_SPRITE_OBJECTS} per scanline, so parts of it will disappear.`,
            }] : [],
    };
}
function spriteObjectCount(image, animations) {
    const objects = new Set();
    for (const frames of animations) {
        for (const tiles of frames) {
            for (const { sliceX, sliceY } of tiles) {
                const rows = pattern(image, sliceX, sliceY).match(/.{8}/g);
                if (!rows.some((row) => /[^0]/.test(row)))
                    continue;
                const mirrored = rows.map((row) => [...row].reverse().join(""));
                objects.add([rows, mirrored, [...rows].reverse(), [...mirrored].reverse()].map((orientation) => orientation.join("")).sort()[0]);
            }
        }
    }
    return objects.size;
}
function replaceNestedIds(value, assetId, trail = "root") {
    if (Array.isArray(value))
        return value.map((entry, index) => replaceNestedIds(entry, assetId, `${trail}.${index}`));
    if (typeof value !== "object" || value === null)
        return value;
    return Object.fromEntries(Object.entries(value).map(([key, child]) => [
        key,
        key === "id" && trail !== "root" ? nestedId(assetId, trail) : replaceNestedIds(child, assetId, `${trail}.${key}`),
    ]));
}
function withPaletteIndex(metadata, paletteIndex) {
    for (const state of asArray(metadata.states, "states")) {
        for (const animation of asArray(asObject(state, "state").animations, "animations")) {
            for (const frame of asArray(asObject(animation, "animation").frames, "frames")) {
                for (const tile of asArray(asObject(frame, "frame").tiles, "tiles"))
                    asObject(tile, "tile").paletteIndex = paletteIndex;
            }
        }
    }
    return metadata;
}
export async function createSpriteResource(projectRoot, input, access) {
    const paletteIndex = input.paletteIndex === undefined ? undefined : integer(input.paletteIndex, "paletteIndex", 0, 7);
    if ((input.frameWidth !== undefined || input.frameHeight !== undefined) && input.profile !== "metasprite") {
        spriteError("INVALID_INPUT", "frameWidth and frameHeight apply to the metasprite profile only.");
    }
    if (input.profile === "template") {
        if (!input.templateAssetId) {
            spriteError("SPRITE_TEMPLATE_REQUIRED", "The template profile requires an existing templateAssetId.");
        }
        const template = await findAssetMetadata(projectRoot, { assetId: input.templateAssetId }, access);
        if (template.metadata._resourceType !== "sprite") {
            spriteError("INVALID_SPRITE_TEMPLATE", "A sprite template must refer to an existing sprite asset.");
        }
        if (template.metadata.width !== input.width || template.metadata.height !== input.height) {
            spriteError("SPRITE_TEMPLATE_DIMENSIONS", "Sprite source dimensions must match the selected native template.");
        }
        const metadata = {
            ...replaceNestedIds(template.metadata, input.id),
            id: input.id,
            name: input.name,
            symbol: `sprite_${resourceSlug(input.name, "sprite")}`,
            filename: input.filename,
            width: input.width,
            height: input.height,
            checksum: input.checksum,
        };
        return { metadata: paletteIndex === undefined ? metadata : withPaletteIndex(metadata, paletteIndex), diagnostics: [] };
    }
    if (input.spriteMode === "8x8") {
        spriteError("SPRITE_MODE_UNSUPPORTED", "Generated sprite profiles build 8 × 16 objects, but this project's sprite mode is 8 × 8, where GB Studio would compile only the top half of each. Set the project's sprite mode to 8 × 16, or use the template profile with a sprite made for 8 × 8.");
    }
    const layout = input.profile === "metasprite" ? metaspriteLayout(input) : simpleLayout(input);
    const numTiles = spriteObjectCount(input.image, layout.animations);
    const maxObjects = input.colorMode === "color" ? MAX_COLOR_SPRITE_OBJECTS : MAX_SPRITE_OBJECTS;
    if (numTiles > maxObjects) {
        spriteError("SPRITE_TILE_LIMIT", `The sprite needs ${numTiles} distinct 8 × 16 tiles after GB Studio's flip deduplication; a ${input.colorMode === "color" ? "Color Only" : "Color + Monochrome or Monochrome"} scene holds at most ${maxObjects}, fewer beside a large background.`);
    }
    const metadata = {
        _resourceType: "sprite",
        id: input.id,
        name: input.name,
        symbol: `sprite_${resourceSlug(input.name, "sprite")}`,
        states: [
            {
                id: nestedId(input.id, "state", 0),
                name: "",
                animationType: layout.animationType,
                flipLeft: layout.flipLeft,
                animations: layout.animations.map((frames, animationIndex) => ({
                    id: nestedId(input.id, "animation", animationIndex),
                    frames: frames.map((tiles, frameIndex) => ({
                        id: nestedId(input.id, "frame", animationIndex, frameIndex),
                        tiles: tiles.map((placement, tileIndex) => objectTile(input.id, animationIndex, frameIndex, tileIndex, placement, paletteIndex ?? 0)),
                    })),
                })),
            },
        ],
        numTiles,
        canvasOriginX: 0,
        canvasOriginY: 0,
        canvasWidth: layout.canvasWidth,
        canvasHeight: layout.canvasHeight,
        boundsX: layout.bounds.x,
        boundsY: layout.bounds.y,
        boundsWidth: layout.bounds.width,
        boundsHeight: layout.bounds.height,
        animSpeed: 15,
        filename: input.filename,
        width: input.width,
        height: input.height,
        checksum: input.checksum,
    };
    return { metadata, diagnostics: layout.diagnostics };
}
async function loadSprite(projectRoot, input, access) {
    const assetId = input.spriteId ?? input.assetId;
    if (input.spriteId && input.assetId && input.spriteId !== input.assetId) {
        spriteError("INVALID_INPUT", "spriteId and assetId must identify the same sprite.");
    }
    const loaded = await findAssetMetadata(projectRoot, { assetId, assetPath: input.assetPath }, access);
    if (loaded.metadata._resourceType !== "sprite") {
        spriteError("INVALID_SPRITE_RESOURCE", `Asset ${loaded.assetPath} is not a native game sprite.`);
    }
    return loaded;
}
function summarizeSprite(metadata, assetPath, includeFrames = false) {
    const states = asArray(metadata.states, "states").map((entry, stateIndex) => {
        const state = asObject(entry, `state ${stateIndex}`);
        return {
            id: String(state.id),
            name: String(state.name ?? ""),
            animationType: String(state.animationType),
            flipLeft: state.flipLeft === true,
            animations: asArray(state.animations, `state ${stateIndex} animations`).map((animationEntry, animationIndex) => {
                const animation = asObject(animationEntry, `animation ${animationIndex}`);
                const frames = asArray(animation.frames, `animation ${animationIndex} frames`);
                const result = {
                    id: String(animation.id),
                    index: animationIndex,
                    frameCount: frames.length,
                };
                if (includeFrames) {
                    result.frames = frames.map((frameEntry, frameIndex) => {
                        const frame = asObject(frameEntry, `frame ${frameIndex}`);
                        const tiles = asArray(frame.tiles, `frame ${frameIndex} tiles`);
                        return {
                            id: String(frame.id),
                            tileCount: tiles.length,
                            tiles: tiles.map((tileEntry, tileIndex) => {
                                const tile = asObject(tileEntry, `tile ${tileIndex}`);
                                return {
                                    id: String(tile.id),
                                    x: asNumber(tile.x),
                                    y: asNumber(tile.y),
                                    sliceX: asNumber(tile.sliceX),
                                    sliceY: asNumber(tile.sliceY),
                                    flipX: tile.flipX === true,
                                    flipY: tile.flipY === true,
                                    palette: asNumber(tile.palette),
                                    paletteIndex: asNumber(tile.paletteIndex),
                                    objPalette: String(tile.objPalette ?? "OBP0"),
                                    priority: tile.priority === true,
                                };
                            }),
                        };
                    });
                }
                return result;
            }),
        };
    });
    return {
        id: String(metadata.id),
        kind: "sprite",
        name: String(metadata.name),
        assetPath,
        metadataPath: `${assetPath}.gbsres`,
        width: asNumber(metadata.width),
        height: asNumber(metadata.height),
        checksum: String(metadata.checksum),
        numTiles: asNumber(metadata.numTiles),
        canvas: {
            originX: asNumber(metadata.canvasOriginX),
            originY: asNumber(metadata.canvasOriginY),
            width: asNumber(metadata.canvasWidth, 16),
            height: asNumber(metadata.canvasHeight, 16),
        },
        bounds: {
            x: asNumber(metadata.boundsX),
            y: asNumber(metadata.boundsY),
            width: asNumber(metadata.boundsWidth),
            height: asNumber(metadata.boundsHeight),
        },
        animSpeed: asNumber(metadata.animSpeed),
        states,
    };
}
export async function inspectSprite(projectRoot, input, access) {
    const loaded = await loadSprite(projectRoot, input, access);
    return summarizeSprite(loaded.metadata, loaded.assetPath, input.includeFrames);
}
export async function updateSprite(projectRoot, input, access) {
    const loaded = await loadSprite(projectRoot, input, access);
    const updated = structuredClone(loaded.metadata);
    if (input.name !== undefined) {
        const name = input.name.trim();
        if (!name)
            spriteError("INVALID_INPUT", "Sprite names cannot be empty.");
        updated.name = name;
        updated.symbol = `sprite_${resourceSlug(name, "sprite")}`;
    }
    if (input.animSpeed !== undefined)
        updated.animSpeed = integer(input.animSpeed, "animSpeed", 0, 255);
    if (input.boundsX !== undefined)
        updated.boundsX = integer(input.boundsX, "boundsX", -128, 127);
    if (input.boundsY !== undefined)
        updated.boundsY = integer(input.boundsY, "boundsY", -128, 127);
    if (input.boundsWidth !== undefined)
        updated.boundsWidth = integer(input.boundsWidth, "boundsWidth", 1, 255);
    if (input.boundsHeight !== undefined)
        updated.boundsHeight = integer(input.boundsHeight, "boundsHeight", 1, 255);
    if (input.flipLeft !== undefined || input.animationType !== undefined) {
        const stateIndex = integer(input.stateIndex ?? 0, "stateIndex", 0, 31);
        const states = asArray(updated.states, "states");
        const state = asObject(states[stateIndex], `state ${stateIndex}`);
        if (input.flipLeft !== undefined)
            state.flipLeft = input.flipLeft;
        if (input.animationType !== undefined) {
            if (!["fixed", "multi", "multi_movement"].includes(input.animationType)) {
                spriteError("INVALID_INPUT", "animationType must be fixed, multi, or multi_movement.");
            }
            state.animationType = input.animationType;
        }
    }
    await writeProjectJsonAtomic(loaded.projectRoot, loaded.metadataPath, updated);
    return summarizeSprite(updated, loaded.assetPath, input.includeFrames);
}
function compositeFrame(source, metadata, frame) {
    const width = integer(asNumber(metadata.canvasWidth, 16), "sprite canvasWidth", 1, 256);
    const height = integer(asNumber(metadata.canvasHeight, 16), "sprite canvasHeight", 1, 256);
    // Native 8x16 metasprites use a centered X origin and positive Y points up
    // from the bottom tile row. Canvases narrower than 16 keep their X origin.
    const originX = width < 16 ? 0 : width / 2 - SPRITE_TILE_WIDTH;
    const originY = height - SPRITE_TILE_HEIGHT;
    const image = new PNG({ width, height, colorType: 6 });
    for (const tileEntry of asArray(frame.tiles, "frame tiles")) {
        const tile = asObject(tileEntry, "tile");
        for (let y = 0; y < SPRITE_TILE_HEIGHT; y += 1) {
            for (let x = 0; x < SPRITE_TILE_WIDTH; x += 1) {
                const sourceX = asNumber(tile.sliceX) + (tile.flipX === true ? SPRITE_TILE_WIDTH - x - 1 : x);
                const sourceY = asNumber(tile.sliceY) + (tile.flipY === true ? SPRITE_TILE_HEIGHT - y - 1 : y);
                const destinationX = originX + asNumber(tile.x) + x;
                const destinationY = originY - asNumber(tile.y) + y;
                if (sourceX < 0 ||
                    sourceY < 0 ||
                    sourceX >= source.width ||
                    sourceY >= source.height ||
                    destinationX < 0 ||
                    destinationY < 0 ||
                    destinationX >= width ||
                    destinationY >= height) {
                    continue;
                }
                const readIndex = (source.width * sourceY + sourceX) * 4;
                const red = source.data[readIndex] ?? 0;
                const green = source.data[readIndex + 1] ?? 0;
                const blue = source.data[readIndex + 2] ?? 0;
                const alpha = source.data[readIndex + 3] ?? 0;
                if (alpha === 0 || (red === CHROMA_RED && green === CHROMA_GREEN && blue === CHROMA_BLUE))
                    continue;
                const writeIndex = (width * destinationY + destinationX) * 4;
                image.data[writeIndex] = red;
                image.data[writeIndex + 1] = green;
                image.data[writeIndex + 2] = blue;
                image.data[writeIndex + 3] = alpha;
            }
        }
    }
    return image;
}
export function scaledImage(source, scale) {
    if (scale === 1)
        return source;
    const image = new PNG({ width: source.width * scale, height: source.height * scale, colorType: 6 });
    for (let y = 0; y < image.height; y += 1) {
        for (let x = 0; x < image.width; x += 1) {
            const from = (source.width * Math.floor(y / scale) + Math.floor(x / scale)) * 4;
            const to = (image.width * y + x) * 4;
            source.data.copy(image.data, to, from, from + 4);
        }
    }
    return image;
}
async function writePreview(root, relativeOutput, image) {
    if (!relativeOutput || path.extname(relativeOutput).toLowerCase() !== ".png") {
        spriteError("INVALID_INPUT", "Sprite previews require a project-local .png outputPath.");
    }
    const output = await resolveProjectPath(root, relativeOutput);
    await mkdir(path.dirname(output), { recursive: true });
    await resolveProjectPath(root, path.dirname(output), { mustExist: true });
    const bytes = PNG.sync.write(image);
    const handle = await open(output, "wx", 0o600).catch((error) => {
        if (error instanceof Error && "code" in error && error.code === "EEXIST") {
            spriteError("SPRITE_PREVIEW_OUTPUT_EXISTS", "The sprite preview output already exists and was preserved. Choose a new project-local .png outputPath.");
        }
        throw error;
    });
    try {
        await handle.writeFile(bytes);
        await handle.sync();
    }
    finally {
        await handle.close();
    }
    return {
        outputPath: projectRelativePath(root, output),
        width: image.width,
        height: image.height,
        sha256: createHash("sha256").update(bytes).digest("hex"),
        provenance: "authored-source-composite",
        emulatorFrame: false,
        label: SOURCE_PREVIEW_LABEL,
    };
}
function selectedFrame(metadata, stateIndex, animationIndex, frameIndex) {
    const state = asObject(asArray(metadata.states, "states")[stateIndex], `state ${stateIndex}`);
    const animation = asObject(asArray(state.animations, `state ${stateIndex} animations`)[animationIndex], `animation ${animationIndex}`);
    return asObject(asArray(animation.frames, `animation ${animationIndex} frames`)[frameIndex], `frame ${frameIndex}`);
}
function enlargedScale(metadata, side) {
    const largest = Math.max(asNumber(metadata.canvasWidth, 16), asNumber(metadata.canvasHeight, 16));
    return Math.min(8, Math.max(1, Math.floor(side / largest)));
}
async function spriteDisplay(projectRoot, input, access) {
    let shades;
    if (input.paletteId !== undefined) {
        const palette = requirePalette(await paletteProject(projectRoot, access), input.paletteId, access);
        const colors = validColors(palette.colors);
        if (colors === undefined)
            spriteError("INVALID_PALETTE_COLORS", `Palette ${input.paletteId} does not hold four RGB colors.`);
        shades = new Map([["e0f8cf", colors[0]], ["86c06c", colors[1]], ["071821", colors[3]]]);
    }
    const corrected = input.colorCorrection === "chromatic";
    return {
        paint(image) {
            if (shades === undefined && !corrected)
                return image;
            for (let offset = 0; offset < image.data.length; offset += 4) {
                if (image.data[offset + 3] === 0)
                    continue;
                let rgb = [image.data[offset], image.data[offset + 1], image.data[offset + 2]];
                const mapped = shades?.get(rgb.map((channel) => channel.toString(16).padStart(2, "0")).join(""));
                if (mapped !== undefined)
                    rgb = [0, 2, 4].map((at) => Number.parseInt(mapped.slice(at, at + 2), 16));
                if (corrected)
                    rgb = chromaticDisplayColor(...rgb);
                image.data.set(rgb, offset);
            }
            return image;
        },
        details: { ...(input.paletteId === undefined ? {} : { paletteId: input.paletteId }), colorCorrection: corrected ? "chromatic" : "none" },
    };
}
export async function previewSprite(projectRoot, input, access) {
    const loaded = await loadSprite(projectRoot, input, access);
    const stateIndex = integer(input.stateIndex ?? 0, "stateIndex", 0, 31);
    const animationIndex = integer(input.animationIndex ?? 0, "animationIndex", 0, 7);
    const frameIndex = integer(input.frameIndex ?? 0, "frameIndex", 0, 31);
    const scale = integer(input.scale ?? enlargedScale(loaded.metadata, PREVIEW_FRAME_SIDE), "scale", 1, 8);
    const display = await spriteDisplay(loaded.projectRoot, input, access);
    const frame = selectedFrame(loaded.metadata, stateIndex, animationIndex, frameIndex);
    const source = PNG.sync.read(await readFile(await resolveProjectPath(loaded.projectRoot, loaded.assetPath, { mustExist: true })), {
        checkCRC: true,
    });
    const outputPath = input.outputPath ?? `artifacts/sprite-previews/${resourceSlug(String(loaded.metadata.name), "sprite")}-s${stateIndex}-a${animationIndex}-f${frameIndex}-x${scale}-${randomUUID()}.png`;
    return {
        id: String(loaded.metadata.id),
        scale,
        ...display.details,
        ...(await writePreview(loaded.projectRoot, outputPath, scaledImage(display.paint(compositeFrame(source, loaded.metadata, frame)), scale))),
    };
}
const FONT = {
    A: ["010", "101", "111", "101", "101"],
    C: ["111", "100", "100", "100", "111"],
    E: ["111", "100", "110", "100", "111"],
    F: ["111", "100", "110", "100", "100"],
    I: ["111", "010", "010", "010", "111"],
    M: ["101", "111", "111", "101", "101"],
    N: ["101", "111", "111", "111", "101"],
    O: ["111", "101", "101", "101", "111"],
    P: ["110", "101", "110", "100", "100"],
    R: ["110", "101", "110", "101", "101"],
    S: ["111", "100", "111", "001", "111"],
    T: ["111", "010", "010", "010", "010"],
    U: ["101", "101", "101", "101", "111"],
    V: ["101", "101", "101", "101", "010"],
    W: ["101", "101", "111", "111", "101"],
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "001", "001", "001"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
};
function fill(image, red, green, blue) {
    for (let offset = 0; offset < image.data.length; offset += 4) {
        image.data[offset] = red;
        image.data[offset + 1] = green;
        image.data[offset + 2] = blue;
        image.data[offset + 3] = 255;
    }
}
function drawText(image, text, originX, originY) {
    let cursor = originX;
    for (const character of text.toUpperCase()) {
        const glyph = FONT[character];
        if (glyph) {
            for (let row = 0; row < glyph.length; row += 1) {
                for (let column = 0; column < 3; column += 1) {
                    if (glyph[row]?.[column] !== "1")
                        continue;
                    const x = cursor + column;
                    const y = originY + row;
                    if (x < 0 || y < 0 || x >= image.width || y >= image.height)
                        continue;
                    const offset = (image.width * y + x) * 4;
                    image.data[offset] = 0xe0;
                    image.data[offset + 1] = 0xf8;
                    image.data[offset + 2] = 0xcf;
                    image.data[offset + 3] = 255;
                }
            }
        }
        cursor += 4;
    }
}
function blit(source, target, originX, originY) {
    for (let y = 0; y < source.height; y += 1) {
        for (let x = 0; x < source.width; x += 1) {
            const from = (source.width * y + x) * 4;
            if ((source.data[from + 3] ?? 0) === 0)
                continue;
            const to = (target.width * (originY + y) + originX + x) * 4;
            source.data.copy(target.data, to, from, from + 4);
        }
    }
}
export async function spriteContactSheet(projectRoot, input, access) {
    const loaded = await loadSprite(projectRoot, input, access);
    const stateIndex = integer(input.stateIndex ?? 0, "stateIndex", 0, 31);
    const columns = integer(input.columns ?? 4, "columns", 1, 8);
    const scale = integer(input.scale ?? enlargedScale(loaded.metadata, SHEET_FRAME_SIDE), "scale", 1, 8);
    const display = await spriteDisplay(loaded.projectRoot, input, access);
    const state = asObject(asArray(loaded.metadata.states, "states")[stateIndex], `state ${stateIndex}`);
    const frames = [];
    for (const [animationIndex, animationEntry] of asArray(state.animations, "animations").entries()) {
        const animation = asObject(animationEntry, `animation ${animationIndex}`);
        const animationFrames = asArray(animation.frames, `animation ${animationIndex} frames`).map((frameEntry, frameIndex) => asObject(frameEntry, `frame ${frameIndex}`));
        if (animationFrames.every((frame, frameIndex) => asArray(frame.tiles, `frame ${frameIndex} tiles`).length === 0))
            continue;
        for (const [frameIndex, frame] of animationFrames.entries()) {
            if (frames.length >= MAX_PREVIEW_FRAMES) {
                spriteError("SPRITE_PREVIEW_LIMIT", `Sprite contact sheets are limited to ${MAX_PREVIEW_FRAMES} authored frames.`);
            }
            frames.push({ animationIndex, frameIndex, frame });
        }
    }
    if (frames.length === 0)
        spriteError("SPRITE_PREVIEW_EMPTY", "The selected sprite state contains no visible authored frames.");
    const source = PNG.sync.read(await readFile(await resolveProjectPath(loaded.projectRoot, loaded.assetPath, { mustExist: true })), {
        checkCRC: true,
    });
    const frameWidth = integer(asNumber(loaded.metadata.canvasWidth, 16), "sprite canvasWidth", 1, 256) * scale;
    const frameHeight = integer(asNumber(loaded.metadata.canvasHeight, 16), "sprite canvasHeight", 1, 256) * scale;
    const cellWidth = Math.max(frameWidth + 8, 52);
    const cellHeight = frameHeight + 15;
    const rows = Math.ceil(frames.length / columns);
    const image = new PNG({ width: Math.max(cellWidth * columns + 8, 92), height: rows * cellHeight + 20 });
    fill(image, 0x07, 0x18, 0x21);
    drawText(image, "SOURCE SPRITE PREVIEW", 4, 5);
    frames.forEach(({ animationIndex, frameIndex, frame }, index) => {
        const x = (index % columns) * cellWidth + 5;
        const y = Math.floor(index / columns) * cellHeight + 16;
        blit(scaledImage(display.paint(compositeFrame(source, loaded.metadata, frame)), scale), image, x, y);
        drawText(image, `A${animationIndex} F${frameIndex}`, x, y + frameHeight + 3);
    });
    return {
        id: String(loaded.metadata.id),
        scale,
        ...display.details,
        ...(await writePreview(loaded.projectRoot, input.outputPath, image)),
        frameCount: frames.length,
        frames: frames.map(({ animationIndex, frameIndex }) => ({ animationIndex, frameIndex })),
    };
}
//# sourceMappingURL=sprites.js.map