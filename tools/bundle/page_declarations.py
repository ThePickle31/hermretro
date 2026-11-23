"""Prepare backend-owned RPC names and Build workflow instructions for the Desktop bundle."""

import argparse
import json
import runpy

import rpc_names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if rpc_names.main(["--check"] if args.check else []):
        return 1

    workflow = runpy.run_path(str(rpc_names.ROOT / "backend/hermes/workflow.py"))
    output = rpc_names.ROOT / "page/pages/build/workflow.js"
    lines = ["// Generated from backend/hermes/workflow.py by tools/bundle/page_declarations.py."]
    for name in ("BUILD_START", "PLAN_START"):
        lines.append(f"export const {name} = {json.dumps(workflow[name])}")
    text = "\n".join(lines) + "\n"
    if not output.is_file() or output.read_text() != text:
        if args.check:
            print("Build workflow is stale\nFIX: run node tools/bundle/bundle.mjs")
            return 1
        output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
