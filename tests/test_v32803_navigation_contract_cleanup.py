from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

FILES = (
    ROOT / "tests" / "test_v3143_asset_class_watchlists.py",
    ROOT / "tests" / "test_v3149_native_routing_clean_nav.py",
    ROOT / "tests" / "test_v3220_market_regime_vol_credit_research.py",
    ROOT / "tests" / "test_v3226_seasonality_edge_lab.py",
    ROOT / "tests" / "test_v3227_cot_x_seasonality_lab.py",
    ROOT / "tests" / "test_v32401_navigation_test_contract_cleanup.py",
    ROOT / "tests" / "test_v3250_cot_price_historical_analog_lab.py",
    ROOT / "tests" / "test_v3251_fx_relative_cot_analog.py",
)


def test_stale_navigation_contracts_are_removed():
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


def test_cleanup_targets_parse():
    for path in FILES:
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
