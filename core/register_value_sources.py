"""Read the shared local/Cloud value stores without changing their provenance."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegisterValueSources:
    local_register: Any = None
    local_raw: int | None = None
    cloud_display: str | None = None


def register_value_sources(window, reg_no: int) -> RegisterValueSources:
    reg = window.latest_regs.get(reg_no)
    local = reg if reg is not None and getattr(reg, "value_source", "local") != "cloud" else None
    raw = local.raw_value if local is not None else (
        window.last_values.get(reg_no) if reg is None else None)
    cloud = getattr(window, "cloud_overlay_by_reg", {}).get(reg_no)
    return RegisterValueSources(local, int(raw) & 0xFFFF if raw is not None else None,
                                str(cloud["value"]) if cloud and "value" in cloud else None)
