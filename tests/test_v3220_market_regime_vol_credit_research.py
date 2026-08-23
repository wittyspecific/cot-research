from pathlib import Path
import ast

import pandas as pd

from src.credit_stress import classify_credit_snapshot
from src.market_risk_regime import build_market_risk_regime
from src.volatility_regime import classify_volatility_snapshot

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def _pages_dict(text: str):
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign)) and ((isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pages" for t in n.targets)) or (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == "pages")))
    return node.value


def _section(text: str, name: str):
    node = _pages_dict(text)
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and key.value == name:
            return [ast.get_source_segment(text, item) or "" for item in value.elts]
    raise AssertionError(name)


def test_navigation_places_three_pages_after_currency_strength_visible_order():
    from pathlib import Path
    import ast
    app = Path(__file__).resolve().parents[1] / "app.py"
    text = app.read_text(encoding="utf-8")
    tree = ast.parse(text)
    research = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "RESEARCH" and isinstance(value, ast.List):
                research = value
    assert research is not None
    paths = []
    for item in research.elts:
        for child in ast.walk(item):
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value.startswith("pages/"):
                paths.append(child.value); break
    assert paths == ["pages/opportunity_scanner.py", "pages/market_analysis_hub.py", "pages/currency_strength_hub.py", "pages/macro_regime.py"]





def test_market_regime_uses_equal_bucket_votes():
    rows = []
    for symbol, macro, micro, comm in (("ES",1,1,10),("NQ",1,1,8),("HG",1,1,5),("AUD",1,1,3),("JPY",-1,-1,-2),("ZN",-1,-1,-1)):
        rows.append({"symbol": symbol, "macro_dir": macro, "micro_dir": micro, "commercial_change_4w": comm})
    def classifier(row):
        return {"macro": {"direction": int(row["macro_dir"])}, "micro": {"direction": int(row["micro_dir"])}}
    out = build_market_risk_regime(pd.DataFrame(rows), classifier=classifier)
    assert out["regime"] in {"RISK-ON", "STRONG RISK-ON"}
    assert out["available_buckets"] == 5
    assert len(out["buckets"]) == 5


def test_volatility_classifier_distinguishes_stress_and_relief():
    idx = pd.date_range("2025-01-01", periods=100, freq="B")
    calm_vix = pd.Series([20.0] * 90 + [18,17,16,15,14,14,13.5,13,12.5,12], index=idx)
    calm_3m = pd.Series([21.0] * 100, index=idx)
    assert classify_volatility_snapshot(calm_vix, calm_3m)["regime"] == "RISK-ON"
    stress_vix = pd.Series([14.0] * 90 + [15,17,19,22,25,28,31,34,37,40], index=idx)
    stress_3m = pd.Series([20.0] * 100, index=idx)
    stress = classify_volatility_snapshot(stress_vix, stress_3m)
    assert stress["regime"] == "RISK-OFF"
    assert stress["curve"] == "BACKWARDATION"


def test_credit_classifier_detects_widening_stress():
    idx = pd.date_range("2025-01-01", periods=120, freq="B")
    hy = pd.Series([3.0] * 95 + [3.0,3.05,3.10,3.15,3.20,3.25,3.30,3.35,3.40,3.45,3.50,3.60,3.70,3.80,3.90,4.00,4.10,4.20,4.30,4.40,4.50,4.60,4.70,4.80,4.90], index=idx)
    ig = pd.Series([1.0] * 120, index=idx)
    out = classify_credit_snapshot(hy, ig)
    assert out["regime"] == "STRESS"
    assert out["direction"] == "WIDENING"


def test_pages_hide_exact_methodology_from_trader_view():
    for name in (
        "market_regime.py",
        "volatility_regime.py",
        "credit_stress.py",
    ):
        text = (
            ROOT / "pages" / name
        ).read_text(
            encoding="utf-8"
        )
        lowered = text.lower()

        # Trader-facing pages must explicitly state that internal
        # methodology is hidden.
        assert (
            "schwellen" in lowered
            or "zuordnung" in lowered
        ), name

        # The pages use slightly different wording to make clear that
        # they are context/research layers rather than direct signals.
        assert any(
            token in lowered
            for token in (
                "trade-signal",
                "trade",
                "entry-filter",
                "research-layer",
                "research-/kontextschicht",
                "research-/kontext",
            )
        ), name




def test_python_files_parse():
    for path in (ROOT / "src" / "research_market_data.py", ROOT / "src" / "market_risk_regime.py", ROOT / "src" / "volatility_regime.py", ROOT / "src" / "credit_stress.py", ROOT / "pages" / "market_regime.py", ROOT / "pages" / "volatility_regime.py", ROOT / "pages" / "credit_stress.py", APP):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
