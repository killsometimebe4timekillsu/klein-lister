#!/usr/bin/env bash
# One-time interactive login on the runner machine. Opens a visible browser that
# uses the same profile as the workflow, so you can solve CAPTCHA / SMS checks once.
# Run it as the same OS user the GitHub runner runs as, from your data repo:
#   bash /path/to/klein-lister/scripts/login.sh [data-dir]
set -euo pipefail
tool_dir="$(cd "$(dirname "$0")/.." && pwd)"
data_dir="$(cd "${1:-.}" && pwd)"
[[ -f "${data_dir}/config.yaml" ]] || { echo "no config.yaml in ${data_dir}" >&2; exit 1; }

: "${KLEINANZEIGEN_BOT_USERNAME:?export KLEINANZEIGEN_BOT_USERNAME first}"
: "${KLEINANZEIGEN_BOT_PASSWORD:?export KLEINANZEIGEN_BOT_PASSWORD first}"

bash "${tool_dir}/scripts/install-bot.sh"
KLEIN_LISTER_DATA_DIR="${data_dir}" python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import sync; sync.render_config()' "${tool_dir}/scripts"
# The login command needs a visible browser: drop the headless flag for this run.
sed -i.bak '/--headless/d' "${data_dir}/.runtime/config.yaml" && rm -f "${data_dir}/.runtime/config.yaml.bak"
cd "${data_dir}/.runtime" && "${HOME}/.klein-lister/bin/kleinanzeigen-bot" --workspace-mode=portable --config=config.yaml login
