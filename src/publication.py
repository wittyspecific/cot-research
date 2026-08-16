
from __future__ import annotations

import pandas as pd

# Von der CFTC explizit dokumentierte Sonderveröffentlichungen.
SPECIAL_RELEASES = {
    # ION-Störung 2023
    "2023-01-31": "2023-02-24",
    "2023-02-07": "2023-03-03",
    "2023-02-14": "2023-03-08",
    "2023-02-21": "2023-03-10",
    "2023-02-28": "2023-03-14",
    "2023-03-07": "2023-03-16",

    # CFTC-Veröffentlichungsunterbrechung / Catch-up 2025
    "2025-09-30": "2025-11-19",
    "2025-10-07": "2025-11-21",
    "2025-10-14": "2025-11-25",
    "2025-10-21": "2025-12-02",
    "2025-10-28": "2025-12-05",
    "2025-11-04": "2025-12-09",
    "2025-11-10": "2025-12-10",
    "2025-11-18": "2025-12-12",
    "2025-11-25": "2025-12-15",
    "2025-12-02": "2025-12-17",
    "2025-12-09": "2025-12-19",
    "2025-12-16": "2025-12-23",
    "2025-12-23": "2025-12-29",
}

SPECIAL_RELEASES = {
    pd.Timestamp(k): pd.Timestamp(v)
    for k, v in SPECIAL_RELEASES.items()
}


def publication_info(report_date) -> dict:
    rd = pd.Timestamp(report_date).normalize()

    if rd in SPECIAL_RELEASES:
        return {
            "report_date": rd,
            "publication_date": SPECIAL_RELEASES[rd],
            "publication_status": "VERIFIED SPECIAL RELEASE",
        }

    return {
        "report_date": rd,
        "publication_date": rd + pd.Timedelta(days=3),
        "publication_status": "ESTIMATED STANDARD RELEASE",
    }


def backtest_available_date(report_date) -> pd.Timestamp:
    """
    Konservativer Verfügbarkeitsanker für Tagesdaten-Backtests.

    Bei verifizierten Sonderveröffentlichungen wird das tatsächliche
    Publikationsdatum genutzt. Für gewöhnliche historische Wochen verwendet
    der Bot den Dienstag eine Woche nach dem Positionsstichtag, weil die CFTC
    keine vollständige historische Liste aller Holiday-Release-Daten anbietet.
    """
    info = publication_info(report_date)

    if info["publication_status"].startswith("VERIFIED"):
        return pd.Timestamp(info["publication_date"])

    return pd.Timestamp(info["report_date"]) + pd.Timedelta(days=7)
