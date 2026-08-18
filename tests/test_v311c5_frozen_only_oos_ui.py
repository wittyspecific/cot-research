from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v311c5_oos_reveal_is_frozen_only():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    assert "FROZEN-ONLY OOS" in text
    assert "frozen_candidates_from_scan" in text
    assert "Nur die vor OOS eingefrorenen Hypothesen werden angezeigt." in text


def test_v311c5_oos_block_has_no_general_top20_selection():
    text = (ROOT / "pages/research_lab.py").read_text(encoding="utf-8")
    start = text.index('"Frozen OOS Reveal"')
    end = text.index(
        "V3.11C ist weiterhin ein Single-Market-Scanner",
        start,
    )
    block = text[start:end]
    assert ".head(20)" not in block
    assert 'robustness_scan["sample_ok"]' not in block
