// Helpers for bytes, used across the engine. Imports only Node's own modules, so any module can use it.
import { createHash } from "node:crypto";

export const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

/** The SHA-256 of `value` (bytes or a string), in lowercase hex. */
export function sha256Hex(value) {
  return createHash("sha256").update(value).digest("hex");
}
