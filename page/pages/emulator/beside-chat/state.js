// State of the emulator tabs beside the chat.
import { atom } from '#sdk'
import { ID } from '#app/ids.js'

export const ALWAYS_VISIBLE = atom(true)

// Bumped after every finished build or turn, so an open emulator checks its ROM at once.
export const BUILD_TICK = atom(0)
// Game id → the latest presentation the tab should show: { seq, note, t }.
export const PRESENTED = atom({})

// Game id → close() of its open side tab.
export const sideTabs = new Map()
// Presentations already acted on ('<game id>:<presentedAt>'), so the fallback never repeats one.
export const presentationsSeen = new Set()
export const sideSurface = id => `side:${id}`
export const sideKey = id => `${ID}.emulator.${id}`
