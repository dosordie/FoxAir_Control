#!/usr/bin/env bash
set -Eeuo pipefail

LAB_ROOT="/opt/phnix-lab"
ROOTFS="$LAB_ROOT/rootfs"
APP="$ROOTFS/data/phnixIot4G"
SRC="${1:-$LAB_ROOT/runtime-import/source/SIM7600_Runtime}"

log() { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ -r "$APP" ]] || die "$APP fehlt"
command -v strings >/dev/null 2>&1 || die "strings fehlt"

PAT='AT\+CGMM|CGMM|SIMCOM|SIM7[0-9]{3}[A-Za-z0-9_.+-]*|MDM[0-9]{4}|modem model|module model'

log "Relevante Strings direkt in phnixIot4G"
strings -a -t x "$APP" | grep -Ei "$PAT" || true

log "Relevante Symbolnamen in phnixIot4G"
if command -v arm-linux-gnueabihf-readelf >/dev/null 2>&1; then
  arm-linux-gnueabihf-readelf -Ws "$APP" 2>/dev/null \
    | grep -Ei 'cgmm|simcom|modem|uim|imei|iccid|at(_|$)|uart485' \
    | head -n 200 || true
else
  echo "arm-linux-gnueabihf-readelf nicht vorhanden"
fi

log "Modellstrings im privaten Runtime-Dump (nur passende Treffer)"
if [[ -d "$SRC" ]]; then
  # Nur kleine/typische Konfigurations- und Executable-Baeume scannen. Ausgabe
  # wird strikt auf Modellbezeichnungen begrenzt, damit keine DeviceSecrets,
  # IMEIs oder andere geraetespezifische Daten versehentlich ausgegeben werden.
  while IFS= read -r -d '' f; do
    hits="$(strings -a "$f" 2>/dev/null | grep -Eio 'SIMCOM[_ -]?SIM[0-9A-Za-z_.+-]+|SIM7[0-9]{3}[A-Za-z0-9_.+-]*|MDM[0-9]{4}' | sort -u | head -n 20 || true)"
    if [[ -n "$hits" ]]; then
      while IFS= read -r h; do
        printf '%s: %s\n' "${f#$SRC/}" "$h"
      done <<< "$hits"
    fi
  done < <(find "$SRC/etc" "$SRC/firmware" "$SRC/usr_bin" "$SRC/usr_sbin" \
                   "$SRC/bin" "$SRC/sbin" -xdev -type f -size -20M -print0 2>/dev/null)
else
  echo "Runtime-Dump nicht gefunden: $SRC"
fi

cat <<'EOF'

Nur Offline-Analyse; es wurde kein AT-Befehl an das reale Modem gesendet.
Bitte die komplette Ausgabe posten. Danach bauen wir die kleinste moegliche
AT+CGMM-Antwort fuer den naechsten isolierten A/B-Test.
EOF
