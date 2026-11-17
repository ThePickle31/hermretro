// Files attached to a Build message: { path, name, key?, image?, detail? }. `image` is a small picture
// for the chip (a close-up of an annotated object); `detail` replaces the plain "About <path>:" line
// HermRetro reads ahead of the message.

/** Attachments are told apart by `key` (several marks share one frame), else by path. */
export const attachmentKey = item => item.key ?? item.path

/** `current` plus every attachment in `more` it does not hold yet. */
export function mergeAttachments(current, more) {
  const known = new Set(current.map(attachmentKey))

  return [...current, ...more.filter(item => !known.has(attachmentKey(item)))]
}

/** The line HermRetro reads for one attachment, ahead of the message. */
export const attachmentLine = item => item.detail ?? `About ${item.path}:`
