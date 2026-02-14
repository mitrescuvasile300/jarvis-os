FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY agent/ ./agent/
COPY config/ ./config/
COPY skills/ ./skills/
COPY scripts/ ./scripts/
COPY jarvis/ ./jarvis/

# Create data directories
RUN mkdir -p /app/data /app/memory /app/logs

# Non-root user
RUN useradd -m -r jarvis && chown -R jarvis:jarvis /app
USER jarvis

EXPOSE 8080

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -m jarvis.healthcheck

CMD ["python", "-m", "jarvis.server"]
