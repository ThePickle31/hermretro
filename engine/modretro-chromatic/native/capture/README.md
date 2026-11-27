# Native Chromatic capture backends

## macOS

`macos/chromatic-capture-helper` is a universal arm64/x86_64 executable for macOS 13 or later. The plugin verifies `macos/manifest.json` before spawning it with `--stdio`. Camera/microphone access uses normal macOS permissions, requested only after the user enables device capture in Connection settings. The browser is display-only.

The helper is built from ModRetro's `source/native-capture.swift` with system frameworks; it contains no FFmpeg or third-party codecs. That source and its build script are in ModRetro's source repository, which is not public; the engine ships the verified binary only. Never run a build automatically at plugin startup.

Signing differs by architecture in the helper shipped with 1.0.5: its arm64 slice has a linker-generated ad-hoc signature; its x86_64 slice is unsigned. The inspected artifact does not establish Hardened Runtime, independent App Sandbox confinement, a Developer ID publisher identity, or notarization. No exploit was demonstrated by that static inspection.

The existing checksum, consent, IPC, file and lifetime controls remain in place; they are not an OS sandbox guarantee. Full-duration hardware qualification also remains separate. See `docs/native-device-capture.md` for evidence boundaries and runtime limits.

Preview encoding and file writes run on a separate serial queue, targeting at most 60 frames per second. One newer pending sample replaces older pending samples. Each published JPEG carries its captured connection, frame ID and PTS; the server holds a file lease through its verified read. Stop invalidates pending samples and waits for in-flight work without blocking the control queue or its independent watchdog. Native callback/encode/publication timings share the helper's uptime clock; they are not a measurement of physical display latency. Status retains the actual video format observed after capture starts, separately from the advertised format list.

`--preview-pipeline-test` checks slow-encoder replacement, reconnect invalidation, file leases and Stop drainage without opening a device. It injects a fixed JPEG, so a pass does not verify the image encoder, GPU, USB capture or end-to-end latency. `--preview-codec-test` separately encodes generated pixels through the production CoreImage queue and decodes the resulting JPEG; it still does not open a device or measure physical latency.

Preview counters distinguish published encoded frames, intentionally replaced pending samples and AVFoundation's dropped-video callbacks. Source frame-ID gaps alone are not evidence of USB loss, and these counters do not replace recording statistics.


## Linux

`linux/arm64/ffmpeg` and `linux/x64/ffmpeg` are minimal static FFmpeg 8.0.3 executables with libvpx 1.15.2. hermretro does not ship them: they are built from a patched FFmpeg source that is not public. Without them, Linux device capture reports that it is unavailable; everything else, and capture on macOS, is unaffected. Where they are present, the plugin verifies the selected executable against `linux/manifest.json` before use. Its existing Node runtime owns the V4L2 child, frame pipes, WebM sink and private output files. No separate Node CLI, shell, runtime compilation or network input is used. Linux has no macOS TCC/Enable step; USB audio is explicitly unsupported in this build.

The input must be a matching Chromatic USB instance and V4L2 capture node. The adapter revalidates it before each opening and passes an opened descriptor; it never selects a default webcam. A preview producer must actually close before a recording producer starts. The recording deadline includes that handoff. JPEG/framehash tee outputs authenticate the same encoded preview packets; VP8 packet counts are separate. Source-drop counts are unknown, and timestamps are relative to each input generation.

A small carried patch uses V4L2 node-specific capabilities when the kernel supplies them, so metadata-only siblings cannot be mistaken for video capture nodes. The original FFmpeg archive is unchanged; the patch (`source/ffmpeg-v4l2-device-caps.patch` in ModRetro's source repository) records the delta.

The FFmpeg configuration disables network, GPL and nonfree components. FFmpeg remains LGPL-2.1-or-later; libvpx, musl and zlib carry their own notices in `licenses/native-capture/`. This configuration is not a patent, signing or redistribution clearance claim. ModRetro keeps the original source archives, the two build scripts, image definitions and source checksums in its source repository.

ModRetro's build scripts expect `/build` to contain the source archives, `ffmpeg-v4l2-device-caps.patch` and `SOURCE-SHA256`; run them inside their corresponding Docker image. Build products, package lists and configuration logs remain in that work directory. The recipe is provided for rebuilding; byte-for-byte reproducibility across changed build tools is not claimed. The x64 validation runs through Linux instruction translation on an ARM host, which is not native x64 hardware evidence. Neither architecture's synthetic tests establish a real USB capture result.
