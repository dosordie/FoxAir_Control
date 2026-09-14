"""Explicit register policy for parameter backup and safe restore."""

BACKUP_BLOCKS = [
    # Persistent and safe user-interface configuration.
    ("Bedienoberfläche: Sprache", 1015, 1015),
    ("Bedienoberfläche: Logo", 1017, 1017),
    ("Paket 1", 1018, 1090),
    ("Paket 2", 1101, 1180),
    ("Paket 3", 1191, 1270),
    ("Paket 4", 1281, 1360),
    ("Paket 5", 1371, 1450),
    ("Paket 6 optional", 1461, 1540),
    ("Paket 7 optional", 1551, 1630),
]

# Writable 1xxx registers intentionally excluded from both backup and restore.
# They are runtime controls/values or commands whose replay could affect operation.
EXCLUDED_WRITABLE_REGISTERS = {
    1011: "Laufzeit-/Steuerwert: Anlage AN/AUS",
    1012: "Laufzeit-/Steuerwert: aktueller Soll-Betriebsmodus",
    1013: "Laufzeitwert: externe Wassertanktemperatur",
    1014: "Laufzeit-/Steuerwert: Zentralregler-Abtaufreigabe",
    1016: "Command-/Aktionsregister: manuelle Steuerung, Silent und Abtauen",
}

# Protocol/package metadata omitted from backup; the register model marks these
# headers read-only.
READ_ONLY_BLOCK_HEADER_RANGES = (
    (1091, 1100),
    (1181, 1190),
    (1271, 1280),
    (1361, 1370),
    (1451, 1460),
    (1541, 1550),
)
