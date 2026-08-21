from pathlib import Path
import ast
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
PAGE = ROOT / "pages" / "seasonality_edge_lab.py"
ENGINE = ROOT / "src" / "seasonality_edge_research.py"


def _app_sections():
    text = APP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    assign = next(
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and (
            (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "pages"
                    for t in node.targets
                )
            )
            or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "pages"
            )
        )
        and isinstance(node.value, ast.Dict)
    )

    out = {}
    for key, value in zip(assign.value.keys, assign.value.values):
        if (
            isinstance(key, ast.Constant)
            and isinstance(value, ast.List)
        ):
            out[str(key.value)] = [
                ast.get_source_segment(text, item) or ""
                for item in value.elts
            ]
    return out


def test_page_is_under_research():
    sections = _app_sections()
    assert "RESEARCH" in sections
    research = "\n".join(sections["RESEARCH"])
    assert "pages/seasonality_edge_lab.py" in research
    assert "Seasonality Edge Lab" in research


def test_research_page_contains_edge_sections():
    text = PAGE.read_text(encoding="utf-8")
    for token in (
        "Current Seasonal State",
        "Turn Window Surface",
        "Phase Shift",
        "Multi-Window Robustness",
        "COT × Seasonal Turn",
        "kein neuer Ranking-Score",
    ):
        assert token in text


def test_engine_exposes_transparent_research_contracts():
    text = ENGINE.read_text(encoding="utf-8")
    for token in (
        "def seasonal_template(",
        "def seasonal_turns(",
        "def offset_forward_surface(",
        "def phase_shift_match(",
        "def stability_table(",
        "def positioning_flow_context(",
        "def transition_hypothesis(",
    ):
        assert token in text

    for forbidden in (
        "ranking_score",
        "setup_score",
        "alignment_score",
        "OrderSend",
        "PositionClose",
    ):
        assert forbidden not in text


def test_synthetic_template_and_surface_work():
    dates = pd.bdate_range("2006-01-02", "2026-08-20")
    t = np.arange(len(dates), dtype=float)
    seasonal = 0.03 * np.sin(2.0 * np.pi * t / 252.0)
    drift = 0.00005 * t
    close = 100.0 * np.exp(drift + seasonal)
    prices = pd.DataFrame({"close": close}, index=dates)

    from src.seasonality_edge_research import (
        offset_forward_surface,
        seasonal_template,
    )

    template = seasonal_template(prices, years=15)
    assert not template.empty
    assert len(template) == 252

    surface = offset_forward_surface(
        prices,
        years=15,
        offsets=(-5, 0, 5),
        horizons=(10, 20),
    )
    assert not surface.empty
    assert set(surface["offset_days"]) == {-5, 0, 5}


def test_files_parse():
    for path in (APP, PAGE, ENGINE):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
