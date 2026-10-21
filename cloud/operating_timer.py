"""Explicit M-timer schema and conversions; no I/O or inferred grants."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

M_TIMER_CODES = {
    **{1281 + (n - 1) * 7 + offset: f'M{n} {suffix}'
       for n in range(1, 7)
       for offset, suffix in enumerate(('Start', 'End', 'Hot Water Target',
                                        'Heating Target', 'Cooling Target', 'Mode', 'Max. Power'))},
    1323: 'M1_2 Enalbe', 1324: 'M3_4 Enalbe', 1325: 'M5_6 Enalbe',
}
M_CODE_REGISTERS = {code: reg for reg, code in M_TIMER_CODES.items()}
M_TIME_CODES = frozenset(code for reg, code in M_TIMER_CODES.items() if reg < 1323 and (reg-1281) % 7 in (0, 1))
M_SCALED_CODES = frozenset(code for reg, code in M_TIMER_CODES.items() if reg < 1323 and (reg-1281) % 7 in (2, 3, 4, 6))
M_MODE_CODES = frozenset(code for reg, code in M_TIMER_CODES.items() if reg < 1323 and (reg-1281) % 7 == 5)
M_MASK_CODES = frozenset(M_TIMER_CODES[reg] for reg in (1323, 1324, 1325))
M_POWER_CODES = frozenset(code for code in M_SCALED_CODES if code.endswith('Max. Power'))


def m_timer_word(code, value, metadata=None, *, for_write=False):
    """Cloud engineering value -> local word; invalid/missing never means zero."""
    from cloud.warmlink_value_translator import parse_cloud_word
    if code not in M_CODE_REGISTERS or value in (None, '') or isinstance(value, bool):
        raise ValueError('Fehlender/ungültiger Betriebsart-Timerwert')
    if code in M_SCALED_CODES:
        try:
            number = Decimal(str(value).strip().replace(',', '.')) * 10
            if not number.is_finite():
                raise ValueError("Wert muss endlich sein")
            if for_write and number != number.to_integral_value():
                raise ValueError("Schreibwerte müssen 0,1-Schritte verwenden")
            number = number.to_integral_value(rounding=ROUND_HALF_UP)
            if (not (-32768 <= number <= 32767)
                    or (code in M_POWER_CODES and number < 0)):
                raise ValueError('Wert nicht als 0,1-Schritt im lokalen Register darstellbar')
            return int(number) & 0xFFFF
        except InvalidOperation as exc:
            raise ValueError('Ungültiger Temperatur-/Leistungswert') from exc
    word = parse_cloud_word(value, metadata)
    if word is None:
        raise ValueError('Ungültiges 16-Bit-Wort')
    if code in M_TIME_CODES and (word >> 8 > 23 or word & 255 > 59):
        raise ValueError('Ungültige Uhrzeit (Stunde 0–23, Minute 0–59)')
    return word


def m_timer_write_value(code, raw):
    """Local word -> canonical Cloud value, preserving decimal engineering units."""
    if not isinstance(raw, int) or not 0 <= raw <= 65535:
        raise ValueError('Ungültiges lokales Timerwort')
    if code in M_MASK_CODES:
        return f'{raw:016b}'
    if code in M_SCALED_CODES:
        signed = raw if raw < 32768 else raw - 65536
        value = str(Decimal(signed) / 10)
        m_timer_word(code, value)
        return value
    m_timer_word(code, raw)
    if code in M_MODE_CODES and raw not in (0, 1, 2, 3, 4, 9):
        raise ValueError('Unbekannte Betriebsart darf nicht neu geschrieben werden')
    return str(raw)


def m_mask_batches(commands, baselines):
    """Disable changed active bits first, parameters together, enable last.

    Unchanged partner flags are never cleared. Mixed disable/enable pairs are
    committed once, after parameter readbacks, so activation cannot run early.
    """
    disable, final = [], []
    for code, value in commands:
        if code not in M_MASK_CODES:
            continue
        if code not in baselines:
            raise ValueError('Tagesmasken im Betriebsart-Timer frisch lesen; Ausgangswert fehlt')
        old, new = baselines[code], m_timer_word(code, value)
        if not isinstance(old, int) or not 0 <= old <= 65535:
            raise ValueError('Ungültiger Tagesmasken-Ausgangswert')
        off = (old & ~new) & 0x8080
        on = (~old & new) & 0x8080
        if off and not on:
            disable.append((code, value))
        else:
            final.append((code, value))
    parameters = tuple(item for item in commands if item[0] not in M_MASK_CODES)
    return tuple(batch for batch in (tuple(disable), parameters, tuple(final)) if batch)
