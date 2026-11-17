// The prompt library.
export const SETUP_PROMPT =
  'Set up hermretro so I can create games, build ROMs, and run automated playtests. Check what is already installed and prepare the missing dependencies.'

export const DEVICE_CLI_PROMPT =
  "Install ModRetro's Chromatic device software for hermretro so I can use my physical Chromatic."

// The prompt library, in ModRetro's quickstart order. `{folder}` / `{name}` are filled from the
// inputs on the Prompts page; `src` says whether the prompt follows ModRetro's quickstart or is
// one of Hermes' own. Prompts with `hw` need a set-up Chromatic.
export const PROMPT_SECTIONS = [
  {
    id: 'plan',
    n: '01',
    title: 'Plan',
    prompts: [
      {
        id: 'plan',
        title: 'Plan a game',
        src: 'hermes',
        text: 'Use hermretro to help me plan a small Game Boy Color game before we build anything. Interview me briefly, then write the game brief, backlog and test plan into the project.'
      }
    ]
  },
  {
    id: 'create',
    n: '02',
    title: 'Create',
    prompts: [
      {
        id: 'new-game',
        title: 'Create a new game',
        src: 'modretro',
        text: 'Use hermretro to create and select a new GB Studio project at {folder}/{name}. Make a small exploration game where a gardener collects three seeds and plants them to unlock a gate.',
        defaults: { name: 'MoonGarden' },
        note: 'The parent folder must already exist.'
      },
      {
        id: 'remix',
        title: 'Remix an example',
        src: 'modretro',
        text: 'Use hermretro to create and select a Wrecklight remix at {folder}/{name}. Show me its rooms and controls, then help me turn the opening area into an abandoned research station.',
        defaults: { name: 'MyWrecklight' },
        note: 'The Wrecklight source is not bundled; the agent will ask for a local copy if needed.'
      }
    ]
  },
  {
    id: 'play',
    n: '03',
    title: 'Play',
    prompts: [
      {
        id: 'play-game',
        title: 'Play my game',
        src: 'modretro',
        text: 'Build my selected game and show it to me in the emulator beside the chat so I can play it. Show me the new build there whenever we make a change worth trying.'
      },
      {
        id: 'playtest',
        title: 'Build and playtest',
        src: 'hermes',
        text: 'Build my selected game, then run an automated playtest: boot it, walk around the first room, and show me real frames from the emulator.'
      }
    ]
  },
  {
    id: 'polish',
    n: '04',
    title: 'Polish',
    prompts: [
      {
        id: 'scene',
        title: 'Add a scene',
        src: 'modretro',
        text: 'Add a village scene to my selected project with three houses, a central fountain, and a character I can talk to. Connect it to the starting area.'
      },
      {
        id: 'artwork',
        title: 'Characters and artwork',
        src: 'modretro',
        text: "Create a small robot player sprite with idle and walking animations that fit this project's style and Game Boy hardware limits. Add it to the game and show it in a scene."
      },
      {
        id: 'palette',
        title: 'Update the palette',
        src: 'modretro',
        text: 'Give this scene a moonlit palette with cool blue shadows and warm window lights. Check readability and show the result from the emulator.'
      },
      {
        id: 'audit',
        title: 'Hardware limits audit',
        src: 'modretro',
        text: "Audit my project's backgrounds and sprites for Game Boy hardware limits. Identify problems and fix any assets that would prevent a successful build."
      }
    ]
  },
  {
    id: 'device',
    n: '05',
    title: 'On your Chromatic',
    prompts: [
      {
        id: 'stream',
        title: 'Stream to Chromatic',
        src: 'modretro',
        hw: true,
        text: 'Stream a two-minute live demo of my built ROM to the connected Chromatic so I can try its controls, video, and audio.'
      },
      {
        id: 'flash',
        title: 'Flash a cartridge',
        src: 'modretro',
        hw: true,
        text: 'Flash my built homebrew ROM to the connected Chromatic cartridge, then guide me through manual boot, gameplay, and audio checks.'
      }
    ]
  }
]

export const ALL_PROMPTS = PROMPT_SECTIONS.flatMap(section => section.prompts.map(prompt => ({ ...prompt, section })))
export const promptById = id => ALL_PROMPTS.find(prompt => prompt.id === id) ?? ALL_PROMPTS[0]
export const FLASH_PROMPT = promptById('flash').text

export const NEW_GAME_PROMPT =
  'Use hermretro to help me start a new Game Boy Color game. Ask me what I want to make, then create the project, build it and show me the first frame.'
