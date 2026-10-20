"""Route scoring and recommendation based on weather risk and travel time."""

from __future__ import annotations

from typing import Any

from .risk import RiskLevel


RISK_LABEL_TO_SCORE = {
    "Low": RiskLevel.LOW,
    "Moderate": RiskLevel.MODERATE,
    "High": RiskLevel.HIGH,
    "Severe": RiskLevel.SEVERE,
    "No Travel": RiskLevel.NO_TRAVEL,
}


def summarize_route_risk(checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Aggregate checkpoint risks into mile-band stats.

    Each checkpoint (except the last) owns the miles to the next checkpoint.
    The final checkpoint contributes 0 additional miles but still affects average risk.
    """
    if not checkpoints:
        return {
            "severe_miles": 0.0,
            "high_miles": 0.0,
            "no_travel_miles": 0.0,
            "average_risk": 0.0,
            "max_risk": "Low",
            "checkpoint_count": 0,
        }

    severe_miles = 0.0
    high_miles = 0.0
    no_travel_miles = 0.0
    risk_sum = 0.0
    max_score = RiskLevel.LOW

    for i, cp in enumerate(checkpoints):
        label = cp.get("risk", "Low")
        score = int(RISK_LABEL_TO_SCORE.get(label, RiskLevel.LOW))
        risk_sum += score
        max_score = max(max_score, score)

        if i >= len(checkpoints) - 1:
            continue
        miles = float(checkpoints[i + 1].get("miles_from_origin", 0)) - float(
            cp.get("miles_from_origin", 0)
        )
        miles = max(miles, 0.0)
        if score >= RiskLevel.NO_TRAVEL:
            no_travel_miles += miles
            severe_miles += miles
        elif score >= RiskLevel.SEVERE:
            severe_miles += miles
        elif score >= RiskLevel.HIGH:
            high_miles += miles

    avg = risk_sum / len(checkpoints)
    return {
        "severe_miles": round(severe_miles, 2),
        "high_miles": round(high_miles, 2),
        "no_travel_miles": round(no_travel_miles, 2),
        "average_risk": round(avg, 3),
        "max_risk": RiskLevel(max_score).label,
        "checkpoint_count": len(checkpoints),
    }


def recommendation_sort_key(route: dict[str, Any]) -> tuple:
    summary = route.get("summary") or {}
    return (
        float(summary.get("severe_miles", 0)),
        float(summary.get("high_miles", 0)),
        float(summary.get("average_risk", 0)),
        float(route.get("duration_seconds", 0)),
    )


def recommend_route(routes: list[dict[str, Any]]) -> tuple[str | None, str]:
    """
    Prefer: fewest Severe miles → fewest High miles → lowest avg risk → shortest time.
    Returns (route_id, reason).
    """
    if not routes:
        return None, "No routes available."

    ranked = sorted(routes, key=recommendation_sort_key)
    best = ranked[0]
    summary = best.get("summary") or {}
    reason = (
        f"Recommended for fewest severe miles ({summary.get('severe_miles', 0)}), "
        f"then high miles ({summary.get('high_miles', 0)}), "
        f"average risk {summary.get('average_risk', 0)}, "
        f"and travel time."
    )
    return best.get("id"), reason
