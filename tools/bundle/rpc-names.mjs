/** Runs tools/bundle/rpc_names.py, which makes page/app/rpc-names.js from the backend's @rpc declarations
 *  (Python from PATH), for tools/bundle/bundle.mjs before every build or check. */
import { spawnSync } from 'node:child_process'

/** Regenerate (or with `check`, verify) page/app/rpc-names.js from the backend's @rpc declarations. */
export function rpcNames(root, check) {
  for (const python of ['python3', 'python']) {
    const result = spawnSync(python, ['tools/bundle/rpc_names.py', ...(check ? ['--check'] : [])], { cwd: root, encoding: 'utf8' })

    if (result.error?.code === 'ENOENT') {
      continue
    }

    const output = `${result.stdout ?? ''}${result.stderr ?? ''}`.trim()

    if (result.status !== 0) {
      return [output || `${python} tools/bundle/rpc_names.py failed`]
    }

    if (output) {
      console.log(output)
    }

    return []
  }

  return ['Python was not found, so page/app/rpc-names.js (generated from backend/) could not be made\nFIX: install Python 3.11 or newer (python3 on PATH), then run node tools/bundle/bundle.mjs again']
}
