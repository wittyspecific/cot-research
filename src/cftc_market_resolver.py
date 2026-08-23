from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any, Iterable

import pandas as pd


_CODE_KEYS = (
    "cftc_contract_market_code",
    "contract_market_code",
    "cftc_market_code",
)


def _normalize(value: Any) -> str:
    text = str(value or "").upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())


def _records(universe: Any) -> list[dict[str, Any]]:
    if universe is None:
        return []
    if isinstance(universe, pd.DataFrame):
        return universe.to_dict(orient="records")
    if isinstance(universe, dict):
        for key in ("data", "records", "markets", "results"):
            value = universe.get(key)
            if isinstance(value, (list, tuple)):
                return [dict(item) for item in value if isinstance(item, dict)]
        if universe and all(not isinstance(value, (list, tuple, dict)) for value in universe.values()):
            return [dict(universe)]
        return [dict(value) for value in universe.values() if isinstance(value, dict)]
    if isinstance(universe, (list, tuple)):
        return [dict(item) for item in universe if isinstance(item, dict)]
    return []


def _code_from_row(row: dict[str, Any]) -> str | None:
    lower = {str(key).lower(): value for key, value in row.items()}
    for key in _CODE_KEYS:
        value = lower.get(key)
        if value not in (None, ""):
            return str(value).strip()

    for key, value in row.items():
        normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if "contractmarketcode" in normalized_key or "cftcmarketcode" in normalized_key:
            if value not in (None, ""):
                return str(value).strip()
    return None


def _row_text(row: dict[str, Any]) -> str:
    parts = []
    for key, value in row.items():
        key_text = str(key).lower()
        if "code" in key_text:
            continue
        if value is None:
            continue
        parts.append(str(value))
    return _normalize(" ".join(parts))


def _tenor(text: str) -> int | None:
    normalized = _normalize(text)
    match = re.search(r"\b(2|5|10|30)\s*(?:YEAR|YR|Y)\b", normalized)
    return int(match.group(1)) if match else None


def _instrument_kind(text: str) -> str | None:
    normalized = _normalize(text)
    if "BOND" in normalized:
        return "BOND"
    if "NOTE" in normalized or "T NOTE" in normalized:
        return "NOTE"
    return None


def _score(alias: str, candidate: str) -> float:
    a = _normalize(alias)
    c = _normalize(candidate)
    if not a or not c:
        return 0.0

    if "TREASURY" in a and "TREASURY" not in c:
        return 0.0

    a_tenor = _tenor(a)
    c_tenor = _tenor(c)
    if a_tenor is not None and c_tenor is not None and a_tenor != c_tenor:
        return 0.0

    a_kind = _instrument_kind(a)
    c_kind = _instrument_kind(c)
    if a_kind is not None and c_kind is not None and a_kind != c_kind:
        return 0.0

    if a == c:
        score = 110.0
    elif a in c:
        score = 100.0
    else:
        a_tokens = set(a.split())
        c_tokens = set(c.split())
        overlap = len(a_tokens & c_tokens) / max(1, len(a_tokens))
        ratio = SequenceMatcher(None, a, c).ratio()
        score = max(90.0 * overlap, 82.0 * ratio)

    if "ULTRA" in c and "ULTRA" not in a:
        score -= 12.0
    if "MICRO" in c and "MICRO" not in a:
        score -= 12.0

    return score


def resolve_universe_alias(
    universe: Any,
    aliases: Iterable[str],
    *,
    minimum_score: float = 72.0,
) -> dict[str, Any] | None:
    """Resolve a CFTC universe row directly from human-readable aliases.

    This is a fallback for markets that are absent from CLASSIC_MARKETS. It
    never invents a CFTC contract code: the code must exist in the universe.
    """

    best: tuple[float, dict[str, Any], str] | None = None

    for row in _records(universe):
        code = _code_from_row(row)
        if not code:
            continue

        candidate = _row_text(row)
        if not candidate:
            continue

        row_best = 0.0
        row_alias = ""
        for alias in aliases:
            score = _score(str(alias), candidate)
            if score > row_best:
                row_best = score
                row_alias = str(alias)

        if best is None or row_best > best[0]:
            best = (row_best, row, row_alias)

    if best is None or best[0] < float(minimum_score):
        return None

    score, row, alias = best
    code = _code_from_row(row)
    if not code:
        return None

    return {
        "cftc_contract_market_code": code,
        "matched_alias": alias,
        "match_score": float(score),
        "resolved_via": "universe_alias",
        "market_text": _row_text(row),
    }
