from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
PAGE = ROOT / "pages" / "analog_diagnostics.py"

MARKER = "V3.20.0 · ADVANCED DIRECT ACCESS GUARD"


def test_analog_diagnostics_has_direct_guard():
    source = PAGE.read_text(
        encoding="utf-8"
    )

    assert MARKER in source
    assert "st.stop" in source


def test_analog_diagnostics_parses():
    ast.parse(
        PAGE.read_text(
            encoding="utf-8"
        ),
        filename=str(PAGE),
    )


def test_analog_diagnostics_is_in_advanced():
    text = APP.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        text,
        filename=str(APP),
    )

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Dict,
        ):
            continue

        for key, value in zip(
            node.keys,
            node.values,
        ):
            if (
                isinstance(
                    key,
                    ast.Constant,
                )
                and isinstance(
                    key.value,
                    str,
                )
                and "ADVANCED"
                in key.value.upper()
                and isinstance(
                    value,
                    ast.List,
                )
            ):
                paths = []

                for item in value.elts:
                    if (
                        isinstance(
                            item,
                            ast.Call,
                        )
                        and item.args
                        and isinstance(
                            item.args[0],
                            ast.Constant,
                        )
                    ):
                        paths.append(
                            str(
                                item.args[0].value
                            )
                        )

                assert (
                    "pages/analog_diagnostics.py"
                    in paths
                )
                return

    raise AssertionError(
        "ADVANCED navigation not found"
    )
