from pathlib import Path
import pandas as pd

from src.analysis import current_signal, hedger_cycle_state

ROOT = Path(__file__).resolve().parents[1]


def _cot(indexes):
    return pd.DataFrame({
        "report_date": pd.date_range("2026-01-01", periods=len(indexes), freq="7D"),
        "commercial_index": indexes,
        "commercial_net": [100 + i for i in range(len(indexes))],
    })


def test_upper_extreme_is_full_hedge_without_direction():
    out = hedger_cycle_state(_cot([70, 85, 95, 100]))
    assert out["phase"] == "EXTREME"
    assert out["direction"] == 0
    assert out["extreme_direction"] == 1
    assert "FULL HEDGE" in out["state"]


def test_leaving_upper_extreme_creates_bullish_release():
    out = hedger_cycle_state(_cot([70, 85, 95, 75]))
    assert out["phase"] == "RELEASE"
    assert out["direction"] == 1
    assert "BULLISH RELEASE" in out["state"]


def test_light_minimal_theme_and_dashboard_are_present():
    style = (ROOT / "src/style.py").read_text()
    app = (ROOT / "app.py").read_text()
    assert '"bg": "#F6F8FB"' in style
    assert '"accent": "#16A34A"' in style
    assert 'pages/dashboard.py' in app
    assert 'V3.9.0' in app


def test_watchlist_explains_state_not_signal():
    text = (ROOT / "pages/watchlist.py").read_text()
    assert "COT 100 bedeutet FULL HEDGE" in text
    assert "BULLISH RELEASE" in text
    assert "WAITING FOR RELEASE" in text


def test_extreme_without_release_is_not_directional_signal():
    row = pd.Series({"commercial_index": 100.0, "retail_index": 0.0})
    assert current_signal(row) == "NEUTRAL"


def test_lower_release_is_bearish_only_after_leaving_extreme():
    out = hedger_cycle_state(_cot([30, 15, 5, 25]))
    assert out["phase"] == "RELEASE"
    assert out["direction"] == -1
    assert "BEARISH RELEASE" in out["state"]
