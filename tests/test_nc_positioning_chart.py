import ast
import unittest
from pathlib import Path


class NCPositioningChartRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("pages/marktanalyse.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_noncommercial_index_is_computed(self):
        self.assertIn(
            'cot["noncommercial_index"] = cot_index(',
            self.source,
        )

    def test_noncommercial_index_trace_exists(self):
        self.assertIn(
            'name="Non-Commercial COT-Index"',
            self.source,
        )

    def test_noncommercial_percentile_trace_exists(self):
        self.assertIn(
            'name="Non-Commercial-Netto-Perzentil · 156W"',
            self.source,
        )

    def test_crowding_context_exists(self):
        self.assertIn(
            "LONG-CROWDING · DREHT AB",
            self.source,
        )
        self.assertIn(
            "SHORT-CROWDING · DREHT AB",
            self.source,
        )

    def test_nc_is_not_described_as_independent_confirmation(self):
        self.assertIn(
            "keine zusätzliche unabhängige Bestätigung",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
