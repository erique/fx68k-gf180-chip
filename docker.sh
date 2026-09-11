#!/usr/bin/env bash
# Ubuntu 24.04 + Nix. Same as CI: nix develop --command …
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
IMAGE="${IMAGE:-$(basename "$ROOT"):dev}"

usage() {
    cat <<EOF
Usage: $0 [build | command ...]

  ./docker.sh                      interactive nix develop
  ./docker.sh build                build the image only
  ./docker.sh make librelane       same as CI: nix develop --command make librelane
EOF
}

build_image() {
    extra=()
    if [[ -n "${UBUNTU_MIRROR:-}" ]]; then
        extra+=(--build-arg "UBUNTU_MIRROR=${UBUNTU_MIRROR}")
    fi
    docker build "${extra[@]}" -t "$IMAGE" "$ROOT"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ "${1:-}" == "build" ]]; then
    build_image
    exit 0
fi

# Always build so ./docker.sh is not the previous nix-shell image (Docker cache
# is a no-op when Dockerfile/entrypoint are unchanged).
build_image

run_opts=(--rm -e TERM -v "$ROOT":/work -w /work)
if [[ -t 0 && -t 1 ]]; then
    run_opts+=(-it)
fi

exec docker run "${run_opts[@]}" "$IMAGE" "$@"
