import path from "node:path";
import { z } from "zod";
import { deleteActor, inspectActor, updateActor } from "../actors.js";
import { deleteAsset, importAsset, inspectAsset, updateAsset } from "../assets.js";
import { composeMusic } from "../audio.js";
import { editCollisions, inspectCollisions } from "../collisions.js";
import { previewDialogue } from "../dialogue-preview.js";
import { analyzeDialogue } from "../dialogue.js";
import { inspectEngineFields, updateEngineFields } from "../engine-fields.js";
import { describeEvents } from "../event-catalog.js";
import { createSceneTransition, editScript, inspectScript, liftTargetEventId } from "../game-scripts.js";
import { inspectVariables, updateVariable } from "../game-variables.js";
import { updateNativeTitleAtlas } from "../native-title-atlas.js";
import { assignScenePalette, createPalette, inspectPalettes, paintBackgroundPalette, updatePalette, } from "../palettes.js";
import { GameStudioProjectError } from "../project.js";
import { applySceneBatch, deleteScene, inspectScene } from "../scene-batch.js";
import { analyzeSceneGraphics, previewSceneContactSheet, previewSceneGraphics } from "../scene-graphics.js";
import { inspectSprite, previewSprite, spriteContactSheet, updateSprite } from "../sprites.js";
import { createTrigger, deleteTrigger, inspectTrigger, updateTrigger } from "../triggers.js";
import { worldDependencies } from "../world-queries.js";
import { domainSchemas } from "./schemas.js";
import { registerTilemapTools } from "./tilemap.js";
const readOnly = {
    readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false,
};
const createOnly = {
    readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false,
};
const updateExisting = {
    readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false,
};
function inspectedScriptTarget({ target, eventId: _eventId, ...flat }) {
    if (target !== undefined && Object.keys(flat).length > 0) {
        throw new GameStudioProjectError("INVALID_INPUT", "Give the script as target or as sceneId with its actorId, triggerId, scriptKey and branchPath, not both");
    }
    if (target === undefined && flat.sceneId === undefined) {
        throw new GameStudioProjectError("INVALID_INPUT", "script_inspect requires sceneId, with optional actorId, triggerId, scriptKey and branchPath");
    }
    return target ?? flat;
}
/** Register bounded domain-first project editing and readback operations. */
export function registerProjectDomains(server, context) {
    registerTilemapTools(server, context);
    function inspect(operation) {
        return context.safely(() => context.runRead(operation));
    }
    function mutate(operation, committedPaths) {
        return context.safely(() => context.runMutation(async (project, access) => {
            const result = await operation(project, access);
            const paths = committedPaths?.(result, project) ?? [];
            if (paths.length > 0)
                await access.noteCommittedPaths(paths);
            return result;
        }));
    }
    function transact(operation) {
        return context.safely(() => context.runTransaction(operation));
    }
    function authoredOutput(result, project) {
        const outputPath = "outputPath" in result ? result.outputPath : result.path;
        const relative = path.relative(project.projectRoot, path.resolve(project.projectRoot, outputPath));
        const normalized = relative.split(path.sep).join("/");
        return normalized.startsWith("project/") || normalized.startsWith("assets/")
            ? [relative]
            : [];
    }
    server.registerTool("scene_inspect", {
        title: "Inspect one scene", description: "Read a scene and up to 25 actors and 25 triggers. Returns project revision for scene_apply/delete and exact sceneRevision for trigger_create or scene-owned script edits. Scripts are omitted by default; use script_inspect for one event or branch. Check truncated for omissions.",
        inputSchema: domainSchemas.sceneInspect, annotations: readOnly,
    }, async (input) => inspect((project, access) => inspectScene(project.projectPath, input, access)));
    server.registerTool("scene_delete", {
        title: "Delete a scene", description: "Delete an unreferenced scene, or use dryRun to preview. Guard with scene_inspect.revision (the whole-project revision).",
        inputSchema: domainSchemas.sceneDelete, annotations: updateExisting,
    }, async (input) => transact((project, access) => deleteScene(project.projectPath, input, access)));
    server.registerTool("scene_apply", {
        title: "Apply a bounded scene transaction", description: "Apply 1–100 ordered scene, actor, trigger, event, collision, or variable edits. Guard with scene_inspect.revision; dryRun previews without writing. Distributed projects have best-effort rollback, not cross-file atomicity.",
        inputSchema: domainSchemas.sceneApply, annotations: updateExisting,
    }, async (input) => transact((project, access) => applySceneBatch(project.projectPath, input, access)));
    server.registerTool("actor_inspect", {
        title: "Inspect actor", description: "Read one scene actor and its current resource revision without modifying the project.",
        inputSchema: domainSchemas.actorInspect, annotations: readOnly,
    }, async (input) => inspect((project, access) => inspectActor(project.projectPath, input, access)));
    server.registerTool("actor_update", {
        title: "Update actor", description: "Update one existing actor's position, sprite, facing direction, or editable metadata.",
        inputSchema: domainSchemas.actorUpdate, annotations: updateExisting,
    }, async (input) => mutate((project, access) => updateActor(project.projectPath, input, access)));
    server.registerTool("actor_delete", {
        title: "Delete actor", description: "Delete one unreferenced actor without changing unrelated scene or script resources.",
        inputSchema: domainSchemas.actorDelete, annotations: updateExisting,
    }, async (input) => mutate((project, access) => deleteActor(project.projectPath, input, access)));
    server.registerTool("trigger_inspect", {
        title: "Inspect trigger", description: "Read one scene trigger, its bounds, scripts, and stable resource revision.",
        inputSchema: domainSchemas.triggerInspect, annotations: readOnly,
    }, async (input) => inspect((project, access) => inspectTrigger(project.projectPath, input, access)));
    server.registerTool("trigger_create", {
        title: "Create trigger", description: "Create a bounded native scene trigger without replacing existing resources. Guard with scene_inspect.sceneRevision.",
        inputSchema: domainSchemas.triggerCreate, annotations: createOnly,
    }, async (input) => mutate((project, access) => createTrigger(project.projectPath, input, access)));
    server.registerTool("trigger_update", {
        title: "Update trigger", description: "Update an existing trigger's name, position, dimensions, or editable properties.",
        inputSchema: domainSchemas.triggerUpdate, annotations: updateExisting,
    }, async (input) => mutate((project, access) => updateTrigger(project.projectPath, input, access)));
    server.registerTool("trigger_delete", {
        title: "Delete trigger", description: "Delete one unreferenced trigger while preserving unrelated gameplay resources.",
        inputSchema: domainSchemas.triggerDelete, annotations: updateExisting,
    }, async (input) => mutate((project, access) => deleteTrigger(project.projectPath, input, access)));
    server.registerTool("asset_import", {
        title: "Import an image or audio asset", description: "Register project-local PNGs, music and sound effects as native assets: one with assetPath and kind, or up to 32 in assets (all or none). Music is a hUGETracker .uge or a four-channel .mod; a sound is a .wav (up to about 3.6 s) or a Game Boy .vgm/.vgz. The tool checks an audio file, writes its sidecar with an ID that stays the same, and returns a playEvent (EVENT_MUSIC_PLAY or EVENT_SOUND_PLAY_EFFECT) to add to a script; to write music from notes, use music_compose. Sprite profiles: static 16x16, directional 48x16, directional_animated 96x16, metasprite (a row of frameWidth x frameHeight frames, e.g. 32x32, built from 8x16 tiles), template. sprite.paletteIndex picks the scene sprite palette slot (0-7) for every tile. Generated profiles need the project's 8x16 sprite mode. A metasprite's collision box covers its whole frame; TOPDOWN sprites (sprite.sceneType, default the project's default scene type) on a 16 px top-down grid get a 16x16 box from the 16-pixel profiles. Each result includes the graphics analysis (status, tile budget as GB Studio compiles it, violations). native_metadata imports a complete sprite PNG/JSON pair: requires sourcePath, sprite.metadataPath, sourceSha256, metadataSha256 and a fresh whole-project expectedRevision. It creates only new outputs, supports dryRun, and returns the complete deterministic ID map with detail:'full'. Source paths stay inside the selected project. Actor rebinding is a separate guarded operation; do not replay an uncertain import.",
        inputSchema: domainSchemas.assetImport, annotations: createOnly,
    }, async (input) => input.sprite?.profile === "native_metadata" ? transact((project, access) => importAsset(project.projectRoot, input, access)) : mutate((project, access) => importAsset(project.projectRoot, input, access), (result) => (result.imported ?? [result]).flatMap((asset) => [asset.assetPath, asset.metadataPath])));
    server.registerTool("asset_inspect", {
        title: "Inspect an asset", description: "Read a native background, sprite, song or sound and its sidecar metadata. Provide assetId or assetPath; if both are supplied, they must identify the same asset.",
        inputSchema: domainSchemas.assetInspect, annotations: readOnly,
    }, async (input) => inspect((project, access) => inspectAsset(project.projectRoot, input, access)));
    server.registerTool("music_compose", {
        title: "Write a song", description: "Write an original song from note lists as a hUGETracker .uge under assets/music and register it with an ID that stays the same; returns the ID, the loop length and a playEvent (EVENT_MUSIC_PLAY) to add to a script. Give sections and an order, or bundled for a ready track. Channels: pulse1 (melody), pulse2 (harmony), wave (bass) and noise (drums). Each channel is a list of rows; a note rings until the next note or rest. Example section: {name:'A', pulse1:'C5:2 E5:2 G5:4 . -:3', wave:'C3:4 G2:4', noise:'kick:2 hat:2 snare:2 hat:2'}. Songs loop.",
        inputSchema: domainSchemas.musicCompose, annotations: updateExisting,
    }, async (input) => mutate((project, access) => composeMusic(project.projectRoot, input, access), (result) => [result.assetPath, result.metadataPath]));
    server.registerTool("asset_update", {
        title: "Update image asset", description: "Update native sidecar properties, or initialize replacement background palette assignments with copyTileColorsFrom and expectedRevision. Palette transfer preserves existing UI cells, requires equal dimensions, and supports dryRun.",
        inputSchema: domainSchemas.assetUpdate, annotations: updateExisting,
    }, async (input) => input.copyTileColorsFrom !== undefined ? transact((project, access) => updateAsset(project.projectPath, input, access)) : mutate((project, access) => updateAsset(project.projectRoot, input, access), (result) => [result.metadataPath]));
    server.registerTool("asset_delete", {
        title: "Delete image asset", description: "Delete one unreferenced native image and its sidecar. Provide assetId or assetPath; if both are supplied, they must identify the same asset.",
        inputSchema: domainSchemas.assetDelete, annotations: updateExisting,
    }, async (input) => mutate((project, access) => deleteAsset(project.projectRoot, input, access), (result) => [result.assetPath, result.metadataPath]));
    server.registerTool("native_graphics_update", {
        title: "Update a supported native graphics atlas",
        description: "Apply inert atlas data to the supported wrecklight-title-v1 renderer only. Requires a whole-project expectedRevision and the complete current-header digest in the contract; dryRun previews. Preserves animation, attributes, font and credits. The contract path is informational, not a destination. Plugin files are outside the public project revision, so use the returned headerSha256 for the next preimage. This does not update dependency profiles or prove rendered output.",
        inputSchema: domainSchemas.nativeTitleAtlas, annotations: updateExisting,
    }, async (input) => transact((project, access) => updateNativeTitleAtlas(project.projectPath, input, access)));
    server.registerTool("sprite_inspect", {
        title: "Inspect sprite animation", description: "Inspect genuine sprite states, animation slots, frame counts, object bounds, and optional bounded frame metadata.",
        inputSchema: domainSchemas.spriteInspect, annotations: readOnly,
    }, async (input) => inspect((project, access) => inspectSprite(project.projectRoot, input, access)));
    server.registerTool("sprite_edit", {
        title: "Update sprite metadata", description: "Update native sprite animation speed, collision bounds, state settings, or displayed name.",
        inputSchema: domainSchemas.spriteUpdate, annotations: updateExisting,
    }, async (input) => mutate((project, access) => updateSprite(project.projectRoot, input, access), (result) => [result.metadataPath]));
    server.registerTool("sprite_preview", {
        title: "Preview authored sprite", description: "Write one labeled authored sprite frame, enlarged by default and optionally in a palette's sprite colors; this is not an emulator framebuffer. Omit outputPath for a unique capture, or supply a new PNG path.",
        inputSchema: domainSchemas.spritePreview, annotations: updateExisting,
    }, async (input) => mutate((project, access) => previewSprite(project.projectRoot, input, access), authoredOutput));
    server.registerTool("sprite_contact_sheet", {
        title: "Preview sprite animation frames", description: "Write a labeled bounded sprite-source animation sheet, enlarged by default and optionally in a palette's sprite colors, without claiming genuine gameplay-frame provenance.",
        inputSchema: domainSchemas.spriteContactSheet, annotations: updateExisting,
    }, async (input) => mutate((project, access) => spriteContactSheet(project.projectRoot, input, access), authoredOutput));
    server.registerTool("palette_inspect", {
        title: "Inspect project palettes", description: "Read one project-global four-color palette by paletteId, or list a bounded page. Returns the reserved UI palette and affected scene counts. Follow nextCursor to continue; if the project changes, restart without cursor.",
        inputSchema: z.object({
            paletteId: z.string().trim().min(1).max(256).optional().describe("Exact palette ID. Returns one item in palettes; omit limit and cursor."),
            limit: z.number().int().min(1).max(250).optional().describe("Maximum palettes to list per page (default 250); the response byte limit can return fewer. Omit with paletteId."),
            cursor: z.string().min(1).max(2048).optional().describe("Use the prior nextCursor to continue the same project listing. Omit with paletteId; restart without cursor after a project change."),
        }).strict(), annotations: readOnly,
    }, async (input) => inspect((project, access) => inspectPalettes(project.projectPath, access, input)));
    server.registerTool("palette_create", {
        title: "Create a color palette", description: "Create one genuine project-global Game Boy Color palette: four RGB colors, or three for a sprite palette.",
        inputSchema: domainSchemas.paletteCreate, annotations: createOnly,
    }, async (input) => mutate((project, access) => createPalette(project.projectPath, input, access), (result) => [result.resourcePath]));
    server.registerTool("palette_update", {
        title: "Update a color palette", description: "Update an existing shared palette while preserving authored default colors unless explicitly requested.",
        inputSchema: domainSchemas.paletteUpdate, annotations: updateExisting,
    }, async (input) => mutate((project, access) => updatePalette(project.projectPath, input, access), (result) => [result.resourcePath]));
    server.registerTool("palette_assign", {
        title: "Assign scene palette", description: "Assign one actual background or object palette slot while protecting the reserved UI slot by default. A sprite slot returns the three colors sprites show and warns when entry 2 holds a color they never draw.",
        inputSchema: domainSchemas.scenePaletteAssign, annotations: updateExisting,
    }, async (input) => mutate((project, access) => assignScenePalette(project.projectPath, input, access), (result) => [result.resourcePath]));
    server.registerTool("palette_paint", {
        title: "Paint background palette tiles", description: "Change native tile-color assignments on an unbound background without rewriting PNG pixels. For a background bound to a tilemap recipe, use tilemap_inspect then tilemap_edit replace_cells with unchanged pixel hashes; this direct tool does not update the recipe.",
        inputSchema: domainSchemas.backgroundPalettePaint, annotations: updateExisting,
    }, async (input) => mutate((project, access) => paintBackgroundPalette(project.projectPath, input, access), (result) => [result.resourcePath]));
    server.registerTool("graphics_analyze_scene", {
        title: "Analyze scene graphics budgets", description: "Analyze authored background tiles, palette slots, sprite metadata, and engine/hardware budgets. Sprite usage estimates do not establish compiled allocation. Static actor scanline estimates exclude the player and do not establish simultaneous visibility; use emulator frames for runtime evidence.",
        inputSchema: domainSchemas.sceneGraphicsAnalyze, annotations: readOnly,
    }, async (input) => inspect((project, access) => analyzeSceneGraphics(project.projectPath, input, access)));
    server.registerTool("graphics_preview_scene", {
        title: "Preview authored scene colors", description: "Write a static background color projection for sceneId, or an ordered contact sheet for 1–16 distinct sceneIds. Supply one form and a new PNG path; neither mode overwrites files. Output is enlarged 2x by default (magnification 1–4); columns apply only to sheets. colorCorrection chromatic approximates the Chromatic's display. Actors, UI, camera motion, and runtime gameplay are not shown.",
        inputSchema: domainSchemas.sceneGraphicsPreview, annotations: updateExisting,
    }, async (input) => mutate((project, access) => {
        const { sceneId, sceneIds, columns, ...options } = input;
        if (sceneIds !== undefined) {
            if (sceneId !== undefined)
                throw new Error("Supply sceneId or sceneIds, not both.");
            return previewSceneContactSheet(project.projectPath, { ...options, sceneIds, columns }, access);
        }
        if (sceneId === undefined || columns !== undefined) {
            throw new Error("Supply sceneId for a single preview, or sceneIds for contact-sheet layout options.");
        }
        return previewSceneGraphics(project.projectPath, { ...options, sceneId }, access);
    }, (result, project) => typeof result.outputPath === "string"
        ? authoredOutput({ outputPath: result.outputPath }, project)
        : []));
    server.registerTool("script_inspect", {
        title: "Inspect gameplay script", description: "Read one scene, actor, trigger, or nested event-branch script, named by sceneId with optional actorId, triggerId, scriptKey and branchPath (or the same fields as target). Returns its owner-resource revision for script_edit or script_transition; this differs from the project revision.",
        inputSchema: domainSchemas.scriptInspect, annotations: readOnly,
    }, async (input) => context.safely(() => {
        const request = liftTargetEventId({ target: inspectedScriptTarget(input), ...(input.eventId === undefined ? {} : { eventId: input.eventId }) });
        return context.runRead((project, access) => inspectScript(project.projectPath, request, access));
    }));
    server.registerTool("script_edit", {
        title: "Edit gameplay script event", description: "Insert, update, delete, or reorder one native event. Guard with script_inspect.revision for the same target; the returned revision can guard the next edit.",
        inputSchema: domainSchemas.scriptEdit, annotations: updateExisting,
    }, async (input) => mutate((project, access) => editScript(project.projectPath, liftTargetEventId(input), access)));
    server.registerTool("script_transition", {
        title: "Create a scene transition", description: "Insert a typed scene-switch event after checking its destination and coordinate bounds. Inspect destination collisions separately for passability. Guard with script_inspect.revision for the same source target.",
        inputSchema: domainSchemas.scriptTransition, annotations: updateExisting,
    }, async (input) => mutate((project, access) => createSceneTransition(project.projectPath, input, access)));
    server.registerTool("event_describe", {
        title: "Describe GB Studio events", description: "Look up GB Studio's script events. With no arguments, list the categories; with query, category or includeDeprecated, list matching events (command, name, one-line summary; 40 at a time, nextCursor for more); with events, describe up to 5: every arg with its type, default, allowed values and the conditions under which it is used, child branches, warnings, deprecation with its replacement and how to convert, what the event needs first, and an example to adapt. Read from GB Studio's own event definitions; needs no project.",
        inputSchema: domainSchemas.eventDescribe, annotations: readOnly,
    }, async (input) => context.safely(() => describeEvents(input)));
    server.registerTool("variable_inspect", {
        title: "Inspect named game variables", description: "Read authored global variable metadata and its resource revision. Use emulator_debug for live values; this tool does not read runtime memory.",
        inputSchema: domainSchemas.variableInspect, annotations: readOnly,
    }, async (input) => inspect((project, access) => inspectVariables(project.projectPath, input, access)));
    server.registerTool("variable_set", {
        title: "Create or update a named variable", description: "Create or update an authored global variable. Provide a name for a new variable; omit its ID or symbol for automatic defaults, or supply a decimal ID and var_<identifier> symbol. Guard with variable_inspect.revision; this does not change live emulator memory.",
        inputSchema: domainSchemas.variableSet, annotations: updateExisting,
    }, async (input) => mutate((project, access) => updateVariable(project.projectPath, { ...input, action: "upsert" }, access)));
    server.registerTool("variable_delete", {
        title: "Delete a named variable", description: "Delete an unreferenced authored global variable; guard with variable_inspect.revision. Use world_dependencies if deletion is blocked. This does not change live emulator memory.",
        inputSchema: domainSchemas.variableDelete, annotations: updateExisting,
    }, async (input) => mutate((project, access) => updateVariable(project.projectPath, { ...input, action: "delete" }, access)));
    server.registerTool("engine_field_inspect", {
        title: "Inspect native engine field overrides",
        description: "Read bounded native engine-field overrides, preserving numeric checkbox values and the resource's exact revision.",
        inputSchema: domainSchemas.engineFieldInspect, annotations: readOnly,
    }, async (input) => inspect((project, access) => inspectEngineFields(project.projectPath, input, access)));
    server.registerTool("engine_field_update", {
        title: "Update native engine field overrides",
        description: "Safely update or append bounded native engine-field overrides with numeric checkbox validation and optional optimistic resource revisions.",
        inputSchema: domainSchemas.engineFieldUpdate, annotations: updateExisting,
    }, async (input) => mutate((project, access) => updateEngineFields(project.projectPath, input, access)));
    server.registerTool("collision_inspect", {
        title: "Inspect scene collision tiles", description: "Decode a bounded rectangular sample of the selected scene's actual hexadecimal collision grid.",
        inputSchema: domainSchemas.collisionInspect, annotations: readOnly,
    }, async (input) => inspect((project, access) => inspectCollisions(project.projectPath, input, access)));
    server.registerTool("collision_edit", {
        title: "Edit scene collision tiles", description: "Change bounded collision tiles or rectangles in an unbound scene. For a bound tilemap use tilemap_edit to synchronize its recipe. Untouched bytes stay intact; resetInvalid explicitly replaces a malformed grid with zeros before editing.",
        inputSchema: domainSchemas.collisionEdit, annotations: updateExisting,
    }, async (input) => mutate((project, access) => editCollisions(project.projectPath, input, access)));
    server.registerTool("dialogue_analyze", {
        title: "Analyze authored dialogue fit", description: "Measure real selected-font glyph widths, explicit authored pages, dialogue-card layouts, overflow, and optional safe wrapping suggestions.",
        inputSchema: domainSchemas.dialogueAnalyze, annotations: readOnly,
    }, async (input) => inspect((project, access) => analyzeDialogue(project.projectPath, input, access)));
    server.registerTool("dialogue_preview", {
        title: "Preview authored dialogue", description: "Write a bounded native-size font-aware static dialogue preview explicitly labeled as not emulator or runtime verified.",
        inputSchema: domainSchemas.dialoguePreview, annotations: updateExisting,
    }, async (input) => mutate((project, access) => previewDialogue(project.projectPath, input, access), authoredOutput));
    server.registerTool("world_dependencies", {
        title: "Inspect indexed gameplay dependencies",
        description: "Read gameplay relationships and semantic coverage without changing project files. Page references with cursor and coverage reasons with coverageCursor; both retain totals and generation-bound cursors within 32 KiB. Coverage can be incomplete because of unresolved native references or unsupported custom-event sources, authored contract, or invocation; compiling, retrying or adopting a tilemap cannot establish an unsupported custom-event contract.",
        inputSchema: domainSchemas.worldDependencies, annotations: readOnly,
    }, async (input) => inspect((_project, access) => worldDependencies(access, input)));
}
//# sourceMappingURL=register.js.map