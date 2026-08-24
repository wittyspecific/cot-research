from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.seasonality_edge_research import (
    current_phase_day,
    seasonal_template,
    seasonal_turns,
)


# V3.30.6 · SHARED SEASONAL PATH CHART


@dataclass(frozen=True)
class SeasonalPathChartState:
    available: bool
    history_years: int
    sample_size: int
    phase_day: int | None
    reason: str = ""


def build_seasonal_path_figure(
    prices: pd.DataFrame,
    *,
    history_years: int = 20,
) -> tuple[go.Figure | None, SeasonalPathChartState]:
    template = seasonal_template(
        prices,
        years=int(history_years),
    )
    phase_day = current_phase_day(prices)

    if template is None or template.empty:
        return (
            None,
            SeasonalPathChartState(
                available=False,
                history_years=int(history_years),
                sample_size=0,
                phase_day=phase_day,
                reason=(
                    "Keine ausreichende abgeschlossene Preishistorie "
                    "für den saisonalen Jahrespfad."
                ),
            ),
        )

    sample_size = 0
    if "sample_size" in template.columns:
        sample_values = pd.to_numeric(
            template["sample_size"],
            errors="coerce",
        ).dropna()
        if not sample_values.empty:
            sample_size = int(sample_values.max())

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=template["phase_day"],
            y=template["q75_pct"],
            mode="lines",
            name="75%-Quantil",
            line=dict(width=0, color="rgba(101,217,139,0)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=template["phase_day"],
            y=template["q25_pct"],
            mode="lines",
            name="25–75% Band",
            line=dict(width=0, color="rgba(101,217,139,0)"),
            fill="tonexty",
            fillcolor="rgba(101,217,139,0.48)",
            hoverinfo="skip",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=template["phase_day"],
            y=template["median_pct"],
            mode="lines",
            name=f"Median · {sample_size or int(history_years)}J",
            line=dict(width=2.4, color="#FF7373"),
            hovertemplate=(
                "Handelstag %{x}<br>"
                "Median %{y:.2f}%"
                "<extra></extra>"
            ),
        )
    )

    turns = seasonal_turns(template)

    if turns is not None and not turns.empty:
        tops = turns[turns["turn_type"].eq("TOP")]
        bottoms = turns[turns["turn_type"].eq("BOTTOM")]

        if not bottoms.empty:
            fig.add_trace(
                go.Scatter(
                    x=bottoms["phase_day"],
                    y=bottoms["seasonal_level_pct"],
                    mode="markers",
                    name="Seasonal Bottoms",
                    marker=dict(size=6, color="#B59BFF"),
                    hovertemplate=(
                        "Seasonal Bottom<br>"
                        "Tag %{x}<br>"
                        "%{y:.2f}%"
                        "<extra></extra>"
                    ),
                )
            )

        if not tops.empty:
            fig.add_trace(
                go.Scatter(
                    x=tops["phase_day"],
                    y=tops["seasonal_level_pct"],
                    mode="markers",
                    name="Seasonal Tops",
                    marker=dict(size=6, color="#F2B84B"),
                    hovertemplate=(
                        "Seasonal Top<br>"
                        "Tag %{x}<br>"
                        "%{y:.2f}%"
                        "<extra></extra>"
                    ),
                )
            )

    if phase_day is not None:
        fig.add_vline(
            x=int(phase_day),
            line_width=1.4,
            line_dash="dash",
            line_color="#657382",
            annotation_text="aktuelle Phase",
            annotation_position="top right",
            annotation_font=dict(color="#F3F6FB", size=11),
        )

    fig.update_layout(
        height=440,
        margin=dict(l=6, r=6, t=22, b=0),
        paper_bgcolor="#081018",
        plot_bgcolor="#081018",
        font=dict(color="#C8D1DC"),
        xaxis=dict(
            title="Normalisierter Handelstag im Jahr",
            gridcolor="#22303D",
            linecolor="#22303D",
            zeroline=False,
        ),
        yaxis=dict(
            title="Kumulativer saisonaler Log-Return (%)",
            gridcolor="#22303D",
            linecolor="#22303D",
            zeroline=True,
            zerolinecolor="#34424F",
        ),
        legend=dict(
            orientation="h",
            y=-0.16,
            x=0,
            font=dict(color="#C8D1DC", size=11),
        ),
        hovermode="x",
    )

    return (
        fig,
        SeasonalPathChartState(
            available=True,
            history_years=int(history_years),
            sample_size=sample_size,
            phase_day=phase_day,
        ),
    )


def render_seasonal_path_chart(
    prices: pd.DataFrame,
    *,
    history_years: int = 20,
    key: str | None = None,
) -> SeasonalPathChartState:
    fig, state = build_seasonal_path_figure(
        prices,
        history_years=history_years,
    )

    if fig is None:
        st.info(state.reason or "Insufficient Data")
        return state

    kwargs = {
        "use_container_width": True,
        "config": {
            "displaylogo": False,
            "displayModeBar": False,
        },
    }

    if key is not None:
        kwargs["key"] = key

    st.plotly_chart(
        fig,
        **kwargs,
    )

    st.caption(
        "Median abgeschlossener Jahre · 25–75%-Band = Streuung der "
        "historischen Saisonpfade · Tops/Bottoms markieren Wendepunkte · "
        "gestrichelte Linie = aktuelle normalisierte Jahresphase."
    )

    return state
