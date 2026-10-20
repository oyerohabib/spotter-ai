from django.test import SimpleTestCase

from routing.risk import (
    RiskLevel,
    apply_load_overrides,
    classify_checkpoint,
    classify_rain,
    classify_snow,
    classify_wind,
)


class WindClassificationTests(SimpleTestCase):
    def test_wind_bands(self):
        self.assertEqual(classify_wind(24.9), RiskLevel.LOW)
        self.assertEqual(classify_wind(25), RiskLevel.MODERATE)
        self.assertEqual(classify_wind(34.9), RiskLevel.MODERATE)
        self.assertEqual(classify_wind(35), RiskLevel.HIGH)
        self.assertEqual(classify_wind(44.9), RiskLevel.HIGH)
        self.assertEqual(classify_wind(45), RiskLevel.SEVERE)
        self.assertEqual(classify_wind(54.9), RiskLevel.SEVERE)
        self.assertEqual(classify_wind(55), RiskLevel.NO_TRAVEL)


class RainSnowClassificationTests(SimpleTestCase):
    def test_rain_bands(self):
        self.assertEqual(classify_rain(0.09), RiskLevel.LOW)
        self.assertEqual(classify_rain(0.10), RiskLevel.MODERATE)
        self.assertEqual(classify_rain(0.24), RiskLevel.MODERATE)
        self.assertEqual(classify_rain(0.25), RiskLevel.HIGH)
        self.assertEqual(classify_rain(0.49), RiskLevel.HIGH)
        self.assertEqual(classify_rain(0.50), RiskLevel.SEVERE)
        self.assertEqual(classify_rain(1.00), RiskLevel.SEVERE)
        self.assertEqual(classify_rain(1.01), RiskLevel.NO_TRAVEL)

    def test_snow_bands(self):
        self.assertEqual(classify_snow(0.49), RiskLevel.LOW)
        self.assertEqual(classify_snow(0.5), RiskLevel.MODERATE)
        self.assertEqual(classify_snow(0.99), RiskLevel.MODERATE)
        self.assertEqual(classify_snow(1.0), RiskLevel.HIGH)
        self.assertEqual(classify_snow(1.99), RiskLevel.HIGH)
        self.assertEqual(classify_snow(2.0), RiskLevel.SEVERE)
        self.assertEqual(classify_snow(3.0), RiskLevel.SEVERE)
        self.assertEqual(classify_snow(3.01), RiskLevel.NO_TRAVEL)


class LoadOverrideTests(SimpleTestCase):
    def test_gt_55_always_no_travel(self):
        self.assertEqual(
            apply_load_overrides(55, 10_000, RiskLevel.LOW),
            RiskLevel.NO_TRAVEL,
        )

    def test_45_54_heavy_load_no_travel(self):
        self.assertEqual(
            apply_load_overrides(50, 30_001, RiskLevel.MODERATE),
            RiskLevel.NO_TRAVEL,
        )
        self.assertEqual(
            apply_load_overrides(50, 30_000, RiskLevel.SEVERE),
            RiskLevel.SEVERE,
        )

    def test_35_44_very_heavy_load_severe(self):
        self.assertEqual(
            apply_load_overrides(40, 40_001, RiskLevel.LOW),
            RiskLevel.SEVERE,
        )
        self.assertEqual(
            apply_load_overrides(40, 40_000, RiskLevel.HIGH),
            RiskLevel.HIGH,
        )


class CheckpointClassificationTests(SimpleTestCase):
    def test_max_of_conditions_then_load(self):
        result = classify_checkpoint(
            wind_mph=20,
            rain_in_hr=0.3,
            snow_in_hr=0.1,
            load_weight_lb=20_000,
        )
        self.assertEqual(result["rain_risk"], "High")
        self.assertEqual(result["risk"], "High")
        self.assertEqual(result["risk_score"], int(RiskLevel.HIGH))

    def test_load_can_escalate_wind(self):
        result = classify_checkpoint(
            wind_mph=40,
            rain_in_hr=0.0,
            snow_in_hr=0.0,
            load_weight_lb=45_000,
        )
        self.assertEqual(result["weather_risk"], "High")
        self.assertEqual(result["risk"], "Severe")
