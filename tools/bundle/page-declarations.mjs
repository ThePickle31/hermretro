import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'

export const WORKFLOW_SOURCE = 'backend/hermes/workflow.py'
const WORKFLOW_MODULE = 'page/pages/build/workflow.js'

/** Generate or check the Desktop's backend-owned RPC names and Build instructions. */
export function pageDeclarations(root, ...flags) {
  for (const python of ['python3', 'python']) {
    const result = spawnSync(python, ['tools/bundle/page_declarations.py', ...flags], { cwd: root, encoding: 'utf8' })

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


/** Regenerate the Desktop fallback before esbuild reads it when watching its Python source. */
export function watchWorkflow(root) {
  const generated = path.join(root, WORKFLOW_MODULE)
  const watchFiles = [path.join(root, WORKFLOW_SOURCE)]

  return {
    name: 'build-workflow',
    setup(build) {
      build.onLoad({ filter: /workflow\.js$/ }, args => {
        if (args.path !== generated) {
          return
        }

        const problems = pageDeclarations(root, '--workflow-only')

        return problems.length
          ? { errors: problems.map(text => ({ text })), watchFiles }
          : { contents: readFileSync(generated, 'utf8'), watchFiles }
      })
    }
  }
}
