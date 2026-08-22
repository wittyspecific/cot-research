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


def test_v324_navigation_places_macro_then_analog_then_fx_then_market():
    text = APP.read_text(encoding="utf-8")
    research = _section(text, "RESEARCH")

    fx_matrix = next(i for i, item in enumerate(research) if "pages/forex_matrix.py" in item)
    yld = next(i for i, item in enumerate(research) if "pages/yield_spreads.py" in item)
    macro = next(i for i, item in enumerate(research) if "pages/macro_model_library.py" in item)
    analog = next(i for i, item in enumerate(research) if "pages/cot_price_analog.py" in item)
    fx_analog = next(i for i, item in enumerate(research) if "pages/fx_relative_cot_analog.py" in item)
    market = next(i for i, item in enumerate(research) if "pages/market_regime.py" in item)
    vol = next(i for i, item in enumerate(research) if "pages/volatility_regime.py" in item)
    credit = next(i for i, item in enumerate(research) if "pages/credit_stress.py" in item)

    assert yld == fx_matrix + 1
    assert macro == yld + 1
    assert analog == macro + 1
    assert fx_analog == analog + 1
    assert market == fx_analog + 1
    assert vol == market + 1
    assert credit == vol + 1




def test_cleanup_changes_test_contract_only():
    source = LEGACY_TEST.read_text(encoding="utf-8")

    assert "pages/macro_model_library.py" in source
    assert "pages/cot_price_analog.py" in source
    assert "pages/fx_relative_cot_analog.py" in source
    assert "assert fx_analog[0] == analog[0] + 1" in source
    assert "assert market == fx_analog[0] + 1" in source




def test_files_parse():
    for path in (APP, LEGACY_TEST):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
