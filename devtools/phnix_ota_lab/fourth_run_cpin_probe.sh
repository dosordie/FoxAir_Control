#!/usr/bin/env bash
set -Eeuo pipefail

LAB_ROOT="/opt/phnix-lab"
ROOTFS="$LAB_ROOT/rootfs"
RUN_SECS="${1:-50}"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$LAB_ROOT/logs/cpin-probe-$STAMP"

log()  { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || die "Bitte als root starten: sudo $0 [Sekunden]"
[[ -x "$ROOTFS/data/phnixIot4G" ]] || die "$ROOTFS/data/phnixIot4G fehlt"
[[ -x "$ROOTFS/usr/bin/qemu-arm-static" ]] || die "$ROOTFS/usr/bin/qemu-arm-static fehlt"
for c in unshare socat timeout python3 xxd ip mount; do
  command -v "$c" >/dev/null 2>&1 || die "$c fehlt"
done
case "$RUN_SECS" in ''|*[!0-9]*) die "Laufzeit muss eine ganze Zahl sein";; esac
(( RUN_SECS >= 10 && RUN_SECS <= 120 )) || die "Laufzeit muss zwischen 10 und 120 Sekunden liegen"

install -d -m 0755 "$RUN_DIR" "$ROOTFS/dev" "$ROOTFS/dev/pts"
for p in ttyGS0 smd8 ttyHSL2; do
  [[ ! -e "$ROOTFS/dev/$p" && ! -L "$ROOTFS/dev/$p" ]] || die "$ROOTFS/dev/$p existiert bereits"
done

cat > "$RUN_DIR/at_responder.py" <<'PY'
#!/usr/bin/env python3
import os, select, sys, time
peer, tx_path, event_path = sys.argv[1:4]
fd = os.open(peer, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
buf = b""
seen = set()
responses = {
    b"AT+CGMM":  b"\r\nSIMCOM_SIM7600E-H\r\n\r\nOK\r\n",
    b"AT+CPIN?": b"\r\n+CPIN: READY\r\n\r\nOK\r\n",
}
with open(tx_path, "ab", buffering=0) as tx, open(event_path, "a", buffering=1) as ev:
    ev.write("Responder started; replies only to AT+CGMM and AT+CPIN?.\n")
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
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                cmd = line.strip(b"\r \t")
                if not cmd:
                    continue
                ev.write("RX " + cmd.decode("latin1", "replace") + "\n")
                if cmd in responses:
                    os.write(fd, responses[cmd])
                    ev.write("TX response for " + cmd.decode("ascii", "replace") + "\n")
        except BlockingIOError:
            continue
        except OSError as exc:
            ev.write(f"Responder stopped: {exc}\n")
            break
PY
chmod 0755 "$RUN_DIR/at_responder.py"

log "Vierter A/B-Test: CGMM und CPIN werden beantwortet"
log "CGMM -> SIMCOM_SIM7600E-H; CPIN -> +CPIN: READY; alles Weitere nur mitschneiden."
log "/dev/ttyHSL2 bleibt abwesend; Prozess-Netzwerk bleibt vollstaendig isoliert."

set +e
unshare --net --mount --fork bash -c '
  set -Eeuo pipefail
  ROOTFS="$1"; RUN_DIR="$2"; RUN_SECS="$3"
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
  { ip -brief link; echo; ip -brief addr; echo; ip route; echo; ip -6 route || true; } > "$RUN_DIR/network.txt"
  if ip route show default | grep -q . || ip -6 route show default | grep -q .; then exit 90; fi

  socat PTY,raw,echo=0,link="$ROOTFS/dev/ttyGS0" PTY,raw,echo=0,link="$RUN_DIR/ttyGS0.peer" 2>"$RUN_DIR/socat-ttyGS0.log" & SOC_GS0=$!
  socat PTY,raw,echo=0,link="$ROOTFS/dev/smd8" PTY,raw,echo=0,link="$RUN_DIR/smd8.peer" 2>"$RUN_DIR/socat-smd8.log" & SOC_SMD8=$!
  for i in $(seq 1 40); do
    [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" ]] && break
    sleep 0.1
  done
  [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" ]] || exit 92

  cat "$RUN_DIR/ttyGS0.peer" > "$RUN_DIR/ttyGS0-tx.bin" & CAT_GS0=$!
  python3 "$RUN_DIR/at_responder.py" "$RUN_DIR/smd8.peer" "$RUN_DIR/smd8-tx.bin" "$RUN_DIR/responder.log" & RESP_PID=$!

  {
    echo "ttyGS0 -> $(readlink "$ROOTFS/dev/ttyGS0")"
    echo "smd8   -> $(readlink "$ROOTFS/dev/smd8")"
    echo "ttyHSL2 absent: $([[ ! -e "$ROOTFS/dev/ttyHSL2" ]] && echo yes || echo no)"
    echo "CGMM response: SIMCOM_SIM7600E-H"
    echo "CPIN response: +CPIN: READY"
  } > "$RUN_DIR/pty-map.txt"

  ulimit -c 0
  timeout -k 2 "${RUN_SECS}s" chroot "$ROOTFS" /usr/bin/qemu-arm-static -L / -strace /data/phnixIot4G >"$RUN_DIR/stdout.log" 2>"$RUN_DIR/qemu-strace.log"
' bash "$ROOTFS" "$RUN_DIR" "$RUN_SECS"
RC=$?
set -e
printf '%s\n' "$RC" > "$RUN_DIR/exit-code.txt"

printf '\nExit-Code: %s\n' "$RC"
case "$RC" in
  124) echo "Erwarteter Timeout: Prozess lief weiter.";;
  136) echo "SIGFPE: aktiver Pfad lief erneut in eine Ausnahme.";;
  0) echo "Programm hat selbst beendet.";;
  90) die "Netzwerk-Sicherheitspruefung fehlgeschlagen";;
  92) die "PTY-Erzeugung fehlgeschlagen";;
  *) echo "Programm/QEMU beendete sich mit Fehlercode $RC.";;
esac

printf '\n=== PTY / Testantworten ===\n'; cat "$RUN_DIR/pty-map.txt" 2>/dev/null || true
printf '\n=== AT-Responder ===\n'; cat "$RUN_DIR/responder.log" 2>/dev/null || true
printf '\n=== Erkannte AT-Kommandos ===\n'
if [[ -s "$RUN_DIR/smd8-tx.bin" ]]; then
  python3 - "$RUN_DIR/smd8-tx.bin" <<'PY'
import sys
b=open(sys.argv[1],'rb').read().replace(b'\r',b'\n').decode('latin1','replace')
for line in b.splitlines():
    line=line.strip()
    if line.startswith('AT'): print(line)
PY
else echo '(keine)'; fi

printf '\n=== smd8 Rohdaten ===\n'; [[ -s "$RUN_DIR/smd8-tx.bin" ]] && xxd -g1 "$RUN_DIR/smd8-tx.bin" | head -n 180 || echo '(keine)'
printf '\n=== Relevante stdout-Logs ===\n'; grep -aEi 'CGMM|CPIN|CCID|CSQ|CGREG|CREG|CGSN|APN|ttyHSL2|485|AT port' "$RUN_DIR/stdout.log" 2>/dev/null | tail -n 180 || true
printf '\n=== Relevante Device-Zugriffe ===\n'; grep -aE '/dev/(ttyGS0|smd8|ttyHSL2|diag|smem_log)' "$RUN_DIR/qemu-strace.log" 2>/dev/null || true
printf '\n=== ttyHSL2 Kontext ===\n'
if grep -aq '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" 2>/dev/null; then grep -an -B10 -A18 '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" | head -n 240; else echo '(weiterhin kein ttyHSL2-Zugriff)'; fi
printf '\n=== Netzwerk-Systemcalls ===\n'; grep -aE 'socket\(|connect\(|bind\(|sendto\(|recvfrom\(' "$RUN_DIR/qemu-strace.log" 2>/dev/null || echo '(keine)'
printf '\n=== Trace-Ende ===\n'; tail -n 100 "$RUN_DIR/qemu-strace.log" 2>/dev/null || true
printf '\nLogs: %s\n' "$RUN_DIR"
cat <<'EOF'

Testdesign:
- Bisher akzeptierte CGMM-Antwort bleibt bestehen.
- Neu wird nur AT+CPIN? mit +CPIN: READY + OK beantwortet.
- Alle weiteren AT-Kommandos werden nur protokolliert.
- /dev/ttyHSL2 bleibt abwesend.
- Kein LAN/Internet im Prozess-Namespace.
EOF
