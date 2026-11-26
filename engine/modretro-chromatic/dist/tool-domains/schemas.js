import { z } from "zod";
import { nativeTitleAtlasSchema } from "../native-title-atlas.js";
import { MAX_EMULATOR_FRAMES, MAX_EMULATOR_INSPECTION_BYTES, MAX_EMULATOR_OAM_OBJECTS, MAX_EMULATOR_STEP_INPUTS, MAX_EMULATOR_STEP_SAMPLES, } from "../emulator.js";
import { BUNDLED_TRACKS, DUTY_INSTRUMENTS, WAVE_INSTRUMENTS } from "../audio.js";
export const identifier = z.string().trim().min(1).max(256);
// Express the compiler's canonical decimal/safe-integer limit in JSON Schema as well as the service.
const variableId = z.string().trim().regex(/^(?:0|[1-9]\d{0,14}|[1-8]\d{15}|900[0-6]\d{12}|90070\d{11}|90071[0-8]\d{10}|900719[0-8]\d{9}|9007199[0-1]\d{8}|90071992[0-4]\d{7}|900719925[0-3]\d{6}|9007199254[0-6]\d{5}|90071992547[0-3]\d{4}|9007199254740[0-8]\d{2}|90071992547409[0-8]\d|900719925474099[01])$/u)
    .describe("Canonical nonnegative decimal string, e.g. 0 or 12: no leading zeros; maximum 9007199254740991. This is an authored ID, not an emulator memory address.");
const variableSymbol = z.string().trim().max(256).regex(/^var_[A-Za-z][A-Za-z0-9_]*$/u)
    .describe("Optional compiler symbol, e.g. var_audit_counter. Must begin with var_ followed by an ASCII letter, then letters, digits or underscores. Omit to retain the existing symbol or generate one from a new variable's name.");
export const boundedPath = z.string().trim().min(1).max(4_096).refine((value) => !value.includes("\0"), "Paths must not contain NUL characters.");
export const boundedName = z.string().trim().min(1).max(200);
export const direction = z.enum(["up", "down", "left", "right"]);
export const coordinate = z.number().int().min(0).max(65_535);
export const tileCoordinate = z.number().int().min(0).max(255);
export const dimension = z.number().int().min(1).max(4_096);
export const customProperties = z.record(z.string(), z.unknown());
export const revision = z.string().trim().min(1).max(256);
export const paletteColor = z.string().regex(/^#?[\da-fA-F]{6}$/u);
const colorCorrectionOption = z.enum(["none", "chromatic"])
    .describe("none (default) writes the palette's exact colors; chromatic applies the color correction the hermretro player uses, an approximation of the Chromatic's screen.");
const paletteColors = z.array(paletteColor).min(3).max(4)
    .describe("Four colors, lightest to darkest; or three for a sprite palette (lightest, middle, darkest), stored as entries 0, 1 and 3 because sprites never show entry 2. Three colors in an update keep the palette's entry 2.");
export const emulatorButton = z.enum(["a", "b", "up", "down", "left", "right", "start", "select"]);
/** A step's frame count; the engine refuses 0 with a pointer to emulator_observe instead of a bare range error. */
export const frameCount = z.number().int().min(0).max(MAX_EMULATOR_FRAMES);
export const imageLayoutSchema = z.enum(["individual", "contact-sheet"]);
const emulatorButtonSet = z.array(emulatorButton).max(8).refine((buttons) => new Set(buttons).size === buttons.length, "Buttons must be unique.");
export const emulatorColorCorrection = colorCorrectionOption
    .describe("none (default) returns the emulator's colors; chromatic shows color-hardware frames with the hermretro player's color correction, an approximation of the Chromatic's screen. A monochrome session, including a dual-mode cartridge run as DMG, keeps the emulator's colors. Sample hashes stay those of the native frames.");
const emulatorImageOptions = {
    includeImages: z.boolean().optional(),
    imageLayout: imageLayoutSchema.optional(),
    scale: z.number().int().min(1).max(4).optional().describe("Enlarge returned images 1–4× with square pixels (contact sheets default to 2×); sample hashes stay those of the native frames."),
    colorCorrection: emulatorColorCorrection.optional(),
    detail: z.enum(["compact", "full"]).optional().describe("compact (default): frame, buttons, samples and recordingSpan. full returns every field the engine reports, such as the ROM, runtime, clock, recording state and retained sample paths."),
};
/** The live-state selectors emulator_debug takes, shared by emulator_step's debug request. */
export const liveStateSelectors = {
    variableIds: z.array(identifier).max(32).optional(),
    variableNames: z.array(identifier).max(32).optional().describe("Authored variable names or symbols: an exact match first, then the full name or symbol in any case, then the symbol without var_ (has_oil). Ambiguous names list their IDs. Omit both variable lists for every variable."),
    actors: z.union([z.literal("all"), z.array(identifier).min(1).max(20)]).optional().describe("Current-scene actors to report live, by authored name, ID or symbol (an exact match in any scene first, then the name in any case), or 'all'. The player is always reported; an actor of another scene is listed as not in the current scene, with its scene, or with each match's ID and scene when several match."),
    includeScene: z.boolean().optional(),
};
const spritePreviewColors = {
    paletteId: identifier.optional().describe("Draw the frame in this palette's sprite colors (entries 0, 1 and 3) instead of the source shades."),
    colorCorrection: colorCorrectionOption.optional(),
};
const backgroundImportOptions = z.object({ autoColor: z.boolean().optional() }).strict();
const simpleSpriteImport = z.object({
    profile: z.enum(["static", "static16x16", "directional", "directional48x16", "directional_animated", "directional_animated96x16", "metasprite", "template"]),
    templateAssetId: identifier.optional(),
    paletteIndex: z.number().int().min(0).max(7).optional().describe("Scene sprite palette slot (0-7) every tile uses in color mode; defaults to 0."),
    frameWidth: z.number().int().min(8).max(128).optional().describe("metasprite only: frame width, a multiple of 8."),
    frameHeight: z.number().int().min(16).max(128).optional().describe("metasprite only: frame height, a multiple of 16; the PNG is one row of frames this tall."),
    sceneType: z.string().trim().min(1).max(64).optional().describe("Scene type the sprite is for, e.g. TOPDOWN or PLATFORM; defaults to the project's default scene type. TOPDOWN on a 16 px top-down grid gives the 16-pixel profiles a 16x16 collision box."),
}).strict();
export const scriptTarget = z.object({
    sceneId: identifier,
    actorId: identifier.optional(),
    triggerId: identifier.optional(),
    scriptKey: z.string().trim().min(1).max(100).optional(),
    branchPath: z.array(z.object({ eventId: identifier, branch: identifier }).strict()).max(64).optional(),
}).strict();
const scriptEventTarget = scriptTarget.extend({
    eventId: identifier.optional().describe("The event to inspect or edit, the same as eventId beside target; give one of them."),
});
const collisionEdit = z.object({
    shape: z.enum(["tile", "rectangle"]),
    x: tileCoordinate,
    y: tileCoordinate,
    width: z.number().int().min(1).max(255).optional(),
    height: z.number().int().min(1).max(255).optional(),
    value: z.number().int().min(0).max(255),
    operation: z.enum(["replace", "or", "andNot"]).optional(),
}).strict();
const sceneBatchOperation = z.object({
    type: z.enum([
        "actor.create", "actor.update", "actor.delete", "actor_create", "actor_update", "actor_delete",
        "trigger.create", "trigger.update", "trigger.delete", "trigger_create", "trigger_update", "trigger_delete",
        "event.edit", "script.edit", "script_edit", "event_edit",
        "scene.transition", "scene_transition", "scene.update", "scene_update",
        "collision.edit", "collision_edit",
        "variable.upsert", "variable.delete", "variable.update", "variable_update",
    ]),
    clientId: identifier.optional(),
    input: customProperties.optional(),
    id: identifier.optional(),
    sceneId: identifier.optional(),
    actorId: identifier.optional(),
    triggerId: identifier.optional(),
    variableId: identifier.optional(),
    name: boundedName.optional(),
    x: coordinate.optional(),
    y: coordinate.optional(),
    width: dimension.optional(),
    height: dimension.optional(),
    direction: direction.optional(),
    spriteSheetId: identifier.optional(),
    properties: customProperties.optional(),
    action: z.enum(["insert", "update", "delete", "move", "upsert"]).optional(),
    target: scriptEventTarget.optional(),
    eventId: identifier.optional(),
    event: customProperties.optional(),
    patch: customProperties.optional(),
    index: z.number().int().min(0).max(10_000).optional(),
    beforeEventId: identifier.optional(),
    afterEventId: identifier.optional(),
    destinationSceneId: identifier.optional(),
    fadeSpeed: z.union([z.string().max(32), z.number().int().min(0).max(255)]).optional(),
    edits: z.array(collisionEdit).max(1_024).optional(),
    resetInvalid: z.boolean().optional(),
    symbol: identifier.optional(),
    expectedRevision: revision.optional(),
}).strict();
const assetLookup = {
    assetId: identifier.optional(),
    assetPath: boundedPath.optional(),
};
const spriteLookup = {
    ...assetLookup,
    spriteId: identifier.optional(),
    includeFrames: z.boolean().optional(),
};
const dialogueBase = {
    sceneId: identifier.optional(),
    actorId: identifier.optional(),
    triggerId: identifier.optional(),
    eventId: identifier.optional(),
    scriptKey: z.string().trim().min(1).max(100).optional(),
    text: z.union([z.string().max(20_000), z.array(z.string().max(20_000)).min(1).max(100)]).optional(),
    eventCommand: z.literal("EVENT_TEXT").optional(),
    fontId: identifier.optional(),
    avatarId: identifier.optional(),
    profile: z.enum(["auto", "conservative"]).optional(),
    maxWidthPx: z.number().int().min(1).max(160).optional(),
    maxVisibleLines: z.number().int().min(1).max(16).optional(),
};
const songRows = z.string().max(8_000)
    .describe("Rows separated by spaces: a note in scientific pitch (C4, F#3, Bb5), . to rest, - to hold; :N makes a row last N rows (C4:4).");
const songPulseInstrument = z.enum(Object.keys(DUTY_INSTRUMENTS));
const songWaveInstrument = z.enum(Object.keys(WAVE_INSTRUMENTS));
const songPulseChannel = z.union([songRows, z.object({ notes: songRows, instrument: songPulseInstrument.optional() }).strict()])
    .describe("A pulse channel's rows, C2–B7, or {notes, instrument} with lead, soft, pluck, square or thin.");
const songWaveChannel = z.union([songRows, z.object({ notes: songRows, instrument: songWaveInstrument.optional() }).strict()])
    .describe("The wave channel's rows, C1–B6, or {notes, instrument} with bass, mellow, saw or hollow.");
export const domainSchemas = {
    nativeTitleAtlas: nativeTitleAtlasSchema,
    actorInspect: z.object({ sceneId: identifier, actorId: identifier }).strict(),
    actorUpdate: z.object({
        sceneId: identifier, actorId: identifier, name: boundedName.optional(),
        x: tileCoordinate.optional(), y: tileCoordinate.optional(), direction: direction.optional(),
        spriteSheetId: identifier.optional(), properties: customProperties.optional(), expectedRevision: revision.optional(),
    }).strict(),
    actorDelete: z.object({ sceneId: identifier, actorId: identifier, expectedRevision: revision.optional() }).strict(),
    triggerInspect: z.object({ sceneId: identifier, triggerId: identifier }).strict(),
    triggerCreate: z.object({
        sceneId: identifier, name: boundedName, id: identifier.optional(), x: tileCoordinate, y: tileCoordinate,
        width: z.number().int().min(1).max(255).optional(), height: z.number().int().min(1).max(255).optional(),
        properties: customProperties.optional(), expectedRevision: revision.optional().describe("Exact scene resource revision: use scene_inspect.sceneRevision, not its whole-project revision."),
    }).strict(),
    triggerUpdate: z.object({
        sceneId: identifier, triggerId: identifier, name: boundedName.optional(), x: tileCoordinate.optional(), y: tileCoordinate.optional(),
        width: z.number().int().min(1).max(255).optional(), height: z.number().int().min(1).max(255).optional(),
        properties: customProperties.optional(), expectedRevision: revision.optional(),
    }).strict(),
    triggerDelete: z.object({ sceneId: identifier, triggerId: identifier, expectedRevision: revision.optional() }).strict(),
    sceneInspect: z.object({
        sceneId: identifier, includeScripts: z.boolean().optional(), maxActors: z.number().int().min(1).max(100).optional(),
        maxTriggers: z.number().int().min(1).max(100).optional(), maxEvents: z.number().int().min(1).max(250).optional(),
    }).strict(),
    sceneDelete: z.object({ sceneId: identifier, expectedRevision: revision.optional().describe("Whole-project revision from scene_inspect.revision or project_inspect.revision."), dryRun: z.boolean().optional() }).strict(),
    sceneApply: z.object({
        sceneId: identifier, operations: z.array(sceneBatchOperation).min(1).max(100),
        dryRun: z.boolean().optional(), expectedRevision: revision.optional().describe("Whole-project revision from scene_inspect.revision or project_inspect.revision; resource revisions are not interchangeable."),
    }).strict(),
    assetImport: z.object({
        assetPath: boundedPath.optional().describe("Destination: a PNG under assets/backgrounds or assets/sprites, a .uge or .mod under assets/music, or a .wav, .vgm or .vgz under assets/sounds. Required with kind unless assets is given."),
        kind: z.enum(["background", "sprite", "music", "sound"]).optional(), sourcePath: boundedPath.optional(),
        name: boundedName.optional(), id: identifier.optional(),
        background: backgroundImportOptions.optional(),
        sprite: z.discriminatedUnion("profile", [
            simpleSpriteImport,
            z.object({ profile: z.literal("native_metadata"), metadataPath: boundedPath,
                sourceSha256: z.string().regex(/^[a-f0-9]{64}$/i), metadataSha256: z.string().regex(/^[a-f0-9]{64}$/i),
            }).strict(),
        ]).optional(),
        assets: z.array(z.object({
            assetPath: boundedPath, kind: z.enum(["background", "sprite", "music", "sound"]), sourcePath: boundedPath.optional(),
            name: boundedName.optional(), id: identifier.optional(),
            background: backgroundImportOptions.optional(), sprite: simpleSpriteImport.optional(),
        }).strict()).min(1).max(32).optional().describe("Import several assets in one call instead of the single-asset fields; all are checked before any is written. native_metadata is not allowed here."),
        expectedRevision: revision.optional().describe("Required whole-project revision for native_metadata only."),
        dryRun: z.boolean().optional().describe("Validate the complete native_metadata import without publishing; defaults false."),
        detail: z.enum(["compact", "full"]).optional().describe("compact (default) returns each asset's id, paths and analysis; full adds a native_metadata import's ID map and pattern accounting."),
        // Keep a ZodObject: the MCP SDK cannot publish a top-level ZodEffects schema.
        // importAsset enforces the cross-field requirements before preparing any writes.
    }).strict(),
    assetInspect: z.object(assetLookup).strict(),
    musicCompose: z.object({
        assetPath: boundedPath.optional().describe("Destination .uge under assets/music. Defaults to assets/music/<bundled>.uge for a bundled track."),
        name: boundedName.optional(), id: identifier.optional(),
        bundled: z.enum(BUNDLED_TRACKS).optional().describe("Write a bundled original track instead of sections: bright-start (bouncy title), meadow-walk (easy overworld), cave-echo (slow minor dungeon), victory-lap (fanfare)."),
        ticksPerRow: z.number().int().min(2).max(20).optional().describe("Frames (1/60 s) each row lasts; with 4 rows to a beat 6 is 150 BPM, 7 about 128 (default), 8 about 112, 10 about 90."),
        instruments: z.object({
            pulse1: songPulseInstrument.optional(), pulse2: songPulseInstrument.optional(), wave: songWaveInstrument.optional(),
        }).strict().optional().describe("The song's instrument per channel (default pulse1 lead, pulse2 soft, wave bass); a section's channel can override it."),
        sections: z.array(z.object({
            name: z.string().trim().min(1).max(32),
            pulse1: songPulseChannel.optional(), pulse2: songPulseChannel.optional(), wave: songWaveChannel.optional(),
            noise: songRows.optional().describe("Drums: kick, snare, hat, . (rest) and - (hold), each with an optional :N."),
        }).strict()).min(1).max(16).optional().describe("Named passages. A channel left out is silent; a shorter channel holds to the section's longest."),
        order: z.array(z.string().trim().min(1).max(32)).min(1).max(64).optional().describe("Section names in playing order, repeats allowed; defaults to each section once. The song loops back to the start."),
        overwrite: z.boolean().optional().describe("Replace the song already at assetPath, keeping its ID and every event that plays it."),
    }).strict(),
    assetUpdate: z.object({
        ...assetLookup, name: boundedName.optional(), autoColor: z.boolean().optional(),
        copyTileColorsFrom: identifier.optional(), expectedRevision: revision.optional(), dryRun: z.boolean().optional(),
    }).strict(),
    assetDelete: z.object(assetLookup).strict(),
    spriteInspect: z.object(spriteLookup).strict(),
    spriteUpdate: z.object({
        ...spriteLookup, name: boundedName.optional(), animSpeed: z.number().int().min(0).max(255).optional(),
        boundsX: z.number().int().min(-128).max(127).optional(), boundsY: z.number().int().min(-128).max(127).optional(),
        boundsWidth: z.number().int().min(1).max(255).optional(), boundsHeight: z.number().int().min(1).max(255).optional(),
        stateIndex: z.number().int().min(0).max(31).optional().describe("Existing state to update when setting flipLeft or animationType; defaults to 0."), flipLeft: z.boolean().optional(),
        animationType: z.enum(["fixed", "multi", "multi_movement"]).optional(),
    }).strict(),
    spritePreview: z.object({
        ...spriteLookup, stateIndex: z.number().int().min(0).max(31).optional(),
        animationIndex: z.number().int().min(0).max(7).optional(), frameIndex: z.number().int().min(0).max(31).optional(),
        outputPath: boundedPath.optional(),
        scale: z.number().int().min(1).max(8).optional().describe("Integer enlargement; defaults to the largest that keeps the frame within 128 pixels."),
        ...spritePreviewColors,
    }).strict(),
    spriteContactSheet: z.object({
        ...spriteLookup, outputPath: boundedPath, columns: z.number().int().min(1).max(8).optional(),
        scale: z.number().int().min(1).max(8).optional().describe("Integer enlargement; defaults to the largest that keeps each frame within 64 pixels."),
        stateIndex: z.number().int().min(0).max(31).optional(),
        ...spritePreviewColors,
    }).strict(),
    paletteCreate: z.object({ name: boundedName, colors: paletteColors, id: identifier.optional() }).strict(),
    paletteUpdate: z.object({
        paletteId: identifier, name: boundedName.optional(), colors: paletteColors.optional(),
        updateDefaultColors: z.boolean().optional(),
    }).strict(),
    scenePaletteAssign: z.object({
        sceneId: identifier, target: z.enum(["background", "sprite"]), slot: z.number().int().min(0).max(7),
        paletteId: identifier, allowUiSlot: z.boolean().optional(),
    }).strict(),
    backgroundPalettePaint: z.object({
        backgroundId: identifier, sceneId: identifier.optional(),
        edits: z.array(z.object({
            x: tileCoordinate, y: tileCoordinate,
            width: z.number().int().min(1).max(255).optional(), height: z.number().int().min(1).max(255).optional(),
            slot: z.number().int().min(0).max(7),
        }).strict()).min(1).max(1_024),
    }).strict(),
    sceneGraphicsAnalyze: z.object({
        sceneId: identifier, detail: z.enum(["summary", "tiles"]).optional(),
        tileOffset: z.number().int().min(0).max(65_535).optional(), tileLimit: z.number().int().min(1).max(512).optional(),
        includeStaticOam: z.boolean().optional(),
    }).strict(),
    sceneGraphicsPreview: z.object({
        sceneId: identifier.optional(), sceneIds: z.array(identifier).min(1).max(16).optional(),
        outputPath: boundedPath, displayMode: z.enum(["color", "mono"]).optional(),
        colorCorrection: colorCorrectionOption.optional(), columns: z.number().int().min(1).max(8).optional(),
        magnification: z.number().int().min(1).max(4).optional().describe("Integer enlargement; defaults to 2, or 1 when the enlarged image would be too large."),
    }).strict(),
    scriptInspect: z.object({
        ...scriptTarget.partial().shape,
        target: scriptEventTarget.optional().describe("The same script as one object; give either target or sceneId with its optional actorId, triggerId, scriptKey and branchPath."),
        eventId: identifier.optional(),
    }).strict(),
    scriptEdit: z.object({
        action: z.enum(["insert", "update", "delete", "move"]), target: scriptEventTarget,
        eventId: identifier.optional(), event: customProperties.optional(), patch: customProperties.optional(),
        index: z.number().int().min(0).max(10_000).optional(), beforeEventId: identifier.optional(), afterEventId: identifier.optional(),
        expectedRevision: revision.optional().describe("Owner-resource revision returned by script_inspect for the same target, or the preceding successful script edit."),
    }).strict(),
    scriptTransition: z.object({
        target: scriptTarget, destinationSceneId: identifier, x: tileCoordinate, y: tileCoordinate,
        direction: direction.optional(), fadeSpeed: z.union([z.string().max(32), z.number().int().min(0).max(255)]).optional(),
        index: z.number().int().min(0).max(10_000).optional(), expectedRevision: revision.optional().describe("Owner-resource revision from script_inspect for the same source target."),
    }).strict(),
    eventDescribe: z.object({
        events: z.array(z.string().trim().min(1).max(64)).min(1).max(5).optional().describe('Up to 5 event commands to describe in full, e.g. ["EVENT_IF","EVENT_SET_VALUE"].'),
        query: z.string().trim().min(1).max(100).optional().describe("Words to find in an event's command, name, summary, category or arg names, e.g. sound or actor position."),
        category: z.string().trim().min(1).max(64).optional().describe("A category from the listing, e.g. Actor, Dialogue & Menus or Uncategorized."),
        includeDeprecated: z.boolean().optional().describe("List deprecated events too (default false); alone, lists every event."),
        cursor: z.string().regex(/^\d{1,4}$/).optional().describe("A listing's nextCursor, to list the matches after it."),
        detail: z.enum(["full", "compact"]).optional().describe("With events: compact leaves out descriptions and conditions (default full)."),
    }).strict(),
    variableInspect: z.object({ variableId: variableId.optional() }).strict(),
    variableSet: z.object({ variableId: variableId.optional(), name: boundedName.optional().describe("Required when creating a new variable; omit only to retain an existing name."), symbol: variableSymbol.optional(), expectedRevision: revision.optional().describe("Variable-resource revision returned by variable_inspect or the preceding successful variable edit.") }).strict(),
    variableDelete: z.object({ variableId, expectedRevision: revision.optional().describe("Variable-resource revision returned by variable_inspect or the preceding successful variable edit.") }).strict(),
    engineFieldInspect: z.object({
        fieldIds: z.array(identifier).max(250).optional(),
        limit: z.number().int().min(1).max(250).optional(),
    }).strict(),
    engineFieldUpdate: z.object({
        updates: z.array(z.object({
            id: identifier,
            value: z.union([z.string().max(1_024), z.number().int().safe().finite()]),
        }).strict()).min(1).max(100),
        expectedRevision: revision.optional(),
    }).strict(),
    collisionInspect: z.object({
        sceneId: identifier, x: tileCoordinate.optional(), y: tileCoordinate.optional(),
        width: z.number().int().min(1).max(255).optional(), height: z.number().int().min(1).max(255).optional(),
        maxCells: z.number().int().min(1).max(4_096).optional(),
    }).strict(),
    collisionEdit: z.object({ sceneId: identifier, edits: z.array(collisionEdit).min(1).max(1_024), resetInvalid: z.boolean().optional(), expectedRevision: revision.optional() }).strict(),
    dialogueAnalyze: z.object({
        ...dialogueBase, wrap: z.enum(["none", "word"]).optional(), paginate: z.boolean().optional(), includeSuggestion: z.boolean().optional(),
        eventLimit: z.number().int().min(1).max(2_048).optional(),
        pageLimit: z.number().int().min(1).max(4_096).optional(),
    }).strict(),
    dialoguePreview: z.object({
        ...dialogueBase, outputPath: boundedPath, pageIndex: z.number().int().min(0).max(4_095).optional(),
        pageIndices: z.array(z.number().int().min(0).max(4_095)).min(1).max(64).optional(),
        columns: z.number().int().min(1).max(8).optional(), magnification: z.number().int().min(1).max(4).optional(),
    }).strict(),
    worldDependencies: z.object({
        node: z.object({
            type: z.enum(["scene", "actor", "trigger", "asset", "palette", "variable", "script", "actorPrefab", "triggerPrefab", "settings"]),
            id: identifier,
        }).strict(),
        direction: z.enum(["incoming", "outgoing", "both"]).optional(),
        relations: z.array(z.string().trim().min(1).max(64)).max(32).optional(),
        sceneId: identifier.optional(),
        depth: z.union([z.literal(1), z.literal(2), z.literal(3)]).optional(),
        limit: z.number().int().min(1).max(250).optional(),
        cursor: z.string().min(1).max(2_048).optional(),
        coverageCursor: z.string().min(1).max(2_048).optional(),
    }).strict(),
    emulatorStep: z.object({
        buttons: emulatorButtonSet.optional().describe("With frames, for one held set: the complete set of held buttons; [] is neutral."),
        frames: frameCount.optional().describe("With buttons: native frames to advance, at least 1. To look without advancing, use emulator_observe."),
        sampleCount: z.number().int().min(0).max(MAX_EMULATOR_STEP_SAMPLES).optional().describe("With buttons and frames: evenly spaced samples ending on the last frame, at least 1; defaults to 1. For no images, set includeImages:false."),
        inputs: z.array(z.object({
            buttons: emulatorButtonSet.describe("The complete set of held buttons for this input; [] is neutral."),
            frames: frameCount.describe("Native frames to hold this set, at least 1."),
            sample: z.boolean().optional().describe("Also sample this input's last frame; the last input is always sampled."),
        }).strict()).max(MAX_EMULATOR_STEP_INPUTS).optional().describe("Instead of buttons and frames: ordered inputs run in this one call, at most 3,600 frames and 8 samples in all. Press, wait, press again: [{buttons:['a'],frames:2},{buttons:[],frames:30},{buttons:['a'],frames:2}]."),
        debug: z.object({
            ...liveStateSelectors,
            variableNames: liveStateSelectors.variableNames.describe("Authored variable names or symbols, matched as emulator_debug matches them. Only the variables named here or in variableIds are reported."),
        }).strict().optional().describe("Also return the live state on the last frame, as emulator_debug reads it: live (the player, ui with the dialogue or menu and the buttons input accepts, scripts), the scene unless includeScene:false, and the actors and variables named. {} asks for live and the scene. Needs source mode; a refusal comes back in debug, and the step still ran. If the emulator stopped during the read, session.status is lost."),
        ...emulatorImageOptions,
    }).strict(),
    emulatorObserve: z.object(emulatorImageOptions).strict(),
    emulatorInspect: z.object({
        view: z.enum(["oam", "memory", "vram"]).describe("oam reads hardware sprite objects; memory and vram read a bounded byte range."),
        visibleOnly: z.boolean().optional().describe("oam only: filter out objects not visible on screen."),
        limit: z.number().int().min(1).max(MAX_EMULATOR_OAM_OBJECTS).optional().describe("oam only: maximum objects to return."),
        includeScanlineSummary: z.boolean().optional().describe("oam only: include peak sprite count, peak scanlines, and the count of scanlines over the hardware limit."),
        region: z.enum(["vram", "wram", "oam", "hram"]).optional().describe("Required for memory and vram; the vram view requires region vram."),
        offset: z.number().int().min(0).max(65_535).optional().describe("Required for memory and vram: zero-based byte offset within the region, not an absolute CPU address."),
        length: z.number().int().min(1).max(MAX_EMULATOR_INSPECTION_BYTES).optional().describe("Required for memory and vram: byte count; the full range must fit within the region."),
        bank: z.number().int().min(0).max(7).optional().describe("memory/vram only: optional for VRAM (0–1) or WRAM (0–7). A banked WRAM range must fit within 4 KiB."),
    }).strict(),
};
//# sourceMappingURL=schemas.js.map