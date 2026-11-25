// Steps in plain words: what each tool call did, and the files it touched.
import { baseName, isAbsolute, joinPath } from '#app/paths.js'

const guideName = args => String(args?.name ?? 'a').replace(/^hermretro:/, '').replace(/[-_]/g, ' ')
const fileWords = (running, done, fallback = 'a file') => args => {
  const name = baseName(args?.path ?? args?.file_path) || fallback

  return [`${running} ${name}`, `${done} ${name}`]
}

// asset_import: art, music or sound effects, by the kinds in the call; assets when it mixes art and audio.
const AUDIO_WORDS = { music: 'music', sound: 'sound', 'music sound': 'music and sound' }
const importWords = args => {
  const kinds = [...new Set((Array.isArray(args?.assets) ? args.assets : [args]).map(asset => asset?.kind))].sort()
  const audio = kinds.filter(kind => kind === 'music' || kind === 'sound')
  const what = audio.length === 0 ? 'art' : audio.length === kinds.length ? AUDIO_WORDS[audio.join(' ')] : 'assets'

  return [`Adding ${what} to the game`, `Added ${what} to the game`]
}

// Tool → [while it runs, once it is done]. Chromatic tools go without their `chromatic_` prefix.
const STEP_WORDS = {
  project_create: ['Creating the project', 'Created the project'],
  project_create_blank: ['Creating the project', 'Created the project'],
  project_select: ['Opening the project', 'Opened the project'],
  project_inspect: ['Reading the project', 'Read the project'],
  project_inventory: ['Listing what\u2019s in the game', 'Listed what\u2019s in the game'],
  project_discover: ['Looking for the project', 'Found the project'],
  project_refresh: ['Checking the project', 'Checked the project'],
  scene_create: ['Adding a scene', 'Added a scene'],
  scene_update: ['Editing a scene', 'Edited a scene'],
  scene_apply: ['Editing the scene', 'Edited the scene'],
  scene_inspect: ['Looking at a scene', 'Looked at a scene'],
  scene_delete: ['Removing a scene', 'Removed a scene'],
  actor_create: ['Adding a character', 'Added a character'],
  actor_update: ['Editing a character', 'Edited a character'],
  actor_inspect: ['Looking at a character', 'Looked at a character'],
  actor_delete: ['Removing a character', 'Removed a character'],
  trigger_create: ['Adding a trigger', 'Added a trigger'],
  trigger_update: ['Editing a trigger', 'Edited a trigger'],
  trigger_inspect: ['Looking at a trigger', 'Looked at a trigger'],
  trigger_delete: ['Removing a trigger', 'Removed a trigger'],
  script_edit: ['Writing a script', 'Wrote a script'],
  script_inspect: ['Reading a script', 'Read a script'],
  script_transition: ['Linking two scenes', 'Linked two scenes'],
  dialogue_update: ['Writing dialogue', 'Wrote dialogue'],
  dialogue_analyze: ['Checking the dialogue fits', 'Checked the dialogue fits'],
  dialogue_preview: ['Previewing dialogue', 'Previewed dialogue'],
  asset_import: importWords,
  asset_inspect: ['Inspecting the asset', 'Inspected the asset'],
  music_compose: ['Writing music', 'Wrote music'],
  asset_update: ['Updating the art', 'Updated the art'],
  asset_delete: ['Removing art', 'Removed art'],
  sprite_edit: ['Tuning a sprite', 'Tuned a sprite'],
  sprite_inspect: ['Looking at a sprite', 'Looked at a sprite'],
  sprite_preview: ['Previewing a sprite', 'Previewed a sprite'],
  sprite_contact_sheet: ['Laying out the animation', 'Laid out the animation'],
  palette_create: ['Making a palette', 'Made a palette'],
  palette_update: ['Changing a palette', 'Changed a palette'],
  palette_assign: ['Colouring the scene', 'Coloured the scene'],
  palette_paint: ['Painting colours', 'Painted colours'],
  palette_inspect: ['Looking at the palettes', 'Looked at the palettes'],
  graphics_analyze: ['Checking the graphics limits', 'Checked the graphics limits'],
  graphics_analyze_scene: ['Checking the scene\u2019s graphics', 'Checked the scene\u2019s graphics'],
  graphics_preview_scene: ['Rendering the scene', 'Rendered the scene'],
  native_graphics_update: ['Updating the title art', 'Updated the title art'],
  collision_edit: ['Drawing walls', 'Drew walls'],
  collision_inspect: ['Checking walls', 'Checked walls'],
  variable_set: ['Setting a variable', 'Set a variable'],
  variable_inspect: ['Reading a variable', 'Read a variable'],
  variable_delete: ['Removing a variable', 'Removed a variable'],
  settings_update: ['Changing game settings', 'Changed game settings'],
  engine_field_update: ['Tuning the engine', 'Tuned the engine'],
  engine_field_inspect: ['Reading engine settings', 'Read engine settings'],
  tilemap_atlas_create: ['Making a tile set', 'Made a tile set'],
  tilemap_create: ['Building the map', 'Built the map'],
  tilemap_edit: ['Editing the map', 'Edited the map'],
  tilemap_compile: ['Compiling the map', 'Compiled the map'],
  tilemap_inspect: ['Checking the map', 'Checked the map'],
  world_dependencies: ['Tracing how scenes connect', 'Traced how scenes connect'],
  rom_build: ['Building the game', 'Built the game'],
  rom_inspect: ['Checking the ROM', 'Checked the ROM'],
  web_build: ['Building the playable copy', 'Built the playable copy'],
  web_preview: ['Getting the player ready', 'Got the player ready'],
  web_preview_close: ['Closing the player', 'Closed the player'],
  present_game: ['Handing you the game', 'Handed you the game'],
  emulator_run: ['Starting the emulator', 'Started the emulator'],
  emulator_replay: ['Replaying the playtest', 'Replayed the playtest'],
  emulator_step: ['Playing the game', 'Played the game'],
  emulator_observe: ['Looking at the screen', 'Looked at the screen'],
  emulator_inspect: ['Reading the game\u2019s memory', 'Read the game\u2019s memory'],
  emulator_audio: ['Checking game audio', 'Checked game audio'],
  emulator_debug: ['Checking the game state', 'Checked the game state'],
  emulator_checkpoint: ['Saving a checkpoint', 'Saved a checkpoint'],
  emulator_clip: ['Recording a clip', 'Recorded a clip'],
  emulator_review: ['Reviewing the playtest', 'Reviewed the playtest'],
  emulator_recording: ['Saving the recording', 'Saved the recording'],
  emulator_status: ['Checking the emulator', 'Checked the emulator'],
  emulator_close: ['Closing the emulator', 'Closed the emulator'],
  toolchain_prepare: ['Installing the toolchain', 'Installed the toolchain'],
  toolchain_doctor: ['Checking the toolchain', 'Checked the toolchain'],
  studio_device_cli: ['Setting up the Chromatic tools', 'Set up the Chromatic tools'],
  game_info: ['Writing the game card', 'Wrote the game card'],
  device: ['Checking the Chromatic', 'Checked the Chromatic'],
  device_capture: ['Opening the Chromatic feed', 'Opened the Chromatic feed'],
  play: ['Streaming to the Chromatic', 'Streamed to the Chromatic'],
  flash: ['Writing the cartridge', 'Wrote the cartridge'],
  setup: ['Setting up the Chromatic', 'Set up the Chromatic'],
  skill_view: args => [`Reading the ${guideName(args)} guide`, `Read the ${guideName(args)} guide`],
  terminal: ['Running a command', 'Ran a command'],
  execute_code: ['Running some code', 'Ran some code'],
  write_file: fileWords('Writing', 'Wrote'),
  patch: fileWords('Editing', 'Edited'),
  read_file: fileWords('Reading', 'Read'),
  search_files: ['Searching the files', 'Searched the files'],
  vision_analyze: args => {
    const name = baseName(args?.image_url) || 'an image'

    return [`Looking at ${name}`, `Looked at ${name}`]
  },
  web_search: ['Searching the web', 'Searched the web'],
  web_extract: ['Reading a web page', 'Read a web page'],
  browser_exec: ['Using the browser', 'Used the browser'],
  delegate_task: ['Handing a task to a helper', 'A helper finished a task'],
  image_generate: ['Generating an image', 'Generated an image'],
  desktop_preview: ['Opening a preview', 'Opened a preview'],
  clarify: args => {
    const count = Array.isArray(args?.questions) ? args.questions.length : 1

    return ['Asking you', `Asked you ${count === 1 ? 'a question' : `${count} questions`}`]
  }
}

// Plumbing the user does not need to see as steps.
export const HIDDEN_STEPS = new Set(['tool_describe', 'tool_search', 'todo', 'memory', 'skill_manage', 'skills_list', 'session_search', 'tool_call', 'session_status', 'build_report'])
export const BUILD_STEPS = new Set(['rom_build', 'web_build', 'web_preview', 'present_game'])

export const shortTool = name => String(name ?? '').replace(/^chromatic_/, '')

export function stepWords(tool) {
  const short = shortTool(tool.name)
  const words = STEP_WORDS[short]
  const pair = typeof words === 'function' ? words(tool.args ?? {}) : words

  if (tool.state === 'unknown') {
    return [pair?.[0] ?? 'Building', 'Build outcome unknown']
  }

  if (pair) {
    return pair
  }

  const plain = short.replace(/[_.]/g, ' ')

  return [`Using ${plain}`, `Used ${plain}`]
}

export function stepDetail(tool) {
  if (tool.state === 'failed' && tool.info?.error) {
    return tool.info.error
  }

  if (tool.progress?.message) {
    return tool.progress.message
  }

  if (shortTool(tool.name) === 'terminal' && tool.args?.command) {
    return tool.args.command.split('\n')[0]
  }

  const text = tool.summary ?? tool.preview ?? ''

  return typeof text === 'string' ? text : ''
}

function imagePath(value, root) {
  if (typeof value !== 'string' || !/\.(png|gif|jpe?g|webp)$/i.test(value)) {
    return null
  }

  return isAbsolute(value) ? value.replace(/^file:\/\//, '') : joinPath(root, value)
}

/** Paths in the order the emulator returned them. Identical screenshots can occur more than once. */
export function capturedFrames(tool, root) {
  if (tool.state !== 'done' || !shortTool(tool.name).startsWith('emulator_')) {
    return []
  }

  return (tool.info?.images ?? []).map(value => imagePath(value, root)).filter(path => path && assetKind(path) === 'Playtest frame')
}

/** The unique images a step made or looked at, for the asset viewer. */
export function stepImages(tool, root) {
  const found = []
  const add = value => {
    const path = imagePath(value, root)

    if (path && !found.includes(path)) {
      found.push(path)
    }
  }

  add(tool.image)

  for (const image of tool.info?.images ?? []) {
    add(image)
  }

  add(tool.args?.image_url)
  add(tool.info?.assetPath ?? tool.args?.assetPath)

  for (const path of tool.info?.assetPaths ?? []) {
    add(path)
  }

  add(tool.info?.outputPath ?? tool.args?.outputPath)

  return tool.state === 'failed' ? [] : found
}

export function assetKind(path) {
  const value = String(path ?? '')

  if (/[\\/]assets[\\/]sprites[\\/]/.test(value)) {
    return 'Sprite'
  }

  if (/[\\/]assets[\\/]backgrounds[\\/]/.test(value)) {
    return 'Background'
  }

  if (/[\\/]assets[\\/](ui|fonts)[\\/]/.test(value)) {
    return 'Interface'
  }

  if (/[\\/](playtests|frames)[\\/]/.test(value)) {
    return 'Playtest frame'
  }

  return 'Image'
}
