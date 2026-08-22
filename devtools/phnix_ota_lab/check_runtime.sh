#!/usr/bin/env bash
set -Eeuo pipefail

ROOTFS="/opt/phnix-lab/rootfs"
QEMU="$ROOTFS/usr/bin/qemu-arm-static"
APP="$ROOTFS/data/phnixIot4G"

log()  { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || die "Bitte als root starten: sudo $0"
[[ -x "$QEMU" ]] || die "qemu-arm-static fehlt im RootFS: $QEMU"
[[ -x "$APP" ]] || die "phnixIot4G fehlt oder ist nicht ausfuehrbar: $APP"
[[ -e "$ROOTFS/lib/ld-linux.so.3" ]] || die "ARM-Loader fehlt: $ROOTFS/lib/ld-linux.so.3"

log "ELF-Dateien pruefen"
file "$ROOTFS/lib/ld-linux.so.3"
file "$APP"

log "ARM-Runtime nur laden und Libraries auflisten"
# LD_TRACE_LOADED_OBJECTS wird vom glibc/eglibc-Loader ausgewertet. Dadurch
# werden die benoetigten Shared Libraries ausgegeben und main() der Anwendung
# NICHT aufgerufen. Das ist fuer diesen Check absichtlich sicherer als ein
# normaler Programmstart.
set +e
OUT=$(chroot "$ROOTFS" \
  /usr/bin/qemu-arm-static \
  -L / \
  -E LD_TRACE_LOADED_OBJECTS=1 \
  /data/phnixIot4G 2>&1)
RC=$?
set -e

printf '%s\n' "$OUT"
printf '\nExit-Code: %s\n' "$RC"

if grep -qi 'not found' <<<"$OUT"; then
  die "Mindestens eine Shared Library fehlt."
fi

if grep -qiE 'exec format error|could not open|no such file|invalid elf|error while loading' <<<"$OUT"; then
  die "Loader-/QEMU-Fehler erkannt. Ausgabe siehe oben."
fi

if [[ $RC -ne 0 ]]; then
  die "Runtime-Check endete mit Exit-Code $RC."
fi

log "Runtime-Check erfolgreich: kein 'not found', main() wurde nicht gestartet."
