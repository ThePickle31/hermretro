// Helpers for plain values, used across the engine. Imports nothing, so any module can use it.

export function isObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function asString(value, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

export function asNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function deepFreeze(value) {
  if (typeof value !== "object" || value === null || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

/** A read-only Map: its entries are fixed when it is made. */
export class FrozenMap {
  #entries;
  constructor(entries) {
    this.#entries = new Map(entries);
    Object.freeze(this);
  }
  get size() {
    return this.#entries.size;
  }
  get(key) {
    return this.#entries.get(key);
  }
  has(key) {
    return this.#entries.has(key);
  }
  entries() {
    return this.#entries.entries();
  }
  keys() {
    return this.#entries.keys();
  }
  values() {
    return this.#entries.values();
  }
  [Symbol.iterator]() {
    return this.#entries[Symbol.iterator]();
  }
  forEach(callback, receiver) {
    this.#entries.forEach((value, key) => callback.call(receiver, value, key, this));
  }
}
