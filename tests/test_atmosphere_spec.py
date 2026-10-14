from __future__ import annotations

import unittest

from blender_addon.cozyverse_builder.core.atmosphere_spec import (
    AtmosphereValues,
    deserialize_preset,
    PRESETS,
    cloud_color,
    cloud_cover,
    kelvin_rgb,
    night_factor,
    sky_colors,
    star_visibility,
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
        self.assertIn('"schema_version":"3.0"', serialize_preset(values))
        self.assertEqual(values.season, "SUMMER")

    def test_v3_weather_round_trip(self) -> None:
        values = AtmosphereValues(7, 30, 40, 20, 10, "SNOW", 0, 0, 2700, True, 15, 35, 20, 65, "WINTER", "LOW")
        self.assertEqual(deserialize_preset(serialize_preset(values)), values)

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

    def test_ten_looks_all_validate_and_round_trip(self) -> None:
        self.assertEqual(len(PRESETS), 10)
        for values in PRESETS.values():
            self.assertEqual(deserialize_preset(serialize_preset(values)), values)

    def test_sky_is_dark_at_night_pale_by_day_and_warm_at_sunset(self) -> None:
        night_h, night_z = sky_colors(1.0, 50.0)
        day_h, day_z = sky_colors(12.0, 50.0)
        self.assertGreater(sum(day_h), sum(night_h) * 3)
        self.assertGreater(sum(day_z), sum(night_z) * 5)
        sunset_h, _ = sky_colors(17.6, 100.0)
        self.assertGreater(sunset_h[0], sunset_h[2])  # red beats blue at the horizon

    def test_stars_only_at_night_and_hidden_by_weather(self) -> None:
        self.assertEqual(night_factor(12.0), 0.0)
        self.assertEqual(night_factor(1.0), 1.0)
        self.assertEqual(star_visibility(12.0, 100.0, "CLEAR", 0.0), 0.0)
        clear = star_visibility(1.0, 70.0, "CLEAR", 0.0)
        self.assertAlmostEqual(clear, 0.7)
        self.assertLess(star_visibility(1.0, 70.0, "RAIN", 0.0), clear * 0.2)
        self.assertLess(star_visibility(1.0, 70.0, "CLEAR", 100.0), clear * 0.2)
        self.assertEqual(star_visibility(1.0, 0.0, "CLEAR", 0.0), 0.0)

    def test_cloud_cover_is_forced_up_by_precipitation_and_fog(self) -> None:
        self.assertEqual(cloud_cover(10.0, "CLEAR"), 10.0)
        self.assertEqual(cloud_cover(10.0, "RAIN"), 80.0)
        self.assertEqual(cloud_cover(95.0, "SNOW"), 95.0)
        self.assertEqual(cloud_cover(10.0, "FOG"), 50.0)
        self.assertEqual(cloud_cover(500.0, "CLEAR"), 100.0)

    def test_cloud_color_is_bright_by_day_rosy_at_sunset_dim_at_night(self) -> None:
        day, night, sunset = cloud_color(12.0, 40.0), cloud_color(1.0, 40.0), cloud_color(17.6, 100.0)
        self.assertGreater(sum(day), sum(night) * 6)
        self.assertGreater(sunset[0], sunset[2])

    def test_every_look_has_its_own_cloud_cover_and_old_presets_get_a_default(self) -> None:
        self.assertGreater(PRESETS["OVERCAST"].clouds_amount, 85.0)
        self.assertLess(PRESETS["STARRY_NIGHT"].clouds_amount, 15.0)
        for values in PRESETS.values():
            self.assertEqual(deserialize_preset(serialize_preset(values)).clouds_amount, values.clouds_amount)
        old = '{"schema_version":"3.0","time_hour":7,"sun_intensity":30,"warmth":40,"ambient_intensity":20,"interior_intensity":10,"weather":"CLEAR","rain_amount":0}'
        self.assertEqual(deserialize_preset(old).clouds_amount, 35.0)


if __name__ == "__main__":
    unittest.main()
