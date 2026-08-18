from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"


def _source():
    return WATCH.read_text(encoding="utf-8")


def test_main_watchlist_merges_fx_research_overlay():
    text = _source()
    assert "def _merge_fx_research_into_pipeline(" in text
    assert "pipeline = _merge_fx_research_into_pipeline(" in text
    assert "research_fx_active" in text
    assert "EARLY FX WATCH" in text


def test_main_table_uses_trader_decision_columns():
    text = _source()
    for header in (
        "<th>Bias</th>",
        "<th>Confidence</th>",
        "<th>Timing</th>",
        "<th>Action</th>",
    ):
        assert header in text


def test_soft_research_does_not_overwrite_hard_conflict():
    text = _source()
    assert "research_direction_conflict" in text
    assert "WARTEN · SIGNALKONFLIKT" in text
    assert "hard regime direction wins" in text


def test_separate_early_fx_watch_is_no_longer_rendered():
    text = _source()
    assert "_render_fx_early_research_watch(fx_early_watch)" not in text
    assert "def _render_fx_early_research_watch(" in text


def test_early_fx_filter_exists():
    text = _source()
    assert '"Early FX"' in text
    assert 'filtered["research_fx_active"].fillna(False)' in text


def test_non_fx_falls_back_to_existing_regime_logic():
    text = _source()
    assert "return _legacy_trader_next_step(row)" in text
    assert 'row.get("regime_status", "NORMAL")' in text
