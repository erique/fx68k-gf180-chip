#!/bin/sh
# Load Nix and start the daemon if this image has no systemd (--init none).
# Sourced from /bin/sh (Docker RUN) and from bash (entrypoint).
# shellcheck disable=SC1091
if [ -f /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh ]; then
    . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
elif [ -f /root/.nix-profile/etc/profile.d/nix.sh ]; then
    . /root/.nix-profile/etc/profile.d/nix.sh
fi

if [ ! -S /nix/var/nix/daemon-socket/socket ]; then
    nix-daemon --daemon >/tmp/nix-daemon.log 2>&1 &
    while [ ! -S /nix/var/nix/daemon-socket/socket ]; do
        sleep 1
    done
fi
