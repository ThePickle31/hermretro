# Inspect efficiently and manage revisions

Use compact `chromatic_project_inspect` to obtain identity, selected settings, a project
revision, exact resource and health totals, and bounded diagnostics.
`chromatic_project_inventory` returns a normalized, paginated resource graph by default.
Filter it by `sceneId`, `resourceTypes`, `assetTypes`, `detail`, `fields`, or
`limit`; scenes reference `actorIds` and `triggerIds` while each resource is
returned only once. A `STALE_CURSOR` requires a fresh inspection.

Read game data through these and the other `*_inspect` tools, not by opening `.gbsres` or `.gbsproj` files with
`cat`, `grep` or a script: the tools return what the engine reads, with the revisions edits need.

## The world index

The session-owned semantic world index performs one complete authored-resource
census when exact initial project health is needed. Subsequent focused reads
and server-authored changes should reuse indexed identities and mutation IDs,
not repeatedly rebuild the entire project graph. The index never writes a
database, cache, lock, or marker into the user's project.

Request `chromatic_session_status {"includeIndexStats":true}` only when diagnosing index
behavior. Unchanged focused warm reads should not increase counters such as
`fullInventoryBuilds`, `fullHashPasses`, or `authoredFileReads`.

## Revisions and freshness

Project revisions use 64-character `sha256-merkle-v2` tokens covering the
selected descriptor, `project/**`, and `assets/**`. Previously issued revisions
and cursors can become stale after an upgrade or change. Local plugin event
handlers can affect semantic-query freshness without being included in the
public project revision.

Server-authored updates become visible immediately. External desktop edits are
eventually observed by the filesystem watcher; an ordinary warm read does not
prove that an undelivered external edit is absent. Request expensive
`chromatic_project_refresh {"mode":"strong"}` only when an authoritative whole-project
verification is needed, including globally sensitive destructive decisions.

## Write locks

Authoring calls from cooperating plugin processes share locks outside the
project. If an interrupted write later reports `RESOURCE_WRITE_LOCKED`, do not
infer whether it completed or repeat it. Reread the exact native resource when
available. Project-wide locks can be recovered when the same host can prove the
old owner exited; an ambiguous or older resource-level lock stays protected and
has no public unlock tool. A distributed resource lock applies to that owner;
legacy resources share the `.gbsproj`, so its lock can block multiple edits.
If it persists after the writing sessions are closed, preserve the project and
error details for operator recovery. An external GB Studio editor does not
participate in these locks.

## Compiler preset

`chromatic_project_inspect` and `chromatic_project_inventory` with `includeSettings:true` report the
current `compilerPreset`. `chromatic_settings_update` accepts `expectedRevision` from `chromatic_project_inspect` and checks
it against a fresh project snapshot before writing. Its `compilerPreset`
setting supports the editor's four compiler search budgets: `1000`, `3000`
(default), `50000`, and `100000`. Larger budgets spend more time compiling; measure the
resulting ROM rather than assuming they improve runtime performance.
