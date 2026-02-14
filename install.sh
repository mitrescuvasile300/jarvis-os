#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Jarvis OS — One-Line Installer
#
# Usage: curl -fsSL https://raw.githubusercontent.com/mitrescuvasile300/jarvis-os/main/install.sh | bash
# ═══════════════════════════════════════════════════════════════

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BLUE}⚡ Jarvis OS — Installer${NC}"
echo "═════════════════════════════════════════"
echo ""

# Step 1: Check Docker
echo -e "${YELLOW}[1/5]${NC} Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed.${NC}"
    echo ""
    echo "Install Docker first:"
    echo "  macOS:   brew install --cask docker"
    echo "  Linux:   curl -fsSL https://get.docker.com | sh"
    echo "  Windows: https://docs.docker.com/desktop/install/windows-install/"
    echo ""
    exit 1
fi
echo -e "  ${GREEN}✅ Docker $(docker --version | grep -oP '\d+\.\d+\.\d+')${NC}"

if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Install Docker Desktop for Compose support.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✅ Docker Compose available${NC}"

# Step 2: Clone
echo ""
echo -e "${YELLOW}[2/5]${NC} Downloading Jarvis OS..."
if [ -d "jarvis-os" ]; then
    echo "  Directory 'jarvis-os' already exists. Updating..."
    cd jarvis-os && git pull && cd ..
else
    git clone https://github.com/mitrescuvasile300/jarvis-os.git
fi
cd jarvis-os
echo -e "  ${GREEN}✅ Downloaded${NC}"

# Step 3: Configure
echo ""
echo -e "${YELLOW}[3/5]${NC} Configuring..."
if [ ! -f .env ]; then
    cp .env.example .env
fi

# Agent name
echo ""
read -p "  🤖 Agent name [Jarvis]: " AGENT_NAME
AGENT_NAME=${AGENT_NAME:-Jarvis}
sed -i.bak "s/AGENT_NAME=.*/AGENT_NAME=$AGENT_NAME/" .env 2>/dev/null || true

# LLM choice
echo ""
echo "  Which AI model do you want to use?"
echo ""
echo "    1) 🟢 OpenAI (GPT-4o)       — Best quality, needs API key (~\$0.01/message)"
echo "    2) 🟠 Anthropic (Claude)     — Great quality, needs API key (~\$0.01/message)"
echo "    3) 🟣 Ollama (Llama 3)       — FREE, runs locally on your computer"
echo ""
read -p "  Choice [1/2/3]: " LLM_CHOICE

case $LLM_CHOICE in
    1)
        echo ""
        read -p "  Enter your OpenAI API key (sk-...): " API_KEY
        sed -i.bak "s/LLM_PROVIDER=.*/LLM_PROVIDER=openai/" .env 2>/dev/null || true
        sed -i.bak "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$API_KEY/" .env 2>/dev/null || true
        echo -e "  ${GREEN}✅ OpenAI configured${NC}"
        ;;
    2)
        echo ""
        read -p "  Enter your Anthropic API key (sk-ant-...): " API_KEY
        sed -i.bak "s/LLM_PROVIDER=.*/LLM_PROVIDER=anthropic/" .env 2>/dev/null || true
        sed -i.bak "s/.*ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$API_KEY/" .env 2>/dev/null || true
        echo -e "  ${GREEN}✅ Anthropic configured${NC}"
        ;;
    3)
        sed -i.bak "s/LLM_PROVIDER=.*/LLM_PROVIDER=ollama/" .env 2>/dev/null || true
        echo -e "  ${GREEN}✅ Ollama configured (free, no API key needed)${NC}"
        OLLAMA=true
        ;;
    *)
        echo "  Using OpenAI (default)"
        ;;
esac

# Clean up .bak files from sed
rm -f .env.bak

echo -e "  ${GREEN}✅ Configuration saved${NC}"

# Step 4: Build & Start
echo ""
echo -e "${YELLOW}[4/5]${NC} Building & starting $AGENT_NAME..."
echo "  (This may take 1-2 minutes on first run)"
echo ""

if [ "$OLLAMA" = true ]; then
    docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build 2>&1 | while read line; do
        echo "  $line"
    done
    echo ""
    echo "  Downloading Llama 3 model (this may take a few minutes)..."
    docker exec jarvis-ollama ollama pull llama3 2>&1 | tail -5
else
    docker compose up -d --build 2>&1 | while read line; do
        echo "  $line"
    done
fi

echo -e "  ${GREEN}✅ Running${NC}"

# Step 5: Wait for health
echo ""
echo -e "${YELLOW}[5/5]${NC} Waiting for $AGENT_NAME to start..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
    echo -n "."
done
echo ""

if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    echo ""
    echo -e "${GREEN}═════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ $AGENT_NAME is ready!${NC}"
    echo -e "${GREEN}═════════════════════════════════════════${NC}"
    echo ""
    echo -e "  🌐 Dashboard:  ${BLUE}http://localhost:8080${NC}"
    echo -e "  💬 CLI Chat:   docker exec -it jarvis-agent jarvis chat"
    echo -e "  📊 Health:     curl http://localhost:8080/health"
    echo ""
    echo -e "  ${YELLOW}Stop:${NC}    docker compose down"
    echo -e "  ${YELLOW}Logs:${NC}    docker compose logs -f"
    echo -e "  ${YELLOW}Restart:${NC} docker compose restart"
    echo ""

    # Auto-open browser
    if command -v open &> /dev/null; then
        open http://localhost:8080
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8080
    fi
else
    echo -e "${YELLOW}⏳ $AGENT_NAME is still starting. Check: docker compose logs -f${NC}"
fi
