# Security

Please report security problems privately through GitHub's **Report a vulnerability** button on this
repository's Security tab (private vulnerability reporting), not in a public issue. Include what you found, how to
reproduce it and which version or commit you used. You will get an answer within a week.

hermretro runs a background process (the broker) on the user's machine, downloads pinned tools, can drive a
connected ModRetro Chromatic when the user turns hardware tools on, and serves the game player on a loopback port.
Reports about any of these are welcome. Only the latest release is supported.

## Known advisories in the vendored engine

The engine (`engine/modretro-chromatic/`) is ModRetro's release with the maintainer's changes (`engine/CHANGES.md`),
verified by hash, and its
Node dependencies are installed from its own pinned lock file. We cannot bump them without an engine update, so
GitHub's alerts for them stay open as accepted risks until then, and Dependabot opens no pull requests for that
folder.

- **zod 3.25.76, GHSA-mrhx-c7xc-m3w5** (fixed in 4.6.6): validating an oversized constrained collection can
  exhaust memory. The engine validates tool arguments with zod; its only input is the local agent's tool calls,
  sent as the same user over a private socket. The worst case is one engine worker running out of memory, which
  the broker replaces. Accepted until an engine update brings zod 4.
