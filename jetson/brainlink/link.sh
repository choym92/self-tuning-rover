#!/bin/sh
# Keep local forwards from this container to the Mac mini's loopback: 8080 = llama-server (Gemma),
# 8093 = Supertonic (Kalman's voice).
# The rover is the SSH client, so the listener lives here and disappears with the connection; the
# mini's key line only allows this one forward (docs/preflight.md, 2026-11-07).
MINI="${MINI:?set MINI to the Mac mini address}"
while true; do
  ssh -N -i /keys/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes \
      -o UserKnownHostsFile=/keys/known_hosts -o StrictHostKeyChecking=yes \
      -o ExitOnForwardFailure=yes -o ServerAliveInterval=5 -o ServerAliveCountMax=3 -o ConnectTimeout=10 \
      -L 0.0.0.0:8080:127.0.0.1:8080 -L 0.0.0.0:8093:127.0.0.1:8093 "paul@${MINI}"
  echo "$(date -Iseconds) link down (exit $?), retrying in 3 s"
  sleep 3
done
