#!/usr/bin/env bash
# Downloads the kleinanzeigen-bot binary into ~/.klein-lister/bin (once per version).
set -euo pipefail

version="${KLEINANZEIGEN_BOT_VERSION:-latest}"
os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/')"
bin_dir="${HOME}/.klein-lister/bin"
bin="${bin_dir}/kleinanzeigen-bot-${version}"

mkdir -p "${bin_dir}"
# "latest" is a rolling release, so always refresh it; pinned versions are cached.
if [[ "${version}" == "latest" || ! -x "${bin}" ]]; then
  curl -fsSL "https://github.com/Second-Hand-Friends/kleinanzeigen-bot/releases/download/${version}/kleinanzeigen-bot-${os}-${arch}" -o "${bin}.tmp"
  chmod 755 "${bin}.tmp"
  mv "${bin}.tmp" "${bin}"
fi
ln -sf "${bin}" "${bin_dir}/kleinanzeigen-bot"
"${bin_dir}/kleinanzeigen-bot" version

if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "${bin_dir}" >> "${GITHUB_PATH}"
fi
