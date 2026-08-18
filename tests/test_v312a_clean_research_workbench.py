from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "research_lab.py"


def _text():
    return PAGE.read_text(encoding="utf-8")


def test_research_market_is_not_in_global_sidebar_anymore():
    text = _text()
    assert "with st.sidebar:" not in text
    assert "1 · Research Context" in text
    assert "Markt / Kontrakt" in text


def test_state_basis_and_flow_families_are_explicitly_separated():
    text = _text()
    assert '"State-Basis"' in text
    assert "Flow-Familien im Scan" in text
    assert "Percentile · Raw Contracts · Net/OI" in text


def test_forward_horizon_is_part_of_research_context():
    text = _text()
    assert "v312_research_horizon" in text
    assert '("Forward", f"{int(dyn_horizon)}W")' in text


def test_only_positioning_dynamics_is_primary_visible_workflow():
    text = _text()
    assert "V3.12B · VERTICAL POSITIONING WORKFLOW" in text
    assert "Archiv · Legacy Research" in text
    assert "tab5 = st.container()" in text
    assert "tab5, tab1, tab2, tab3, tab4 = st.tabs(" not in text


def test_monotonicity_state_is_research_context_bound():
    text = _text()
    assert "v311c1_monotonic_candidate|{research_context_key}" in text


def test_no_direct_streamlit_plotly_chart_is_added():
    text = _text()
    assert "st.plotly_chart(" not in text
