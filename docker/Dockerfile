# ═══════════════════════════════════════════════════════════
# Jarvis OS — App Image (fast rebuild, code only)
#
# Uses jarvis-base for heavy deps (apt-get, pip, Chromium).
# This layer only copies code — rebuilds in ~5 seconds.
#
# First time:  docker build -f docker/Dockerfile.base -t jarvis-base .
# Then:        docker compose up -d --build
# ═══════════════════════════════════════════════════════════

FROM jarvis-base:latest

WORKDIR /app

# Copy application code only (deps are in base image)
COPY agent/ ./agent/
COPY config/ ./config/
COPY skills/ ./skills/
COPY skills-community/ ./skills-community/
COPY scripts/ ./scripts/
COPY jarvis/ ./jarvis/
COPY dashboard/ ./dashboard/
COPY plugins/ ./plugins/
COPY pyproject.toml .

# Install jarvis package
RUN pip install --no-cache-dir .

# Entrypoint
RUN mkdir -p /app/data /app/knowledge /app/settings /app/logs
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -m jarvis.healthcheck

CMD ["/app/entrypoint.sh"]
