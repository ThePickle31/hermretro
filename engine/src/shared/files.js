// Helpers for files and file system errors, used across the engine. Imports nothing, so any module can use it.

/** Whether `error` is a system error with this code (ENOENT, EEXIST...). */
export function isSystemError(error, code) {
  return typeof error === "object" && error !== null && "code" in error && error.code === code;
}

/** Whether two stats are of the same file. */
export function sameFile(left, right) {
  return left.dev === right.dev && left.ino === right.ino;
}
