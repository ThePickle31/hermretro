"""Use the engine's project writer gate while Python replaces a live image."""

import select
import subprocess
from contextlib import contextmanager

from ..system.paths import ENGINE_ROOT, find_node


class RestoreConflict(OSError):
    """Restore lost to another writer."""


_HOLD_LOCK = """
const [moduleUrl, root] = process.argv.slice(1);
const { withProjectWriteLock } = await import(moduleUrl);
try {
    await withProjectWriteLock(root, async () => {
        process.stdout.write('locked\\n');
        for await (const chunk of process.stdin) { /* Wait for the caller to close the pipe. */ }
    }, { timeoutMs: 0 });
} catch (error) {
    console.error(error.message);
    process.exitCode = error.code === 'RESOURCE_WRITE_LOCKED' ? 2 : 1;
}
"""


@contextmanager
def project_writer_lock(root):
    """Hold the same canonical root lock as the engine until the caller closes stdin."""
    node = find_node()
    if not node["ok"]:
        raise OSError("Node.js is needed to lock the project before restoring an image.")
    module_url = (ENGINE_ROOT / "src" / "project-files.js").as_uri()
    with subprocess.Popen(
        [node["path"], "--input-type=module", "-e", _HOLD_LOCK, module_url, str(root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        try:
            if not select.select([process.stdout], [], [], 5)[0]:
                raise OSError("Could not lock the project before restoring the image.")
            held = process.stdout.readline() == b"locked\n"
            if held:
                yield
        finally:
            # Closing the pipe releases the lock even if the Python caller exits unexpectedly.
            try:
                _, error = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _, error = process.communicate()
        if not held:
            if process.returncode == 2:
                raise RestoreConflict("The project is locked. Try restoring the image again shortly.")
            raise OSError(error.decode(errors="replace").strip() or "Could not lock the project.")
