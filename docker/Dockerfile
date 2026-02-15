FROM python:3.11-slim

WORKDIR /app

# System deps for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium

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
