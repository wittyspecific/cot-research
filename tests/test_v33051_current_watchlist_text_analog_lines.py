from pathlib import Path
import ast
import hashlib


ROOT = Path(__file__).resolve().parents[1]

OPPORTUNITY = ROOT / "pages" / "opportunity_scanner.py"
WATCHLIST = ROOT / "pages" / "watchlist.py"
MARKET = ROOT / "pages" / "market_analysis_hub.py"
MANIFEST = ROOT / "docs" / "V3293_WATCHLIST_SHA256.txt"


def _source(path):
    return path.read_text(
        encoding="utf-8"
    )


def test_v33051_targets_current_wl9_renderer():
    source = _source(OPPORTUNITY)

    assert "V3.30.5.1 · CURRENT WL9 WATCHLIST TEXT OVERRIDE" in source
    assert ".wl9-chip" in source
    assert ".wl9-phase" in source
    assert ".wl9-plan" in source
    assert ".wl9-signal" in source
    assert ".wl9-bias" in source
    assert ".wl9-arrow" in source


def test_v33051_macro_micro_are_text_only():
    source = _source(OPPORTUNITY)

    assert ".wl9-chip.macro-bull" in source
    assert ".wl9-chip.macro-bear" in source
    assert ".wl9-chip.micro-bull" in source
    assert ".wl9-chip.micro-bear" in source
    assert "background: transparent !important" in source
    assert "color: var(--v33051-green) !important" in source
    assert "color: var(--v33051-red) !important" in source


def test_v33051_phase_plan_signal_are_white_text():
    source = _source(OPPORTUNITY)

    assert ".wl9-phase" in source
    assert ".wl9-plan" in source
    assert ".wl9-signal" in source
    assert "color: var(--v33051-text) !important" in source


def test_v33051_original_watchlist_stays_byte_identical():
    if not MANIFEST.exists():
        return

    expected = MANIFEST.read_text(
        encoding="utf-8"
    ).strip().split()[0]

    actual = hashlib.sha256(
        WATCHLIST.read_bytes()
    ).hexdigest()

    assert actual == expected


def test_v33051_uses_real_analog_lines():
    source = _source(MARKET)

    assert "V3.30.5.1 · REAL MULTI-HORIZON ANALOG LINE CHART" in source
    assert "go.Figure()" in source
    assert "go.Scatter(" in source
    assert "Median-Pfad" in source
    assert "25%-Pfad" in source
    assert "75%-Pfad" in source
    assert "(2, 4, 8, 12)" in source
    assert "st.bar_chart(" not in source


def test_v33051_preserves_current_watchlist_contract_not_stale_helpers():
    source = _source(WATCHLIST)

    assert "def _render_trader_table(" in source
    assert "classify_macro_micro_trade" in source
    assert "wl9-chip" in source
    assert "wl9-signal" in source


def test_v33051_files_parse():
    for path in (
        OPPORTUNITY,
        MARKET,
        WATCHLIST,
    ):
        ast.parse(
            _source(path),
            filename=str(path),
        )
