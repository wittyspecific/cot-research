from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
LEGACY_TEST = ROOT / "tests" / "test_v3220_market_regime_vol_credit_research.py"


def _section(text: str, key: str):
    tree = ast.parse(text, filename=str(APP))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for dict_key, value in zip(node.keys, node.values):
            if (
                isinstance(dict_key, ast.Constant)
                and dict_key.value == key
                and isinstance(value, ast.List)
            ):
                lines = text.splitlines()
                return [
                    "\n".join(
                        lines[item.lineno - 1:item.end_lineno]
                    )
                    for item in value.elts
                ]
    raise AssertionError(f"Section not found: {key}")


def test_v324_navigation_places_macro_then_macro_cot_then_analogs_then_market():
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




def test_cleanup_changes_test_contract_only():
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




def test_files_parse():
    for path in (APP, LEGACY_TEST):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
