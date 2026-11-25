"""Build instructions shared by the studio prompt, per-game context, tool results and Desktop fallback."""

# A build is a checkpoint: the agent keeps authoring until everything agreed with the user is in the game.
CHECKPOINT = (
    "A build is a checkpoint, not a hand-off: keep authoring until everything agreed for this build is in the game; "
    "only then "
)
# Handing the game to the user, in order, once everything agreed is built; the prompt section's steps end with it too.
PRESENT = "show it with chromatic_present_game in the hermretro emulator"
DELIVER = (
    "playtest it yourself using chromatic_emulator_run and chromatic_emulator_step; fill in its game card with chromatic_game_info; "
    + PRESENT
    + "; end the turn with chromatic_build_report."
)

AUTHOR_AND_DELIVER = (
    "author everything agreed with the chromatic_* tools, building with chromatic_rom_build as you go "
    "(a build is a checkpoint, not a hand-off); once all of it is in, " + DELIVER
)
GAME_STEPS = (
    "For a new game, use the chosen mode. Build it: ask a few questions, get approval of a short scope list, "
    "then create the project. Plan first: use hermretro:game-planning to interview the user, create the project "
    "to hold the draft, and wait for explicit brief approval before authoring or building. For either mode, "
    + AUTHOR_AND_DELIVER
)
EDIT_GAME = (
    "For a game brought in for editing or already presented, make the requested changes, build and playtest them, "
    "update the game card as needed, then " + PRESENT + " and call chromatic_build_report."
)
# What keeps the game the user's real, buildable project.
GAME_RULES = (
    "Read and change the game's .gbsres and .gbsproj files only through the chromatic_* tools, never yourself, and "
    "never open another game's project. Draw art as PNG files and bring it and audio in with chromatic_asset_import; "
    "never write anything under build/, and never build, export or playtest the game with other programs. Run helper "
    "code from a script file, not python -c or a heredoc. When no tool can do what the game needs, tell the user what "
    "is missing. hermretro owns README.md, .hermretro/ and game.json's id, gameVersion and rom. Do not create or "
    "change skills unless the user asks."
)

# The build card's guidance, for the Build conversation's context and the prompt section.
BUILD_REPORT_GUIDANCE = (
    "At the end of a turn that changed or built the game (after building, your own playtest and presenting), "
    "call chromatic_build_report once (title, summary, changes with asset paths, tested/untested, notes, up to 4 "
    "suggestions; for a game with docs/game/TEST-PLAN.md also every open check's result on this ROM, as "
    "chromatic_playtest last replayed the checks you bound to recordings after the rebuild, and the difficulty "
    "from your own run; finishRun names the recording of your one run from power-on), then keep the "
    "written reply to one or two short sentences."
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

BUILD_START = AGREE_A_LIST + " " + BUILD_THE_LIST + " Then " + DELIVER
PLAN_START = (
    "Plan it first: load hermretro:game-planning, interview the user briefly, create the project, write "
    "the game brief, backlog and test plan into it, and wait for the user to approve the brief before "
    "authoring or building. Record the approval in the brief. " + BUILD_THE_BRIEF + " Then " + DELIVER
)
PLAN_CONTINUE = (
    "Finish the short interview, then create the project to hold the draft brief, backlog and test plan "
    "(hermretro:game-planning). Wait for explicit brief approval before authoring or building and record "
    "the approval in the brief. " + BUILD_THE_BRIEF + " Then " + DELIVER
)
PLAN_BOUND = (
    "Before authoring or building, check docs/game/GAME-BRIEF.md. If the brief is missing or still awaiting "
    "approval, use hermretro:game-planning to finish or revise it and wait for the user's explicit approval. "
    "Record that approval in the brief before starting the build. " + BUILD_THE_BRIEF + " Then " + DELIVER
)
BUILD_CONTINUE = (
    "Until the user approves the list of what you will make, create nothing and change the list as "
    "they ask. " + BUILD_THE_LIST + " Then " + DELIVER
)

BUILD_BOUND = (
    "Use the approved scope list in docs/game/FIRST-BUILD.md to finish the first build. If the list is missing, "
    "recover the approved list from the conversation or ask for approval, then save it. Build every agreed item "
    "and check it against the list before presenting. Then " + DELIVER
)

SYSTEM_PROMPT_SECTION = (
    "hermretro's chromatic_* tools make native GB Studio games for the ModRetro Chromatic. "
    # Hermes lists the plugin's skills itself; after a compaction the summary no longer holds what they said.
    "Load the task's hermretro skill with skill_view, and again after a context compaction. "
    "Use one project per chat. Omit destinationPath unless the user names another folder. "
    + GAME_STEPS
    + " "
    + EDIT_GAME
    + " "
    "Nothing opens for the user after a build. After chromatic_build_report, reply in one or two short sentences. "
    + GAME_RULES
    + " Hardware tools stay off until the user enables them in Settings > Plugins > hermretro."
)
