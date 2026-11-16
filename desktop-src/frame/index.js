// Runs first in the player frame, before GB Studio's player and the engine's modules (inlined at the
// top of <head> by adapter/player_server.py, which fills the two placeholders below). Built by
// tools/bundle.mjs into player/frame-shim.js.
import { installAnnotateHost } from './annotate-host.js'
import { listenForCommands } from './commands.js'
import { watchState } from './engine.js'
import { forwardLogs, installFetch, installStorage } from './sandbox.js'
import { installStyles, setView } from './view.js'

const params = new URLSearchParams(location.search)

forwardLogs()
installStorage(params, '__DEFAULT_COLOR__', '__COLOR_KEY__')
installFetch()
setView(params.get('view') || 'full')
installStyles()
listenForCommands(installAnnotateHost())
watchState()
