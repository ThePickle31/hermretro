import { execFile, spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { constants, writeFileSync } from "node:fs";
import fs from "node:fs/promises";
import { access, lstat, mkdir, mkdtemp, readdir, readFile, realpath, rename, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { promisify } from "node:util";
import { detectDependencies, probeDependencies } from "../scripts/dependency-doctor.mjs";
export { detectDependencies, probeDependencies } from "../scripts/dependency-doctor.mjs";
import { findGbStudioCli, resolveToolchainRoot } from "./compiler-selection.js";
import { hashDebugRom, parseGlobalsDefinitions, parseNoiDefinitions } from "./debug-symbols.js";
import { captureBuildSourceProvenance, LIVE_STATE_ENGINE_SHA256, LIVE_STATE_LAYOUT, rememberAuthenticatedSourceBuild, sameBuildSourceObservation, verifyBuildDebugAbi, } from "./build-provenance.js";
import { deprecatedEventGuidance, unavailableEventMessage, unknownEventMessage } from "./event-catalog.js";
import { assertSafePlatformPath, isPathWithinRoot, readPlatformEnvironmentVariable, runtimeExecutablePaths, sanitizeSubprocessEnvironment, verifyWindowsPrivatePath, } from "./platform.js";
import { isSystemError } from "./project-files.js";
const execFileAsync = promisify(execFile);
const MAX_TIMEOUT_MS = 600_000;
const DEFAULT_TIMEOUT_MS = 120_000;
const SUCCESS_STDOUT_TAIL_LINES = 20;
const BUILD_LOG_DIRECTORY = path.join("build", "logs");
const HEADER_MINIMUM_BYTES = 0x150;
const MAX_ROM_BYTES = 8 * 1024 * 1024;
const NINTENDO_LOGO = Buffer.from(("ce ed 66 66 cc 0d 00 0b 03 73 00 83 00 0c 00 0d " +
    "00 08 11 1f 88 89 00 0e dc cc 6e e6 dd dd d9 99 " +
    "bb bb 67 63 6e 0e ec cc dd dc 99 9f bb b9 33 3e").replace(/\s+/g, ""), "hex");
const CARTRIDGE_TYPES = {
    0x00: { name: "ROM ONLY", mapper: "none" },
    0x01: { name: "MBC1", mapper: "MBC1" },
    0x02: { name: "MBC1+RAM", mapper: "MBC1" },
    0x03: { name: "MBC1+RAM+BATTERY", mapper: "MBC1" },
    0x05: { name: "MBC2", mapper: "MBC2" },
    0x06: { name: "MBC2+BATTERY", mapper: "MBC2" },
    0x08: { name: "ROM+RAM", mapper: "none" },
    0x09: { name: "ROM+RAM+BATTERY", mapper: "none" },
    0x0b: { name: "MMM01", mapper: "MMM01" },
    0x0c: { name: "MMM01+RAM", mapper: "MMM01" },
    0x0d: { name: "MMM01+RAM+BATTERY", mapper: "MMM01" },
    0x0f: { name: "MBC3+TIMER+BATTERY", mapper: "MBC3" },
    0x10: { name: "MBC3+TIMER+RAM+BATTERY", mapper: "MBC3" },
    0x11: { name: "MBC3", mapper: "MBC3" },
    0x12: { name: "MBC3+RAM", mapper: "MBC3" },
    0x13: { name: "MBC3+RAM+BATTERY", mapper: "MBC3" },
    0x19: { name: "MBC5", mapper: "MBC5" },
    0x1a: { name: "MBC5+RAM", mapper: "MBC5" },
    0x1b: { name: "MBC5+RAM+BATTERY", mapper: "MBC5" },
    0x1c: { name: "MBC5+RUMBLE", mapper: "MBC5" },
    0x1d: { name: "MBC5+RUMBLE+RAM", mapper: "MBC5" },
    0x1e: { name: "MBC5+RUMBLE+RAM+BATTERY", mapper: "MBC5" },
    0x20: { name: "MBC6", mapper: "MBC6" },
    0x22: { name: "MBC7+SENSOR+RUMBLE+RAM+BATTERY", mapper: "MBC7" },
    0xfc: { name: "POCKET CAMERA", mapper: "camera" },
    0xfd: { name: "BANDAI TAMA5", mapper: "TAMA5" },
    0xfe: { name: "HuC3", mapper: "HuC3" },
    0xff: { name: "HuC1+RAM+BATTERY", mapper: "HuC1" },
};
const RAM_SIZES = {
    0x00: 0,
    0x01: 2 * 1024,
    0x02: 8 * 1024,
    0x03: 32 * 1024,
    0x04: 128 * 1024,
    0x05: 64 * 1024,
};
function isInside(root, candidate) {
    return isPathWithinRoot(root, candidate);
}
function samePlatformPath(first, second) {
    if (process.platform !== "win32") {
        return first === second;
    }
    return isPathWithinRoot(first, second, "win32") && isPathWithinRoot(second, first, "win32");
}
function configuredEnvironmentValue(name) {
    return readPlatformEnvironmentVariable(process.env, name);
}
async function resolveExistingWithinRoot(root, input) {
    assertSafePlatformPath(input);
    const absolute = path.resolve(root, input);
    if (!isInside(root, absolute)) {
        throw new Error(`Path escapes the project root: ${input}`);
    }
    const canonical = await realpath(absolute);
    if (!isInside(root, canonical)) {
        throw new Error(`Path resolves outside the project root: ${input}`);
    }
    return canonical;
}
export async function resolveProjectBuildInput(projectRoot, projectPath) {
    const project = await resolveExistingWithinRoot(await realpath(path.resolve(projectRoot)), projectPath);
    if (path.extname(project).toLowerCase() !== ".gbsproj") {
        throw new Error("Input must be a .gbsproj file.");
    }
    return project;
}
async function resolveOutputWithinRoot(root, input) {
    assertSafePlatformPath(input);
    const absolute = path.resolve(root, input);
    if (!isInside(root, absolute)) {
        throw new Error(`Output path escapes the project root: ${input}`);
    }
    let ancestor = absolute;
    while (true) {
        try {
            const canonicalAncestor = await realpath(ancestor);
            if (!isInside(root, canonicalAncestor)) {
                throw new Error(`Output path resolves outside the project root: ${input}`);
            }
            return absolute;
        }
        catch (error) {
            if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT") {
                throw error;
            }
            const parent = path.dirname(ancestor);
            if (parent === ancestor || !isInside(root, parent)) {
                throw new Error(`Output path escapes the project root: ${input}`);
            }
            ancestor = parent;
        }
    }
}
async function exists(candidate) {
    try {
        await access(candidate);
        return true;
    }
    catch {
        return false;
    }
}
function isolatedCompilerEnvironment(temporaryDirectory) {
    return sanitizeSubprocessEnvironment(process.env, process.platform, temporaryDirectory, {
        preserveCertificateAuthority: true,
    });
}
/** Passive metadata readiness unless the caller explicitly names health probes. */
export async function doctor(projectRoot, options = {}) {
    options.signal?.throwIfAborted();
    const root = await realpath(path.resolve(projectRoot));
    const report = Object.assign(await detectDependencies(options), { projectRoot: root });
    options.signal?.throwIfAborted();
    return options.probes?.length ? probeDependencies(report, { probes: options.probes, signal: options.signal }) : report;
}
function romSizeFromCode(code) {
    if (code >= 0x00 && code <= 0x08) {
        return 32 * 1024 * 2 ** code;
    }
    return { 0x52: 72 * 16 * 1024, 0x53: 80 * 16 * 1024, 0x54: 96 * 16 * 1024 }[code] ?? null;
}
/** Read and validate the bytes the Game Boy boot ROM actually checks. */
export async function inspectRom(romPath, projectRoot) {
    let absolute;
    if (projectRoot) {
        const root = await realpath(path.resolve(projectRoot));
        absolute = await resolveExistingWithinRoot(root, romPath);
    }
    else {
        absolute = await realpath(path.resolve(romPath));
    }
    const before = await fs.lstat(absolute);
    if (!before.isFile() || before.size > MAX_ROM_BYTES) {
        throw new Error("ROM must be a regular file no larger than 8 MiB");
    }
    const sameFile = (a, b) => ["dev", "ino", "size", "mode", "nlink", "uid", "gid", "mtimeMs", "ctimeMs"].every((key) => a[key] === b[key]);
    const handle = await fs.open(absolute, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
    let bytes;
    try {
        const opened = await handle.stat();
        if (!opened.isFile() || !sameFile(before, opened))
            throw new Error("ROM changed while opening");
        bytes = Buffer.alloc(before.size);
        let offset = 0;
        while (offset < bytes.length) {
            const read = await handle.read(bytes, offset, bytes.length - offset, offset);
            if (read.bytesRead === 0)
                throw new Error("ROM changed while reading");
            offset += read.bytesRead;
        }
        const extra = await handle.read(Buffer.alloc(1), 0, 1, offset);
        if (extra.bytesRead !== 0 || !sameFile(opened, await handle.stat())
            || !sameFile(opened, await fs.lstat(absolute)) || await realpath(absolute) !== absolute) {
            throw new Error("ROM changed while reading");
        }
    }
    finally {
        await handle.close();
    }
    if (bytes.length < HEADER_MINIMUM_BYTES) {
        throw new Error(`ROM is too small to contain a complete Game Boy cartridge header: ${bytes.length} bytes`);
    }
    const colorFlag = bytes[0x143];
    const colorMode = colorFlag === 0xc0 ? "gbc-only" : colorFlag === 0x80 ? "gbc" : "dmg";
    const titleEnd = colorFlag === 0xc0 || colorFlag === 0x80 ? 0x143 : 0x144;
    const title = bytes.subarray(0x134, titleEnd).toString("ascii").replace(/\0.*$/, "");
    const cartridgeType = bytes[0x147];
    const cartridge = CARTRIDGE_TYPES[cartridgeType] ?? {
        name: `UNKNOWN (0x${cartridgeType.toString(16).padStart(2, "0")})`,
        mapper: "unknown",
    };
    const romSizeCode = bytes[0x148];
    const ramSizeCode = bytes[0x149];
    const headerChecksum = bytes[0x14d];
    let computedHeaderChecksum = 0;
    for (let index = 0x134; index <= 0x14c; index += 1) {
        computedHeaderChecksum = (computedHeaderChecksum - bytes[index] - 1) & 0xff;
    }
    const nintendoLogoValid = bytes.subarray(0x104, 0x134).equals(NINTENDO_LOGO);
    const headerChecksumValid = headerChecksum === computedHeaderChecksum;
    return {
        path: absolute,
        sizeBytes: bytes.length,
        sha256: createHash("sha256").update(bytes).digest("hex"),
        title,
        colorMode,
        colorFlag,
        cartridgeType,
        cartridgeTypeName: cartridge.name,
        mapper: cartridge.mapper,
        romSizeCode,
        declaredRomSizeBytes: romSizeFromCode(romSizeCode),
        ramSizeCode,
        declaredRamSizeBytes: RAM_SIZES[ramSizeCode] ?? null,
        nintendoLogoValid,
        headerChecksum,
        computedHeaderChecksum,
        headerChecksumValid,
        valid: nintendoLogoValid && headerChecksumValid,
    };
}
function readCommandFailure(error) {
    if (!(error instanceof Error)) {
        return { exitCode: null, stdout: "", stderr: String(error), compilerStderr: "" };
    }
    const processError = error;
    const compilerStderr = withoutNodeDeprecationNotice(processError.stderr?.toString() ?? "");
    return {
        exitCode: typeof processError.code === "number" ? processError.code : null,
        stdout: processError.stdout?.toString() ?? "",
        stderr: compilerStderr || processError.message,
        compilerStderr,
    };
}
// GB Studio's warning for an event it has no definition for (compileEntityEvents.ts): it leaves the event out and still
// writes the ROM.
const GB_STUDIO_UNKNOWN_EVENT = /^No compiler for command "([^"]*)"\. Are you missing a plugin\? /;
function droppedGbStudioEvent(builder, stdout, stderr) {
    return builder === "gb-studio-cli" && `${stdout}\n${stderr}`.split(/\r?\n/).some((line) => GB_STUDIO_UNKNOWN_EVENT.test(line.trim()));
}
// What GB Studio's build worker prints when a build stops (buildWorker.ts): this, then the error and its stack.
const GB_STUDIO_BUILD_FAILURE = /^buildTask process terminated with error: /gm;
// GB Studio's error for an event whose compile threw (compileEntityEvents.ts): the cause, then where as JSON. Every
// event around it wraps it again with the wrapped error as the cause, and each one is also printed on its own.
const GB_STUDIO_EVENT_COMPILE_FAILURE = /^(?:Error: )?Compiling "([^"]+)" failed with error "([\s\S]*)"\. (\{(?:"\w+":"(?:[^"\\]|\\.)*",?)*\})$/;
const GB_STUDIO_EVENT_COMPILE_LINE = /\bCompiling "[^"]+" failed with error "/;
// The innermost event a failed GB Studio build stopped on, read from the worker's last failure record as a whole (a
// cause can span lines), or undefined when something else stopped it.
function failedGbStudioEventCompile(stderr) {
    const text = stderr.replace(/\r\n/g, "\n");
    const record = [...text.matchAll(GB_STUDIO_BUILD_FAILURE)].at(-1);
    if (!record)
        return undefined;
    let failure;
    let match = GB_STUDIO_EVENT_COMPILE_FAILURE.exec(text.slice(record.index + record[0].length).split(/\n\s+at /)[0].trimEnd());
    for (; match; match = GB_STUDIO_EVENT_COMPILE_FAILURE.exec(match[2]))
        failure = { event: match[1], cause: match[2], location: match[3] };
    return failure;
}
const GB_STUDIO_DEPRECATION = /^"([^"]+)" is deprecated and will be removed in a future release\.(?: Use "([^"]+)" instead\.)?.*\(([A-Z][A-Z0-9_]*)\)$/;
function withoutNodeDeprecationNotice(text) {
    const kept = [];
    let notice = false;
    for (const line of text.split("\n")) {
        if (/^(?:\(node:\d+\)\s+)?\[DEP0190\]\s+DeprecationWarning:/.test(line.trim()))
            notice = true;
        else if (!(notice && /^\(Use `node --trace-deprecation \.\.\.` to show where the warning was created\)$/.test(line.trim()))) {
            notice = false;
            kept.push(line);
        }
    }
    return kept.join("\n");
}
function successfulBuildOutput(stdout, stderr, logged) {
    const lines = stdout.replace(/\r?\n$/, "").split(/\r?\n/);
    const omitted = logged ? lines.length - SUCCESS_STDOUT_TAIL_LINES : 0;
    return {
        stdout: omitted > 0 ? `${lines.slice(omitted).join("\n")}\n` : stdout,
        ...(omitted > 0 ? { stdoutOmittedLines: omitted } : {}),
        stderr: stderr.split("\n").filter((line) => !GB_STUDIO_DEPRECATION.test(line.trim())).join("\n"),
    };
}
async function writeBuildLog(root, outputPath, { command, args, exitCode, stdout, stderr }) {
    const text = [`$ ${[command, ...args].join(" ")}`, `exit code: ${exitCode ?? "none"}`, "", "[stdout]", stdout, "[stderr]", stderr].join("\n");
    let logPath;
    let staged;
    try {
        const directory = await resolveOutputWithinRoot(root, BUILD_LOG_DIRECTORY);
        await mkdir(directory, { recursive: true });
        const metadata = await lstat(directory);
        if (metadata.isSymbolicLink() || !metadata.isDirectory() || !samePlatformPath(await realpath(directory), directory)) {
            throw new Error(`the log folder must be a real project-local directory: ${directory}`);
        }
        logPath = path.join(directory, `${path.basename(outputPath)}.log`);
        staged = `${logPath}.${process.pid}-${Date.now()}.tmp`;
        await writeFile(staged, text, { flag: "wx", mode: 0o644 });
        await rename(staged, logPath);
        return { logPath };
    }
    catch (error) {
        if (staged)
            await rm(staged, { force: true }).catch(() => { });
        return { logError: `The build log could not be written${logPath ? ` to ${logPath}` : ""}: ${error instanceof Error ? error.message : String(error)}` };
    }
}
/** Add a small actionable index without replacing the original process log. */
export function summarizeBuildDiagnostics(input) {
    const maximum = 16;
    const errors = [];
    const others = [];
    const seen = new Set();
    let diagnosticsTruncated = false;
    const add = (diagnostic) => {
        const message = diagnostic.message.trim().slice(0, 500);
        const key = `${diagnostic.code}\0${message}`;
        if (seen.has(key))
            return;
        seen.add(key);
        const kept = diagnostic.severity === "error" ? errors : others;
        if (kept.length === maximum) {
            diagnosticsTruncated = true;
            return;
        }
        kept.push({ ...diagnostic, message });
    };
    if (input.cancelled)
        add({ severity: "error", code: "BUILD_CANCELLED", message: "The build was cancelled.", suggestedAction: "The cancelled attempt cannot authenticate new debug artifacts. Rerun the build when ready." });
    else if (input.timedOut)
        add({ severity: "error", code: "BUILD_TIMEOUT", message: "The compiler exceeded the requested time limit.", suggestedAction: "Inspect the retained compiler output, fix any reported source error, then retry with a bounded larger timeoutMs if needed." });
    const authoredDeprecations = new Set((input.authoring ?? []).filter((diagnostic) => diagnostic.code === "DEPRECATED_EVENT").map((diagnostic) => diagnostic.event));
    if (input.outputLimit)
        add({ severity: "error", code: "BUILD_OUTPUT_LIMIT", message: "Compiler output exceeded its 8 MiB per-stream limit and was truncated.", suggestedAction: "Inspect the retained output prefix and fix a repeatedly emitted compiler error or overly verbose project plugin before retrying." });
    // A failed GB Studio build that stopped on an event's compile: that event once, with its replacement when GB Studio
    // deprecates it (which then stands for the event's deprecation warning).
    const compileFailure = input.builder === "gb-studio-cli" && !input.success ? failedGbStudioEventCompile(input.stderr) : undefined;
    const failureGuidance = compileFailure && deprecatedEventGuidance(compileFailure.event);
    const guidedEvent = failureGuidance ? compileFailure.event : undefined;
    const failureLines = new Set(compileFailure ? compileFailure.cause.split("\n").map((line) => line.trim()) : []);
    if (compileFailure) {
        const { event, cause, location } = compileFailure;
        add({
            severity: "error",
            code: "SCRIPT_EVENT_COMPILE_FAILED",
            message: `Compiling "${event}" failed with error "${cause}". ${location}`,
            event,
            suggestedAction: unavailableEventMessage(event, "The project") ?? `GB Studio stopped on ${event}: ${cause.replace(/\.$/, "")}. Fix that event in the script the message names (event_describe gives its args), then rebuild.${failureGuidance ? ` ${event} is deprecated: ${failureGuidance}` : ""}`,
        });
    }
    for (const raw of `${input.stderr}\n${input.stdout}`.split(/\r?\n/)) {
        const line = raw.trim();
        if (!line)
            continue;
        const deprecated = GB_STUDIO_DEPRECATION.exec(line);
        if (deprecated) {
            const [, helper, replacement, event] = deprecated;
            if (authoredDeprecations.has(event) || event === guidedEvent)
                continue;
            add({
                severity: "warning",
                code: "DEPRECATED_EVENT",
                message: line,
                event,
                suggestedAction: `The ROM is fine. GB Studio compiles ${event} with ${helper}, which a future release removes${replacement ? ` for ${replacement}` : ""}: replace this project's ${event} events with a current event.`,
            });
            continue;
        }
        const unknownEvent = input.builder === "gb-studio-cli" ? GB_STUDIO_UNKNOWN_EVENT.exec(line) : null;
        if (unknownEvent) {
            add({
                severity: "error",
                code: "UNKNOWN_EVENT_COMMAND",
                message: line,
                event: unknownEvent[1],
                suggestedAction: `${unknownEventMessage(unknownEvent[1], "The project")} The ROM was built without it: replace it with a real event and rebuild.`,
            });
            continue;
        }
        // The compile failure's own lines: each wrapper, and the cause as GB Studio printed it.
        if (compileFailure && (GB_STUDIO_EVENT_COMPILE_LINE.test(line) || failureLines.has(line)))
            continue;
        let code;
        let suggestedAction = "";
        if (/compiler process cleanup could not be confirmed/i.test(line)) {
            code = "BUILD_CLEANUP_UNCONFIRMED";
            suggestedAction = "Inspect the reported compiler process before starting another build. No successful build or debug receipt is claimed.";
        }
        else if (/source changed.*build|source.*identity.*changed|source-debug build provenance/i.test(line)) {
            code = "SOURCE_CHANGED_DURING_BUILD";
            suggestedAction = "Finish or pause external edits, then rebuild with captureDebugArtifacts:true. Do not use these sidecars for source-aware debugging.";
        }
        else if (/same-build|debug artifact|linker \.noi|globals\.i/i.test(line) && /unavailable|missing|requires|must|mismatch|does not match|invalid|malformed|outside|refuses/i.test(line)) {
            code = "DEBUG_ARTIFACTS_UNAVAILABLE";
            suggestedAction = "Run the supported official game compiler CLI with captureDebugArtifacts:true again. ROM-only play does not require source-debug artifacts.";
        }
        else if (/(?:missing|cannot find|could not find|not found|ENOENT|no such file).*(?:asset|background|sprite|font|music|sound|\.png|\.gbsres)|(?:asset|background|sprite|font|music|sound).*(?:missing|not found)/i.test(line)) {
            code = "MISSING_AUTHORED_RESOURCE";
            suggestedAction = "Use project_inventory or world_dependencies to find the referenced resource, then restore its source file or fix the authored reference.";
        }
        else if (/too many.*(?:tile|sprite)|(?:tile|sprite).*(?:budget|limit|maximum).*exceed|exceed.*(?:tile|sprite).*(?:budget|limit|maximum)/i.test(line)) {
            code = "GRAPHICS_BUDGET_EXCEEDED";
            suggestedAction = "Run graphics_analyze_scene for the affected scene and reduce the reported background, sprite, palette, or OAM usage.";
        }
        else if (/too many.*variables|(?:VM_HEAP_SIZE|MAX_GLOBAL_VARS).*(?:exceed|error|too|unable)|not enough.*(?:variable|heap)/i.test(line)) {
            code = "VARIABLE_BUDGET_EXCEEDED";
            suggestedAction = "Inspect authored variable references and shared scripts; reuse or remove unnecessary variables before rebuilding.";
        }
        else if (/(?:ROM|bank|area|region).*(?:overflow|does not fit|out of space)|(?:overflow|not enough space).*(?:ROM|bank|area)/i.test(line)) {
            code = "ROM_CAPACITY_EXCEEDED";
            suggestedAction = "Inspect the named linker bank or generated resource and reduce its data size, or choose a supported larger cartridge setting.";
        }
        else if (/error in scene\s+['"]/i.test(line)) {
            code = "SCENE_COMPILATION_FAILED";
            suggestedAction = "Find the exact scene symbol in project_inventory and inspect its actors, triggers, and authored event references with world_dependencies.";
        }
        else if (/\b(?:fatal error|error(?:\s+\d+)?\s*[:#]|undefined symbol|unresolved symbol|syntax error)(?:\s|$)/i.test(line)) {
            code = "COMPILER_ERROR";
            suggestedAction = "Inspect the named source or generated symbol and the surrounding retained compiler output; correct the authored event, asset, or project plugin, then rebuild.";
        }
        if (!code)
            continue;
        const location = /(?:^|[\s'"(])((?:project|assets|plugins)[/\\][^\r\n'"()]*?\.(?:gbsres|png|c|h|s|js|ts))(?:[:(](\d+))?/i.exec(line);
        const resourcePath = location?.[1]?.replaceAll("\\", "/");
        const lineNumber = location?.[2] ? Number(location[2]) : undefined;
        add({ severity: input.success ? "warning" : "error", code, message: line, suggestedAction,
            ...(resourcePath && resourcePath.length <= 1024 ? { resourcePath,
                ...(lineNumber !== undefined && Number.isSafeInteger(lineNumber) && lineNumber > 0 ? { line: lineNumber } : {}) } : {}) });
    }
    for (const diagnostic of input.authoring ?? []) {
        if (!(diagnostic.code === "DEPRECATED_EVENT" && diagnostic.event === guidedEvent))
            add(diagnostic);
    }
    if (!input.success && errors.length === 0) {
        add({ severity: "error", code: "BUILD_FAILED", message: input.exitCode === 0 ? "The compiler did not produce a valid requested ROM or required debug artifacts." : `The compiler failed${input.exitCode === null ? "" : ` with exit code ${input.exitCode}`}.`, suggestedAction: "Read the retained stdout/stderr, run toolchain_doctor, and fix the first reported error before rebuilding." });
    }
    const diagnostics = [...errors, ...others];
    return { diagnostics: diagnostics.slice(0, maximum), diagnosticsTruncated: diagnosticsTruncated || diagnostics.length > maximum };
}
function processRunning(child) {
    return child.pid !== undefined && child.exitCode === null && child.signalCode === null;
}
async function waitForProcessExit(child, timeoutMs) {
    if (!processRunning(child))
        return true;
    return new Promise((resolve) => {
        const finish = (exited) => {
            clearTimeout(timer);
            child.off("exit", exitedListener);
            resolve(exited);
        };
        const exitedListener = () => finish(true);
        const timer = setTimeout(() => finish(!processRunning(child)), timeoutMs);
        child.once("exit", exitedListener);
        if (!processRunning(child))
            finish(true);
    });
}
function processGroupExists(pid) {
    try {
        process.kill(-pid, 0);
        return true;
    }
    catch (error) {
        return !(error instanceof Error && "code" in error && error.code === "ESRCH");
    }
}
async function waitForProcessGroupExit(pid, timeoutMs) {
    const deadline = performance.now() + timeoutMs;
    while (processGroupExists(pid)) {
        if (performance.now() >= deadline)
            return false;
        await delay(25);
    }
    return true;
}
/** Terminate only the compiler process group/tree created for this invocation. */
async function terminateBuildCommand(child, environment) {
    const pid = child.pid;
    if (pid === undefined)
        return undefined;
    if (process.platform !== "win32") {
        try {
            process.kill(-pid, "SIGTERM");
        }
        catch (error) {
            if (error instanceof Error && "code" in error && error.code === "ESRCH")
                return undefined;
            child.kill("SIGTERM");
        }
        if (!await waitForProcessGroupExit(pid, 750)) {
            try {
                process.kill(-pid, "SIGKILL");
            }
            catch {
                // The group may have exited already; the wait below is what says whether it did.
            }
            if (!await waitForProcessGroupExit(pid, 1_000)) {
                return `Compiler process cleanup could not be confirmed for process group ${pid}.`;
            }
        }
        if (!await waitForProcessExit(child, 1_000))
            return `Compiler process cleanup could not be confirmed for process ${pid}.`;
        return undefined;
    }
    // Windows has no negative-PID process groups. Use the trusted OS executable,
    // before killing the parent, so taskkill can still enumerate its descendants.
    let treeTerminated = false;
    try {
        const systemRoot = readPlatformEnvironmentVariable(environment, "SystemRoot", "win32");
        if (!systemRoot)
            throw new Error("No trusted Windows SystemRoot is available");
        const canonicalRoot = await realpath(systemRoot);
        const taskkill = path.join(canonicalRoot, "System32", "taskkill.exe");
        const metadata = await lstat(taskkill);
        if (!metadata.isFile() || metadata.isSymbolicLink() || !samePlatformPath(taskkill, await realpath(taskkill))) {
            throw new Error("The Windows process-tree terminator is not a real system executable");
        }
        await execFileAsync(taskkill, ["/PID", String(pid), "/T", "/F"], {
            cwd: canonicalRoot, env: environment, windowsHide: true, encoding: "utf8", timeout: 5_000, maxBuffer: 64 * 1024,
        });
        treeTerminated = true;
    }
    catch {
        if (processRunning(child))
            child.kill("SIGKILL");
    }
    const exited = await waitForProcessExit(child, 1_000);
    return treeTerminated && exited ? undefined : `Compiler process cleanup could not be confirmed for Windows process tree ${pid}.`;
}
export async function runBuildCommand(command, args, options) {
    if (options.signal?.aborted) {
        throw Object.assign(new Error("The build was cancelled before the compiler started."), {
            name: "AbortError", code: "ABORT_ERR", stdout: "", stderr: "", buildCancelled: true,
        });
    }
    if (options.evidence)
        options.evidence.startedAt = new Date().toISOString();
    // With `started`, the compiler waits on its standard input until `started` has seen its process id and returned.
    const gated = options.started !== undefined && process.platform !== "win32";
    const child = gated
        ? spawn("/bin/sh", ["-c", 'read -r go && [ "$go" = go ] && exec "$0" "$@"', command, ...args], {
            cwd: options.cwd, env: options.environment, detached: true, stdio: ["pipe", "pipe", "pipe"],
        })
        : spawn(command, args, {
            cwd: options.cwd, env: options.environment, windowsHide: true,
            detached: process.platform !== "win32", stdio: ["ignore", "pipe", "pipe"],
        });
    const evidence = options.evidence;
    if (evidence) {
        if (child.pid !== undefined)
            evidence.pid = child.pid;
        child.once("spawn", () => { evidence.spawnedAt = new Date().toISOString(); });
        child.once("exit", (code, signal) => { evidence.exit = { at: new Date().toISOString(), code, signal }; });
    }
    let reason;
    let stopping;
    const maximum = 8 * 1024 * 1024;
    const stdout = [];
    const stderr = [];
    let stdoutBytes = 0;
    let stderrBytes = 0;
    let outputLimitReached = false;
    let processError;
    let executionSettled = false;
    let closed = false;
    let forcedSettlement = false;
    let resolveClosed;
    const childClosed = new Promise((resolve) => { resolveClosed = resolve; });
    let resolveExecution;
    let rejectExecution;
    const execution = new Promise((resolve, reject) => {
        resolveExecution = resolve;
        rejectExecution = reject;
    });
    const finishExecution = (exitCode, signal, warning) => {
        if (executionSettled)
            return;
        executionSettled = true;
        const output = { stdout: Buffer.concat(stdout).toString("utf8"), stderr: Buffer.concat(stderr).toString("utf8") };
        if (!warning && !processError && exitCode === 0 && signal === null) {
            resolveExecution(output);
            return;
        }
        const failure = processError ?? Object.assign(new Error(warning ? "The compiler did not complete its bounded shutdown." : `The compiler ${signal ? `was terminated by ${signal}` : `exited with status ${exitCode ?? "unknown"}`}.`), { code: exitCode ?? undefined });
        Object.assign(failure, output, warning ? { buildCleanupWarning: warning } : {});
        rejectExecution(failure);
    };
    const terminate = () => terminateBuildCommand(child, options.environment).catch((error) => `Compiler process cleanup could not be confirmed for process ${child.pid ?? "unknown"}: ${error instanceof Error ? error.message.slice(0, 200) : "termination failed"}.`);
    const stop = (requested) => {
        reason ??= requested;
        stopping ??= (async () => {
            let warning = await terminate();
            // Descendants can inherit these pipes after escaping the process group.
            // Never let a missing ChildProcess 'close' event defeat the time limit.
            if (!closed)
                await Promise.race([childClosed, delay(100)]);
            if (!closed && !executionSettled) {
                warning ??= `Compiler process cleanup could not be confirmed for process ${child.pid ?? "unknown"}; inherited output pipes remained open.`;
                forcedSettlement = true;
                finishExecution(child.exitCode, child.signalCode, warning);
                child.stdout.destroy();
                child.stderr.destroy();
                child.unref();
            }
            return warning;
        })();
    };
    const collect = (stream, chunk) => {
        if (executionSettled)
            return;
        const used = stream === "stdout" ? stdoutBytes : stderrBytes;
        const remaining = Math.max(0, maximum - used);
        if (remaining > 0)
            (stream === "stdout" ? stdout : stderr).push(chunk.subarray(0, remaining));
        if (stream === "stdout")
            stdoutBytes += Math.min(chunk.length, remaining);
        else
            stderrBytes += Math.min(chunk.length, remaining);
        if (chunk.length > remaining && !outputLimitReached) {
            outputLimitReached = true;
            processError ??= Object.assign(new Error(`Compiler ${stream} exceeded its bounded output limit.`), { code: "ERR_CHILD_PROCESS_STDIO_MAXBUFFER" });
            stop("output-limit");
        }
    };
    const onStdout = (chunk) => collect("stdout", chunk);
    const onStderr = (chunk) => collect("stderr", chunk);
    const onError = (error) => {
        processError ??= error;
        if (evidence)
            evidence.error = { name: error.name, message: error.message, ...(error.code === undefined ? {} : { code: error.code }) };
    };
    const onClose = (exitCode, signal) => {
        closed = true;
        if (evidence)
            evidence.close = { at: new Date().toISOString(), code: exitCode, signal };
        resolveClosed();
        finishExecution(exitCode, signal);
    };
    child.stdout.on("data", onStdout);
    child.stderr.on("data", onStderr);
    child.on("error", onError);
    child.once("close", onClose);
    if (gated) {
        child.stdin.on("error", () => { });
        let go = false;
        try {
            if (child.pid !== undefined) {
                options.started(child.pid);
                go = true;
            }
        }
        catch (error) {
            processError ??= error instanceof Error ? error : new Error(String(error));
        }
        child.stdin.end(go ? "go\n" : "");
    }
    const cancel = () => stop("cancelled");
    const timer = setTimeout(() => stop("timeout"), options.timeoutMs);
    timer.unref();
    options.signal?.addEventListener("abort", cancel, { once: true });
    if (options.signal?.aborted)
        cancel();
    try {
        const result = await execution;
        if (reason === undefined)
            return result;
        throw Object.assign(new Error(reason === "cancelled" ? "The build was cancelled." : "The compiler exceeded the requested time limit."), result);
    }
    catch (error) {
        const failure = error instanceof Error ? error : new Error(String(error));
        // Also clean up descendants after an unexpected CLI exit or output overflow.
        const warning = await (stopping ?? terminate());
        if (reason === "cancelled")
            failure.buildCancelled = true;
        if (reason === "timeout")
            failure.buildTimedOut = true;
        if (outputLimitReached)
            failure.buildOutputLimit = true;
        if (warning)
            failure.buildCleanupWarning = warning;
        if (evidence && warning)
            evidence.cleanupWarning = warning;
        throw failure;
    }
    finally {
        if (evidence) {
            evidence.stdoutBytes = stdoutBytes;
            evidence.stderrBytes = stderrBytes;
            evidence.outputTruncated = outputLimitReached;
            if (reason)
                evidence.stopReason = reason;
        }
        clearTimeout(timer);
        options.signal?.removeEventListener("abort", cancel);
        child.stdout.off("data", onStdout);
        child.stderr.off("data", onStderr);
        if (forcedSettlement) {
            child.off("close", onClose);
            child.off("error", onError);
            // The unref'd process may still emit an error after cleanup was reported.
            child.on("error", () => { });
        }
    }
}
async function trustedTemporaryParent(candidate, projectRoot) {
    try {
        assertSafePlatformPath(candidate);
        const absolute = path.resolve(candidate);
        const requested = await lstat(absolute);
        // macOS intentionally links /tmp to /private/tmp; other redirected roots
        // can place compiler intermediates in attacker-controlled locations.
        if (requested.isSymbolicLink() && (process.platform === "win32" || absolute !== path.resolve("/tmp")))
            return null;
        const canonical = await realpath(absolute);
        if (isInside(projectRoot, canonical))
            return null;
        const metadata = await lstat(canonical);
        if (metadata.isSymbolicLink() || !metadata.isDirectory())
            return null;
        if (process.platform === "win32") {
            return await verifyWindowsPrivatePath(canonical, { purpose: "temporary", platform: "win32" })
                ? canonical
                : null;
        }
        const currentUid = typeof process.getuid === "function" ? process.getuid() : undefined;
        const privateOwner = currentUid !== undefined && metadata.uid === currentUid && (metadata.mode & 0o022) === 0;
        const stickySystem = (metadata.mode & 0o1000) !== 0 &&
            (metadata.uid === 0 || (currentUid !== undefined && metadata.uid === currentUid));
        return privateOwner || stickySystem ? canonical : null;
    }
    catch {
        return null;
    }
}
async function selectTrustedTemporaryParent(projectRoot) {
    const considered = new Set();
    const localApplicationData = process.platform === "win32" ? configuredEnvironmentValue("LOCALAPPDATA") : undefined;
    const candidates = process.platform === "win32"
        ? [...(localApplicationData ? [path.join(localApplicationData, "Temp")] : []), os.tmpdir()]
        : [os.tmpdir(), "/tmp"];
    for (const candidate of candidates) {
        const absolute = path.resolve(candidate);
        const deduplicated = process.platform === "win32" ? absolute.toLowerCase() : absolute;
        if (considered.has(deduplicated))
            continue;
        considered.add(deduplicated);
        const trusted = await trustedTemporaryParent(absolute, projectRoot);
        if (trusted !== null)
            return trusted;
    }
    throw new Error("game compiler could not find a trusted temporary directory outside the selected project.");
}
async function createIsolatedBuildDirectory(projectRoot) {
    // GBDK's linker silently fails with the long absolute paths common in nested projects.
    // A short, trusted OS parent preserves real compilation while mkdtemp isolates runs.
    const temporaryParent = await selectTrustedTemporaryParent(projectRoot);
    const temporaryDirectory = await mkdtemp(path.join(temporaryParent, "gbs-"));
    try {
        const existing = await lstat(temporaryDirectory);
        if (existing.isSymbolicLink() || !existing.isDirectory() ||
            !samePlatformPath(await realpath(temporaryDirectory), temporaryDirectory) ||
            !samePlatformPath(path.dirname(temporaryDirectory), temporaryParent) || isInside(projectRoot, temporaryDirectory)) {
            throw new Error(`game-build temporary build directory is not a secure owned system directory: ${temporaryDirectory}`);
        }
        return temporaryDirectory;
    }
    catch (error) {
        await rm(temporaryDirectory, { recursive: true, force: true }).catch(() => { });
        throw error;
    }
}
async function removeIsolatedBuildDirectory(directory, projectRoot) {
    const expectedParent = path.dirname(directory);
    const trustedParent = await trustedTemporaryParent(expectedParent, projectRoot);
    if (trustedParent === null || !samePlatformPath(trustedParent, expectedParent) ||
        !/^gbs-[A-Za-z0-9]{6}$/.test(path.basename(directory))) {
        throw new Error(`Refusing to remove an unexpected game-build temporary directory: ${directory}`);
    }
    const existing = await lstat(directory);
    if (existing.isSymbolicLink() || !existing.isDirectory() || !samePlatformPath(await realpath(directory), directory)) {
        throw new Error(`Refusing to remove a relocated game-build temporary directory: ${directory}`);
    }
    await rm(directory, { recursive: true, force: true });
}
// A game's GB Studio builds share one compiler folder, so GB Studio's object cache (`_gbscache`, whose keys include the
// folder's path) lasts from one build to the next. Everything else in it is removed before and after each build.
// A build holds the folder through claim files: one for the engine and one for the compiler's process group, which
// can outlive the engine and starts only once its claim is written. Another build meanwhile gets a fresh folder.
const SHARED_BUILD_CACHE = "_gbscache";
const SHARED_BUILD_TOOLCHAIN = ".toolchain";
const SHARED_BUILD_UNFINISHED = ".unfinished";
const SHARED_BUILD_CLAIM = /^\.claim-(\d+)-[0-9a-f-]{36}$/;
function sharedBuildKeeps(entry) {
    return entry === SHARED_BUILD_CACHE || entry === SHARED_BUILD_TOOLCHAIN || SHARED_BUILD_CLAIM.test(entry);
}
function signalReaches(target) {
    try {
        process.kill(target, 0);
        return true;
    }
    catch (error) {
        return !isSystemError(error, "ESRCH");
    }
}
// A claim's process, or the process group it leads: the compiler's group outlives its first process. A process that
// took over a dead claim's id keeps it alive too, which only means fresh folders until it exits.
function claimIsAlive(pid) {
    return pid > 0 && (signalReaches(pid) || signalReaches(-pid));
}
async function clearSharedBuildDirectory(directory) {
    for (const entry of await readdir(directory)) {
        if (!sharedBuildKeeps(entry))
            await rm(path.join(directory, entry), { recursive: true, force: true });
    }
}
// GB Studio's cache keys follow only `include "..."` lines into the build's include folder, so a game that brings
// compiler input of its own could leave a stale engine object: its own engine code (`assets/engine`) or any plugin
// (an engine overlay, or an event that writes a header an engine file reads). Such a game builds in a fresh folder.
// A plugin is a folder in `plugins`; GB Studio's own `plugins/README.md` is not one.
async function gameBringsCompilerInput(projectDirectory) {
    try {
        await lstat(path.join(projectDirectory, "assets", "engine"));
        return true;
    }
    catch (error) {
        if (!isSystemError(error, "ENOENT"))
            throw error;
    }
    try {
        return (await readdir(path.join(projectDirectory, "plugins"), { withFileTypes: true })).some((entry) => !entry.isFile());
    }
    catch (error) {
        if (isSystemError(error, "ENOENT"))
            return false;
        throw error;
    }
}
// The compiler, by content: the CLI, its build worker, GB Studio's engine and this computer's GBDK. A different one
// drops the cache. Undefined when GB Studio is not laid out as expected or holds a link (its target could change).
async function sharedBuildToolchain(gbStudioCli) {
    const studio = path.resolve(path.dirname(gbStudioCli), "..", "..");
    const parts = [gbStudioCli, path.join(path.dirname(gbStudioCli), "buildWorker.js"), path.join(studio, "appData", "engine"), path.join(studio, "buildTools", `${process.platform}-${process.arch}`)];
    const hash = createHash("sha256");
    const add = async (candidate) => {
        const metadata = await lstat(candidate);
        hash.update(`${candidate}\0`);
        if (metadata.isSymbolicLink())
            return false;
        if (metadata.isDirectory()) {
            const entries = (await readdir(candidate)).sort((left, right) => (left < right ? -1 : left > right ? 1 : 0));
            for (const entry of entries) {
                if (!(await add(path.join(candidate, entry))))
                    return false;
            }
        }
        else if (metadata.isFile()) {
            hash.update(await readFile(candidate)).update("\0");
        }
        return true;
    };
    try {
        for (const part of parts) {
            if ((await realpath(part)) !== part || !(await add(part)))
                return undefined;
        }
    }
    catch (error) {
        if (isSystemError(error, "ENOENT"))
            return undefined;
        throw error;
    }
    return hash.digest("hex");
}
async function sharedCacheState(directory, state = new Map()) {
    let entries;
    try {
        entries = await readdir(directory, { withFileTypes: true });
    }
    catch (error) {
        if (isSystemError(error, "ENOENT"))
            return state;
        throw error;
    }
    for (const entry of entries) {
        const candidate = path.join(directory, entry.name);
        if (entry.isDirectory()) {
            await sharedCacheState(candidate, state);
        }
        else {
            const metadata = await lstat(candidate);
            state.set(candidate, `${metadata.ino}:${metadata.size}:${metadata.mtimeMs}:${metadata.ctimeMs}`);
        }
    }
    return state;
}
async function claimSharedBuildDirectory(projectRoot, projectFile, gbStudioCli) {
    if (process.platform === "win32" || typeof process.getuid !== "function" || (await gameBringsCompilerInput(path.dirname(projectFile))))
        return undefined;
    const toolchain = await sharedBuildToolchain(gbStudioCli);
    if (toolchain === undefined)
        return undefined;
    const uid = process.getuid();
    const temporaryParent = await selectTrustedTemporaryParent(projectRoot);
    const name = createHash("sha256").update(`${uid}\0${projectFile}`).digest("hex").slice(0, 6);
    const directory = path.join(temporaryParent, `gbs_${name}`);
    try {
        await mkdir(directory, { mode: 0o700 });
    }
    catch (error) {
        if (!isSystemError(error, "EEXIST"))
            throw error;
    }
    const existing = await lstat(directory);
    if (existing.isSymbolicLink() || !existing.isDirectory() || existing.uid !== uid || (existing.mode & 0o077) !== 0 ||
        !samePlatformPath(await realpath(directory), directory) || isInside(projectRoot, directory)) {
        return undefined;
    }
    const claim = path.join(directory, `.claim-${process.pid}-${randomUUID()}`);
    await writeFile(claim, "", { flag: "wx", mode: 0o600 });
    try {
        // Until a listing shows no other claim: one written after a listing belongs to a process alive at that listing.
        for (let others = true; others;) {
            others = false;
            for (const entry of await readdir(directory)) {
                const owner = SHARED_BUILD_CLAIM.exec(entry);
                const other = path.join(directory, entry);
                if (!owner || other === claim)
                    continue;
                others = true;
                if (claimIsAlive(Number(owner[1]))) {
                    await rm(claim, { force: true });
                    return undefined;
                }
                await rm(other, { force: true });
            }
        }
        const cache = path.join(directory, SHARED_BUILD_CACHE);
        // A build that never finished (its engine or compiler stopped first) may have left a cached object half written.
        const unfinished = await exists(path.join(directory, SHARED_BUILD_UNFINISHED));
        const recorded = await readFile(path.join(directory, SHARED_BUILD_TOOLCHAIN), "utf8").catch(() => "");
        if (unfinished || recorded !== toolchain)
            await rm(cache, { recursive: true, force: true });
        await clearSharedBuildDirectory(directory);
        await writeFile(path.join(directory, SHARED_BUILD_TOOLCHAIN), toolchain, { mode: 0o600 });
        await writeFile(path.join(directory, SHARED_BUILD_UNFINISHED), "", { mode: 0o600 });
        const engineSources = path.join(path.dirname(gbStudioCli), "..", "..", "appData", "engine", "gbvm", "src");
        return { directory, claim, projectDirectory: path.dirname(projectFile), engineSources, cacheBefore: await sharedCacheState(cache) };
    }
    catch (error) {
        await rm(claim, { force: true }).catch(() => { });
        throw error;
    }
}
// The compiler's own claim, written before it is let start; a failure here stops it from starting.
function claimSharedBuildForCompiler(shared, pid) {
    const claim = path.join(shared.directory, `.claim-${pid}-${randomUUID()}`);
    writeFileSync(claim, "", { flag: "wx", mode: 0o600 });
    shared.compilerClaim = { claim, pid };
}
// GB Studio's keys see a file's quoted includes and only the values it uses from data/game_globals.i, without their
// names: enough for its engine's own files, whose other includes are GBDK's, but not for the game's generated ones
// (scripts with swapped constant names, a raw `.include`, a plugin's output). So only the objects of GB Studio's own
// engine files (in its `appData/engine/gbvm/src`, outside `src/data`) are kept after each build; the rest compile
// on every build.
async function keepOnlyEngineObjects(shared) {
    const build = path.join(shared.directory, "_gbsbuild");
    const engineObjects = new Set();
    const collect = async (relative) => {
        let entries;
        try {
            entries = await readdir(path.join(build, "src", relative), { withFileTypes: true });
        }
        catch (error) {
            if (isSystemError(error, "ENOENT"))
                return;
            throw error;
        }
        for (const entry of entries) {
            const name = path.join(relative, entry.name);
            if (entry.isDirectory()) {
                if (name !== "data")
                    await collect(name);
            }
            else if (/\.[cs]$/.test(entry.name) && (await exists(path.join(shared.engineSources, name)))) {
                const object = await readFile(path.join(build, "obj", `${entry.name.slice(0, -2)}.o`)).catch(() => undefined);
                if (object)
                    engineObjects.add(object.toString("base64"));
            }
        }
    };
    await collect("");
    for (const file of (await sharedCacheState(path.join(shared.directory, SHARED_BUILD_CACHE))).keys()) {
        if (!engineObjects.has((await readFile(file)).toString("base64")))
            await rm(file, { force: true });
    }
}
// GB Studio sets these only when a project setting asks for one, and its keys include the whole environment: an
// inherited one would make builds with and without that setting look alike.
const GB_STUDIO_BUILD_MODES = ["COLOR", "SGB", "BATTERYLESS", "DEBUG"];
function sharedBuildEnvironment(environment) {
    const output = { ...environment };
    for (const name of GB_STUDIO_BUILD_MODES)
        delete output[name];
    return output;
}
async function releaseSharedBuildDirectory(shared, compilerSucceeded) {
    try {
        // A compiler group that is still running keeps the folder, and its unfinished mark drops the cache once it is gone.
        if (shared.compilerClaim && claimIsAlive(shared.compilerClaim.pid))
            return;
        // GB Studio writes its cache only after compiling, without replacing files atomically: what a compiler that
        // was stopped or failed changed there is forgotten.
        if (compilerSucceeded && (await gameBringsCompilerInput(shared.projectDirectory))) {
            // A plugin or engine code that arrived during the build: what it compiled is not kept.
            await rm(path.join(shared.directory, SHARED_BUILD_CACHE), { recursive: true, force: true });
        }
        else if (compilerSucceeded) {
            await keepOnlyEngineObjects(shared);
        }
        else {
            const cacheAfter = await sharedCacheState(path.join(shared.directory, SHARED_BUILD_CACHE));
            for (const [file, state] of cacheAfter) {
                if (shared.cacheBefore.get(file) !== state)
                    await rm(file, { force: true });
            }
        }
        await clearSharedBuildDirectory(shared.directory);
        if (shared.compilerClaim)
            await rm(shared.compilerClaim.claim, { force: true });
    }
    finally {
        await rm(shared.claim, { force: true });
    }
}
async function secureInternalBuildFile(directory, filename) {
    const candidate = path.join(directory, filename);
    let metadata;
    try {
        metadata = await lstat(candidate);
    }
    catch (error) {
        if (error instanceof Error && "code" in error && error.code === "ENOENT") {
            throw new Error(`Required same-build debug artifact is unavailable: ${filename}`);
        }
        throw error;
    }
    if (metadata.isSymbolicLink() || !metadata.isFile() || !samePlatformPath(await realpath(candidate), candidate)) {
        throw new Error(`Same-build debug artifact must be a real internal file: ${filename}`);
    }
    return readFile(candidate);
}
async function secureDebugArtifactDirectory(root, outputPath) {
    const directory = await resolveOutputWithinRoot(root, `${outputPath}.debug`);
    try {
        await mkdir(directory, { mode: 0o700 });
    }
    catch (error) {
        if (!(error instanceof Error) || !("code" in error) || error.code !== "EEXIST")
            throw error;
    }
    const metadata = await lstat(directory);
    if (metadata.isSymbolicLink() || !metadata.isDirectory() || !samePlatformPath(await realpath(directory), directory)) {
        throw new Error(`Debug artifact directory must be a real project-local directory: ${directory}`);
    }
    return directory;
}
async function assertSafeDebugArtifactDestination(destination) {
    try {
        const metadata = await lstat(destination);
        if (metadata.isSymbolicLink() || !metadata.isFile()) {
            throw new Error(`Debug artifact destination must not be a symbolic link or non-file: ${destination}`);
        }
    }
    catch (error) {
        if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT")
            throw error;
    }
}
async function sameBuildLiveStateLayout(buildRoot) {
    try {
        for (const [file, sha256] of Object.entries(LIVE_STATE_ENGINE_SHA256)) {
            if (file.startsWith("src/states/")) {
                try {
                    await lstat(path.join(buildRoot, file));
                }
                catch (error) {
                    if (error instanceof Error && "code" in error && error.code === "ENOENT")
                        continue;
                    throw error;
                }
            }
            if (createHash("sha256").update(await secureInternalBuildFile(buildRoot, file)).digest("hex") !== sha256)
                return undefined;
        }
        return LIVE_STATE_LAYOUT;
    }
    catch {
        return undefined;
    }
}
async function captureSameBuildDebugArtifacts(root, temporaryDirectory, outputPath, builtRom = outputPath) {
    const directory = path.join(temporaryDirectory, "_gbsbuild", "build", "rom");
    let metadata;
    try {
        metadata = await lstat(directory);
    }
    catch (error) {
        if (error instanceof Error && "code" in error && error.code === "ENOENT") {
            throw new Error("Official game compiler CLI did not preserve its same-build internal ROM directory");
        }
        throw error;
    }
    if (metadata.isSymbolicLink() || !metadata.isDirectory() || !samePlatformPath(await realpath(directory), directory)) {
        throw new Error("Official game compiler internal ROM directory must be a real isolated directory");
    }
    const candidates = (await readdir(directory, { withFileTypes: true })).filter((entry) => /\.(?:gb|gbc)$/i.test(entry.name));
    if (candidates.length !== 1 || !candidates[0].isFile()) {
        throw new Error("Official game compiler debug capture requires exactly one regular same-build internal ROM");
    }
    const internalRomFilename = candidates[0].name;
    const stem = path.basename(internalRomFilename, path.extname(internalRomFilename));
    const [internalRom, finalRom, noi, globals] = await Promise.all([
        secureInternalBuildFile(directory, internalRomFilename),
        readFile(builtRom),
        secureInternalBuildFile(directory, `${stem}.noi`),
        secureInternalBuildFile(directory, "globals.i"),
    ]);
    const romSha256 = hashDebugRom(internalRom);
    if (romSha256 !== hashDebugRom(finalRom)) {
        throw new Error("Same-build internal ROM SHA-256 does not match the final output ROM");
    }
    parseNoiDefinitions(noi.toString("utf8"));
    parseGlobalsDefinitions(globals.toString("utf8"));
    const artifactDirectory = await secureDebugArtifactDirectory(root, outputPath);
    const noiPath = path.join(artifactDirectory, "symbols.noi");
    const globalsPath = path.join(artifactDirectory, "globals.i");
    await Promise.all([assertSafeDebugArtifactDestination(noiPath), assertSafeDebugArtifactDestination(globalsPath)]);
    const stagingDirectory = await mkdtemp(path.join(artifactDirectory, ".capture-"));
    try {
        const stagedNoi = path.join(stagingDirectory, "symbols.noi");
        const stagedGlobals = path.join(stagingDirectory, "globals.i");
        await Promise.all([
            writeFile(stagedNoi, noi, { flag: "wx", mode: 0o600 }),
            writeFile(stagedGlobals, globals, { flag: "wx", mode: 0o600 }),
        ]);
        await Promise.all([rename(stagedNoi, noiPath), rename(stagedGlobals, globalsPath)]);
    }
    finally {
        await rm(stagingDirectory, { recursive: true, force: true });
    }
    let sourceDebugAbi;
    let sourceDebugUnavailableReason;
    let liveStateLayout;
    try {
        const include = path.join(temporaryDirectory, "_gbsbuild", "include");
        const [bankdata, dataManager, vm] = await Promise.all([
            secureInternalBuildFile(include, "bankdata.h"),
            secureInternalBuildFile(include, "data_manager.h"),
            secureInternalBuildFile(include, "vm.h"),
        ]);
        sourceDebugAbi = verifyBuildDebugAbi({ bankdata, dataManager, vm });
        if (!sourceDebugAbi)
            sourceDebugUnavailableReason = "The same-build engine headers do not match a supported scene-pointer and global-variable layout.";
        else
            liveStateLayout = await sameBuildLiveStateLayout(path.join(temporaryDirectory, "_gbsbuild"));
    }
    catch {
        sourceDebugUnavailableReason = "The official build did not preserve the engine headers needed to authenticate source-debug memory layouts.";
    }
    return {
        directory: artifactDirectory,
        noiPath,
        globalsPath,
        romSha256,
        noiSha256: hashDebugRom(noi),
        globalsSha256: hashDebugRom(globals),
        internalRomFilename,
        ...(sourceDebugAbi ? { sourceDebugAbi, ...(liveStateLayout ? { liveStateLayout } : {}) } : { sourceDebugUnavailableReason }),
    };
}
/** Compile an existing bounded C source or an actual native game project, without a shell. */
export async function buildRom(options) {
    const root = await realpath(path.resolve(options.projectRoot));
    if (options.projectPath && options.sourcePath) {
        throw new Error("Provide either projectPath or sourcePath, not both.");
    }
    if (!options.projectPath && !options.sourcePath) {
        throw new Error("A .gbsproj projectPath or a C sourcePath is required.");
    }
    if (options.captureDebugArtifacts !== undefined && typeof options.captureDebugArtifacts !== "boolean") {
        throw new Error("captureDebugArtifacts must be a boolean");
    }
    if (options.captureDebugArtifacts && !options.projectPath) {
        throw new Error("Debug artifact capture requires an official game compiler .gbsproj build");
    }
    const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1_000 || timeoutMs > MAX_TIMEOUT_MS) {
        throw new Error(`timeoutMs must be an integer between 1000 and ${MAX_TIMEOUT_MS}.`);
    }
    const colorMode = options.colorMode ?? "dmg";
    if (colorMode !== "dmg" && colorMode !== "gbc" && colorMode !== "gbc-only") {
        throw new Error(`Unsupported Game Boy color mode: ${String(colorMode)}`);
    }
    const source = await resolveExistingWithinRoot(root, options.projectPath ?? options.sourcePath);
    const expectedInputExtension = options.projectPath ? ".gbsproj" : ".c";
    if (path.extname(source).toLowerCase() !== expectedInputExtension) {
        throw new Error(`Input must be a ${expectedInputExtension} file.`);
    }
    if (!(await stat(source)).isFile()) {
        throw new Error(`Input is not a regular file: ${source}`);
    }
    const defaultExtension = colorMode === "dmg" ? ".gb" : ".gbc";
    const defaultOutput = path.join("build", `${path.basename(source, expectedInputExtension)}${defaultExtension}`);
    const outputPath = await resolveOutputWithinRoot(root, options.outputPath ?? defaultOutput);
    if (![".gb", ".gbc"].includes(path.extname(outputPath).toLowerCase())) {
        throw new Error("ROM output must have a .gb or .gbc extension.");
    }
    if (samePlatformPath(source, outputPath)) {
        throw new Error("ROM output cannot overwrite its input.");
    }
    let command;
    let romArguments;
    let builder;
    let gbStudioCli;
    const toolchainRoot = await resolveToolchainRoot(root, options.toolchainRoot);
    if (options.projectPath) {
        const cli = await findGbStudioCli(toolchainRoot);
        gbStudioCli = cli;
        if (!cli) {
            throw new Error('The official GB Studio CLI is unavailable in the selected toolchain. Use the packaged setup skill to prepare runtime,build and bind the resulting toolchain before building. toolchain_doctor with tasks:["projectBuild"] checks readiness; it does not install dependencies.');
        }
        command = process.execPath;
        // The official CLI otherwise suppresses compiler and linker diagnostics.
        romArguments = (rom) => [cli, "make:rom", source, rom, "--verbose"];
        builder = "gb-studio-cli";
    }
    else {
        const compiler = runtimeExecutablePaths(toolchainRoot).gbdkCompiler;
        if (!(await exists(compiler))) {
            throw new Error('GBDK-2020 lcc is unavailable in the selected toolchain. Use toolchain_doctor with tasks:["cBuild"] to inspect setup before compiling C source.');
        }
        command = await resolveExistingWithinRoot(toolchainRoot, compiler);
        const colorFlags = colorMode === "gbc-only" ? ["-Wm-yC"] : colorMode === "gbc" ? ["-Wm-yc"] : [];
        romArguments = (rom) => [...colorFlags, "-o", rom, source];
        builder = "gbdk";
    }
    await mkdir(path.dirname(outputPath), { recursive: true });
    // Recheck after creating directories to avoid traversing a concurrently inserted symlink.
    await resolveOutputWithinRoot(root, outputPath);
    try {
        const existing = await lstat(outputPath);
        if (existing.isSymbolicLink()) {
            throw new Error(`ROM output must not be a symbolic link: ${outputPath}`);
        }
    }
    catch (error) {
        if (!(error instanceof Error) || !("code" in error) || error.code !== "ENOENT") {
            throw error;
        }
    }
    const startedAt = performance.now();
    const sharedBuild = builder === "gb-studio-cli" ? await claimSharedBuildDirectory(root, source, gbStudioCli).catch(() => undefined) : undefined;
    const temporaryDirectory = builder === "gb-studio-cli" ? sharedBuild?.directory ?? (await createIsolatedBuildDirectory(root)) : undefined;
    let compilerSucceeded = false;
    let exitCode = 0;
    let stdout = "";
    let stderr = "";
    let compilerStderr = "";
    let buildFailed = false;
    let sourceProvenance;
    let debugSkipped;
    const debugOptional = () => options.debugArtifactsOptional === true && options.signal?.aborted !== true;
    let stagingDirectory;
    try {
        // The compiler writes into a folder beside the ROM; only a build that succeeds replaces the ROM.
        stagingDirectory = await mkdtemp(path.join(path.dirname(outputPath), ".rom-build-"));
        const builtRom = path.join(stagingDirectory, path.basename(outputPath));
        const args = romArguments(builtRom);
        try {
            if (options.captureDebugArtifacts) {
                try {
                    sourceProvenance = await captureBuildSourceProvenance(source, args[0], options.signal);
                }
                catch (error) {
                    if (!debugOptional())
                        throw error;
                    debugSkipped = error instanceof Error ? error.message : String(error);
                }
            }
            const result = await runBuildCommand(command, args, {
                cwd: root,
                timeoutMs,
                signal: options.signal,
                ...(sharedBuild ? {
                    environment: sharedBuildEnvironment(isolatedCompilerEnvironment(temporaryDirectory)),
                    started: (pid) => claimSharedBuildForCompiler(sharedBuild, pid),
                } : { environment: isolatedCompilerEnvironment(temporaryDirectory) }),
            });
            compilerSucceeded = true;
            stdout = result.stdout;
            stderr = withoutNodeDeprecationNotice(result.stderr);
            compilerStderr = stderr;
        }
        catch (error) {
            buildFailed = true;
            ({ exitCode, stdout, stderr, compilerStderr } = readCommandFailure(error));
            const failure = error instanceof Error ? error : new Error(String(error));
            const cancelled = failure.buildCancelled || options.signal?.aborted === true;
            if (failure.buildCleanupWarning)
                stderr = [stderr, failure.buildCleanupWarning].filter(Boolean).join("\n");
            const log = await writeBuildLog(root, outputPath, { command, args, exitCode, stdout, stderr });
            return {
                success: false,
                builder,
                command,
                args,
                exitCode,
                stdout,
                stderr,
                ...(compilerStderr === stderr ? {} : { compilerStderr }),
                ...(cancelled ? { cancelled: true } : {}),
                ...(failure.buildOutputLimit ? { outputTruncated: true } : {}),
                ...summarizeBuildDiagnostics({ builder, stdout, stderr, success: false, exitCode,
                    timedOut: failure.buildTimedOut, cancelled, outputLimit: failure.buildOutputLimit,
                    authoring: options.authoringWarnings }),
                durationMs: Math.round(performance.now() - startedAt),
                outputPath,
                ...log,
                rom: null,
            };
        }
        let rom = null;
        try {
            rom = await inspectRom(builtRom, root);
        }
        catch (error) {
            stderr = [stderr, error instanceof Error ? error.message : String(error)].filter(Boolean).join("\n");
        }
        let debugArtifacts;
        buildFailed = rom?.valid !== true || droppedGbStudioEvent(builder, stdout, stderr);
        if (!buildFailed && options.captureDebugArtifacts && debugSkipped === undefined && temporaryDirectory) {
            try {
                debugArtifacts = await captureSameBuildDebugArtifacts(root, temporaryDirectory, outputPath, builtRom);
                const after = await captureBuildSourceProvenance(source, args[0], options.signal);
                if (!sourceProvenance || !sameBuildSourceObservation(sourceProvenance, after)) {
                    throw new Error("game compiler source changed during the build; source-debug artifacts are stale. Rebuild after finishing external edits.");
                }
                debugArtifacts.sourceProvenance = sourceProvenance;
            }
            catch (error) {
                debugArtifacts = undefined;
                const reason = error instanceof Error ? error.message : String(error);
                if (debugOptional()) {
                    debugSkipped = reason;
                }
                else {
                    buildFailed = true;
                    stderr = [stderr, reason].filter(Boolean).join("\n");
                }
            }
        }
        const cancelled = options.signal?.aborted === true;
        if (cancelled) {
            buildFailed = true;
            debugArtifacts = undefined;
            stderr = [stderr, "The build was cancelled."].filter(Boolean).join("\n");
        }
        if (buildFailed) {
            rom = null;
        }
        else {
            await rename(builtRom, outputPath);
            rom = { ...rom, path: await realpath(outputPath) };
        }
        const log = await writeBuildLog(root, outputPath, { command, args, exitCode, stdout, stderr });
        const result = {
            success: !buildFailed,
            builder,
            command,
            args,
            exitCode,
            ...(buildFailed ? { stdout, stderr } : successfulBuildOutput(stdout, stderr, log.logPath !== undefined)),
            ...(compilerStderr === stderr ? {} : { compilerStderr }),
            ...(cancelled ? { cancelled: true } : {}),
            ...summarizeBuildDiagnostics({ builder, stdout, stderr, success: !buildFailed, exitCode, cancelled, authoring: options.authoringWarnings }),
            durationMs: Math.round(performance.now() - startedAt),
            outputPath,
            ...log,
            rom,
            ...(debugArtifacts ? { debugArtifacts } : {}),
            ...(!buildFailed && debugSkipped !== undefined
                ? { sourceDebug: { available: false, code: "SOURCE_DEBUG_UNAVAILABLE", reason: `No debug artifacts were captured: ${debugSkipped}` } }
                : {}),
        };
        if (sourceProvenance)
            rememberAuthenticatedSourceBuild(result, args[0], sourceProvenance, debugArtifacts?.sourceDebugAbi);
        return result;
    }
    catch (error) {
        buildFailed = true;
        throw error;
    }
    finally {
        if (stagingDirectory)
            await rm(stagingDirectory, { recursive: true, force: true }).catch(() => { });
        if (temporaryDirectory) {
            try {
                if (sharedBuild)
                    await releaseSharedBuildDirectory(sharedBuild, compilerSucceeded);
                else
                    await removeIsolatedBuildDirectory(temporaryDirectory, root);
            }
            catch (error) {
                if (!buildFailed) {
                    // hermretro: allow no-unsafe-finally — a cleanup failure is the build's error only when the build itself succeeded
                    throw error;
                }
            }
        }
    }
}
