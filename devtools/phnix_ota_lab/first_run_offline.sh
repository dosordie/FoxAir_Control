#!/usr/bin/env bash
set -Eeuo pipefail

LAB_ROOT="/opt/phnix-lab"
ROOTFS="$LAB_ROOT/rootfs"
RUN_SECS="${1:-20}"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$LAB_ROOT/logs/first-run-$STAMP"

log()  { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m[WARN]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || die "Bitte als root starten: sudo $0 [Sekunden]"
[[ -x "$ROOTFS/data/phnixIot4G" ]] || die "$ROOTFS/data/phnixIot4G fehlt"
[[ -x "$ROOTFS/usr/bin/qemu-arm-static" ]] || die "$ROOTFS/usr/bin/qemu-arm-static fehlt"
command -v unshare >/dev/null 2>&1 || die "unshare fehlt"
command -v ip >/dev/null 2>&1 || die "ip fehlt"
command -v timeout >/dev/null 2>&1 || die "timeout fehlt"

case "$RUN_SECS" in
  ''|*[!0-9]*) die "Laufzeit muss eine ganze Zahl in Sekunden sein" ;;
esac
(( RUN_SECS >= 1 && RUN_SECS <= 120 )) || die "Laufzeit muss zwischen 1 und 120 Sekunden liegen"

install -d -m 0755 "$RUN_DIR" "$ROOTFS/dev" "$ROOTFS/tmp" "$ROOTFS/cache"
chmod 1777 "$ROOTFS/tmp"

# Nur elementare Unix-Devices bereitstellen. Qualcomm-/SIMCom-Devices und
# /dev/ttyHSL2 werden fuer den ersten Lauf absichtlich NICHT erzeugt.
make_dev() {
  local path="$1" major="$2" minor="$3" mode="$4"
  if [[ ! -e "$ROOTFS/dev/$path" ]]; then
    mknod -m "$mode" "$ROOTFS/dev/$path" c "$major" "$minor"
  fi
}
make_dev null    1 3 666
make_dev zero    1 5 666
make_dev random  1 8 666
make_dev urandom 1 9 666

log "Sicherheitspruefung"
for p in ttyHSL2 diag smd8 smem_log; do
  if [[ -e "$ROOTFS/dev/$p" ]]; then
    die "$ROOTFS/dev/$p existiert bereits. Fuer den ersten Lauf bitte entfernen/umbenennen."
  fi
done

log "Baseline der beschreibbaren Lab-Dateien erfassen"
(
  cd "$ROOTFS"
  find data cache tmp -xdev -type f -print0 2>/dev/null | sort -z | xargs -0 -r sha256sum
) > "$RUN_DIR/files-before.sha256"

cat > "$RUN_DIR/README.txt" <<EOF
PHNIX first offline run
Timestamp: $STAMP
Timeout: ${RUN_SECS}s
Network: private Linux network namespace; only loopback is enabled; no veth, no default route
RootFS: $ROOTFS
Guest: /data/phnixIot4G via qemu-arm-static -strace
Qualcomm/RS485 devices deliberately absent: /dev/ttyHSL2 /dev/diag /dev/smd8 /dev/smem_log
EOF

log "Erster echter Start: isoliertes Network-Namespace, maximal ${RUN_SECS}s"
log "SSH der VM bleibt aktiv; nur dieser Prozess bekommt keinen LAN-/Internetzugang."

set +e
unshare --net --fork bash -c '
  set -Eeuo pipefail
  ROOTFS="$1"
  RUN_DIR="$2"
  RUN_SECS="$3"

  ip link set lo up
  {
    echo "=== ip -brief link ==="
    ip -brief link
    echo
    echo "=== ip -brief addr ==="
    ip -brief addr
    echo
    echo "=== ip route ==="
    ip route
    echo
    echo "=== ip -6 route ==="
    ip -6 route || true
  } > "$RUN_DIR/network.txt"

  if ip route show default | grep -q .; then
    echo "UNSAFE: default route exists" >&2
    exit 90
  fi
  if ip -6 route show default | grep -q .; then
    echo "UNSAFE: IPv6 default route exists" >&2
    exit 91
  fi

  # chroot normally changes cwd to /. The original application lived in /data;
  # keep cwd at /data without requiring an ARM shell inside the rootfs.
  cd "$ROOTFS/data"
  ulimit -c 0
  timeout -k 2 "${RUN_SECS}s" \
    chroot --skip-chdir "$ROOTFS" \
      /usr/bin/qemu-arm-static -L / -strace /data/phnixIot4G \
      > "$RUN_DIR/stdout.log" 2> "$RUN_DIR/qemu-strace.log"
' bash "$ROOTFS" "$RUN_DIR" "$RUN_SECS"
RC=$?
set -e
printf '%s\n' "$RC" > "$RUN_DIR/exit-code.txt"

log "Dateien nach dem Lauf erfassen"
(
  cd "$ROOTFS"
  find data cache tmp -xdev -type f -print0 2>/dev/null | sort -z | xargs -0 -r sha256sum
) > "$RUN_DIR/files-after.sha256"

{
  echo "=== neue/geaenderte Dateihashes ==="
  diff -u "$RUN_DIR/files-before.sha256" "$RUN_DIR/files-after.sha256" || true
} > "$RUN_DIR/files-diff.txt"

printf '\nExit-Code: %s\n' "$RC"
case "$RC" in
  0)   echo "Programm hat innerhalb des Zeitfensters selbst beendet." ;;
  124) echo "Erwarteter Timeout: Prozess lief nach ${RUN_SECS}s noch und wurde beendet." ;;
  137) echo "Prozess musste nach Timeout hart beendet werden." ;;
  90|91) die "Netzwerk-Sicherheitspruefung fehlgeschlagen. Binary wurde nicht gestartet." ;;
  *)   echo "Programm/QEMU beendete sich mit Fehlercode $RC." ;;
esac

printf '\n=== Netzwerk-Namespace ===\n'
cat "$RUN_DIR/network.txt" 2>/dev/null || true

printf '\n=== Interessante Datei-/Device-/Netzwerkzugriffe (letzte 160 Treffer) ===\n'
grep -aE '(/dev/|/etc/|/data/|/cache/|socket\(|connect\(|bind\(|sendto\(|recvfrom\()' \
  "$RUN_DIR/qemu-strace.log" 2>/dev/null | tail -n 160 || true

printf '\n=== Letzte 80 Zeilen QEMU/Guest-Trace ===\n'
tail -n 80 "$RUN_DIR/qemu-strace.log" 2>/dev/null || true

printf '\n=== Datei-Aenderungen ===\n'
cat "$RUN_DIR/files-diff.txt" 2>/dev/null || true

printf '\nLogs: %s\n' "$RUN_DIR"
cat <<'EOF'

Sicherheit:
- Der Gastprozess lief in einem eigenen Network-Namespace ohne Default-Route.
- Der normale Netzwerkstack/SSH der Debian-VM wurde nicht veraendert.
- /dev/ttyHSL2 und die Qualcomm-Modemdevices waren absichtlich nicht vorhanden.
- Der Lauf war zeitlich begrenzt.
EOF
