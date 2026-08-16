
from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis import cot_index, rolling_percentile

REPORT_GROUPS = {
    "disaggregated": [
        ("producer", "Producer / Merchant", "Physischer Hedger-Kontext"),
        ("managed_money", "Managed Money", "Institutionelle Spekulation"),
        ("swap", "Swap Dealer", "Separater Swap-/Intermediär-Kontext"),
        ("other_reportable", "Other Reportables", "Sonstige Reportables"),
        ("nonreportable", "Nonreportable", "Nicht meldepflichtige Positionen"),
    ],
    "tff": [
        ("dealer", "Dealer / Intermediary", "Intermediärs-/Kundengeschäft"),
        ("asset_manager", "Asset Manager / Institutional", "Institutionelle Positionierung"),
        ("leveraged_funds", "Leveraged Funds", "Gehebelte / spekulative Positionierung"),
        ("other_reportable", "Other Reportables", "Sonstige Reportables"),
        ("nonreportable", "Nonreportable", "Nicht meldepflichtige Positionen"),
    ],
}


def enrich_report_positioning(
    df: pd.DataFrame,
    report_type: str,
    index_weeks: int = 26,
    validation_weeks: int = 156,
) -> pd.DataFrame:
    out = df.copy()
    oi = out["open_interest_all"].replace(0, np.nan)

    for key, _, _ in REPORT_GROUPS[report_type]:
        long_col = f"{key}_long"
        short_col = f"{key}_short"

        if long_col not in out.columns or short_col not in out.columns:
            continue

        net = out[long_col] - out[short_col]
        net_oi = net / oi

        out[f"{key}_net"] = net
        out[f"{key}_net_oi"] = net_oi
        out[f"{key}_index"] = cot_index(net, int(index_weeks))
        out[f"{key}_raw_percentile"] = rolling_percentile(
            net, int(validation_weeks)
        )
        out[f"{key}_net_oi_percentile"] = rolling_percentile(
            net_oi, int(validation_weeks)
        )
        out[f"{key}_change_4w"] = net.diff(4)
        out[f"{key}_net_oi_change_4w"] = net_oi.diff(4)
        out[f"{key}_change_4w_percentile"] = rolling_percentile(
            out[f"{key}_change_4w"], int(validation_weeks)
        )

    return out


def latest_group_table(
    enriched: pd.DataFrame,
    report_type: str,
) -> pd.DataFrame:
    if enriched is None or enriched.empty:
        return pd.DataFrame()

    latest = enriched.iloc[-1]
    rows = []

    for key, label, role in REPORT_GROUPS[report_type]:
        rows.append({
            "Gruppe": label,
            "Rolle": role,
            "Netto": latest.get(f"{key}_net", np.nan),
            "Raw-Netto-%ile": latest.get(f"{key}_raw_percentile", np.nan),
            "Netto/OI": latest.get(f"{key}_net_oi", np.nan),
            "Netto/OI-%ile": latest.get(f"{key}_net_oi_percentile", np.nan),
            "COT-Index 26W": latest.get(f"{key}_index", np.nan),
            "Netto Δ4W": latest.get(f"{key}_change_4w", np.nan),
            "Netto/OI Δ4W": latest.get(f"{key}_net_oi_change_4w", np.nan),
        })

    return pd.DataFrame(rows)


def raw_oi_relation(
    raw_percentile: float,
    oi_percentile: float,
) -> str:
    if not np.isfinite(raw_percentile) or not np.isfinite(oi_percentile):
        return "ZU WENIG HISTORIE"

    raw_high = raw_percentile >= 80
    raw_low = raw_percentile <= 20
    oi_high = oi_percentile >= 80
    oi_low = oi_percentile <= 20

    if raw_high and oi_high:
        return "BEIDE HISTORISCH HOCH"
    if raw_low and oi_low:
        return "BEIDE HISTORISCH NIEDRIG"
    if raw_high and not oi_high:
        return "RAW HOCH · OI-NORMALISIERT NICHT HOCH"
    if raw_low and not oi_low:
        return "RAW NIEDRIG · OI-NORMALISIERT NICHT NIEDRIG"
    if oi_high and not raw_high:
        return "OI-NORMALISIERT HOCH · RAW NICHT HOCH"
    if oi_low and not raw_low:
        return "OI-NORMALISIERT NIEDRIG · RAW NICHT NIEDRIG"

    return "KEIN STRUKTURELLER KONFLIKT"
