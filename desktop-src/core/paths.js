// Small helpers for project file paths.
export const baseName = value => String(value ?? '').split(/[\\/]/).filter(Boolean).pop() ?? ''
export const isAbsolute = value => typeof value === 'string' && (value.startsWith('/') || /^[a-zA-Z]:[\\/]/.test(value) || value.startsWith('file://'))
export const joinPath = (root, relative) => (root ? `${root.replace(/[\\/]+$/, '')}/${relative.replace(/^\.?[\\/]+/, '')}` : null)
