#!/usr/bin/env bash
# Interactive login on a runner without a screen. Starts a virtual screen you
# can watch and type into over VNC, then runs login.sh on it, so you log in
# yourself (including any CAPTCHA or SMS check) in the bot's real browser profile.
#
# Run it as the runner's OS user, in a terminal (the login command waits for ENTER):
#   bash /path/to/klein-lister/scripts/login-remote.sh [data-dir]
#
# VNC listens on localhost only, so reach it through an SSH tunnel:
#   ssh -L 5900:localhost:5900 <runner>      then open localhost:5900 in a VNC viewer
# or set KLEIN_LISTER_VNC_LISTEN to a private address such as the runner's Tailscale IP.
# Needs: sudo apt install xvfb x11vnc
set -euo pipefail
tool_dir="$(cd "$(dirname "$0")/.." && pwd)"
listen="${KLEIN_LISTER_VNC_LISTEN:-localhost}"
port="${KLEIN_LISTER_VNC_PORT:-5900}"

source "${tool_dir}/scripts/login-env.sh"  # asks for the account name before the screen starts

for cmd in Xvfb x11vnc; do
  command -v "$cmd" >/dev/null || { echo "$cmd not found: sudo apt install xvfb x11vnc" >&2; exit 1; }
done

workdir="$(mktemp -d)"
passfile="${workdir}/vnc-pass"
trap 'kill "${vnc_pid:-}" "${xvfb_pid:-}" 2>/dev/null || true; rm -rf "${workdir}"' EXIT
password="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 10)"
printf '%s\n' "${password}" > "${passfile}"
chmod 600 "${passfile}"

export DISPLAY=:99
Xvfb "${DISPLAY}" -screen 0 1440x900x24 &
xvfb_pid=$!
sleep 1
x11vnc -display "${DISPLAY}" -listen "${listen}" -rfbport "${port}" -passwdfile "${passfile}" -forever -quiet &
vnc_pid=$!

echo "Virtual screen is up. Connect a VNC viewer to ${listen}:${port} (password: ${password})."
echo "Log in to Kleinanzeigen in the Chromium window, then come back here and press ENTER."
bash "${tool_dir}/scripts/login.sh" "$@"
