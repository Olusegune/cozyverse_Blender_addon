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


PRESETS = {
    "GOLDEN_HOUR": AtmosphereValues(18.0, 55.0, 88.0, 38.0, 70.0, "CLEAR", 0.0),
    "RAINY_CAFE": AtmosphereValues(19.0, 25.0, 76.0, 28.0, 95.0, "RAIN", 45.0),
    "MOONLIT": AtmosphereValues(22.0, 12.0, 18.0, 16.0, 62.0, "CLEAR", 0.0),
    "MISTY_DAWN": AtmosphereValues(6.5, 32.0, 58.0, 42.0, 35.0, "CLEAR", 0.0),
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


def warmth_rgb(warmth: float) -> tuple[float, float, float]:
    factor = clamp(warmth, 0.0, 100.0) / 100.0
    cool = (0.62, 0.76, 1.0)
    warm = (1.0, 0.38, 0.12)
    return tuple(cool[index] * (1.0 - factor) + warm[index] * factor for index in range(3))


def serialize_preset(values: AtmosphereValues) -> str:
    payload = {"schema_version": "1.0", **asdict(values)}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def deserialize_preset(payload: str) -> AtmosphereValues:
    data = json.loads(payload)
    if data.get("schema_version") != "1.0":
        raise ValueError("Unsupported atmosphere preset schema")
    weather = data.get("weather")
    if weather not in {"CLEAR", "RAIN"}:
        raise ValueError("Unsupported atmosphere weather")
    return AtmosphereValues(
        clamp(data["time_hour"], 0.0, 24.0),
        clamp(data["sun_intensity"], 0.0, 100.0),
        clamp(data["warmth"], 0.0, 100.0),
        clamp(data["ambient_intensity"], 0.0, 100.0),
        clamp(data["interior_intensity"], 0.0, 100.0),
        weather,
        clamp(data["rain_amount"], 0.0, 100.0),
    )

