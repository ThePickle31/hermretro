# Start and select the intended project

The trusted runtime/toolchain checkout, authorized workspace, selected project,
and emulator artifact root are distinct. A plugin cache, installed checkout,
toolchain, or bundled starter never implicitly authorizes a user's project.

Carry returned absolute artifact paths across tools. A relative `chromatic_rom_build`
`outputPath` is selected-project-relative, while `chromatic_rom_inspect`, emulator ROM and
recording paths resolve from the authorized
workspace. That workspace may contain a nested selected project. In particular,
pass the build's returned absolute `outputPath` to `chromatic_rom_inspect` and
`chromatic_emulator_run`, and retain the returned absolute `recordingPath` for later
export or clip extraction. The short `build/...` examples in
[browser preview](browser-preview.md) assume that the selected project root is also the authorized workspace.

## Select an existing project

Begin with read-only `chromatic_session_status`. To use an existing project when no
workspace has been authorized, `chromatic_project_select` must use its absolute
`.gbsproj` path. That selection authorizes only the selected project's directory:

```text
chromatic_session_status {}
chromatic_toolchain_doctor {}
chromatic_project_select {"projectPath":"/absolute/path/to/MyGame/project.gbsproj"}
chromatic_project_inspect {}
chromatic_project_inventory {"resourceTypes":["scene","actor","asset"],"detail":"standard"}
```

On Windows, provide the actual absolute drive-qualified project path and escape
backslashes when writing JSON. Relative selection remains unavailable until an
appropriate workspace has been explicitly authorized.

## Create a project

For a new project, leave `destinationPath` out: hermretro creates it in its games folder (`<plugin>/games/<name>`).
For a folder the user names, `chromatic_project_create` accepts an
absolute new destination whose real canonical parent directory already exists.
It creates no missing parents, never overwrites an existing destination, and
authorizes only the created project, not its parent or siblings. Creation
leaves selection unchanged unless `select: true` is explicit.

## One project per chat

hermretro starts each chat's engine worker without a configured workspace
and binds it to one project folder; for a sibling project, start a new chat.
(With `GB_STUDIO_WORKSPACE_ROOT` set for the engine, creation, discovery, and
selection could use paths relative to that fixed boundary:)

```text
chromatic_project_discover {"projectPath":"MyGame/project.gbsproj"}
chromatic_project_select {"projectPath":"MyGame/project.gbsproj"}
chromatic_project_inspect {}
```

`chromatic_project_discover` is read-only: it never selects or authorizes a project and
cannot precede authorization in an unconfigured session. The selected project
must remain inside the authorized boundary after resolving symlinks. Editing
the bundled starter directly additionally requires `allowStarter: true`.

Within an authorized workspace, `chromatic_project_create` remains confined to it;
neither creation nor selection can broaden access to a sibling outside it.
Relative creation requires an authorized workspace. Choose `template: "starter"`
for a minimal `Start` scene. For the complete editable
[Wrecklight sample](wrecklight-remix.md), use `template: "wrecklight"` and supply
its matching local `templateSourcePath` when using the compact package.
Wrecklight must be copied: direct
selection of either bundled copy is rejected, even with `allowStarter: true`.
Close an active emulator
with `chromatic_emulator_close` before selecting another project. `chromatic_session_status` can report
the selected project, authorized workspace, selection generation, and emulator
state without granting further access. Selecting another project automatically
closes its predecessor's browser preview and invalidates that preview URL.
