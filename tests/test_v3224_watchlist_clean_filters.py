from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"
CORE = ROOT / "src" / "watchlist_macro_micro.py"
SCAN = ROOT / "src" / "watchlist.py"
MICRO = ROOT / "src" / "micro_trigger.py"
SEASON = ROOT / "src" / "watchlist_seasonality.py"


def _text():
    return WATCH.read_text(encoding="utf-8")


def test_clean_filter_structure():
    text = _text()
    assert "f_asset, f_dir, f_phase, f_age = st.columns(" in text
    assert '"Assetklasse"' in text
    assert '"Richtung"' in text
    assert '"Setup-Phase"' in text
    assert 'only_all_aligned = st.checkbox(' in text
    assert '"Nur alles aligned"' in text


def test_no_primary_quick_filter_radio():
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
                raise AssertionError("watchlist_primary_view radio still rendered")


def test_only_all_aligned_is_seasonality_confirmation_filter():
    text = _text()

    assert "if only_all_aligned and not filtered.empty:" in text
    assert "filtered = filtered.loc[_aligned_mask].copy()" in text

    tree = ast.parse(text)

    found = False
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "bool"
            and len(node.args) == 1
        ):
            continue

        get_call = node.args[0]
        if not (
            isinstance(get_call, ast.Call)
            and isinstance(get_call.func, ast.Attribute)
            and get_call.func.attr == "get"
        ):
            continue

        alignment_call = get_call.func.value
        if not (
            isinstance(alignment_call, ast.Call)
            and isinstance(alignment_call.func, ast.Name)
            and alignment_call.func.id == "_full_alignment_state"
            and len(alignment_call.args) == 1
            and isinstance(alignment_call.args[0], ast.Name)
            and alignment_call.args[0].id == "row"
        ):
            continue

        if not (
            len(get_call.args) >= 2
            and isinstance(get_call.args[0], ast.Constant)
            and get_call.args[0].value == "aligned"
            and isinstance(get_call.args[1], ast.Constant)
            and get_call.args[1].value is False
        ):
            continue

        found = True
        break

    assert found, "existing _full_alignment_state(row).get('aligned', False) contract missing"



def test_setup_phase_multiselect_remains():
    text = _text()
    assert 'phase_filter = st.multiselect(' in text
    assert 'placeholder="Alle Phasen"' in text
    assert 'key="watchlist_setup_phase_filter"' in text


def test_macro_micro_are_collapsed():
    text = _text()
    tree = ast.parse(text)
    expander = None
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
            expander = node
            break

    assert expander is not None
    seg = ast.get_source_segment(text, expander) or ""
    assert '"Makro-Phase"' in seg
    assert '"Mikro-Trigger"' in seg


def test_existing_phase_logic_survives():
    text = _text()
    assert "def _watchlist_setup_phase(" in text
    assert "def _watchlist_phase_filter_match(" in text
    assert "def _full_alignment_state(" in text
    assert '"Phase / Plan"' in text


def test_core_files_untouched():
    for path in (CORE, SCAN, MICRO, SEASON):
        text = path.read_text(encoding="utf-8")
        assert "V3.22.4" not in text


def test_watchlist_parses():
    ast.parse(_text(), filename=str(WATCH))
