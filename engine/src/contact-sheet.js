import { createHash } from "node:crypto";
import { PNG } from "pngjs";
import { chromaticDisplayColor } from "./palettes.js";
export const GAME_BOY_FRAME_WIDTH = 160;
export const GAME_BOY_FRAME_HEIGHT = 144;
export const MAX_CONTACT_SHEET_FRAMES = 64;
export const MAX_CONTACT_SHEET_MAGNIFICATION = 6;
export const MAX_CONTACT_SHEET_FRAME_BYTES = 2 * 1024 * 1024;
export const MAX_CONTACT_SHEET_LABEL_LENGTH = 160;
export const MAX_CONTACT_SHEET_PNG_BYTES = 8 * 1024 * 1024;
const MAX_CANVAS_DIMENSION = 8_192;
const MAX_CANVAS_PIXELS = 32_000_000;
const GUTTER = 12;
const PADDING = 8;
const FONT_WIDTH = 5;
const FONT_HEIGHT = 7;
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const CANVAS_COLOR = [13, 17, 23, 255];
const CARD_COLOR = [22, 27, 34, 255];
const BORDER_COLOR = [48, 54, 61, 255];
const PRIMARY_TEXT = [230, 237, 243, 255];
const SECONDARY_TEXT = [139, 148, 158, 255];
const FRAME_ACCENT = [88, 166, 255, 255];
const CHANGE_ACCENT = [255, 184, 76, 255];
/** Compact, dependency-free 5-by-7 glyphs stored as seven five-bit rows. */
const GLYPHS = {
  " ": [0, 0, 0, 0, 0, 0, 0],
  "!": [4, 4, 4, 4, 4, 0, 4],
  '"': [10, 10, 10, 0, 0, 0, 0],
  "#": [10, 10, 31, 10, 31, 10, 10],
  $: [4, 15, 20, 14, 5, 30, 4],
  "%": [24, 25, 2, 4, 8, 19, 3],
  "&": [12, 18, 20, 8, 21, 18, 13],
  "'": [4, 4, 8, 0, 0, 0, 0],
  "(": [2, 4, 8, 8, 8, 4, 2],
  ")": [8, 4, 2, 2, 2, 4, 8],
  "*": [0, 4, 21, 14, 21, 4, 0],
  "+": [0, 4, 4, 31, 4, 4, 0],
  ",": [0, 0, 0, 0, 4, 4, 8],
  "-": [0, 0, 0, 31, 0, 0, 0],
  ".": [0, 0, 0, 0, 0, 12, 12],
  "/": [1, 2, 4, 8, 16, 0, 0],
  0: [14, 17, 19, 21, 25, 17, 14],
  1: [4, 12, 4, 4, 4, 4, 14],
  2: [14, 17, 1, 2, 4, 8, 31],
  3: [30, 1, 1, 14, 1, 1, 30],
  4: [2, 6, 10, 18, 31, 2, 2],
  5: [31, 16, 30, 1, 1, 17, 14],
  6: [6, 8, 16, 30, 17, 17, 14],
  7: [31, 1, 2, 4, 8, 8, 8],
  8: [14, 17, 17, 14, 17, 17, 14],
  9: [14, 17, 17, 15, 1, 2, 12],
  ":": [0, 12, 12, 0, 12, 12, 0],
  ";": [0, 12, 12, 0, 12, 12, 8],
  "<": [2, 4, 8, 16, 8, 4, 2],
  "=": [0, 0, 31, 0, 31, 0, 0],
  ">": [8, 4, 2, 1, 2, 4, 8],
  "?": [14, 17, 1, 2, 4, 0, 4],
  "@": [14, 17, 23, 21, 23, 16, 14],
  A: [14, 17, 17, 31, 17, 17, 17],
  B: [30, 17, 17, 30, 17, 17, 30],
  C: [14, 17, 16, 16, 16, 17, 14],
  D: [30, 17, 17, 17, 17, 17, 30],
  E: [31, 16, 16, 30, 16, 16, 31],
  F: [31, 16, 16, 30, 16, 16, 16],
  G: [14, 17, 16, 23, 17, 17, 15],
  H: [17, 17, 17, 31, 17, 17, 17],
  I: [14, 4, 4, 4, 4, 4, 14],
  J: [7, 2, 2, 2, 2, 18, 12],
  K: [17, 18, 20, 24, 20, 18, 17],
  L: [16, 16, 16, 16, 16, 16, 31],
  M: [17, 27, 21, 21, 17, 17, 17],
  N: [17, 25, 21, 19, 17, 17, 17],
  O: [14, 17, 17, 17, 17, 17, 14],
  P: [30, 17, 17, 30, 16, 16, 16],
  Q: [14, 17, 17, 17, 21, 18, 13],
  R: [30, 17, 17, 30, 20, 18, 17],
  S: [15, 16, 16, 14, 1, 1, 30],
  T: [31, 4, 4, 4, 4, 4, 4],
  U: [17, 17, 17, 17, 17, 17, 14],
  V: [17, 17, 17, 17, 17, 10, 4],
  W: [17, 17, 17, 21, 21, 21, 10],
  X: [17, 17, 10, 4, 10, 17, 17],
  Y: [17, 17, 10, 4, 4, 4, 4],
  Z: [31, 1, 2, 4, 8, 16, 31],
  "[": [14, 8, 8, 8, 8, 8, 14],
  "\\": [16, 8, 4, 2, 1, 0, 0],
  "]": [14, 2, 2, 2, 2, 2, 14],
  "^": [4, 10, 17, 0, 0, 0, 0],
  _: [0, 0, 0, 0, 0, 0, 31],
  "`": [8, 4, 0, 0, 0, 0, 0],
  "{": [2, 4, 4, 8, 4, 4, 2],
  "|": [4, 4, 4, 4, 4, 4, 4],
  "}": [8, 4, 4, 2, 4, 4, 8],
  "~": [0, 0, 9, 22, 0, 0, 0],
};
export class ContactSheetError extends Error {
  constructor(message, options) {
    super(message, options);
    this.name = "ContactSheetError";
  }
}
function validateLabel(value, field) {
  if (
    typeof value !== "string" ||
    value.length > MAX_CONTACT_SHEET_LABEL_LENGTH ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new ContactSheetError(
      `The contact-sheet ${field} must be a string of at most ${MAX_CONTACT_SHEET_LABEL_LENGTH} printable characters`,
    );
  }
}
function fillRectangle(image, x, y, width, height, color) {
  for (let row = y; row < y + height; row += 1) {
    for (let column = x; column < x + width; column += 1) {
      const offset = (image.width * row + column) * 4;
      image.data[offset] = color[0];
      image.data[offset + 1] = color[1];
      image.data[offset + 2] = color[2];
      image.data[offset + 3] = color[3];
    }
  }
}
function drawText(image, x, y, text, maxWidth, color, scale) {
  const advance = (FONT_WIDTH + 1) * scale;
  const maxCharacters = Math.max(0, Math.floor((maxWidth + scale) / advance));
  const normalized = text
    .toUpperCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/gu, "");
  const clipped =
    normalized.length > maxCharacters && maxCharacters > 3
      ? `${normalized.slice(0, maxCharacters - 3)}...`
      : normalized.slice(0, maxCharacters);
  for (let index = 0; index < clipped.length; index += 1) {
    const glyph = GLYPHS[clipped[index] ?? "?"] ?? GLYPHS["?"];
    for (let row = 0; row < FONT_HEIGHT; row += 1) {
      const bits = glyph[row] ?? 0;
      for (let column = 0; column < FONT_WIDTH; column += 1) {
        if ((bits & (1 << (FONT_WIDTH - column - 1))) !== 0) {
          fillRectangle(image, x + index * advance + column * scale, y + row * scale, scale, scale, color);
        }
      }
    }
  }
  return normalized.length > maxCharacters;
}
function compositeFrame(canvas, source, previous, left, top, magnification, highlightChanges) {
  let changedPixels = 0;
  for (let sourceY = 0; sourceY < source.height; sourceY += 1) {
    for (let sourceX = 0; sourceX < source.width; sourceX += 1) {
      const offset = (source.width * sourceY + sourceX) * 4;
      const changed =
        previous !== undefined &&
        (source.data[offset] !== previous.data[offset] ||
          source.data[offset + 1] !== previous.data[offset + 1] ||
          source.data[offset + 2] !== previous.data[offset + 2] ||
          source.data[offset + 3] !== previous.data[offset + 3]);
      if (changed) changedPixels += 1;
      const alpha = (source.data[offset + 3] ?? 255) / 255;
      const red = Math.round((source.data[offset] ?? 0) * alpha + CARD_COLOR[0] * (1 - alpha));
      const green = Math.round((source.data[offset + 1] ?? 0) * alpha + CARD_COLOR[1] * (1 - alpha));
      const blue = Math.round((source.data[offset + 2] ?? 0) * alpha + CARD_COLOR[2] * (1 - alpha));
      const color =
        changed && highlightChanges
          ? [
              Math.round(red * 0.45 + CHANGE_ACCENT[0] * 0.55),
              Math.round(green * 0.45 + CHANGE_ACCENT[1] * 0.55),
              Math.round(blue * 0.45 + CHANGE_ACCENT[2] * 0.55),
              255,
            ]
          : [red, green, blue, 255];
      fillRectangle(
        canvas,
        left + sourceX * magnification,
        top + sourceY * magnification,
        magnification,
        magnification,
        color,
      );
    }
  }
  return changedPixels;
}
/** Recolors decoded RGBA pixels in place with the hermretro player's color correction. */
function chromaticCorrectImage(image) {
  for (let offset = 0; offset < image.data.length; offset += 4) {
    image.data.set(chromaticDisplayColor(image.data[offset], image.data[offset + 1], image.data[offset + 2]), offset);
  }
  return image;
}
/** A frame as returned: color-corrected first when asked, then enlarged, decoding the PNG once. */
export function displayPng(bytes, { colorCorrection = "none", magnification = 1 }) {
  if (!Number.isSafeInteger(magnification) || magnification < 1 || magnification > MAX_CONTACT_SHEET_MAGNIFICATION) {
    throw new ContactSheetError(
      `Image magnification must be an integer between 1 and ${MAX_CONTACT_SHEET_MAGNIFICATION}`,
    );
  }
  if (colorCorrection !== "chromatic" && magnification === 1) return bytes;
  const source = PNG.sync.read(bytes, { checkCRC: true });
  if (colorCorrection === "chromatic") chromaticCorrectImage(source);
  if (magnification === 1) return PNG.sync.write(source, { colorType: 6, inputColorType: 6, inputHasAlpha: true });
  const canvas = new PNG({ width: source.width * magnification, height: source.height * magnification });
  compositeFrame(canvas, source, undefined, 0, 0, magnification, false);
  return PNG.sync.write(canvas, { colorType: 6, inputColorType: 6, inputHasAlpha: true });
}
export function contactSheetLayout(dimensions, columns, magnification) {
  const rows = Math.ceil(dimensions.length / columns);
  const fontScale = magnification >= 3 ? 2 : 1;
  const lineHeight = (FONT_HEIGHT + 3) * fontScale;
  const imageWidth = Math.max(GAME_BOY_FRAME_WIDTH, ...dimensions.map((entry) => entry.width)) * magnification;
  const imageHeight = Math.max(...dimensions.map((entry) => entry.height)) * magnification;
  const cardWidth = imageWidth + PADDING * 2;
  const cardHeight = imageHeight + PADDING * 3 + lineHeight * 2;
  const headerHeight = PADDING + lineHeight * 2;
  const width = GUTTER + columns * (cardWidth + GUTTER);
  const height = headerHeight + GUTTER + rows * (cardHeight + GUTTER);
  const fits = width <= MAX_CANVAS_DIMENSION && height <= MAX_CANVAS_DIMENSION && width * height <= MAX_CANVAS_PIXELS;
  return {
    rows,
    fontScale,
    lineHeight,
    imageWidth,
    imageHeight,
    cardWidth,
    cardHeight,
    headerHeight,
    width,
    height,
    fits,
  };
}
/**
 * Compose existing PNG bytes only: no filesystem access, capture, worker call,
 * sampling, or provenance inference. Callers retain their original metadata.
 * Variable dimensions support authored scene projections without rescaling or
 * cropping them to a fabricated Game Boy framebuffer.
 */
export function renderContactSheetPng(options) {
  options.signal?.throwIfAborted();
  if (!Array.isArray(options.images) || options.images.length < 1 || options.images.length > MAX_CONTACT_SHEET_FRAMES) {
    throw new ContactSheetError(`Contact sheets require between 1 and ${MAX_CONTACT_SHEET_FRAMES} images`);
  }
  validateLabel(options.title, "title");
  validateLabel(options.subtitle, "subtitle");
  const magnification = options.magnification ?? 2;
  const columns = options.columns ?? Math.min(3, options.images.length);
  if (!Number.isSafeInteger(magnification) || magnification < 1 || magnification > MAX_CONTACT_SHEET_MAGNIFICATION) {
    throw new ContactSheetError(
      `Contact-sheet magnification must be an integer between 1 and ${MAX_CONTACT_SHEET_MAGNIFICATION}`,
    );
  }
  if (!Number.isSafeInteger(columns) || columns < 1 || columns > MAX_CONTACT_SHEET_FRAMES) {
    throw new ContactSheetError(`Contact-sheet columns must be an integer between 1 and ${MAX_CONTACT_SHEET_FRAMES}`);
  }
  let totalPixels = 0;
  const dimensions = Array.from(options.images, (entry) => {
    options.signal?.throwIfAborted();
    if (typeof entry !== "object" || entry === null)
      throw new ContactSheetError("Each contact-sheet image must contain PNG bytes and labels");
    validateLabel(entry.label, "label");
    validateLabel(entry.caption, "caption");
    const bytes = entry.png;
    if (
      !Buffer.isBuffer(bytes) ||
      bytes.length < 33 ||
      bytes.length > MAX_CONTACT_SHEET_FRAME_BYTES ||
      !bytes.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE) ||
      bytes.readUInt32BE(8) !== 13 ||
      bytes.toString("ascii", 12, 16) !== "IHDR"
    ) {
      throw new ContactSheetError("Contact-sheet images must be bounded PNG bytes");
    }
    if (
      typeof entry.sha256 !== "string" ||
      !/^[a-f\d]{64}$/u.test(entry.sha256) ||
      createHash("sha256").update(bytes).digest("hex") !== entry.sha256
    ) {
      throw new ContactSheetError("The contact-sheet image SHA-256 does not match its PNG bytes");
    }
    const width = bytes.readUInt32BE(16);
    const height = bytes.readUInt32BE(20);
    totalPixels += width * height;
    if (
      width < 1 ||
      height < 1 ||
      width > MAX_CANVAS_DIMENSION ||
      height > MAX_CANVAS_DIMENSION ||
      totalPixels > MAX_CANVAS_PIXELS
    ) {
      throw new ContactSheetError("The contact-sheet input dimensions exceed the safe pixel budget");
    }
    return { width, height };
  });
  const {
    rows,
    fontScale,
    lineHeight,
    imageWidth,
    imageHeight,
    cardWidth,
    cardHeight,
    headerHeight,
    width,
    height,
    fits,
  } = contactSheetLayout(dimensions, columns, magnification);
  if (!fits) {
    throw new ContactSheetError("The contact-sheet dimensions exceed the maximum safe canvas size");
  }
  // All dimensions and aggregate allocation bounds are checked before decoding.
  const images = options.images.map(({ png }) => {
    options.signal?.throwIfAborted();
    let image;
    try {
      image = PNG.sync.read(png, { checkCRC: true });
    } catch (error) {
      throw new ContactSheetError("The contact-sheet image is not a valid PNG", { cause: error });
    }
    return options.colorCorrection === "chromatic" ? chromaticCorrectImage(image) : image;
  });
  const canvas = new PNG({ width, height });
  fillRectangle(canvas, 0, 0, width, height, CANVAS_COLOR);
  const headerClipped = [
    drawText(canvas, GUTTER, PADDING, options.title, width - GUTTER * 2, PRIMARY_TEXT, fontScale),
    drawText(canvas, GUTTER, PADDING + lineHeight, options.subtitle, width - GUTTER * 2, SECONDARY_TEXT, fontScale),
  ];
  const tiles = images.map((image, index) => {
    options.signal?.throwIfAborted();
    const entry = options.images[index];
    const cardX = GUTTER + (index % columns) * (cardWidth + GUTTER);
    const cardY = headerHeight + GUTTER + Math.floor(index / columns) * (cardHeight + GUTTER);
    const x = cardX + PADDING;
    const y = cardY + PADDING;
    fillRectangle(canvas, cardX, cardY, cardWidth, cardHeight, BORDER_COLOR);
    fillRectangle(canvas, cardX + 1, cardY + 1, cardWidth - 2, cardHeight - 2, CARD_COLOR);
    compositeFrame(canvas, image, undefined, x, y, magnification, false);
    const labelY = y + imageHeight + PADDING;
    const labelsClipped = [
      drawText(canvas, x, labelY, entry.label, imageWidth, FRAME_ACCENT, fontScale),
      drawText(canvas, x, labelY + lineHeight, entry.caption, imageWidth, PRIMARY_TEXT, fontScale),
    ];
    return {
      index,
      sha256: entry.sha256,
      sourceWidth: image.width,
      sourceHeight: image.height,
      x,
      y,
      width: image.width * magnification,
      height: image.height * magnification,
      label: entry.label,
      caption: entry.caption,
      labelsClipped,
    };
  });
  const png = PNG.sync.write(canvas, { colorType: 6, inputColorType: 6, inputHasAlpha: true });
  options.signal?.throwIfAborted();
  if (png.length > MAX_CONTACT_SHEET_PNG_BYTES)
    throw new ContactSheetError("The contact-sheet PNG exceeds its byte limit");
  return {
    png,
    sha256: createHash("sha256").update(png).digest("hex"),
    width,
    height,
    columns,
    rows,
    magnification,
    imageCount: images.length,
    title: options.title,
    subtitle: options.subtitle,
    headerClipped,
    tiles,
  };
}
