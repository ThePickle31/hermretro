# Release checklist

CI proves the code on Linux, Apple Silicon and Intel macOS runners, including the real engine. What it cannot
prove is the desktop app on a real machine. Before a stable release (and after any change to setup, the
broker or `backend/system/host.py`), run this on a MacBook and on a Linux desktop.

## On the machine

1. Update Hermes Desktop to the newest version, then install or update hermretro (`hermes plugins update
   hermretro` in the profile it was installed into, or Rescan in Capabilities > Plugins). The install asks no
   questions about scanner findings. After an update, the page asks for a restart: quit and reopen the app,
   and the message is gone.
2. Open the hermretro page. Setup lists the downloads; run the install. It finishes, and Setup shows every step
   green. Note the time.
3. Make a game from an idea on Build's New Game. The Build page shows the chat, the steps get words (no raw tool names), a
   build finishes, and the game opens in the emulator beside the chat.
4. Play it with the keyboard for a minute: picture, sound, input, no stutter. Pause, resume, open it full size.
5. Ask for a change ("make the player faster"). It rebuilds, the emulator reloads the new build, and the build
   history lists both builds; Restore the first one.
6. Games page: the game is there with its card; "Open games folder" opens Finder at `~/.hermes/hermretro/games`.
7. Quit and reopen the app; the game, the chat and the build history are still there.
8. In Activity Monitor, after five idle minutes with the page closed: one `python` broker process, and no
   leftover `node` workers after 30 minutes.
9. Remove downloaded tools (Setup), then install again: it works, and the game is untouched.
10. With a Chromatic (optional, hardware tools turned on): device status, then play on the device.

Write the result (system, Hermes version, pass or what failed) in the release pull request.

## Updating from the last release

CI proves that the release users have now updates to the candidate: `python tools/ci/clean_install_check.py
--update-from` installs the newest `v*` tag on `origin/main` into a throwaway Hermes home, uses it (studio profile,
a library game with a thumbnail, a New Game chat, a running broker), then runs `hermes plugins update hermretro`
and checks the update asks nothing, the new code registers only in `hermretro`, reads the library back, and
replaces the old broker when its code changed (keeps it when not). It works from a release in either layout
(`adapter/` before the reorganization, `backend/` after; `LAYOUTS` in `tools/ci/update_check.py`). That update from
the newest release runs on every CI run. A pull request that deletes or moves a file, or changes the install,
registration, broker, update paths or ignore rules (`UPGRADE` in `tools/ci/changes.py`), also updates from the
checkout's `dev` parent (`--update-from HEAD^1`, the tested merge commit's first parent); other pull requests skip
that second update. Nothing to edit when releasing: once the new tag is on `main`, every later run updates from it. To try an older starting point, pass it: `--update-from v0.0.4`. A change that moves where user state
lives (`backend/system/paths.py`) or what the broker answers to `hello` must keep this check green, or migrate.

Before a release, `python tools/retrodev mac` runs the checks on the MacBook when one is set up
(`retrodev config set mac_host <host>`; asleep or unset, CI's macOS runners cover it). Once `release publish` has
made the draft, `python tools/retrodev release verify <version>` checks the notes and the tag (the update check from
the previous stable release that publish ran on the same commit counts); `--publish` then publishes it.

## Then release

The release rules are in the agent guide ("Releases"); the commands are `python tools/retrodev release run` (the
version pull request only when `dev` does not say the version yet, then publish and report the verified URL;
`--draft` stops at the draft), or its steps one at a time, `release
prepare`, `release publish`, `release verify` and `release next` (`tools/retrodev/README.md`, "Releases").
After reporting publication, run the printed `release next` command separately to prepare `dev`, or use
`release run --with-next` to wait for that work inline.
