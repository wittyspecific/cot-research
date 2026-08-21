from pathlib import Path
import ast

import pandas as pd
import pytest

import src.yield_spreads as ys


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "yield_spreads.py"
PAGE = ROOT / "pages" / "yield_spreads.py"
REQ = ROOT / "requirements.txt"


def _rba_csv():
    lines = [
        "Title,Australian Government 10 year bond,Australian Government 2 year bond",
        "Series ID,FCMYGBAG10D,FCMYGBAG2D",
    ]
    dates = pd.date_range("2026-06-01", periods=40, freq="B")
    for i, date in enumerate(dates):
        lines.append(
            f"{date:%Y-%m-%d},{4.50 + i * 0.001:.3f},{4.10 + i * 0.001:.3f}"
        )
    return "\n".join(lines).encode()


def test_aud_v3164_uses_same_official_rba_url():
    text = ENGINE.read_text(encoding="utf-8")
    assert "AUD_URL_V3162" in text
    assert "fetch_aud_2y_v3164" in text
    assert '"AUD": fetch_aud_2y_v3164' in text


def test_transport_function_has_curl_cffi_and_system_curl_fallback():
    text = ENGINE.read_text(encoding="utf-8")
    assert "from curl_cffi import requests as curl_requests" in text
    assert 'shutil.which("curl")' in text
    assert "impersonate=\"chrome\"" in text


def test_parser_still_uses_exact_rba_series():
    series = ys._parse_rba_2y_v3163(_rba_csv())
    assert len(series) == 40
    assert series.iloc[-1] == pytest.approx(4.139)


def test_requirements_include_curl_cffi():
    if REQ.exists():
        text = REQ.read_text(encoding="utf-8").lower()
        assert "curl_cffi" in text


def test_page_visible_version_is_v3164():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.4 · RBA 403 TRANSPORT FIX" in text


def test_legacy_markers_remain_for_regression_tests():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.1 · HISTORICALLY NORMALIZED 2Y YIELD SPREADS" in text
    assert "V3.16.2 · REPAIRED OFFICIAL 2Y DATA ADAPTERS" in text
    assert "V3.16.3 · OFFICIAL 2Y ADAPTERS COMPLETE" in text


def test_engine_and_page_parse():
    ast.parse(ENGINE.read_text(encoding="utf-8"))
    ast.parse(PAGE.read_text(encoding="utf-8"))
