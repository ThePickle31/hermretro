// A duration that keeps counting.
import { clock, useNow } from '../core/time.js'

export function Elapsed({ since }) {
  const now = useNow(Boolean(since))

  return since ? clock(now - since) : ''
}
