#!/usr/bin/env bash
set -Eeuo pipefail

LAB_ROOT="/opt/phnix-lab"
ROOTFS="$LAB_ROOT/rootfs"
RUN_SECS="${1:-45}"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$LAB_ROOT/logs/bootstrap-probe-$STAMP"

log()  { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || die "Bitte als root starten: sudo $0 [Sekunden]"
[[ -x "$ROOTFS/data/phnixIot4G" ]] || die "$ROOTFS/data/phnixIot4G fehlt"
[[ -x "$ROOTFS/usr/bin/qemu-arm-static" ]] || die "$ROOTFS/usr/bin/qemu-arm-static fehlt"
command -v unshare >/dev/null 2>&1 || die "unshare fehlt"
command -v socat >/dev/null 2>&1 || die "socat fehlt"
command -v timeout >/dev/null 2>&1 || die "timeout fehlt"
command -v python3 >/dev/null 2>&1 || die "python3 fehlt"

case "$RUN_SECS" in
  ''|*[!0-9]*) die "Laufzeit muss eine ganze Zahl in Sekunden sein" ;;
esac
(( RUN_SECS >= 10 && RUN_SECS <= 120 )) || die "Laufzeit muss zwischen 10 und 120 Sekunden liegen"

install -d -m 0755 "$RUN_DIR" "$ROOTFS/dev" "$ROOTFS/dev/pts"

for p in ttyGS0 smd8 ttyHSL2; do
  [[ ! -e "$ROOTFS/dev/$p" && ! -L "$ROOTFS/dev/$p" ]] || die "$ROOTFS/dev/$p existiert bereits. Bitte vor dem Test entfernen."
done

cat > "$RUN_DIR/at_responder.py" <<'PY'
#!/usr/bin/env python3
import os, sys, time, select

peer = sys.argv[1]
run_dir = sys.argv[2]

tx_path = os.path.join(run_dir, "smd8-tx.bin")
rx_path = os.path.join(run_dir, "smd8-rx.bin")
log_path = os.path.join(run_dir, "at-dialog.log")

# Deliberately synthetic ICCID. It is not copied from a real modem and is used
# only to let the original parser continue in this isolated lab.
RESPONSES = {
    b"AT+CGMM": b"\r\nSIMCOM_SIM7600E-H\r\n\r\nOK\r\n",
    b"AT+CPIN?": b"\r\n+CPIN: READY\r\n\r\nOK\r\n",
    b"AT+CCID": b"\r\n+CCID: 8949000000000000000\r\n\r\nOK\r\n",
    b'AT+CGDCONT=1,"IPV4V6","orange.m2m.spec"': b"\r\nOK\r\n",
    b'AT+CGDCONT=6,"IPV4V6","orange.m2m.spec"': b"\r\nOK\r\n",
}

fd = os.open(peer, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
buf = bytearray()

with open(tx_path, "ab", buffering=0) as tx, open(rx_path, "ab", buffering=0) as rx, open(log_path, "a", buffering=1) as lg:
    lg.write("Controlled bootstrap responder started\n")
    lg.write("Only statically verified startup commands are answered. Unknown commands get no reply.\n")
    while True:
        r, _, _ = select.select([fd], [], [], 0.5)
        if not r:
            continue
        try:
            data = os.read(fd, 4096)
        except BlockingIOError:
            continue
        if not data:
            time.sleep(0.05)
            continue
        tx.write(data)
        buf.extend(data)
        while b"\n" in buf:
            line, _, rest = buf.partition(b"\n")
            buf[:] = rest
            cmd = line.rstrip(b"\r")
            if not cmd:
                continue
            lg.write("TX  " + repr(cmd) + "\n")
            reply = RESPONSES.get(cmd)
            if reply is None:
                lg.write("RX  <no reply: unknown command>\n")
                continue
            os.write(fd, reply)
            rx.write(reply)
            lg.write("RX  " + repr(reply) + "\n")
PY
chmod 0755 "$RUN_DIR/at_responder.py"

log "Bootstrap-A/B-Test vorbereiten"
log "Antworten nur auf CGMM, CPIN, CCID und die statisch belegten E-H-APN-Kommandos."
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

  for i in $(seq 1 30); do
    [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" && -L "$RUN_DIR/ttyGS0.peer" && -L "$RUN_DIR/smd8.peer" ]] && break
    sleep 0.1
  done
  [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" ]] || { echo "PTY-Erzeugung fehlgeschlagen" >&2; exit 92; }

  cat "$RUN_DIR/ttyGS0.peer" > "$RUN_DIR/ttyGS0-tx.bin" &
  CAT_GS0=$!

  python3 "$RUN_DIR/at_responder.py" "$RUN_DIR/smd8.peer" "$RUN_DIR" &
  RESP_PID=$!

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

printf '\n=== Kontrollierter AT-Dialog ===\n'
cat "$RUN_DIR/at-dialog.log" 2>/dev/null || true

printf '\n=== ttyHSL2-Zugriffe ===\n'
if grep -aq '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" 2>/dev/null; then
  grep -an -B8 -A16 '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" | head -n 220
else
  echo '(weiterhin kein ttyHSL2-Zugriff)'
fi

printf '\n=== Relevante Device-Zugriffe ===\n'
grep -aE '/dev/(ttyGS0|smd8|ttyHSL2|diag|smem_log)' "$RUN_DIR/qemu-strace.log" 2>/dev/null | tail -n 160 || true

printf '\n=== Netzwerk-Systemcalls ===\n'
grep -aE 'socket\(|connect\(|bind\(|sendto\(|recvfrom\(' "$RUN_DIR/qemu-strace.log" 2>/dev/null | tail -n 120 || echo '(keine)'

printf '\n=== phnixIot4G stdout (letzte 160 Zeilen) ===\n'
tail -n 160 "$RUN_DIR/stdout.log" 2>/dev/null || true

printf '\n=== Letzte 100 Trace-Zeilen ===\n'
tail -n 100 "$RUN_DIR/qemu-strace.log" 2>/dev/null || true

printf '\nLogs: %s\n' "$RUN_DIR"
cat <<'EOF'

Testdesign:
- Vollstaendig offline in eigenem Network-Namespace.
- ttyGS0 und smd8 sind PTYs.
- Antwortet nur auf statisch belegte Startup-Kommandos:
    AT+CGMM -> SIMCOM_SIM7600E-H + OK
    AT+CPIN? -> +CPIN: READY + OK
    AT+CCID -> synthetische ICCID + OK
    E-H APN context 1/6 -> OK
- Unbekannte AT-Kommandos werden nur protokolliert und NICHT beantwortet.
- ttyHSL2 bleibt absichtlich abwesend, damit sein erster open()-Versuch sichtbar wird.
- Keine realen Identitaeten/Secrets werden verwendet.
EOF
