// Times and durations in words.
import { useEffect, useState } from '#sdk'

export function ago(seconds, now) {
  const elapsed = Math.max(0, Math.round(now / 1000 - seconds))

  if (elapsed < 5) {
    return 'just now'
  }

  if (elapsed < 60) {
    return `${elapsed}s ago`
  }

  if (elapsed < 3600) {
    return `${Math.round(elapsed / 60)} min ago`
  }

  return `${Math.round(elapsed / 3600)} h ago`
}

export function useNow(active, every = 1000) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!active) {
      return undefined
    }

    setNow(Date.now())

    const id = setInterval(() => setNow(Date.now()), every)

    return () => clearInterval(id)
  }, [active, every])

  return now
}

export function spanWords(ms) {
  const seconds = Math.max(0, Math.round(ms / 1000))

  if (seconds < 60) {
    return `${seconds}s`
  }

  const minutes = Math.floor(seconds / 60)

  return minutes < 60 ? `${minutes}m ${String(seconds % 60).padStart(2, '0')}s` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

export function clock(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000))

  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function timeOfDay(at) {
  if (!at) {
    return ''
  }

  try {
    return new Date(at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  } catch {
    return ''
  }
}
