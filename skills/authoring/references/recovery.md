# Recover the failed step

Use the returned code, original request/operation identity, and dispatch evidence
to choose the next action. Correct a definite input prerequisite under the
user's existing authorization, then continue the requested work. Ask only for
missing project identity, intent, or required permission. A timeout or missing
reply is not evidence that an action never started.

| Evidence | Next action |
| --- | --- |
| `PROJECT_SELECTION_REQUIRED` | Read `chromatic_session_status`, then `chromatic_project_select` the known intended absolute `.gbsproj` path and repeat the affected call. This also applies to `chromatic_device_capture` status/read calls, which require a selected project. Preserve the same owner's capture ID; do not create a substitute project or capture. If another project/session is active, resolve that ownership before switching. For a standalone ROM call whose error offers workspace configuration, follow that instruction; capture still requires a native project. |
| A definite rejected input or stale revision before mutation | Refresh only the relevant state, correct the input, and continue within the original request. For device operations, require positive non-start evidence such as `operationStarted:false`; reuse existing consent, but keep the exact intended ROM and device. A returned operation or uncertain dispatch goes through original-operation recovery instead. |
| `CHROMATIC_JOURNAL_ACCESS_DENIED`, `EACCES`, `EPERM`, or a reported OS denial | Identify the specific file/device permission needed. Apply an already-authorized normal access correction where available; otherwise request that permission once. Preserve the denial and continue independent work. Do not relocate the journal, reinstall dependencies, or bypass the denied surface. |
| An operation is running, unresolved, or its reply was lost | Read the original `chromatic_device` `operation_status` by `operationId`, or by the caller's original direct-MCP `requestId` if no operation ID returned. A copied preview request ID is preview-scoped: use its copied operation ID, or call `chromatic_web_preview` `install_status` with `installationRequestId` set to that original UUID. Supplied IDs never fall back to the latest request. Match the returned request ID and known generation before adopting a result; `requestedOperationUnknown: true` preserves the original uncertainty. If exact public lookup is unavailable, that same dialog's **Check status** uses its saved request ID. These are status reads, not replacement attempts. |
| A closed `device.program_failed` | Use the original operation's public error/recovery and the preview's **Copy error** report, including optional `failureDetails`. Preserve `cartridgeWrite: "outcome-unverified"`. The generic code and observed low-level tokens do not identify a cause or authorize a retry. If original details are unavailable, say so once and leave the cause unknown. |
| The user cannot see the game in the hermretro emulator | Give the user `studio.playerUrl` from `chromatic_present_game` and retain any concrete browser error they report. Continue requested gameplay checks with public emulator tools on the exact intended ROM, preparing the emulator component if needed under existing authorization. Follow [stepped playtesting](../../rom-debugging/references/stepped-playtesting.md#when-browser-play-is-unavailable); report native gameplay separately from unobserved browser UI and physical hardware. |

For a known first-use activation requirement or an explicit Developer Mode error,
direct the user to the official [ModRetro Updater](https://support.modretro.com/en_us/articles/chromatic-firmware-updater-ryhoYnzCx).
The plugin does not manage activation or collect codes. Do not infer an invalid
code or a seat limit from a generic failure. After the updater workflow, use
fresh device discovery and selection and the normal flash confirmation; preserve
any previous write's uncertain outcome. See the
[deployment skill](../../deployment/SKILL.md#prepare-a-first-write-on-a-new-computer).

After a targeted correction, check its result before proceeding. If the same
failure persists without new evidence, retain the concrete blocker and choose
independent work; do not cycle through resets, new request IDs, or repeat approval
questions. Report what failed, what the original evidence establishes, and which
part of the user's task can still continue.
