"""tools/engine/compare_bundles.mjs: two bundles hold the same program only when nothing but layout, grouping
parentheses and where imports stand differs; a difference that is only renamed bindings is named as such and is still
a difference; anything that changes what runs is a difference. Each case of two programs that run differently is run
in Node first, to show they really do."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "engine"
NODE = shutil.which("node")
INSTALLED = (TOOLS / "npm" / "node_modules" / "acorn" / "package.json").is_file()

# A bundle as esbuild writes one: marked modules, imports at the head of the module that uses them.
BUNDLE = """// dist/a.js
import { basename as basename2, dirname } from "node:path";
var first = 1;
var second = 2;
function pick(value) {
  return { first, value: `level1:${basename2(value)}`, at: /v1/.test(value) ? dirname(value) : value };
}

// dist/b.js
var entry = { sha256: "x", first };
console.log(pick("/v1/a"), entry.sha256, second);
export {
  pick
};
"""
# Modules the programs below import.
HELPERS = {
    "a.mjs": 'console.log("a");\n',
    "b.mjs": 'console.log("b");\n',
    "star.mjs": 'const v = 5;\nexport { v as "*" };\nexport const k = 1;\n',
}
# Pairs of programs that differ in what they do, though a careless comparison would call them the same.
DIFFERENT = {
    "import order": ('import "./a.mjs";\nimport "./b.mjs";\n', 'import "./b.mjs";\nimport "./a.mjs";\n'),
    "a binding and a global": ("const a = 1;\nconsole.log(typeof a);\n", "const a = 1;\nconsole.log(typeof b);\n"),
    "a namespace and an export named *": (
        'import * as v from "./star.mjs";\nconsole.log(typeof v);\n',
        'import { "*" as v } from "./star.mjs";\nconsole.log(typeof v);\n',
    ),
    "a name eval reads": (
        'const a = 1;\nconsole.log(eval("typeof a"));\n',
        'const b = 1;\nconsole.log(eval("typeof a"));\n',
    ),
    "a function's own name": ("function f() {}\nconsole.log(f.name);\n", "function g() {}\nconsole.log(g.name);\n"),
    "a name given to an arrow": (
        "const f = () => 1;\nconsole.log(f.name);\n",
        "const g = () => 1;\nconsole.log(g.name);\n",
    ),
    "__proto__ in shorthand": (
        "const __proto__ = { value: 7 };\nconsole.log({ __proto__ }.value);\n",
        "const __proto__ = { value: 7 };\nconsole.log({ __proto__: __proto__ }.value);\n",
    ),
    "a parenthesised assignment target": (
        "let f;\nf = () => {};\nconsole.log(f.name);\n",
        "let f;\n(f) = () => {};\nconsole.log(f.name);\n",
    ),
    "an imported name eval reads": (
        'import { basename as aa } from "node:path";\nconsole.log(eval("typeof aa"));\n',
        'import { basename as bb } from "node:path";\nconsole.log(eval("typeof aa"));\n',
    ),
    "a name in an error message": (
        "try {\n  const first = first;\n} catch (error) {\n  console.log(error.message);\n}\n",
        "try {\n  const second = second;\n} catch (error) {\n  console.log(error.message);\n}\n",
    ),
    "private names": (
        "class A {\n  #x = 1;\n  #y = 2;\n  get v() {\n    return this.#x;\n  }\n}\nconsole.log(new A().v);\n",
        "class A {\n  #y = 1;\n  #x = 2;\n  get v() {\n    return this.#x;\n  }\n}\nconsole.log(new A().v);\n",
    ),
    "a template's raw text": ("console.log(String.raw`\\x61`);\n", "console.log(String.raw`a`);\n"),
    "a parenthesised target in a pattern": (
        "let f;\n[f = () => {}] = [];\nconsole.log(f.name);\n",
        "let f;\n[(f) = () => {}] = [];\nconsole.log(f.name);\n",
    ),
}
# Bundles that must compare the same as themselves.
VALID = {
    "an imported binding exported again": 'import { suffix } from "../scripts/helper.mjs";\nexport { suffix };\n',
    "a class that names itself": "class C {\n  static self = C;\n}\nexport { C };\n",
    "an exported pattern with a default": "export const { a = 1 } = {};\n",
    "a string like a separator": 'console.log("/*! hermretro-statement */");\n',
    "imports only": 'import "./a.mjs";\nimport { k } from "./star.mjs";\n',
    "a marker inside a template": "console.log(`\n// dist/c.js\nlevel1`);\n",
    "statements ended by a line break": 'foo()\nimport "./a.mjs"\n[bar()];\n',
}


def bundle_with(**replacements: str) -> str:
    text = BUNDLE
    for old, new in replacements.items():
        assert old in text, old
        text = text.replace(old, new)
    return text


@unittest.skipUnless(NODE and INSTALLED, "node or tools/engine/npm is missing (npm ci --prefix tools/engine/npm)")
class EngineCompareTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def node(self, *args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
        return subprocess.run([NODE, *args], cwd=cwd, capture_output=True, text=True, timeout=120)

    def compare(self, before: str, after: str) -> subprocess.CompletedProcess:
        (self.folder / "before.js").write_text(before)
        (self.folder / "after.js").write_text(after)
        return self.node(
            str(TOOLS / "compare_bundles.mjs"), str(self.folder / "before.js"), str(self.folder / "after.js")
        )

    def assertSame(self, before: str, after: str):
        done = self.compare(before, after)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("the bundles hold the same program", done.stdout)

    def assertDifferent(self, before: str, after: str):
        done = self.compare(before, after)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(done.stderr, "")

    def test_layout_grouping_and_where_imports_stand_do_not_count(self):
        # Layout changed, parentheses added, a shorthand written out, an import moved to another module and split.
        moved = bundle_with(
            **{
                'import { basename as basename2, dirname } from "node:path";\n': "",
                "var first = 1;": "var first   =   (1);",
                "{ first, value": "{ first: first, value",
                "// dist/b.js\n": (
                    '// dist/b.js\nimport { dirname } from "node:path";\n'
                    'import { basename as basename2 } from "node:path";\n'
                ),
            }
        )
        self.assertSame(BUNDLE, moved)

    def test_renamed_bindings_are_named_and_still_differ(self):
        done = self.compare(BUNDLE, BUNDLE.replace("basename2", "basename7"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("differ only in the names of 1 bindings:\n  basename2 -> basename7", done.stdout)
        # Removing one of two names for the same import is not a rename.
        both = 'import { basename as aa, basename as bb } from "node:path";\nconsole.log(aa);\n'
        done = self.compare(both, 'import { basename as aa } from "node:path";\nconsole.log(aa);\n')
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("differ only in the names", done.stdout)
        self.assertIn("imported only by the first", done.stdout)

    def test_every_change_to_what_runs_counts(self):
        changes = {
            "another import": {"? dirname(value)": "? basename2(value)"},
            "another binding": {"console.log(pick(": "console.log(pick(second, "},
            "a property name": {"entry.sha256": "entry.sha512"},
            "a regular expression": {"/v1/.test": "/v2/.test"},
            "template text": {"`level1:": "`level2:"},
            "an exported name": {"  pick\n};": "  pick as choose\n};"},
            "an imported name": {'dirname } from "node:path"': 'resolve as dirname } from "node:path"'},
        }
        for change, replacements in changes.items():
            with self.subTest(change=change):
                self.assertDifferent(BUNDLE, bundle_with(**replacements))

    def test_modules_run_in_another_order_differ(self):
        a, b = BUNDLE.split("// dist/b.js\n")
        swapped = "// dist/b.js\n" + b.replace("export {\n  pick\n};\n", "") + a + "export {\n  pick\n};\n"
        done = self.compare(BUNDLE, swapped)
        self.assertEqual(done.returncode, 1)
        self.assertIn("first difference", done.stdout)

    def test_requests_in_another_order_differ(self):
        # The same module asked for with other attributes can be another module, so attributes are part of a request.
        first = 'import data from "./x.json" with { type: "json" };\nimport "./x.json";\nconsole.log(data);\n'
        second = 'import "./x.json";\nimport data from "./x.json" with { type: "json" };\nconsole.log(data);\n'
        done = self.compare(first, second)
        self.assertEqual(done.returncode, 1)
        self.assertIn("requested in another order", done.stdout)

    def test_programs_that_run_differently_differ(self):
        for name, text in HELPERS.items():
            (self.folder / name).write_text(text)
        for case, (before, after) in DIFFERENT.items():
            with self.subTest(case=case):
                outputs = []
                for name, text in (("before.mjs", before), ("after.mjs", after)):
                    (self.folder / name).write_text(text)
                    ran = self.node(str(self.folder / name), cwd=self.folder)
                    outputs.append((ran.returncode, ran.stdout, ran.stderr.splitlines()[-1:]))
                self.assertNotEqual(outputs[0], outputs[1], "the two programs should run differently")
                self.assertDifferent(before, after)

    def test_valid_bundles_are_the_same_as_themselves(self):
        for case, text in VALID.items():
            with self.subTest(case=case):
                self.assertSame(text, text)
        self.assertDifferent(VALID["statements ended by a line break"], "foo()[bar()];\n")


if __name__ == "__main__":
    unittest.main()
