from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "research_lab.py"


def _text():
    return PAGE.read_text(encoding="utf-8")


def test_v312e_pre_oos_gate_is_visible():
    text = _text()
    assert "4D · Pre-OOS Decision Gate" in text
    assert "PASS / HOLD / REJECT" in text
    assert "Kein neuer Parameter wird hier gesucht." in text


def test_v312e_has_fixed_3x3_region():
    text = _text()
    assert "Fixed 3×3 Parameter Region" in text
    assert "(104, 156, 208)" in (
        ROOT / "src" / "positioning_cross_market.py"
    ).read_text(encoding="utf-8")
    assert "(70.0, 75.0, 80.0)" in (
        ROOT / "src" / "positioning_cross_market.py"
    ).read_text(encoding="utf-8")


def test_v312e_requires_complete_core_fx_universe_for_pass():
    module = (
        ROOT / "src" / "positioning_cross_market.py"
    ).read_text(encoding="utf-8")
    assert "CORE_FX_UNIVERSE_SIZE = 7" in module
    assert "universe_complete" in module
    assert "vollständiges 7er Core-FX-Universum" in module


def test_v312e_does_not_touch_oos_or_production():
    module = (
        ROOT / "src" / "positioning_cross_market.py"
    ).read_text(encoding="utf-8")
    assert "never reads OOS" in module
    assert "st.plotly_chart(" not in _text()
