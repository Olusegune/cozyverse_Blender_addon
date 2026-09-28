from __future__ import annotations

import unittest

from blender_addon.cozyverse_builder.core.atmosphere_spec import (
    AtmosphereValues,
    deserialize_preset,
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
        values = AtmosphereValues(19.0, 25.0, 76.0, 28.0, 95.0, "RAIN", 45.0)
        self.assertEqual(deserialize_preset(serialize_preset(values)), values)

    def test_preset_rejects_unsupported_weather(self) -> None:
        payload = '{"schema_version":"1.0","time_hour":1,"sun_intensity":1,"warmth":1,"ambient_intensity":1,"interior_intensity":1,"weather":"TORNADO","rain_amount":1}'
        with self.assertRaisesRegex(ValueError, "weather"):
            deserialize_preset(payload)


if __name__ == "__main__":
    unittest.main()

