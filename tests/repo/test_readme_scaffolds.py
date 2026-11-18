"""No feature README offers a `retrodev new` that `new` refuses there.

`new` adds no RPC, tool or event to a standard-library-only feature (tools/retrodev/policy.toml [new] stdlib_only:
the broker, system); its README says where such declarations go instead (a gateway-side feature).
"""

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ReadmeScaffoldTests(unittest.TestCase):
    def test_stdlib_only_features_offer_no_rpc_tool_or_event_scaffold(self):
        policy = tomllib.loads((ROOT / "tools" / "retrodev" / "policy.toml").read_text())
        found = []
        for name in policy["new"]["stdlib_only"]:
            readme = ROOT / "backend" / name / "README.md"
            text = readme.read_text() if readme.is_file() else ""
            found += [
                f"backend/{name}/README.md: {hit.group(0)}"
                for hit in re.finditer(rf"retrodev new (?:rpc|tool|event) {name}\b[^`]*", text)
            ]
        self.assertEqual(
            found,
            [],
            "\nthese READMEs offer a `retrodev new` that new refuses (the feature stays stdlib-only)\n"
            "FIX: point at a gateway-side feature that reaches this one through its front door",
        )


if __name__ == "__main__":
    unittest.main()
