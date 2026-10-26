# Sourced by login.sh and login-remote.sh, not run on its own.
# Asks for the account name instead of requiring an `export`, so nothing ends up in
# the shell history. The password is typed into the browser by the person; the bot
# only needs some value for the ${KLEINANZEIGEN_BOT_PASSWORD} placeholder in its config.
if [[ -z "${KLEINANZEIGEN_BOT_USERNAME:-}" ]]; then
  [[ -t 0 ]] || { echo "set KLEINANZEIGEN_BOT_USERNAME, or run this in a terminal to be asked for it" >&2; exit 1; }
  read -rp "Kleinanzeigen account (e-mail address): " KLEINANZEIGEN_BOT_USERNAME
  [[ -n "${KLEINANZEIGEN_BOT_USERNAME}" ]] || { echo "no account given" >&2; exit 1; }
fi
export KLEINANZEIGEN_BOT_USERNAME
export KLEINANZEIGEN_BOT_PASSWORD="${KLEINANZEIGEN_BOT_PASSWORD:-unused}"
