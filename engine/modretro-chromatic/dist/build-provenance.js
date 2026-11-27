import { createHash } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, readdir, realpath } from "node:fs/promises";
import path from "node:path";
import { isPathWithinRoot } from "./platform.js";
import { PROJECT_REVISION_ALGORITHM } from "./project-access.js";
import { ProjectRevisionTree } from "./project-revision.js";
const SOURCE_DIRECTORIES = ["project", "assets", "plugins"];
const ENGINE_LAYOUT = "gbvm-farptr3-uword16-v1";
// Deliberately process-local. A JSON document of asserted hashes is not a
// receipt that this server built a selected project and captured its sidecars.
const AUTHENTICATED_BUILDS = new WeakMap();
const SOURCE_OBSERVATIONS = new WeakMap();
// Parsed from the captured header, never accepted from a serialized artifact
// or public caller. Keep the existing public ABI shape/digest unchanged.
const ABI_GLOBAL_HEAPS = new WeakMap();
function systemError(error, code) {
    return typeof error === "object" && error !== null && "code" in error && error.code === code;
}
function samePath(left, right) {
    return isPathWithinRoot(left, right) && isPathWithinRoot(right, left);
}
function observeFile(observation, filename, metadata) {
    observation.update(JSON.stringify([filename, metadata.dev.toString(), metadata.ino.toString(),
        metadata.mode.toString(), metadata.size.toString(), metadata.mtimeNs.toString(), metadata.ctimeNs.toString()])).update("\0");
}
async function hashRegularFile(filename, observation, signal) {
    signal?.throwIfAborted();
    const before = await lstat(filename, { bigint: true });
    if (!before.isFile() || before.isSymbolicLink() || !samePath(await realpath(filename), filename)) {
        throw new Error(`Source provenance requires a real regular file: ${filename}`);
    }
    const descriptor = await open(filename, constants.O_RDONLY | (process.platform === "win32" ? 0 : (constants.O_NOFOLLOW ?? 0)));
    try {
        const opened = await descriptor.stat({ bigint: true });
        if (before.dev !== opened.dev || before.ino !== opened.ino || before.size !== opened.size
            || before.mtimeNs !== opened.mtimeNs || before.ctimeNs !== opened.ctimeNs) {
            throw new Error("Project source changed while its build identity was being collected; retry the build.");
        }
        const digest = createHash("sha256");
        for await (const chunk of descriptor.createReadStream({ autoClose: false })) {
            signal?.throwIfAborted();
            digest.update(chunk);
        }
        const after = await descriptor.stat({ bigint: true });
        if (before.dev !== after.dev || before.ino !== after.ino || before.size !== after.size
            || before.mtimeNs !== after.mtimeNs || before.ctimeNs !== after.ctimeNs) {
            throw new Error("Project source changed while its build identity was being collected; retry the build.");
        }
        if (observation)
            observeFile(observation, filename, after);
        return digest.digest("hex");
    }
    finally {
        await descriptor.close();
    }
}
async function collectSourceFiles(root, directory, entries, observation, signal) {
    signal?.throwIfAborted();
    let metadata;
    try {
        metadata = await lstat(directory, { bigint: true });
    }
    catch (error) {
        if (systemError(error, "ENOENT")) {
            observation.update(JSON.stringify([directory, "missing"])).update("\0");
            return;
        }
        throw error;
    }
    if (!metadata.isDirectory() || metadata.isSymbolicLink() || !samePath(await realpath(directory), directory)) {
        throw new Error("Source provenance requires real authored directories inside the selected project.");
    }
    observeFile(observation, directory, metadata);
    const children = (await readdir(directory, { withFileTypes: true }))
        .sort((left, right) => Buffer.compare(Buffer.from(left.name), Buffer.from(right.name)));
    for (const child of children) {
        const filename = path.join(directory, child.name);
        if (child.isDirectory())
            await collectSourceFiles(root, filename, entries, observation, signal);
        else
            entries.push({
                relativePath: path.relative(root, filename).split(path.sep).join("/"),
                sha256: await hashRegularFile(filename, observation, signal),
            });
    }
}
/** Strong exact-byte identity for the descriptor, authored files, and project plugins. */
export async function captureBuildSourceProvenance(projectPath, compilerPath, signal) {
    signal?.throwIfAborted();
    const project = await realpath(path.resolve(projectPath));
    const root = path.dirname(project);
    const observation = createHash("sha256").update("codex-gb-studio\0build-source-observation-v1\0");
    const publicEntries = [{ relativePath: path.basename(project), sha256: await hashRegularFile(project, observation, signal) }];
    for (const directory of SOURCE_DIRECTORIES.slice(0, 2)) {
        await collectSourceFiles(root, path.join(root, directory), publicEntries, observation, signal);
    }
    const plugins = [];
    await collectSourceFiles(root, path.join(root, "plugins"), plugins, observation, signal);
    const projectRevision = new ProjectRevisionTree(publicEntries).revision();
    const pluginRevision = new ProjectRevisionTree(plugins).revision();
    const sourceFingerprint = createHash("sha256")
        .update("codex-gb-studio\0build-source-v1\0")
        .update(projectRevision).update(pluginRevision).digest("hex");
    const result = {
        formatVersion: 1,
        projectPath: project,
        projectRevision,
        revisionAlgorithm: PROJECT_REVISION_ALGORITHM,
        sourceFingerprint,
        compilerSha256: await hashRegularFile(await realpath(compilerPath), observation, signal),
    };
    SOURCE_OBSERVATIONS.set(result, observation.digest("hex"));
    return result;
}
export function sameBuildSourceProvenance(left, right) {
    return samePath(left.projectPath, right.projectPath)
        && left.projectRevision === right.projectRevision
        && left.sourceFingerprint === right.sourceFingerprint
        && left.compilerSha256 === right.compilerSha256;
}
/** Detect writes restored to the same bytes without depending on filesystem watchers. */
export function sameBuildSourceObservation(left, right) {
    const before = SOURCE_OBSERVATIONS.get(left);
    return before !== undefined && before === SOURCE_OBSERVATIONS.get(right) && sameBuildSourceProvenance(left, right);
}
function supportedGlobalHeap(vm) {
    const lines = vm.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const guard = /^#\s*ifndef\s+([A-Za-z_][A-Za-z0-9_]*)$/.exec(lines[0] ?? "")?.[1];
    const hasGuard = guard !== undefined && lines[1] === `#define ${guard}`;
    const conditions = [];
    let heap;
    let declaration = false;
    let globalMapping = false;
    const unconditional = () => conditions.length === 0
        || (conditions.length === 1 && conditions[0].outer && !conditions[0].alternative);
    // This is a supported source shape, not an attempted C preprocessor.
    if ((vm.match(/\bVM_HEAP_SIZE\b/g) ?? []).length !== 2)
        return undefined;
    for (let index = 0; index < lines.length; index++) {
        const line = lines[index];
        if (/^#\s*(?:if|ifdef|ifndef)\b/.test(line)) {
            conditions.push({ outer: index === 0 && hasGuard, alternative: false });
        }
        else if (/^#\s*(?:else|elif)\b/.test(line)) {
            if (!conditions.length)
                return undefined;
            conditions[conditions.length - 1].alternative = true;
        }
        else if (/^#\s*endif\b/.test(line)) {
            if (!conditions.pop())
                return undefined;
        }
        else if (/^#\s*define\s+VM_HEAP_SIZE\b/.test(line)) {
            const literal = /^#\s*define\s+VM_HEAP_SIZE\s+([1-9][0-9]*)$/.exec(line)?.[1];
            if (!unconditional() || heap !== undefined || literal === undefined)
                return undefined;
            heap = Number(literal);
            if (!Number.isSafeInteger(heap) || heap > 0x2000 / 2)
                return undefined;
        }
        else if (/^#\s*(?:define|undef)\s+VM_GLOBAL\b/.test(line)) {
            if (globalMapping || !unconditional()
                || !/^#\s*define\s+VM_GLOBAL\(([A-Za-z_][A-Za-z0-9_]*)\)\s+script_memory\s*\[\s*\(\s*\1\s*\)\s*\]$/.test(line))
                return undefined;
            globalMapping = true;
        }
        else if (/^extern\b.*\bscript_memory\b/.test(line)) {
            if (declaration || !unconditional()
                || !/^extern\s+UWORD\s+script_memory\s*\[\s*VM_HEAP_SIZE\s*\+\s*\(\s*VM_MAX_CONTEXTS\s*\*\s*VM_CONTEXT_STACK_SIZE\s*\)\s*\]\s*;$/.test(line))
                return undefined;
            declaration = true;
        }
        else if (/\bVM_HEAP_SIZE\b/.test(line) || /^#\s*(?:define|undef)\s+script_memory\b/.test(line))
            return undefined;
    }
    return conditions.length === 0 && declaration && globalMapping ? heap : undefined;
}
function normalizeHeaderSource(bytes) {
    // C phase 2 splices physical lines once, before recognizing comments or
    // directives. The original bytes still supply the ABI digest below.
    const source = Buffer.from(bytes).toString("utf8").replace(/\\\r?\n/g, "");
    let unterminated = false;
    const clean = source.replace(/"(?:\\[^\r\n]|[^"\\\r\n])*"|'(?:\\[^\r\n]|[^'\\\r\n])*'|\/\*[\s\S]*?\*\/|\/\/[^\r\n]*|["']|\/\*/g, (token) => {
        if (token === '"' || token === "'" || token === "/*") {
            unterminated = true;
            return token;
        }
        // Recognize literals before comments, then mask both. Quoted markers must
        // not hide active directives or supply a fake structural declaration.
        return token.replace(/[^\r\n]/g, " ");
    });
    return unterminated ? undefined : clean;
}
/** Check only the layouts actually decoded by source-debug, using same-build headers. */
export function verifyBuildDebugAbi(headers) {
    const bankdata = normalizeHeaderSource(headers.bankdata);
    const dataManager = normalizeHeaderSource(headers.dataManager);
    const vm = normalizeHeaderSource(headers.vm);
    if (bankdata === undefined || dataManager === undefined || vm === undefined)
        return undefined;
    const globalHeapWords = supportedGlobalHeap(vm);
    if (!/typedef\s+struct\s+far_ptr_t\s*\{\s*UBYTE\s+bank\s*;\s*void\s*\*\s*ptr\s*;\s*\}\s*far_ptr_t\s*;/.test(bankdata)
        || !/extern\s+far_ptr_t\s+current_scene\s*;/.test(dataManager)
        || globalHeapWords === undefined)
        return undefined;
    const digest = createHash("sha256").update(`${ENGINE_LAYOUT}\0`);
    for (const bytes of [headers.bankdata, headers.dataManager, headers.vm]) {
        digest.update(createHash("sha256").update(bytes).digest());
    }
    const abi = Object.freeze({ layout: ENGINE_LAYOUT, sha256: digest.digest("hex") });
    ABI_GLOBAL_HEAPS.set(abi, globalHeapWords);
    return abi;
}
export const LIVE_STATE_LAYOUT = "gbstudio-4.3.0-e1-live-v2";
export const LIVE_STATE_ENGINE_SHA256 = Object.freeze({
    "include/actor.h": "aaed624fc6755e3200326bb5a1f636cd46432d0ab92c7181586b9451255f4db6",
    "include/bankdata.h": "42fb6f3540b9744639e74bbeaabd1d5a6a7e0c63a566bca8c72fd6fd08264654",
    "include/data_manager.h": "299b3c71962dd9914b8b152ea23081584883ff2c003d7f45743e8f74b18572e2",
    "include/gbs_types.h": "a55bf0eb19d96790459d854108f24c6d27dc5af1603ed3fee3d1fa610ca9bb2e",
    "include/input.h": "2f13adaeb9e4f31c2def5816633271a209ef19d377bed43aa3400078cf65d693",
    "include/math.h": "7f1d00b9e9eed911872fa42209c23073c8fcf02f3e39c9aee8a8f2aa27cb2169",
    "include/ui.h": "2c4c0a0f001bda0e512dc4fafd5b41380302a7347b347c8517a177b6dad0a199",
    "include/vm.h": "735d2c3ae88ebcf2b4f5cac48f727cc1b2ed5d2db67b1054a6e9050fbeccb607",
    "include/vm.i": "d07af6798364e4bcbc2b128738d9470d9529f3f4e4516538273b997213ec58f3",
    "src/core/actor.c": "b7360f4e84c720090e127aa047daa21f7d70517a4a2d9512d2a96f568e9ee5f5",
    "src/core/core.c": "7978d2147d09294f25886d604fc4093cb1ba2084e809cab46b32d86861bbe353",
    "src/core/data_manager.c": "2ff20d8a9d3efe6b752d391d988aa9c74e669d87a13dcaf37f64700b5987d190",
    "src/core/input.c": "7b4db1936abb55f826abfa0cfc1c3cc2b5379b24c6476bf9750fbce370331210",
    "src/core/ui.c": "2bdb8547aaea5c43b48d90c84a0a06c62a84cdfcd77f58780aa4245c255b9c55",
    "src/core/vm.c": "7dc77593c03a2354bbfa72a87bdf539c47c62a97a63e744fff58360f8666197c",
    "src/core/vm_gameboy.c": "a4f89644092f814ac6392331770a7f79713654188b4d21c7e8be076ff3b8ba91",
    "src/core/vm_ui.c": "435963c667f68afea93c83f1fa39321b2778cad8dd453a98b56c63cca169fdbb",
    "src/states/adventure.c": "1f48b90a0feaa743ae54311aecadd10f4beb816d0b130b581a533fcfbb07a89b",
    "src/states/logo.c": "4a0e5f6e8b410a2d21c63de4a5b57ca0d8f2c1c0bd4284261929a752434126ca",
    "src/states/platform.c": "a3be840ff9fed3cbb6cd879c156f3dcd3784d6050559f16ac546d1f727b3e382",
    "src/states/pointnclick.c": "e11cbc940de4badd56f4ef5ae9bda701b1432c14198c98b8b8361b5af5a6ec26",
    "src/states/shmup.c": "1cfb193d1f9f67a1db63613293e01f97e7271fd742def8b233f83e6206274159",
    "src/states/topdown.c": "58eb9d200fdce227b643ab21623fe70cbc9a086d49aa454f0ecb7ff2c559e668"
});
/** @internal Called only after successful same-build capture and source revalidation. */
export function rememberAuthenticatedSourceBuild(build, compilerPath, source, abi) {
    if (!build.success || build.builder !== "gb-studio-cli" || !build.debugArtifacts)
        return;
    const globalHeapWords = abi && ABI_GLOBAL_HEAPS.get(abi);
    AUTHENTICATED_BUILDS.set(build, Object.freeze({
        outputPath: build.outputPath,
        compilerPath,
        source: Object.freeze({ ...source }),
        artifacts: Object.freeze({ ...build.debugArtifacts }),
        ...(abi && globalHeapWords !== undefined ? { abi: Object.freeze({ ...abi }), globalHeapWords } : {}),
    }));
}
/** A serialized or caller-created build result deliberately has no receipt. */
export function authenticatedSourceBuild(build) {
    return AUTHENTICATED_BUILDS.get(build);
}
