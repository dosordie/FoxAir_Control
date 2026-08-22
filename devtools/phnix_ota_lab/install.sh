#!/usr/bin/env bash
set -Eeuo pipefail

# PHNIX/FoxAir OTA lab bootstrap for a fresh Debian VM.
# Installs the tools needed to run/analyse the original ARM phnixIot4G binary,
# provide a local MQTT/HTTP test environment and later emulate /dev/ttyHSL2.
#
# This script does NOT copy firmware, credentials or modem files and does NOT
# change the VM's routing/firewall. Keep Internet isolation at Proxmox level.

LAB_ROOT="/opt/phnix-lab"
MOSQ_CONF="/etc/mosquitto/conf.d/phnix-lab.conf"

log()  { printf '\n\033[1;32m[PHNIX-LAB]\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m[WARN]\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }
trap 'die "Fehler in Zeile $LINENO. Installation abgebrochen."' ERR

if [[ ${EUID} -ne 0 ]]; then
    die "Bitte als root starten: sudo ./install.sh"
fi

[[ -r /etc/os-release ]] || die "/etc/os-release fehlt. Debian konnte nicht erkannt werden."
# shellcheck disable=SC1091
source /etc/os-release

if [[ "${ID:-}" != "debian" ]]; then
    die "Dieses Script ist fuer Debian vorgesehen. Gefunden: ${PRETTY_NAME:-unbekannt}"
fi

case "${VERSION_ID:-}" in
    12|13) log "Erkannt: ${PRETTY_NAME}" ;;
    *) warn "Getestetes Ziel ist Debian 12/13. Gefunden: ${PRETTY_NAME:-unbekannt}. Ich versuche es trotzdem." ;;
esac

export DEBIAN_FRONTEND=noninteractive

log "APT-Paketlisten aktualisieren"
apt-get update

CORE_PACKAGES=(
    ca-certificates
    curl
    wget
    git
    jq
    file
    xxd
    less
    tree
    htop
    lsof
    iproute2
    iputils-ping
    netcat-openbsd
    socat
    tcpdump
    strace
    openssl
    build-essential
    pkg-config
    cmake
    python3
    python3-pip
    python3-venv
    qemu-user-static
    binfmt-support
    mosquitto
    mosquitto-clients
)

log "Kernwerkzeuge installieren"
apt-get install -y --no-install-recommends "${CORE_PACKAGES[@]}"

# Useful packages whose names/availability can vary slightly between Debian releases.
OPTIONAL_PACKAGES=(
    gdb-multiarch
    binutils
    binutils-arm-linux-gnueabihf
    elfutils
    pax-utils
    busybox-static
    python3-serial
    python3-paho-mqtt
    python3-flask
    ripgrep
    bsdextrautils
)

log "Optionale Analysewerkzeuge installieren, sofern verfuegbar"
for pkg in "${OPTIONAL_PACKAGES[@]}"; do
    if apt-cache show "$pkg" >/dev/null 2>&1; then
        apt-get install -y --no-install-recommends "$pkg"
    else
        warn "Paket nicht verfuegbar, uebersprungen: $pkg"
    fi
done

log "ARM binfmt/QEMU aktivieren"
if command -v update-binfmts >/dev/null 2>&1; then
    update-binfmts --enable qemu-arm >/dev/null 2>&1 || true
fi

if ! command -v qemu-arm-static >/dev/null 2>&1; then
    die "qemu-arm-static wurde nicht gefunden."
fi

log "Lab-Verzeichnisstruktur anlegen"
install -d -m 0755 \
    "$LAB_ROOT" \
    "$LAB_ROOT/rootfs" \
    "$LAB_ROOT/rootfs/bin" \
    "$LAB_ROOT/rootfs/sbin" \
    "$LAB_ROOT/rootfs/lib" \
    "$LAB_ROOT/rootfs/usr/lib" \
    "$LAB_ROOT/rootfs/etc" \
    "$LAB_ROOT/rootfs/data" \
    "$LAB_ROOT/rootfs/cache" \
    "$LAB_ROOT/rootfs/dev" \
    "$LAB_ROOT/rootfs/proc" \
    "$LAB_ROOT/rootfs/sys" \
    "$LAB_ROOT/rootfs/tmp" \
    "$LAB_ROOT/firmware" \
    "$LAB_ROOT/logs" \
    "$LAB_ROOT/pcap" \
    "$LAB_ROOT/tools" \
    "$LAB_ROOT/tmp"
chmod 1777 "$LAB_ROOT/rootfs/tmp" "$LAB_ROOT/tmp"

# A venv is useful for future simulators. --system-site-packages lets it use the
# Debian-packaged pyserial/paho/flask modules without requiring PyPI later.
if [[ ! -x "$LAB_ROOT/venv/bin/python" ]]; then
    log "Python-Virtualenv anlegen"
    python3 -m venv --system-site-packages "$LAB_ROOT/venv"
fi

log "Lokalen MQTT-Testbroker konfigurieren"
install -d -m 0755 /etc/mosquitto/conf.d

cat > "$MOSQ_CONF" <<'EOF'
# PHNIX OTA lab broker. Intentionally loopback-only.
# qemu-arm user-mode processes in this VM can reach it via 127.0.0.1.
listener 1883 127.0.0.1
allow_anonymous true
EOF

# Debian normally includes conf.d already. Add it only if a minimal image omitted it.
if ! grep -Eq '^[[:space:]]*include_dir[[:space:]]+/etc/mosquitto/conf\.d([[:space:]]|$)' /etc/mosquitto/mosquitto.conf; then
    printf '\ninclude_dir /etc/mosquitto/conf.d\n' >> /etc/mosquitto/mosquitto.conf
fi

# Validate config before restarting the service.
mosquitto -c /etc/mosquitto/mosquitto.conf -t
systemctl enable mosquitto >/dev/null 2>&1 || true
systemctl restart mosquitto

log "Lokalen MQTT-Broker testen"
TMP_SUB="$(mktemp)"
timeout 5 mosquitto_sub -h 127.0.0.1 -p 1883 -t 'phnix-lab/selftest' -C 1 > "$TMP_SUB" &
SUB_PID=$!
sleep 0.3
mosquitto_pub -h 127.0.0.1 -p 1883 -t 'phnix-lab/selftest' -m 'ok'
wait "$SUB_PID"
if ! grep -qx 'ok' "$TMP_SUB"; then
    rm -f "$TMP_SUB"
    die "MQTT-Selbsttest fehlgeschlagen."
fi
rm -f "$TMP_SUB"

log "Hilfsscript phnix-lab-info installieren"
cat > /usr/local/bin/phnix-lab-info <<'EOF'
#!/usr/bin/env bash
set -u
printf '=== PHNIX OTA Lab ===\n'
printf 'Host: '; grep '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '"'
printf 'QEMU: '; qemu-arm-static --version 2>/dev/null | head -n1 || true
printf 'qemu-arm binfmt: '
if command -v update-binfmts >/dev/null 2>&1 && update-binfmts --display qemu-arm 2>/dev/null | grep -q 'enabled'; then
    echo enabled
else
    echo unknown/disabled
fi
printf 'Mosquitto: '
if systemctl is-active --quiet mosquitto; then
    echo 'active (127.0.0.1:1883)'
else
    echo inactive
fi
printf 'Lab root: /opt/phnix-lab\n'
printf '\nDirectories:\n'
find /opt/phnix-lab -maxdepth 2 -type d -printf '  %p\n' 2>/dev/null | sort
EOF
chmod 0755 /usr/local/bin/phnix-lab-info

# If invoked through sudo, allow the normal admin user to work in the lab tree.
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    LAB_GROUP="$(id -gn "$SUDO_USER")"
    chown -R "$SUDO_USER:$LAB_GROUP" "$LAB_ROOT"
fi

log "Installation abgeschlossen"
phnix-lab-info

cat <<'EOF'

Naechster Schritt:
  1. SIM7600-Dateien noch NICHT wahllos kopieren.
  2. Zuerst die Runtime-Abhaengigkeiten von phnixIot4G sichern.
  3. Danach unter /opt/phnix-lab/rootfs/ ablegen.
  4. Anschliessend testen wir qemu-arm-static, Libraries und /dev/ttyHSL2 per PTY.

Wichtig:
  - Der MQTT-Broker lauscht nur auf 127.0.0.1:1883.
  - Dieses Script aendert Routing/Firewall nicht.
  - Fuer ein komplett isoliertes Lab Internetzugriff in Proxmox sperren bzw. eine
    Bridge ohne Gateway/physische Uplink-Schnittstelle verwenden.
  - Keine DeviceSecrets, IMEI oder Firmwaredateien in das oeffentliche GitHub-Repo committen.
EOF
