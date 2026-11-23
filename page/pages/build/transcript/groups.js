// A turn's steps in five plain groups.
import { shortTool } from './step-words.js'

const PLAN_STEPS = new Set(['skill_view', 'project_select', 'project_inspect', 'project_inventory', 'project_discover', 'project_refresh', 'toolchain_doctor', 'toolchain_prepare', 'web_search', 'web_extract', 'clarify', 'read_file', 'search_files'])
// The steps that make or choose the conversation's project (rootOf).
const PROJECT_STEPS = new Set(['project_create', 'project_create_blank', 'project_select'])
// Steps that are only a glance: left out of the simple view unless they show a picture.
export const MINOR_STEPS = /^(skill_view|read_file|search_files|project_inventory|project_inspect|toolchain_doctor|world_dependencies|.+_inspect|.+_status|.+_analyze)$/
// Always the same groups, in this order: [kind, while it runs, once done, done without a picture].
const WORK_GROUPS = [
  ['plan', 'Planning', 'Planned it'],
  ['art', 'Drawing the art', 'Drew the art', 'Worked on the art'],
  ['level', 'Setting up the level', 'Set up the level'],
  ['build', 'Building it', 'Built it'],
  ['test', 'Play-testing it', 'Play-tested it'],
  ['other', 'Working on it', 'Worked on it']
]
export const GROUP_MIN_STEPS = 8
const ART_HINT = /\.(png|gif|aseprite)\b|art-src|sprite|background|cover|palette/i

function phaseOf(tool) {
  const short = shortTool(tool.name)

  if (PLAN_STEPS.has(short)) {
    return 'plan'
  }

  if (/^(sprite_|asset_|palette_|graphics_|native_graphics_|tilemap_|image_generate$|game_info$)/.test(short)) {
    return 'art'
  }

  if (/^(project_create|scene_|actor_|trigger_|script_|dialogue_|collision_|variable_|settings_|engine_field_|world_dependencies$)/.test(short)) {
    return 'level'
  }

  if (/^(rom_|web_build|web_preview|present_game$)/.test(short)) {
    return 'build'
  }

  if (/^emulator_/.test(short)) {
    return 'test'
  }

  // A script or file that draws art is art; other commands and edits join what they were helping with.
  if (/^(terminal|execute_code|write_file|patch)$/.test(short) && ART_HINT.test(JSON.stringify(tool.args ?? {}))) {
    return 'art'
  }

  return null
}

/** A turn's entries in the fixed groups (in WORK_GROUPS order). A step that belongs to none (a command,
 *  a file edit), a note or an answer joins the group of the step before it; ones before any step join
 *  the first group. Also says which group was touched last (the live one while it works). */
export function workGroups(entries) {
  const groups = new Map()
  const before = []
  let current = null

  for (const entry of entries) {
    const kind = entry.type === 'step' ? phaseOf(entry.tool) : null

    if (kind) {
      current = kind

      if (!groups.has(kind)) {
        groups.set(kind, [])
      }

      groups.get(kind).push(...before.splice(0), entry)
    } else if (current) {
      groups.get(current).push(entry)
    } else {
      before.push(entry)
    }
  }

  if (before.length) {
    groups.set('other', before)
    current = current ?? 'other'
  }

  return {
    groups: WORK_GROUPS.filter(([kind]) => groups.has(kind)).map(([kind]) => ({ kind, entries: groups.get(kind) })),
    last: current
  }
}

export function groupTitle(group, live, made) {
  const words = WORK_GROUPS.find(([kind]) => kind === group.kind) ?? WORK_GROUPS[WORK_GROUPS.length - 1]

  return live ? words[1] : group.kind === 'art' && !made && words[3] ? words[3] : words[2]
}

/** The project folder a conversation works in: the game's, or the one its first project step made or chose (not
 *  another step's, such as the toolchain check's runtime folder). */
export function rootOf(game, items) {
  if (game?.projectRoot) {
    return game.projectRoot
  }

  for (const item of items) {
    for (const tool of item.kind === 'tools' ? item.tools : []) {
      if (PROJECT_STEPS.has(shortTool(tool.name)) && tool.info?.projectRoot) {
        return tool.info.projectRoot
      }
    }
  }

  return null
}
