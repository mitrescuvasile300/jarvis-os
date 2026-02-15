#!/bin/bash
# Jarvis OS — First-time setup
# Creates persistent directories and .env file

echo "🤖 Setting up Jarvis OS..."

# Create persistent data directories (bind-mounted into container)
mkdir -p persistent/data persistent/knowledge persistent/settings persistent/uploads
echo "✅ Created persistent/ directories"

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || echo "# Jarvis OS Environment" > .env
    echo "✅ Created .env (add your API keys here or set them from the UI)"
else
    echo "✓ .env already exists"
fi

echo ""
echo "🚀 Ready! Run:"
echo "   docker compose up -d --build"
echo ""
echo "Then open http://localhost:8080"
