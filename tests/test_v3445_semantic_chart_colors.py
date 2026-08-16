from pathlib import Path
import unittest


class SemanticChartColorSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).resolve().parents[1] / "src" / "style.py").read_text()

    def test_semantic_palette_is_defined(self):
        self.assertIn('"commercial": "#19C7FF"', self.source)
        self.assertIn('"noncommercial": "#FF9D00"', self.source)
        self.assertIn('"retail": "#9BE600"', self.source)
        self.assertIn('"speculative": "#B887FF"', self.source)

    def test_noncommercial_mapping_precedes_commercial_mapping(self):
        noncommercial = self.source.index('if "non-commercial" in name or "noncommercial" in name:')
        commercial = self.source.index('if "commercial" in name:', noncommercial)
        self.assertLess(noncommercial, commercial)

    def test_palette_is_applied_centrally(self):
        self.assertIn('_apply_semantic_chart_colors(fig)', self.source)
        self.assertIn('colorway=CHART_COLORWAY', self.source)


if __name__ == "__main__":
    unittest.main()
