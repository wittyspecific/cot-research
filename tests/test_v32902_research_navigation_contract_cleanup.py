from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

TARGETS = (
    ROOT / "tests" / "test_v3153_intermarket_page.py",
    ROOT / "tests" / "test_v3160_yield_spreads.py",
    ROOT / "tests" / "test_v354_sidebar_sections.py",
)


def test_v32902_cleanup_targets_parse():
    for path in TARGETS:
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )


def test_v32902_old_sidebar_contracts_are_gone():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in TARGETS
    )

    # These exact old assumptions must no longer be executable test code.
    assert 'assert \'"pages/intermarket.py"\' in text' not in combined
    assert 'text.index(\'"pages/watchlist.py"\')' not in combined
    assert 'text.index("pages/watchlist.py")' not in combined


def test_v32902_new_four_page_contract_is_referenced():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in TARGETS
    )

    assert "pages/opportunity_scanner.py" in combined
    assert "pages/market_analysis_hub.py" in combined
