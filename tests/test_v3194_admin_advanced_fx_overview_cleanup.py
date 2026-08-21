from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
FX = ROOT / "pages" / "forex_matrix.py"
YIELD_PAGE = ROOT / "pages" / "yield_spreads.py"


def _pages_dict(text: str):
    tree = ast.parse(text)
    node = next(
        n
        for n in tree.body
        if isinstance(n, (ast.Assign, ast.AnnAssign))
        and (
            (
                isinstance(n, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "pages"
                    for t in n.targets
                )
            )
            or (
                isinstance(n, ast.AnnAssign)
                and isinstance(n.target, ast.Name)
                and n.target.id == "pages"
            )
        )
    )
    assert isinstance(node.value, ast.Dict)
    return node.value


def _sections(text: str):
    value = _pages_dict(text)
    out = {}
    for key, section in zip(value.keys, value.values):
        if isinstance(key, ast.Constant) and isinstance(section, ast.List):
            out[str(key.value)] = [
                ast.get_source_segment(text, item) or ""
                for item in section.elts
            ]
    return out


def _top_level_index(text: str, predicate):
    tree = ast.parse(text)
    for idx, node in enumerate(tree.body):
        if predicate(node, text):
            return idx
    raise AssertionError("Expected top-level statement not found")


def _is_section(node, text: str, label: str) -> bool:
    if not (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "section_line"
        and node.value.args
        and isinstance(node.value.args[0], ast.Constant)
    ):
        return False
    return node.value.args[0].value == label


def _contains_call(node, func_name: str) -> bool:
    # Search inside one TOP-LEVEL statement/container.
    # This correctly handles calls nested in with/if/try blocks.
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == func_name
        ):
            return True
    return False


def _top_level_container_index_for_call(text: str, func_name: str) -> int:
    tree = ast.parse(text)
    for idx, node in enumerate(tree.body):
        # Ignore function/class definitions: we want runtime page rendering,
        # not the render function's own definition.
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            continue

        if _contains_call(node, func_name):
            return idx

    raise AssertionError(
        f"Runtime call {func_name}(...) not found in top-level page flow"
    )


def test_advanced_is_admin_only_before_navigation():
    text = APP.read_text(encoding="utf-8")
    assert 'if not is_admin:' in text
    assert 'pages.pop("ADVANCED", None)' in text
    assert text.index('pages.pop("ADVANCED", None)') < text.index('st.navigation(')


def test_yield_spreads_visible_only_via_advanced_but_legacy_source_contract_preserved():
    text = APP.read_text(encoding="utf-8")
    sections = _sections(text)

    research = sections["RESEARCH"]
    advanced = sections["ADVANCED"]

    currency_idx = next(
        i for i, s in enumerate(research)
        if "pages/forex_matrix.py" in s
    )
    yield_idx = next(
        i for i, s in enumerate(research)
        if "pages/yield_spreads.py" in s
    )

    assert yield_idx == currency_idx + 1

    assert any(
        "pages/yield_spreads.py" in s
        for s in advanced
    )

    assert "REMOVE LEGACY RESEARCH YIELD PAGE BEFORE NAVIGATION" in text
    assert 'getattr(page, "title", None) != "Yield Spreads"' in text
    assert text.index(
        "REMOVE LEGACY RESEARCH YIELD PAGE BEFORE NAVIGATION"
    ) < text.index("st.navigation(")


def test_fx_overview_render_order_and_detail_removed():
    text = FX.read_text(encoding="utf-8")

    cot_section = _top_level_index(
        text,
        lambda node, src: _is_section(
            node, src, "COT Währungsübersicht"
        ),
    )

    cot_table = _top_level_container_index_for_call(
        text,
        "render_currency_table",
    )

    combined_section = _top_level_index(
        text,
        lambda node, src: _is_section(
            node, src, "COT + Yield Spreads Währungsübersicht"
        ),
    )

    pairs_call = _top_level_container_index_for_call(
        text,
        "render_pairs",
    )

    assert cot_section < cot_table < combined_section < pairs_call

    assert 'key="v3170_fundamental_currency"' not in text
    assert "_v3170_detail =" not in text


def test_pair_table_no_visible_20y_history_column():
    text = FX.read_text(encoding="utf-8")
    tree = ast.parse(text)
    render_pairs = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "render_pairs"
    )
    segment = ast.get_source_segment(text, render_pairs) or ""

    assert '"seasonality_detail"' not in segment
    assert '"20J-Historie"' not in segment
    assert '"seasonality_compact"' in segment


def test_yield_page_is_labeled_advanced():
    text = YIELD_PAGE.read_text(encoding="utf-8")
    assert '"Advanced · Rates"' in text


def test_files_parse():
    for path in (APP, FX, YIELD_PAGE):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
