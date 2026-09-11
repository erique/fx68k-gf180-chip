# Same host as .github/workflows/ci.yml: Ubuntu 24.04 + Determinate Nix + fossi cache.
# Runtime matches CI: nix develop --command make …
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG UBUNTU_MIRROR=http://mirrors.kernel.org/ubuntu

RUN set -eu; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/ubuntu.sources; do \
        if [ -f "$f" ]; then \
            sed -i \
                -e "s|http://archive.ubuntu.com/ubuntu|${UBUNTU_MIRROR}|g" \
                -e "s|http://security.ubuntu.com/ubuntu|${UBUNTU_MIRROR}|g" \
                "$f"; \
        fi; \
    done \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        make \
        python3 \
        sudo \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Same installer extra-conf as .github/actions/setup_nix/action.yml (no systemd in the image).
RUN curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix \
        | sh -s -- install linux \
            --init none \
            --no-confirm \
            --extra-conf 'extra-substituters = https://nix-cache.fossi-foundation.org' \
            --extra-conf 'extra-trusted-public-keys = nix-cache.fossi-foundation.org:3+K59iFwXqKsL7BNu6Guy0v+uTlwsxYQxjspXzqLYQs=' \
            --extra-conf 'extra-experimental-features = nix-command flakes'

ENV PATH=/nix/var/nix/profiles/default/bin:/root/.nix-profile/bin:${PATH}
ENV USER=root
# libgit2 (Nix flakes) rejects a host-owned /work when the container is root.
ENV GIT_CONFIG_COUNT=1
ENV GIT_CONFIG_KEY_0=safe.directory
ENV GIT_CONFIG_VALUE_0=*

COPY docker/nix-env.sh /usr/local/bin/nix-env.sh
RUN chmod +x /usr/local/bin/nix-env.sh

WORKDIR /opt/flake
COPY flake.nix flake.lock /opt/flake/

# Same prefetch as .github/actions/build_nix/action.yml (current system, not a hard-coded x86_64).
RUN . /usr/local/bin/nix-env.sh \
    && nix develop --accept-flake-config --command bash -lc 'librelane --version && command -v yosys'

WORKDIR /work
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
