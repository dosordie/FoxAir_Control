#!/usr/bin/env bash
set -Eeuo pipefail

LAB_ROOT="/opt/phnix-lab"
ROOTFS="$LAB_ROOT/rootfs"
RUN_SECS="${1:-30}"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$LAB_ROOT/logs/at-probe-$STAMP"

log()  { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || die "Bitte als root starten: sudo $0 [Sekunden]"
[[ -x "$ROOTFS/data/phnixIot4G" ]] || die "$ROOTFS/data/phnixIot4G fehlt"
[[ -x "$ROOTFS/usr/bin/qemu-arm-static" ]] || die "$ROOTFS/usr/bin/qemu-arm-static fehlt"
command -v unshare >/dev/null 2>&1 || die "unshare fehlt"
command -v socat >/dev/null 2>&1 || die "socat fehlt"
command -v timeout >/dev/null 2>&1 || die "timeout fehlt"
command -v xxd >/dev/null 2>&1 || die "xxd fehlt"

case "$RUN_SECS" in
  ''|*[!0-9]*) die "Laufzeit muss eine ganze Zahl in Sekunden sein" ;;
esac
(( RUN_SECS >= 5 && RUN_SECS <= 120 )) || die "Laufzeit muss zwischen 5 und 120 Sekunden liegen"

install -d -m 0755 "$RUN_DIR" "$ROOTFS/dev" "$ROOTFS/dev/pts"

for p in ttyGS0 smd8 ttyHSL2; do
  [[ ! -e "$ROOTFS/dev/$p" && ! -L "$ROOTFS/dev/$p" ]] || die "$ROOTFS/dev/$p existiert bereits. Bitte vor dem Test entfernen."
done

log "A/B-Test vorbereiten: nur /dev/ttyGS0 und /dev/smd8 werden als PTYs bereitgestellt"
log "/dev/ttyHSL2 bleibt absichtlich NICHT vorhanden. Netzwerk bleibt vollstaendig isoliert."

set +e
unshare --net --mount --fork bash -c '
  set -Eeuo pipefail
  ROOTFS="$1"
  RUN_DIR="$2"
  RUN_SECS="$3"

  cleanup() {
    set +e
    [[ -n "${CAT_GS0:-}" ]] && kill "$CAT_GS0" 2>/dev/null || true
    [[ -n "${CAT_SMD8:-}" ]] && kill "$CAT_SMD8" 2>/dev/null || true
    [[ -n "${SOC_GS0:-}" ]] && kill "$SOC_GS0" 2>/dev/null || true
    [[ -n "${SOC_SMD8:-}" ]] && kill "$SOC_SMD8" 2>/dev/null || true
    rm -f "$ROOTFS/dev/ttyGS0" "$ROOTFS/dev/smd8"
    umount "$ROOTFS/dev/pts" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM

  mount --make-rprivate /
  mount --bind /dev/pts "$ROOTFS/dev/pts"

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

  if ip route show default | grep -q . || ip -6 route show default | grep -q .; then
    echo "UNSAFE: default route exists" >&2
    exit 90
  fi

  socat -d -d \
    PTY,raw,echo=0,link="$ROOTFS/dev/ttyGS0" \
    PTY,raw,echo=0,link="$RUN_DIR/ttyGS0.peer" \
    2> "$RUN_DIR/socat-ttyGS0.log" &
  SOC_GS0=$!

  socat -d -d \
    PTY,raw,echo=0,link="$ROOTFS/dev/smd8" \
    PTY,raw,echo=0,link="$RUN_DIR/smd8.peer" \
    2> "$RUN_DIR/socat-smd8.log" &
  SOC_SMD8=$!

  for i in $(seq 1 30); do
    [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" && -L "$RUN_DIR/ttyGS0.peer" && -L "$RUN_DIR/smd8.peer" ]] && break
    sleep 0.1
  done
  [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" ]] || { echo "PTY-Erzeugung fehlgeschlagen" >&2; exit 92; }

  # Capture only what the original application sends. No modem replies are generated.
  cat "$RUN_DIR/ttyGS0.peer" > "$RUN_DIR/ttyGS0-tx.bin" &
  CAT_GS0=$!
  cat "$RUN_DIR/smd8.peer" > "$RUN_DIR/smd8-tx.bin" &
  CAT_SMD8=$!

  {
    echo "ttyGS0 -> $(readlink "$ROOTFS/dev/ttyGS0")"
    echo "smd8   -> $(readlink "$ROOTFS/dev/smd8")"
    echo "ttyHSL2 absent: $([[ ! -e "$ROOTFS/dev/ttyHSL2" ]] && echo yes || echo no)"
  } > "$RUN_DIR/pty-map.txt"

  ulimit -c 0
  timeout -k 2 "${RUN_SECS}s" \
    chroot "$ROOTFS" \
      /usr/bin/qemu-arm-static -L / -strace /data/phnixIot4G \
      > "$RUN_DIR/stdout.log" 2> "$RUN_DIR/qemu-strace.log"
' bash "$ROOTFS" "$RUN_DIR" "$RUN_SECS"
RC=$?
set -e
printf '%s\n' "$RC" > "$RUN_DIR/exit-code.txt"

printf '\nExit-Code: %s\n' "$RC"
case "$RC" in
  0)   echo "Programm hat selbst beendet." ;;
  124) echo "Erwarteter Timeout: phnixIot4G lief nach ${RUN_SECS}s noch." ;;
  137) echo "Prozess musste nach Timeout hart beendet werden." ;;
  90)  die "Netzwerk-Sicherheitspruefung fehlgeschlagen. Binary wurde nicht gestartet." ;;
  92)  die "PTY-Erzeugung fehlgeschlagen." ;;
  *)   echo "Programm/QEMU beendete sich mit Fehlercode $RC." ;;
esac

printf '\n=== PTY-Zuordnung ===\n'
cat "$RUN_DIR/pty-map.txt" 2>/dev/null || true

printf '\n=== phnixIot4G stdout (letzte 120 Zeilen) ===\n'
tail -n 120 "$RUN_DIR/stdout.log" 2>/dev/null || true

printf '\n=== Relevante Device-Zugriffe ===\n'
grep -aE '/dev/(ttyGS0|smd8|ttyHSL2|diag|smem_log)' "$RUN_DIR/qemu-strace.log" 2>/dev/null || true

printf '\n=== Netzwerk-Systemcalls ===\n'
grep -aE 'socket\(|connect\(|bind\(|sendto\(|recvfrom\(' "$RUN_DIR/qemu-strace.log" 2>/dev/null || echo '(keine)'

for p in ttyGS0 smd8; do
  printf '\n=== %s: vom Original gesendete Bytes ===\n' "$p"
  if [[ -s "$RUN_DIR/${p}-tx.bin" ]]; then
    xxd -g1 "$RUN_DIR/${p}-tx.bin" | head -n 120
    printf '\nASCII/Strings:\n'
    strings -a "$RUN_DIR/${p}-tx.bin" | head -n 120 || true
  else
    echo '(keine Bytes gesendet)'
  fi
done

printf '\n=== ttyHSL2 Kontext ===\n'
if grep -aq '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" 2>/dev/null; then
  grep -an -B8 -A12 '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" | head -n 160
else
  echo '(weiterhin kein ttyHSL2-Zugriff)'
fi

printf '\n=== Letzte 80 Trace-Zeilen ===\n'
tail -n 80 "$RUN_DIR/qemu-strace.log" 2>/dev/null || true

printf '\nLogs: %s\n' "$RUN_DIR"
cat <<'EOF'

Testdesign:
- Gegenueber dem ersten Offline-Lauf wurden nur ttyGS0 und smd8 als PTYs hinzugefuegt.
- Es werden keinerlei AT-Antworten erzeugt.
- ttyHSL2 bleibt absichtlich abwesend.
- Kein LAN/Internet im Prozess-Namespace.
EOF
