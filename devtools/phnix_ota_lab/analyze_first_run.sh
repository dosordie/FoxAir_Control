#!/usr/bin/env bash
set -Eeuo pipefail

LAB_ROOT="/opt/phnix-lab"
RUN_DIR="${1:-}"

if [[ -z "$RUN_DIR" ]]; then
  RUN_DIR="$(find "$LAB_ROOT/logs" -maxdepth 1 -type d -name 'first-run-*' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)"
fi

[[ -n "$RUN_DIR" && -d "$RUN_DIR" ]] || { echo "Kein first-run Log gefunden." >&2; exit 1; }
TRACE="$RUN_DIR/qemu-strace.log"
STDOUT="$RUN_DIR/stdout.log"
[[ -f "$TRACE" ]] || { echo "Trace fehlt: $TRACE" >&2; exit 1; }

echo "=== PHNIX first-run Analyse ==="
echo "Run: $RUN_DIR"
echo

printf '%s\n' '=== Exit-Code ==='
cat "$RUN_DIR/exit-code.txt" 2>/dev/null || true

echo
printf '%s\n' '=== phnixIot4G stdout ==='
if [[ -s "$STDOUT" ]]; then
  sed -n '1,200p' "$STDOUT"
else
  echo '(leer)'
fi

echo
printf '%s\n' '=== Alle Zugriffe auf relevante Devices ==='
grep -aE '/dev/(ttyHSL2|ttyGS0|smd8|diag|smem_log)' "$TRACE" || echo '(keine)'

echo
printf '%s\n' '=== Eindeutige fehlende Pfade (open/access/execve, ENOENT) ==='
grep -a 'errno=2 (No such file or directory)' "$TRACE" \
  | sed -nE 's/.*(open|openat|access|execve)\("([^"]+)".*/\2/p' \
  | sort | uniq -c | sort -nr || true

echo
printf '%s\n' '=== Netzwerk-Systemcalls ==='
grep -aE ' (socket|connect|bind|listen|accept|sendto|recvfrom|getpeername|getsockname)\(' "$TRACE" || echo '(keine)'

echo
printf '%s\n' '=== GPIO/system()-Aufrufe ==='
grep -aE 'execve\("/bin/sh"|/sys/class/gpio/' "$TRACE" || echo '(keine)'

echo
printf '%s\n' '=== /data und /cache Zugriffe ==='
grep -aE '(/data/|/cache/)' "$TRACE" || echo '(keine)'

echo
printf '%s\n' '=== ttyHSL2 Kontext (+/- 8 Zeilen) ==='
if grep -aq '/dev/ttyHSL2' "$TRACE"; then
  grep -an -B8 -A8 '/dev/ttyHSL2' "$TRACE"
else
  echo '(kein ttyHSL2-Zugriff im gesamten Trace)'
fi

echo
printf '%s\n' '=== qmi_fw.conf Kontext (+/- 5 Zeilen) ==='
grep -an -B5 -A5 '/etc/qmi_fw.conf' "$TRACE" || echo '(keine)'

echo
printf '%s\n' '=== Datei-Aenderungen ==='
cat "$RUN_DIR/files-diff.txt" 2>/dev/null || true

echo
printf '%s\n' '=== Trace Statistik ==='
printf 'Zeilen: '; wc -l < "$TRACE"
printf 'PIDs/TIDs im Trace: '
awk '/^[0-9]+ /{print $1}' "$TRACE" | sort -u | wc -l
