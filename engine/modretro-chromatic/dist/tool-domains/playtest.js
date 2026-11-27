import { createHash } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, realpath } from "node:fs/promises";
import { z } from "zod";
import { renderContactSheetPng } from "../contact-sheet.js";
import { MAX_EMULATOR_FRAMES, MAX_EMULATOR_CLIP_CUTS, MAX_EMULATOR_RECORDING_BYTES, MAX_EMULATOR_RECORDING_EVENTS, MAX_EMULATOR_RECORDING_FRAMES, MAX_EMULATOR_REVIEW_ACTIONS, MAX_EMULATOR_REVIEW_IMAGES, MAX_EMULATOR_REVIEW_METADATA_BYTES, } from "../emulator.js";
import { isPathWithinRoot } from "../platform.js";
import { boundedPath, identifier, imageLayoutSchema, liveStateSelectors } from "./schemas.js";
const readOnly = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
const changeSession = { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false };
export const recordingOptionsSchema = z.object({
    outputPath: boundedPath.optional(),
    sampleEveryFrames: z.number().int().min(1).max(3_600).optional(),
    recentFrameCount: z.number().int().min(1).max(64).optional(),
    maxBytes: z.number().int().min(65_536).max(512 * 1024 * 1024).optional(),
    maxFrames: z.number().int().min(1).max(216_000).optional(),
    maxWallTimeMs: z.number().int().min(1).max(3_600_000).optional(),
}).strict();
export const MAX_REPLAY_EXPECTED_VARIABLES = 8;
export const replayExpectSchema = z.object({
    frames: z.enum(["match", "ignore"]).optional().describe("match (default): a frame that differs from the recording fails; ignore: only the scene and variables decide (replay with onDivergence:'continue')."),
    scene: z.string().trim().min(1).max(256).optional().describe("The scene's name or symbol where the replay ends, read in source debug mode."),
    variables: z.record(z.string().trim().min(1).max(256), z.number().int().min(-32_768).max(65_535)).optional().describe(`Up to ${MAX_REPLAY_EXPECTED_VARIABLES} variable names or symbols and their values where the replay ends, read in source debug mode.`),
}).strict();
export const recordingPrefixPinSchema = z.object({
    eventCount: z.number().int().min(1).max(MAX_EMULATOR_RECORDING_EVENTS),
    eventDigest: z.string().regex(/^[0-9a-f]{64}$/u),
    byteLength: z.number().int().min(1).max(MAX_EMULATOR_RECORDING_BYTES),
    sha256: z.string().regex(/^[0-9a-f]{64}$/u),
}).strict();
const recordingReviewShape = {
    recordingPath: boundedPath.optional().describe("Optional recording directory; use the path returned when recording began or omit for the current/recent recording."),
    sessionId: z.string().regex(/^[0-9a-f]{32}$/u).describe("Exact sessionId from emulator_step's recordingSpan."),
    branchId: z.string().max(100).regex(/^branch-[0-9]{4,}$/u).describe("Exact branchId from the same recordingSpan."),
    fromActionIndex: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER).describe("Exclusive normalized start boundary from recordingSpan; equal bounds request an empty interval."),
    toActionIndex: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER).describe("Inclusive normalized end boundary from the same recordingSpan."),
    fromFrame: z.number().int().min(0).max(MAX_EMULATOR_RECORDING_FRAMES).optional().describe("Optional with toFrame; both must match the selected normalized action boundaries."),
    toFrame: z.number().int().min(0).max(MAX_EMULATOR_RECORDING_FRAMES).optional().describe("Optional with fromFrame; both must match the selected normalized action boundaries."),
    prefixPin: recordingPrefixPinSchema.optional().describe("Optional exact prefixPin returned in recordingSpan; protects the reviewed journal prefix."),
    maxImages: z.number().int().min(1).max(MAX_EMULATOR_REVIEW_IMAGES).optional().describe(`Maximum returned real samples, 1 to ${MAX_EMULATOR_REVIEW_IMAGES}; defaults to four. Review a longer interval in parts.`),
};
function validateRecordingReview(input, context) {
    if (input.toActionIndex < input.fromActionIndex || input.toActionIndex - input.fromActionIndex > MAX_EMULATOR_REVIEW_ACTIONS) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: ["toActionIndex"], message: `Review requires an ordered interval of at most ${MAX_EMULATOR_REVIEW_ACTIONS} normalized actions.` });
    }
    if ((input.fromFrame === undefined) !== (input.toFrame === undefined)) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: ["fromFrame"], message: "Review frame bounds must be supplied together." });
    }
    if (input.fromFrame !== undefined && input.toFrame !== undefined &&
        (input.toFrame < input.fromFrame || input.toFrame - input.fromFrame > MAX_EMULATOR_FRAMES)) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: ["toFrame"], message: `Review requires an ordered interval of at most ${MAX_EMULATOR_FRAMES} native frames.` });
    }
}
export const recordingReviewSchema = z.object(recordingReviewShape).strict().superRefine(validateRecordingReview);
// Keep the registered v3 schema a plain object: the SDK's discovery conversion
// does not expose fields wrapped in ZodEffects. Cross-field checks run below.
const recordingReviewToolSchema = z.object({
    ...recordingReviewShape,
    includeImages: z.boolean().optional().describe("Set false to receive metadata without inline images in either layout."),
    imageLayout: imageLayoutSchema.optional().describe("Individual images are the default; contact-sheet labels the same samples in memory without new captures or file writes."),
}).strict();
async function reviewedImage(frame, authorizedRoot) {
    const root = await realpath(authorizedRoot);
    const path = await realpath(frame.path);
    const entry = await lstat(frame.path);
    if (!isPathWithinRoot(root, path) || entry.isSymbolicLink() || !entry.isFile() || entry.size > 1024 * 1024) {
        throw new Error("Review images must be bounded regular files inside the authorized workspace.");
    }
    const file = await open(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
    try {
        const before = await file.stat();
        if (!before.isFile() || before.size > 1024 * 1024)
            throw new Error("The recorded review image exceeds its byte limit.");
        // A fixed-size read also bounds a file that is concurrently replaced/grown.
        const buffer = Buffer.alloc(before.size + 1);
        let count = 0;
        while (count < buffer.length) {
            const read = await file.read(buffer, count, buffer.length - count, count);
            if (read.bytesRead === 0)
                break;
            count += read.bytesRead;
        }
        const after = await file.stat();
        if (count !== before.size || after.size !== before.size || after.mtimeMs !== before.mtimeMs ||
            await realpath(frame.path) !== path)
            throw new Error("The recorded review image changed while being read.");
        const bytes = buffer.subarray(0, count);
        if (bytes.length < 24 || !bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) ||
            bytes.readUInt32BE(16) !== 160 || bytes.readUInt32BE(20) !== 144 ||
            createHash("sha256").update(bytes).digest("hex") !== frame.sha256) {
            throw new Error("Recorded review image failed PNG/dimension/digest verification.");
        }
        return bytes;
    }
    finally {
        await file.close();
    }
}
export const sourceDebugQuerySchema = z.object({
    ...liveStateSelectors,
    collisions: z.object({
        x: z.number().int().min(0).max(255),
        y: z.number().int().min(0).max(255),
        width: z.number().int().min(1).max(256),
        height: z.number().int().min(1).max(256),
    }).strict().optional(),
    referenceLimit: z.number().int().min(0).max(64).optional().describe("Authored references to the scene and selected variables; defaults to 0 (compact) or 16 (full)."),
    detail: z.enum(["compact", "full"]).optional().describe("compact (default): frame, scene, live state, variables and what you ask for. full adds the build identity, the standing limitations and references."),
}).strict();
export function registerPlaytestTools(context) {
    const { server, safely } = context;
    server.registerTool("emulator_review", {
        title: "Review committed recorded inputs and sampled frames",
        description: `Review a recorded input interval (fromActionIndex,toActionIndex] using the recordingSpan returned by emulator_step. Returns verified retained samples, known physical input-delivery records, pins, missing endpoints and sampling gaps; never captures or advances play. Empty intervals and post-close reads are supported. Maximum 3,600 native frames, 4,096 actions, ${MAX_EMULATOR_REVIEW_IMAGES} images and 2 MiB metadata. Integrity does not establish a gameplay outcome.`,
        inputSchema: recordingReviewToolSchema,
        annotations: readOnly,
    }, async ({ includeImages = true, imageLayout = "individual", ...input }) => {
        try {
            const validated = recordingReviewSchema.parse(input);
            return await context.runOperation(async () => {
                const review = await context.emulator().recordingReview(validated);
                if (review.frames.length > (validated.maxImages ?? 4))
                    throw new Error("The recording review returned too many images.");
                const images = [];
                if (includeImages) {
                    const root = context.authorizedRoot();
                    for (const frame of review.frames) {
                        images.push(await reviewedImage(frame, root));
                    }
                }
                if (imageLayout === "contact-sheet") {
                    const sheetResult = (contactSheet) => {
                        const value = { ...review, contactSheet };
                        if (Buffer.byteLength(JSON.stringify(value), "utf8") > MAX_EMULATOR_REVIEW_METADATA_BYTES) {
                            throw new Error("The recording review including contact-sheet metadata exceeds its byte limit.");
                        }
                        return context.toolResult(value);
                    };
                    if (images.length === 0)
                        return sheetResult({
                            status: includeImages ? "unavailable" : "omitted", reason: includeImages ? "no-retained-frames" : "includeImages:false",
                        });
                    const { png, ...sheet } = renderContactSheetPng({
                        title: "RECORDED SAMPLES / GAPS NOT SHOWN",
                        subtitle: `SESSION PREFIX ${review.sessionId.slice(0, 12)} / ${review.branchId}`,
                        images: images.map((png, index) => {
                            const frame = review.frames[index];
                            return {
                                png, sha256: frame.sha256, label: `FRAME ${frame.frame} / ACTION ${frame.actionIndex}`,
                                caption: `${frame.origin.kind === "direct" ? "DIRECT RECORD" : "IMPORTED PREFIX"} / INPUTS IN METADATA`,
                            };
                        }),
                    });
                    const result = sheetResult({
                        status: "available", provenance: "recorded-frame-contact-sheet", ...sheet,
                        frameIndices: review.frames.map((_, index) => index), extraFramesCaptured: 0,
                    });
                    result.content.push({ type: "image", data: png.toString("base64"), mimeType: "image/png" });
                    return result;
                }
                const result = context.toolResult(review);
                for (const bytes of images)
                    result.content.push({ type: "image", data: bytes.toString("base64"), mimeType: "image/png" });
                return result;
            });
        }
        catch (error) {
            return context.errorResult(error);
        }
    });
    server.registerTool("emulator_checkpoint", {
        title: "Save or branch from an opaque checkpoint",
        description: "Save a paused, neutral, sampled state or restore it into the same ROM and runtime: the exact ROM, or a rebuild of the unchanged project. Saving needs an active recording (emulator_run with recording:{}, not yet stopped) and a sampled neutral frame: no held buttons, and the last emulator_step ended with buttons:[] for at least one frame, such as a final input {buttons:[],frames:1}. Restoring preserves the original attempt and starts a new recorded branch; incompatible or stale states fail before loading.",
        inputSchema: z.object({
            action: z.enum(["save", "restore"]),
            checkpointId: identifier.optional().describe("Restore only; required checkpointId returned by save."),
            recordingPath: boundedPath.optional().describe("Restore only; optional directory containing the original recording and checkpoint."),
            label: z.string().trim().min(1).max(160).optional().describe("Save only; an optional label for the new checkpoint."),
        }).strict(),
        annotations: changeSession,
    }, async (input) => safely(() => context.runOperation(async () => {
        if (input.action === "save") {
            if (input.checkpointId !== undefined || input.recordingPath !== undefined)
                throw new Error("Checkpoint save accepts only an optional label.");
            return context.emulator().checkpointSave({ ...(input.label === undefined ? {} : { label: input.label }) });
        }
        if (input.checkpointId === undefined)
            throw new Error("Checkpoint restore requires checkpointId.");
        if (input.label !== undefined)
            throw new Error("Checkpoint restore does not accept a new label.");
        return context.emulator().checkpointRestore({ checkpointId: input.checkpointId, ...(input.recordingPath === undefined ? {} : { recordingPath: input.recordingPath }) });
    })));
    server.registerTool("emulator_recording", {
        title: "Inspect, finish, archive or retrieve a recorded attempt",
        description: "Inspect/export history, stop the active recording, or archive/retrieve/restore it. stop finalizes the recording and ends its session: steps, input and checkpoints are refused until emulator_run boots again (restart:true, or recording:{} to record), and emulator_replay with the recordingPath and branchId stop returns continues from where it ended (it reached the end when replay.replayedActions equals replay.source.actionCount). access_diagnostic takes only action; without a worker, lease, recording read or process probe, it cannot prove liveness or authorize recovery. Maintenance requires closed transports and exclusive client access. Archive moves unchanged bytes in the project, preserves original-path mapping and releases admission reservation, not disk space. Retrieval verifies provenance without an emulator; restore reinstates quota.",
        inputSchema: z.object({
            action: z.enum(["status", "export", "stop", "archive", "retrieve", "restore", "access_diagnostic"]),
            recordingPath: boundedPath.optional().describe("Required and the only other input for archive/retrieve/restore; optional for status/export; do not pass for stop or access_diagnostic."),
            branchId: identifier.optional().describe("Export only; select a recorded branch. Omit to use the current/default branch."),
            actionOffset: z.number().int().min(0).max(216_000).optional().describe("Export action offset; use nextActionOffset for the next page. This does not page evidence."),
            limit: z.number().int().min(1).max(128).optional().describe("Export returns up to 64 actions by default and the latest min(limit, 32) evidence samples. Check counts and truncation for omissions."),
            outcome: z.enum(["passed", "failed", "needs-review", "cancelled"]).optional().describe("Stop only; optional assessment when finalizing the active recording."),
            reason: z.string().max(1_000).optional().describe("Stop only; optional explanation for the active recording's outcome."),
        }).strict(),
        annotations: changeSession,
    }, async (input) => safely(() => {
        if (input.action === "access_diagnostic") {
            if (Object.keys(input).some(key => key !== "action"))
                throw new Error("Access diagnosis accepts only action; no recording is opened.");
            const root = context.authorizedRoot();
            const emulator = context.emulator();
            if (emulator.projectRoot !== root)
                throw new Error("Recording access diagnosis is unresolved while the authorized root binding is changing.");
            // Do not queue behind a pending worker or attempt to acquire its lease.
            return Promise.resolve(emulator.recordingAccessDiagnostic());
        }
        return context.runOperation(async () => {
            const emulator = context.emulator();
            if (input.action === "archive" || input.action === "retrieve" || input.action === "restore") {
                if (input.recordingPath === undefined || Object.keys(input).some(key => !["action", "recordingPath"].includes(key))) {
                    throw new Error("Recording maintenance requires only action and an explicit recordingPath");
                }
                return emulator.recordingMaintain({ action: input.action, recordingPath: input.recordingPath });
            }
            if (input.action === "status")
                return emulator.recordingStatus({ recordingPath: input.recordingPath });
            if (input.action === "stop") {
                if (input.recordingPath !== undefined || input.branchId !== undefined)
                    throw new Error("Only the active recording can be finalized.");
                return emulator.recordingStop({ outcome: input.outcome, reason: input.reason });
            }
            const exported = await emulator.recordingExport({ recordingPath: input.recordingPath, branchId: input.branchId });
            const offset = input.actionOffset ?? 0;
            const limit = input.limit ?? 64;
            return {
                ...exported,
                actions: exported.actions.slice(offset, offset + limit),
                evidence: exported.evidence.slice(-Math.min(limit, 32)),
                actionCount: exported.actions.length,
                evidenceCount: exported.evidence.length,
                actionOffset: offset,
                nextActionOffset: offset + limit < exported.actions.length ? offset + limit : null,
                truncation: { actions: offset > 0 || offset + limit < exported.actions.length, evidence: exported.evidence.length > Math.min(limit, 32) },
            };
        });
    }));
    server.registerTool("emulator_clip", {
        title: "Extract a supporting playtest clip",
        description: "Extract a GIF from genuine retained recorded frames without reopening or advancing a ROM. Restore maintenance-archived recordings first with emulator_recording. Requires exact retained endpoints, at most 600 selected frame occurrences and 60 seconds of native game time. Sparse samples are held, never interpolated; output never overwrites files. Returns source/output timing, gaps and digest.",
        inputSchema: z.object({
            outputPath: boundedPath.describe("New .gif path inside the recording directory or the authorized artifacts directory."),
            recordingPath: boundedPath.optional().describe("Optional retained or restored recording directory; maintenance archives must be restored first."),
            branchId: identifier.optional().describe("Optional recorded branch to use for the source frames."),
            startFrame: z.number().int().min(0).max(216_000).optional().describe("Inclusive start for one interval; do not combine with cuts."),
            endFrame: z.number().int().min(0).max(216_000).optional().describe("Inclusive end for one interval; do not combine with cuts."),
            maxFrames: z.number().int().min(1).max(600).optional(),
            cuts: z.array(z.object({
                startFrame: z.number().int().min(0).max(216_000),
                endFrame: z.number().int().min(0).max(216_000),
            }).strict()).min(1).max(MAX_EMULATOR_CLIP_CUTS).optional().describe("One to 16 ordered inclusive intervals; repeats are preserved. Do not combine with top-level startFrame or endFrame."),
        }).strict(),
        annotations: changeSession,
    }, async (input) => safely(() => context.runOperation(() => context.emulator().clip(input))));
    server.registerTool("emulator_debug", {
        title: "Inspect authenticated author state",
        description: "Read the current scene, variable values, live state and authored collision tiles and references while paused. live reports the player (and named actors) tile and pixel position, direction, moving and moveSpeed (scripted moves and top-down walking; a platformer player reports platform state and velocities in pixels per frame instead), withheld while sceneLoading; ui: overlayOpen, dialogue (none, drawing, waiting, menu or unknown) and the buttons the script that owns input accepts next; scripts: running count and whether the VM is locked. To read it after playing, pass debug to emulator_step instead. Works on a ROM rom_build built in this session (it captures debug artifacts by default) once emulator_run starts it. Rejects stale source/artifacts or different ROM bytes; unavailable in ROM-only mode.",
        inputSchema: sourceDebugQuerySchema,
        annotations: readOnly,
    }, async (input) => safely(() => context.runOperation(() => context.sourceDebug(input))));
}
