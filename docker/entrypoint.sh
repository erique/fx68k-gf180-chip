#!/usr/bin/env bash
# CI uses `nix develop --command make …` (not nix-shell / flake-compat).
set -euo pipefail

# shellcheck disable=SC1091
. /usr/local/bin/nix-env.sh

export USER="${USER:-root}"

# Mounted /work is owned by the host user; the image runs as root. libgit2
# refuses that unless the path is a git safe.directory (CI never hits this).
git config --global --add safe.directory '*'

cd /work

if [[ $# -eq 0 ]]; then
    exec nix develop --accept-flake-config
fi
exec nix develop --accept-flake-config --command "$@"
