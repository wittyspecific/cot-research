import ast
import unittest
from pathlib import Path


class V3441MetricLabelHotfixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("pages/marktanalyse.py").read_text(encoding="utf-8")
        ast.parse(cls.source)

    def test_unsupported_tone_kwarg_is_gone(self):
        self.assertNotIn('tone=nc_crowding["tone"]', self.source)

    def test_156w_is_explicit(self):
        self.assertIn('"Commercial Netto · 156W"', self.source)
        self.assertIn('"Non-Commercial Netto · 156W"', self.source)
        self.assertIn('name="Commercial-Netto-Perzentil · 156W"', self.source)
        self.assertIn('name="Non-Commercial-Netto-Perzentil · 156W"', self.source)
        self.assertIn('name="Retail-Netto-Perzentil · 156W"', self.source)


if __name__ == "__main__":
    unittest.main()
