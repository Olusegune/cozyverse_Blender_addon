"""Pure-Python mappings for CozyVerse Atmosphere Lab."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AtmosphereValues:
    time_hour: float
    sun_intensity: float
    warmth: float
    ambient_intensity: float
    interior_intensity: float
    weather: str
    rain_amount: float
    exposure: float = 0.0
    practical_temperature: float = 2700.0
    practical_lights: bool = True
    fog_amount: float = 0.0
    wind_amount: float = 0.0
    wetness_amount: float = 0.0
    snow_amount: float = 0.0
    season: str = "SUMMER"
    weather_quality: str = "MEDIUM"
    clouds_amount: float = 35.0


PRESETS = {
    "GOLDEN_HOUR": AtmosphereValues(18.0, 55.0, 88.0, 38.0, 70.0, "CLEAR", 0.0, 0.25, 2400.0, clouds_amount=40.0),
    "RAINY_CAFE": AtmosphereValues(19.0, 25.0, 76.0, 28.0, 95.0, "RAIN", 45.0, 0.5, 2200.0, clouds_amount=85.0),
    "MOONLIT": AtmosphereValues(22.0, 12.0, 18.0, 16.0, 62.0, "CLEAR", 0.0, 0.8, 3200.0, clouds_amount=22.0),
    "MISTY_DAWN": AtmosphereValues(6.5, 32.0, 58.0, 42.0, 35.0, "CLEAR", 0.0, 0.35, 3000.0, clouds_amount=48.0),
    "BRIGHT_DAY": AtmosphereValues(12.0, 72.0, 42.0, 55.0, 0.0, "CLEAR", 0.0, -0.1, 4000.0, False, clouds_amount=32.0),
    "BLUE_HOUR": AtmosphereValues(20.0, 18.0, 24.0, 24.0, 82.0, "CLEAR", 0.0, 0.65, 2600.0, clouds_amount=30.0),
    "STARRY_NIGHT": AtmosphereValues(1.0, 8.0, 12.0, 12.0, 85.0, "CLEAR", 0.0, 0.9, 2800.0, clouds_amount=8.0),
    "SUNSET_GLOW": AtmosphereValues(17.6, 65.0, 100.0, 30.0, 60.0, "CLEAR", 0.0, 0.2, 2300.0, clouds_amount=58.0),
    "OVERCAST": AtmosphereValues(13.0, 20.0, 30.0, 64.0, 25.0, "CLEAR", 0.0, 0.1, 4200.0, True, 22.0, clouds_amount=92.0),
    "FIRST_SNOW": AtmosphereValues(16.0, 32.0, 28.0, 50.0, 78.0, "SNOW", 0.0, 0.3, 2800.0, True, 12.0, 8.0, 0.0, 55.0, "WINTER", clouds_amount=80.0),
}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def sun_elevation_degrees(time_hour: float) -> float:
    """Return an artistic sun elevation from -8 degrees at night to 58 at noon."""
    hour = clamp(time_hour, 0.0, 24.0)
    daylight = math.sin(((hour - 6.0) / 12.0) * math.pi)
    return max(-8.0, daylight * 58.0)


def sun_azimuth_degrees(time_hour: float) -> float:
    return (clamp(time_hour, 0.0, 24.0) / 24.0) * 360.0 - 90.0


def _mix(first: tuple[float, ...], second: tuple[float, ...], amount: float) -> tuple[float, ...]:
    return tuple(a + (b - a) * amount for a, b in zip(first, second))


def night_factor(time_hour: float) -> float:
    """1.0 once the sun is well below the horizon, fading to 0.0 shortly after sunrise."""
    return clamp((2.0 - sun_elevation_degrees(time_hour)) / 10.0, 0.0, 1.0)


def sky_colors(time_hour: float, warmth: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """(horizon, zenith) sky colors: deep blue night, pale day, a warm glow around sunrise and sunset."""
    elevation = sun_elevation_degrees(time_hour)
    daylight = clamp((elevation + 8.0) / 66.0, 0.0, 1.0) ** 0.8
    horizon = _mix((0.03, 0.05, 0.14), (0.62, 0.76, 0.95), daylight)
    zenith = _mix((0.004, 0.008, 0.04), (0.20, 0.43, 0.84), daylight)
    glow = clamp(1.0 - abs(elevation - 6.0) / 16.0, 0.0, 1.0) * (clamp(warmth, 0.0, 100.0) / 100.0)
    return _mix(horizon, (0.98, 0.50, 0.28), glow * 0.7), _mix(zenith, (0.45, 0.25, 0.40), glow * 0.25)


def cloud_cover(clouds_amount: float, weather: str) -> float:
    """Effective cloud cover 0-100: rain and snow always bring a heavy sky, fog a soft one."""
    cover = clamp(clouds_amount, 0.0, 100.0)
    if weather in {"RAIN", "SNOW"}:
        return max(cover, 80.0)
    if weather == "FOG":
        return max(cover, 50.0)
    return cover


def cloud_color(time_hour: float, warmth: float) -> tuple[float, float, float]:
    """Cloud tint: bright white by day, rosy at sunrise and sunset, a dim blue-grey at night."""
    elevation = sun_elevation_degrees(time_hour)
    daylight = clamp((elevation + 8.0) / 66.0, 0.0, 1.0) ** 0.7
    base = _mix((0.035, 0.045, 0.09), (1.0, 1.0, 1.0), daylight)
    glow = clamp(1.0 - abs(elevation - 6.0) / 16.0, 0.0, 1.0) * (clamp(warmth, 0.0, 100.0) / 100.0)
    return _mix(base, (1.0, 0.62, 0.45), glow * 0.6)


def star_visibility(time_hour: float, stars_amount: float, weather: str, fog_amount: float) -> float:
    """How strongly stars show: only at night, dimmed by fog and hidden behind rain or snow clouds."""
    clouds = 0.12 if weather in {"RAIN", "SNOW"} else 1.0
    return night_factor(time_hour) * clamp(stars_amount, 0.0, 100.0) / 100.0 * (1.0 - clamp(fog_amount, 0.0, 100.0) / 100.0 * 0.85) * clouds


def warmth_rgb(warmth: float) -> tuple[float, float, float]:
    factor = clamp(warmth, 0.0, 100.0) / 100.0
    cool = (0.62, 0.76, 1.0)
    warm = (1.0, 0.38, 0.12)
    return tuple(cool[index] * (1.0 - factor) + warm[index] * factor for index in range(3))


def kelvin_rgb(temperature: float) -> tuple[float, float, float]:
    """Approximate a 1,800-6,500 K practical-light color without dependencies."""
    value = clamp(temperature, 1800.0, 6500.0) / 100.0
    red = 255.0 if value <= 66.0 else 329.698727446 * ((value - 60.0) ** -0.1332047592)
    green = 99.4708025861 * math.log(value) - 161.1195681661 if value <= 66.0 else 288.1221695283 * ((value - 60.0) ** -0.0755148492)
    blue = 255.0 if value >= 66.0 else (0.0 if value <= 19.0 else 138.5177312231 * math.log(value - 10.0) - 305.044792731)
    return tuple(clamp(channel, 0.0, 255.0) / 255.0 for channel in (red, green, blue))


def serialize_preset(values: AtmosphereValues) -> str:
    payload = {"schema_version": "3.0", **asdict(values)}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def deserialize_preset(payload: str) -> AtmosphereValues:
    data = json.loads(payload)
    schema_version = data.get("schema_version")
    if schema_version not in {"1.0", "2.0", "3.0"}:
        raise ValueError("Unsupported atmosphere preset schema")
    weather = data.get("weather")
    if weather not in {"CLEAR", "RAIN", "FOG", "SNOW"}:
        raise ValueError("Unsupported atmosphere weather")
    return AtmosphereValues(
        clamp(data["time_hour"], 0.0, 24.0),
        clamp(data["sun_intensity"], 0.0, 100.0),
        clamp(data["warmth"], 0.0, 100.0),
        clamp(data["ambient_intensity"], 0.0, 100.0),
        clamp(data["interior_intensity"], 0.0, 100.0),
        weather,
        clamp(data["rain_amount"], 0.0, 100.0),
        clamp(data.get("exposure", 0.0), -3.0, 3.0),
        clamp(data.get("practical_temperature", 2700.0), 1800.0, 6500.0),
        bool(data.get("practical_lights", True)),
        clamp(data.get("fog_amount", 0.0), 0.0, 100.0),
        clamp(data.get("wind_amount", 0.0), 0.0, 100.0),
        clamp(data.get("wetness_amount", 0.0), 0.0, 100.0),
        clamp(data.get("snow_amount", 0.0), 0.0, 100.0),
        data.get("season", "SUMMER") if data.get("season", "SUMMER") in {"SPRING", "SUMMER", "AUTUMN", "WINTER"} else "SUMMER",
        data.get("weather_quality", "MEDIUM") if data.get("weather_quality", "MEDIUM") in {"LOW", "MEDIUM", "HIGH"} else "MEDIUM",
        clamp(data.get("clouds_amount", 35.0), 0.0, 100.0),
    )
