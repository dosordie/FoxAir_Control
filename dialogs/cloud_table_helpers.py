# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from cloud.warmlink_codes import (
    cloud_hint,
    cloud_modbus_register,
    code_confidence,
    code_display_name,
    code_unit,
)


def mask_cloud_value(value: Any, show_ids: bool = False) -> str:
    text = str(value or "")
    if show_ids or len(text) <= 8:
        return text
    return text[:4] + "…" + text[-4:]


def try_float(value: Any) -> Optional[float]:
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def binary_to_int(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if text and set(text) <= {"0", "1"} and len(text) <= 32:
        try:
            return int(text, 2)
        except Exception:
            return None
    return None


def local_display_value(latest_regs: dict, reg_no: int) -> tuple[str, Optional[float]]:
    reg = latest_regs.get(int(reg_no))
    if reg is None:
        return "", None
    text = str(getattr(reg, "display_value", ""))
    # ersten numerischen Anteil fuer groben Diff extrahieren
    m = re.search(r"[-+]?\d+(?:[\.,]\d+)?", text)
    return text, try_float(m.group(0)) if m else try_float(getattr(reg, "signed_value", ""))


def device_combo_label(device: dict[str, Any], show_ids: bool = False) -> tuple[str, str]:
    code = str(device.get("deviceCode") or "")
    nick = str(device.get("deviceNickName") or device.get("model") or device.get("custModel") or "Gerät")
    status = str(device.get("deviceStatus", ""))
    return f"{nick} | {status} | {mask_cloud_value(code, show_ids=show_ids)}", code


def device_table_value(device: dict[str, Any], key: str, sensitive_fields: set[str], show_ids: bool = False) -> str:
    value = device.get(key, "")
    if key in sensitive_fields:
        value = mask_cloud_value(value, show_ids=show_ids)
    return str(value)


def filtered_cloud_rows(data_rows: list[dict[str, Any]], needle: str, unsupported_only: bool) -> list[dict[str, Any]]:
    needle = str(needle or "").strip().lower()
    rows = []
    for row in data_rows:
        code = str(row.get("code", ""))
        hint = cloud_hint(code)
        name = code_display_name(code)
        note = str(hint.get("note", ""))
        value = row.get("value", "")
        supported = bool(row.get("supported"))
        if unsupported_only and supported:
            continue
        hay = " ".join(str(x) for x in (code, name, value, row.get("dataType", ""), note)).lower()
        if needle and needle not in hay:
            continue
        rows.append(row)
    return rows


def data_table_values(row: dict[str, Any]) -> tuple[list[Any], str]:
    code = str(row.get("code", ""))
    hint = cloud_hint(code)
    reg = cloud_modbus_register(code)
    mapping = str(reg) if reg is not None else str(hint.get("confidence") or "")
    status = "veraltet" if row.get("stale") else ("OK" if row.get("supported") else "leer/unsupported")
    vals = [
        code,
        code_display_name(code),
        row.get("value", ""),
        row.get("dataType") or hint.get("dataType") or hint.get("cloud_dataType", ""),
        row.get("rangeStart", ""),
        row.get("rangeEnd", ""),
        row.get("lastFetch", ""),
        status,
        mapping,
        hint.get("note", ""),
    ]
    return vals, status


def compare_source_rows(data_rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], int | None]]:
    rows = []
    for row in data_rows:
        code = str(row.get("code", ""))
        hint = cloud_hint(code)
        reg_no = cloud_modbus_register(code)
        if reg_no is None:
            if str(hint.get("confidence") or "") == "unknown" or code in ("SG Status",):
                rows.append((row, None))
            continue
        rows.append((row, reg_no))
    return rows


def compare_table_values(
    row: dict[str, Any],
    reg_no: int | None,
    *,
    latest_regs: dict,
    regmap: dict,
    display_parts_for_register: Callable[[int, str], tuple[Any, str, Any]],
    cloud_display_text: Callable[[str, Any], str],
) -> tuple[list[Any], str]:
    code = str(row.get("code", ""))
    hint = cloud_hint(code)
    cloud_val = row.get("value", "")
    unit = code_unit(code)
    cloud_txt = cloud_display_text(code, cloud_val)
    local_txt, local_num = ("", None)
    diff_txt = ""
    status = "cloud-only"
    local_code = ""
    if reg_no is not None:
        info = regmap.get(int(reg_no))
        _block, local_code, _clean = display_parts_for_register(int(reg_no), info.name)
        local_txt, local_num = local_display_value(latest_regs, int(reg_no))
        cloud_num = try_float(cloud_val)
        if local_txt:
            status = "OK" if row.get("supported") else "leer"
        else:
            status = "kein lokaler Wert"
        if local_num is not None and cloud_num is not None:
            diff_txt = f"{cloud_num - local_num:+.3g}"
    elif not row.get("supported"):
        status = "leer/unsupported"
    vals = [
        code,
        "" if reg_no is None else str(reg_no),
        local_code,
        code_display_name(code),
        local_txt,
        cloud_txt,
        diff_txt,
        unit,
        code_confidence(code),
        status,
        hint.get("note", ""),
    ]
    return vals, status


def finder_code_label(row: dict[str, Any]) -> tuple[str, str] | None:
    code = str(row.get("code", ""))
    if not code:
        return None
    value = row.get("value", "")
    return f"{code} = {value} ({code_confidence(code) or 'unknown'})", code


def finder_cloud_row(data_rows: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    for row in data_rows:
        if str(row.get("code", "")) == str(code):
            return row
    return None


def value_finder_matches(
    *,
    code: str,
    cloud_raw: Any,
    latest_regs_items: list[tuple[Any, Any]],
    regmap: dict,
    display_parts_for_register: Callable[[int, str], tuple[Any, str, Any]],
    tolerance: float,
    hide_zero: bool,
) -> list[list[str]]:
    cloud_num = try_float(cloud_raw)
    cloud_bin = binary_to_int(cloud_raw)
    matches: list[list[str]] = []
    for reg_no, reg in latest_regs_items:
        raw = getattr(reg, "raw_value", None)
        signed = getattr(reg, "signed_value", None)
        display = str(getattr(reg, "display_value", ""))
        info = regmap.get(int(reg_no))
        try:
            raw_i = int(raw) if raw is not None else None
        except Exception:
            raw_i = None
        try:
            signed_i = int(signed) if signed is not None else None
        except Exception:
            signed_i = None
        if hide_zero and cloud_num == 0 and (raw_i == 0 or signed_i == 0):
            continue
        reasons: list[str] = []
        if cloud_bin is not None and raw_i is not None and (raw_i & 0xFFFF) == cloud_bin:
            reasons.append("binary==raw")
        if cloud_num is not None:
            for label, candidate in (("raw", raw_i), ("signed", signed_i)):
                if candidate is None:
                    continue
                if abs(float(candidate) - cloud_num) <= tolerance:
                    reasons.append(f"{label}==cloud")
                if abs(float(candidate) / 10.0 - cloud_num) <= tolerance:
                    reasons.append(f"{label}/10==cloud")
                if abs(float(candidate) / 100.0 - cloud_num) <= tolerance:
                    reasons.append(f"{label}/100==cloud")
            m = re.search(r"[-+]?\d+(?:[\.,]\d+)?", display)
            local_num = try_float(m.group(0)) if m else None
            if local_num is not None and abs(local_num - cloud_num) <= tolerance:
                reasons.append("display==cloud")
        if str(cloud_raw) and str(cloud_raw) in display:
            reasons.append("Text in Anzeige")
        if reasons:
            _block, local_code, _clean = display_parts_for_register(int(reg_no), info.name if info else f"Reg {reg_no}")
            matches.append([
                code,
                str(cloud_raw),
                str(reg_no),
                local_code,
                str(info.name if info else getattr(reg, "name", "")),
                display,
                ", ".join(sorted(set(reasons))),
                "candidate",
            ])
    return matches
