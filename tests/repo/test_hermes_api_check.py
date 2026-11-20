"""tools/ci/hermes_api_check.py tells a Python that cannot import Hermes apart from a Hermes that renamed a name."""

import contextlib
import io
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ci"))

import hermes_api_check  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import api as hermes_api  # noqa: E402 - the repository root goes on sys.path first


def importer(broken: dict):
    """An import_module that fails for the modules in ``broken`` and gives every other a callable for each name."""

    def load(module):
        if module in broken:
            raise broken[module]
        return types.SimpleNamespace(**{attribute: print for _module, attribute in hermes_api.USED})

    return load


def run(load) -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = hermes_api_check.main(load)
    return code, err.getvalue()


class HermesApiCheck(unittest.TestCase):
    def test_a_module_that_fails_to_import_is_reported_with_its_error_not_as_a_rename(self):
        module = hermes_api.USED[-1][0]
        code, err = run(importer({module: ModuleNotFoundError("No module named 'ruamel'")}))
        self.assertEqual(code, 1)
        self.assertIn(f"{module}: ModuleNotFoundError: No module named 'ruamel'", err)
        self.assertIn("FIX: run with a Python that imports Hermes and its dependencies", err)
        self.assertNotIn("lacks", err)
        self.assertNotIn("rename", err)

    def test_no_hermes_at_all_names_hermes_cli_alone(self):
        code, err = run(importer({"hermes_cli": ModuleNotFoundError("No module named 'hermes_cli'")}))
        self.assertEqual(code, 1)
        self.assertEqual(err.count("ModuleNotFoundError"), 1, err)

    def test_a_hermes_that_imports_reaches_the_name_check(self):
        with mock.patch.object(hermes_api, "missing", return_value=["hermes_cli.config.load_config_readonly"]):
            code, err = run(importer({}))
        self.assertEqual(code, 1)
        self.assertIn("this Hermes lacks: hermes_cli.config.load_config_readonly", err)
        with mock.patch.object(hermes_api, "missing", return_value=[]):
            self.assertEqual(run(importer({}))[0], 0)


if __name__ == "__main__":
    unittest.main()
