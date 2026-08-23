from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"

WRAPPERS = {
    "pages/advanced_market_regime.py": "pages/market_regime.py",
    "pages/advanced_credit_stress.py": "pages/credit_stress.py",
    "pages/advanced_seasonality_edge_lab.py": "pages/seasonality_edge_lab.py",
}

ORIGINAL_DIAGNOSTICS = set(
    WRAPPERS.values()
)

MARKER = "V3.20.0 · ADVANCED DIRECT ACCESS GUARD"


def _groups():
    text = APP.read_text(
        encoding="utf-8"
    )
    tree = ast.parse(
        text,
        filename=str(APP),
    )

    groups = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue

        for key, value in zip(
            node.keys,
            node.values,
        ):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.List)
            ):
                groups[key.value] = value

    return text, groups


def _paths(text, node):
    paths = []

    for item in node.elts:
        for child in ast.walk(item):
            if (
                isinstance(child, ast.Constant)
                and isinstance(child.value, str)
                and child.value.startswith("pages/")
            ):
                paths.append(child.value)
                break

    return paths


def test_research_menu_is_slimmer():
    from pathlib import Path
    import ast
    app = Path(__file__).resolve().parents[1] / "app.py"
    text = app.read_text(encoding="utf-8")
    tree = ast.parse(text)
    research = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "RESEARCH" and isinstance(value, ast.List):
                research = value
    assert research is not None
    paths = []
    for item in research.elts:
        for child in ast.walk(item):
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value.startswith("pages/"):
                paths.append(child.value); break
    assert paths == ["pages/opportunity_scanner.py", "pages/market_analysis_hub.py", "pages/currency_strength_hub.py", "pages/macro_regime.py"]


def test_advanced_uses_guarded_wrappers():
    text, groups = _groups()

    advanced = _paths(
        text,
        groups["ADVANCED"],
    )

    for wrapper in WRAPPERS:
        assert wrapper in advanced

        source = (
            ROOT
            / wrapper
        ).read_text(
            encoding="utf-8"
        )

        assert MARKER in source
        assert "runpy.run_path" in source

        ast.parse(
            source,
            filename=wrapper,
        )


def test_original_diagnostic_pages_still_parse():
    for rel in ORIGINAL_DIAGNOSTICS:
        path = ROOT / rel

        ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )


def test_german_visible_titles():
    text = APP.read_text(
        encoding="utf-8"
    )

    for token in (
        'title="Beobachtungsliste"',
        'title="Makro-Zyklus"',
        'title="Makro × COT"',
        'title="COT × Preis-Analog"',
        'title="FX-COT-Analog"',
        'title="Volatilität"',
        'title="COT × Saisonalität"',
        'title="Marktregime"',
        'title="Kreditstress"',
        'title="Saisonalitäts-Labor"',
    ):
        assert token in text


def test_app_parses():
    ast.parse(
        APP.read_text(
            encoding="utf-8"
        ),
        filename=str(APP),
    )
