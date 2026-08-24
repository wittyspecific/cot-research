from pathlib import Path
import ast
import hashlib


ROOT = Path(__file__).resolve().parents[1]

OPPORTUNITY = ROOT / "pages" / "opportunity_scanner.py"
WATCHLIST = ROOT / "pages" / "watchlist.py"
MANIFEST = ROOT / "docs" / "V3293_WATCHLIST_SHA256.txt"

MARKER = "V3.29.5.1 · WATCHLIST FLAT DARK POST OVERRIDE"


def _source(path):
    return path.read_text(encoding="utf-8")


def test_v32951_post_override_is_installed():
    source = _source(OPPORTUNITY)

    assert MARKER in source
    assert "def _apply_v32951_watchlist_flat_dark_post_override(" in source


def test_v32951_override_runs_after_legacy_watchlist():
    source = _source(OPPORTUNITY)

    run_pos = source.index(
        "_run_legacy_watchlist_with_routing()"
    )
    style_pos = source.index(
        "_apply_v32951_watchlist_flat_dark_post_override()"
    )

    assert run_pos < style_pos


def test_v32951_removes_watchlist_pill_backgrounds():
    source = _source(OPPORTUNITY)

    assert ".sw-chip," in source
    assert ".sw-signal," in source
    assert ".sw-plan," in source
    assert "background: transparent !important" in source
    assert "border: 0 !important" in source


def test_v32951_kpi_and_legend_use_page_background():
    source = _source(OPPORTUNITY)

    assert ".sw-card," in source
    assert ".sw-legend," in source
    assert "background: var(--qa-bg) !important" in source


def test_v32951_bias_is_readable():
    source = _source(OPPORTUNITY)

    assert ".sw-bias," in source
    assert "color: var(--qa-text) !important" in source
    assert "opacity: 1 !important" in source


def test_v32951_signal_states_are_text_only_but_colored():
    source = _source(OPPORTUNITY)

    assert ".sw-signal.signal-aligned" in source
    assert ".sw-signal.signal-watch" in source
    assert ".sw-signal.signal-neutral" in source
    assert ".sw-signal.signal-ready" in source
    assert "--qa-green: #65D98B" in source
    assert "--qa-red: #FF7373" in source
    assert "--qa-amber: #F2B84B" in source


def test_v32951_original_watchlist_remains_byte_identical():
    expected = MANIFEST.read_text(
        encoding="utf-8"
    ).strip()

    actual = hashlib.sha256(
        WATCHLIST.read_bytes()
    ).hexdigest()

    assert actual == expected


def test_v32951_opportunity_page_parses():
    ast.parse(
        _source(OPPORTUNITY),
        filename=str(OPPORTUNITY),
    )
