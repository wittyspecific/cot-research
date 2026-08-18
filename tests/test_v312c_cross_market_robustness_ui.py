from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "research_lab.py"


def _text():
    return PAGE.read_text(encoding="utf-8")


def test_v312c_has_cross_market_robustness_stage():
    text = _text()
    assert "4B · Cross-Market Robustness" in text
    assert "Core-FX Robustness berechnen" in text
    for market in ("EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD"):
        assert market in text


def test_v312c_cross_market_ranking_is_train_validation_only():
    text = _text()
    assert "Kein OOS fließt in diesen " in text
    assert "Cross-Market Score ein." in text
    assert "aggregate_cross_market_scans" in text
    assert "cross_market_candidate_detail" in text


def test_v312c_uses_same_positioning_episode_engine_for_each_market():
    text = _text()
    assert "_cross_market_scan_one" in text
    assert "build_positioning_episode_dataset" in text
    assert "scan_parameter_robustness" in text


def test_v312c_does_not_add_direct_plotly_renderer():
    assert "st.plotly_chart(" not in _text()
