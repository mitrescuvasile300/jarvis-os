#!/bin/bash
# Jarvis OS Entrypoint — ensures persistent directories exist with correct permissions

# Create persistent dirs if they don't exist (bind mounts from host)
mkdir -p /app/data /app/knowledge /app/settings /app/data/uploads /app/logs

# Load saved settings into environment (API keys, model config)
if [ -f /app/settings/keys.env ]; then
    echo "[entrypoint] Loading saved settings from /app/settings/keys.env"
    set -a
    source /app/settings/keys.env
    set +a
fi

# Start Jarvis
exec python -m jarvis.server
