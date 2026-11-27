# Reviewed custom-event dependencies

The world index can use a reviewed custom-event extractor without evaluating
project JavaScript. This is trusted maintained-source configuration, not a
public project setting. A command name, plugin manifest, successful build, or
project-provided `complete` flag never establishes complete semantic coverage.

The catalog (`REVIEWED_CUSTOM_EVENTS` in `dist/custom-event-dependencies.js`)
is empty today: its reviewed profiles were all for ModRetro's Wrecklight sample,
which hermretro does not ship. So every project-owned custom event is
unreviewed, and its effects leave coverage incomplete. A profile added later
requires its complete matching handler/helper set; individual hashes from
different profiles cannot be combined. Changed or ambiguous inputs leave
coverage incomplete.

When coverage is incomplete, use `world_dependencies` and its `coverageCursor`
to inspect the actual reasons. Some reasons concern native references, such as
an unresolved variable or engine field. `UNVERIFIED_CUSTOM_EVENT_CONTRACT` can
mean changed, mixed or unreviewed handler/compiler sources, an unsupported
authored contract (for example, a different owner or descriptor), or an invalid
invocation. A successful build, retry, or `adopt_binding` cannot establish an
unsupported custom-event contract. Bound-room tilemap operations refuse with
`TILEMAP_DEPENDENCY_UNCERTAIN` and leave native output unchanged. Atlas-only
inspection remains available, but does not grant room-edit coverage.

## What a review must establish

A `ReviewedEventContract` in `src/custom-event-dependencies.ts` records:

- A review ID and version, the reviewed loader profile, and the exported command.
- The complete handler's project-relative path, byte count and SHA256.
- The complete required helper/definition bindings, including data that affects
  exports, field handling, defaults, nested branches and resource resolution.
- The fields accepted by the handler, distinguishing editor defaults from values
  actually supplied to compilation.
- A maintained extractor that enumerates all relevant project variable and
  resource effects, plus only the child branches actually compiled.

Review the complete handler and the relevant helper/definition closure. Hashes
identify that reviewed source; they do not prove what it does. Bump the review
version when its interpretation or extractor dependencies change. The registry
fingerprint includes descriptor metadata and extractor function text, but it
cannot authenticate mutable state captured by a JavaScript closure. Extractors
must therefore use only their supplied immutable input/context and reviewed
maintained constants.

The current binding domain is the existing indexed project snapshot:
`project/**`, `assets/**` and `plugins/**`. A dependency on an external compiler,
SDK, patched engine materialization, emitted actor layout or an unindexed file
does not become verified merely by recording its path or a past build hash.
If those semantics cannot be established within the bound context, the entry
must remain absent or return `status: "incomplete"`. Do not add a broad path
exception, an arbitrary first-seen baseline, or execute a plugin to fill the gap.

## Resolving the handler

The reviewed GB Studio 4.3.2 source loads core handlers before project exports
from `plugins/*/**/events/event*.js`, keyed by exported ID. The registry requires
the exact handler and all dependency hashes/sizes from the complete index. It
does not infer export IDs with a text regex or depend on glob ordering to choose
between competing exports.

Missing or changed bindings, multiple matching exports, multiple reviews
claiming the selected handler, or another unreviewed export make the selected
review uncertain. An unreviewed export can also override a familiar core event;
an indexed graph cannot borrow that event's native semantics in this case.
Direct graph callers without the indexed binding map cannot establish reviewed
custom-event coverage.

`ReviewedEventRegistry` is injected only through the maintained graph/index
constructor options. The ordinary MCP uses the maintained default catalog; it
does not deserialize registry objects or executable extractors from a project.

## Extracting effects

Compilation receives event arguments merged with child fields, with child fields
taking precedence. The extractor follows that behavior and does not automatically
apply editor defaults. Unknown input fields, malformed children, unresolved
targets, unsupported access types, excessive results, thrown exceptions or an
explicitly incomplete effect result keep coverage incomplete.

An extractor receives a cloned, frozen input and context. Its complete result
can describe `read`, `write`, or `read-write` variable effects and typed resource
relationships. Resource targets must resolve uniquely, including scene context
for actor identities. Formal/local variables use the graph's existing binding
rules; an unresolved formal is not a global variable.

Only returned `events` branches are expanded. A declared but uncompiled branch
is not promoted to executable behavior. Authored structural preservation still
retains the underlying data, including opaque and commented content.

Results are bounded to 4096 effects, 256 child branches, 256-character target and
scene IDs, and 128-character relation names. The registry admits at most 697
contracts and 256 dependency/field rows per contract. These are ceilings, not
permission to omit a required dependency or truncate an effect set into success.

## Freshness and destructive changes

The existing plugin semantic generation remains separate from the public
project revision. Handler/helper/export changes invalidate that generation and
the reviewed graph fingerprint. An extractor may depend on other indexed
resources, so nonempty registries conservatively rebuild the semantic graph
instead of taking the optimization that revisits only a changed actor. They
also bypass the opaque-file shortcut: ordinary committed-path updates to helper
files publish new coverage, review evidence and semantic freshness immediately,
including when a helper is deleted, without waiting for a strong refresh.

Prepared transactions retain their existing strong refresh and semantic-generation
comparison immediately before publication. A helper changing after preparation
therefore refuses the write even if the public authored revision did not change.

Hidden variable and resource effects also become structural references, tagged
with their review identity. They protect native background ownership and
destructive resource operations. Same-scene deletion cannot discard a hidden
reference merely because the final authored-argument scan cannot see it. It
remains conservatively in use while its owner survives the transaction; removing
that owner removes the reference. The pre-edit index cannot prove dependencies
introduced by a proposed owner. Until proposed overlays are semantically
evaluated, indexed destructive batches conservatively refuse any simultaneous
creation or change of a surviving scene, actor or trigger, including non-script
field changes. Pure owner removal remains allowed when the remaining reference
checks pass. This guard applies even if no reviewed event was used before the
batch; it does not infer safety from an empty pre-edit reference set.

## Verification boundary

ModRetro's focused inert fixtures, which hermretro does not ship, exercised
accepted bindings, real-versus-editor defaults, compiled children, hidden
variable/resource preservation, unreviewed/changed/ambiguous exports,
unresolved or incomplete effects, and stale pre-write refusal. Fixture handler
files are read as data and never loaded. They do not certify a compiler
installation, an emulator run or runtime gameplay.
