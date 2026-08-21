from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
TRADER_PAGE = ROOT / "pages" / "intermarket.py"
LAB_PAGE = ROOT / "pages" / "intermarket_lab.py"
ENGINE = ROOT / "src" / "intermarket.py"


def _pages_sections(text: str):
    tree = ast.parse(text)
    pages_node = next(
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and (
            (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "pages"
                    for target in node.targets
                )
            )
            or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "pages"
            )
        )
    )
    assert isinstance(pages_node.value, ast.Dict)

    sections = {}
    for key, value in zip(
        pages_node.value.keys,
        pages_node.value.values,
    ):
        if (
            isinstance(key, ast.Constant)
            and isinstance(value, ast.List)
        ):
            sections[str(key.value)] = [
                ast.get_source_segment(text, item) or ""
                for item in value.elts
            ]
    return sections


def test_intermarket_lab_is_registered_in_advanced():
    text = APP.read_text(encoding="utf-8")
    sections = _pages_sections(text)

    assert any(
        "pages/intermarket_lab.py" in item
        for item in sections["ADVANCED"]
    )
    assert not any(
        "pages/intermarket_lab.py" in item
        for item in sections.get("RESEARCH", [])
    )


def test_advanced_remains_admin_only():
    text = APP.read_text(encoding="utf-8")
    assert 'pages.pop("ADVANCED", None)' in text
    assert text.index(
        'pages.pop("ADVANCED", None)'
    ) < text.index("st.navigation(")


def test_trader_intermarket_hides_methodology():
    text = TRADER_PAGE.read_text(encoding="utf-8")

    assert 'section_line(\n    "Beziehungsmatrix"' not in text
    assert "matrix = relationship_matrix()" not in text
    assert "Datenprobleme ·" not in text
    assert "row['rationale']" not in text
    assert 'row["rationale"]' not in text
    assert "<div class=\"im-rel\">" not in text


def test_trader_intermarket_keeps_analysis_outputs():
    text = TRADER_PAGE.read_text(encoding="utf-8")

    assert "INTERMARKET_RELATIONSHIPS" in text
    assert "evaluate_relationships" in text
    assert "Makro" in text
    assert "Mikro" in text
    assert "GESAMT" in text
    assert "FX ↔ Commodity" in text
    assert "Risk ↔ Volatility" in text


def test_legacy_intermarket_source_contracts_survive():
    text = TRADER_PAGE.read_text(encoding="utf-8")

    assert "V3.15.5 · EXPANDED COT INTERMARKET UNIVERSE" in text
    assert "Research-/Confluence-Layer" in text
    assert "weder Watchlist-Signal" in text
    assert "Trade-Entscheidung" in text


def test_lab_contains_analysis_path_and_data_quality():
    text = LAB_PAGE.read_text(encoding="utf-8")

    assert "V3.19.5 · INTERMARKET LAB" in text
    assert "relationship_matrix" in text
    assert "Beziehungsmatrix" in text
    assert "Gewicht" in text
    assert "Regimeabhängig" in text
    assert "Warum" in text
    assert "Datenqualität" in text
    assert "Aktuelle Rohbewertung" in text


def test_engine_is_not_modified_by_v3195_marker():
    text = ENGINE.read_text(encoding="utf-8")
    assert "V3.19.5" not in text


def test_files_parse():
    for path in (APP, TRADER_PAGE, LAB_PAGE, ENGINE):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
