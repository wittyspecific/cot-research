import ast
import unittest
from pathlib import Path


class V3443MarketSeasonalityYAxisTests(unittest.TestCase):
    def test_multi_horizon_card_exists(self):
        source = Path("pages/marktanalyse.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('"Saison · 20J / 20-40-60T"', source)
        self.assertIn('for _horizon in (20, 40, 60):', source)
        self.assertIn('market_multi_seasonality_summary["compact"]', source)

    def test_axis_drag_config_enabled(self):
        source = Path("src/style.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('"showAxisDragHandles": True', source)
        self.assertIn('"showAxisRangeEntryBoxes": True', source)

    def test_single_axis_is_right_sided(self):
        source = Path("src/style.py").read_text(encoding="utf-8")
        self.assertIn('if "yaxis2" not in fig.layout.to_plotly_json():', source)
        self.assertIn('fig.update_yaxes(side="right")', source)

    def test_help_text_mentions_scaling(self):
        source = Path("pages/marktanalyse.py").read_text(encoding="utf-8")
        self.assertIn(
            "Y-Skala rechts ziehen = vertikal stauchen / strecken",
            source,
        )

    def test_custom_tradingview_scale_is_reusable_and_y_only(self):
        source = Path("src/style.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("def tradingview_plotly_chart(", source)
        self.assertIn("pointerdown", source)
        self.assertIn("requestAnimationFrame", source)
        self.assertIn("drag.center", source)
        self.assertIn("`${drag.axisKey}.range`", source)
        self.assertIn("Plotly.relayout(gd, update)", source)
        self.assertNotIn("update[`xaxis.range`]", source)

    def test_all_project_plotly_charts_use_custom_renderer(self):
        pages = [
            Path("pages/marktanalyse.py"),
            Path("pages/research_lab.py"),
        ]
        combined = "\n".join(p.read_text(encoding="utf-8") for p in pages)
        for p in pages:
            ast.parse(p.read_text(encoding="utf-8"))
        self.assertNotIn("st.plotly_chart(", combined)
        self.assertEqual(combined.count("tradingview_plotly_chart("), 11)


if __name__ == "__main__":
    unittest.main()
