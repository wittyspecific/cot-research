from pathlib import Path
import ast

import pandas as pd
import pytest

from src.yield_spreads import (
    _parse_cad_lookup_html,
    _parse_rba_2y_v3163,
    _parse_rbnz_2y_v3163,
)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "yield_spreads.py"
PAGE = ROOT / "pages" / "yield_spreads.py"


def test_cad_html_parser_finds_selected_2y_table():
    dates = pd.date_range("2026-06-01", periods=40, freq="B")
    table = pd.DataFrame(
        {
            "Date": dates.strftime("%Y-%m-%d"),
            "2 year V39051": [2.50 + i * 0.001 for i in range(40)],
        }
    )
    html = table.to_html(index=False).encode()
    series = _parse_cad_lookup_html(html)
    assert len(series) == 40
    assert series.index[-1] == dates[-1]
    assert series.iloc[-1] == pytest.approx(2.539)


def test_rba_ragged_csv_parser_handles_variable_width_rows():
    lines = [
        "Title,Australian Government 10 year bond,Australian Government 2 year bond",
        "Series ID,FCMYGBAG10D,FCMYGBAG2D",
    ]
    dates = pd.date_range("2026-06-01", periods=40, freq="B")
    for i, date in enumerate(dates):
        lines.append(
            f"{date:%Y-%m-%d},{4.50 + i * 0.001:.3f},{4.10 + i * 0.001:.3f}"
        )
    lines.append("footer")
    lines.append("note,one,two,three,four,six")
    raw = "\n".join(lines).encode()

    series = _parse_rba_2y_v3163(raw)
    assert len(series) == 40
    assert series.iloc[-1] == pytest.approx(4.139)


def test_rbnz_parser_finds_exact_benchmark_set(monkeypatch):
    dates = pd.date_range("2026-06-01", periods=40, freq="B")
    rows = [
        ["", "Secondary market government bond closing yields (%pa)", "", "", ""],
        ["Date", "1 year", "2 year", "5 year", "10 year"],
    ]
    for i, date in enumerate(dates):
        rows.append(
            [
                date.strftime("%Y-%m-%d"),
                2.8 + i * 0.001,
                3.0 + i * 0.001,
                3.2 + i * 0.001,
                3.4 + i * 0.001,
            ]
        )
    frame = pd.DataFrame(rows)

    import src.yield_spreads as ys
    monkeypatch.setattr(ys, "_read_excel_candidates", lambda raw: [frame])

    series = _parse_rbnz_2y_v3163(b"x")
    assert len(series) == 40
    assert series.iloc[-1] == pytest.approx(3.039)


def test_v3163_fetchers_override_only_broken_three():
    text = ENGINE.read_text(encoding="utf-8")
    assert '"CAD": fetch_cad_2y_v3163' in text
    assert '"AUD": fetch_aud_2y_v3163' in text
    assert '"NZD": fetch_nzd_2y_v3163' in text
    assert '"EUR": fetch_eur_2y_v3162' in text
    assert '"GBP": fetch_gbp_2y_v3162' in text
    assert '"JPY": fetch_jpy_2y_v3162' in text


def test_v3163_page_version_visible():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.3 · OFFICIAL 2Y ADAPTERS COMPLETE" in text


def test_engine_page_parse():
    ast.parse(ENGINE.read_text(encoding="utf-8"))
    ast.parse(PAGE.read_text(encoding="utf-8"))
