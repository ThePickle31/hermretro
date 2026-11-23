"""Build instructions shared by the studio prompt, per-game context, tool results and Desktop fallback."""

# A build is a checkpoint: the agent keeps authoring until everything agreed with the user is in the game.
CHECKPOINT = (
    "A build is a checkpoint, not a hand-off: keep authoring until everything agreed with the user is in the game; "
    "only then "
)
# Handing the game to the user, in order, once everything agreed is built; the prompt section's steps end with it too.
PRESENT = "show it with chromatic_present_game in the hermretro emulator"
DELIVER = (
    "playtest it yourself with the chromatic_emulator_* tools; fill in its game card with chromatic_game_info; "
    + PRESENT
    + "; end the turn with chromatic_build_report."
)

GAME_STEPS = (
    "Make a game in this order: agree what to make with the user (a few quick questions, then a short list of what "
    "you will make that they change until they approve it; or with hermretro:game-planning a brief, kept in the new "
    "project, that they approve); create the project; author everything agreed with the chromatic_* tools, building "
    "with chromatic_rom_build as you go (a build is a checkpoint, not a hand-off); once all of it is in, " + DELIVER
)
# What keeps the game the user's real, buildable project.
GAME_RULES = (
    "Change the game only through the chromatic_* tools: draw art as PNG files and bring it in with "
    "chromatic_asset_import, but never write .gbsres or .gbsproj files or anything under build/ yourself, and never "
    "build, export or playtest the game with other programs. When no tool can do what the game needs, tell the "
    "user what is missing. Do not create or change skills unless the user asks."
)

# The build card's guidance, for the Build conversation's context and the prompt section.
BUILD_REPORT_GUIDANCE = (
    "At the end of a turn that changed or built the game (after building, your own playtest and presenting), "
    "call chromatic_build_report once (title, summary, changes with asset paths, tested/untested, notes, up to 4 "
    "suggestions), then keep the written reply to one or two short sentences."
)

SHOW_ART_CONTEXT = (
    "To show the user a game's art (a sprite, background or cover), put the real file on its own line as "
    "MEDIA:<absolute path>, e.g. its assets/sprites/<name>.png: the Build page draws it in the game's colours, "
    "animates a sprite and opens it in its viewer (frames, palette, scenes, versions) on a click. Do not draw a "
    "preview or contact sheet to show existing art; make one only when the user asks for a picture that "
    "does not exist yet."
)

# Build it: what the first build holds is agreed as a list the user approves, then all of it is built before the game
# is presented.
AGREE_A_LIST = (
    "Ask the user a few quick questions in one short message, offering sensible defaults. Once they have answered, "
    "reply with a short list of what you will make (concept, controls, core loop, rooms or levels, characters, how "
    "to win and lose, art and colours, what is left out) and end your turn: change the list whenever the user asks, "
    "and create nothing until they approve it."
)
BUILD_THE_LIST = (
    "Once the user approves the list, create the project, save the approved list in it as "
    "docs/game/FIRST-BUILD.md and build all of it in one go. Before presenting, check every item against the build: "
    "keep building while any is missing, and name in the build report only an item no tool can make."
)
# Plan first: once the brief is approved, the same one full build.
BUILD_THE_BRIEF = (
    "Once the user approves the brief, build everything in its scope in one go, then check the test plan against "
    "the build before presenting."
)

BUILD_START = AGREE_A_LIST + " " + BUILD_THE_LIST + " Then " + PRESENT + "."
PLAN_START = (
    "Plan it first: load hermretro:game-planning, interview the user briefly, create the project, write "
    "the game brief, backlog and test plan into it, and wait for the user to approve the brief before "
    "authoring anything. " + BUILD_THE_BRIEF
)
PLAN_CONTINUE = (
    "If its project does not exist yet, create it once the user is ready. Author nothing until the "
    "user has approved the game brief (hermretro:game-planning). " + BUILD_THE_BRIEF
)
BUILD_CONTINUE = (
    "Until the user approves the list of what you will make, create nothing and change the list as "
    "they ask. " + BUILD_THE_LIST
)

SYSTEM_PROMPT_SECTION = (
    "hermretro is installed: tools named chromatic_* build real Game Boy / Game Boy Color games "
    "(native GB Studio projects) for the ModRetro Chromatic. For any work on such a game, first load the matching "
    "skill with skill_view: "
    "hermretro:setup (any setup or repair), hermretro:game-planning, hermretro:authoring, "
    "hermretro:pixel-art, hermretro:rom-debugging (build and emulator testing), "
    "hermretro:deployment (physical Chromatic). Call chromatic_* tools directly, never from execute_code. "
    "One conversation works on one project folder; use a new chat for a different project. "
    "New games go in the hermretro games folder: leave out destinationPath unless the user names another "
    "folder. " + GAME_STEPS + " "
    "Nothing opens for the user after a build; chromatic_present_game shows the game in the hermretro emulator. "
    "After chromatic_build_report, keep the written reply to one or two short sentences. "
    + GAME_RULES
    + " Hardware tools stay off until the user enables them in Settings > Plugins > hermretro."
)
