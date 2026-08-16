import ast
import unittest
from pathlib import Path


class FXRuntimeHelperRegressionTests(unittest.TestCase):
    def test_required_fx_runtime_helpers_exist(self):
        source = Path("src/fx_relative.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        required = {
            "load_currency_usd_values",
            "synthesize_pair_prices",
            "add_20y_multi_pair_seasonality",
        }
        self.assertTrue(required.issubset(functions), required - functions)

    def test_multi_horizon_function_calls_existing_helpers(self):
        source = Path("src/fx_relative.py").read_text(encoding="utf-8")
        self.assertIn("values = load_currency_usd_values()", source)
        self.assertIn("prices = synthesize_pair_prices(", source)


if __name__ == "__main__":
    unittest.main()
