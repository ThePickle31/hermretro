# Third-party notices

The MIT licence in `LICENSE` covers the hermretro backend, desktop page, skills and tooling in this
repository. It does not cover the bundled engine under `engine/modretro-chromatic/` or the components inside
it, which keep their own licences, listed below.

hermretro bundles one third-party package under `engine/modretro-chromatic/`, with one small change (below).
Every file in it is recorded with size, mode and SHA-256 in
`engine/pins/1.0.34/manifest.json`, and the plugin refuses to start an engine that does not
match that record.

**Change made by hermretro** (allowed by the engine's MIT licence; recorded as `local_patches` in the
manifest): in `dist/server.js` and `dist/device-capture/linux-helper.js`, the path ffmpeg uses to read the
Chromatic's video during Linux hardware capture is `/dev/fd/6` instead of the equivalent per-process path
under the proc filesystem. On Linux `/dev/fd` is a link to that same directory, so ffmpeg opens the same
file. The original path made Hermes's install-time security scan ask for confirmation on every install.
Nothing else in the engine differs from ModRetro's 1.0.34.

**Left out by hermretro:** the engine's two FFmpeg builds for Linux hardware capture
(`native/capture/linux/x64/ffmpeg` and `native/capture/linux/arm64/ffmpeg`). They are LGPL-2.1-or-later and
built from a patched FFmpeg source that is not public, so hermretro cannot meet the LGPL's source obligation
and does not distribute them. Their manifest, provenance record and licence texts stay in place; without the
binaries, capturing a real Chromatic's video on Linux reports itself unavailable. Nothing else uses FFmpeg.

## ModRetro Chromatic Plugin engine 1.0.34

- Engine code (`dist/`, `scripts/`, documentation, examples, skills): MIT, Copyright (c) 2026 Eric Provencher.
  Licence text: `engine/modretro-chromatic/LICENSE`.
- Its own third-party notices: `engine/modretro-chromatic/THIRD_PARTY_NOTICES.md` and
  `engine/modretro-chromatic/licenses/`. These cover the GBVM runtime (MIT), GBDK (GPL-2.0 with linking
  exception), bundled JavaScript dependencies, and the Linux capture components (FFmpeg LGPL-2.1-or-later,
  libvpx BSD-3-Clause, musl, zlib, GCC runtime; the binaries themselves are left out, see above).
- hermretro's skills (`skills/`) are adapted from the engine's skills and documentation (MIT, Copyright (c)
  2026 Eric Provencher), edited for Hermes.

Its Node dependencies are installed from the engine's pinned lock file. Known advisories in them, and why each is
accepted until an engine update, are listed in `.github/SECURITY.md`.

## ModRetro Chromatic CLI 1.2.1 (proprietary, not bundled)

hermretro does not contain ModRetro's closed-source Chromatic CLI executables, its streaming FPGA image or its
embedded Gowin USB driver installer. They are **not** MIT-licensed. Only when the user sets up hardware support,
and after they accept ModRetro's terms (https://modretro.com/eula), hermretro downloads the package for their
platform from ModRetro's official npm releases (`@modretro/chromatic-cli-*`), checks it against the SHA-256
pinned in `engine/modretro-chromatic/third-party/chromatic-cli/PROVENANCE.json`, and unpacks it unchanged
in hermretro's folder in the Hermes home on that machine (`~/.hermes/hermretro/.cache/`).

`engine/modretro-chromatic/third-party/chromatic-cli/` holds only the engine's notice, provenance record and
SBOM for that package (`NOTICE.md`, `PROVENANCE.json`, `SBOM.json`). The redistribution permission described in
`NOTICE.md` was granted to the official ModRetro Chromatic Plugin for Codex, not to hermretro, which is why
hermretro downloads the binaries instead of shipping them.

## Installed separately, not bundled

The engine's setup downloads these from their official sources when the user asks for it: GB Studio CLI 4.3.2,
GBDK 4.5.0, PyBoy 2.7.0 (LGPL-3.0-only), Pillow, a managed Python and, optionally, the GB Studio desktop editor.

## Trademarks

ModRetro and Chromatic are trademarks of their owner. hermretro is an independent plugin and is not made
or endorsed by ModRetro, OpenAI or Nous Research.
