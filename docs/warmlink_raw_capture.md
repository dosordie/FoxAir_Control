# WarmLink RAW Langzeit-Capture

Der RAW-Capture schreibt RX/TX-Binärdaten verlustfrei. Diese Binärdateien sind die maßgebliche Quelle der Wahrheit für spätere Analysen.

`events.jsonl` ist nur ein Hilfsindex zu den Binärdaten. Die Parser-Metadaten darin basieren auf den TCP-Chunks, die das Betriebssystem liefert. TCP-Chunks sind nicht automatisch vollständige Modbus-/WarmLink-Frames und dürfen deshalb nicht blind als Frames interpretiert werden.

Für jeden RX/TX-Chunk bleiben die nützlichen Indexfelder erhalten, insbesondere `ts`, `mono_s`, `dir`, `offset`, `len` und `hex_head`. Parser-Felder werden bewusst vorsichtig gesetzt:

- `parser="chunk"`: unklassifizierter TCP-Chunk ohne sicheren Frame-Anfang.
- `parser="partial"`: zu kurz für eine sichere Bewertung.
- `parser="frame_start"`: plausibler neuer Frame-Anfang mit erwarteter Busadresse und bekanntem oder gezielt auffälligem Funktionscode.
- `parser="continuation"`: Folgechunk eines bereits erkannten großen WarmLink-Blocks.
- `parser="frame"`: nur verwenden, wenn ein vollständiger Frame sicher vorliegt.

`unknown_function` bedeutet nur dann eine Auffälligkeit, wenn ein plausibler neuer Frame mit erwarteter Busadresse erkannt wurde und der Function Code wirklich unbekannt ist. Folgechunks großer WarmLink-Statusblöcke werden nicht als `unknown_function` gewertet.

Normale WarmLink-FC16-Statusblöcke wie `0x63 0x10` für Startadressen `0x0443` (1091), `0x07D1` (2001) und `0x082B` (2091) mit 90 Registern sind normaler Datenverkehr und kein Firmware-Verdacht. Ein Firmware-Hinweis sollte nur bei zusätzlichen Auffälligkeiten wie unbekannten oder fortlaufenden Startadressen, deutlich größeren Datenmengen, ungewöhnlich hoher Frequenz über längere Zeit oder Korrelation mit Reconnect/Reboot bzw. 2104-Änderungen entstehen.
