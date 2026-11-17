// The frame's one way out: a message to the Studio page that embeds it.

/** Post to the parent page; the frame may be detached while it unloads, so failures are ignored. */
export function post(message) {
  try {
    parent.postMessage(message, '*')
  } catch {
    // the page is gone
  }
}
