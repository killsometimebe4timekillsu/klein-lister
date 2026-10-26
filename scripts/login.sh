#!/usr/bin/env bash
# One-time interactive login on the runner machine. Opens a visible browser that
# uses the same profile as the workflow, so you can solve CAPTCHA / SMS checks once.
# Run it as the same OS user the GitHub runner runs as.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${KLEINANZEIGEN_BOT_USERNAME:?export KLEINANZEIGEN_BOT_USERNAME first}"
: "${KLEINANZEIGEN_BOT_PASSWORD:?export KLEINANZEIGEN_BOT_PASSWORD first}"

bash scripts/install-bot.sh
python3 -c 'import sys; sys.path.insert(0, "scripts"); import sync; sync.render_config()'
# The login command needs a visible browser: drop the headless flag for this run.
sed -i.bak '/--headless/d' .runtime/config.yaml && rm -f .runtime/config.yaml.bak
cd .runtime && "${HOME}/.klein-lister/bin/kleinanzeigen-bot" --workspace-mode=portable --config=config.yaml login
