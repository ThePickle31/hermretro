"""Build an isolated Hermes runtime from a hermes-agent checkout (CI only; run with Hermes's prepared Python).

    "$HERMES_PYTHON" tools/hermes_runtime.py <hermes-agent checkout>

Uses Hermes's own package manager (`pm.build_environment`), the same way Hermes's plugin-validate action does,
and exports `HERMES_CLI` (the command that runs that Hermes) and `HERMES_SOURCE` (the checkout, for the install
scan) through GitHub's environment file.
"""
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path


def main() -> int:
    source = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(source))
    from pm import build_environment  # type: ignore[import-not-found]

    python = build_environment(source=source, out=source / ".build" / "runtime", explicit=True)
    cli = f"{shlex.quote(str(python))} -I -m hermes_cli.main"
    print(f"HERMES_CLI={cli}")
    exported = os.environ.get("GITHUB_ENV")
    if exported:
        with open(exported, "a", encoding="utf-8") as handle:
            handle.write(f"HERMES_CLI={cli}\nHERMES_SOURCE={source}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
