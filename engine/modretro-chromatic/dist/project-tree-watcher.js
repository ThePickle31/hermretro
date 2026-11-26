import { EventEmitter } from "node:events";
import { lstatSync, readdirSync, watch } from "node:fs";
import path from "node:path";

function vanishedProjectTreeEntry(error) {
    return typeof error === "object" && error !== null && (error.code === "ENOENT" || error.code === "ENOTDIR");
}
function sameProjectTreeFolder(watched, stats) {
    return stats !== undefined && watched.dev === stats.dev && watched.ino === stats.ino;
}
class ProjectTreeWatcher extends EventEmitter {
    #root;
    #persistent;
    #folders = new Map();
    #closed = false;
    constructor(root, options, listener) {
        super();
        this.#root = path.resolve(root);
        this.#persistent = options.persistent ?? true;
        this.on("change", listener);
        try {
            this.#watchFolder(this.#root, false);
        } catch (error) {
            this.close();
            throw error;
        }
    }
    close() {
        if (this.#closed)
            return;
        this.#closed = true;
        for (const folder of this.#folders.values())
            folder.watcher.close();
        this.#folders.clear();
        this.emit("close");
    }
    /**
     * Watch `folder` and every folder below it; `report` names each entry found as new. A watch follows the folder it
     * was added on, and fs.watch and readdirSync follow symbolic links, so the folder must be the same folder (not a
     * link) before the watch and after its listing; one that changed in between is not watched.
     */
    #watchFolder(folder, report) {
        if (this.#closed)
            return;
        let entries;
        try {
            const stats = this.#folderAt(folder);
            if (!stats)
                throw Object.assign(new Error(`The watched project path is not a folder: ${folder}`), { code: "ENOTDIR" });
            const watched = { dev: stats.dev, ino: stats.ino };
            watched.watcher = watch(folder, { persistent: this.#persistent }, (eventType, name) => this.#onFolderEvent(folder, watched, eventType, name));
            watched.watcher.on("error", (error) => this.#fail(error));
            this.#folders.set(folder, watched);
            entries = readdirSync(folder, { withFileTypes: true });
            if (!sameProjectTreeFolder(watched, this.#folderAt(folder)))
                throw Object.assign(new Error(`The watched project folder changed while it was read: ${folder}`), { code: "ENOTDIR" });
        } catch (error) {
            if (folder === this.#root || !vanishedProjectTreeEntry(error))
                throw error;
            this.#forget(folder);
            return;
        }
        for (const entry of entries) {
            const file = path.join(folder, entry.name);
            if (report)
                this.#report("rename", file);
            if (entry.isDirectory() && !this.#folders.has(file))
                this.#watchFolder(file, report);
        }
    }
    /**
     * An event from the watch on `folder`. One about the folder itself (it was removed, moved, replaced or changed;
     * Node names it by the folder's own name) or from a folder no longer at its path watches that path again.
     */
    #onFolderEvent(folder, watched, eventType, name) {
        if (this.#closed || this.#folders.get(folder) !== watched)
            return;
        try {
            if (name == null) {
                this.emit("change", eventType, null);
                return;
            }
            const file = path.join(folder, name.toString());
            const current = this.#folderAt(file);
            const aboutItself = name.toString() === path.basename(folder) && current === undefined && !this.#exists(file);
            if (aboutItself || !sameProjectTreeFolder(watched, this.#folderAt(folder))) {
                this.#watchAgain(folder);
                return;
            }
            const known = this.#folders.get(file);
            if (known && !sameProjectTreeFolder(known, current))
                this.#forget(file);
            this.#report(eventType, file);
            if (current && !this.#folders.has(file))
                this.#watchFolder(file, true);
        } catch (error) {
            this.#fail(error);
        }
    }
    #watchAgain(folder) {
        this.#forget(folder);
        if (folder === this.#root)
            throw Object.assign(new Error(`The watched project folder was removed or replaced: ${folder}`), { code: "ENOENT" });
        this.#report("rename", folder);
        if (this.#folderAt(folder))
            this.#watchFolder(folder, true);
    }
    /** The folder's lstat, or undefined when `file` is gone or is not a folder now. */
    #folderAt(file) {
        try {
            const stats = lstatSync(file);
            return stats.isDirectory() ? stats : undefined;
        } catch (error) {
            if (vanishedProjectTreeEntry(error))
                return undefined;
            throw error;
        }
    }
    #exists(file) {
        try {
            lstatSync(file);
            return true;
        } catch (error) {
            if (vanishedProjectTreeEntry(error))
                return false;
            throw error;
        }
    }
    #forget(folder) {
        const below = folder + path.sep;
        for (const [watched, { watcher }] of this.#folders) {
            if (watched === folder || watched.startsWith(below)) {
                watcher.close();
                this.#folders.delete(watched);
            }
        }
    }
    #report(eventType, file) {
        this.emit("change", eventType, path.relative(this.#root, file));
    }
    #fail(error) {
        if (this.#closed)
            return;
        this.close();
        this.emit("error", error);
    }
}
/**
 * A recursive project watch whose every failure is an "error" event. Node's recursive fs.watch is native on macOS and
 * Windows. On Linux, Node 24.22, 26.9 and newer keep one watch per folder whose handlers throw outside any "error"
 * event (ENOTDIR when a watched folder becomes a file, or a watch that cannot be added), which ends the engine; there
 * the engine keeps those per-folder watches itself, on every Node version.
 */
export function watchProjectTree(root, options, listener) {
    return process.platform === "linux" ? new ProjectTreeWatcher(root, options, listener) : watch(root, options, listener);
}
