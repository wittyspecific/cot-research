from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"


def _text():
    return WATCH.read_text(encoding="utf-8")


def test_v3142_watchlist_has_season_column():
    text = _text()
    assert "<th>Season</th>" in text
    assert "calculate_market_20y_multi_seasonality" in text


def test_v3142_renderer_has_no_delta_values():
    text = _text()
    tree = ast.parse(text)
    node = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and n.name == "_render_trader_table"
    )
    lines = text.splitlines()
    body = "\n".join(lines[node.lineno - 1:node.end_lineno])
    assert "Δ1" not in body
    assert "Δ2" not in body
    assert "Δ4" not in body


def test_v3142_uses_release_priority_core():
    text = _text()
    assert "classify_macro_micro_trade" in text
    assert "Makro</b>&nbsp;= 156W · aktiv ab Release" in text
    assert "Makro führt nach Release" in text
