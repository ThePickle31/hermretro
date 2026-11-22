// The app's own background colour behind an element (the attract level's sky, the player frame's page).

/** The page's own background under `el` (the first ancestor that paints one): { css, rgb: [r, g, b] 0-255 }.
 *  Browsers report it as rgb()/rgba() or, for a color-mix() theme, as color(srgb r g b) with 0-1 channels. */
export function backgroundOf(el, getStyle) {
  for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
    const css = getStyle(node).backgroundColor, nums = (css.match(/[\d.]+/g) || []).map(Number)
    const unit = css.startsWith('color(') ? 255 : 1
    if (nums.length >= 3 && (nums.length < 4 || nums[3] > 0.5)) return { css, rgb: nums.slice(0, 3).map(v => v * unit) }
  }
  return { css: 'rgb(16 18 24)', rgb: [16, 18, 24] }
}
