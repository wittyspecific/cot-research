from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

TARGETS = (
    ROOT / "tests" / "test_v3212_dashboard_trader_focus.py",
    ROOT / "tests" / "test_v3213_dashboard_top3_aligned.py",
    ROOT / "tests" / "test_v3214_dashboard_cleanup_quant_research_brand.py",
)


def test_v32904_dashboard_contract_files_parse():
    for path in TARGETS:
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )


def test_v32904_new_dashboard_hubs_are_expected():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in TARGETS
    )

    assert "pages/opportunity_scanner.py" in combined
    assert "pages/market_analysis_hub.py" in combined
    assert "pages/currency_strength_hub.py" in combined


def test_v32904_old_direct_research_quick_links_are_not_required():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in TARGETS
    )

    assert 'text.index(\'st.page_link("pages/watchlist.py"\')' not in combined
    assert 'text.index(\'st.page_link("pages/intermarket.py"\')' not in combined
    assert 'text.index(\'st.page_link("pages/forex_matrix.py"\')' not in combined
