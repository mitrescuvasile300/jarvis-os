FROM python:3.11-slim

WORKDIR /app

# Python dependencies only (no system packages needed)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY agent/ ./agent/
COPY config/ ./config/
COPY skills/ ./skills/
COPY skills-community/ ./skills-community/
COPY scripts/ ./scripts/
COPY jarvis/ ./jarvis/
COPY dashboard/ ./dashboard/
COPY plugins/ ./plugins/
COPY pyproject.toml .

# Install jarvis package (non-editable in container)
RUN pip install --no-cache-dir .

# Create data directories + entrypoint
RUN mkdir -p /app/data /app/knowledge /app/settings /app/logs
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -m jarvis.healthcheck

# Run as root so bind mounts work regardless of host UID
# (entrypoint creates dirs + loads settings + starts server)
CMD ["/app/entrypoint.sh"]
