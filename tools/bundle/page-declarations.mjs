import { spawnSync } from 'node:child_process'

/** Generate or check the Desktop's backend-owned RPC names and Build instructions. */
export function pageDeclarations(root, check) {
  for (const python of ['python3', 'python']) {
    const result = spawnSync(python, ['tools/bundle/page_declarations.py', ...(check ? ['--check'] : [])], { cwd: root, encoding: 'utf8' })

    if (result.error?.code === 'ENOENT') {
      continue
    }

    const output = `${result.stdout ?? ''}${result.stderr ?? ''}`.trim()

    if (result.status !== 0) {
      return [output || `${python} tools/bundle/page_declarations.py failed`]
    }

    if (output) {
      console.log(output)
    }

    return []
  }

  return ['Python was not found, so the Desktop declarations could not be generated\nFIX: install Python 3.11 or newer (python3 on PATH), then run node tools/bundle/bundle.mjs again']
}
