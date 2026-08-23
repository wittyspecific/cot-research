
from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover
    px = None
    go = None

from src.macro.config import SERIES_SPECS
from src.macro.macro_model_library import evaluate
from src.style import (
    apply_style,
    context_strip,
    metric_card,
    page_header,
    section_line,
)


apply_style()

page_header(
    "Research · Macro",
    "Makro Model Library",
    "Business Cycle Core · Sequencing · Imminent Recession · Breadth · Liquidity Modifier",
    "V3.26.0 · TRANSITION & MACRO FAMILIES",
)

st.caption(
    "Kein Entry-Signal. Der Business Cycle Core definiert das Makro-Regime. "
    "Breadth/Scatter erklären die Breite; Liquidity modifiziert Timing und Amplitude, "
    "darf das Cycle-Regime aber nicht überschreiben."
)


@st.cache_data(ttl=21600, show_spinner=False)
def _load_macro(force_refresh=False):
    return evaluate(
        config_path="config/macro_model_library.toml",
        force_refresh=force_refresh,
    )


refresh = st.button(
    "Makrodaten aktualisieren",
    icon=":material/refresh:",
)

with st.spinner("Makroserien und Business-Cycle-Core werden ausgewertet …"):
    result = _load_macro(
        force_refresh=refresh
    )

if refresh:
    st.cache_data.clear()


context_strip(
    [
        ("Cycle", result["cycle_phase"]),
        ("Transition", result["transition_state"]),
        ("Stand", result["as_of"]),
        (
            "Datenabdeckung",
            f"{result['data_quality']['required_series_ok']}/"
            f"{result['data_quality']['required_series_total']}",
        ),
    ]
)


section_line(
    "1 · Business Cycle Core",
    "Leading → Coincident → Lagging · jeweils relativ zur langfristigen Equilibrium-Referenz",
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    metric_card(
        "CYCLE PHASE",
        result["cycle_phase"],
        f"Confidence {result['confidence']:.0%}",
    )

with c2:
    metric_card(
        "LEADING",
        (
            f"{result['leading']['index']:+.0f}"
            if result["leading"]["index"] is not None
            else "—"
        ),
        (
            f"Dist. Eq. {result['leading']['distance']:+.1f}"
            if result["leading"]["distance"] is not None
            else "Equilibrium N/V"
        ),
    )

with c3:
    metric_card(
        "COINCIDENT",
        (
            f"{result['coincident']['index']:+.0f}"
            if result["coincident"]["index"] is not None
            else "—"
        ),
        (
            f"Dist. Eq. {result['coincident']['distance']:+.1f}"
            if result["coincident"]["distance"] is not None
            else "Equilibrium N/V"
        ),
    )

with c4:
    metric_card(
        "LAGGING",
        (
            f"{result['lagging']['index']:+.0f}"
            if result["lagging"]["index"] is not None
            else "—"
        ),
        "deskriptiv · kein Regime-Treiber",
    )


history = pd.DataFrame(
    result.get("cycle_history", [])
)

if not history.empty:
    history["date"] = pd.to_datetime(
        history["date"],
        errors="coerce",
    )
    history = history.dropna(
        subset=["date"]
    )

    chart = history[
        ["date", "leading", "coincident", "lagging"]
    ].melt(
        id_vars="date",
        var_name="Tier",
        value_name="Index",
    )

    if px is not None:
        fig = px.line(
            chart,
            x="date",
            y="Index",
            color="Tier",
            labels={
                "date": "Datum",
                "Index": "Cycle Index",
            },
        )
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_width=1,
        )
        fig.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=15, b=10),
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displaylogo": False},
        )
    else:
        pivot = chart.pivot(
            index="date",
            columns="Tier",
            values="Index",
        )
        st.line_chart(
            pivot,
            use_container_width=True,
        )

st.caption(
    "Equilibrium ist hier eine transparente, prior-only Public-Proxy-Konstruktion. "
    "Sie ist nicht Henrik Zebergs proprietäre Equilibrium-Formel."
)

divergence = result.get(
    "phase_divergence",
    "N/V",
)

if divergence == "EXPECTED_SLOWDOWN_DIVERGENCE":
    st.info(
        "Leading liegt schwächer als Coincident: Das ist eine erwartete Slowdown-Sequenz, "
        "kein einfacher Widerspruch."
    )
elif divergence == "EXPECTED_RECOVERY_DIVERGENCE":
    st.info(
        "Leading verbessert sich vor Coincident: Das ist eine erwartete Recovery-Sequenz."
    )



section_line(
    "1b · Transition Models & Macro Families",
    "Housing → Labor → Household · Coincident → US 2Y · Research only, kein zusätzlicher Cycle Vote",
)

transition_models = result.get(
    "transition_models",
    {},
)

macro_families = result.get(
    "macro_families",
    {},
)

tf1, tf2, tf3 = st.columns(
    3
)

for column, key, label in (
    (
        tf1,
        "labor_quality",
        "LABOR QUALITY",
    ),
    (
        tf2,
        "housing_activity",
        "HOUSING ACTIVITY",
    ),
    (
        tf3,
        "household_resilience",
        "HOUSEHOLD RESILIENCE",
    ),
):
    family_item = macro_families.get(
        key,
        {},
    )

    positive = family_item.get(
        "positive_breadth"
    )

    with column:
        metric_card(
            label,
            family_item.get(
                "state",
                "N/V",
            ),
            (
                f"positive breadth {positive:.0%}"
                if positive is not None
                else "nicht genügend Daten"
            ),
        )

tt1, tt2, tt3 = st.columns(
    3
)

for column, key, label in (
    (
        tt1,
        "housing_to_labor",
        "HOUSING → LABOR",
    ),
    (
        tt2,
        "labor_to_household",
        "LABOR → HOUSEHOLD",
    ),
    (
        tt3,
        "coincident_to_2y",
        "COINCIDENT → US 2Y",
    ),
):
    item = transition_models.get(
        key,
        {},
    )

    with column:
        metric_card(
            label,
            item.get(
                "state",
                "N/V",
            ),
            item.get(
                "interpretation",
                "keine Transition-Diagnose verfügbar",
            ),
        )

family_rows = []

for key in (
    "labor_quality",
    "housing_activity",
    "household_resilience",
):
    item = macro_families.get(
        key,
        {},
    )

    family_rows.append(
        {
            "Macro Family": item.get(
                "label",
                key,
            ),
            "State": item.get(
                "state",
                "N/V",
            ),
            "Positive": item.get(
                "positive_components",
                0,
            ),
            "Negative": item.get(
                "negative_components",
                0,
            ),
            "Available": item.get(
                "available_components",
                0,
            ),
            "Role": item.get(
                "role",
                "DIAGNOSTIC_ONLY_NO_CYCLE_VOTE",
            ),
        }
    )

st.dataframe(
    pd.DataFrame(
        family_rows
    ),
    use_container_width=True,
    hide_index=True,
)

with st.expander(
    "Transition & Macro Family Details",
    expanded=False,
):
    component_rows = []

    for family_key, family_item in macro_families.items():
        for component in family_item.get(
            "components",
            [],
        ):
            direction = component.get(
                "direction"
            )

            component_rows.append(
                {
                    "Family": family_item.get(
                        "label",
                        family_key,
                    ),
                    "Component": component.get(
                        "label",
                        "",
                    ),
                    "Level": component.get(
                        "value"
                    ),
                    "Change": component.get(
                        "change"
                    ),
                    "Direction": (
                        "POSITIVE"
                        if direction == 1
                        else (
                            "NEGATIVE"
                            if direction == -1
                            else (
                                "NEUTRAL"
                                if direction == 0
                                else "CONTEXT"
                            )
                        )
                    ),
                    "Change Unit": component.get(
                        "change_unit",
                        "",
                    ),
                    "Note": component.get(
                        "note",
                        "",
                    ),
                }
            )

    if component_rows:
        st.dataframe(
            pd.DataFrame(
                component_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

    transition_rows = []

    for item in transition_models.values():
        transition_rows.append(
            {
                "Transition": item.get(
                    "label",
                    "",
                ),
                "State": item.get(
                    "state",
                    "N/V",
                ),
                "Interpretation": item.get(
                    "interpretation",
                    "",
                ),
                "Role": item.get(
                    "role",
                    "TRANSITION_DIAGNOSTIC_ONLY",
                ),
            }
        )

    if transition_rows:
        st.dataframe(
            pd.DataFrame(
                transition_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

st.caption(
    "Wichtig: Diese neuen Familien verändern die produktive Business-Cycle-Phase bewusst nicht. "
    "Sie sollen die Sequenz sichtbar machen: Housing kann Labor führen, Labor kann auf Household Demand übertragen, "
    "und Coincident Growth kann dem US 2Y vorauslaufen. Erst nach historischer Robustheitsprüfung würden wir daraus "
    "kalibrierte Transition-Regeln ableiten."
)


section_line(
    "2 · Imminent Recession Cluster",
    "phase-conditional · zählt nur während eines bestätigten SLOWDOWN",
)

imminent = result["imminent_recession"]

i1, i2, i3 = st.columns(3)

with i1:
    metric_card(
        "STATE",
        imminent["state"],
        "nur im Slowdown aktiviert",
    )

with i2:
    metric_card(
        "ACTIVE",
        f"{imminent['active_count']}/{imminent['total']}",
        (
            f"observed {imminent['observed_count']}/{imminent['total']}"
        ),
    )

with i3:
    metric_card(
        "TRANSITION RISK",
        f"{imminent['score']:.0f}/100",
        "kein Recession-Timing-Datum",
    )

criteria_rows = [
    {
        "Kriterium": item["label"],
        "Beobachtet": "✓" if item["observed"] else "—",
        "Aktiv im Cluster": "✓" if item["active"] else "—",
    }
    for item in imminent["criteria"]
]

st.dataframe(
    pd.DataFrame(criteria_rows),
    use_container_width=True,
    hide_index=True,
)

if not imminent["phase_gate_active"]:
    st.caption(
        "Die Kriterien dürfen beobachtet werden, sind aber außerhalb eines bestätigten "
        "SLOWDOWN bewusst NICHT als Imminent-Recession-Cluster aktiv."
    )


section_line(
    "3 · Model Breadth & Makro ML Scatter",
    "Diagnose der Breite · definiert das Cycle-Regime nicht",
)

breadth = result["model_breadth"]
bh = breadth.get("history", {})

b1, b2, b3, b4 = st.columns(4)

leading_now = breadth.get("tiers", {}).get(
    "leading",
    {},
)

with b1:
    metric_card(
        "LEADING RISK-OFF",
        f"{leading_now.get('risk_off_breadth', 0.0):.0%}",
        leading_now.get("state", "N/V"),
    )

with b2:
    metric_card(
        "4W",
        f"{bh.get('4W', {}).get('leading', {}).get('risk_off_breadth', 0.0):.0%}",
        "Leading Family Breadth",
    )

with b3:
    metric_card(
        "13W",
        f"{bh.get('13W', {}).get('leading', {}).get('risk_off_breadth', 0.0):.0%}",
        "Leading Family Breadth",
    )

with b4:
    coincident_now = breadth.get(
        "tiers",
        {},
    ).get("coincident", {})
    metric_card(
        "COINCIDENT RISK-OFF",
        f"{coincident_now.get('risk_off_breadth', 0.0):.0%}",
        coincident_now.get("state", "N/V"),
    )


atomic = pd.DataFrame(
    result.get("atomic_models", [])
)

if not atomic.empty:
    scatter = atomic[
        atomic["signal"].ne("N/V")
        & atomic["score"].notna()
    ].copy()

    scatter["confidence_pct"] = (
        pd.to_numeric(
            scatter["confidence"],
            errors="coerce",
        )
        * 100.0
    )
    scatter["persistence_pct"] = (
        pd.to_numeric(
            scatter["persistence_13w"],
            errors="coerce",
        )
        * 100.0
    )
    scatter["plot_size"] = scatter[
        "persistence_pct"
    ].clip(lower=8.0)

    if px is not None and not scatter.empty:
        fig = px.scatter(
            scatter,
            x="score",
            y="confidence_pct",
            size="plot_size",
            color="tier",
            hover_name="name",
            hover_data={
                "family": True,
                "signal": True,
                "score": ":.1f",
                "confidence_pct": ":.0f",
                "persistence_pct": ":.0f",
                "raw_value": True,
                "description": True,
                "plot_size": False,
            },
            labels={
                "score": "Model Score  ← Risk-Off | Risk-On →",
                "confidence_pct": "Confidence (%)",
                "tier": "Tier",
            },
            size_max=28,
        )
        fig.add_vline(
            x=0,
            line_dash="dash",
            line_width=1,
        )
        fig.update_xaxes(
            range=[-105, 105]
        )
        fig.update_yaxes(
            range=[0, 105]
        )
        fig.update_layout(
            height=540,
            margin=dict(l=10, r=10, t=15, b=10),
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displaylogo": False},
        )
    else:
        st.scatter_chart(
            scatter,
            x="score",
            y="confidence_pct",
            color="tier",
            size="plot_size",
            use_container_width=True,
        )

st.caption(
    "Scatter: X = Richtung · Y = Confidence · Punktgröße = 13W-Persistenz. "
    "Die 70%-Regel gilt nur als Family-Breadth-Diagnose und darf die Cycle-Phase nicht überschreiben."
)

family = pd.DataFrame(
    result.get("family_consensus", [])
)

if not family.empty:
    family_show = family.copy()
    family_show["agreement"] = (
        pd.to_numeric(
            family_show["agreement"],
            errors="coerce",
        )
        * 100.0
    )
    st.dataframe(
        family_show.rename(
            columns={
                "tier": "Tier",
                "family": "Family",
                "signal": "Signal",
                "agreement": "Agreement",
                "active_models": "Aktiv",
                "risk_off_models": "Risk-Off",
                "risk_on_models": "Risk-On",
                "neutral_models": "Neutral",
            }
        ).style.format(
            {"Agreement": "{:.0f}%"},
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )


section_line(
    "4 · Liquidity Modifier",
    "Policy · Credit · Market Liquidity · modifiziert, überschreibt den Cycle aber nicht",
)

liq = result["liquidity_modifier"]
l1, l2, l3, l4 = st.columns(4)

with l1:
    metric_card(
        "LIQUIDITY",
        liq["state"],
        (
            f"Score {liq['score']:+.0f}"
            if liq.get("score") is not None
            else "Score N/V"
        ),
    )

for column, key, label in (
    (l2, "policy", "POLICY"),
    (l3, "credit", "CREDIT"),
    (l4, "market", "MARKET"),
):
    with column:
        value = liq.get(
            "channels",
            {},
        ).get(key)
        metric_card(
            label,
            (
                f"{value:+.0f}"
                if value is not None
                else "—"
            ),
            "Modifier channel",
        )

st.caption(
    liq.get(
        "interpretation",
        "",
    )
)


section_line(
    "5 · Explainability",
    "Sequenz statt mechanischer Gesamtpunktzahl",
)

for driver in result.get("drivers", []):
    st.markdown(f"- {driver}")


with st.expander(
    "Atomic Models · Details",
    expanded=False,
):
    if atomic.empty:
        st.info("Keine Atomic Models verfügbar.")
    else:
        detail = atomic.copy()
        detail["confidence"] = (
            pd.to_numeric(
                detail["confidence"],
                errors="coerce",
            )
            * 100
        )
        detail["persistence_13w"] = (
            pd.to_numeric(
                detail["persistence_13w"],
                errors="coerce",
            )
            * 100
        )
        st.dataframe(
            detail.rename(
                columns={
                    "name": "Modell",
                    "tier": "Tier",
                    "family": "Family",
                    "signal": "Signal",
                    "score": "Score",
                    "confidence": "Confidence",
                    "persistence_13w": "Persistenz 13W",
                    "raw_value": "Rohwert",
                    "description": "Hypothese",
                }
            ).style.format(
                {
                    "Score": "{:+.1f}",
                    "Confidence": "{:.0f}%",
                    "Persistenz 13W": "{:.0f}%",
                    "Rohwert": "{:.4f}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )



section_line(
    "6 · Historical Validation",
    "1990+ · Cycle-Phasen gegen USREC/NBER-Chronologie · keine automatische Neukalibrierung",
)

validation = result.get("historical_validation", {})
validation_summary = validation.get("summary", {})
validation_episodes = pd.DataFrame(
    validation.get("episodes", [])
)

v1, v2, v3, v4 = st.columns(4)

with v1:
    metric_card(
        "EVALUABLE",
        (
            f"{int(validation_summary.get('episodes_evaluable', 0))}/"
            f"{int(validation_summary.get('episodes_total', 0))}"
        ),
        "NBER/USREC Episoden ab 1990",
    )

with v2:
    value = validation_summary.get(
        "slowdown_before_start_rate"
    )
    lead = validation_summary.get(
        "median_slowdown_lead_weeks"
    )
    metric_card(
        "SLOWDOWN VOR START",
        f"{value:.0%}" if value is not None else "—",
        (
            f"Median Lead {lead:.0f}W"
            if lead is not None
            else "Median Lead —"
        ),
    )

with v3:
    value = validation_summary.get(
        "contraction_near_start_rate"
    )
    lag = validation_summary.get(
        "median_contraction_lag_weeks"
    )
    metric_card(
        "CONTRACTION NAHE START",
        f"{value:.0%}" if value is not None else "—",
        (
            f"Median Lag {lag:+.0f}W"
            if lag is not None
            else "Median Lag —"
        ),
    )

with v4:
    value = validation_summary.get(
        "false_contraction_share_outside_recession"
    )
    metric_card(
        "FALSE CONTRACTION",
        f"{value:.1%}" if value is not None else "—",
        "Anteil außerhalb USREC-Rezessionswochen",
    )

if not validation_episodes.empty:
    show = validation_episodes.copy()

    for col in (
        "pre13w_warning_share",
        "contraction_overlap_share",
    ):
        if col in show.columns:
            show[col] = (
                pd.to_numeric(
                    show[col],
                    errors="coerce",
                )
                * 100.0
            )

    show = show.rename(
        columns={
            "episode": "Episode",
            "start": "NBER Start",
            "end": "NBER Ende",
            "evaluable": "Auswertbar",
            "phase_at_start": "Phase @ Start",
            "phase_at_end": "Phase @ Ende",
            "slowdown_onset": "Slowdown Start",
            "slowdown_lead_weeks": "Slowdown Lead W",
            "contraction_first": "Erste Contraction",
            "contraction_lag_weeks": "Contraction Lag W",
            "recovery_first": "Erste Recovery",
            "recovery_vs_end_weeks": "Recovery vs Ende W",
            "pre13w_warning_share": "Pre-13W Warnung",
            "contraction_overlap_share": "Contraction Overlap",
        }
    )

    st.dataframe(
        show.style.format(
            {
                "Slowdown Lead W": "{:.1f}",
                "Contraction Lag W": "{:+.1f}",
                "Recovery vs Ende W": "{:+.1f}",
                "Pre-13W Warnung": "{:.0f}%",
                "Contraction Overlap": "{:.0f}%",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

st.warning(
    "**RETROSPECTIVE_REVISED_DATA:** "
    + validation.get(
        "warning",
        "Keine Validierungswarnung verfügbar.",
    )
)

st.caption(
    "Interpretation: positiver Slowdown Lead = Warnung vor offiziellem Rezessionsstart; "
    "Contraction Lag < 0 = Modell war vor dem NBER-Start bereits in Contraction. "
    "Diese Auswertung misst den bestehenden V3.24-Core und führt bewusst keine automatische Neukalibrierung durch."
)



section_line(
    "6b · Contraction Calibration Lab",
    "Research only · Timing vs. Overlap vs. False Positives · keine automatische Regeländerung",
)

st.caption(
    "Verglichen werden: Current V3.24 · Candidate A · Candidate B · Candidate C · Candidate D"
)

calibration = validation.get(
    "contraction_calibration",
    {},
)
candidate_frame = pd.DataFrame(
    calibration.get("candidates", [])
)
episode_frame = pd.DataFrame(
    calibration.get("episodes", [])
)

st.caption(
    calibration.get(
        "normal_cycle_definition",
        "2020 wird separat als exogener Schockfall ausgewiesen.",
    )
)

if not candidate_frame.empty:
    current_map = {
        row["candidate"]: row
        for row in candidate_frame.to_dict("records")
    }

    summary_cols = st.columns(5)
    for col, key in zip(
        summary_cols,
        ["CURRENT", "A", "B", "C", "D"],
    ):
        row = current_map.get(key, {})
        with col:
            metric_card(
                row.get("label", key).upper(),
                "CONTRACTION" if row.get("current_active") else "NO",
                (
                    f"seit {row.get('current_onset')}"
                    if row.get("current_onset")
                    else row.get("logic", "")
                ),
            )

    show = candidate_frame.copy()
    for col in (
        "normal_hit_pm13w_rate",
        "normal_mean_overlap_share",
        "normal_false_contraction_share",
        "all_hit_pm13w_rate",
        "all_mean_overlap_share",
        "all_false_contraction_share",
    ):
        if col in show.columns:
            show[col] = pd.to_numeric(
                show[col], errors="coerce"
            ) * 100.0

    show = show.rename(
        columns={
            "label": "Regel",
            "logic": "Logik",
            "current_active": "Jetzt",
            "current_onset": "Aktiv seit",
            "normal_hit_pm13w_rate": "±13W Hit",
            "normal_median_lag_weeks": "Median Lag W",
            "normal_mean_overlap_share": "Overlap",
            "normal_false_contraction_share": "False Pos.",
            "normal_avg_spell_weeks": "Ø Spell W",
            "all_hit_pm13w_rate": "±13W Hit inkl. 2020",
            "all_median_lag_weeks": "Median Lag inkl. 2020 W",
        }
    )

    desired = [
        "Regel",
        "Logik",
        "Jetzt",
        "Aktiv seit",
        "±13W Hit",
        "Median Lag W",
        "Overlap",
        "False Pos.",
        "Ø Spell W",
        "±13W Hit inkl. 2020",
        "Median Lag inkl. 2020 W",
    ]

    st.dataframe(
        show[[col for col in desired if col in show.columns]].style.format(
            {
                "±13W Hit": "{:.0f}%",
                "Median Lag W": "{:+.1f}",
                "Overlap": "{:.0f}%",
                "False Pos.": "{:.1f}%",
                "Ø Spell W": "{:.1f}",
                "±13W Hit inkl. 2020": "{:.0f}%",
                "Median Lag inkl. 2020 W": "{:+.1f}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

if not episode_frame.empty:
    with st.expander(
        "Calibration · Episodenvergleich 1990 / 2001 / 2008 / 2020",
        expanded=False,
    ):
        episode_show = episode_frame.copy()
        if "overlap_share" in episode_show.columns:
            episode_show["overlap_share"] = pd.to_numeric(
                episode_show["overlap_share"], errors="coerce"
            ) * 100.0

        episode_show = episode_show.rename(
            columns={
                "candidate_label": "Regel",
                "episode": "Episode",
                "onset": "Contraction Onset",
                "lag_weeks": "Lag W",
                "hit_pm13w": "±13W Hit",
                "overlap_share": "Overlap",
                "shock_case": "Shock Case",
            }
        )

        st.dataframe(
            episode_show[
                [
                    col
                    for col in (
                        "Regel",
                        "Episode",
                        "Contraction Onset",
                        "Lag W",
                        "±13W Hit",
                        "Overlap",
                        "Shock Case",
                    )
                    if col in episode_show.columns
                ]
            ].style.format(
                {
                    "Lag W": "{:+.1f}",
                    "Overlap": "{:.0f}%",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

st.warning(
    "**RESEARCH_ONLY_NO_AUTO_CALIBRATION:** "
    + calibration.get(
        "warning",
        "Die Kandidaten ändern die produktive Cycle-Phase nicht.",
    )
)

st.caption(
    "Ziel ist nicht der niedrigste False-Positive-Wert um jeden Preis. "
    "Gesucht wird ein robuster Trade-off: Contraction möglichst nahe am normalen "
    "Rezessionsbeginn, ausreichend hoher Rezessions-Overlap und deutlich weniger "
    "False Positives. 2020 bleibt sichtbar, wird aber nicht zur normalen Cycle-Kalibrierung gezählt."
)

section_line(
    "7 · Data Registry / Point-in-Time",
    "native Frequenz → Feature → conservative availability → weekly alignment",
)

status = result["data_quality"]["series_status"]
registry = []

for spec in SERIES_SPECS:
    item = status.get(spec.key, {})
    registry.append(
        {
            "Serie": spec.label,
            "Series-ID": spec.series_id,
            "Frequenz": spec.frequency,
            "Release-Lag": f"{spec.release_lag_days}d",
            "Required": spec.required,
            "Status": item.get("status", "N/V"),
            "Rows": item.get("rows", 0),
            "Hinweis": spec.note,
        }
    )

st.dataframe(
    pd.DataFrame(registry),
    use_container_width=True,
    hide_index=True,
)

st.warning(
    "**Point-in-Time:** "
    + result["data_quality"]["point_in_time"]["warning"]
)


with st.expander(
    "Methodik · Hierarchie",
    expanded=False,
):
    st.markdown(
        """
**V3.24-Hierarchie**

1. **Business Cycle Core** bestimmt `EXPANSION / SLOWDOWN / CONTRACTION / RECOVERY`.
2. **Imminent Recession Cluster** wird nur innerhalb `SLOWDOWN` aktiviert.
3. **Model Breadth / Scatter** beschreibt Breite und Persistenz, bestimmt aber nicht das Regime.
4. **Liquidity Modifier** erklärt Amplitude, Verzögerung und Overshoot, überschreibt den Cycle nicht.
5. Die bestehende COT-, Seasonality-, Marktstruktur- und Execution-Logik bleibt außerhalb dieses Moduls.

**Wichtig:** Dies ist eine eigene, transparente Implementierung öffentlich beschriebener
Business-Cycle-Prinzipien. Proprietäre Zeberg-Gewichte, Glättungen und Equilibrium-Formeln
sind nicht bekannt und werden nicht behauptet oder nachgebaut.
"""
    )
