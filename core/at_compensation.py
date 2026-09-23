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

AT_MODE_VALUES = (0, 1, 2)
AT_READ_BLOCKS = (
    (1234, 3),
    (1250, 6),
    (1164, 2),
    (2014, 1),
    (2048, 1),
)
AT_LIVE_REGISTERS = frozenset(
    register
    for start, quantity in AT_READ_BLOCKS
    for register in range(start, start + quantity)
)
FALLBACK_TARGET_LIMITS = (5.0, 70.0)


def target_limits(minimum: float | None, maximum: float | None) -> tuple[float, float]:
    """Use valid R10/R11 values or conservative editor limits while unavailable."""
    if minimum is None or maximum is None or minimum > maximum:
        return FALLBACK_TARGET_LIMITS
    return float(minimum), float(maximum)


def encode_temp1(value: float) -> int:
    """Encode a signed TEMP1 value into its unsigned Modbus representation."""
    return int(round(float(value) * 10.0)) & 0xFFFF


def linear_write_plan(slope: float, offset: float) -> tuple[tuple[int, int], ...]:
    """Return only the two writes belonging to the linear curve."""
    return ((1234, encode_temp1(slope)), (1235, encode_temp1(offset)))


def seven_point_write_plan(targets: dict[int, float]) -> tuple[tuple[int, int], ...]:
    """Return the seven curve writes in firmware point order."""
    return tuple((register, encode_temp1(targets[register])) for _at, register in AT_SEVEN_POINT_REGISTERS)


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
