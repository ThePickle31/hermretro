// Putting what the user sees into the Build composer (never sent): the current frame with a line to
// finish, for "Ask HermRetro" and for a check that went wrong.
import { host } from '#sdk'
import { injectBuildDraft } from '#pages/build/chat/store.js'
import { attachToBuild } from '#pages/build/composer/composer.js'
import { saveCapture } from '#shared/player/capture.js'

/** Save the frame and add it to the composer with `text` to finish; without a frame, just the text. */
async function attachFrame({ game, stored, image, text }) {
  if (!stored) {
    return
  }

  const { path, failure } = await saveCapture(game, image)

  if (path) {
    attachToBuild(stored, [{ key: path, path, name: 'this frame' }], text)
  } else {
    injectBuildDraft(stored, text)
    host.notify({ kind: 'warning', message: `The screenshot was not saved: ${failure}` })
  }
}

/** "Something's wrong" on a check: remember it as reported and start the message with the frame. */
export async function reportCheck({ bridge, game, stored, playtest, item }) {
  playtest.report(item.key, item.text)
  await attachFrame({ game, stored, image: await bridge.snap(), text: `When I tried \u201c${item.text}\u201d, ` })
}

export async function askAboutMoment({ bridge, game, stored }) {
  await attachFrame({ game, stored, image: await bridge.snap(), text: `About what ${game.title} shows here: ` })
}
