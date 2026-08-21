from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
DASH = ROOT / "pages" / "dashboard.py"


def _calls(text: str) -> str:
    tree = ast.parse(text)
    return "\n".join(
        ast.get_source_segment(text, node) or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )


def test_dashboard_top3_is_not_rendered():
    text = DASH.read_text(encoding="utf-8")
    executable = _calls(text)

    assert "Potenzial · Top 3 Setups" not in executable
    assert "Aktuelle aligned Setups werden geprüft" not in executable
    assert "_dashboard_full_alignment_state(" not in text


def test_dashboard_no_longer_loads_alignment_scan_helpers():
    text = DASH.read_text(encoding="utf-8")
    tree = ast.parse(text)

    loaded_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
    }

    assert "scan_classic_markets" not in loaded_names
    assert "classify_macro_micro_trade" not in loaded_names
    assert "calculate_market_20y_multi_seasonality" not in loaded_names


def test_dashboard_keeps_requested_quick_access_order():
    text = DASH.read_text(encoding="utf-8")

    trade = text.index('st.page_link("pages/trade_planner.py"')
    watch = text.index('st.page_link("pages/watchlist.py"')
    intermarket = text.index('st.page_link("pages/intermarket.py"')
    currency = text.index('st.page_link("pages/forex_matrix.py"')

    assert trade < watch < intermarket < currency


def test_visible_product_brand_is_quant_research():
    text = APP.read_text(encoding="utf-8")

    assert 'page_title="Quant Research"' in text
    assert "cot-brand-title\">Quant Research</div>" in text
    assert "### 📊 Quant Research" in text


def test_specific_cot_research_module_names_may_remain():
    text = APP.read_text(encoding="utf-8")

    # Product brand changed; COT-specific module names remain semantically valid.
    assert "Quant Research" in text


def test_files_parse():
    for path in (APP, DASH):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
