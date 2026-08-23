
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.cftc import load_cftc_universe, load_history, resolve_market
from src.cftc_reports import (
    DATASETS,
    load_report_history,
    load_report_universe,
    primary_report_for_asset_class,
    resolve_report_market,
)
from src.config import (
    INDEX_LOWER,
    INDEX_UPPER,
    NET_VALIDATION_WEEKS,
    NC_DIV_FLOW_WINDOW_W,
    NC_DIV_PATH_WINDOW_W,
    NC_DIV_PRICE_WINDOW_W,
    NC_DIV_STANDARDIZE_HIST_W,
    NC_DIV_USE_OI_NORM,
    NC_DIV_Z_THRESHOLD,
    NC_CONFIRMING_WEEKS,
    NC_DIVERGENCE_WEEKS,
    NC_MIN_ACTIVE_BUILD_SHARE,
    NC_MIN_ACTIVE_LEG_GROSS_PCT,
    NC_MIN_NET_CHANGE_GROSS_PCT,
    NC_MIN_PRICE_MOVE_PCT,
)
from src.markets import CLASSIC_MARKETS
from src.prices import load_prices, price_alignment_audit
from src.report_analysis import REPORT_GROUPS, enrich_report_positioning
from src.analysis import (
    attach_cot_prices,
    enrich_cot,
    historical_nc_divergences_legacy,
)
from src.nc_divergence import (
    build_divergence_history,
    compare_legacy_and_new_events,
    historical_divergence_events,
    redundancy_metrics,
    yearly_signal_counts,
)
from src.research_lab import (
    circular_shift_null_model,
    index_window_comparison,
    release_decay_study,
)
from src.positioning_dynamics_research import (
    build_positioning_episode_dataset,
    compare_flow_measures,
    quantile_effect_study,
    research_question_coverage,
    summarize_window_threshold_grid,
)
from src.positioning_cross_market import (
    aggregate_cross_market_scans,
    candidate_flow_overlap,
    cross_market_candidate_detail,
    cross_market_coverage_diagnostic,
    cross_market_findings,
    cross_market_flow_redundancy,
    cross_market_leave_one_out,
    cross_market_neighborhood_summary,
    cross_market_parameter_neighborhood,
    evaluate_pre_oos_decision_gate,
    fixed_parameter_region_matrix,
    leave_one_out_summary,
)
from src.positioning_robustness import (
    build_pre_oos_freeze_snapshot,
    candidate_freeze_id,
    candidate_overlap_table,
    candidate_review_label,
    distinct_candidate_shortlist,
    flow_monotonicity_diagnostic,
    freeze_snapshot_json,
    frozen_candidates_from_scan,
    incremental_value_table,
    monotonicity_summary,
    overlap_redundancy_summary,
    reviewed_shortlist,
    scan_parameter_robustness,
    scanner_findings,
    strict_monotonicity_assessment,
)
from src.style import (
    apply_style,
    context_strip,
    definition,
    page_header,
    section_line,
    metric_card,
    plotly_config,
    tradingview_chart,
    tradingview_plotly_chart,
)

# V3.20.0 · ADVANCED DIRECT ACCESS GUARD
_v3200_trader = dict(st.session_state.get("auth_trader") or {})
if (
    not _v3200_trader
    or str(_v3200_trader.get("role", "TRADER")).upper() != "ADMIN"
):
    st.error("Kein Zugriff auf den Advanced-Bereich.")
    st.stop()

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("intermarket.py")), run_name="__main__")
