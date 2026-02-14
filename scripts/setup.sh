#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Jarvis OS — First-Time Setup Wizard
# ═══════════════════════════════════════════════════════════════

set -e

echo ""
echo "🤖 Jarvis OS — Setup Wizard"
echo "═══════════════════════════════════════════════"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install it:"
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker found: $(docker --version)"
echo ""

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📄 Created .env from template"
else
    echo "📄 .env already exists"
fi

# Ask for LLM provider
echo ""
echo "Which LLM provider do you want to use?"
echo "  1) OpenAI (GPT-4o) — requires API key"
echo "  2) Anthropic (Claude) — requires API key"
echo "  3) Ollama (local) — no API key, runs on your GPU"
echo ""
read -p "Choice [1/2/3]: " llm_choice

case $llm_choice in
    1)
        read -p "Enter your OpenAI API key: " api_key
        sed -i "s/LLM_PROVIDER=.*/LLM_PROVIDER=openai/" .env
        sed -i "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$api_key/" .env
        echo "✅ OpenAI configured"
        ;;
    2)
        read -p "Enter your Anthropic API key: " api_key
        sed -i "s/LLM_PROVIDER=.*/LLM_PROVIDER=anthropic/" .env
        sed -i "s/# ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$api_key/" .env
        echo "✅ Anthropic configured"
        ;;
    3)
        sed -i "s/LLM_PROVIDER=.*/LLM_PROVIDER=ollama/" .env
        echo "✅ Ollama configured (will use docker-compose.ollama.yml)"
        ;;
    *)
        echo "Using default (OpenAI)"
        ;;
esac

# Generate random API key for the agent
AGENT_KEY=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
sed -i "s/AGENT_API_KEY=.*/AGENT_API_KEY=$AGENT_KEY/" .env
echo ""
echo "🔑 Generated agent API key: $AGENT_KEY"

# Ask for agent name
echo ""
read -p "What should your agent be called? [Jarvis]: " agent_name
agent_name=${agent_name:-Jarvis}
sed -i "s/AGENT_NAME=.*/AGENT_NAME=$agent_name/" .env
echo "✅ Agent name: $agent_name"

# Build and start
echo ""
echo "═══════════════════════════════════════════════"
echo "🚀 Starting $agent_name..."
echo ""

if [ "$llm_choice" = "3" ]; then
    docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build
    echo ""
    echo "⏳ Pulling Ollama model (this may take a few minutes)..."
    docker exec jarvis-ollama ollama pull llama3
else
    docker compose up -d --build
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "✅ $agent_name is running!"
echo ""
echo "🌐 API:  http://localhost:8080"
echo "💬 Chat: docker exec -it jarvis-agent python -m jarvis.cli chat"
echo "📊 Status: curl http://localhost:8080/health"
echo ""
echo "To stop: docker compose down"
echo "To view logs: docker compose logs -f"
echo "═══════════════════════════════════════════════"
