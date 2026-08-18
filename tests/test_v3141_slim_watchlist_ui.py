
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"

def _text():
    return WATCH.read_text(encoding="utf-8")

def test_v3141_slim_headers_are_present():
    text = _text()
    for value in ("<th>Makro</th>", "<th>Mikro</th>", "<th>Bias</th>", "<th>Plan</th>", "<th>Signal</th>"):
        assert value in text

def test_v3141_no_delta_values_in_primary_renderer():
    text = _text()
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_render_trader_table")
    lines = text.splitlines()
    body = "\n".join(lines[node.lineno - 1:node.end_lineno])
    assert "Δ1" not in body
    assert "Δ2" not in body
    assert "Δ4" not in body

def test_v3141_filters_remain_compact_with_fresh_micro():
    assert '["Alle", "Fresh Micro", "Aligned", "Watch", "Context Ready"]' in _text()

def test_v3141_keeps_dual_horizon_data_logic():
    text = _text()
    assert 'row.get("dual_156w_direction"' in text
    assert 'row.get("dual_26w_direction"' in text
    assert "LONG ONLY" in text
    assert "SHORT ONLY" in text
    assert "Pullback abwarten" in text
    assert "Auf Anstieg warten" in text
