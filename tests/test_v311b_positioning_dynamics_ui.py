from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v311b_research_lab_exposes_positioning_dynamics_tab():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "Positioning Dynamics" in text
    assert "104W vs. 156W vs. 208W" in text
    assert "Depth & Duration" in text
    assert "Velocity & Acceleration" in text


def test_v311b_uses_research_core_without_changing_production_config():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "build_positioning_episode_dataset" in text
    assert "summarize_window_threshold_grid" in text
    assert "quantile_effect_study" in text
    assert "compare_flow_measures" in text
    assert "Produktionsparameter bleiben unverändert" in text


def test_v311b_tff_dealer_is_explicitly_a_hypothesis():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "TFF Dealer/Intermediary" in text
    assert "nicht als physische Hedger" in text
    assert "Research-Test" in text


def test_v311b_avoids_threshold_pseudoreplication_for_feature_studies():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert 'dynamics_events.get("window_weeks")' in text
    assert 'dynamics_events.get("threshold_upper")' in text
    assert "nicht künstlich mehrfach" in text
