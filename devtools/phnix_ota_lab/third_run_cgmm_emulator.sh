#!/usr/bin/env bash
set -Eeuo pipefail

LAB_ROOT="/opt/phnix-lab"
ROOTFS="$LAB_ROOT/rootfs"
RUN_SECS="${1:-30}"
MODEL="SIMCOM_SIM7600E-H"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$LAB_ROOT/logs/cgmm-emulator-$STAMP"

log() { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || die "Bitte als root starten: sudo $0 [Sekunden]"
[[ -x "$ROOTFS/data/phnixIot4G" ]] || die "$ROOTFS/data/phnixIot4G fehlt"
[[ -x "$ROOTFS/usr/bin/qemu-arm-static" ]] || die "$ROOTFS/usr/bin/qemu-arm-static fehlt"
for cmd in unshare socat timeout xxd python3 ip; do
  command -v "$cmd" >/dev/null 2>&1 || die "$cmd fehlt"
done

case "$RUN_SECS" in
  ''|*[!0-9]*) die "Laufzeit muss eine ganze Zahl in Sekunden sein" ;;
esac
(( RUN_SECS >= 5 && RUN_SECS <= 120 )) || die "Laufzeit muss zwischen 5 und 120 Sekunden liegen"

install -d -m 0755 "$RUN_DIR" "$ROOTFS/dev" "$ROOTFS/dev/pts"
for p in ttyGS0 smd8 ttyHSL2; do
  [[ ! -e "$ROOTFS/dev/$p" && ! -L "$ROOTFS/dev/$p" ]] || die "$ROOTFS/dev/$p existiert bereits. Bitte vor dem Test entfernen."
done

cat > "$RUN_DIR/cgmm_emulator.py" <<'PY'
#!/usr/bin/env python3
import os
import select
import sys
import time

peer, from_app_path, to_app_path, transcript_path, model = sys.argv[1:]
reply = ("\r\n" + model + "\r\n\r\nOK\r\n").encode("ascii")
fd = os.open(peer, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
buf = b""
reply_count = 0

with open(from_app_path, "ab", buffering=0) as from_app, \
     open(to_app_path, "ab", buffering=0) as to_app, \
     open(transcript_path, "a", encoding="utf-8", buffering=1) as transcript:
    transcript.write(f"MODEL={model}\n")
    transcript.write("RULE=reply only to exact AT+CGMM\n")
    while True:
        ready, _, _ = select.select([fd], [], [], 0.25)
        if not ready:
            continue
        try:
            data = os.read(fd, 4096)
        except BlockingIOError:
            continue
        if not data:
            time.sleep(0.05)
            continue

        from_app.write(data)
        buf += data

        while True:
            positions = [p for p in (buf.find(b"\r"), buf.find(b"\n")) if p >= 0]
            if not positions:
                break
            pos = min(positions)
            line = buf[:pos]
            end = pos
            while end < len(buf) and buf[end] in b"\r\n":
                end += 1
            buf = buf[end:]
            if not line:
                continue

            text = line.decode("ascii", errors="replace")
            transcript.write(f"APP -> MODEM: {text!r}\n")
            if line == b"AT+CGMM":
                os.write(fd, reply)
                to_app.write(reply)
                reply_count += 1
                transcript.write(f"MODEM -> APP: {reply!r}\n")
                transcript.write(f"CGMM_REPLY_COUNT={reply_count}\n")
PY
chmod 0755 "$RUN_DIR/cgmm_emulator.py"

log "Test 3: nur AT+CGMM wird beantwortet"
printf 'Modellantwort: %s\n' "$MODEL"
printf 'Lab-Modus: Netzwerk isoliert | ttyGS0+smd8 = PTY | ttyHSL2 fehlt\n'

set +e
unshare --net --mount --fork bash -c '
  set -Eeuo pipefail
  ROOTFS="$1"
  RUN_DIR="$2"
  RUN_SECS="$3"
  MODEL="$4"

  cleanup() {
    set +e
    for pid in "${EMU_PID:-}" "${CAT_GS0:-}" "${SOC_GS0:-}" "${SOC_SMD8:-}"; do
      [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done
    rm -f "$ROOTFS/dev/ttyGS0" "$ROOTFS/dev/smd8"
    umount "$ROOTFS/dev/pts" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM

  mount --make-rprivate /
  mount --bind /dev/pts "$ROOTFS/dev/pts"
  ip link set lo up

  if ip route show default | grep -q . || ip -6 route show default | grep -q .; then
    echo "Netzwerk-Namespace hat unerwartet eine Default-Route" >&2
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

  for _ in $(seq 1 30); do
    [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" && -L "$RUN_DIR/ttyGS0.peer" && -L "$RUN_DIR/smd8.peer" ]] && break
    sleep 0.1
  done
  [[ -L "$ROOTFS/dev/ttyGS0" && -L "$ROOTFS/dev/smd8" ]] || exit 92

  cat "$RUN_DIR/ttyGS0.peer" > "$RUN_DIR/ttyGS0-from-app.bin" &
  CAT_GS0=$!

  python3 "$RUN_DIR/cgmm_emulator.py" \
    "$RUN_DIR/smd8.peer" \
    "$RUN_DIR/smd8-from-app.bin" \
    "$RUN_DIR/smd8-to-app.bin" \
    "$RUN_DIR/smd8-transcript.txt" \
    "$MODEL" &
  EMU_PID=$!

  sleep 0.2
  ulimit -c 0
  timeout -k 2 "${RUN_SECS}s" \
    chroot "$ROOTFS" \
      /usr/bin/qemu-arm-static -L / -strace /data/phnixIot4G \
      > "$RUN_DIR/stdout.log" 2> "$RUN_DIR/qemu-strace.log"
' bash "$ROOTFS" "$RUN_DIR" "$RUN_SECS" "$MODEL"
RC=$?
set -e
printf '%s\n' "$RC" > "$RUN_DIR/exit-code.txt"

printf '\nExit-Code: %s\n' "$RC"
case "$RC" in
  0)   echo "Programm hat selbst beendet." ;;
  124) echo "Timeout: phnixIot4G lief nach ${RUN_SECS}s noch." ;;
  137) echo "Prozess musste nach Timeout hart beendet werden." ;;
  136) echo "SIGFPE wie im vorherigen Lauf; Transcript zeigt, ob CGMM davor verarbeitet wurde." ;;
  90)  die "Unerwartete Default-Route im Test-Namespace." ;;
  92)  die "PTY-Erzeugung fehlgeschlagen." ;;
  *)   echo "Programm/QEMU beendete sich mit Fehlercode $RC." ;;
esac

printf '\n=== AT-Transcript ===\n'
cat "$RUN_DIR/smd8-transcript.txt" 2>/dev/null || echo '(kein AT-Verkehr aufgezeichnet)'

printf '\n=== smd8: Original -> Emulator ===\n'
if [[ -s "$RUN_DIR/smd8-from-app.bin" ]]; then
  xxd -g1 "$RUN_DIR/smd8-from-app.bin" | head -n 160
else
  echo '(keine Bytes)'
fi

printf '\n=== smd8: Emulator -> Original ===\n'
if [[ -s "$RUN_DIR/smd8-to-app.bin" ]]; then
  xxd -g1 "$RUN_DIR/smd8-to-app.bin" | head -n 80
else
  echo '(keine Antwort gesendet)'
fi

printf '\n=== phnixIot4G stdout (letzte 120 Zeilen) ===\n'
tail -n 120 "$RUN_DIR/stdout.log" 2>/dev/null || true

printf '\n=== Relevante Device-Zugriffe ===\n'
grep -aE '/dev/(ttyGS0|smd8|ttyHSL2|diag|smem_log)' "$RUN_DIR/qemu-strace.log" 2>/dev/null || true

printf '\n=== Netzwerk-Systemcalls ===\n'
grep -aE 'socket\(|connect\(|bind\(|sendto\(|recvfrom\(' "$RUN_DIR/qemu-strace.log" 2>/dev/null || echo '(keine)'

printf '\n=== ttyHSL2 Kontext ===\n'
if grep -aq '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" 2>/dev/null; then
  grep -an -B8 -A12 '/dev/ttyHSL2' "$RUN_DIR/qemu-strace.log" | head -n 160
else
  echo '(weiterhin kein ttyHSL2-Zugriff)'
fi

printf '\n=== Letzte 100 Trace-Zeilen ===\n'
tail -n 100 "$RUN_DIR/qemu-strace.log" 2>/dev/null || true

printf '\nLogs: %s\n' "$RUN_DIR"
cat <<'ENDTEXT'

A/B-Aenderung gegenueber Test 2:
- exakt eine neue Emulation: AT+CGMM -> SIMCOM_SIM7600E-H + OK
- alle weiteren AT-Befehle bleiben unbeantwortet
- ttyHSL2 bleibt abwesend
- Netzwerk bleibt isoliert
ENDTEXT
