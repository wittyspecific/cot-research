from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


FX_PAIRS = {
    "EURUSD": {"base": "EUR", "quote": "USD", "ticker": "EURUSD=X"},
    "GBPUSD": {"base": "GBP", "quote": "USD", "ticker": "GBPUSD=X"},
    "AUDUSD": {"base": "AUD", "quote": "USD", "ticker": "AUDUSD=X"},
    "NZDUSD": {"base": "NZD", "quote": "USD", "ticker": "NZDUSD=X"},
    "USDJPY": {"base": "USD", "quote": "JPY", "ticker": "JPY=X"},
    "USDCHF": {"base": "USD", "quote": "CHF", "ticker": "CHF=X"},
    "USDCAD": {"base": "USD", "quote": "CAD", "ticker": "CAD=X"},
    "EURGBP": {"base": "EUR", "quote": "GBP", "ticker": "EURGBP=X"},
    "EURJPY": {"base": "EUR", "quote": "JPY", "ticker": "EURJPY=X"},
    "EURCHF": {"base": "EUR", "quote": "CHF", "ticker": "EURCHF=X"},
    "EURAUD": {"base": "EUR", "quote": "AUD", "ticker": "EURAUD=X"},
    "EURNZD": {"base": "EUR", "quote": "NZD", "ticker": "EURNZD=X"},
    "EURCAD": {"base": "EUR", "quote": "CAD", "ticker": "EURCAD=X"},
    "GBPJPY": {"base": "GBP", "quote": "JPY", "ticker": "GBPJPY=X"},
    "GBPCHF": {"base": "GBP", "quote": "CHF", "ticker": "GBPCHF=X"},
    "GBPAUD": {"base": "GBP", "quote": "AUD", "ticker": "GBPAUD=X"},
    "GBPNZD": {"base": "GBP", "quote": "NZD", "ticker": "GBPNZD=X"},
    "GBPCAD": {"base": "GBP", "quote": "CAD", "ticker": "GBPCAD=X"},
    "AUDJPY": {"base": "AUD", "quote": "JPY", "ticker": "AUDJPY=X"},
    "AUDCHF": {"base": "AUD", "quote": "CHF", "ticker": "AUDCHF=X"},
    "AUDNZD": {"base": "AUD", "quote": "NZD", "ticker": "AUDNZD=X"},
    "AUDCAD": {"base": "AUD", "quote": "CAD", "ticker": "AUDCAD=X"},
    "NZDJPY": {"base": "NZD", "quote": "JPY", "ticker": "NZDJPY=X"},
    "NZDCHF": {"base": "NZD", "quote": "CHF", "ticker": "NZDCHF=X"},
    "NZDCAD": {"base": "NZD", "quote": "CAD", "ticker": "NZDCAD=X"},
    "CADJPY": {"base": "CAD", "quote": "JPY", "ticker": "CADJPY=X"},
    "CADCHF": {"base": "CAD", "quote": "CHF", "ticker": "CADCHF=X"},
    "CHFJPY": {"base": "CHF", "quote": "JPY", "ticker": "CHFJPY=X"},
}


TFF_GROUPS = (
    ("dealer", "Dealer / Intermediary", "INTERMEDIARY CONTEXT"),
    ("asset_manager", "Asset Manager", "INSTITUTIONAL"),
    ("leveraged_funds", "Leveraged Funds", "MOMENTUM / SPECULATIVE"),
    ("nonreportable", "Nonreportable", "RESIDUAL / CONTRARIAN"),
)


PRICE_FEATURES = (
    "price_return_4w",
    "price_return_8w",
    "price_return_13w",
    "price_return_26w",
    "price_drawdown_26w",
    "price_vs_ma13",
    "price_vs_ma26",
    "price_vol_13w",
)


def _finite(value: Any) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan
    return value if np.isfinite(value) else np.nan


def _clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if prices is None or len(prices) == 0:
        return pd.DataFrame()

    if isinstance(prices, pd.Series):
        prices = prices.to_frame("close")

    frame = prices.copy()
    frame.index = pd.to_datetime(
        frame.index,
        errors="coerce",
    )
    frame = frame[
        ~frame.index.isna()
    ].sort_index()

    if getattr(
        frame.index,
        "tz",
        None,
    ) is not None:
        frame.index = frame.index.tz_localize(
            None
        )

    frame = frame[
        ~frame.index.duplicated(
            keep="last"
        )
    ]

    lookup = {
        str(col)
        .strip()
        .lower()
        .replace(" ", "_"): col
        for col in frame.columns
    }

    close_col = next(
        (
            lookup[key]
            for key in (
                "close",
                "adj_close",
                "adjclose",
            )
            if key in lookup
        ),
        None,
    )

    if close_col is None:
        return pd.DataFrame()

    high_col = lookup.get("high")
    low_col = lookup.get("low")

    out = pd.DataFrame(
        index=frame.index
    )
    out["close"] = pd.to_numeric(
        frame[close_col],
        errors="coerce",
    )
    out["high"] = (
        pd.to_numeric(
            frame[high_col],
            errors="coerce",
        )
        if high_col is not None
        else out["close"]
    )
    out["low"] = (
        pd.to_numeric(
            frame[low_col],
            errors="coerce",
        )
        if low_col is not None
        else out["close"]
    )

    out = out.dropna(
        subset=["close"]
    )
    out["high"] = out[
        "high"
    ].fillna(
        out["close"]
    )
    out["low"] = out[
        "low"
    ].fillna(
        out["close"]
    )

    return out


def _rolling_percentile(
    series: pd.Series,
    *,
    window: int = 156,
    min_periods: int = 52,
) -> pd.Series:
    x = pd.to_numeric(
        series,
        errors="coerce",
    ).astype(float)

    def _rank(values):
        values = np.asarray(
            values,
            dtype=float,
        )
        values = values[
            np.isfinite(values)
        ]
        if len(values) < int(
            min_periods
        ):
            return np.nan

        current = values[-1]
        return float(
            100.0
            * np.mean(
                values <= current
            )
        )

    return x.rolling(
        int(window),
        min_periods=int(
            min_periods
        ),
    ).apply(
        _rank,
        raw=True,
    )


def build_currency_leg(
    enriched_cot: pd.DataFrame,
    currency: str,
    *,
    release_lag_days: int = 3,
) -> pd.DataFrame:
    """
    Build a TFF currency-leg history.

    Net positioning is expressed as Net/OI for the currency future itself.
    The COT snapshot is conservatively available at report_date + 3 days.
    """
    if (
        enriched_cot is None
        or enriched_cot.empty
    ):
        return pd.DataFrame()

    x = enriched_cot.copy()

    required = {
        "report_date",
        "open_interest_all",
    }
    if not required.issubset(
        x.columns
    ):
        return pd.DataFrame()

    x["report_date"] = pd.to_datetime(
        x["report_date"],
        errors="coerce",
    )

    x = (
        x.dropna(
            subset=["report_date"]
        )
        .sort_values(
            "report_date"
        )
        .drop_duplicates(
            "report_date",
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    if len(x) < 30:
        return pd.DataFrame()

    oi = pd.to_numeric(
        x["open_interest_all"],
        errors="coerce",
    ).replace(
        0,
        np.nan,
    )

    out = pd.DataFrame(
        {
            "report_date": x[
                "report_date"
            ],
            "availability_date": (
                x["report_date"]
                + pd.to_timedelta(
                    int(
                        release_lag_days
                    ),
                    unit="D",
                )
            ),
        }
    )

    for key, _, _ in TFF_GROUPS:
        long_col = f"{key}_long"
        short_col = f"{key}_short"

        if (
            long_col not in x.columns
            or short_col not in x.columns
        ):
            continue

        longs = pd.to_numeric(
            x[long_col],
            errors="coerce",
        )
        shorts = pd.to_numeric(
            x[short_col],
            errors="coerce",
        )

        net_oi = (
            longs - shorts
        ) / oi

        out[
            f"{key}_net_oi"
        ] = net_oi

        percentile = _rolling_percentile(
            net_oi,
            window=156,
            min_periods=52,
        )
        out[
            f"{key}_percentile_centered"
        ] = (
            percentile - 50.0
        ) / 50.0

        for weeks in (
            1,
            2,
            4,
        ):
            out[
                f"{key}_net_oi_delta_{weeks}w"
            ] = net_oi.diff(
                weeks
            )

    out["currency"] = str(
        currency
    )

    return out.reset_index(
        drop=True
    )


def _merge_currency_legs(
    base_leg: pd.DataFrame | None,
    quote_leg: pd.DataFrame | None,
    *,
    base: str,
    quote: str,
) -> pd.DataFrame:
    """
    Create pair-direction relative COT features.

    Non-USD cross:
        relative = base currency future - quote currency future

    XXXUSD:
        relative = XXX currency future

    USDXXX:
        relative = - XXX currency future

    USD therefore acts as the quotation/reference leg; no DXY COT proxy is
    forced into a bilateral FX pair.
    """
    base = str(
        base
    ).upper()
    quote = str(
        quote
    ).upper()

    if base == "USD" and quote == "USD":
        return pd.DataFrame()

    if quote == "USD":
        if (
            base_leg is None
            or base_leg.empty
        ):
            return pd.DataFrame()

        merged = base_leg.copy()
        sign = 1.0

        pair = pd.DataFrame(
            {
                "report_date": merged[
                    "report_date"
                ],
                "availability_date": merged[
                    "availability_date"
                ],
            }
        )

        for key, _, _ in TFF_GROUPS:
            for suffix in (
                "net_oi",
                "percentile_centered",
                "net_oi_delta_1w",
                "net_oi_delta_2w",
                "net_oi_delta_4w",
            ):
                col = (
                    f"{key}_{suffix}"
                )
                if col in merged.columns:
                    pair[
                        f"relative_{col}"
                    ] = (
                        sign
                        * pd.to_numeric(
                            merged[col],
                            errors="coerce",
                        )
                    )

        return pair.reset_index(
            drop=True
        )

    if base == "USD":
        if (
            quote_leg is None
            or quote_leg.empty
        ):
            return pd.DataFrame()

        merged = quote_leg.copy()
        sign = -1.0

        pair = pd.DataFrame(
            {
                "report_date": merged[
                    "report_date"
                ],
                "availability_date": merged[
                    "availability_date"
                ],
            }
        )

        for key, _, _ in TFF_GROUPS:
            for suffix in (
                "net_oi",
                "percentile_centered",
                "net_oi_delta_1w",
                "net_oi_delta_2w",
                "net_oi_delta_4w",
            ):
                col = (
                    f"{key}_{suffix}"
                )
                if col in merged.columns:
                    pair[
                        f"relative_{col}"
                    ] = (
                        sign
                        * pd.to_numeric(
                            merged[col],
                            errors="coerce",
                        )
                    )

        return pair.reset_index(
            drop=True
        )

    if (
        base_leg is None
        or quote_leg is None
        or base_leg.empty
        or quote_leg.empty
    ):
        return pd.DataFrame()

    left = base_leg.copy().sort_values(
        "availability_date"
    )
    right = quote_leg.copy().sort_values(
        "availability_date"
    )

    merged = pd.merge_asof(
        left,
        right,
        on="availability_date",
        direction="nearest",
        tolerance=pd.Timedelta(
            days=7
        ),
        suffixes=(
            "_base",
            "_quote",
        ),
    )

    merged = merged.dropna(
        subset=[
            "availability_date"
        ]
    )

    pair = pd.DataFrame(
        {
            "report_date": pd.to_datetime(
                merged[
                    "report_date_base"
                ],
                errors="coerce",
            ),
            "availability_date": pd.to_datetime(
                merged[
                    "availability_date"
                ],
                errors="coerce",
            ),
        }
    )

    for key, _, _ in TFF_GROUPS:
        for suffix in (
            "net_oi",
            "percentile_centered",
            "net_oi_delta_1w",
            "net_oi_delta_2w",
            "net_oi_delta_4w",
        ):
            stem = (
                f"{key}_{suffix}"
            )
            base_col = (
                f"{stem}_base"
            )
            quote_col = (
                f"{stem}_quote"
            )

            if (
                base_col in merged.columns
                and quote_col
                in merged.columns
            ):
                pair[
                    f"relative_{stem}"
                ] = (
                    pd.to_numeric(
                        merged[
                            base_col
                        ],
                        errors="coerce",
                    )
                    - pd.to_numeric(
                        merged[
                            quote_col
                        ],
                        errors="coerce",
                    )
                )

    return pair.reset_index(
        drop=True
    )


def _align_prices(
    prices: pd.DataFrame,
    availability_dates: pd.Series,
) -> pd.DataFrame:
    p = _clean_prices(
        prices
    )
    if p.empty:
        return pd.DataFrame()

    right = p.reset_index()
    index_col = right.columns[
        0
    ]
    right = right.rename(
        columns={
            index_col: "price_date"
        }
    )
    right["price_date"] = pd.to_datetime(
        right["price_date"],
        errors="coerce",
    )
    right = (
        right.dropna(
            subset=["price_date"]
        )
        .sort_values(
            "price_date"
        )
    )

    left = pd.DataFrame(
        {
            "availability_date": pd.to_datetime(
                availability_dates,
                errors="coerce",
            )
        }
    )
    left = (
        left.dropna(
            subset=[
                "availability_date"
            ]
        )
        .sort_values(
            "availability_date"
        )
    )

    if (
        left.empty
        or right.empty
    ):
        return pd.DataFrame()

    return pd.merge_asof(
        left,
        right,
        left_on="availability_date",
        right_on="price_date",
        direction="backward",
        allow_exact_matches=True,
    )


def build_fx_pair_setup(
    prices: pd.DataFrame,
    *,
    pair: str,
    base_cot: pd.DataFrame | None,
    quote_cot: pd.DataFrame | None,
) -> dict[str, Any]:
    pair = str(
        pair
    ).upper()

    spec = FX_PAIRS.get(
        pair
    )
    if spec is None:
        return {
            "available": False,
            "reason": (
                f"Unbekanntes FX-Paar: {pair}"
            ),
        }

    base = spec[
        "base"
    ]
    quote = spec[
        "quote"
    ]

    base_leg = (
        None
        if base == "USD"
        else build_currency_leg(
            base_cot,
            base,
        )
    )
    quote_leg = (
        None
        if quote == "USD"
        else build_currency_leg(
            quote_cot,
            quote,
        )
    )

    relative = _merge_currency_legs(
        base_leg,
        quote_leg,
        base=base,
        quote=quote,
    )

    if relative.empty:
        return {
            "available": False,
            "reason": (
                "Keine gemeinsame relative COT-Historie verfügbar."
            ),
        }

    aligned = _align_prices(
        prices,
        relative[
            "availability_date"
        ],
    )

    if aligned.empty:
        return {
            "available": False,
            "reason": (
                "FX-Preisreihe konnte nicht mit COT-Veröffentlichungen ausgerichtet werden."
            ),
        }

    frame = relative.copy().reset_index(
        drop=True
    )

    aligned = aligned.reset_index(
        drop=True
    )

    if len(aligned) != len(frame):
        common = min(
            len(aligned),
            len(frame),
        )
        frame = frame.iloc[
            -common:
        ].reset_index(
            drop=True
        )
        aligned = aligned.iloc[
            -common:
        ].reset_index(
            drop=True
        )

    frame[
        "price_date"
    ] = aligned[
        "price_date"
    ].values
    frame[
        "close"
    ] = aligned[
        "close"
    ].values
    frame[
        "high"
    ] = aligned[
        "high"
    ].values
    frame[
        "low"
    ] = aligned[
        "low"
    ].values

    close = pd.to_numeric(
        frame["close"],
        errors="coerce",
    )

    for weeks in (
        4,
        8,
        13,
        26,
    ):
        frame[
            f"price_return_{weeks}w"
        ] = close.pct_change(
            weeks,
            fill_method=None,
        )

    frame[
        "price_drawdown_26w"
    ] = (
        close
        / close.rolling(
            26,
            min_periods=13,
        ).max()
        - 1.0
    )

    frame[
        "price_vs_ma13"
    ] = (
        close
        / close.rolling(
            13,
            min_periods=8,
        ).mean()
        - 1.0
    )

    frame[
        "price_vs_ma26"
    ] = (
        close
        / close.rolling(
            26,
            min_periods=13,
        ).mean()
        - 1.0
    )

    logret = np.log(
        close
        / close.shift(1)
    )

    frame[
        "price_vol_13w"
    ] = (
        logret.rolling(
            13,
            min_periods=8,
        ).std(
            ddof=0
        )
        * np.sqrt(
            52.0
        )
    )

    level_features = [
        col
        for col in frame.columns
        if (
            col.startswith(
                "relative_"
            )
            and (
                col.endswith(
                    "_net_oi"
                )
                or col.endswith(
                    "_percentile_centered"
                )
            )
        )
    ]

    flow_features = [
        col
        for col in frame.columns
        if (
            col.startswith(
                "relative_"
            )
            and "_delta_"
            in col
        )
    ]

    return {
        "available": True,
        "reason": "",
        "pair": pair,
        "base": base,
        "quote": quote,
        "ticker": spec[
            "ticker"
        ],
        "frame": frame,
        "price_features": [
            col
            for col in PRICE_FEATURES
            if col in frame.columns
        ],
        "level_features": level_features,
        "flow_features": flow_features,
    }


def _robust_scale(
    frame: pd.DataFrame,
    columns: list[str],
) -> tuple[pd.Series, pd.Series]:
    values = frame[
        columns
    ].apply(
        pd.to_numeric,
        errors="coerce",
    )

    median = values.median(
        axis=0
    )

    mad = (
        values.sub(
            median,
            axis=1,
        )
        .abs()
        .median(
            axis=0
        )
    )

    robust_sigma = (
        mad
        / 0.6744897501960817
    )

    std = values.std(
        axis=0,
        ddof=0,
    )

    scale = robust_sigma.where(
        robust_sigma > 1e-9,
        std,
    )

    scale = scale.where(
        scale > 1e-9,
        1.0,
    )

    return median, scale


def _similarity(
    current: pd.Series,
    candidates: pd.DataFrame,
    columns: list[str],
    reference: pd.DataFrame,
) -> pd.Series:
    columns = [
        col
        for col in columns
        if (
            col in current.index
            and col in candidates.columns
        )
    ]

    if not columns:
        return pd.Series(
            np.nan,
            index=candidates.index,
            dtype=float,
        )

    median, scale = _robust_scale(
        reference,
        columns,
    )

    current_z = (
        pd.to_numeric(
            current[
                columns
            ],
            errors="coerce",
        )
        - median
    ) / scale

    candidate_z = (
        candidates[
            columns
        ].apply(
            pd.to_numeric,
            errors="coerce",
        )
        - median
    ).div(
        scale,
        axis=1,
    )

    diff = candidate_z.sub(
        current_z,
        axis=1,
    )

    count = diff.notna().sum(
        axis=1
    )

    mse = (
        diff.pow(
            2
        )
        .sum(
            axis=1,
            skipna=True,
        )
        .div(
            count.replace(
                0,
                np.nan,
            )
        )
    )

    rmse = np.sqrt(
        mse.clip(
            lower=0.0
        )
    )

    sim = (
        100.0
        * np.exp(
            -0.5
            * rmse.pow(
                2
            )
        )
    )

    minimum = max(
        2,
        int(
            np.ceil(
                len(
                    columns
                )
                * 0.50
            )
        ),
    )

    return sim.where(
        count >= minimum
    ).clip(
        0.0,
        100.0,
    )


def _entry_price(
    prices: pd.DataFrame,
    anchor: pd.Timestamp,
) -> tuple[
    pd.Timestamp | None,
    float,
]:
    p = _clean_prices(
        prices
    )
    if p.empty:
        return None, np.nan

    pos = p.index.searchsorted(
        pd.Timestamp(
            anchor
        ),
        side="right",
    ) - 1

    if pos < 0:
        return None, np.nan

    date = pd.Timestamp(
        p.index[
            int(
                pos
            )
        ]
    )

    return (
        date,
        _finite(
            p.iloc[
                int(
                    pos
                )
            ]["close"]
        ),
    )


def _future_close(
    prices: pd.DataFrame,
    target: pd.Timestamp,
) -> float:
    p = _clean_prices(
        prices
    )
    if p.empty:
        return np.nan

    pos = p.index.searchsorted(
        pd.Timestamp(
            target
        ),
        side="left",
    )

    if pos >= len(
        p
    ):
        return np.nan

    return _finite(
        p.iloc[
            int(
                pos
            )
        ]["close"]
    )


def _forward_outcome(
    prices: pd.DataFrame,
    anchor: pd.Timestamp,
    *,
    excursion_horizon_weeks: int,
) -> dict[str, Any]:
    p = _clean_prices(
        prices
    )
    entry_date, entry = _entry_price(
        p,
        anchor,
    )

    out = {
        "entry_price_date": entry_date,
        "entry_price": entry,
    }

    if (
        entry_date is None
        or not np.isfinite(
            entry
        )
        or entry <= 0
    ):
        for weeks in (
            2,
            4,
            8,
            12,
        ):
            out[
                f"return_{weeks}w"
            ] = np.nan

        out[
            "downside_excursion"
        ] = np.nan
        out[
            "upside_excursion"
        ] = np.nan
        return out

    for weeks in (
        2,
        4,
        8,
        12,
    ):
        future = _future_close(
            p,
            entry_date
            + pd.Timedelta(
                weeks=int(
                    weeks
                )
            ),
        )

        out[
            f"return_{weeks}w"
        ] = (
            future
            / entry
            - 1.0
            if np.isfinite(
                future
            )
            else np.nan
        )

    end = (
        entry_date
        + pd.Timedelta(
            weeks=int(
                excursion_horizon_weeks
            )
        )
    )

    path = p.loc[
        (
            p.index
            > entry_date
        )
        & (
            p.index
            <= end
        )
    ]

    if path.empty:
        out[
            "downside_excursion"
        ] = np.nan
        out[
            "upside_excursion"
        ] = np.nan
    else:
        out[
            "downside_excursion"
        ] = float(
            path[
                "low"
            ].min()
            / entry
            - 1.0
        )
        out[
            "upside_excursion"
        ] = float(
            path[
                "high"
            ].max()
            / entry
            - 1.0
        )

    return out


def _spaced_matches(
    ranked: pd.DataFrame,
    *,
    top_n: int,
    min_spacing_weeks: int,
) -> pd.DataFrame:
    selected = []
    dates = []

    for idx, row in ranked.iterrows():
        date = pd.Timestamp(
            row[
                "availability_date"
            ]
        )

        if all(
            abs(
                (
                    date - other
                ).days
            )
            >= int(
                min_spacing_weeks
            ) * 7
            for other in dates
        ):
            selected.append(
                idx
            )
            dates.append(
                date
            )

        if len(
            selected
        ) >= int(
            top_n
        ):
            break

    return ranked.loc[
        selected
    ].copy()


def analyze_fx_relative_analogs(
    prices: pd.DataFrame,
    *,
    pair: str,
    base_cot: pd.DataFrame | None,
    quote_cot: pd.DataFrame | None,
    top_n: int = 8,
    min_spacing_weeks: int = 13,
    exclude_recent_weeks: int = 26,
    outcome_horizon_weeks: int = 8,
) -> dict[str, Any]:
    setup = build_fx_pair_setup(
        prices,
        pair=pair,
        base_cot=base_cot,
        quote_cot=quote_cot,
    )

    if not setup.get(
        "available"
    ):
        return {
            "available": False,
            "reason": setup.get(
                "reason",
                "FX Relative COT Setup nicht verfügbar.",
            ),
        }

    frame = setup[
        "frame"
    ].copy()

    all_features = (
        setup[
            "price_features"
        ]
        + setup[
            "level_features"
        ]
        + setup[
            "flow_features"
        ]
    )

    if not all_features:
        return {
            "available": False,
            "reason": (
                "Keine nutzbaren FX-Analog-Features."
            ),
        }

    completeness = (
        frame[
            all_features
        ]
        .notna()
        .sum(
            axis=1
        )
    )

    minimum = max(
        5,
        int(
            np.ceil(
                len(
                    all_features
                )
                * 0.55
            )
        ),
    )

    valid = frame.loc[
        completeness
        >= minimum
    ].copy()

    if len(
        valid
    ) < 20:
        return {
            "available": False,
            "reason": (
                "Zu wenig gemeinsame FX-Preis-/COT-Historie mit ausreichender Feature-Abdeckung."
            ),
        }

    current = valid.iloc[
        -1
    ].copy()

    current_date = pd.Timestamp(
        current[
            "availability_date"
        ]
    )

    cutoff = (
        current_date
        - pd.Timedelta(
            weeks=max(
                int(
                    exclude_recent_weeks
                ),
                int(
                    outcome_horizon_weeks
                )
                + 2,
            )
        )
    )

    candidates = valid.loc[
        pd.to_datetime(
            valid[
                "availability_date"
            ]
        )
        <= cutoff
    ].copy()

    if len(
        candidates
    ) < int(
        top_n
    ):
        return {
            "available": False,
            "reason": (
                "Nicht genügend historische FX-Analog-Kandidaten."
            ),
        }

    reference = valid.loc[
        pd.to_datetime(
            valid[
                "availability_date"
            ]
        )
        <= current_date
    ].copy()

    candidates[
        "price_similarity"
    ] = _similarity(
        current,
        candidates,
        setup[
            "price_features"
        ],
        reference,
    )

    candidates[
        "relative_cot_level_similarity"
    ] = _similarity(
        current,
        candidates,
        setup[
            "level_features"
        ],
        reference,
    )

    candidates[
        "relative_cot_flow_similarity"
    ] = _similarity(
        current,
        candidates,
        setup[
            "flow_features"
        ],
        reference,
    )

    components = pd.DataFrame(
        {
            "price": candidates[
                "price_similarity"
            ],
            "level": candidates[
                "relative_cot_level_similarity"
            ],
            "flow": candidates[
                "relative_cot_flow_similarity"
            ],
        },
        index=candidates.index,
    )

    weights = pd.Series(
        {
            "price": 0.50,
            "level": 0.25,
            "flow": 0.25,
        }
    )

    denominator = (
        components.notna()
        .mul(
            weights,
            axis=1,
        )
        .sum(
            axis=1
        )
    )

    candidates[
        "similarity"
    ] = (
        components.mul(
            weights,
            axis=1,
        )
        .sum(
            axis=1,
            skipna=True,
        )
        / denominator.replace(
            0.0,
            np.nan,
        )
    )

    ranked = (
        candidates.dropna(
            subset=[
                "similarity"
            ]
        )
        .sort_values(
            [
                "similarity",
                "relative_cot_flow_similarity",
            ],
            ascending=[
                False,
                False,
            ],
        )
    )

    matches = _spaced_matches(
        ranked,
        top_n=int(
            top_n
        ),
        min_spacing_weeks=int(
            min_spacing_weeks
        ),
    )

    outcomes = []

    for idx, row in matches.iterrows():
        outcome = _forward_outcome(
            prices,
            pd.Timestamp(
                row[
                    "availability_date"
                ]
            ),
            excursion_horizon_weeks=int(
                outcome_horizon_weeks
            ),
        )

        outcomes.append(
            {
                "_idx": idx,
                **outcome,
            }
        )

    if outcomes:
        outcome_frame = (
            pd.DataFrame(
                outcomes
            )
            .set_index(
                "_idx"
            )
        )

        for col in outcome_frame.columns:
            matches[
                col
            ] = outcome_frame[
                col
            ]

    matches = matches.sort_values(
        [
            "similarity",
            "relative_cot_flow_similarity",
        ],
        ascending=[
            False,
            False,
        ],
    ).reset_index(
        drop=True
    )

    matches.insert(
        0,
        "rank",
        np.arange(
            1,
            len(
                matches
            )
            + 1,
        ),
    )

    horizon = int(
        outcome_horizon_weeks
    )

    values = pd.to_numeric(
        matches.get(
            f"return_{horizon}w"
        ),
        errors="coerce",
    ).dropna()

    bullish = int(
        (
            values > 0
        ).sum()
    )
    bearish = int(
        (
            values < 0
        ).sum()
    )
    flat = int(
        (
            values == 0
        ).sum()
    )

    aggregate = {
        "matches": int(
            len(
                matches
            )
        ),
        "outcomes_available": int(
            len(
                values
            )
        ),
        "bullish_count": bullish,
        "bearish_count": bearish,
        "flat_count": flat,
        "positive_rate": (
            float(
                (
                    values > 0
                ).mean()
            )
            if len(
                values
            )
            else np.nan
        ),
        "median_return": (
            float(
                values.median()
            )
            if len(
                values
            )
            else np.nan
        ),
        "median_similarity": float(
            pd.to_numeric(
                matches[
                    "similarity"
                ],
                errors="coerce",
            ).median()
        ),
        "median_downside_excursion": float(
            pd.to_numeric(
                matches[
                    "downside_excursion"
                ],
                errors="coerce",
            ).median()
        ),
        "median_upside_excursion": float(
            pd.to_numeric(
                matches[
                    "upside_excursion"
                ],
                errors="coerce",
            ).median()
        ),
        "horizon_weeks": horizon,
    }

    if (
        len(
            values
        ) > 0
        and bullish
        > bearish
        and aggregate[
            "median_return"
        ]
        > 0
    ):
        bias = "BULLISH"
    elif (
        len(
            values
        ) > 0
        and bearish
        > bullish
        and aggregate[
            "median_return"
        ]
        < 0
    ):
        bias = "BEARISH"
    else:
        bias = "MIXED"

    aggregate[
        "bias"
    ] = bias

    if len(
        values
    ) < 6:
        aggregate[
            "sample_quality"
        ] = "SMALL SAMPLE"
    elif len(
        values
    ) < 12:
        aggregate[
            "sample_quality"
        ] = "LIMITED SAMPLE"
    else:
        aggregate[
            "sample_quality"
        ] = "BROADER SAMPLE"

    current_groups = []

    for key, label, role in TFF_GROUPS:
        current_groups.append(
            {
                "group": label,
                "role": role,
                "relative_net_oi": _finite(
                    current.get(
                        f"relative_{key}_net_oi"
                    )
                ),
                "relative_percentile": _finite(
                    current.get(
                        f"relative_{key}_percentile_centered"
                    )
                ),
                "relative_delta_1w": _finite(
                    current.get(
                        f"relative_{key}_net_oi_delta_1w"
                    )
                ),
                "relative_delta_2w": _finite(
                    current.get(
                        f"relative_{key}_net_oi_delta_2w"
                    )
                ),
                "relative_delta_4w": _finite(
                    current.get(
                        f"relative_{key}_net_oi_delta_4w"
                    )
                ),
            }
        )

    current_summary = {
        "pair": setup[
            "pair"
        ],
        "base": setup[
            "base"
        ],
        "quote": setup[
            "quote"
        ],
        "ticker": setup[
            "ticker"
        ],
        "report_date": pd.Timestamp(
            current[
                "report_date"
            ]
        ),
        "availability_date": current_date,
        "price_date": pd.Timestamp(
            current[
                "price_date"
            ]
        ),
        "close": _finite(
            current[
                "close"
            ]
        ),
        "price_return_4w": _finite(
            current.get(
                "price_return_4w"
            )
        ),
        "price_return_13w": _finite(
            current.get(
                "price_return_13w"
            )
        ),
        "price_drawdown_26w": _finite(
            current.get(
                "price_drawdown_26w"
            )
        ),
        "price_vs_ma26": _finite(
            current.get(
                "price_vs_ma26"
            )
        ),
        "groups": current_groups,
    }

    return {
        "available": bool(
            not matches.empty
        ),
        "reason": "",
        "pair": setup[
            "pair"
        ],
        "base": setup[
            "base"
        ],
        "quote": setup[
            "quote"
        ],
        "ticker": setup[
            "ticker"
        ],
        "matches": matches,
        "aggregate": aggregate,
        "current": current_summary,
        "method": {
            "price_weight": 0.50,
            "relative_cot_level_weight": 0.25,
            "relative_cot_flow_weight": 0.25,
            "min_spacing_weeks": int(
                min_spacing_weeks
            ),
            "exclude_recent_weeks": int(
                exclude_recent_weeks
            ),
            "usd_method": (
                "USD is the bilateral reference leg; no DXY COT proxy is forced into USD pairs."
            ),
        },
    }


def normalized_fx_paths(
    prices: pd.DataFrame,
    *,
    current_anchor: pd.Timestamp,
    historical_anchors: list[pd.Timestamp],
    lookback_weeks: int = 13,
    forward_weeks: int = 8,
) -> pd.DataFrame:
    p = _clean_prices(
        prices
    )
    if p.empty:
        return pd.DataFrame()

    anchors = [
        (
            "CURRENT",
            pd.Timestamp(
                current_anchor
            ),
            True,
        )
    ]

    anchors.extend(
        (
            pd.Timestamp(
                anchor
            ).date().isoformat(),
            pd.Timestamp(
                anchor
            ),
            False,
        )
        for anchor in historical_anchors
    )

    rows = []

    for label, anchor, current in anchors:
        entry_date, entry = _entry_price(
            p,
            anchor,
        )

        if (
            entry_date is None
            or not np.isfinite(
                entry
            )
            or entry <= 0
        ):
            continue

        start = (
            entry_date
            - pd.Timedelta(
                weeks=int(
                    lookback_weeks
                )
            )
        )

        end = (
            entry_date
            if current
            else entry_date
            + pd.Timedelta(
                weeks=int(
                    forward_weeks
                )
            )
        )

        sample = p.loc[
            (
                p.index
                >= start
            )
            & (
                p.index
                <= end
            ),
            [
                "close"
            ],
        ].copy()

        if sample.empty:
            continue

        sample[
            "relative_day"
        ] = (
            sample.index
            - entry_date
        ).days

        sample[
            "normalized"
        ] = (
            sample[
                "close"
            ]
            / entry
            * 100.0
        )

        sample[
            "analog"
        ] = label

        rows.append(
            sample[
                [
                    "relative_day",
                    "normalized",
                    "analog",
                ]
            ]
        )

    if not rows:
        return pd.DataFrame()

    return pd.concat(
        rows,
        ignore_index=True,
    )
