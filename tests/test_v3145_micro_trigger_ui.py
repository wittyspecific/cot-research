from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"
SCAN = ROOT / "src" / "watchlist.py"


def _function_body(name):
    text = WATCH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = text.splitlines()
    return "\n".join(lines[node.lineno - 1:node.end_lineno])


def test_v3145_live_kpi_copy_uses_trigger_90_10():
    body = _function_body("_kpis")
    assert "COT Index 26W · Trigger 90/10" in body
    assert "COT Index 26W · 80/20" not in body


def test_v3145_fresh_micro_filter_exists():
    text = WATCH.read_text(encoding="utf-8")
    assert '"Fresh Micro"' in text
    assert 'filtered["micro_trigger_fresh"]' in text


def test_v3145_scan_uses_full_history_trigger():
    text = SCAN.read_text(encoding="utf-8")
    assert "latest_micro_trigger(" in text
    assert '"micro_trigger_direction"' in text
    assert '"micro_trigger_age_weeks"' in text
    assert '"micro_trigger_fresh"' in text


def test_v3145_fresh_trigger_rows_reach_pipeline():
    text = WATCH.read_text(encoding="utf-8")
    assert "def _ensure_fresh_micro_rows(" in text
    assert "pipeline = _ensure_fresh_micro_rows(" in text


def test_v3145_renderer_shows_trigger_age():
    body = _function_body("_render_trader_table")
    assert "diese Woche" in body
    assert 'f"vor {micro_age}W"' in body


def test_v3145_watchlist_parses():
    ast.parse(WATCH.read_text(encoding="utf-8"))
