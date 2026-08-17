from pathlib import Path
import unittest


class SemanticChartColorSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).resolve().parents[1] / "src" / "style.py").read_text()

    def test_semantic_palette_is_defined(self):
        self.assertIn('"commercial": "#16A34A"', self.source)
        self.assertIn('"noncommercial": "#2563EB"', self.source)
        self.assertIn('"retail": "#F59E0B"', self.source)
        self.assertIn('"speculative": "#7C3AED"', self.source)

    def test_noncommercial_mapping_precedes_commercial_mapping(self):
        noncommercial = self.source.index('if "non-commercial" in name or "noncommercial" in name:')
        commercial = self.source.index('if "commercial" in name:', noncommercial)
        self.assertLess(noncommercial, commercial)

    def test_palette_is_applied_centrally(self):
        self.assertIn('_apply_semantic_chart_colors(fig)', self.source)
        self.assertIn('colorway=CHART_COLORWAY', self.source)


if __name__ == "__main__":
    unittest.main()
