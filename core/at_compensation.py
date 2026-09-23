"""Firmware-compatible calculations for GL9 outdoor-temperature compensation."""

AT_SEVEN_POINT_REGISTERS = (
    (-20.0, 1250),
    (-10.0, 1251),
    (-5.0, 1252),
    (0.0, 1235),
    (5.0, 1253),
    (10.0, 1254),
    (20.0, 1255),
)


def calculate_seven_point_target(
    outdoor_temperature: float,
    targets: dict[int, float],
    minimum: float,
    maximum: float,
) -> float:
    """Interpolate the GL9 seven-point curve and apply its R10/R11 limits."""
    outdoor = max(-20.0, min(20.0, float(outdoor_temperature)))
    points = [(at, float(targets[register])) for at, register in AT_SEVEN_POINT_REGISTERS]
    value = points[-1][1]
    for (left_at, left_value), (right_at, right_value) in zip(points, points[1:]):
        if outdoor <= right_at:
            fraction = (outdoor - left_at) / (right_at - left_at)
            value = left_value + fraction * (right_value - left_value)
            break
    return max(float(minimum), min(float(maximum), value))
