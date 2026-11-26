import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { z } from "zod";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { prepareToolchain } from "./toolchain-prepare.js";
import { inventoryProjectNormalized } from "./project-snapshot.js";
import { readPlatformEnvironmentVariable } from "./platform.js";
import { GameStudioProjectError, inventoryProject, inspectProject, createScene, updateScene, createActor, updateDialogue, updateSettings } from "./project.js";
import { ProjectTransactionError, withProjectMutation } from "./scene-batch.js";
import { resolveProjectBuildInput, doctor, inspectRom, buildRom } from "./build.js";
import { ChromaticDeviceError, ChromaticService } from "./chromatic.js";
import { displayPng, renderContactSheetPng } from "./contact-sheet.js";
import { analyzeDialogue } from "./dialogue.js";
import { RecordingAccessError } from "./recording-maintenance.js";
import { EmulatorError, EmulatorTimelineError, EmulatorService } from "./emulator.js";
import { analyzeGraphics } from "./graphics.js";
import { createMcpPathPrivacy } from "./mcp-path-privacy.js";
import { PlaytestError } from "./playtest-errors.js";
import { BLANK_PROJECT_GAME_TYPES, BLANK_PROJECT_COLOR_MODES, ProjectSession } from "./project-session.js";
import { SourceDebugError, createSourceDebugContext } from "./source-debug.js";
import { spritePaletteWarnings } from "./scene-graphics.js";
import { tileCoordinate, revision, emulatorColorCorrection, domainSchemas } from "./tool-domains/schemas.js";
import { authoringWarnings, authoringScripts } from "./event-catalog.js";
import { registerProjectDomains } from "./tool-domains/register.js";
import { registerChromaticTools } from "./tool-domains/chromatic.js";
import { recordingOptionsSchema, MAX_REPLAY_EXPECTED_VARIABLES, replayExpectSchema, registerPlaytestTools } from "./tool-domains/playtest.js";
import { webBuildFailureResult, nativeRomRevision, rememberNativeRom, buildWeb } from "./web-build.js";
import { PreviewInputError } from "./web-preview-input.js";
import { WebPreviewService } from "./web-preview.js";
import { nativeSelectionSchema } from "./device-capture/native-protocol.js";
import { NativeDeviceCaptureService } from "./native-device-capture.js";

const SERVER_NAME = "modretro-chromatic";
const SERVER_VERSION = "1.0.34";
const WEB_ANNOTATION_ASSETS = fileURLToPath(new URL("../dist/web-annotations/", import.meta.url));
const DEVICE_ASSETS = process.env.CHROMATIC_DEVICE_SKINS ? path.resolve(process.env.CHROMATIC_DEVICE_SKINS) : fileURLToPath(new URL("../../../player/skins/", import.meta.url));
const readOnly = {
    readOnlyHint: true,
    destructiveHint: false,
    idempotentHint: true,
    openWorldHint: false
};
const createOnly = {
    readOnlyHint: false,
    destructiveHint: false,
    idempotentHint: false,
    openWorldHint: false
};
const updateExisting = {
    readOnlyHint: false,
    destructiveHint: true,
    idempotentHint: false,
    openWorldHint: false
};
const changeSession = {
    readOnlyHint: false,
    destructiveHint: false,
    idempotentHint: false,
    openWorldHint: false
};
const emptyInput = z.object({}).strict();
const identifier = z.string().trim().min(1).max(256);
const boundedPath = z.string().trim().min(1).max(4096).refine((value) => !value.includes("\0"), "Paths must not contain NUL characters.");
const position = z.number().int().min(-32768).max(32767);
const dimension = z.number().int().min(1).max(4096);
const sceneDimension = z.number().int().min(1).max(255);
const customProperties = z.record(z.string(), z.unknown());
const direction = z.enum(["up", "down", "left", "right"]);
const initialFrameCount = z.number().int().min(0).max(3600);
const webBuildInput = z.object({
    outputPath: boundedPath.optional().describe("Export directory relative to the selected project; defaults to build/web."),
    timeoutMs: z.number().int().min(1_000).max(600_000).optional().describe("Time allowed for the official export, in milliseconds."),
    force: z.boolean().optional().describe("Rebuild instead of reusing an unchanged, verified export."),
    cacheOnly: z.boolean().optional().describe("Use only an unchanged, verified export; refuse instead of compiling on a cache miss.")
}).strict();
const webPreviewInput = webBuildInput.extend({
    outputPath: webBuildInput.shape.outputPath.describe("Open only: project-relative export directory; defaults to build/web."),
    timeoutMs: webBuildInput.shape.timeoutMs.describe("Open only: time allowed for the official export, in milliseconds."),
    force: webBuildInput.shape.force.describe("Open only: rebuild instead of reusing an unchanged, verified export."),
    action: z.enum(["open", "recover", "status", "capture_state", "list_states", "restore_state", "input", "start_recording", "recording_status", "stop_recording", "read_capture", "install_status", "dismiss_install_failure"]).optional().describe("Default open. Recover reopens a verified existing export without rebuilding. State commands control the already-open player."),
    viewId: z.string().uuid().optional().describe("For capture_state or restore_state: use a player ID from status when more than one browser view is open."),
    installationBinding: z.object({ generation: z.string().regex(/^[a-f0-9]{32}$/), requestId: z.string().uuid(), operationId: z.string().min(1).max(128) }).strict().optional().describe("dismiss_install_failure only: exact generation/requestId/operationId from install_status. Explicitly acknowledges the known-closed failed attempt without erasing evidence or writing a cartridge; fresh selection and confirmation are still required."),
    installationRequestId: z.string().uuid().optional().describe("install_status only: original preview request ID. When supplied, return only that request with no fallback; when omitted, return the latest manual request. Match the returned request ID and generation before adopting its result."),
    stateId: z.string().regex(/^[a-f0-9]{64}$/).optional().describe("For restore_state only: required saved state ID from list_states."),
    binding: z.object({
        listenerId: z.string().regex(/^[a-f0-9]{32}$/),
        viewId: z.string().uuid(),
        romSha256: z.string().regex(/^[a-f0-9]{64}$/),
        runtimeSha256: z.string().regex(/^[a-f0-9]{64}$/),
        sourceRevision: z.string().min(1).max(1024),
        inputGeneration: z.number().int().nonnegative()
    }).strict().optional().describe("Input only: copy the exact listener, player, build and input generation from status."),
    buttons: z.array(z.enum(["up", "down", "left", "right", "a", "b", "start", "select"])).max(8).optional().describe("Input only: unique ordinary game buttons, with no opposing directions. Empty observes a neutral interval."),
    durationMs: z.number().int().min(50).max(2_000).optional().describe("Input only: wall-clock hold, 250 ms by default; not exact frames."),
    recordingBinding: z.object({ listenerId: z.string().regex(/^[a-f0-9]{32}$/), viewId: z.string().uuid(), romSha256: z.string().regex(/^[a-f0-9]{64}$/), runtimeSha256: z.string().regex(/^[a-f0-9]{64}$/), sourceRevision: z.string().min(1).max(1024), recordingGeneration: z.number().int().nonnegative() }).strict().optional().describe("Start recording only: exact listener, view, build and recording generation from status."),
    recordingDurationMs: z.number().int().min(1_000).max(600_000).optional().describe("Start recording only: fixed duration, 180000 ms by default; at most 600000 ms."),
    recordingId: z.string().uuid().optional().describe("Original job ID for recording_status, stop_recording or read_capture. Never retry an uncertain start.")
}).strict();
const dialogueMutationOptions = {
    validation: z.enum(["warn", "reject"]).optional(),
    wrap: z.enum(["none", "word"]).optional(),
    paginate: z.boolean().optional()
};
function boundedDialogueFit(analysis) {
    return {
        dialogueFit: {
            valid: analysis.valid,
            confidence: analysis.confidence,
            font: analysis.font,
            pageCount: analysis.pageCount,
            lineCount: analysis.lineCount,
            maximumMeasuredLinePx: analysis.maximumMeasuredLinePx,
            diagnosticCount: analysis.diagnosticCount,
            diagnosticCounts: analysis.diagnosticCounts
        },
        fitWarnings: analysis.diagnostics.slice(0, 8)
    };
}
function toRecord(value) {
    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
        return value;
    }
    return { value };
}
function formatToolResult(value) {
    const structuredContent = toRecord(value);
    const labels = [];
    const failed = structuredContent.success === false;
    const dryRun = structuredContent.dryRun === true;
    const headline = failed ? "Operation failed" : dryRun ? "Preview only; no changes applied" : "Completed";
    if (failed && typeof structuredContent.exitCode === "number")
        labels.push(`exit ${structuredContent.exitCode}`);
    if (structuredContent.cancelled === true)
        labels.push("cancelled");
    if (structuredContent.outputTruncated === true)
        labels.push("output truncated");
    if (structuredContent.diagnosticsTruncated === true)
        labels.push("diagnostics truncated");
    if ([structuredContent.truncated, structuredContent.truncation].some((truncation) => truncation === true || typeof truncation === "object" && truncation !== null && Object.values(truncation).some((field) => field === true)))
        labels.push("partial results");
    const coverage = toRecord(structuredContent.coverage);
    if (typeof coverage.complete === "boolean")
        labels.push(`dependency coverage ${coverage.complete ? "complete" : "incomplete"}`);
    const coveragePagination = toRecord(coverage.pagination);
    const coverageLimitations = toRecord(coveragePagination.limitations);
    const coverageEvidence = toRecord(coveragePagination.reviewedCustomEvents);
    if (typeof coverageLimitations.total === "number" && typeof coverageLimitations.returned === "number" && typeof coverageEvidence.total === "number" && typeof coverageEvidence.returned === "number") {
        const total = coverageLimitations.total + coverageEvidence.total;
        if (total > 0)
            labels.push(`${coverageLimitations.returned + coverageEvidence.returned} of ${total} coverage diagnostics`);
    }
    if (typeof coveragePagination.nextCursor === "string")
        labels.push("more coverage; use coverageCursor");
    const health = toRecord(structuredContent.health);
    for (const [field, label] of [[health.errorCount, "project errors"], [health.warningCount, "project warnings"]]) {
        if (typeof field === "number" && field > 0)
            labels.push(`${label}: ${field}`);
    }
    for (const key of ["warnings", "fitWarnings", "diagnostics"]) {
        const field = structuredContent[key];
        const total = key === "diagnostics" ? structuredContent.diagnosticCount : undefined;
        if (Array.isArray(field) && field.length > 0) {
            labels.push(`${key}: ${field.length}${typeof total === "number" && total > field.length ? ` of ${total}` : ""}`);
        }
    }
    if (typeof structuredContent.selected === "boolean")
        labels.push(structuredContent.selected ? "project selected" : "no project selected");
    if (typeof structuredContent.emulatorActive === "boolean")
        labels.push(structuredContent.emulatorActive ? "emulator active" : "emulator inactive");
    if (typeof structuredContent.ready === "boolean") {
        const basis = structuredContent.readinessBasis === "compatible-metadata" ? "metadata readiness" : "readiness";
        labels.push(`${basis}: ${structuredContent.ready ? "ready" : "not ready"}`);
    }
    if (typeof structuredContent.probesPassed === "boolean") {
        labels.push(`requested probes: ${structuredContent.probesPassed ? "passed" : "failed"}`);
    }
    if (Array.isArray(structuredContent.changedPaths)) {
        labels.push(`${dryRun ? "planned files" : "changed files"}: ${structuredContent.changedPaths.length}`);
    }
    const paged = typeof structuredContent.returned === "number" && typeof structuredContent.total === "number";
    if (paged)
        labels.push(`${structuredContent.returned} of ${structuredContent.total} records`);
    if (typeof structuredContent.nextCursor === "string")
        labels.push("more available; use nextCursor");
    if (typeof structuredContent.nextActionOffset === "number")
        labels.push("more actions; use nextActionOffset");
    if (Array.isArray(structuredContent.actions) && typeof structuredContent.actionCount === "number") {
        labels.push(`${structuredContent.actions.length} of ${structuredContent.actionCount} actions`);
    }
    for (const key of ["name", "projectName", "frame", "frameCount"]) {
        const field = structuredContent[key];
        if (typeof field === "string" || typeof field === "number")
            labels.push(`${key}: ${String(field).slice(0, 60)}`);
    }
    if (!paged)
        for (const key of ["scenes", "actors", "triggers", "assets", "palettes", "variables"]) {
            const field = structuredContent[key];
            if (Array.isArray(field) && field.length > 0)
                labels.push(`${key}: ${field.length}`);
        }
    const summary = `${headline}${labels.length > 0 ? ` (${labels.join("; ")})` : ""}.`;
    return {
        content: [{ type: "text", text: summary }],
        structuredContent
    };
}
function formatErrorResult(error) {
    const message = error instanceof Error ? error.message : String(error);
    const accessFailure = error instanceof RecordingAccessError ? error : error instanceof EmulatorError && error.cause instanceof RecordingAccessError ? error.cause : undefined;
    const code = error instanceof Error && "code" in error && typeof error.code === "string" ? error.code : "GB_STUDIO_TOOL_ERROR";
    const structuredContent = {
        error: message,
        code,
        ...error instanceof ProjectTransactionError ? { recovery: error.recovery } : {},
        ...error instanceof PreviewInputError && error.commandId ? { commandId: error.commandId } : {},
        ...error instanceof ChromaticDeviceError && error.details ? { details: error.details } : {},
        ...accessFailure === undefined ? {} : { recordingAccessFailure: accessFailure.failure },
        ...error instanceof PlaytestError && error.recordingPath !== undefined ? { recordingPath: error.recordingPath } : {},
        ...error instanceof EmulatorError && error.execution !== undefined ? {
            execution: error.execution,
            imageDelivery: error.imageDelivery
        } : {},
        ...error instanceof EmulatorError && error.cleanup !== undefined ? { cleanup: error.cleanup } : {},
        ...error instanceof EmulatorTimelineError ? {
            failedActionIndex: error.failedActionIndex,
            startFrame: error.startFrame,
            advancedFrames: error.advancedFrames,
            frame: error.frame,
            activeButtons: error.activeButtons
        } : {}
    };
    return {
        content: [{ type: "text", text: JSON.stringify(structuredContent) }],
        structuredContent,
        isError: true
    };
}
async function runWithSourceDebugState(current, setContext, operation) {
    setContext(undefined);
    try {
        const next = await operation.resolve();
        const running = await operation.run();
        if (next !== undefined && running.romSha256 !== next.identity.romSha256) {
            const mismatch = new PlaytestError("SOURCE_DEBUG_ROM_MISMATCH", "The loaded emulator ROM does not match the authenticated build.");
            if (operation.mismatched === undefined)
                throw mismatch;
            operation.mismatched(mismatch);
            return running;
        }
        setContext(next);
        return running;
    } catch (error) {
        if (current !== undefined && operation.isActive()) {
            try {
                const remaining = await operation.status();
                if (operation.isActive() && remaining.paused === true && remaining.romSha256 === current.identity.romSha256) {
                    setContext(current);
                }
            } catch {
            }
        }
        throw error;
    }
}
function compactBuildDebug({ debugArtifacts, sourceDebug, ...result }) {
    return {
        ...result,
        ...debugArtifacts ? { debugArtifacts: { directory: debugArtifacts.directory } } : {},
        ...sourceDebug ? { sourceDebug: sourceDebug.available ? { available: true } : sourceDebug } : {}
    };
}
function createGbStudioServer(options = {}) {
    const configuredToolchain = process.env.GB_STUDIO_TOOLCHAIN_ROOT;
    const session = new ProjectSession({
        ...options,
        ...configuredToolchain === undefined ? {} : { toolchainRoot: configuredToolchain },
        isEmulatorActive: () => emulator.active,
        isProjectBusy: () => deviceCapture.busy
    });
    const emulatorOptions = configuredToolchain === undefined ? {} : { toolchainRoot: configuredToolchain };
    const redactPaths = createMcpPathPrivacy({
        visibility: process.env.GB_STUDIO_MCP_PATH_VISIBILITY,
        workspaceRoot: () => session.workspaceRoot,
        workspaceAliases: [options.workspaceRoot, process.env.GB_STUDIO_WORKSPACE_ROOT],
        runtimeRoot: session.runtimeRoot,
        toolchainRoot: configuredToolchain,
        pythonPath: process.env.GB_STUDIO_PYTHON,
        home: os.homedir() || process.env.USERPROFILE || process.env.HOME,
        homeAliases: [process.env.HOME, process.env.USERPROFILE]
    });
    function toolResult(value) {
        return redactPaths(formatToolResult(value));
    }
    function errorResult(error) {
        return redactPaths(formatErrorResult(error));
    }
    async function safely(action) {
        try {
            return toolResult(await action());
        } catch (error) {
            return errorResult(error);
        }
    }
    let emulator = new EmulatorService({
        projectRoot: session.workspaceRoot ?? session.runtimeRoot,
        ...emulatorOptions
    });
    const sourceBuilds = new Map();
    // The linker symbols each official build captured with its ROM, by ROM SHA-256: the emulator worker places a ROM's
    // save signature only from these, so a checkpoint crosses only a verified rebuild.
    const buildSymbols = new Map();
    let activeSourceDebug;
    let emulatorOperationTail = Promise.resolve();
    let emulatorOperationGeneration = 0;
    let emulatorOperationsPending = 0;
    const emulatorOperationControllers = new Set();
    let emulatorCancellation;
    let closing = false;
    let closePromise;
    const chromatic = new ChromaticService({ root: session.runtimeRoot, ...options.chromatic });
    const webPreview = new WebPreviewService({
        chromatic,
        isProjectSelected: (projectRoot) => session.selectedProject?.projectRoot === projectRoot,
        deviceCaptureAvailability: () => deviceCapture.availability(),
        serveDeviceView: (request, response, projectRoot, route, origin) => deviceCapture.servePreview(request, response, projectRoot, session.selectionGeneration, route, origin)
    });
    const deviceCapture = new NativeDeviceCaptureService({
        ...options.deviceCapture,
        helperManifest: fileURLToPath(new URL("../native/capture/macos/manifest.json", import.meta.url)),
        linuxHelperManifest: fileURLToPath(new URL("../native/capture/linux/manifest.json", import.meta.url)),
        deviceAssetsRoot: DEVICE_ASSETS,
        assetsRoot: fileURLToPath(new URL("../dist/", import.meta.url)),
        isSelected: (root, generation) => session.selectedProject?.projectRoot === root && session.selectionGeneration === generation
    });
    let initialSelectionError;
    const initialized = session.initialize().then(async (project) => {
        if (project !== undefined)
            await rebindAuthorizedEmulator(project.projectRoot);
        return project;
    }).catch((error) => {
        initialSelectionError = error;
        return undefined;
    });
    const server = new McpServer({ name: SERVER_NAME, title: "ModRetro Chromatic", version: SERVER_VERSION }, {
        instructions: "Use project_create_blank for a blank game or project_create for a sample. Select the project before editing. In Hermes, show a successful playable build to the user early with chromatic_present_game (the hermretro emulator beside the chat); if the user cannot see that emulator, open studio.playerUrl from its result with desktop_preview, never web_preview URLs. Defer updates that could interrupt human play, saves or recordings; resolve unknown outcomes first. Do not arbitrarily reload or autoplay. Continue gameplay headlessly with public PyBoy emulator_run on the intended exact ROM, then emulator_step and emulator_observe; use emulator_review for retained evidence. Browser access is not a prerequisite for gameplay checks. If PyBoy is missing, follow the setup skill for the emulator component within existing authorization. Keep denials and uncertain actions scoped; never replay them. Native gameplay does not verify browser UI, annotations or physical capture. Use device_capture to watch physical play beside the chat in Hermes Desktop; emulator controls cannot drive hardware. Inspect the exact ROM before an approved device action. Close only temporary sessions you own when no longer needed, preserving user play and recordings."
    });
    async function selectedProject() {
        await initialized;
        if (initialSelectionError !== undefined && session.selectedProject === undefined) {
            throw initialSelectionError;
        }
        return session.requireSelectedProject();
    }
    function authorizedEmulatorRoot() {
        const root = session.authorizedOperationRoot();
        if (emulator.projectRoot !== root)
            throw new Error("The emulator workspace binding is changing; select the intended project before continuing.");
        return root;
    }
    function performAuthorizedEmulatorOperation(action) {
        return performEmulatorOperation(async () => {
            await initialized;
            authorizedEmulatorRoot();
            return action();
        });
    }
    function assertEmulatorIdle() {
        if (closing)
            throw new PlaytestError("EMULATOR_OPERATION_CANCELLED", "The plugin is closing; no new emulator work can start.");
        if (emulatorCancellation !== undefined) {
            throw new PlaytestError("EMULATOR_BUSY", "The emulator is still closing. Wait for cleanup before starting another operation.");
        }
    }
    function performEmulatorOperation(action, parentSignal) {
        assertEmulatorIdle();
        const generation = emulatorOperationGeneration;
        const controller = new AbortController();
        const cancel = () => controller.abort();
        parentSignal?.addEventListener("abort", cancel, { once: true });
        if (parentSignal?.aborted)
            controller.abort();
        emulatorOperationControllers.add(controller);
        emulatorOperationsPending += 1;
        const operation = emulatorOperationTail.then(async () => {
            if (closing || generation !== emulatorOperationGeneration || controller.signal.aborted) {
                throw new PlaytestError("EMULATOR_OPERATION_CANCELLED", "The queued emulator operation was cancelled.");
            }
            return action(controller.signal);
        });
        const settled = operation.finally(() => {
            emulatorOperationsPending -= 1;
            emulatorOperationControllers.delete(controller);
            parentSignal?.removeEventListener("abort", cancel);
        });
        emulatorOperationTail = settled.then(() => undefined, () => undefined);
        return settled;
    }
    async function cancelEmulatorSession() {
        if (emulatorCancellation !== undefined)
            return emulatorCancellation;
        emulatorOperationGeneration += 1;
        for (const controller of emulatorOperationControllers)
            controller.abort();
        const pending = emulatorOperationTail;
        const cancellation = (async () => {
            try {
                return await emulator.control({ action: "cancel" });
            } finally {
                await pending;
                await emulator.close();
                activeSourceDebug = undefined;
            }
        })();
        emulatorCancellation = cancellation;
        try {
            return await cancellation;
        } finally {
            if (emulatorCancellation === cancellation)
                emulatorCancellation = undefined;
        }
    }
    async function closeEmulatorSession() {
        if (emulatorCancellation !== undefined) {
            await emulatorCancellation;
            return;
        }
        if (emulatorOperationsPending > 0) {
            await cancelEmulatorSession();
            return;
        }
        emulatorOperationGeneration += 1;
        const closing = (async () => {
            await emulator.close();
            activeSourceDebug = undefined;
        })();
        emulatorCancellation = closing;
        try {
            await closing;
        } finally {
            if (emulatorCancellation === closing)
                emulatorCancellation = undefined;
        }
    }
    async function rememberSourceBuild(result, projectPath, access) {
        if (!result.success || result.debugArtifacts === undefined)
            return result;
        try {
            const context = await createSourceDebugContext({ build: result, projectPath, access });
            sourceBuilds.delete(context.identity.romSha256);
            sourceBuilds.set(context.identity.romSha256, context);
            while (sourceBuilds.size > 8)
                sourceBuilds.delete(sourceBuilds.keys().next().value);
            return { ...result, sourceDebug: { available: true, identity: context.identity } };
        } catch (error) {
            return {
                ...result,
                sourceDebug: {
                    available: false,
                    code: error instanceof Error && "code" in error ? error.code : "SOURCE_DEBUG_UNAVAILABLE",
                    reason: error instanceof Error ? error.message : String(error)
                }
            };
        }
    }
    async function buildSelectedRom({ detail = "compact", ...input }) {
        if (input.sourcePath) {
            if (input.projectPath)
                throw new Error("Provide either projectPath or sourcePath, not both.");
            return performMutation(() => buildRom({ ...input, projectRoot: authorizedEmulatorRoot(), projectPath: undefined }));
        }
        return performProjectArtifact(async (project, access) => {
            const projectPath = input.projectPath ?? project.projectPath;
            const selected = path.resolve(project.projectRoot, projectPath) === path.resolve(project.projectPath);
            const before = selected ? await nativeRomRevision(project.projectRoot, project.projectPath).catch(() => null) : null;
            if (selected)
                await access.strongRefresh();
            const inventory = selected ? await access.legacyInventory() : await inventoryProject(await resolveProjectBuildInput(project.projectRoot, projectPath));
            const duplicates = inventory.diagnostics.filter((diagnostic) => diagnostic.code === "DUPLICATE_SYMBOL");
            if (duplicates.length > 0)
                throw new GameStudioProjectError("DUPLICATE_SYMBOL", duplicates.map((diagnostic) => diagnostic.message).join(". "), duplicates[0].resourcePath);
            const shared = await authoringScripts(inventory);
            const result = await buildRom({ ...input, captureDebugArtifacts: input.captureDebugArtifacts ?? true, debugArtifactsOptional: input.captureDebugArtifacts === undefined, projectRoot: project.projectRoot, projectPath, authoringWarnings: [...authoringWarnings(inventory, shared), ...await spritePaletteWarnings(inventory, shared)] });
            if (before && result.success !== false && typeof result.outputPath === "string" && result.rom)
                await rememberNativeRom(before, project.projectPath, { path: result.outputPath, sha256: result.rom.sha256 }, configuredToolchain).catch(() => {
                });
            const relative = path.relative(project.projectRoot, result.outputPath).split(path.sep).join("/");
            if (relative.startsWith("project/") || relative.startsWith("assets/"))
                await access.noteCommittedPaths([result.outputPath]);
            if (result.success && result.debugArtifacts)
                rememberBuildSymbols(result.debugArtifacts);
            const remembered = await rememberSourceBuild(result, project.projectPath, access);
            return detail === "full" ? remembered : compactBuildDebug(remembered);
        });
    }
    async function sourceContextForRom(romPath) {
        authorizedEmulatorRoot();
        const digest = emulator.romSha256(romPath);
        const context = sourceBuilds.get(digest);
        if (context === undefined || context.projectPath !== (await selectedProject()).projectPath) {
            throw new PlaytestError("SOURCE_DEBUG_UNAVAILABLE", "No build in this session captured debug artifacts for this ROM in the selected project. Rebuild it with rom_build (it captures them unless captureDebugArtifacts is false) and run the ROM it returns.");
        }
        await context.assertCompatibleRom(digest);
        return context;
    }
    function rememberBuildSymbols({ romSha256, noiPath, noiSha256 }) {
        buildSymbols.delete(romSha256);
        buildSymbols.set(romSha256, { romSha256, path: noiPath, sha256: noiSha256 });
        while (buildSymbols.size > 8)
            buildSymbols.delete(buildSymbols.keys().next().value);
    }
    function withBuildSymbols(romPath, options) {
        const symbols = buildSymbols.get(emulator.romSha256(romPath));
        return symbols === undefined ? options : { ...options, symbols };
    }
    async function runEmulator(romPath, options, debugMode, signal) {
        return openEmulator(romPath, debugMode, signal, () => emulator.run(romPath, withBuildSymbols(romPath, options), signal));
    }
    async function replayEmulator(romPath, options, debugMode, signal) {
        return openEmulator(romPath, debugMode, signal, () => emulator.replay(romPath, withBuildSymbols(romPath, options), signal));
    }
    function sourceDebugUnavailable(error) {
        return { unavailable: { available: false, code: error.code, reason: error.message } };
    }
    async function automaticSourceContext(romPath) {
        try {
            return { context: await sourceContextForRom(romPath) };
        } catch (error) {
            if (!(error instanceof PlaytestError || error instanceof SourceDebugError) || !error.code.startsWith("SOURCE_DEBUG_"))
                throw error;
            return sourceDebugUnavailable(error);
        }
    }
    async function openEmulator(romPath, debugMode, signal, open) {
        await initialized;
        authorizedEmulatorRoot();
        let chosen = { context: undefined };
        const running = await runWithSourceDebugState(activeSourceDebug, (source) => {
            activeSourceDebug = source;
        }, {
            resolve: async () => {
                chosen = debugMode === "rom" ? { context: undefined } : debugMode === "source" ? { context: await sourceContextForRom(romPath) } : await automaticSourceContext(romPath);
                return chosen.context;
            },
            ...debugMode === undefined ? { mismatched: (error) => {
                chosen = sourceDebugUnavailable(error);
            } } : {},
            run: async () => {
                if (signal?.aborted)
                    throw new PlaytestError("EMULATOR_OPERATION_CANCELLED", "The emulator open request was cancelled before execution.");
                return open();
            },
            isActive: () => signal?.aborted !== true && emulatorCancellation === undefined && emulator.active,
            status: () => emulator.status()
        });
        const fallback = chosen.unavailable?.code === "SOURCE_DEBUG_UNAVAILABLE" ? undefined : chosen.unavailable;
        return { ...running, debugMode: chosen.context === undefined ? "rom" : "source", ...fallback ? { sourceDebug: fallback } : {} };
    }
    async function inspectSource(input, reads = emulator) {
        if (activeSourceDebug === undefined) {
            throw new PlaytestError("SOURCE_DEBUG_DISABLED", "This emulator session runs without source debugging. Rebuild with rom_build (it captures debug artifacts unless captureDebugArtifacts is false) and start the ROM it returns with emulator_run.");
        }
        return activeSourceDebug.inspect(reads, input);
    }
    /**
     * A step's debug request, read on the step's last frame inside the same emulator operation. Variables are only the
     * named ones, and a refusal is returned as data: the step has already run, so it is never an error to retry. The
     * read never ends the session itself (a timeout fails only the read); its error text is bounded like the
     * engine's other reported failures.
     */
    async function stepLiveState({ variableIds, variableNames, ...query }) {
        const reads = {
            status: () => emulator.status({ keepSession: true }),
            inspect: (view) => emulator.inspect(view, { keepSession: true })
        };
        try {
            authorizedEmulatorRoot();
            const named = variableIds === undefined && variableNames === undefined ? { variableIds: [] } : { variableIds, variableNames };
            const { scene, live, variables, limitations } = await inspectSource({ ...query, ...named, referenceLimit: 0 }, reads);
            return {
                ...scene ? { scene: { id: scene.id, name: scene.name, type: scene.type } } : {},
                ...live ? { live } : {},
                ...variables.length > 0 ? { variables: variables.map(({ id, name, value }) => ({ id, name, value })) } : {},
                ...limitations ? { limitations } : {}
            };
        } catch (cause) {
            const { error, code } = errorResult(cause).structuredContent;
            return { error: error.slice(0, 2_000), code };
        }
    }
    /** Said in a step's result when the emulator stopped during its debug read, so the step never reads as a plain success. */
    function lostSession(observation) {
        const recorded = observation.recordingSpan !== undefined;
        return {
            status: "lost",
            recording: recorded ? "interrupted" : "none",
            recovery: recorded ? "The recording kept this step's inputs (recordingSpan) and ends interrupted: emulator_recording status reads it. emulator_run starts a new session." : "emulator_run starts a new session."
        };
    }
    async function performMutation(action) {
        await initialized;
        return session.withActivity(action);
    }
    async function performProjectRead(action) {
        await initialized;
        if (initialSelectionError !== undefined && session.selectedProject === undefined) {
            throw initialSelectionError;
        }
        return session.withSelectedProjectAccess(action);
    }
    async function performProjectMutation(action) {
        return performQueuedProjectOperation(action, true);
    }
    async function performProjectArtifact(action) {
        return performQueuedProjectOperation(action, false);
    }
    async function performQueuedProjectOperation(action, authoredWrite) {
        return performProjectRead((project, access) => withProjectMutation(project.projectRoot, async () => {
            await access.ensureFresh();
            return action(project, access);
        }, { authoredWrite }));
    }
    async function performProjectTransaction(action) {
        return performProjectRead(action);
    }
    async function prepareDialogueMutation(projectPath, text, options, target, access) {
        const explicitlyRequested = options.validation !== undefined || options.wrap !== undefined || options.paginate !== undefined;
        let analysis;
        try {
            analysis = await analyzeDialogue(projectPath, {
                ...target,
                text,
                ...options.wrap === undefined ? {} : { wrap: options.wrap },
                ...options.paginate === undefined ? {} : { paginate: options.paginate },
                includeSuggestion: true
            }, access);
        } catch (error) {
            if (!explicitlyRequested && error instanceof GameStudioProjectError && error.code === "FONT_NOT_FOUND") {
                return { text };
            }
            throw error;
        }
        if (options.validation === "reject" && !analysis.valid) {
            const overflowCodes = Object.keys(analysis.diagnosticCounts).filter((code) => code === "LINE_OVERFLOW" || code === "PAGE_OVERFLOW").join(", ");
            throw new GameStudioProjectError("DIALOGUE_OVERFLOW", `The authored dialogue does not fit the selected ${analysis.font.name} layout (${overflowCodes || "overflow"}); request word wrapping or pagination explicitly.`);
        }
        const transformed = options.wrap === "word" || options.paginate === true;
        return { text: transformed ? analysis.suggestion?.text ?? text : text, analysis };
    }
    async function rebindAuthorizedEmulator(projectRoot) {
        const emulatorRoot = session.authorizedOperationRoot(projectRoot);
        if (emulator.projectRoot !== emulatorRoot) {
            await emulator.close();
            emulator = new EmulatorService({ projectRoot: emulatorRoot, ...emulatorOptions });
        }
    }
    async function selectProject(input) {
        await initialized;
        const previousProjectRoot = session.selectedProject?.projectRoot;
        const candidate = previousProjectRoot === undefined ? undefined : await session.discover(input.projectPath);
        if (candidate && candidate.projectRoot !== previousProjectRoot)
            await webPreview.stop();
        const discovered = await session.select(input);
        if (previousProjectRoot !== undefined && previousProjectRoot !== discovered.projectRoot) {
            sourceBuilds.clear();
            buildSymbols.clear();
            activeSourceDebug = undefined;
        }
        initialSelectionError = undefined;
        await rebindAuthorizedEmulator(discovered.projectRoot);
        return discovered;
    }
    async function createProject(create, select = false) {
        await initialized;
        const previousProjectRoot = session.selectedProject?.projectRoot;
        const project = await create();
        if (select) {
            if (previousProjectRoot !== undefined && previousProjectRoot !== project.projectRoot) {
                await webPreview.stop();
                sourceBuilds.clear();
                buildSymbols.clear();
                activeSourceDebug = undefined;
            }
            await session.select({ projectPath: project.projectPath, allowStarter: true });
            initialSelectionError = undefined;
        }
        await rebindAuthorizedEmulator(session.selectedProject?.projectRoot ?? project.projectRoot);
        return project;
    }
    server.registerTool("session_status", {
        title: "Inspect native game session",
        description: "Report explicit project selection, authorized workspace identity, selection generation, and active emulator state without authorizing or modifying files.",
        inputSchema: z.object({ includeIndexStats: z.boolean().optional() }).strict(),
        annotations: readOnly
    }, async ({ includeIndexStats }) => safely(async () => {
        await initialized;
        return {
            selected: session.selectedProject !== undefined,
            ...session.selectedProject === undefined ? {} : {
                projectPath: session.selectedProject.projectPath,
                projectRoot: session.selectedProject.projectRoot,
                format: session.selectedProject.format
            },
            ...session.workspaceRoot === undefined ? {} : { workspaceRoot: session.workspaceRoot },
            selectionGeneration: session.selectionGeneration,
            emulatorActive: emulator.active,
            ...includeIndexStats === true ? { indexStats: session.indexStats() } : {}
        };
    }));
    server.registerTool("project_discover", {
        title: "Discover native game project",
        description: "Inspect the explicitly selected native game project, or discover a supplied path inside the already authorized workspace without changing selection.",
        inputSchema: z.object({ projectPath: boundedPath.optional() }).strict(),
        annotations: readOnly
    }, async ({ projectPath }) => safely(async () => {
        if (projectPath === undefined)
            return selectedProject();
        await initialized;
        return session.discover(projectPath);
    }));
    server.registerTool("project_select", {
        title: "Select native game project",
        description: "Select the project to inspect or edit. Without a configured workspace, supply its absolute path; otherwise stay within the authorized workspace. The bundled starter requires allowStarter; active emulators or mutations prevent switching.",
        inputSchema: z.object({ projectPath: boundedPath, allowStarter: z.boolean().optional() }).strict(),
        annotations: changeSession
    }, async (input) => safely(() => performEmulatorOperation(() => selectProject(input))));
    server.registerTool("project_create", {
        title: "Create an editable native game project",
        description: "Create an editable project from starter or the optional Wrecklight source sample. If Wrecklight is not bundled, supply its matching local templateSourcePath. The source is verified and never modified. With no workspace configured, use an absolute new destination under an existing canonical parent; otherwise stay within the workspace. Select only when requested.",
        inputSchema: z.object({
            name: z.string().trim().min(1).max(200),
            destinationPath: boundedPath,
            template: z.enum(["starter", "wrecklight"]),
            templateSourcePath: boundedPath.optional(),
            author: z.string().trim().min(1).max(200).optional(),
            select: z.boolean().optional()
        }).strict(),
        annotations: createOnly
    }, async (input) => safely(() => performEmulatorOperation(() => createProject(() => session.create({ ...input, select: false }), input.select))));
    server.registerTool("project_create_blank", {
        title: "Create a blank game project",
        description: "Create a new editable project with one empty Start scene and original minimal resources, without sample quests, actors or triggers. Configure its native game type and color mode; defaults are TOPDOWN and color. The destination must be new: use an absolute path under an existing parent when no workspace is configured, otherwise stay within the authorized workspace. Select only when requested. No compiler or emulator is required.",
        inputSchema: z.object({
            name: z.string().trim().min(1).max(200),
            destinationPath: boundedPath,
            author: z.string().trim().min(1).max(200).optional(),
            gameType: z.enum(BLANK_PROJECT_GAME_TYPES).optional(),
            colorMode: z.enum(BLANK_PROJECT_COLOR_MODES).optional().describe("mono: monochrome; mixed: color with monochrome compatibility; color: color-only."),
            select: z.boolean().optional()
        }).strict(),
        annotations: createOnly
    }, async (input) => safely(() => performEmulatorOperation(() => createProject(() => session.createBlank({ ...input, select: false }), input.select))));
    server.registerTool("project_inspect", {
        title: "Inspect native game project",
        description: "Read the selected native game project's metadata, settings, format, and project health without changing files.",
        inputSchema: emptyInput,
        annotations: readOnly
    }, async () => safely(() => performProjectRead((project, access) => inspectProject(project.projectPath, { selectionGeneration: access.selectionGeneration }, access))));
    server.registerTool("project_inventory", {
        title: "Find and inventory project resources",
        description: "Find scenes, actors, assets and other resources by name or stable ID, or list them with standard detail (up to 50 per page by default). Narrow by resource type; use nextCursor with the same filters for another page.",
        inputSchema: z.object({
            sceneId: identifier.optional(),
            resourceTypes: z.array(z.enum(["scene", "actor", "trigger", "palette", "asset", "variable", "diagnostic"])).max(7).optional(),
            assetTypes: z.array(z.enum(["background", "sprite", "tileset", "font", "avatar", "emote", "music", "sound", "ui"])).max(9).optional(),
            query: z.string().min(1).max(128).refine((value) => value.trim().length > 0, "Query must contain a non-whitespace character").optional().describe("Case-insensitive literal substring of resource names, IDs, or asset filenames (not diagnostics). Applies before pagination; reuse with nextCursor. Normalized layout only."),
            detail: z.enum(["summary", "standard", "full"]).optional().describe("Default standard. Use summary for IDs and names; full includes resource detail."),
            fields: z.array(identifier).max(32).optional(),
            includeSettings: z.boolean().optional(),
            includeReferencedResources: z.boolean().optional(),
            limit: z.number().int().min(1).max(250).optional(),
            cursor: z.string().min(1).max(4096).optional().describe("Pass the preceding result's nextCursor with the same filters. Reinspect if the cursor becomes stale."),
            layout: z.enum(["normalized", "legacy"]).optional()
        }).strict(),
        annotations: readOnly
    }, async (input) => safely(() => performProjectRead((project, access) => inventoryProjectNormalized(project.projectPath, input, access.selectionGeneration, access))));
    server.registerTool("project_refresh", {
        title: "Strongly refresh indexed project state",
        description: "Perform an explicitly requested authoritative authored-project verification and publish fresh indexed revision, semantic generation, and bounded telemetry without modifying project files.",
        inputSchema: z.object({ mode: z.literal("strong") }).strict(),
        annotations: readOnly
    }, async () => safely(() => performProjectRead(async (_project, access) => {
        await access.strongRefresh();
        return {
            revision: access.revision,
            revisionAlgorithm: access.revisionAlgorithm,
            selectionGeneration: access.selectionGeneration,
            indexGeneration: access.indexGeneration,
            semanticGeneration: access.semanticGeneration,
            indexStats: access.stats()
        };
    })));
    server.registerTool("scene_create", {
        title: "Create native game scene",
        description: "Create one native scene in the selected distributed or legacy native game project.",
        inputSchema: z.object({
            name: z.string().trim().min(1).max(200),
            id: identifier.optional(),
            type: z.string().trim().min(1).max(100).optional(),
            width: sceneDimension.optional(),
            height: sceneDimension.optional(),
            x: position.optional(),
            y: position.optional(),
            backgroundId: identifier.optional(),
            symbol: z.string().trim().min(1).max(100).optional(),
            properties: customProperties.optional()
        }).strict(),
        annotations: createOnly
    }, async (input) => safely(() => performProjectMutation((project, access) => createScene(project.projectPath, input, access))));
    server.registerTool("scene_update", {
        title: "Update native game scene",
        description: "Update an existing scene by stable scene ID while preserving other project resources.",
        inputSchema: z.object({
            sceneId: identifier,
            name: z.string().trim().min(1).max(200).optional(),
            type: z.string().trim().min(1).max(100).optional(),
            width: sceneDimension.optional(),
            height: sceneDimension.optional(),
            x: position.optional(),
            y: position.optional(),
            backgroundId: identifier.optional(),
            properties: customProperties.optional()
        }).strict(),
        annotations: updateExisting
    }, async (input) => safely(() => performProjectMutation((project, access) => updateScene(project.projectPath, input, access))));
    server.registerTool("actor_create", {
        title: "Create native game actor",
        description: "Create an actor in an existing scene, optionally assigning a sprite, facing direction, tile position within the scene, and dialogue.",
        inputSchema: z.object({
            sceneId: identifier,
            name: z.string().trim().min(1).max(200),
            id: identifier.optional(),
            spriteSheetId: identifier.optional(),
            x: tileCoordinate.optional().describe("Tile X coordinate inside the selected scene."),
            y: tileCoordinate.optional().describe("Tile Y coordinate inside the selected scene."),
            direction: direction.optional(),
            dialogue: z.string().max(10_000).optional(),
            properties: customProperties.optional(),
            ...dialogueMutationOptions
        }).strict(),
        annotations: createOnly
    }, async ({ validation, wrap, paginate, ...input }) => safely(() => performProjectMutation(async (project, access) => {
        if (input.dialogue === undefined) {
            if (validation !== undefined || wrap !== undefined || paginate !== undefined) {
                throw new GameStudioProjectError("INVALID_DIALOGUE_LAYOUT", "Actor dialogue validation, wrapping, and pagination require authored dialogue text.");
            }
            return createActor(project.projectPath, input, access);
        }
        const prepared = await prepareDialogueMutation(project.projectPath, input.dialogue, { validation, wrap, paginate }, { sceneId: input.sceneId }, access);
        const actorText = typeof prepared.text === "string" ? prepared.text : prepared.text[0];
        if (actorText === undefined) {
            throw new GameStudioProjectError("INVALID_DIALOGUE_LAYOUT", "Actor dialogue must include at least one authored page.");
        }
        const created = await createActor(project.projectPath, { ...input, dialogue: actorText }, access);
        if (Array.isArray(prepared.text)) {
            const updated = await updateDialogue(project.projectPath, {
                sceneId: input.sceneId,
                actorId: String(created.actor.id),
                text: prepared.text
            }, access);
            const script = Array.isArray(created.actor.script) ? created.actor.script : [];
            created.actor = {
                ...created.actor,
                script: script.map((event) => {
                    if (typeof event !== "object" || event === null || !("id" in event) || event.id !== updated.event.id)
                        return event;
                    return updated.event;
                })
            };
        }
        return prepared.analysis === undefined ? created : { ...created, ...boundedDialogueFit(prepared.analysis) };
    })));
    server.registerTool("dialogue_update", {
        title: "Update scene, actor, or trigger dialogue",
        description: "Update scene, actor, or trigger dialogue; omit actorId and triggerId for the scene. Without eventId, updates the first recursive EVENT_TEXT or creates one. Use expectedRevision from script_inspect to guard the owner resource.",
        inputSchema: z.object({
            sceneId: identifier,
            actorId: identifier.optional(),
            triggerId: identifier.optional(),
            eventId: identifier.optional().describe("Exact dialogue event ID; omit to update the first recursive EVENT_TEXT or create one if none exists."),
            text: z.union([
                z.string().max(10_000),
                z.array(z.string().max(10_000)).min(1).max(100)
            ]),
            scriptKey: z.string().trim().min(1).max(100).optional(),
            expectedRevision: revision.optional().describe("Exact owner-resource revision from script_inspect for this scene, actor, or trigger; use the result revision to guard another update."),
            ...dialogueMutationOptions
        }).strict(),
        annotations: updateExisting
    }, async ({ validation, wrap, paginate, ...input }) => safely(async () => {
        if (input.actorId && input.triggerId) {
            throw new Error("Specify either actorId or triggerId, not both.");
        }
        return performProjectMutation(async (project, access) => {
            const prepared = await prepareDialogueMutation(project.projectPath, input.text, { validation, wrap, paginate }, {
                sceneId: input.sceneId,
                ...input.actorId === undefined ? {} : { actorId: input.actorId },
                ...input.triggerId === undefined ? {} : { triggerId: input.triggerId },
                ...input.eventId === undefined ? {} : { eventId: input.eventId },
                ...input.scriptKey === undefined ? {} : { scriptKey: input.scriptKey }
            }, access);
            const updated = await updateDialogue(project.projectPath, { ...input, text: prepared.text }, access);
            return prepared.analysis === undefined ? updated : { ...updated, ...boundedDialogueFit(prepared.analysis) };
        });
    }));
    server.registerTool("settings_update", {
        title: "Update game settings",
        description: "Update project color, cartridge, music, player start position, direction and move speed, player sprite, palette, or compiler settings. Optional expectedRevision checks the current project before writing.",
        inputSchema: z.object({
            settings: z.object({
                colorMode: z.enum(["mono", "mixed", "color"]).optional(),
                startSceneId: identifier.optional(),
                startX: position.optional(),
                startY: position.optional(),
                startDirection: direction.optional(),
                startMoveSpeed: z.number().min(1 / 32).max(255 / 32).optional().describe("Player move speed in pixels per frame in TOPDOWN, SHMUP and POINTNCLICK scenes: GB Studio offers 0.25, 0.5, 1 (default), 2, 3 and 4. PLATFORM scenes use the plat_* engine fields and ADVENTURE scenes adv_walk_vel and adv_run_vel (engine_field_update)."),
                defaultSceneTypeId: identifier.optional(),
                cartType: z.string().trim().min(1).max(100).optional(),
                musicDriver: z.string().trim().min(1).max(100).optional(),
                compilerPreset: z.union([z.literal(1_000), z.literal(3_000), z.literal(50_000), z.literal(100_000)]).optional(),
                defaultFontId: identifier.optional(),
                playerSpriteSheetId: identifier.optional(),
                defaultPlayerSprites: z.record(z.string().regex(/^[A-Z][A-Z0-9_]{0,99}$/), identifier).optional(),
                defaultBackgroundPaletteIds: z.array(identifier).max(8).optional(),
                defaultSpritePaletteIds: z.array(identifier).max(8).optional(),
                defaultSpritePaletteId: identifier.optional(),
                customColorsEnabled: z.boolean().optional()
            }).strict().refine((settings) => Object.keys(settings).length > 0, {
                message: "Provide at least one setting to update."
            }),
            expectedRevision: z.string().regex(/^[a-f0-9]{64}$/).optional()
        }).strict(),
        annotations: updateExisting
    }, async ({ settings, expectedRevision }) => safely(() => performProjectMutation(async (project, access) => {
        if (expectedRevision !== undefined) {
            await access.strongRefresh();
            if (access.revision !== expectedRevision) {
                throw new GameStudioProjectError("STALE_PROJECT_REVISION", `Expected project revision ${expectedRevision}, but the current revision is ${access.revision}`);
            }
        }
        if (settings.defaultFontId !== undefined) {
            const selectedFont = access.asset({ assetId: settings.defaultFontId }).asset;
            if (selectedFont?.type !== "font") {
                throw new GameStudioProjectError("FONT_NOT_FOUND", `The selected default dialogue font does not exist: ${settings.defaultFontId}`);
            }
        }
        const result = await updateSettings(project.projectPath, settings, access);
        return { ...result, revision: access.revision };
    })));
    server.registerTool("graphics_analyze", {
        title: "Analyze Game Boy pixel art",
        description: "Inspect a real project PNG for dimensions, distinct/flipped tiles, 15-bit GBC colors, palette families, quantization, viewport usage, hardware budgets, and precise violations.",
        inputSchema: z.object({
            assetPath: boundedPath,
            kind: z.enum(["background", "sprite", "tileset"]).optional(),
            colorMode: z.enum(["mono", "mixed", "color"]).optional(),
            allowFlipDeduplication: z.boolean().optional(),
            viewportWidth: dimension.optional(),
            viewportHeight: dimension.optional()
        }).strict(),
        annotations: readOnly
    }, async ({ assetPath, ...options }) => safely(() => performProjectRead((project) => analyzeGraphics(project.projectRoot, assetPath, options))));
    server.registerTool("web_build", {
        title: "Build the official native game browser export",
        description: "Compile the selected native game project with the official make:web command, preserving its genuine Binjgb/WebAssembly browser emulator and reusing a verified export when authored project inputs have not changed.",
        inputSchema: webBuildInput,
        annotations: updateExisting
    }, async (input, extra) => safely(() => performProjectArtifact(async (project, access) => {
        if (input.force === true)
            await access.strongRefresh();
        try {
            return await buildWeb({
                ...input,
                projectRoot: project.projectRoot,
                projectPath: project.projectPath,
                ...configuredToolchain === undefined ? {} : { toolchainRoot: configuredToolchain },
                signal: extra.signal
            });
        } catch (error) {
            const result = webBuildFailureResult(error);
            if (result)
                return result;
            throw error;
        }
    })));
    server.registerTool("web_preview", {
        title: "Preview a game and capture or reopen saved moments",
        description: "Open or refresh the selected project's official player (the engine's own preview). To show the game to the user in Hermes, call chromatic_present_game instead (it shows the game in the hermretro emulator); do not open this URL yourself. If the user says they cannot see that emulator, open studio.playerUrl from chromatic_present_game's result with desktop_preview (action \"open\"). If unavailable, locked or unreachable, keep the URL and state and report the browser limitation; do not launch an external browser. Continue gameplay with public PyBoy emulator_run on the intended exact ROM, then emulator_step/emulator_observe; browser UI and annotation checks remain unverified. Preview URLs are process-local and can expire after plugin restart or a fresh chat. On connection refused, inspect action status; if no live preview exists, select the original project and open again, using the newly returned URL without forcing a rebuild. Do not infer browser-policy failure from connection refused. Preserve unresolved old saves/recordings and explicit access refusals. Reuse only the current active URL for the same task; preserve user play and recording. outputPath, timeoutMs and force apply only to open. Other actions use the already-open player: status lists views, list_states returns saved IDs, and capture_state or restore_state pauses the selected view. Saved states require the exact build; native edits require a rebuild. Input holds ordinary game buttons in the running browser only, with exact status binding, at most 2 seconds. Human input cancels it. Timed video uses start_recording, recording_status, stop_recording and read_capture with the same visible UI recorder. Keep the player open until saved and acknowledged. For an expired URL use action recover on the same project: it only reopens a verified export, never rebuilds or restores unsaved state. No implicit resume or replay; inspect status after uncertainty.",
        inputSchema: webPreviewInput,
        annotations: updateExisting
    }, async (input, extra) => safely(() => performProjectArtifact(async (project, access) => {
        const recordingRead = ["recording_status", "stop_recording", "read_capture"].includes(input.action ?? "");
        if (input.action !== "start_recording" && (input.recordingBinding !== undefined || input.recordingDurationMs !== undefined))
            throw new Error("Recording binding and duration apply only to start_recording.");
        if (input.action === "start_recording" && (!input.recordingBinding || input.recordingId !== undefined || input.viewId !== undefined || input.stateId !== undefined))
            throw new Error("Start recording requires an exact recording binding without state fields.");
        if (recordingRead && (input.viewId !== undefined || input.stateId !== undefined))
            throw new Error("Recording actions cannot include saved-state fields.");
        if (recordingRead !== (input.recordingId !== undefined))
            throw new Error("Recording status, stop and read require the original recordingId.");
        if (input.action !== "input" && (input.binding !== undefined || input.buttons !== undefined || input.durationMs !== undefined))
            throw new Error("Input fields only apply to action input.");
        if (input.action === "dismiss_install_failure" !== (input.installationBinding !== undefined))
            throw new Error("Dismissal requires the exact installation binding; it is not accepted by other actions.");
        if (input.action !== "install_status" && input.installationRequestId !== undefined)
            throw new Error("An installation request ID applies only to install_status.");
        if (["install_status", "dismiss_install_failure"].includes(input.action ?? "") && (input.viewId !== undefined || input.stateId !== undefined))
            throw new Error("Installation control does not accept saved-state fields.");
        if (input.action === "input" && (!input.binding || input.buttons === undefined || input.viewId !== undefined || input.stateId !== undefined))
            throw new Error("Input requires binding and buttons, without state fields.");
        if (input.action && input.action !== "open" && input.action !== "recover") {
            if (input.outputPath !== undefined || input.force !== undefined || input.cacheOnly !== undefined || input.timeoutMs !== undefined)
                throw new Error("Build options only apply to action open.");
            return webPreview.control({ action: input.action, projectRoot: project.projectRoot, viewId: input.viewId, stateId: input.stateId, binding: input.binding, buttons: input.buttons, durationMs: input.durationMs, signal: extra.signal, recordingBinding: input.recordingBinding, recordingDurationMs: input.recordingDurationMs, recordingId: input.recordingId, installationBinding: input.installationBinding, installationRequestId: input.installationRequestId });
        }
        if (input.viewId !== undefined || input.stateId !== undefined)
            throw new Error("View and state IDs only apply to saved-state commands.");
        if (input.action === "recover" && input.force)
            throw new Error("Preview recovery does not force a rebuild. Use open for an intentional rebuild.");
        if (input.force === true)
            await access.strongRefresh();
        let built;
        try {
            built = await buildWeb({
                ...input,
                ...input.action === "recover" ? { cacheOnly: true } : {},
                projectRoot: project.projectRoot,
                projectPath: project.projectPath,
                ...configuredToolchain === undefined ? {} : { toolchainRoot: configuredToolchain },
                signal: extra.signal
            });
        } catch (error) {
            const readiness = await doctor(project.projectRoot, {
                tasks: ["projectBuild"],
                runtimeRoot: session.runtimeRoot,
                toolchainRoot: configuredToolchain ?? session.runtimeRoot,
                nodeExecutable: process.execPath
            }).catch(() => null);
            return {
                ...webBuildFailureResult(error) ?? { success: false, error: error instanceof Error ? error.message : String(error) },
                currentPreview: webPreview.status(),
                recovery: !readiness || readiness.ready ? { action: "inspect_build_error", message: "Preview is not ready. Inspect the build error; do not open a historical URL." } : { action: "prepare_game_tools", tool: "toolchain_prepare", arguments: { components: ["build"] }, message: "Prepare missing game tools, then open this project's preview again. Device drivers are separate." }
            };
        }
        if (!built.success)
            return { ...built, currentPreview: webPreview.status() };
        let preview;
        try {
            if (!built.exportIdentity)
                throw new Error("The browser export has no verified cartridge identity.");
            preview = await webPreview.start(built.outputPath, {
                assetsRoot: WEB_ANNOTATION_ASSETS,
                deviceAssetsRoot: DEVICE_ASSETS,
                romPath: built.exportIdentity.rom.path,
                romSha256: built.exportIdentity.rom.sha256,
                romSizeBytes: built.exportIdentity.rom.sizeBytes,
                sourceRevision: built.sourceRevision,
                projectRoot: project.projectRoot
            });
        } catch (error) {
            return { ...built, success: false, error: error instanceof Error ? error.message : String(error), currentPreview: webPreview.status() };
        }
        return {
            ...built,
            emulator: "binjgb",
            url: preview.url,
            port: preview.port,
            outputPath: built.outputPath,
            indexPath: built.indexPath,
            romPath: built.romPath,
            cached: built.cached,
            sourceRevision: built.sourceRevision,
            reused: preview.reused,
            preview
        };
    })));
    server.registerTool("device_capture", {
        title: "Capture the physical Chromatic USB video feed",
        description: "Open the selected project's physical Chromatic feed for the user to watch. In Hermes Desktop, open the returned URL beside the chat with the desktop_preview tool (action \"open\"); without that tool, give the user the URL. If unavailable, keep the URL and report the blocker without external-browser fallback. Supports macOS and Linux (x64/ARM64); Windows device capture is unavailable. The browser displays native frames and never requests camera or microphone access. On macOS, the user explicitly enables capture in Connection settings and grants normal OS access; tools cannot silently enable it. Optional macOS USB audio must match the same player. On Linux, connect with no Enable step or macOS permission prompt; capture is video-only. list_devices returns exact choices and diagnostic counts; Linux listing briefly opens matching nodes for capabilities without streaming, while macOS listing is passive. permission_status reports platform access state; open_settings opens Connection settings. connect requires inventoryId and exact selection from that list, valid for 60 seconds. start_recording returns a capture ID and deadline (3 minutes default, 10 minutes maximum, 128 MiB); poll status with captureId. Browser visibility does not stop recording. live_frame returns the latest native preview; screenshot saves PNG. read_capture returns the last two frame IDs, a saved screenshot or completed recording (latest by default). stop_recording finalizes 8x integer-upscaled video and keeps the live stream connected; disconnect releases the device. Reuse the active URL; close only owned temporary sessions after user play and saves finish. Do not replay uncertain commands. Native labels and samples do not authenticate the cartridge ROM or prove game FPS.",
        inputSchema: z.object({ action: z.enum(["open", "status", "list_devices", "permission_status", "open_settings", "connect", "disconnect", "screenshot", "live_frame", "read_capture", "start_recording", "stop_recording", "close"]), inventoryId: z.string().uuid().optional(), selection: nativeSelectionSchema.optional(), durationMs: z.number().int().min(1_000).max(600_000).optional(), captureId: z.string().uuid().optional(), tab: z.enum(["connection", "recording"]).optional(), diagnosticTrace: z.boolean().optional().describe("For open only: opt in to bounded service/browser stage evidence before connecting; an existing session must be disconnected and idle to change it."), includeTrace: z.boolean().optional().describe("For status only: return the bounded diagnostic trace when explicitly requested.") }).strict(),
        annotations: { ...changeSession, openWorldHint: true }
    }, async (input) => {
        try {
            const value = await performMutation(async () => {
                if (input.tab !== undefined && input.action !== "open_settings")
                    throw new Error("tab only applies to open_settings.");
                if (input.diagnosticTrace !== undefined && input.action !== "open")
                    throw new Error("diagnosticTrace only applies to open.");
                if (input.includeTrace !== undefined && input.action !== "status")
                    throw new Error("includeTrace only applies to status.");
                if (input.durationMs !== undefined && input.action !== "start_recording")
                    throw new Error("durationMs only applies to start_recording.");
                if (input.captureId !== undefined && !["status", "read_capture"].includes(input.action))
                    throw new Error("captureId only applies to status or read_capture.");
                if (input.action === "connect" ? !input.inventoryId || !input.selection : input.inventoryId !== undefined || input.selection !== undefined)
                    throw new Error("inventoryId and selection are required together for connect and do not apply to other actions.");
                const project = await selectedProject();
                if (input.action === "open")
                    return deviceCapture.open(project.projectRoot, session.selectionGeneration, input.diagnosticTrace);
                if (input.action === "status")
                    return deviceCapture.status(input.captureId, input.includeTrace === true);
                if (input.action === "read_capture")
                    return deviceCapture.readCapture(input.captureId);
                return deviceCapture.control(input.action, input.durationMs, input.inventoryId && input.selection ? { inventoryId: input.inventoryId, selection: input.selection } : undefined, input.tab);
            });
            if ("image" in value && value.image) {
                const { image, ...metadata } = value;
                const result = toolResult(metadata);
                result.content.push({ type: "image", ...image });
                return result;
            }
            return toolResult(value);
        } catch (error) {
            return errorResult(error);
        }
    });
    server.registerTool("web_preview_close", {
        title: "Close the active native game browser preview",
        description: "Stop this plugin instance's local authenticated browser-preview server and invalidate its capability URL without deleting the cached export. Close task-owned temporary previews when finished; preserve a user's ongoing or paused game and unresolved recording/save.",
        inputSchema: emptyInput,
        annotations: { ...changeSession, destructiveHint: true, idempotentHint: true }
    }, async () => safely(async () => {
        try {
            return await webPreview.stop();
        } catch (error) {
            return { closed: false, error: error instanceof Error ? error.message : String(error), currentPreview: webPreview.status() };
        }
    }));
    server.registerTool("rom_build", {
        title: "Build an actual Game Boy ROM",
        description: "Build the selected native game project with the official CLI by default, or compile standalone C with GBDK. Supply only one input path. A project build also captures the debug artifacts emulator_run uses for source debugging, so emulator_debug works on the ROM it returns; pass the returned outputPath to rom_inspect or emulator_run.",
        inputSchema: z.object({
            projectPath: boundedPath.optional().describe("Omit to build the selected .gbsproj. An override must stay within that project; do not combine with sourcePath."),
            sourcePath: boundedPath.optional().describe("Standalone .c source inside the authorized workspace; incompatible with projectPath and debug artifact capture."),
            outputPath: boundedPath.optional().describe("Optional .gb or .gbc output, relative to the selected project for native project builds or to the authorized workspace for standalone C."),
            colorMode: z.enum(["dmg", "gbc", "gbc-only"]).optional(),
            timeoutMs: z.number().int().min(1_000).max(600_000).optional(),
            captureDebugArtifacts: z.boolean().optional().describe("Project builds default to true: matching symbols (about 30 KB in build/<rom>.debug) for emulator_run's source debugging; false skips them. Not for standalone C builds."),
            detail: z.enum(["compact", "full"]).optional().describe("compact (default) reports the debug artifacts' folder and whether source debugging is available; full adds their files, hashes and the build identity.")
        }).strict(),
        annotations: updateExisting
    }, async (input, extra) => safely(() => performEmulatorOperation((signal) => buildSelectedRom({ ...input, signal }), extra.signal)));
    server.registerTool("rom_inspect", {
        title: "Inspect a real cartridge ROM",
        description: "Inspect a .gb or .gbc file, including standalone ROMs inside an authorized workspace; no native game project is required when GB_STUDIO_WORKSPACE_ROOT is configured. Read its exact size and SHA-256, cartridge header, title, color support, mapper, ROM/RAM capacities, Nintendo logo, checksums, and validation status. Use the returned path, sizeBytes, and sha256 to bind Chromatic play or flash to this exact ROM.",
        inputSchema: z.object({ romPath: boundedPath.describe("Relative to the authorized workspace, or an absolute path inside it. Without a workspace, select the containing native game project first. Never select a standalone ROM as a project.") }).strict(),
        annotations: readOnly
    }, async ({ romPath }) => safely(() => inspectRom(romPath, authorizedEmulatorRoot())));
    server.registerTool("toolchain_prepare", {
        title: "Prepare missing game tools",
        description: "Prepare compiler or local emulator dependencies using the installed plugin's managed setup. Use for an authorized build/play request when toolchain_doctor reports missing dependencies. Does not install or register plugins, install device drivers, or activate hardware. Reuses setup-owned components and preserves configured roots and installer locks. Inspect an incomplete result; never blindly retry a refusal. After success continue the original build/preview in this session.",
        inputSchema: z.object({ components: z.array(z.enum(["build", "emulator"])).min(1).max(2) }).strict(),
        annotations: { ...changeSession, openWorldHint: true }
    }, async ({ components }, extra) => safely(() => prepareToolchain(session.runtimeRoot, components, { signal: extra.signal })));
    server.registerTool("toolchain_doctor", {
        title: "Check local game tooling",
        description: "Passively inspect compatible dependency metadata and task readiness for the bound runtime/toolchain. Optional named probes explicitly execute CLI --version, GBDK -v, or isolated emulator imports; no ROM is loaded and metadata readiness is separate from probe health.",
        inputSchema: z.object({
            tasks: z.array(z.enum(["authoring", "projectBuild", "cBuild", "play", "desktop"])).min(1).max(5).optional().describe("Optional readiness filters; omit for the default task set."),
            probes: z.array(z.enum(["cli-version", "gbdk-version", "emulator-import"])).min(1).max(3).optional().describe("Omit for passive metadata only; each named probe explicitly runs a local dependency check.")
        }).strict(),
        annotations: readOnly
    }, async (input, extra) => safely(() => doctor(session.workspaceRoot ?? session.runtimeRoot, {
        ...input,
        runtimeRoot: session.runtimeRoot,
        signal: extra.signal,
        toolchainRoot: readPlatformEnvironmentVariable(process.env, "GB_STUDIO_TOOLCHAIN_ROOT") ?? session.runtimeRoot,
        nodeExecutable: process.execPath,
        pythonPath: readPlatformEnvironmentVariable(process.env, "GB_STUDIO_PYTHON")
    })));
    server.registerTool("emulator_run", {
        title: "Run an actual GB/GBC ROM",
        description: "Start or reuse an isolated headless PyBoy session for the intended genuine ROM. Use it for gameplay checks even when the browser is unavailable, locked or unreachable; no browser session is required. If PyBoy is missing, follow the setup skill's emulator component. Continue with emulator_step/emulator_observe and use emulator_review for retained evidence. Unchanged ROMs retain their live frame and controller state; recording starts a clean bounded recorded boot. Source debugging (emulator_debug) is on when rom_build captured debug artifacts for this exact ROM in this session. This does not verify browser UI or drive physical hardware.",
        inputSchema: z.object({
            romPath: boundedPath.describe("Use the exact cartridge path returned by rom_build or rom_inspect."),
            cgb: z.boolean().optional().describe("On a fresh boot, omit to follow the cartridge default; false forces monochrome DMG, true requests color hardware."),
            initialFrames: initialFrameCount.optional().describe("Frames to advance on a fresh boot only; defaults to 120. Reusing a running ROM does not advance it."),
            restart: z.boolean().optional().describe("Set true for an intentional fresh boot; otherwise an unchanged ROM reuses its current frame and inputs."),
            recording: z.union([z.literal(false), recordingOptionsSchema]).optional().describe("Use an options object (including {}) for a fresh recorded boot; omit or use false to leave recording off for a new boot."),
            debugMode: z.enum(["rom", "source"]).optional().describe("Omit for source when rom_build captured debug artifacts for this exact cartridge in this session, else rom; source requires them; rom turns source debugging off.")
        }).strict(),
        annotations: { ...changeSession, destructiveHint: true }
    }, async ({ romPath, debugMode, ...options }, extra) => safely(() => performEmulatorOperation((signal) => runEmulator(romPath, options, debugMode, signal), extra.signal)));
    server.registerTool("emulator_replay", {
        title: "Replay a recorded attempt on a ROM",
        description: "Boot a ROM, usually one rom_build just rebuilt, the way a recorded attempt booted and play that attempt's inputs again in one call, comparing every frame with the attempt's (coverage:'retained-frames' when an older recording kept only its sampled images). Use it after each rebuild instead of replaying a route by hand. By default the replay stops at the first frame that differs and returns the recorded and replayed images; onDivergence:'continue' plays every input and reports the first difference; toActionIndex replays only up to that action (a recordingSpan's toActionIndex). A replay that starts ends the current session (a refused one leaves it running); the new session stays open where the replay ended, with the last recorded buttons still held, and is recorded as a new attempt (recording:false records nothing), so emulator_step, checkpoints and review continue from there. A cartridge with a real-time clock replays best effort (deterministic:false). Images are the source's retained frame (expected, when it kept one there), the replay's frame at the difference (actual) and the final frame (end). replay.endedSession names the session it ended (with its recording, which it finished when still recording). expect asks for a verdict in the same call (passed, failed, or needs-review when the scene or variables could not be read), and finishRecording stops the replay's recording with that verdict as its outcome, also in the same call, so no other call can come between.",
        inputSchema: z.object({
            romPath: boundedPath.describe("The ROM to replay on: the exact cartridge path returned by rom_build or rom_inspect."),
            recordingPath: boundedPath.optional().describe("The recorded attempt to replay; defaults to the source of a replay that stopped before the end of its route, else the current or most recent recording."),
            sessionId: z.string().regex(/^[0-9a-f]{32}$/u).optional().describe("The attempt's sessionId: the replay is refused, leaving the current session running, when recordingPath holds another attempt."),
            branchId: z.string().max(100).regex(/^branch-[0-9]{4,}$/u).optional().describe("The attempt's branch to replay; defaults to its current branch."),
            toActionIndex: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER).optional().describe("Replay the attempt's actions up to and including this index, such as a recordingSpan's toActionIndex; defaults to all of them."),
            onDivergence: z.enum(["stop", "continue"]).optional().describe("stop (default) ends the replay at the first frame that differs; continue plays every input anyway."),
            recording: z.union([z.literal(false), recordingOptionsSchema]).optional().describe("The replay is recorded with the source attempt's limits; an options object overrides them; false records nothing."),
            expect: replayExpectSchema.optional().describe("What the replay must end in; the result's verdict judges it."),
            finishRecording: z.boolean().optional().describe("true stops the replay's recording where it ended, with the verdict as its outcome; needs a recorded replay."),
            debugMode: z.enum(["rom", "source"]).optional().describe("Omit for source when rom_build captured debug artifacts for this exact cartridge in this session, else rom; source requires them; rom turns source debugging off."),
            includeImages: z.boolean().optional().describe("Set false to receive the report without images."),
            scale: z.number().int().min(1).max(4).optional().describe("Enlarge returned images 1–4× with square pixels; image hashes stay those of the native frames."),
            colorCorrection: emulatorColorCorrection.optional()
        }).strict(),
        annotations: { ...changeSession, destructiveHint: true }
    }, async ({ romPath, debugMode, includeImages = true, scale, colorCorrection, expect, finishRecording = false, ...options }, extra) => {
        try {
            if (finishRecording && options.recording === false)
                throw new EmulatorError("finishRecording stops the replay's recording; leave recording on");
            if (expect?.frames === "ignore" && expect.scene === undefined && expect.variables === undefined)
                throw new EmulatorError("expect checks nothing: give a scene or variables, or leave frames as match");
            if (expect?.variables !== undefined && !(Object.keys(expect.variables).length >= 1 && Object.keys(expect.variables).length <= MAX_REPLAY_EXPECTED_VARIABLES))
                throw new EmulatorError(`expect.variables names 1 to ${MAX_REPLAY_EXPECTED_VARIABLES} variables`);
            return await performEmulatorOperation(async (signal) => {
                const replayed = await replayEmulator(romPath, options, debugMode, signal);
                const colors = frameColors(replayed, colorCorrection);
                const verdict = expect === undefined && !finishRecording ? undefined : await replayVerdict(replayed, expect ?? {});
                let recording = replayed.recording === undefined ? undefined : { recordingPath: replayed.recording.recordingPath, sessionId: replayed.recording.sessionId, branchId: replayed.recording.branchId };
                if (finishRecording && recording !== undefined) {
                    const reason = [...verdict.problems, ...verdict.unreadable === undefined ? [] : [verdict.unreadable]].join(" ").slice(0, 2_000);
                    try {
                        const stopped = await emulator.recordingStop({ outcome: verdict.outcome, ...reason ? { reason } : {} });
                        recording = { ...recording, status: stopped.status, outcome: stopped.outcome };
                    } catch (error) {
                        recording = { ...recording, finishError: error instanceof Error ? error.message : String(error) };
                    }
                }
                const result = toolResult({
                    romSha256: replayed.romSha256,
                    frame: replayed.frame,
                    activeButtons: replayed.activeButtons,
                    debugMode: replayed.debugMode,
                    ...replayed.sourceDebug === undefined ? {} : { sourceDebug: replayed.sourceDebug },
                    replay: replayed.replay,
                    ...verdict === undefined ? {} : { verdict },
                    ...recording === undefined ? {} : { recording },
                    images: replayed.samples.map(({ role, frame, sha256 }) => ({ role, frame, sha256 })),
                    imageDelivery: {
                        status: includeImages ? "available" : "omitted",
                        ...includeImages && scale !== undefined ? { scale } : {},
                        ...includeImages && colorCorrection !== undefined ? { colorCorrection: colors } : {}
                    }
                });
                if (includeImages) {
                    for (const sample of replayed.samples)
                        result.content.push({ type: "image", data: framePng(sample, colors, scale).toString("base64"), mimeType: "image/png" });
                }
                return result;
            }, extra.signal);
        } catch (error) {
            return errorResult(error);
        }
    });
    /** A replay's verdict on expect, read where it ended within the replay's own operation: failed when a frame differs
     *  (unless frames is ignore), not every input to toActionIndex played, or the scene or a variable is another;
     *  needs-review when they could not be read; else passed. */
    async function replayVerdict(replayed, expect) {
        const { replay } = replayed;
        const problems = [];
        if ((expect.frames ?? "match") === "match" && replay.status === "diverged") {
            const at = replay.divergence;
            problems.push(`Frame ${at.frame} (action ${at.actionIndex}) differs from the recording; the last matching frame was ${at.lastMatchedFrame}.`);
        } else if (replay.replayedActions !== replay.toActionIndex) {
            problems.push(`The replay played ${replay.replayedActions} of ${replay.toActionIndex} actions.`);
        }
        const names = Object.keys(expect.variables ?? {});
        const judged = (unreadable, observed) => ({
            outcome: problems.length ? "failed" : unreadable === undefined ? "passed" : "needs-review",
            problems,
            ...unreadable === undefined ? {} : { unreadable },
            ...observed === undefined ? {} : { observed }
        });
        if (expect.scene === undefined && names.length === 0)
            return judged();
        if (replayed.debugMode !== "source")
            return judged("The scene and variables are read only on a ROM rom_build built in this session: rebuild it and replay again.");
        let state;
        try {
            state = await inspectSource({ includeScene: expect.scene !== undefined, referenceLimit: 0, ...names.length ? { variableNames: names } : { variableIds: [] } });
        } catch (error) {
            return judged(error instanceof Error ? error.message : String(error));
        }
        const observed = {};
        if (expect.scene !== undefined) {
            observed.scene = state.scene?.name ?? null;
            if (expect.scene !== state.scene?.name && expect.scene !== state.scene?.symbol)
                problems.push(`The replay ended in scene ${JSON.stringify(observed.scene)}, not ${JSON.stringify(expect.scene)}.`);
        }
        if (names.length) {
            if (state.variables.length !== names.length)
                return judged("expect.variables names one variable twice: name it once.", observed);
            observed.variables = {};
            names.forEach((name, index) => {
                const variable = state.variables[index];
                observed.variables[name] = variable.value;
                if (expect.variables[name] !== variable.value && expect.variables[name] !== variable.unsignedValue)
                    problems.push(`${name} is ${variable.value} where the replay ended, not ${expect.variables[name]}.`);
            });
        }
        return judged(undefined, observed);
    }
    function compactObservation(observation) {
        const { fromPrefixPin: _fromPrefixPin, ...recordingSpan } = observation.recordingSpan ?? {};
        return {
            frame: observation.frame,
            startFrame: observation.startFrame,
            advancedFrames: observation.advancedFrames,
            activeButtons: observation.activeButtons,
            sampledButtons: observation.sampledButtons,
            samples: observation.samples.map(({ frame, sha256, inputIndex }) => ({ frame, sha256, ...inputIndex === undefined ? {} : { inputIndex } })),
            ...observation.recordingSpan === undefined ? {} : { recordingSpan }
        };
    }
    /** The color correction returned frames get: the Chromatic's when asked and the session runs on color hardware. */
    function frameColors(observation, colorCorrection) {
        return colorCorrection === "chromatic" && observation.cgb === true ? "chromatic" : "none";
    }
    function framePng(sample, colors, scale) {
        return displayPng(Buffer.from(sample.pngBase64, "base64"), { colorCorrection: colors, magnification: scale ?? 1 });
    }
    function observationImages(observation, imageLayout, scale, colors, signal) {
        try {
            if (imageLayout !== "contact-sheet") {
                return { pngs: observation.samples.map((sample) => framePng(sample, colors, scale)) };
            }
            const { png, ...sheet } = renderContactSheetPng({
                signal,
                ...scale === undefined ? {} : { magnification: scale },
                colorCorrection: colors,
                title: "RUNTIME SAMPLES / GAPS NOT SHOWN",
                subtitle: `FRAMES ${observation.startFrame}-${observation.frame} / ${observation.samples.length} SAMPLES / NO EXTRA STEPS`,
                images: observation.samples.map((sample) => ({
                    png: Buffer.from(sample.pngBase64, "base64"),
                    sha256: sample.sha256,
                    label: `FRAME ${sample.frame}`,
                    caption: `INPUT ${sample.sampledButtons.length ? sample.sampledButtons.join(" + ") : "NONE"}`
                }))
            });
            return { pngs: [png], sheet };
        } catch (cause) {
            const error = new EmulatorError(`Image delivery failed: ${cause instanceof Error ? cause.message : "unknown composition failure"}. Recover with observe or recorded review, not another step.`, { cause });
            error.execution = observation.execution ?? {
                status: "completed",
                startFrame: observation.startFrame,
                frame: observation.frame,
                advancedFrames: observation.advancedFrames,
                appliedButtons: observation.appliedButtons,
                sampledButtons: observation.sampledButtons
            };
            error.imageDelivery = { status: "failed", recovery: "Use emulator_observe or emulator_review with individual native images. Do not repeat delivered input." };
            throw error;
        }
    }
    function observationResult(observation, { includeImages = true, imageLayout = "individual", scale, colorCorrection, detail = "compact", liveState, session }, signal) {
        const colors = frameColors(observation, colorCorrection);
        const images = includeImages ? observationImages(observation, imageLayout, scale, colors, signal) : { pngs: [] };
        const result = toolResult({
            ...detail === "full" ? {
                ...observation,
                samples: observation.samples.map(({ pngBase64: _bytes, ...sample }) => sample),
                genuineEmulatorFrames: true
            } : compactObservation(observation),
            ...liveState === undefined ? {} : { debug: liveState },
            ...session === undefined ? {} : { session },
            imageDelivery: {
                status: includeImages ? "available" : "omitted",
                sampleCount: observation.samples.length,
                ...includeImages && imageLayout === "individual" && scale !== undefined ? { scale } : {},
                ...includeImages && colorCorrection !== undefined ? { colorCorrection: colors } : {}
            },
            ...imageLayout === "contact-sheet" ? {
                contactSheet: images.sheet === undefined ? { status: "omitted", reason: "includeImages:false" } : {
                    status: "available",
                    provenance: "emulator-sample-contact-sheet",
                    ...images.sheet,
                    sampleIndices: observation.samples.map((_, index) => index),
                    extraFramesAdvanced: 0
                }
            } : {}
        });
        for (const png of images.pngs)
            result.content.push({ type: "image", data: png.toString("base64"), mimeType: "image/png" });
        return result;
    }
    server.registerTool("emulator_step", {
        title: "Play exact frames and observe the result",
        description: "Hold exact button sets for exact native frames and return genuine sampled PNGs. Give buttons and frames for one held set, or inputs for an ordered sequence run in this one call (at most 64 inputs, 3,600 frames and 8 samples in all): send a press, wait and press again as one inputs list, not as repeated identical calls. Each set is complete: buttons persist after the call, the same set does not release/repress them, and [] is neutral. Nothing advances between calls. By default the last frame is sampled and the result is compact; ask for more samples with sampleCount or sample:true, larger images with scale, or every field with detail:'full'. Optional imageLayout:'contact-sheet' lays out the SAME samples with frame/input labels, adding no steps or captures. To see the player, actors, dialogue or variables after the inputs, add debug (emulator_debug's selectors) instead of calling emulator_debug after the step. Errors separate confirmed execution from image delivery: never repeat input merely to recover an image. To look without advancing, use emulator_observe. After emulator_recording stop, steps are refused until emulator_run boots again or emulator_replay, given the recordingPath and branchId stop returned, continues from the recording. colorCorrection:'chromatic' shows color-hardware frames as the Chromatic does.",
        inputSchema: domainSchemas.emulatorStep,
        annotations: changeSession
    }, async ({ includeImages, imageLayout, scale, colorCorrection, detail, debug, ...options }, extra) => {
        try {
            return await performEmulatorOperation(async (signal) => {
                const observation = await emulator.playStep(options, signal);
                const liveState = debug === undefined ? undefined : await stepLiveState(debug);
                const session = liveState?.error !== undefined && !emulator.active ? lostSession(observation) : undefined;
                return observationResult(observation, { includeImages, imageLayout, scale, colorCorrection, detail, liveState, session }, signal);
            }, extra.signal);
        } catch (error) {
            return errorResult(error);
        }
    });
    server.registerTool("emulator_observe", {
        title: "Observe the current genuine framebuffer",
        description: "Return the current real 160×144 framebuffer and frame/input metadata without advancing frames, changing controller state, writing files, or appending recording events. Optional scale enlarges the image; imageLayout:'contact-sheet' labels that same image in memory; the individual PNG remains the default. The result is compact unless detail:'full'. It accepts no actions. Applied input and last-sampled input are reported separately. colorCorrection:'chromatic' shows color-hardware frames as the Chromatic does. Use emulator_step to play.",
        inputSchema: domainSchemas.emulatorObserve,
        annotations: readOnly
    }, async (options, extra) => {
        try {
            return await performEmulatorOperation(async (signal) => observationResult(await emulator.observe(), options, signal), extra.signal);
        } catch (error) {
            return errorResult(error);
        }
    });
    server.registerTool("emulator_inspect", {
        title: "Inspect bounded emulator state",
        description: "Read hardware OAM or bounded memory (up to 2,048 bytes) without advancing frames. The memory and vram views require region, offset and length; vram accepts only region:'vram'. visibleOnly, limit and includeScanlineSummary apply only to the oam view. For variables, scene names, actor positions or dialogue state, use emulator_debug.",
        inputSchema: domainSchemas.emulatorInspect,
        annotations: readOnly
    }, async (input) => safely(() => performEmulatorOperation(async () => {
        let inspection;
        switch (input.view) {
            case "oam":
                inspection = {
                    view: "oam",
                    ...input.visibleOnly === undefined ? {} : { visibleOnly: input.visibleOnly },
                    ...input.limit === undefined ? {} : { limit: input.limit },
                    ...input.includeScanlineSummary === undefined ? {} : { includeScanlineSummary: input.includeScanlineSummary }
                };
                break;
            case "memory":
            case "vram":
                if (input.region === undefined || input.offset === undefined || input.length === undefined) {
                    throw new Error("Memory inspection requires a named region, offset, and bounded byte length.");
                }
                inspection = {
                    view: input.view,
                    region: input.region,
                    offset: input.offset,
                    length: input.length,
                    ...input.bank === undefined ? {} : { bank: input.bank }
                };
                break;
        }
        return emulator.inspect(inspection);
    })));
    server.registerTool("emulator_audio", {
        title: "Check which sound channels the game drives",
        description: "Read the Game Boy sound hardware's registers on the current frame without advancing. active is true when the sound hardware is on and a channel (pulse1, pulse2, wave, noise) is enabled, its DAC on and sent to a speaker; each channel reports active, enabled, dac, panned, and startVolume (pulse and noise envelope start, 0–15) or outputLevel (wave). Registers show what the game drives, not what comes out: a pulse or noise note whose envelope has faded stays active until the next note or cut. This is one frame: check a short sound effect on the frames just after it starts. A song keeps its channels active between notes.",
        inputSchema: emptyInput,
        annotations: readOnly
    }, async () => safely(() => performEmulatorOperation(() => emulator.audio())));
    server.registerTool("emulator_status", {
        title: "Inspect active emulator state",
        description: "With a ROM open, report its identity, native frame count, paused clock, execution time, recording limits, screen size, and held buttons without advancing. To check whether an emulator is active without starting a worker, use session_status and read emulatorActive.",
        inputSchema: emptyInput,
        annotations: readOnly
    }, async () => safely(async () => ({ ...await emulator.status(), debugMode: activeSourceDebug === undefined ? "rom" : "source" })));
    server.registerTool("emulator_close", {
        title: "Close active emulator session",
        description: "Cancel queued or in-flight play/build work, retain recording evidence, stop the isolated worker, and wait for cleanup. Safe to repeat; never deletes prior attempts.",
        inputSchema: emptyInput,
        annotations: { ...changeSession, destructiveHint: true, idempotentHint: true }
    }, async () => safely(async () => {
        await closeEmulatorSession();
        return { closed: true };
    }));
    registerPlaytestTools({
        server,
        emulator: () => emulator,
        authorizedRoot: authorizedEmulatorRoot,
        runOperation: performAuthorizedEmulatorOperation,
        toolResult,
        errorResult,
        safely,
        sourceDebug: inspectSource
    });
    registerProjectDomains(server, {
        runRead: performProjectRead,
        runMutation: performProjectMutation,
        runTransaction: performProjectTransaction,
        safely
    });
    registerChromaticTools(server, {
        service: chromatic,
        authorizedRoot: async () => {
            await initialized;
            return session.authorizedOperationRoot();
        },
        toolResult,
        errorResult
    });
    return {
        server,
        close: () => {
            closing = true;
            return closePromise ??= (async () => {
                const outcomes = await Promise.allSettled([chromatic.close(), webPreview.dispose(), deviceCapture.dispose(), closeEmulatorSession()]);
                session.close();
                await server.close();
                const failures = outcomes.filter((outcome) => outcome.status === "rejected").map((outcome) => outcome.reason);
                if (failures.length)
                    throw new AggregateError(failures, "One or more plugin services did not close cleanly");
            })();
        }
    };
}
async function main() {
    const { server, close } = createGbStudioServer();
    const transport = new StdioServerTransport();
    let stopping = false;
    const shutdown = () => {
        if (stopping)
            return;
        stopping = true;
        void close().catch((error) => {
            const message = error instanceof Error ? error.message : String(error);
            process.stderr.write(`${SERVER_NAME}: ${message}\n`);
            process.exitCode = 1;
        });
    };
    process.on("SIGINT", shutdown);
    process.on("SIGTERM", shutdown);
    process.on("SIGHUP", shutdown);
    process.stdin.once("end", shutdown);
    process.stdin.once("close", shutdown);
    await server.connect(transport);
}
const entrypoint = process.argv[1];
if (entrypoint && import.meta.url === pathToFileURL(path.resolve(entrypoint)).href) {
    main().catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        process.stderr.write(`${SERVER_NAME}: ${message}\n`);
        process.exitCode = 1;
    });
}
export {
    createGbStudioServer,
    runWithSourceDebugState
};
