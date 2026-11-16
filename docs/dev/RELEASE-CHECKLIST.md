# Release checklist

CI proves the code on Linux, Apple Silicon and Intel macOS runners, including the real engine. What it cannot
prove is the desktop app on a real machine. Before a stable release (and after any change to setup, the
broker or `adapter/host_os.py`), run this on a MacBook, and on Linux when the release touched the page.

## On the machine

1. Update Hermes Desktop to the newest version, then install or update hermretro (`hermes plugins update
   hermretro`, or Rescan in Capabilities > Plugins). The install asks no questions about scanner findings.
2. Open the hermretro page. Setup lists the downloads; run the install. It finishes, and Setup shows every step
   green. Note the time.
3. Make a game from an idea on Home. The Build page shows the chat, the steps get words (no raw tool names), a
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

## Then release

The release steps are in the agent guide ("Releases").
