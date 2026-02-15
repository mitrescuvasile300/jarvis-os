#!/bin/bash
# Jarvis OS — Docker Setup
# For native setup, use: ./setup-native.sh

set -e

echo "🤖 Jarvis OS — Docker Setup"
echo "═══════════════════════════════"
echo ""

# Create workspace directory for Docker bind mount
mkdir -p persistent/workspace

# Build base image (heavy deps — only needed once)
if ! docker image inspect jarvis-base >/dev/null 2>&1; then
    echo "📦 Building base image (first time, ~2-5 min)..."
    docker build -f docker/Dockerfile.base -t jarvis-base .
    echo "✅ Base image built"
else
    echo "✓ Base image exists"
fi

# Create .env if missing
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
AGENT_PORT=8080
JARVIS_WORKSPACE=/app/workspace
EOF
    echo "✅ Created .env"
fi

echo ""
echo "🚀 Start:  docker compose up -d --build"
echo "📊 Logs:   docker compose logs -f"
echo "🌐 Open:   http://localhost:8080"
