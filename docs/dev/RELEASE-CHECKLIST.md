# Release checklist

CI proves the code on Linux, Apple Silicon and Intel macOS runners, including the real engine. What it cannot
prove is the desktop app on a real machine: the Git dialog, the page's own install and update, and a first game.
Before a stable release (and after any change to setup, the broker or `backend/system/host.py`), run this on an
Apple Silicon MacBook (the native build of Hermes, not under Rosetta, launched from Finder or the Dock) and on a
Linux x64 desktop. An Intel Mac is welcome but not required; say so when it was not run.

## On the machine

Start from the newest Hermes Desktop and a Hermes home with no hermretro, no `hermretro` profile and no model
credentials (a fresh user account, or `HERMES_HOME` pointed at an empty folder). Keep a clock running from each
click; the times go in the result.

1. **Install from Git.** Open `hermes://plugin/install?repo=ThePickle31/hermretro&enable=1`: the Install from Git
   dialog opens with the repository filled in. Press **Review repository**, then **Install**. It installs without
   asking about scanner findings, and **HermRetro** appears in the sidebar. (Once per release, also install by
   typing the URL into Capabilities → Plugins → **Install from Git** in another empty home.)
2. **Review, then install once.** Open HermRetro. The download list shows every component with version, source
   and size, the Node.js line says it comes from Hermes, and nothing downloads until **Download and install** is
   pressed. Press it. Progress moves (it may sit on one percentage for minutes while GB Studio builds), the
   `hermretro` profile is created, and the page moves on by itself. Note the time from the click to the hardware
   question.
3. **No credentials.** Choose **Start making games**, type an idea, and press **Continue in Build**. Setup finishes
   and Build shows the idea in New Game without sending it. Reload and check that the draft is still there.
   Verify the provider notice and settings link when no model is available. The Emulator page plays the demo with
   no provider; return to Build, then sign in a provider for the `hermretro` profile.
4. **First ROM.** Send the saved draft from New Game. The chat opens in the `hermretro` profile, the steps get
   words (no raw tool names), a build finishes, and the game opens in the emulator beside the chat. Note the time
   from sending to a playable ROM. This is the real readiness check: Setup going green is not enough.
5. Play it with the keyboard for a minute: picture, sound, input, no stutter. Pause, resume, open it full size.
6. Ask for a change ("make the player faster"). It rebuilds, the emulator reloads the new build, and the build
   history lists both builds; Restore the first one.
7. Games page: the game is there with its card; "Open games folder" opens Finder (or the file manager) at
   `~/.hermes/hermretro/games`.
8. Quit and reopen the app; the game, the chat and the build history are still there, and reopening the page
   does not download anything again.
9. After five idle minutes with the page closed (Activity Monitor, or `ps` on Linux): one `python` broker
   process, and no leftover `node` workers after 30 minutes.
10. **Update in the app.** In a home that has the previous release installed (step 1 with the last tag), let the
    **Update ready** chip appear (or press Refresh in the page header), then press **Update now**. It finishes
    without a restart: the page reloads itself, the chip is gone, the Setup page's hermretro row shows the new
    version, and the game and its chat are still there. If it says **Restart to finish** instead, write down why.
    Separately, `hermes plugins update hermretro` from a terminal in the profile it was installed into also
    works, followed by quitting and reopening the app.
11. **Recovery.** Reload while tools download and check that progress resumes. Press **Cancel**, then **Install
    again** once the installer has stopped. Separately, turn the network off mid-install: the page explains the
    failure and **Try again** keeps the finished parts. Delete the throwaway `hermretro` profile: the
    Build page offers **Repair**, which brings it back. **Remove downloaded tools** (Setup), then install again:
    it works, and the game is untouched.
12. With a Chromatic (optional, hardware tools turned on): device status, then play on the device.

Write the result in the draft release's notes before publishing it: system and chip, Hermes version, pass or what
failed per step, and the times from steps 2 and 4.

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

Before a release, the checks can also run on a MacBook over ssh: a fresh clone of the commit there and
`python3 tools/check.py` (CI's macOS runners cover it otherwise).

## Then release

`python tools/release.py`, run again after each step it stops at: the version pull request when `dev` still says the
last released version, CI on `dev`'s head, `main` fast-forwarded, the tag, and the draft with generated notes. Read
the draft, then `python tools/release.py --publish vX.Y.Z`. `--rc` makes a release candidate (`main` stays).
