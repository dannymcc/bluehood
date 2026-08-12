#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Bluehood – macOS Install / Uninstall / Reset
# Installs dependencies into a virtual environment and registers
# a launchd agent so bluehood starts automatically on login.
#
# Usage:
#   ./install.sh [install]            Install (or upgrade) and auto-start.
#   ./install.sh uninstall [--purge]  Stop and remove the agent + venv.
#                                     --purge also deletes data and logs.
#   ./install.sh reset [--purge]      Uninstall, then reinstall and run.
#                                     --purge wipes data for a clean reset.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
step()  { printf "\n${CYAN}── %s${NC}\n" "$*"; }

usage() {
    cat <<'USAGE'
Bluehood – macOS Install / Uninstall / Reset

Usage:
  ./install.sh [install]            Install (or upgrade) and auto-start.
  ./install.sh uninstall [--purge]  Stop and remove the agent + venv.
                                    --purge also deletes data and logs.
  ./install.sh reset [--purge]      Uninstall, then reinstall and run.
                                    --purge wipes data for a clean reset.
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${HOME}/.local/share/bluehood"
VENV_DIR="${DATA_DIR}/venv"     # Must NOT be under ~/Documents, ~/Desktop, etc.
                                 # macOS TCC blocks launchd access to those folders.
LOG_DIR="${HOME}/Library/Logs/bluehood"
PLIST_LABEL="com.bluehood.daemon"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

# ── Verify macOS ─────────────────────────────────────────────
if [[ "$(uname -s)" != "Darwin" ]]; then
    error "This script is for macOS only."
    exit 1
fi

# ── Helpers ──────────────────────────────────────────────────
# Resolve a usable python3 interpreter (>= 3.11).
find_python() {
    local candidate
    for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
        if command -v "${candidate}" &>/dev/null; then
            if "${candidate}" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)' &>/dev/null; then
                printf '%s' "${candidate}"
                return 0
            fi
        fi
    done
    return 1
}

# Stop and unload the launchd agent, then remove the plist.
remove_agent() {
    if launchctl list "${PLIST_LABEL}" &>/dev/null 2>&1; then
        info "Stopping launchd agent …"
        launchctl unload "${PLIST_PATH}" 2>/dev/null || true
    fi
    if [[ -f "${PLIST_PATH}" ]]; then
        rm -f "${PLIST_PATH}"
        info "Removed ${PLIST_PATH}"
    fi
}

# ── Uninstall ────────────────────────────────────────────────
do_uninstall() {
    local purge="${1:-false}"

    step "Uninstalling bluehood"
    remove_agent

    if [[ -d "${VENV_DIR}" ]]; then
        rm -rf "${VENV_DIR}"
        info "Removed venv ${VENV_DIR}"
    fi

    if [[ "${purge}" == "true" ]]; then
        [[ -d "${DATA_DIR}" ]] && rm -rf "${DATA_DIR}" && info "Purged data ${DATA_DIR}"
        [[ -d "${LOG_DIR}"  ]] && rm -rf "${LOG_DIR}"  && info "Purged logs ${LOG_DIR}"
    else
        info "Kept data (${DATA_DIR}) and logs (${LOG_DIR}). Use --purge to remove them."
    fi

    printf "\n${GREEN}✔ Bluehood has been uninstalled.${NC}\n"
}

# ── Install ──────────────────────────────────────────────────
do_install() {
    # ── Step 1: Check Python ────────────────────────────────
    step "1/5  Checking prerequisites"

    local python_bin
    if ! python_bin="$(find_python)"; then
        error "Python 3.11+ not found. Install with:  brew install python@3.12"
        exit 1
    fi
    info "Python $(${python_bin} -c 'import sys; print("%d.%d" % sys.version_info[:2])') (${python_bin}) ✓"
    info "macOS CoreBluetooth available (no extra drivers needed)."

    # ── Step 2: Create directories ───────────────────────────
    # Must happen before venv creation since VENV_DIR is inside DATA_DIR.
    step "2/5  Setting up directories"

    mkdir -p "${DATA_DIR}" "${LOG_DIR}"
    mkdir -p "$(dirname "${PLIST_PATH}")"
    info "Data:  ${DATA_DIR}"
    info "Venv:  ${VENV_DIR}"
    info "Logs:  ${LOG_DIR}"

    # ── Step 3: Create virtual environment ───────────────────
    step "3/5  Creating virtual environment"

    if [[ -d "${VENV_DIR}" ]]; then
        info "Existing venv found – upgrading …"
    else
        "${python_bin}" -m venv "${VENV_DIR}"
        info "Created ${VENV_DIR}"
    fi
    "${VENV_DIR}/bin/pip" install --upgrade pip --quiet

    # ── Step 4: Install bluehood ────────────────────────────
    step "4/5  Installing bluehood package"

    "${VENV_DIR}/bin/pip" install "${SCRIPT_DIR}" --quiet

    # ── Step 5: Install and load launchd agent ───────────────
    step "5/5  Configuring launchd auto-start"

    remove_agent  # unload + remove any previous version first

    cat > "${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>

    <!--
        Call the venv Python directly — no external bash wrapper needed.
        The daemon itself waits for the macOS Bluetooth controller to be
        ready before scanning, avoiding "adapter busy" errors at login.
    -->
    <key>ProgramArguments</key>
    <array>
        <string>${VENV_DIR}/bin/python</string>
        <string>-m</string>
        <string>bluehood.daemon</string>
    </array>

    <!-- WorkingDirectory deliberately set to DATA_DIR (not the
         project source dir) so launchd doesn't need TCC access to
         ~/Documents, ~/Desktop, etc. -->
    <key>WorkingDirectory</key>
    <string>${DATA_DIR}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>BLUEHOOD_DATA_DIR</key>
        <string>${DATA_DIR}</string>
        <key>PATH</key>
        <string>${VENV_DIR}/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>

    <!-- Start automatically on login -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Restart if the process exits with an error -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <!-- Allow more time between crash restarts so the adapter can settle -->
    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/bluehood.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/bluehood.stderr.log</string>

    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
PLIST

    launchctl load -w "${PLIST_PATH}"
    info "launchd agent loaded and enabled."

    # ── Verify ───────────────────────────────────────────────
    # The launcher waits for Bluetooth, so give it extra time
    info "Waiting for launcher to confirm Bluetooth readiness …"
    sleep 8

    if launchctl list "${PLIST_LABEL}" &>/dev/null 2>&1; then
        local pid
        pid=$(launchctl list "${PLIST_LABEL}" 2>/dev/null | awk 'NR==1{print $1}')
        if [[ "${pid}" != "-" && -n "${pid}" ]]; then
            printf "\n${GREEN}✔ Bluehood is running (PID ${pid})!${NC}\n"
            info "Dashboard: http://localhost:8080"
        else
            printf "\n${GREEN}✔ Bluehood agent is registered.${NC}\n"
            info "The launcher is waiting for Bluetooth – check logs for status."
        fi
    else
        warn "Service may not have started – check logs:"
        warn "  tail -f ${LOG_DIR}/bluehood.stderr.log"
    fi

    cat <<EOF

────────────────────────────────────────────
  Bluehood is installed and will auto-start
  every time you log in.

  Commands:
    launchctl stop  ${PLIST_LABEL}
    launchctl start ${PLIST_LABEL}
    launchctl list  ${PLIST_LABEL}
    tail -f ${LOG_DIR}/bluehood.stderr.log

  Uninstall:           ./install.sh uninstall
  Uninstall + wipe:    ./install.sh uninstall --purge
  Reset / reinstall:   ./install.sh reset

  Data:  ${DATA_DIR}
  Logs:  ${LOG_DIR}
────────────────────────────────────────────
EOF
}

# ── Argument parsing ─────────────────────────────────────────
COMMAND="install"
PURGE="false"
for arg in "$@"; do
    case "${arg}" in
        install|uninstall|reset) COMMAND="${arg}" ;;
        --purge)                 PURGE="true" ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "Unknown argument: ${arg} (use --help)"
            exit 1
            ;;
    esac
done

case "${COMMAND}" in
    install)
        do_install
        ;;
    uninstall)
        do_uninstall "${PURGE}"
        ;;
    reset)
        do_uninstall "${PURGE}"
        do_install
        ;;
esac
