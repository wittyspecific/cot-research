from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .analysis import (
    attach_cot_prices,
    classify_positioning_bias,
    commercial_range_state,
    cot_index,
    current_signal,
    enrich_cot,
    hedger_cycle_state,
    net_validation,
    positioning_velocity_state,
)
from .cftc import load_cftc_universe, load_history, resolve_market
from .cftc_reports import (
    DATASETS,
    load_report_history,
    load_report_universe,
    primary_report_for_asset_class,
    resolve_report_market,
)
from .config import (
    COMMERCIAL_RANGE_WEEKS,
    COT_INDEX_WEEKS,
    INDEX_LOWER,
    INDEX_UPPER,
    NET_LOWER_PERCENTILE,
    NET_UPPER_PERCENTILE,
    NET_VALIDATION_WEEKS,
    RELEASE_ACTIVE_WEEKS,
    SEASONAL_FORWARD_HORIZONS_DAYS,
    SEASONAL_HISTORY_WINDOWS,
)
from .ftmo_risk import (
    FTMORiskConfig,
    canonical_instrument,
    classify_cluster,
    ftmo_rule_state,
    fx_pair_from_symbol,
    portfolio_risk_status,
    pretrade_approval,
    risk_cockpit_summary,
)
from .fx_relative import load_currency_cot_profiles, load_currency_usd_values, synthesize_pair_prices
from .fx_relative_core import (
    CURRENCY_ORDER,
    FX_SEASONALITY_FORWARD_DAYS,
    FX_SEASONALITY_HISTORY_YEARS,
    classify_20y_40d_seasonality,
    pair_bias_from_strength,
    summarize_fx_horizons,
)
from .markets import CLASSIC_MARKETS
from .trade_context import all_markets, market_by_symbol, infer_cot_context
from .nc_divergence import current_divergence
from .prices import load_prices, price_alignment_audit
from .publication import publication_info
from .report_analysis import enrich_report_positioning
from .seasonality import forward_statistics, seasonal_consistency
from .watchlist_seasonality_core import classify_asset_seasonality, summarize_multi_horizon


SNAPSHOT_BUILDER_VERSION = "V3.6.2"


def _finite(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if np.isfinite(x) else np.nan


def _clean_scalar(value: Any) -> Any:
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if np.isfinite(x) else None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def _series_dict(row: pd.Series | Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}
    raw = row.to_dict() if isinstance(row, pd.Series) else dict(row)
    return {str(k): _clean_scalar(v) for k, v in raw.items()}


def _records(df: pd.DataFrame | None, tail: int | None = None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    frame = df.tail(tail) if tail else df
    return [_series_dict(row) for _, row in frame.iterrows()]


def _price_features(prices: pd.DataFrame) -> dict[str, Any]:
    if prices is None or prices.empty or "close" not in prices.columns:
        return {"available": False}
    close = pd.to_numeric(prices["close"], errors="coerce").dropna()
    if close.empty:
        return {"available": False}
    latest = float(close.iloc[-1])
    out: dict[str, Any] = {
        "available": True,
        "latest_date": pd.Timestamp(close.index[-1]).isoformat(),
        "latest_close": latest,
        "observations": int(len(close)),
    }
    for days in (1, 5, 10, 20, 40, 60, 120, 252):
        out[f"return_{days}d"] = float(latest / close.iloc[-days - 1] - 1.0) if len(close) > days else None
    returns = np.log(close / close.shift(1)).dropna()
    for days in (20, 60, 120):
        if len(returns) >= days:
            out[f"realized_vol_{days}d_ann"] = float(returns.tail(days).std(ddof=1) * np.sqrt(252.0))
        else:
            out[f"realized_vol_{days}d_ann"] = None
    return out


def _confirmation_snapshot(latest: pd.Series) -> dict[str, Any]:
    cot = _finite(latest.get("commercial_index"))
    comm = _finite(latest.get("commercial_net_percentile"))
    nc = _finite(latest.get("noncommercial_net_percentile"))
    retail = _finite(latest.get("retail_net_percentile"))
    direction = 0
    flags = {"cot": False, "commercial": False, "noncommercial": False, "retail": False}
    if np.isfinite(cot) and cot >= INDEX_UPPER:
        direction = 1
        flags = {
            "cot": True,
            "commercial": bool(np.isfinite(comm) and comm >= NET_UPPER_PERCENTILE),
            "noncommercial": bool(np.isfinite(nc) and nc <= NET_LOWER_PERCENTILE),
            "retail": bool(np.isfinite(retail) and retail <= NET_LOWER_PERCENTILE),
        }
    elif np.isfinite(cot) and cot <= INDEX_LOWER:
        direction = -1
        flags = {
            "cot": True,
            "commercial": bool(np.isfinite(comm) and comm <= NET_LOWER_PERCENTILE),
            "noncommercial": bool(np.isfinite(nc) and nc >= NET_UPPER_PERCENTILE),
            "retail": bool(np.isfinite(retail) and retail >= NET_UPPER_PERCENTILE),
        }
    confirmations = int(sum(int(v) for v in flags.values()))
    return {
        "direction": direction,
        "bias": "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "NEUTRAL",
        "confirmations": confirmations,
        "label": f"{confirmations}/4" if confirmations else "0/4",
        "flags": flags,
    }


def _seasonality_snapshot(prices: pd.DataFrame, cot_direction: int) -> dict[str, Any]:
    if prices is None or prices.empty:
        return {"available": False}
    stats = forward_statistics(
        prices,
        history_windows=SEASONAL_HISTORY_WINDOWS,
        horizons=SEASONAL_FORWARD_HORIZONS_DAYS,
    )
    if stats.empty:
        return {"available": False}
    consistency = seasonal_consistency(
        stats,
        primary_horizon=10,
        required_windows=SEASONAL_HISTORY_WINDOWS,
        reference_years=30,
    )
    horizons: dict[int, dict[str, Any]] = {}
    classified: dict[int, dict[str, Any]] = {}
    for horizon in (20, 40, 60):
        rows = stats[(stats["historie_jahre"] == 20) & (stats["horizont_tage"] == horizon)]
        if rows.empty:
            classified[horizon] = {"support": "N/V", "supports": False, "detail": "Keine ausreichende Historie"}
            continue
        row = rows.iloc[0]
        horizons[horizon] = _series_dict(row)
        classified[horizon] = classify_asset_seasonality(
            cot_direction=int(cot_direction),
            sample_size=int(row["stichprobe"]),
            positive_years=int(row["positive_jahre"]),
            positive_rate=float(row["trefferquote_positiv"]),
            base_rate=float(row["basisrate_positiv"]),
            median_return=float(row["median_rendite"]),
        )
    return {
        "available": True,
        "consistency": consistency,
        "multi_horizon": {
            "horizons": classified,
            "summary": summarize_multi_horizon(classified),
        },
        "twenty_year_horizon_rows": horizons,
        "full_statistics": _records(stats),
    }


def collect_market_research_snapshot(asset_class: str, market: Mapping[str, Any]) -> dict[str, Any]:
    """Capture the current research state for one CFTC market without future recomputation."""
    result: dict[str, Any] = {
        "asset_class": asset_class,
        "market": dict(market),
        "errors": [],
    }
    try:
        universe = load_cftc_universe()
        resolved = resolve_market(dict(market), universe)
        if not resolved:
            raise RuntimeError("Legacy-COT-Serie konnte nicht aufgelöst werden")
        code = str(resolved["cftc_contract_market_code"])
        result["cftc_code"] = code
        raw = load_history(code)
        if raw.empty:
            raise RuntimeError("Legacy-COT-Historie ist leer")
        cot = enrich_cot(
            raw,
            weeks=COT_INDEX_WEEKS,
            validation_weeks=NET_VALIDATION_WEEKS,
            range_weeks=COMMERCIAL_RANGE_WEEKS,
        )
        cot["noncommercial_index"] = cot_index(cot["noncommercial_net"], COT_INDEX_WEEKS)
        valid = cot.dropna(subset=[
            "commercial_index", "commercial_net_percentile", "noncommercial_net_percentile", "retail_net_percentile"
        ])
        if valid.empty:
            raise RuntimeError("Nicht genügend Historie für aktuellen COT-Snapshot")
        latest = valid.iloc[-1]
        confirmation = _confirmation_snapshot(latest)
        positioning = classify_positioning_bias(
            latest,
            upper=INDEX_UPPER,
            lower=INDEX_LOWER,
            validation_upper=NET_UPPER_PERCENTILE,
            validation_lower=NET_LOWER_PERCENTILE,
        )
        validation_direction = "BULLISH" if positioning["direction"] > 0 else "BEARISH" if positioning["direction"] < 0 else "NEUTRAL"
        result["legacy"] = {
            "latest": _series_dict(latest),
            "recent_12w": _records(cot, tail=12),
            "signal": current_signal(latest, INDEX_UPPER, INDEX_LOWER),
            "confirmation_4of4": confirmation,
            "positioning": positioning,
            "net_validation": net_validation(latest, validation_direction, NET_UPPER_PERCENTILE, NET_LOWER_PERCENTILE),
            "commercial_range": commercial_range_state(latest),
            "velocity": positioning_velocity_state(latest, direction=positioning["direction"]),
            "hedger_cycle": hedger_cycle_state(cot, upper=INDEX_UPPER, lower=INDEX_LOWER, release_active_weeks=RELEASE_ACTIVE_WEEKS),
            "publication": publication_info(latest["report_date"]),
        }
    except Exception as exc:
        result["errors"].append(f"COT: {exc}")
        return result

    ticker = str(market.get("ticker", "") or "")
    prices = pd.DataFrame()
    if ticker:
        try:
            prices = load_prices(ticker, raw["report_date"].min())
            result["price_proxy"] = {"ticker": ticker, **_price_features(prices)}
        except Exception as exc:
            result["errors"].append(f"Preisproxy: {exc}")
    else:
        result["price_proxy"] = {"ticker": ticker, "available": False}

    try:
        result["seasonality"] = _seasonality_snapshot(prices, int(result["legacy"]["confirmation_4of4"]["direction"]))
    except Exception as exc:
        result["errors"].append(f"Seasonality: {exc}")

    # Robust modern spec-flow layer, with Legacy NC fallback identical to the analysis page concept.
    try:
        cot_with_prices = attach_cot_prices(cot, prices)
        result["price_alignment_audit"] = price_alignment_audit(cot_with_prices)
        fallback_div = current_divergence(
            cot_with_prices,
            long_col="noncommercial_long",
            short_col="noncommercial_short",
            group_label="Legacy Non-Commercial",
        )
        modern_report_type = primary_report_for_asset_class(asset_class)
        spec_group_key = "managed_money" if modern_report_type == "disaggregated" else "leveraged_funds"
        spec_group_label = "Managed Money" if spec_group_key == "managed_money" else "Leveraged Funds"
        modern_universe = load_report_universe(modern_report_type)
        modern_resolved = resolve_report_market(dict(market), modern_universe)
        if modern_resolved:
            modern_raw = load_report_history(modern_report_type, modern_resolved["cftc_contract_market_code"])
            modern = enrich_report_positioning(
                modern_raw,
                report_type=modern_report_type,
                index_weeks=COT_INDEX_WEEKS,
                validation_weeks=NET_VALIDATION_WEEKS,
            ) if not modern_raw.empty else pd.DataFrame()
        else:
            modern = pd.DataFrame()

        if not modern.empty:
            modern_aligned = attach_cot_prices(modern, prices)
            spec_div = current_divergence(
                modern_aligned,
                long_col=f"{spec_group_key}_long",
                short_col=f"{spec_group_key}_short",
                group_label=spec_group_label,
            )
            result["spec_flow"] = {
                "source": f"{spec_group_label} · {DATASETS[modern_report_type]['label']}",
                "report_type": modern_report_type,
                "group": spec_group_key,
                "latest": _series_dict(modern.iloc[-1]),
                "recent_12w": _records(modern, tail=12),
                "divergence": spec_div,
                "price_alignment_audit": price_alignment_audit(modern_aligned),
            }
        else:
            result["spec_flow"] = {
                "source": "Legacy Non-Commercial · Fallback",
                "report_type": "legacy",
                "group": "noncommercial",
                "divergence": fallback_div,
            }
    except Exception as exc:
        result["errors"].append(f"Spec Flow: {exc}")

    return result


def collect_fx_pair_snapshot(base: str, quote: str) -> dict[str, Any]:
    base = str(base).upper()
    quote = str(quote).upper()
    result: dict[str, Any] = {"base": base, "quote": quote, "pair": f"{base}{quote}", "errors": []}
    try:
        profiles, errors = load_currency_cot_profiles()
        by_symbol = {str(row["symbol"]): row for _, row in profiles.iterrows()}
        if base not in by_symbol or quote not in by_symbol:
            raise RuntimeError("Base- oder Quote-COT-Profil nicht verfügbar")
        base_profile = by_symbol[base]
        quote_profile = by_symbol[quote]
        pair_bias = pair_bias_from_strength(int(base_profile["signed_strength"]), int(quote_profile["signed_strength"]))
        result["base_profile"] = _series_dict(base_profile)
        result["quote_profile"] = _series_dict(quote_profile)
        result["pair_bias"] = pair_bias
        if errors is not None and not errors.empty:
            result["profile_errors"] = _records(errors)
    except Exception as exc:
        result["errors"].append(f"FX COT Profile: {exc}")
        return result

    # Capture the detailed COT/flow state of both currency legs, not only the 4/4 summary.
    for label, currency in (("base_research", base), ("quote_research", quote)):
        found = market_by_symbol(currency)
        if found:
            try:
                asset_class, market = found
                result[label] = collect_market_research_snapshot(asset_class, market)
            except Exception as exc:
                result["errors"].append(f"{currency} Detail: {exc}")

    try:
        values = load_currency_usd_values()
        pair_prices = synthesize_pair_prices(base, quote, values)
        result["pair_price_proxy"] = _price_features(pair_prices)
        stats = forward_statistics(
            pair_prices,
            history_windows=(FX_SEASONALITY_HISTORY_YEARS,),
            horizons=tuple(FX_SEASONALITY_FORWARD_DAYS),
        ) if not pair_prices.empty else pd.DataFrame()
        horizon_results: dict[int, dict[str, Any]] = {}
        rows_by_horizon: dict[int, dict[str, Any]] = {}
        pair_direction = int(result["pair_bias"]["direction"])
        for horizon in FX_SEASONALITY_FORWARD_DAYS:
            rows = stats[(stats["historie_jahre"] == FX_SEASONALITY_HISTORY_YEARS) & (stats["horizont_tage"] == horizon)] if not stats.empty else pd.DataFrame()
            if rows.empty:
                horizon_results[horizon] = {"support": "N/V", "supports": False}
                continue
            row = rows.iloc[0]
            rows_by_horizon[horizon] = _series_dict(row)
            horizon_results[horizon] = classify_20y_40d_seasonality(
                pair_direction=pair_direction,
                sample_size=int(row["stichprobe"]),
                positive_years=int(row["positive_jahre"]),
                positive_rate=float(row["trefferquote_positiv"]),
                base_rate=float(row["basisrate_positiv"]),
                median_return=float(row["median_rendite"]),
            )
        result["seasonality"] = {
            "horizons": horizon_results,
            "rows": rows_by_horizon,
            "summary": summarize_fx_horizons(horizon_results),
            "full_statistics": _records(stats),
        }
    except Exception as exc:
        result["errors"].append(f"FX Seasonality: {exc}")
    return result


def _catalog_spec(snapshot: Mapping[str, Any], symbol: str) -> dict[str, Any]:
    catalog = snapshot.get("symbol_catalog")
    if not isinstance(catalog, pd.DataFrame) or catalog.empty:
        return {}
    exact = catalog[catalog["symbol"].astype(str).str.upper() == str(symbol).upper()]
    if exact.empty:
        return {}
    return _series_dict(exact.iloc[0])


def _mt5_price_context(spec: Mapping[str, Any]) -> dict[str, Any]:
    bid = _finite(spec.get("bid"))
    ask = _finite(spec.get("ask"))
    last = _finite(spec.get("last"))
    mid = (bid + ask) / 2.0 if np.isfinite(bid) and np.isfinite(ask) else np.nan
    mark = last if np.isfinite(last) and last > 0 else mid if np.isfinite(mid) else bid if np.isfinite(bid) else ask
    spread = ask - bid if np.isfinite(bid) and np.isfinite(ask) else np.nan
    return {
        "bid": bid,
        "ask": ask,
        "last": last,
        "mid": mid,
        "mark": mark,
        "spread": spread,
        "spread_pct_mid": float(spread / mid) if np.isfinite(spread) and np.isfinite(mid) and mid != 0 else np.nan,
    }


def collect_trade_snapshot(
    *,
    plan: Mapping[str, Any],
    mt5_snapshot: Mapping[str, Any],
    risk_cfg: FTMORiskConfig,
    context_override: Mapping[str, Any] | None = None,
    include_private_risk: bool = True,
) -> dict[str, Any]:
    """Full as-known-now snapshot for one planned trade.

    The returned object is designed to be serialized immediately and never
    recomputed into the historical row. Missing components are recorded as
    missing/errors instead of being silently backfilled later.
    """
    now = datetime.now(timezone.utc)
    symbol = str(plan.get("cfd_symbol", "") or "")
    side = str(plan.get("side", "") or "").upper()
    entry = float(plan.get("entry"))
    stop = float(plan.get("stop"))
    requested_risk_pct = float(plan.get("requested_risk_pct", risk_cfg.target_trade_risk_pct) or risk_cfg.target_trade_risk_pct)

    account = dict(mt5_snapshot.get("account", {}) or {})
    positions = mt5_snapshot.get("positions")
    if not isinstance(positions, pd.DataFrame):
        positions = pd.DataFrame()
    spec = _catalog_spec(mt5_snapshot, symbol)
    context = dict(context_override or {}) if context_override else infer_cot_context(symbol, spec)

    payload: dict[str, Any] = {
        "meta": {
            "builder_version": SNAPSHOT_BUILDER_VERSION,
            "captured_at_utc": now.isoformat(timespec="seconds"),
            "data_principle": "AS_KNOWN_AT_PLAN_TIME",
            "mt5_source": mt5_snapshot.get("source"),
            "mt5_captured_at": mt5_snapshot.get("captured_at"),
            "mt5_market_time": mt5_snapshot.get("market_time"),
        },
        "execution": {
            "cfd_symbol": symbol,
            "side": side,
            "entry": entry,
            "stop": stop,
            "target": plan.get("target"),
            "zone_type": plan.get("zone_type"),
            "zone_low": plan.get("zone_low"),
            "zone_high": plan.get("zone_high"),
            "timeframe": plan.get("timeframe"),
            "zone_freshness": plan.get("zone_freshness"),
            "retest_count": plan.get("retest_count"),
            "quality_grade": plan.get("quality_grade"),
            "requested_risk_pct": requested_risk_pct,
        },
        "mt5_symbol": {
            "spec": spec,
            "price": _mt5_price_context(spec),
            "instrument": canonical_instrument(symbol),
            "cluster": classify_cluster(symbol, spec.get("currency_base", ""), spec.get("currency_profit", "")),
        },
        "account": account if include_private_risk else {"available": False, "scope": "ADMIN_ONLY"},
        "portfolio": {
            "open_positions": _records(positions) if include_private_risk else [],
            "open_position_count": int(len(positions)) if include_private_risk else None,
            "scope": "FULL" if include_private_risk else "ADMIN_ONLY",
        },
        "research_context": context,
        "errors": [],
    }

    if include_private_risk:
        try:
            rule_state = ftmo_rule_state(account, positions, risk_cfg)
            portfolio_status = portfolio_risk_status(account, positions, risk_cfg)
            cockpit = risk_cockpit_summary(account, positions, risk_cfg)
            payload["risk"] = {
                "available": True,
                "config": risk_cfg.__dict__,
                "ftmo_rule_state": rule_state,
                "portfolio_status": portfolio_status,
                "cockpit": cockpit,
            }
            if spec:
                approval = pretrade_approval(
                    account=account,
                    positions=positions,
                    cfg=risk_cfg,
                    spec=spec,
                    symbol=symbol,
                    side=side,
                    entry=entry,
                    stop=stop,
                    requested_risk_pct=requested_risk_pct,
                )
                payload["risk"]["pretrade_approval"] = approval
            else:
                payload["errors"].append("MT5-Symbolspezifikation für Pre-Trade-Lot-Sizing nicht gefunden.")
        except Exception as exc:
            payload["errors"].append(f"Risk Snapshot: {exc}")
    else:
        payload["risk"] = {
            "available": False,
            "scope": "ADMIN_ONLY",
            "note": "FTMO-/Portfolio-Risk wurde für diesen Trader-Snapshot aus Datenschutzgründen nicht gespeichert.",
        }

    try:
        mode = str(context.get("mode", "NONE") or "NONE").upper()
        if mode == "FX_PAIR":
            payload["research"] = collect_fx_pair_snapshot(context["base"], context["quote"])
        elif mode == "MARKET":
            market = context.get("market") or {}
            asset_class = context.get("asset_class") or ""
            payload["research"] = collect_market_research_snapshot(asset_class, market)
        else:
            payload["research"] = {"available": False, "reason": "Kein COT-Kontext zugeordnet."}
    except Exception as exc:
        payload["errors"].append(f"Research Snapshot: {exc}")
        payload["research"] = {"available": False}

    return payload
