from __future__ import annotations
# V3.19.3 · CURRENCY-BLOCK ROBUSTNESS
# V3.19.2 · STRICT RETROSPECTIVE OOS CONFLICT VALIDATION
# V3.19.1 · REGIME-AWARE COT X RATES EVENT STUDY

import numpy as np
import pandas as pd
import streamlit as st

from src.rates_cot_ml import run_rates_cot_ml_study
from src.style import apply_style, page_header, section_line
from src.yield_cot_fx_returns import run_yield_cot_fx_return_study
from src.yield_cot_regime_event_study import run_regime_aware_event_study
from src.yield_cot_conflict_oos import run_strict_conflict_validation_v3192
from src.yield_cot_currency_block import run_currency_block_robustness_v3193

# V3.20.0 · ADVANCED DIRECT ACCESS GUARD
_v3200_trader = dict(st.session_state.get("auth_trader") or {})
if (
    not _v3200_trader
    or str(_v3200_trader.get("role", "TRADER")).upper() != "ADMIN"
):
    st.error("Kein Zugriff auf den Advanced-Bereich.")
    st.stop()



# V3.19.0 · YIELD X COT ADVANCED RESEARCH
apply_style()


@st.cache_data(
    ttl=6 * 60 * 60,
    show_spinner=False,
)
def _run_fx_return_study_v3190():
    return run_yield_cot_fx_return_study()


@st.cache_data(
    ttl=6 * 60 * 60,
    show_spinner=False,
)
def _run_legacy_rates_cot_v3190():
    return run_rates_cot_ml_study()


def _fmt_date(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    return pd.Timestamp(value).strftime(
        "%d.%m.%Y"
    )


def _direction_label(value) -> str:
    try:
        direction = int(value)
    except Exception:
        direction = 0
    if direction > 0:
        return "BULLISH"
    if direction < 0:
        return "BEARISH"
    return "NEUTRAL"


def _format_metric_table(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    out = frame.copy()
    return out


page_header(
    "Advanced · Macro Research",
    "Yield x COT",
    (
        "Liefert die Kombination aus Positionierung und "
        "2Y-Zinsrepricing einen messbaren Edge für FX-Returns?"
    ),
    "V3.19.0 · COT × RATES → FX RETURNS",
)

st.info(
    "Der frühere Rates→COT-Test bleibt als Forschungsarchiv erhalten. "
    "Der neue Primärtest richtet beide Fundamentalblöcke direkt auf den "
    "FX-Markt: COT-only vs. Rates-only vs. COT+Rates."
)

fx_tab, legacy_tab = st.tabs(
    [
        "COT + Rates → FX Returns",
        "Rates → COT · bisherige Forschung",
    ]
)


with fx_tab:
    section_line(
        "FX Return Study",
        "1W · 4W · 8W Forward Returns · Walk-forward",
    )
    st.caption(
        "Untersucht werden unabhängige State-Change-Episoden. "
        "COT nutzt den konservativen historischen Verfügbarkeitsanker; "
        "Rates erhalten zusätzlich 5 Business Days Safety Lag. "
        "20D-Rates werden gegen ihre eigene historische 5J-Verteilung "
        "normalisiert. Kein Random Split."
    )

    if st.button(
        "FX-Return-Studie starten",
        key="v3190_run_fx_returns",
        type="primary",
    ):
        st.session_state[
            "_v3190_fx_requested"
        ] = True

    if st.session_state.get(
        "_v3190_fx_requested",
        False,
    ):
        try:
            with st.spinner(
                "COT-, Yield- und historische FX-Daten werden "
                "as-of rekonstruiert und Walk-forward getestet …"
            ):
                result = (
                    _run_fx_return_study_v3190()
                )

            meta = result.get(
                "meta",
                {},
            )
            baseline = result.get(
                "baseline",
                pd.DataFrame(),
            )
            ablation = result.get(
                "ablation",
                pd.DataFrame(),
            )
            incremental = result.get(
                "incremental_read",
                {},
            )
            current = result.get(
                "current",
                pd.DataFrame(),
            )

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric(
                    "Währungen",
                    str(
                        len(
                            meta.get(
                                "currencies",
                                [],
                            )
                        )
                    ),
                )
            with c2:
                st.metric(
                    "FX-Paare",
                    str(
                        int(
                            meta.get(
                                "pairs",
                                0,
                            )
                            or 0
                        )
                    ),
                )
            with c3:
                st.metric(
                    "State-Episoden",
                    str(
                        int(
                            meta.get(
                                "episodes",
                                0,
                            )
                            or 0
                        )
                    ),
                )
            with c4:
                st.metric(
                    "8W Returns bekannt",
                    str(
                        int(
                            meta.get(
                                "known_8w_returns",
                                0,
                            )
                            or 0
                        )
                    ),
                )

            st.caption(
                "Zeitraum: "
                f"{_fmt_date(meta.get('first_event'))} "
                f"bis {_fmt_date(meta.get('last_event'))} · "
                f"Rates Safety Lag "
                f"{int(meta.get('rates_safety_lag_bdays', 0) or 0)} BD · "
                f"Purge {int(meta.get('purge_weeks', 0) or 0)}W"
            )

            st.markdown(
                "### 1 · Einfache Baseline · was macht der FX-Preis?"
            )
            st.caption(
                "Hier gibt es noch kein ML. Renditen werden jeweils in die "
                "fundamentale Richtung gedreht: positiv bedeutet, dass das "
                "Paar dem jeweiligen COT-/Rates-Bias gefolgt ist."
            )

            if baseline.empty:
                st.warning(
                    "Keine ausreichenden State-Episoden mit "
                    "Forward-Returns verfügbar."
                )
            else:
                b = baseline.copy()
                b["Hit Rate"] = b[
                    "Hit Rate"
                ].map(
                    lambda x: (
                        "—"
                        if pd.isna(x)
                        else f"{x:.1%}"
                    )
                )
                for col in (
                    "Median Return",
                    "Mean Return",
                ):
                    b[col] = b[col].map(
                        lambda x: (
                            "—"
                            if pd.isna(x)
                            else f"{x:+.2%}"
                        )
                    )

                st.dataframe(
                    b,
                    use_container_width=True,
                    hide_index=True,
                )

            st.markdown(
                "### 2 · Feature-Ablation · COT vs. Rates vs. Combined"
            )
            st.caption(
                "Das ist der zentrale Test. Wenn COT+Rates COT-only "
                "Out-of-Sample nicht verbessert, wird Alignment nicht als "
                "zusätzlicher quantitativer Edge bezeichnet."
            )

            if ablation.empty:
                st.warning(
                    "Noch nicht genügend OOS-Samples für die Ablation."
                )
            else:
                a = ablation.copy()

                percent_cols = {
                    "positive_rate": "Basisrate",
                    "brier_skill": "Brier Skill",
                }
                for source, label in percent_cols.items():
                    if source in a.columns:
                        a[label] = pd.to_numeric(
                            a[source],
                            errors="coerce",
                        ).map(
                            lambda x: (
                                "—"
                                if pd.isna(x)
                                else f"{x:+.1%}"
                                if source == "brier_skill"
                                else f"{x:.1%}"
                            )
                        )

                for source, label in (
                    ("brier_model", "Brier ML"),
                    ("brier_baseline", "Brier Basis"),
                    ("roc_auc", "ROC-AUC"),
                    ("Δ Brier vs COT", "Δ Brier vs COT"),
                    ("Δ AUC vs COT", "Δ AUC vs COT"),
                ):
                    if source in a.columns:
                        a[label] = pd.to_numeric(
                            a[source],
                            errors="coerce",
                        ).map(
                            lambda x: (
                                "—"
                                if pd.isna(x)
                                else f"{x:+.3f}"
                                if source.startswith("Δ")
                                else f"{x:.3f}"
                            )
                        )

                display_cols = [
                    c
                    for c in (
                        "Horizont",
                        "Modell",
                        "validation",
                        "oos_n",
                        "folds",
                        "Basisrate",
                        "Brier ML",
                        "Brier Basis",
                        "Brier Skill",
                        "ROC-AUC",
                        "Δ Brier vs COT",
                        "Δ AUC vs COT",
                    )
                    if c in a.columns
                ]
                st.dataframe(
                    a[display_cols],
                    use_container_width=True,
                    hide_index=True,
                )

                label = str(
                    incremental.get(
                        "label",
                        "INSUFFICIENT DATA",
                    )
                )
                text = str(
                    incremental.get(
                        "text",
                        "",
                    )
                )
                brier_gain = incremental.get(
                    "brier_gain_vs_cot",
                    np.nan,
                )
                auc_gain = incremental.get(
                    "auc_gain_vs_cot",
                    np.nan,
                )
                detail = (
                    f"{text} "
                    f"4W ΔBrier vs COT "
                    f"{brier_gain:+.3f} · "
                    f"ΔAUC {auc_gain:+.3f}"
                    if (
                        np.isfinite(
                            float(brier_gain)
                        )
                        and np.isfinite(
                            float(auc_gain)
                        )
                    )
                    else text
                )

                if label.startswith(
                    "RATES ADD"
                ):
                    st.success(
                        f"{label}: {detail}"
                    )
                elif label.startswith(
                    "SMALL"
                ):
                    st.info(
                        f"{label}: {detail}"
                    )
                else:
                    st.warning(
                        f"{label}: {detail}"
                    )

            st.markdown(
                "### 3 · Aktuelle COT × Rates Konstellationen"
            )
            st.caption(
                "Die Wahrscheinlichkeiten sind Research-Ausgaben. "
                "Sie dürfen nur dann als interessant gelten, wenn das "
                "jeweilige 4W-Modell oben tatsächlich positiven "
                "Walk-forward-Mehrwert zeigt."
            )

            if current.empty:
                st.info(
                    "Keine aktuellen gemeinsamen COT-/Rates-Zustände."
                )
            else:
                cur = current.copy()
                cur["COT"] = cur[
                    "cot_pair_direction"
                ].map(
                    {
                        1: "BULLISH",
                        -1: "BEARISH",
                        0: "NEUTRAL",
                    }
                )
                cur["Rates 20D"] = cur[
                    "rates20_direction"
                ].map(
                    {
                        1: "BULLISH",
                        -1: "BEARISH",
                        0: "NEUTRAL",
                    }
                )
                cur["20D Pctl"] = pd.to_numeric(
                    cur[
                        "rates20_percentile"
                    ],
                    errors="coerce",
                ).map(
                    lambda x: (
                        "—"
                        if pd.isna(x)
                        else f"{x:.0f}%"
                    )
                )
                for col in (
                    "P 4W · COT",
                    "P 4W · Rates",
                    "P 4W · Combined",
                ):
                    if col in cur.columns:
                        cur[col] = pd.to_numeric(
                            cur[col],
                            errors="coerce",
                        ).map(
                            lambda x: (
                                "—"
                                if pd.isna(x)
                                else f"{x:.1%}"
                            )
                        )

                st.dataframe(
                    cur[
                        [
                            c
                            for c in (
                                "pair",
                                "relation",
                                "COT",
                                "Rates 20D",
                                "20D Pctl",
                                "rates_alignment_count",
                                "P 4W · COT",
                                "P 4W · Rates",
                                "P 4W · Combined",
                                "Combined OOS",
                            )
                            if c in cur.columns
                        ]
                    ].rename(
                        columns={
                            "pair": "Paar",
                            "relation": "Fundamental State",
                            "rates_alignment_count": (
                                "Rates Alignment"
                            ),
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            with st.expander(
                "4 · Robustheit nach FX-Paar / Datenfehler",
                expanded=False,
            ):
                by_pair = result.get(
                    "oos_by_pair",
                    pd.DataFrame(),
                )
                errors = result.get(
                    "errors",
                    pd.DataFrame(),
                )

                if not by_pair.empty:
                    st.markdown(
                        "**Combined 4W · OOS nach FX-Paar**"
                    )
                    st.dataframe(
                        by_pair,
                        use_container_width=True,
                        hide_index=True,
                    )

                if not errors.empty:
                    st.markdown(
                        "**Übersprungene Daten / Paare**"
                    )
                    st.dataframe(
                        errors,
                        use_container_width=True,
                        hide_index=True,
                    )


            # V3.19.1 · REGIME-AWARE EVENT STUDY UI
            st.markdown("---")
            st.markdown("## 4 · Regime-Aware COT × Rates Event Study")
            st.caption(
                "Die COT-Logik wird NICHT verändert. Für diese Research-Auswertung werden nur die bestehenden "
                "Phasen lesbarer gruppiert: EXTREME → WATCH, TRANSITION → EARLY, RELEASE/CONFIRMED → ACTIVE."
            )

            _v3191 = run_regime_aware_event_study(result)
            _meta = _v3191.get("meta", {})
            _c1, _c2, _c3, _c4 = st.columns(4)
            _c1.metric("Regime-Episoden", str(int(_meta.get("events", 0) or 0)))
            _c2.metric("WATCH", str(int(_meta.get("watch", 0) or 0)))
            _c3.metric("EARLY", str(int(_meta.get("early", 0) or 0)))
            _c4.metric("ACTIVE", str(int(_meta.get("active", 0) or 0)))

            st.markdown("### 4.1 · COT-Reifegrad allein")
            _stage = _v3191.get("stage_baseline", pd.DataFrame())
            if not _stage.empty:
                _show = _stage.copy()
                _show["Hit Rate"] = _show["Hit Rate"].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
                _show["95% Hit CI"] = _stage.apply(
                    lambda r: "—" if pd.isna(r["CI Low"]) else f"{r['CI Low']:.1%} – {r['CI High']:.1%}", axis=1
                )
                for _col in ("Median Return", "Mean Return"):
                    _show[_col] = _show[_col].map(lambda x: "—" if pd.isna(x) else f"{x:+.2%}")
                st.dataframe(
                    _show[["COT Stage", "Horizont", "n", "Hit Rate", "95% Hit CI", "Median Return", "Mean Return"]],
                    use_container_width=True, hide_index=True,
                )

            st.markdown("### 4.2 · Bringt Rates-Alignment innerhalb desselben COT-Stages etwas?")
            st.caption(
                "ACTIVE wird nur mit ACTIVE verglichen, EARLY nur mit EARLY und WATCH nur mit WATCH. "
                "Damit werden EXTREME/TRANSITION/RELEASE nicht mehr in einen Topf geworfen."
            )
            _ladder = _v3191.get("alignment_ladder", pd.DataFrame())
            if not _ladder.empty:
                _show = _ladder.copy()
                for _col in ("Hit Rate", "Δ Hit vs COT"):
                    _show[_col] = pd.to_numeric(_show[_col], errors="coerce").map(
                        lambda x: "—" if pd.isna(x) else f"{x:+.1%}"
                    )
                for _col in ("Median Return", "Mean Return", "Δ Median vs COT"):
                    _show[_col] = pd.to_numeric(_show[_col], errors="coerce").map(
                        lambda x: "—" if pd.isna(x) else f"{x:+.2%}"
                    )
                _show["95% Hit CI"] = _ladder.apply(
                    lambda r: "—" if pd.isna(r["CI Low"]) else f"{r['CI Low']:.1%} – {r['CI High']:.1%}", axis=1
                )
                st.dataframe(
                    _show[["COT Stage", "Scenario", "Horizont", "n", "Hit Rate", "95% Hit CI", "Median Return", "Mean Return", "Δ Hit vs COT", "Δ Median vs COT"]],
                    use_container_width=True, hide_index=True,
                )

            st.markdown("### 4.3 · ACTIVE/EARLY Conflict · wem folgt der Preis?")
            st.caption("Nur STRONG/EXTREME 20D-Rates-Konflikte; dieselben Episoden werden einmal in COT- und einmal in Rates-Richtung ausgewertet.")
            _conf = _v3191.get("conflicts", pd.DataFrame())
            if not _conf.empty:
                _show = _conf.copy()
                _show["Hit Rate"] = _show["Hit Rate"].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
                for _col in ("Median Return", "Mean Return"):
                    _show[_col] = _show[_col].map(lambda x: "—" if pd.isna(x) else f"{x:+.2%}")
                st.dataframe(
                    _show[["COT Stage", "Conflict View", "Horizont", "n", "Hit Rate", "Median Return", "Mean Return"]],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("Keine ausreichenden ACTIVE/EARLY STRONG/EXTREME Conflict-Episoden mit Forward-Returns.")

            st.caption(
                "V3.19.1 ist bewusst zuerst eine Event Study und noch kein neues ML-Modell. "
                "Nur wenn innerhalb gleicher COT-Reifegrade ein stabiler Unterschied sichtbar wird, "
                "lohnt sich ein gezielter neuer Walk-forward-Test. Die COT-Logik selbst bleibt unverändert."
            )

            # V3.19.2 · STRICT RETROSPECTIVE OOS CONFLICT VALIDATION UI
            st.markdown("---")
            st.markdown(
                "## 5 · Frozen Conflict Hypotheses · Strict Validation"
            )
            st.caption(
                "Die Regeln werden hier NICHT weiter optimiert. "
                "H1/H2/H3 sind exakt aus V3.19.1 eingefroren. "
                "Überlappende 8W- bzw. 4W-Ereignisse werden pro FX-Paar "
                "entfernt. Weil die Hypothesen auf derselben Historie "
                "entdeckt wurden, ist dies eine retrospektive "
                "OOS-/Robustheitsvalidierung und noch kein pristine "
                "unseen Holdout."
            )

            _v3192 = run_strict_conflict_validation_v3192(result)
            _v3192_summary = _v3192.get(
                "summary",
                pd.DataFrame(),
            )
            _v3192_meta = _v3192.get(
                "meta",
                {},
            )

            st.caption(
                "Hypothesen-Freeze: "
                f"{pd.Timestamp(_v3192_meta.get('freeze_date')).strftime('%d.%m.%Y')} · "
                f"Cluster-Bootstrap: "
                f"{int(_v3192_meta.get('bootstrap_reps', 0) or 0)} Replikationen · "
                "COT-Core-Logik unverändert."
            )

            if _v3192_summary.empty:
                st.warning(
                    "Keine ausreichenden Episoden für V3.19.2."
                )
            else:
                _v3192_show = _v3192_summary.copy()

                _v3192_show["95% Hit CI"] = _v3192_summary.apply(
                    lambda row: (
                        "—"
                        if pd.isna(row["Hit CI Low"])
                        else (
                            f"{row['Hit CI Low']:.1%} – "
                            f"{row['Hit CI High']:.1%}"
                        )
                    ),
                    axis=1,
                )
                _v3192_show["Hit Rate"] = _v3192_show[
                    "Hit Rate"
                ].map(
                    lambda x: "—" if pd.isna(x) else f"{x:.1%}"
                )
                _v3192_show["Binomial p"] = _v3192_show[
                    "Binomial p"
                ].map(
                    lambda x: "—" if pd.isna(x) else f"{x:.4f}"
                )
                for _col in (
                    "Median Return",
                    "Mean Return",
                    "Pair Bootstrap Low",
                    "Pair Bootstrap High",
                ):
                    _v3192_show[_col] = _v3192_show[
                        _col
                    ].map(
                        lambda x: "—" if pd.isna(x) else f"{x:+.2%}"
                    )
                for _col in (
                    "Year + Share",
                    "Pair + Share",
                ):
                    _v3192_show[_col] = _v3192_show[
                        _col
                    ].map(
                        lambda x: "—" if pd.isna(x) else f"{x:.1%}"
                    )

                st.dataframe(
                    _v3192_show[
                        [
                            "Hypothese",
                            "Status",
                            "n",
                            "Hit Rate",
                            "95% Hit CI",
                            "Binomial p",
                            "Median Return",
                            "Mean Return",
                            "Pair Bootstrap Low",
                            "Pair Bootstrap High",
                            "Year + Share",
                            "Pair + Share",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                _v3192_h1 = _v3192_summary[
                    _v3192_summary[
                        "Hypothese"
                    ].astype(str).str.startswith("H1")
                ]
                _v3192_h2 = _v3192_summary[
                    _v3192_summary[
                        "Hypothese"
                    ].astype(str).str.startswith("H2")
                ]

                _v3192_primary_statuses = set(
                    pd.concat(
                        [_v3192_h1, _v3192_h2],
                        ignore_index=True,
                    )["Status"].astype(str).tolist()
                )

                if (
                    "ROBUST RETROSPECTIVE"
                    in _v3192_primary_statuses
                ):
                    st.success(
                        "Mindestens eine der eingefrorenen Conflict-Hypothesen "
                        "übersteht die konservative retrospektive Validierung. "
                        "Das ist ein ernstzunehmender Befund, aber wegen der "
                        "vorherigen Hypothesenentdeckung noch kein pristine "
                        "Future-OOS-Beweis."
                    )
                elif any(
                    status.startswith("PROMISING")
                    for status in _v3192_primary_statuses
                ):
                    st.info(
                        "Mindestens eine Conflict-Hypothese bleibt nach "
                        "De-Overlap und Robustheitschecks interessant, ist "
                        "aber noch nicht bestätigt."
                    )
                else:
                    st.warning(
                        "Die eingefrorenen Conflict-Hypothesen werden durch "
                        "die strengere Validierung nicht bestätigt."
                    )

            with st.expander(
                "5.1 · Stabilität nach Jahr",
                expanded=False,
            ):
                _v3192_year = _v3192.get(
                    "by_year",
                    pd.DataFrame(),
                )
                if _v3192_year.empty:
                    st.info(
                        "Keine Jahresauswertung verfügbar."
                    )
                else:
                    _v3192_year_show = _v3192_year.copy()
                    _v3192_year_show["Hit Rate"] = _v3192_year_show[
                        "Hit Rate"
                    ].map(
                        lambda x: "—" if pd.isna(x) else f"{x:.1%}"
                    )
                    for _col in ("Median Return", "Mean Return"):
                        _v3192_year_show[_col] = _v3192_year_show[
                            _col
                        ].map(
                            lambda x: "—" if pd.isna(x) else f"{x:+.2%}"
                        )
                    st.dataframe(
                        _v3192_year_show,
                        use_container_width=True,
                        hide_index=True,
                    )

            with st.expander(
                "5.2 · Stabilität nach FX-Paar",
                expanded=False,
            ):
                _v3192_pair = _v3192.get(
                    "by_pair",
                    pd.DataFrame(),
                )
                if _v3192_pair.empty:
                    st.info(
                        "Keine Paar-Auswertung verfügbar."
                    )
                else:
                    _v3192_pair_show = _v3192_pair.copy()
                    _v3192_pair_show["Hit Rate"] = _v3192_pair_show[
                        "Hit Rate"
                    ].map(
                        lambda x: "—" if pd.isna(x) else f"{x:.1%}"
                    )
                    for _col in ("Median Return", "Mean Return"):
                        _v3192_pair_show[_col] = _v3192_pair_show[
                            _col
                        ].map(
                            lambda x: "—" if pd.isna(x) else f"{x:+.2%}"
                        )
                    st.dataframe(
                        _v3192_pair_show,
                        use_container_width=True,
                        hide_index=True,
                    )

            st.caption(
                "V3.19.2 verändert weder EXTREME/TRANSITION/RELEASE, "
                "noch Commercial-Schwellen, Micro-Trigger oder irgendeine "
                "Trading-Logik. Bei positiver retrospektiver Validierung "
                "würde der nächste echte Test darin bestehen, die eingefrorene "
                "Regel ab jetzt auf neuen zukünftigen Daten zu beobachten."
            )


            # V3.19.3 · CURRENCY-BLOCK ROBUSTNESS UI
            st.markdown("---")
            st.markdown(
                "## 6 · Currency-Block Robustness · H1/H2"
            )
            st.caption(
                "Letzter historischer Robustheitstest für die bereits "
                "eingefrorenen H1/H2-Regeln. Keine neue Schwelle, kein ML "
                "und keine Parametersuche. Geprüft wird nur, ob der Effekt "
                "hauptsächlich von JPY-Paaren oder einem anderen einzelnen "
                "Währungsblock getragen wird."
            )

            _v3193 = run_currency_block_robustness_v3193(result)
            _v3193_summary = _v3193.get(
                "summary",
                pd.DataFrame(),
            )
            _v3193_blocks = _v3193.get(
                "blocks",
                pd.DataFrame(),
            )

            st.markdown(
                "### 6.1 · JPY-Control und Gesamturteil"
            )

            if _v3193_summary.empty:
                st.warning(
                    "Keine ausreichenden V3.19.3 Daten verfügbar."
                )
            else:
                _v3193_summary_show = _v3193_summary.copy()

                for _col in (
                    "All Hit",
                    "ONLY JPY Hit",
                    "EX JPY Hit",
                    "EX JPY Δ Hit",
                    "LOCO Survive Share",
                    "Worst LOCO Hit",
                ):
                    if _col in _v3193_summary_show:
                        _v3193_summary_show[_col] = pd.to_numeric(
                            _v3193_summary_show[_col],
                            errors="coerce",
                        ).map(
                            lambda x: (
                                "—"
                                if pd.isna(x)
                                else f"{x:+.1%}"
                                if "Δ" in _col
                                else f"{x:.1%}"
                            )
                        )

                for _col in (
                    "EX JPY Mean",
                    "Worst LOCO Mean",
                ):
                    if _col in _v3193_summary_show:
                        _v3193_summary_show[_col] = pd.to_numeric(
                            _v3193_summary_show[_col],
                            errors="coerce",
                        ).map(
                            lambda x: (
                                "—"
                                if pd.isna(x)
                                else f"{x:+.2%}"
                            )
                        )

                st.dataframe(
                    _v3193_summary_show,
                    use_container_width=True,
                    hide_index=True,
                )

                _v3193_statuses = set(
                    _v3193_summary[
                        "Status"
                    ].astype(str).tolist()
                )

                if "BROAD CURRENCY ROBUSTNESS" in _v3193_statuses:
                    st.success(
                        "Mindestens eine eingefrorene Conflict-Hypothese "
                        "bleibt auch ohne JPY und über die meisten "
                        "Leave-One-Currency-Out-Blöcke positiv. Das wäre "
                        "breiter als ein reiner JPY-Effekt, bleibt aber "
                        "historische Robustheit und kein Future-OOS-Beweis."
                    )
                elif "JPY-DEPENDENT" in _v3193_statuses:
                    st.warning(
                        "Mindestens eine Hypothese ist stark JPY-abhängig. "
                        "Dann darf sie nicht als allgemeiner COT/Rates-"
                        "Conflict-Effekt interpretiert werden."
                    )
                else:
                    st.info(
                        "Die Währungsblock-Robustheit ist gemischt. "
                        "Der historische Effekt ist weder sauber breit "
                        "noch eindeutig nur JPY-getrieben."
                    )

            st.markdown(
                "### 6.2 · ONLY JPY vs. EX JPY"
            )

            if not _v3193_blocks.empty:
                _v3193_jpy = _v3193_blocks[
                    _v3193_blocks["Block"].isin(
                        ["ALL", "ONLY JPY", "EX JPY"]
                    )
                ].copy()

                _v3193_jpy["95% Hit CI"] = _v3193_jpy.apply(
                    lambda row: (
                        "—"
                        if pd.isna(row["Hit CI Low"])
                        else (
                            f"{row['Hit CI Low']:.1%} – "
                            f"{row['Hit CI High']:.1%}"
                        )
                    ),
                    axis=1,
                )

                for _col in (
                    "Hit Rate",
                    "Positive Pair Share",
                    "Δ Hit vs All",
                ):
                    _v3193_jpy[_col] = pd.to_numeric(
                        _v3193_jpy[_col],
                        errors="coerce",
                    ).map(
                        lambda x: (
                            "—"
                            if pd.isna(x)
                            else f"{x:+.1%}"
                            if _col.startswith("Δ")
                            else f"{x:.1%}"
                        )
                    )

                for _col in (
                    "Median Return",
                    "Mean Return",
                    "Δ Mean vs All",
                ):
                    _v3193_jpy[_col] = pd.to_numeric(
                        _v3193_jpy[_col],
                        errors="coerce",
                    ).map(
                        lambda x: (
                            "—"
                            if pd.isna(x)
                            else f"{x:+.2%}"
                        )
                    )

                _v3193_jpy["Binomial p"] = pd.to_numeric(
                    _v3193_jpy["Binomial p"],
                    errors="coerce",
                ).map(
                    lambda x: (
                        "—"
                        if pd.isna(x)
                        else f"{x:.4f}"
                    )
                )

                st.dataframe(
                    _v3193_jpy[
                        [
                            "Hypothese",
                            "Block",
                            "n",
                            "Pairs",
                            "Hit Rate",
                            "95% Hit CI",
                            "Binomial p",
                            "Median Return",
                            "Mean Return",
                            "Positive Pair Share",
                            "Δ Hit vs All",
                            "Δ Mean vs All",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            with st.expander(
                "6.3 · Leave-One-Currency-Out",
                expanded=False,
            ):
                if _v3193_blocks.empty:
                    st.info(
                        "Keine Leave-One-Currency-Out-Daten verfügbar."
                    )
                else:
                    _v3193_loco = _v3193_blocks[
                        _v3193_blocks[
                            "Block Type"
                        ].eq("LEAVE_ONE_OUT")
                    ].copy()

                    for _col in (
                        "Hit Rate",
                        "Positive Pair Share",
                        "Δ Hit vs All",
                    ):
                        _v3193_loco[_col] = pd.to_numeric(
                            _v3193_loco[_col],
                            errors="coerce",
                        ).map(
                            lambda x: (
                                "—"
                                if pd.isna(x)
                                else f"{x:+.1%}"
                                if _col.startswith("Δ")
                                else f"{x:.1%}"
                            )
                        )

                    for _col in (
                        "Median Return",
                        "Mean Return",
                        "Δ Mean vs All",
                    ):
                        _v3193_loco[_col] = pd.to_numeric(
                            _v3193_loco[_col],
                            errors="coerce",
                        ).map(
                            lambda x: (
                                "—"
                                if pd.isna(x)
                                else f"{x:+.2%}"
                            )
                        )

                    st.dataframe(
                        _v3193_loco[
                            [
                                "Hypothese",
                                "Block",
                                "n",
                                "Pairs",
                                "Hit Rate",
                                "Median Return",
                                "Mean Return",
                                "Positive Pair Share",
                                "Δ Hit vs All",
                                "Δ Mean vs All",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

            st.caption(
                "Interpretation: Wenn EX JPY deutlich zusammenbricht, "
                "während ONLY JPY stark bleibt, ist der Effekt JPY-spezifisch. "
                "Wenn EX JPY und die meisten Leave-One-Currency-Out-Blöcke "
                "positiv bleiben, spricht das für breitere historische "
                "Robustheit. Danach wird die historische Parametersuche "
                "beendet; eine endgültige Bestätigung müsste auf neuen "
                "zukünftigen Daten erfolgen. Die COT-Logik bleibt unverändert."
            )

            st.caption(
                "Research only: Dieses Modul ändert keine Watchlist, "
                "keinen Trade-Bias, kein Journal, kein Risiko und keine "
                "Execution. Ein positiver Befund muss über Zeit und "
                "mehrere Paare stabil bleiben."
            )

        except Exception as exc:
            st.error(
                "FX-Return-Studie konnte nicht abgeschlossen werden: "
                f"{type(exc).__name__}: {exc}"
            )


with legacy_tab:
    section_line(
        "Rates → COT · bisherige Forschung",
        "V3.18.0 / V3.18.1 · archivierter Hypothesentest",
    )
    st.caption(
        "Dieser Bereich wurde aus Währungsstärke hierher verschoben. "
        "Der bisherige Befund bleibt sichtbar: Transition-ML war stark, "
        "aber die Ablation zeigte keinen klaren inkrementellen Rates-Wert; "
        "STRICT LEAD trug Out-of-Sample nicht."
    )

    if st.button(
        "Rates→COT-Studie laden",
        key="v3190_run_legacy_rates_cot",
        type="secondary",
    ):
        st.session_state[
            "_v3190_legacy_requested"
        ] = True

    if st.session_state.get(
        "_v3190_legacy_requested",
        False,
    ):
        try:
            with st.spinner(
                "Bestehende Rates→COT-Studie wird geladen …"
            ):
                legacy = (
                    _run_legacy_rates_cot_v3190()
                )

            metrics = legacy.get(
                "metrics",
                pd.DataFrame(),
            )
            baseline = legacy.get(
                "baseline",
                pd.DataFrame(),
            )
            ablation = legacy.get(
                "ablation",
                pd.DataFrame(),
            )
            strict = legacy.get(
                "strict_subsets",
                pd.DataFrame(),
            )
            sequence = legacy.get(
                "sequence_baseline",
                pd.DataFrame(),
            )

            st.markdown(
                "### Ursprünglicher Walk-forward-Befund"
            )
            if not metrics.empty:
                st.dataframe(
                    metrics,
                    use_container_width=True,
                    hide_index=True,
                )

            st.markdown(
                "### Historische Lead/Lag-Baseline"
            )
            if not baseline.empty:
                st.dataframe(
                    baseline,
                    use_container_width=True,
                    hide_index=True,
                )

            st.markdown(
                "### Feature-Ablation"
            )
            if not ablation.empty:
                st.dataframe(
                    ablation,
                    use_container_width=True,
                    hide_index=True,
                )

            st.markdown(
                "### Echter Rates-Lead · STRICT LEAD"
            )
            if not strict.empty:
                st.dataframe(
                    strict,
                    use_container_width=True,
                    hide_index=True,
                )

            st.markdown(
                "### Rates-Sequenz"
            )
            if not sequence.empty:
                st.dataframe(
                    sequence,
                    use_container_width=True,
                    hide_index=True,
                )

            with st.expander(
                "Robustheit · Jahr / Währung / Leave-One-Currency-Out",
                expanded=False,
            ):
                for title, key in (
                    (
                        "Nach Testjahr",
                        "stability_by_year",
                    ),
                    (
                        "Nach Währung",
                        "stability_by_currency",
                    ),
                    (
                        "Time-aware Leave-One-Currency-Out",
                        "leave_one_currency_out",
                    ),
                ):
                    frame = legacy.get(
                        key,
                        pd.DataFrame(),
                    )
                    if not frame.empty:
                        st.markdown(
                            f"**{title}**"
                        )
                        st.dataframe(
                            frame,
                            use_container_width=True,
                            hide_index=True,
                        )

            st.caption(
                "Diese Legacy-Studie bleibt zur Nachvollziehbarkeit erhalten, "
                "ist aber nicht mehr Teil der operativen Währungsstärke."
            )

        except Exception as exc:
            st.error(
                "Rates→COT-Forschungsarchiv konnte nicht geladen werden: "
                f"{type(exc).__name__}: {exc}"
            )
