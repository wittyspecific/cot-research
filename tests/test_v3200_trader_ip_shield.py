from __future__ import annotations

from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
WATCHLIST = ROOT / "pages" / "watchlist.py"
MARKET = ROOT / "pages" / "marktanalyse.py"
FX = ROOT / "pages" / "forex_matrix.py"
JOURNAL = ROOT / "pages" / "trading_journal.py"


def _pages(text):
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pages" for t in node.targets):
            return node.value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "pages":
            return node.value
    raise AssertionError("pages")


def _section(text, name):
    node = _pages(text)
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and key.value == name:
            return value
    raise AssertionError(name)


def _call_name(call):
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        parts = []
        cur = fn
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def test_advanced_hidden_before_navigation():
    text = APP.read_text(encoding="utf-8")
    assert 'pages.pop("ADVANCED", None)' in text
    assert text.index('pages.pop("ADVANCED", None)') < text.index("st.navigation(")


def test_every_advanced_page_has_direct_guard():
    text = APP.read_text(encoding="utf-8")
    paths = []
    for item in _section(text, "ADVANCED").elts:
        if isinstance(item, ast.Call) and item.args and isinstance(item.args[0], ast.Constant):
            paths.append(str(item.args[0].value))
    assert paths
    for rel in paths:
        if not rel.startswith("pages/"):
            continue
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "V3.20.0 · ADVANCED DIRECT ACCESS GUARD" in source, rel
        assert '.get("role", "TRADER")).upper() != "ADMIN"' in source, rel
        assert "st.stop()" in source, rel


def test_new_labs_are_advanced_only():
    text = APP.read_text(encoding="utf-8")
    advanced = "\n".join(ast.get_source_segment(text, n) or "" for n in _section(text, "ADVANCED").elts)
    for rel in ("pages/watchlist_lab.py", "pages/marktanalyse_lab.py", "pages/fx_lab.py"):
        assert rel in advanced


def test_watchlist_no_executable_fixed_methodology_heading():
    text = WATCHLIST.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            source = ast.get_source_segment(text, n) or ""
            assert not ("st.markdown" in source and "## Feste Methodik" in source)


def test_marktanalyse_no_definition_calls_or_visible_trigger_thresholds():
    text = MARKET.read_text(encoding="utf-8")
    tree = ast.parse(text)
    assert not any(isinstance(n, ast.Call) and _call_name(n) == "definition" for n in ast.walk(tree))
    executable = "\n".join(ast.get_source_segment(text, n) or "" for n in ast.walk(tree) if isinstance(n, ast.Call))
    assert 'name="Bullish Trigger · Eintritt ≥90"' not in executable
    assert 'name="Bearish Trigger · Eintritt ≤10"' not in executable
    assert "fig_idx.add_hline(y=90.0" not in executable
    assert "fig_idx.add_hline(y=10.0" not in executable


def test_fx_recipe_hidden_and_yield_coverage_filter_active():
    text = FX.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for n in ast.walk(tree):
        if isinstance(n, ast.With):
            source = ast.get_source_segment(text, n) or ""
            assert 'st.expander("Wie entsteht der COT-Paarbias?"' not in source
    assert "V3.20.0 · YIELD COVERAGE FILTER" in text
    assert '"rates_20d_available"' in text
    assert ".fillna(0).ge(2)" in text


def test_journal_snapshot_expanders_admin_only():
    text = JOURNAL.read_text(encoding="utf-8")
    tree = ast.parse(text)
    labels = {
        "Strategie-Snapshot · beim Trade eingefroren": False,
        "Vollständigen eingefrorenen Snapshot anzeigen": False,
    }
    for n in ast.walk(tree):
        if not isinstance(n, ast.If):
            continue
        if "is_admin" not in (ast.get_source_segment(text, n.test) or ""):
            continue
        body = "\n".join(ast.get_source_segment(text, x) or "" for x in n.body)
        for label in labels:
            if label in body:
                labels[label] = True
    assert all(labels.values()), labels


def test_files_parse():
    for rel in (
        "app.py", "pages/watchlist.py", "pages/marktanalyse.py", "pages/forex_matrix.py",
        "pages/trading_journal.py", "pages/trade_planner.py", "pages/watchlist_lab.py",
        "pages/marktanalyse_lab.py", "pages/fx_lab.py",
    ):
        p = ROOT / rel
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
