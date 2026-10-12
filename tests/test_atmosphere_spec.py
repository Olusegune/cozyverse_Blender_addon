from __future__ import annotations

import unittest

from blender_addon.cozyverse_builder.core.atmosphere_spec import (
    AtmosphereValues,
    deserialize_preset,
    kelvin_rgb,
    serialize_preset,
    sun_azimuth_degrees,
    sun_elevation_degrees,
    warmth_rgb,
)


class AtmosphereSpecTests(unittest.TestCase):
    def test_sun_mapping_changes_across_day(self) -> None:
        self.assertGreater(sun_elevation_degrees(12.0), sun_elevation_degrees(18.0))
        self.assertNotEqual(sun_azimuth_degrees(8.0), sun_azimuth_degrees(18.0))

    def test_warmth_mapping_is_bounded(self) -> None:
        cold = warmth_rgb(0.0)
        warm = warmth_rgb(100.0)
        self.assertGreater(cold[2], warm[2])
        self.assertGreater(warm[0], cold[0])

    def test_preset_round_trip(self) -> None:
        values = AtmosphereValues(19.0, 25.0, 76.0, 28.0, 95.0, "RAIN", 45.0, 0.5, 2300.0, True)
        self.assertEqual(deserialize_preset(serialize_preset(values)), values)

    def test_v1_preset_migrates_with_safe_defaults(self) -> None:
        payload = '{"schema_version":"1.0","time_hour":18,"sun_intensity":55,"warmth":88,"ambient_intensity":38,"interior_intensity":70,"weather":"CLEAR","rain_amount":0}'
        values = deserialize_preset(payload)
        self.assertEqual(values.exposure, 0.0)
        self.assertEqual(values.practical_temperature, 2700.0)
        self.assertTrue(values.practical_lights)
        self.assertIn('"schema_version":"2.0"', serialize_preset(values))

    def test_kelvin_mapping_is_bounded_and_warmer_at_low_temperature(self) -> None:
        warm = kelvin_rgb(1800.0)
        cool = kelvin_rgb(6500.0)
        self.assertGreater(warm[0], warm[2])
        self.assertGreater(cool[2], warm[2])
        self.assertTrue(all(0.0 <= channel <= 1.0 for channel in warm + cool))

    def test_preset_rejects_unsupported_weather(self) -> None:
        payload = '{"schema_version":"1.0","time_hour":1,"sun_intensity":1,"warmth":1,"ambient_intensity":1,"interior_intensity":1,"weather":"TORNADO","rain_amount":1}'
        with self.assertRaisesRegex(ValueError, "weather"):
            deserialize_preset(payload)


if __name__ == "__main__":
    unittest.main()
