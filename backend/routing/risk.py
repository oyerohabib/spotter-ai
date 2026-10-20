"""Weather and load risk classification for truck routing."""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return {
            RiskLevel.LOW: "Low",
            RiskLevel.MODERATE: "Moderate",
            RiskLevel.HIGH: "High",
            RiskLevel.SEVERE: "Severe",
            RiskLevel.NO_TRAVEL: "No Travel",
        }[self]


def classify_wind(mph: float) -> RiskLevel:
    if mph < 25:
        return RiskLevel.LOW
    if mph < 35:
        return RiskLevel.MODERATE
    if mph < 45:
        return RiskLevel.HIGH
    if mph < 55:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_rain(inches_per_hour: float) -> RiskLevel:
    if inches_per_hour < 0.10:
        return RiskLevel.LOW
    if inches_per_hour < 0.25:
        return RiskLevel.MODERATE
    if inches_per_hour < 0.50:
        return RiskLevel.HIGH
    if inches_per_hour <= 1.00:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_snow(inches_per_hour: float) -> RiskLevel:
    if inches_per_hour < 0.5:
        return RiskLevel.LOW
    if inches_per_hour < 1.0:
        return RiskLevel.MODERATE
    if inches_per_hour < 2.0:
        return RiskLevel.HIGH
    if inches_per_hour <= 3.0:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def apply_load_overrides(wind_mph: float, load_weight_lb: float, base: RiskLevel) -> RiskLevel:
    """Apply load-sensitive wind overrides on top of weather-only risk."""
    risk = base
    if wind_mph >= 55:
        return RiskLevel.NO_TRAVEL
    if 45 <= wind_mph < 55 and load_weight_lb > 30_000:
        return RiskLevel.NO_TRAVEL
    if 35 <= wind_mph < 45 and load_weight_lb > 40_000:
        risk = max(risk, RiskLevel.SEVERE)
    return risk


def classify_checkpoint(
    *,
    wind_mph: float,
    rain_in_hr: float,
    snow_in_hr: float,
    load_weight_lb: float,
) -> dict[str, Any]:
    wind_risk = classify_wind(wind_mph)
    rain_risk = classify_rain(rain_in_hr)
    snow_risk = classify_snow(snow_in_hr)
    weather_risk = max(wind_risk, rain_risk, snow_risk)
    final_risk = apply_load_overrides(wind_mph, load_weight_lb, weather_risk)

    return {
        "wind_risk": wind_risk.label,
        "rain_risk": rain_risk.label,
        "snow_risk": snow_risk.label,
        "weather_risk": weather_risk.label,
        "risk": final_risk.label,
        "risk_score": int(final_risk),
    }
