from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"
CORE = ROOT / "src" / "watchlist_macro_micro.py"
SCAN = ROOT / "src" / "watchlist.py"
MICRO = ROOT / "src" / "micro_trigger.py"
SEASON = ROOT / "src" / "watchlist_seasonality.py"


def _text():
    return WATCH.read_text(encoding="utf-8")


def test_visible_filter_row_has_signal_age():
    text = _text()
    assert "f_asset, f_dir, f_phase, f_age = st.columns(" in text
    assert '"Signalalter"' in text
    assert 'key="watchlist_signal_age_filter"' in text

    for option in (
        "Diese Woche",
        "1W",
        "2W",
        "3W",
        "4W+",
    ):
        assert f'"{option}"' in text


def test_signal_age_uses_existing_age_contracts():
    text = _text()

    assert 'micro.get("age_weeks", -1)' in text
    assert 'row.get("macro_status_age_weeks", -1)' in text
    assert "def _watchlist_setup_signal_age_bucket(" in text


def test_signal_age_filter_is_applied_before_all_aligned():
    text = _text()

    age_pos = text.index(
        "if signal_age_filter and not filtered.empty:"
    )
    aligned_pos = text.index(
        "if only_all_aligned and not filtered.empty:"
    )

    assert age_pos < aligned_pos
    assert "_watchlist_signal_age_filter_match(" in text
    assert "filtered = filtered.loc[_age_mask].copy()" in text


def test_existing_clean_filter_structure_survives():
    text = _text()

    assert '"Assetklasse"' in text
    assert '"Richtung"' in text
    assert '"Setup-Phase"' in text
    assert '"Nur alles aligned"' in text
    assert 'with st.expander("Weitere Filter", expanded=False):' in text
    assert '"Makro-Phase"' in text
    assert '"Mikro-Trigger"' in text


def test_no_new_cot_decision_logic_in_age_helper():
    text = _text()

    start = text.index(
        "def _watchlist_setup_signal_age_weeks("
    )
    end = text.index(
        "\ndef _render_trader_table(",
        start,
    )
    segment = text[start:end]

    for forbidden in (
        "MICRO_TRIGGER_UPPER",
        "MICRO_TRIGGER_LOWER",
        "macro_156w_state(",
        "micro_26w_state(",
        "commercial_index >= 90",
        "commercial_index <= 10",
    ):
        assert forbidden not in segment


def test_core_files_untouched():
    for path in (
        CORE,
        SCAN,
        MICRO,
        SEASON,
    ):
        text = path.read_text(encoding="utf-8")
        assert "V3.22.5" not in text


def test_watchlist_parses():
    ast.parse(
        _text(),
        filename=str(WATCH),
    )
