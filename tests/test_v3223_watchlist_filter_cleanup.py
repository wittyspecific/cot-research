from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"


def _text():
    return WATCH.read_text(encoding="utf-8")


def test_primary_quick_radio_is_removed():
    text = _text()
    tree = ast.parse(text)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "st"
            and fn.attr == "radio"
        ):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "key"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value == "watchlist_primary_view"
            ):
                raise AssertionError("obsolete primary radio still rendered")


def test_visible_filters_are_asset_direction_phase():
    text = _text()
    assert "f_asset, f_dir, f_phase, f_age = st.columns(" in text
    assert '"Setup-Phase"' in text
    assert 'only_all_aligned = st.checkbox(' in text
    assert '"Nur alles aligned"' in text


def test_macro_micro_are_inside_more_filters_expander():
    text = _text()
    tree = ast.parse(text)
    found = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.With) or not node.items:
            continue
        ctx = node.items[0].context_expr
        if not isinstance(ctx, ast.Call):
            continue
        fn = ctx.func
        if not (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "st"
            and fn.attr == "expander"
        ):
            continue
        if (
            ctx.args
            and isinstance(ctx.args[0], ast.Constant)
            and ctx.args[0].value == "Weitere Filter"
        ):
            seg = ast.get_source_segment(text, node) or ""
            assert '"Makro-Phase"' in seg
            assert '"Mikro-Trigger"' in seg
            found = True
            break

    assert found


def test_all_aligned_checkbox_uses_existing_full_alignment():
    text = _text()
    assert "if only_all_aligned and not filtered.empty:" in text
    assert "_full_alignment_state(row)" in text
    assert "filtered = filtered.loc[_aligned_mask].copy()" in text


def test_watchlist_parses():
    ast.parse(_text(), filename=str(WATCH))
