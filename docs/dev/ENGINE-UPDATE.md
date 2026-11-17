# Updating the vendored engine

`engine/modretro-chromatic/` is ModRetro's Chromatic plugin engine (MIT), vendored. The plugin refuses to start
an engine whose files differ from `engine/pins/<version>/manifest.json`, so an update is a deliberate,
single pull request (`chore/engine-<version>`).

1. **Replace the folder** with the new release, leaving out ModRetro's packed CLI archives
   (`third-party/chromatic-cli/executables-v2.br`, `notices.br`) and the Linux capture ffmpeg builds
   (`native/capture/linux/*/ffmpeg`): the plugin never redistributes them.
2. **Re-apply the one local patch** (recorded as `local_patches` in the manifest): in `dist/server.js` and
   `dist/device-capture/linux-helper.js`, the ffmpeg capture input reads `/dev/fd/6` instead of the per-process
   path under the proc filesystem. Without it the install scanner asks every installer for confirmation.
3. **Record the new files**: `python tools/engine/manifest.py write engine/pins/<v>/manifest.json`,
   then copy the `local_patches` entry into it; delete the old manifest.
4. **Pin the tool contracts**: save the new engine's answers to `initialize` and `tools/list` as
   `engine/pins/<v>/tools.json`, in the same shape as the previous file (delete the old folder), and run `python tools/engine/reconcile_schemas.py engine/pins/<v>/tools.json` (it starts the engine and
   diffs every tool; keep its report as `engine/pins/<v>/schema-reconcile.json`).
5. **Bump the version** in `adapter/paths.py` (`ENGINE_VERSION`), the `version:` line of the five adapted skills,
   and `THIRD_PARTY_NOTICES.md`. `python -m unittest tests/test_lockstep.py` lists anything missed.
6. **Compare the skills by hand**: diff `engine/modretro-chromatic/skills/` against the previous release and carry
   real changes into `skills/` (keep the Hermes edits and each `## In hermretro` section).
7. **New or renamed tools**: `tests/test_lockstep.py` names every place (step words, manifest, CONTRACT counts).
8. Run `python tools/check.py full` and the clean install; CI runs integration on Linux and macOS.

Every existing prepared engine (`~/.hermes/hermretro/.cache/engine-<old version>`) is ignored after the bump; the
device CLI shows as missing until it is installed again for the new version.
