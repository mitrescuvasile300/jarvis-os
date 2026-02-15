#!/bin/bash
# Jarvis OS Entrypoint

# Default workspace for Docker
export JARVIS_WORKSPACE="${JARVIS_WORKSPACE:-/app/workspace}"

# Create workspace dirs
mkdir -p "${JARVIS_WORKSPACE}/data" "${JARVIS_WORKSPACE}/knowledge" \
         "${JARVIS_WORKSPACE}/settings" "${JARVIS_WORKSPACE}/uploads" \
         "${JARVIS_WORKSPACE}/projects" "${JARVIS_WORKSPACE}/research" \
         "${JARVIS_WORKSPACE}/scripts" "${JARVIS_WORKSPACE}/logs" \
         "${JARVIS_WORKSPACE}/data/agents" "${JARVIS_WORKSPACE}/data/chroma"

# Load saved settings into environment (API keys, model config)
if [ -f "${JARVIS_WORKSPACE}/settings/keys.env" ]; then
    echo "[entrypoint] Loading saved settings from ${JARVIS_WORKSPACE}/settings/keys.env"
    set -a
    source "${JARVIS_WORKSPACE}/settings/keys.env"
    set +a
fi

# Start Jarvis
exec python -m jarvis.server
