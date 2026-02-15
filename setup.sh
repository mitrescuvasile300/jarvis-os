#!/bin/bash
# Jarvis OS — First-time setup
# Run once. After this, rebuilds take ~5 seconds.

echo "🤖 Setting up Jarvis OS..."
echo ""

# 1. Create persistent directories
mkdir -p persistent/data persistent/knowledge persistent/settings persistent/uploads
echo "✅ Created persistent/ directories"

# 2. Create .env if missing
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || echo "# Jarvis OS Environment" > .env
    echo "✅ Created .env"
else
    echo "✓ .env already exists"
fi

# 3. Build base image (heavy deps — only needed once)
echo ""
echo "📦 Building base image (apt-get + pip + Chromium)..."
echo "   This takes 2-3 minutes the first time, then never again."
echo ""
docker build -f docker/Dockerfile.base -t jarvis-base .

echo ""
echo "✅ Base image built! From now on, rebuilds take ~5 seconds."
echo ""
echo "🚀 Start Jarvis:"
echo "   docker compose up -d --build"
echo ""
echo "🔄 After code changes:"
echo "   git pull && docker compose up -d --build"
echo ""
echo "Open http://localhost:8080"
