// Values that come from the player frame, checked before the page uses them. The frame runs the game's
// own scripts, so whatever it posts is treated as untrusted: images must be PNG data URLs (so an <img>
// never fetches anything), colours plain #rrggbb (they reach inline styles), text is text, lists capped.

const PNG = /^data:image\/png;base64,[A-Za-z0-9+/=]+$/
const COLOR = /^#[0-9a-f]{6}$/i
const MAX_MARKS = 20
const MAX_IMAGE = 4_000_000

const text = (value, max = 300) => (typeof value === 'string' ? value.slice(0, max) : '')

/** A PNG data URL, or '' for anything else. */
export const cleanImage = value => (typeof value === 'string' && value.length <= MAX_IMAGE && PNG.test(value) ? value : '')

const cleanColors = value => (Array.isArray(value) ? value.slice(0, 4).filter(color => typeof color === 'string' && COLOR.test(color)) : null)

/** The engine's metadata: a few named strings, numbers and flags. */
function cleanMetadata(value) {
  if (!value || typeof value !== 'object') {
    return {}
  }

  return Object.fromEntries(
    Object.entries(value)
      .slice(0, 12)
      .map(([key, entry]) => [text(key, 40), Number.isFinite(entry) || typeof entry === 'boolean' ? entry : text(entry, 600)])
  )
}

/** One marked object from the frame (frame/annotate-host.js describeMarks). */
function cleanMark(mark, index) {
  const colors = cleanColors(mark?.colors)
  const original = cleanColors(mark?.original)

  return {
    n: Number.isInteger(mark?.n) && mark.n > 0 && mark.n <= MAX_MARKS ? mark.n : index + 1,
    id: text(mark?.id, 200),
    name: text(mark?.name, 120),
    role: text(mark?.role, 40),
    metadata: cleanMetadata(mark?.metadata),
    colors,
    original: colors && original?.length === colors.length ? original : colors,
    image: cleanImage(mark?.image)
  }
}

export const cleanMarks = value => (Array.isArray(value) ? value.slice(0, MAX_MARKS).map(cleanMark).filter(mark => mark.id) : [])

/** The full view's single pick with its note (FROM_FRAME.NOTE). */
export function cleanNote(data) {
  return {
    target: { name: text(data?.target?.name, 120), role: text(data?.target?.role, 40), metadata: cleanMetadata(data?.target?.metadata) },
    note: text(data?.note, 2000),
    image: cleanImage(data?.image)
  }
}
