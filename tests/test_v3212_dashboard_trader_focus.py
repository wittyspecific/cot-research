from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "pages" / "dashboard.py"


def _executable_calls(text: str) -> str:
    tree = ast.parse(text)
    return "\n".join(
        ast.get_source_segment(text, node) or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )


def test_research_pulse_is_not_rendered():
    text = DASH.read_text(encoding="utf-8")
    executable = _executable_calls(text)
    assert 'section_line("Research Pulse"' not in executable


def test_quick_access_has_requested_four_destinations():
    text = DASH.read_text(encoding="utf-8")
    executable = _executable_calls(text)

    # V3.29.x dashboard quick access follows the consolidated trader workflow.
    for path in (
        "pages/trade_planner.py",
        "pages/opportunity_scanner.py",
        "pages/market_analysis_hub.py",
        "pages/currency_strength_hub.py",
    ):
        assert f'st.page_link("{path}"' in executable


def test_journal_and_prop_desk_are_not_quick_access_links():
    text = DASH.read_text(encoding="utf-8")
    executable = _executable_calls(text)

    assert 'st.page_link("pages/trading_journal.py"' not in executable
    assert 'st.page_link("pages/prop_desk.py"' not in executable


def test_intermarket_precedes_currency_strength():
    text = DASH.read_text(encoding="utf-8")

    # V3.29.x: Intermarket is integrated into Marktanalyse.
    market = text.index(
        'st.page_link("pages/market_analysis_hub.py"'
    )
    currency = text.index(
        'st.page_link("pages/currency_strength_hub.py"'
    )

    assert market < currency


def test_trade_status_is_no_longer_rendered():
    text = DASH.read_text(encoding="utf-8")
    executable = _executable_calls(text)
    assert 'section_line("Trade Status"' not in executable


def test_core_dashboard_sections_survive():
    text = DASH.read_text(encoding="utf-8")
    executable = _executable_calls(text)

    assert 'section_line("Offene Positionen"' in executable
    assert 'metric_card("Equity"' in executable
    assert 'metric_card("Open Risk"' in executable


def test_dashboard_parses():
    ast.parse(
        DASH.read_text(encoding="utf-8"),
        filename=str(DASH),
    )
