#!/usr/bin/env bash
# Installs the kleinanzeigen-bot into ~/.klein-lister/bin (once per version): the prebuilt
# binary, or, on a CPU without AVX2, a source install (see below).
set -euo pipefail

version="${KLEINANZEIGEN_BOT_VERSION:-latest}"
os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/')"
bin_dir="${HOME}/.klein-lister/bin"
bin="${bin_dir}/kleinanzeigen-bot-${version}"

mkdir -p "${bin_dir}"

# The prebuilt Linux binaries contain AVX2 code and die with "Illegal instruction" on older
# CPUs (for example the Intel Celeron J4105). There the bot is run from its source instead.
# KLEINANZEIGEN_BOT_FROM_SOURCE: auto (default) = only without AVX2, 1 = always, 0 = never.
from_source="${KLEINANZEIGEN_BOT_FROM_SOURCE:-auto}"
if [[ "${from_source}" == "auto" ]]; then
  from_source=0
  if [[ "${os}" == "linux" && "${arch}" == "amd64" ]] && ! grep -qw avx2 /proc/cpuinfo; then
    from_source=1
    echo "This CPU has no AVX2, so the prebuilt bot cannot run on it: installing the bot from source."
  fi
fi

install_from_source() {
  local repo="https://github.com/Second-Hand-Friends/kleinanzeigen-bot.git"
  local ref="${version}" root="${HOME}/.klein-lister/source"
  case "${ref}" in
    latest) ref=release ;; # the two rolling release channels are branches upstream
    preview) ref=main ;;
  esac

  for tool in git python3; do
    command -v "${tool}" >/dev/null || { echo "::error::${tool} is missing on the runner"; exit 1; }
  done
  if ! python3 -c 'import sys; sys.exit(not (3, 12) <= sys.version_info[:2] < (3, 16))'; then
    echo "::error::The bot needs Python 3.12 to 3.15 for a source install, found: $(python3 --version)"
    exit 1
  fi

  # A branch or tag name resolves to a commit; anything else is taken as a commit id.
  local sha
  sha="$(git ls-remote "${repo}" "refs/heads/${ref}" "refs/tags/${ref}" | head -n 1 | cut -f1)"
  sha="${sha:-${ref}}"

  local dir="${root}/${ref//\//_}"
  if [[ -x "${dir}/.venv/bin/python" && "$(cat "${dir}/installed-commit" 2>/dev/null || true)" == "${sha}" ]]; then
    echo "Bot source ${sha:0:7} is already installed."
  else
    rm -rf "${dir}"
    mkdir -p "${dir}"
    git -C "${dir}" init -q
    git -C "${dir}" fetch -q --depth 1 "${repo}" "${sha}"
    git -C "${dir}" checkout -q FETCH_HEAD

    # PDM installs the locked dependencies and applies the nodriver patch the bot needs.
    if [[ ! -x "${root}/pdm/bin/pdm" ]]; then
      python3 -m venv "${root}/pdm" || {
        echo "::error::python3 -m venv failed, install the venv package (Debian/Ubuntu: sudo apt install python3-venv)"
        exit 1
      }
      "${root}/pdm/bin/pip" install -q pdm
    fi
    (
      cd "${dir}"
      export GIT_COMMIT_HASH="${sha:0:7}" PDM_CHECK_UPDATE=false
      "${root}/pdm/bin/pdm" install --prod --frozen-lockfile
    )
    echo "${sha}" > "${dir}/installed-commit"
  fi

  # Written next to the final name and moved in, because the name may be a symlink to a binary.
  printf '#!/usr/bin/env bash\nexec "%s/.venv/bin/python" -m kleinanzeigen_bot "$@"\n' "${dir}" > "${bin_dir}/kleinanzeigen-bot.tmp"
  chmod 755 "${bin_dir}/kleinanzeigen-bot.tmp"
  mv -f "${bin_dir}/kleinanzeigen-bot.tmp" "${bin_dir}/kleinanzeigen-bot"
}

if [[ "${from_source}" == "1" ]]; then
  install_from_source
else
  # "latest" is a rolling release, so always refresh it; pinned versions are cached.
  if [[ "${version}" == "latest" || ! -x "${bin}" ]]; then
    curl -fsSL "https://github.com/Second-Hand-Friends/kleinanzeigen-bot/releases/download/${version}/kleinanzeigen-bot-${os}-${arch}" -o "${bin}.tmp"
    chmod 755 "${bin}.tmp"
    mv "${bin}.tmp" "${bin}"
  fi
  ln -sf "${bin}" "${bin_dir}/kleinanzeigen-bot"
fi
"${bin_dir}/kleinanzeigen-bot" version

if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "${bin_dir}" >> "${GITHUB_PATH}"
fi
