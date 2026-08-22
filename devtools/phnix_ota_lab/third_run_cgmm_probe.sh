#!/usr/bin/env bash
set -Eeuo pipefail

LAB_ROOT="/opt/phnix-lab"
ROOTFS="$LAB_ROOT/rootfs"
RUN_SECS="${1:-40}"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$LAB_ROOT/logs/cgmm-probe-$STAMP"

log()  { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || die "Bitte als root starten: sudo $0 [Sekunden]"
[[ -x "$ROOTFS/data/phnixIot4G" ]] || die "$ROOTFS/data/phnixIot4G fehlt"
[[ -x "$ROOTFS/usr/bin/qemu-arm-static" ]] || die "$ROOTFS/usr/bin/qemu-arm-static fehlt"
command -v unshare >/dev/null 2>&1 || die "unshare fehlt"
command -v socat >/dev/null 2>&1 || die "socat fehlt"
command -v timeout >/dev/null 2>&1 || die "timeout fehlt"
command -v python3 >/dev/null 2>&1 || die "python3 fehlt"
command -v xxd >/dev/null 2>&1 || die "xxd fehlt"

case "$RUN_SECS" in
  ''|*[!0-9]*) die "Laufzeit muss eine ganze Zahl in Sekunden sein" ;;
esac
(( RUN_SECS >= 10 && RUN_SECS <= 120 )) || die "Laufzeit muss zwischen 10 und 120 Sekunden liegen"

install -d -m 0755 "$RUN_DIR" "$ROOTFS/dev" "$ROOTFS/dev/pts"

for p in ttyGS0 smd8 ttyHSL2; do
  [[ ! -e "$ROOTFS/dev/$p" && ! -L "$ROOTFS/dev/$p" ]] || die "$ROOTFS/dev/$p existiert bereits. Bitte vor dem Test entfernen."
done

cat > "$RUN_DIR/cgmm_responder.py" <<'PY'
#!/usr/bin/env python3
import os
import select
import sys
import time

peer, tx_path, event_path = sys.argv[1:4]
response = b"\r\nSIMCOM_SIM7600E-H\r\n\r\nOK\r\n"
needle = b"AT+CGMM"

fd = os.open(peer, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
buf = b""
sent = False

with open(tx_path, "ab", buffering=0) as tx, open(event_path, "a", buffering=1) as ev:
    ev.write("Responder started; only AT+CGMM will receive a reply.\n")
    while True:
        try:
            ready, _, _ = select.select([fd], [], [], 0.25)
            if not ready:
                continue
            data = os.read(fd, 4096)
            if not data:
                time.sleep(0.05)
                continue
            tx.write(data)
            buf = (buf + data)[-8192:]
            if not sent and needle in buf:
                os.write(fd, response)
                sent = True
                ev.write("RX matched AT+CGMM -> TX SIMCOM_SIM7600E-H + OK\n")
        except BlockingIOError:
            continue
        except OSError as exc:
            ev.write(f"Responder stopped: {exc}\n")
            break
PY
chmod 0755 "$RUN_DIR/cgmm_responder.py"

log "Dritter A/B-Test: nur AT+CGMM wird beantwortet"
log "Antwort: SIMCOM_SIM7600E-H + OK; alle weiteren AT-Kommandos bleiben unbeantwortet."
log "/dev/ttyHSL2 bleibt abwesend; Prozess-Netzwerk bleibt vollstaendig isoliert."

set +e
unshare --net --mount --fork bash -c '
  set -Eeuo pipefail
  ROOTFS="$1"
  RUN_DIR="$2"
  RUN_SECS="$3"

  cleanup() {
    set +e
    [[ -n "${CAT_GS0:-}" ]] && kill "$CAT_GS0" 2>/dev/null || true
    [[ -n "${RESP_PID:-}" ]] && kill "$RESP_PID" 2>/dev/null || true
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

  for i in $(seq 1 40); do
    [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" && -L "$RUN_DIR/ttyGS0.peer" && -L "$RUN_DIR/smd8.peer" ]] && break
    sleep 0.1
  done
  [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" ]] || { echo "PTY-Erzeugung fehlgeschlagen" >&2; exit 92; }

  cat "$RUN_DIR/ttyGS0.peer" > "$RUN_DIR/ttyGS0-tx.bin" &
  CAT_GS0=$!

  python3 "$RUN_DIR/cgmm_responder.py" \
    "$RUN_DIR/smd8.peer" "$RUN_DIR/smd8-tx.bin" "$RUN_DIR/responder.log" &
  RESP_PID=$!

  {
    echo "ttyGS0 -> $(readlink "$ROOTFS/dev/ttyGS0")"
    echo "smd8   -> $(readlink "$ROOTFS/dev/smd8")"
    echo "ttyHSL2 absent: $([[ ! -e "$ROOTFS/dev/ttyHSL2" ]] && echo yes || echo no)"
    echo "CGMM response: SIMCOM_SIM7600E-H"
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
  136) echo "SIGFPE: ein aktiver Pfad lief weiterhin in eine Division/FP-Ausnahme." ;;
  90)  die "Netzwerk-Sicherheitspruefung fehlgeschlagen. Binary wurde nicht gestartet." ;;
  92)  die "PTY-Erzeugung fehlgeschlagen." ;;
  *)   echo "Programm/QEMU beendete sich mit Fehlercode $RC." ;;
esac

printf '\n=== PTY-Zuordnung / Testantwort ===\n'
cat "$RUN_DIR/pty-map.txt" 2>/dev/null || true

printf '\n=== CGMM-Responder ===\n'
cat "$RUN_DIR/responder.log" 2>/dev/null || echo '(kein Responder-Log)'

printf '\n=== phnixIot4G: CGMM/ModeType/AT-relevante Logs ===\n'
grep -aEi 'CGMM|ModeType|fault CGMM|AT port|ttyGS0' "$RUN_DIR/stdout.log" 2>/dev/null | tail -n 120 || true

printf '\n=== Alle vom Original an smd8 gesendeten Bytes ===\n'
if [[ -s "$RUN_DIR/smd8-tx.bin" ]]; then
  xxd -g1 "$RUN_DIR/smd8-tx.bin" | head -n 160
  printf '\nASCII/Strings:\n'
  strings -a "$RUN_DIR/smd8-tx.bin" | head -n 160 || true
else
  echo '(keine Bytes gesendet)'
fi

printf '\n=== Erkannte AT-Kommandos in Sendereihenfolge ===\n'
if [[ -s "$RUN_DIR/smd8-tx.bin" ]]; then
  python3 - "$RUN_DIR/smd8-tx.bin" <<'PY'
import re, sys
b = open(sys.argv[1], 'rb').read()
text = b.replace(b'\r', b'\n').decode('latin1', 'replace')
for line in text.splitlines():
    line = line.strip()
    if line.startswith('AT'):
        print(line)
PY
else
  echo '(keine)'
fi

printf '\n=== Relevante Device-Zugriffe ===\n'
grep -aE '/dev/(ttyGS0|smd8|ttyHSL2|diag|smem_log)' "$RUN_DIR/qemu-strace.log" 2>/dev/null || true

printf '\n=== ttyHSL2 Kontext ===\n'
if grep -aq '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" 2>/dev/null; then
  grep -an -B10 -A16 '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" | head -n 220
else
  echo '(weiterhin kein ttyHSL2-Zugriff)'
fi

printf '\n=== Netzwerk-Systemcalls ===\n'
grep -aE 'socket\(|connect\(|bind\(|sendto\(|recvfrom\(' "$RUN_DIR/qemu-strace.log" 2>/dev/null || echo '(keine)'

printf '\n=== Letzte 100 Trace-Zeilen ===\n'
tail -n 100 "$RUN_DIR/qemu-strace.log" 2>/dev/null || true

printf '\nLogs: %s\n' "$RUN_DIR"
cat <<'EOF'

Testdesign:
- Gegenueber dem zweiten Lauf wird genau eine neue Information simuliert:
  AT+CGMM -> SIMCOM_SIM7600E-H + OK.
- Andere AT-Kommandos erhalten keine Antwort und werden nur protokolliert.
- /dev/ttyHSL2 bleibt absichtlich abwesend.
- Kein LAN/Internet im Prozess-Namespace.
EOF
