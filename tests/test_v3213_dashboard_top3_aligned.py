from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "pages" / "dashboard.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _calls(text: str) -> str:
    tree = ast.parse(text)
    return "\n".join(
        ast.get_source_segment(text, node) or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )


def test_top3_aligned_section_is_removed_again():
    text = DASH.read_text(encoding="utf-8")
    executable = _calls(text)
    assert "Potenzial · Top 3 Setups" not in executable
    assert "_dashboard_full_alignment_state(" not in text


def test_trade_status_remains_removed():
    text = DASH.read_text(encoding="utf-8")
    assert 'section_line("Trade Status"' not in _calls(text)


def test_intermarket_before_currency_strength():
    text = DASH.read_text(encoding="utf-8")
    assert text.index(
        'st.page_link("pages/intermarket.py"'
    ) < text.index(
        'st.page_link("pages/forex_matrix.py"'
    )


def test_watchlist_is_not_modified_by_dashboard_cleanup():
    text = WATCH.read_text(encoding="utf-8")
    assert "V3.21.4" not in text


def test_dashboard_parses():
    ast.parse(
        DASH.read_text(encoding="utf-8"),
        filename=str(DASH),
    )
