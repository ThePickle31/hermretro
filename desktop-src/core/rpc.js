// Every backend RPC the page calls (`plugin.hermretro.<name>`), in step with docs/dev/CONTRACT.md.
import { ID } from './ids.js'

export const RPC_STATUS = `plugin.${ID}.status`
export const RPC_DOCTOR = `plugin.${ID}.doctor`
export const RPC_STUDIO_PROFILE = `plugin.${ID}.studio_profile`
export const RPC_INSTALL = `plugin.${ID}.install`
export const RPC_REMOVE_TOOLS = `plugin.${ID}.remove_tools`
export const RPC_GAMES = `plugin.${ID}.games`
export const RPC_GAME_THUMB = `plugin.${ID}.game_thumb`
export const RPC_PLAYER = `plugin.${ID}.player`
export const RPC_CAPTURES = `plugin.${ID}.captures`
export const RPC_CAPTURE_IMAGE = `plugin.${ID}.capture_image`
export const RPC_PRESENTATIONS = `plugin.${ID}.presentations`
export const RPC_BUILD = `plugin.${ID}.build`
export const RPC_ASSET = `plugin.${ID}.asset`

//
// One window for every picture on the Build page. The picture comes first (zoom, tile grid); the
// kind of art picks the views (a cover: Image · In game; a sprite: Animation · Sheet · In game; a
// background: Image · In game); a side panel has Details and Change (ask HermRetro, optionally about
// one area); every kept version of the file sits in a strip along the bottom.
export const RPC_ASSET_INFO = `plugin.${ID}.asset_info`
export const RPC_ASSET_RESTORE = `plugin.${ID}.asset_restore`
export const RPC_BUILDS = `plugin.${ID}.builds`
export const RPC_BUILD_RESTORE = `plugin.${ID}.build_restore`
export const RPC_ASSETS = `plugin.${ID}.assets`
