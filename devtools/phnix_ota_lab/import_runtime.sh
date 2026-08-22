#!/usr/bin/env bash
set -Eeuo pipefail

LAB_ROOT="/opt/phnix-lab"
ROOTFS="$LAB_ROOT/rootfs"
SRC="${1:-$LAB_ROOT/runtime-import/source}"

log()  { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m[WARN]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || die "Bitte als root starten: sudo $0 [Quellordner]"
[[ -d "$SRC" ]] || die "Quellordner nicht gefunden: $SRC"

install -d -m 0755 \
  "$ROOTFS/lib" "$ROOTFS/usr/lib" "$ROOTFS/etc/data" \
  "$ROOTFS/data" "$ROOTFS/data/mifi" "$ROOTFS/cache" "$ROOTFS/tmp"
chmod 1777 "$ROOTFS/tmp"

copy_tree() {
  local from="$1" to="$2"
  if [[ -d "$from" ]]; then
    log "Kopiere $from -> $to"
    rsync -a "$from/" "$to/"
  else
    warn "Nicht gefunden, uebersprungen: $from"
  fi
}

copy_file() {
  local from="$1" to="$2"
  if [[ -f "$from" || -L "$from" ]]; then
    install -d -m 0755 "$(dirname "$to")"
    cp -a "$from" "$to"
    log "Kopiert: $from -> $to"
    return 0
  fi
  return 1
}

# Libraries from adb pull. On Windows dumps /usr/lib is often stored as usr_lib.
copy_tree "$SRC/lib" "$ROOTFS/lib"
if [[ -d "$SRC/usr_lib" ]]; then
  copy_tree "$SRC/usr_lib" "$ROOTFS/usr/lib"
elif [[ -d "$SRC/usr/lib" ]]; then
  copy_tree "$SRC/usr/lib" "$ROOTFS/usr/lib"
else
  warn "Weder $SRC/usr_lib noch $SRC/usr/lib gefunden."
fi

# Original application. Accept both common dump layouts.
if ! copy_file "$SRC/phnixIot4G" "$ROOTFS/data/phnixIot4G"; then
  copy_file "$SRC/data/phnixIot4G" "$ROOTFS/data/phnixIot4G" || \
    die "phnixIot4G nicht im Quellordner gefunden."
fi
chmod 0755 "$ROOTFS/data/phnixIot4G"

# Qualcomm configuration. Accept files either in their original tree or flat.
for f in dsi_config.xml netmgr_config.xml qmi_config.xml; do
  if ! copy_file "$SRC/etc/data/$f" "$ROOTFS/etc/data/$f"; then
    copy_file "$SRC/$f" "$ROOTFS/etc/data/$f" || warn "$f fehlt"
  fi
done

if ! copy_file "$SRC/etc/qmi_ip_cfg.xml" "$ROOTFS/etc/qmi_ip_cfg.xml"; then
  copy_file "$SRC/qmi_ip_cfg.xml" "$ROOTFS/etc/qmi_ip_cfg.xml" || warn "qmi_ip_cfg.xml fehlt"
fi

# Small libc/network config files are optional for the first loader test.
for f in nsswitch.conf hosts host.conf; do
  copy_file "$SRC/etc/$f" "$ROOTFS/etc/$f" || true
done
copy_file "$SRC/data/mifi/resolv.conf" "$ROOTFS/data/mifi/resolv.conf" || true

# Deliberately do NOT import persistent device/OTA state automatically.
# phnixIot_device_statisic may contain device-specific identifiers/secrets.
# phnixIot_device_OTA_INFO may contain resume/OTA state. We add them manually
# only if a later controlled test actually requires them.

log "Runtime-Pruefung"
[[ -e "$ROOTFS/lib/ld-linux.so.3" ]] || warn "Loader /lib/ld-linux.so.3 fehlt im RootFS"
file "$ROOTFS/data/phnixIot4G" || true

if command -v arm-linux-gnueabihf-readelf >/dev/null 2>&1; then
  printf '\nDirekte DT_NEEDED-Eintraege:\n'
  arm-linux-gnueabihf-readelf -d "$ROOTFS/data/phnixIot4G" 2>/dev/null | grep NEEDED || true
fi

printf '\nWichtige Dateien im RootFS:\n'
for p in \
  lib/ld-linux.so.3 \
  data/phnixIot4G \
  etc/data/dsi_config.xml \
  etc/data/netmgr_config.xml \
  etc/data/qmi_config.xml \
  etc/qmi_ip_cfg.xml; do
  if [[ -e "$ROOTFS/$p" ]]; then
    printf '  [OK]   %s\n' "$p"
  else
    printf '  [MISS] %s\n' "$p"
  fi
done

cat <<'EOF'

Import abgeschlossen.

NOCH NICHT phnixIot4G starten, solange die VM normalen Internetzugang hat.
Der erste Lauf wird bewusst offline und mit strace ausgefuehrt.

Hinweis:
- qemu-arm binfmt muss dafuer nicht aktiviert sein.
- Wir verwenden explizit qemu-arm-static -L /opt/phnix-lab/rootfs ...
- Geraetespezifische Statistik-/Credential-Dateien wurden absichtlich nicht importiert.
EOF
