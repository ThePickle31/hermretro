"""hermes_host serves every name the area modules define, so hermes_host.<name> keeps working."""
import ast
import importlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapter import hermes_host  # noqa: E402

ADAPTER = Path(__file__).resolve().parents[1] / "adapter"


def top_level_names(module: str) -> set[str]:
    tree = ast.parse((ADAPTER / f"{module}.py").read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {target.id for target in node.targets if isinstance(target, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names - {"logger", "host"}


class MovedNames(unittest.TestCase):
    def test_every_area_definition_is_listed_and_reachable(self):
        for module, listed in hermes_host._MOVED.items():
            defined = top_level_names(module)
            self.assertEqual(defined - set(listed), set(), f"add these to hermes_host._MOVED[{module!r}]")
            self.assertEqual(set(listed) - defined, set(), f"{module} no longer defines these")
            area = importlib.import_module(f"adapter.{module}")
            for name in listed:
                self.assertIs(getattr(hermes_host, name), getattr(area, name), name)

    def test_no_name_is_defined_in_two_places(self):
        seen = {name: "hermes_host" for name in top_level_names("hermes_host")}
        for module in hermes_host._MOVED:
            for name in top_level_names(module):
                self.assertNotIn(name, seen, f"{name} is defined in {seen.get(name)} and {module}")
                seen[name] = module


if __name__ == "__main__":
    unittest.main()
