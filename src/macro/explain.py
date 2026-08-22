
from __future__ import annotations

from typing import Any


def build_drivers(
    *,
    phase: str,
    transition_state: str,
    divergence: str,
    leading,
    coincident,
    lagging,
    imminent: dict[str, Any],
    liquidity: dict[str, Any],
) -> list[str]:
    drivers = []

    if leading.distance is not None:
        sign = "unter" if leading.distance < 0 else "über"
        drivers.append(
            f"Leading Index liegt {abs(leading.distance):.1f} Punkte {sign} seiner Equilibrium-Referenz."
        )

    if coincident.distance is not None:
        sign = "unter" if coincident.distance < 0 else "über"
        drivers.append(
            f"Coincident Index liegt {abs(coincident.distance):.1f} Punkte {sign} seiner Equilibrium-Referenz."
        )

    if divergence == "EXPECTED_SLOWDOWN_DIVERGENCE":
        drivers.append(
            "Leading schwach + Coincident noch stabil = erwartete Slowdown-Sequenz, kein einfacher Modellkonflikt."
        )
    elif divergence == "EXPECTED_RECOVERY_DIVERGENCE":
        drivers.append(
            "Leading verbessert sich vor Coincident = erwartete Recovery-Sequenz."
        )

    if imminent.get("phase_gate_active"):
        drivers.append(
            f"Imminent-Recession-Cluster: {imminent.get('active_count', 0)}/{imminent.get('total', 0)} Kriterien aktiv."
        )

    liquidity_state = liquidity.get("state")
    if liquidity_state and liquidity_state != "N/V":
        drivers.append(
            f"Liquidity Modifier: {liquidity_state}; er verändert das Cycle-Regime nicht."
        )

    drivers.insert(
        0,
        f"Business Cycle: {phase} · Transition: {transition_state}.",
    )

    return drivers[:8]
