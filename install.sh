#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Jarvis OS — One-Line Installer
#
# Usage: curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash
#   or:  bash install.sh
#
# NOTE: All `read` uses /dev/tty so interactive input works
#       even when the script is piped via curl.
# ═══════════════════════════════════════════════════════════════

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Read from terminal (works even when piped via curl)
ask() {
  local prompt="$1"
  local default="$2"
  local REPLY=""

  if [ -t 0 ]; then
    # Running directly (not piped)
    read -p "$prompt" REPLY
  else
    # Running via curl | bash — read from /dev/tty
    read -p "$prompt" REPLY < /dev/tty
  fi

  if [ -z "$REPLY" ] && [ -n "$default" ]; then
    REPLY="$default"
  fi

  echo "$REPLY"
}

# Read password (hidden input)
ask_secret() {
  local prompt="$1"
  local REPLY=""

  if [ -t 0 ]; then
    read -s -p "$prompt" REPLY
  else
    read -s -p "$prompt" REPLY < /dev/tty
  fi

  echo "$REPLY"
}

clear
echo ""
echo -e "${BLUE}"
echo "     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗"
echo "     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝"
echo "     ██║███████║██████╔╝██║   ██║██║███████╗"
echo "██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║"
echo "╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║"
echo " ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "${BOLD}  Your Personal AI Operating System${NC}"
echo -e "${DIM}  ─────────────────────────────────────────${NC}"
echo ""

# ═══════════════════════════════════════════════
# Step 1: Check Docker
# ═══════════════════════════════════════════════
echo -e "${CYAN}[1/5]${NC} ${BOLD}Checking requirements...${NC}"
echo ""

if ! command -v docker &> /dev/null; then
    echo -e "  ${RED}✗ Docker is not installed${NC}"
    echo ""
    echo "  Install Docker first:"
    echo -e "    macOS:   ${BOLD}brew install --cask docker${NC}"
    echo -e "    Linux:   ${BOLD}curl -fsSL https://get.docker.com | sh${NC}"
    echo -e "    Windows: ${BOLD}https://docs.docker.com/desktop/install/windows-install/${NC}"
    echo ""
    exit 1
fi

DOCKER_VERSION=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "unknown")
echo -e "  ${GREEN}✓${NC} Docker ${DIM}v${DOCKER_VERSION}${NC}"

if ! docker compose version &> /dev/null 2>&1; then
    echo -e "  ${RED}✗ Docker Compose not found${NC}"
    echo "  Install Docker Desktop which includes Compose."
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Docker Compose"
echo ""

# ═══════════════════════════════════════════════
# Step 2: Download
# ═══════════════════════════════════════════════
echo -e "${CYAN}[2/5]${NC} ${BOLD}Downloading Jarvis OS...${NC}"
echo ""

if [ -d "jarvis-os" ]; then
    echo -e "  ${DIM}Directory exists, updating...${NC}"
    cd jarvis-os && git pull --quiet 2>/dev/null && cd ..
else
    git clone --quiet https://github.com/mitrescuvasile300/jarvis-os.git 2>/dev/null
fi
cd jarvis-os

echo -e "  ${GREEN}✓${NC} Downloaded"
echo ""

# ═══════════════════════════════════════════════
# Step 3: Configure
# ═══════════════════════════════════════════════
echo -e "${CYAN}[3/5]${NC} ${BOLD}Let's set up your agent${NC}"
echo ""

if [ ! -f .env ]; then
    cp .env.example .env
fi

# ── Agent Name ──
echo -e "  ${BOLD}What should your AI agent be called?${NC}"
echo -e "  ${DIM}This is the name it uses when talking to you.${NC}"
echo ""
AGENT_NAME=$(ask "  Agent name [Jarvis]: " "Jarvis")
echo ""
echo -e "  ${GREEN}✓${NC} Agent name: ${BOLD}${AGENT_NAME}${NC}"
echo ""

# ── LLM Provider ──
echo -e "  ${BOLD}Which AI model do you want to use?${NC}"
echo ""
echo -e "    ${GREEN}1)${NC} 🟢 ${BOLD}OpenAI GPT-4o${NC}          — Best quality ${DIM}(~\$0.01/msg, needs API key)${NC}"
echo -e "    ${GREEN}2)${NC} 🟢 ${BOLD}OpenAI GPT-4o Mini${NC}     — Fast & cheap ${DIM}(~\$0.001/msg, needs API key)${NC}"
echo -e "    ${GREEN}3)${NC} 🟠 ${BOLD}Anthropic Claude${NC}       — Excellent quality ${DIM}(~\$0.01/msg, needs API key)${NC}"
echo -e "    ${GREEN}4)${NC} 🟣 ${BOLD}Ollama Llama 3${NC}         — ${GREEN}FREE${NC}, runs locally ${DIM}(needs 8GB+ RAM)${NC}"
echo ""
LLM_CHOICE=$(ask "  Your choice [1]: " "1")
echo ""

OLLAMA=false
LLM_PROVIDER=""
LLM_MODEL=""

case $LLM_CHOICE in
    1)
        LLM_PROVIDER="openai"
        LLM_MODEL="gpt-4o"
        echo -e "  ${BOLD}Enter your OpenAI API key${NC}"
        echo -e "  ${DIM}Get one at: https://platform.openai.com/api-keys${NC}"
        echo ""
        API_KEY=$(ask_secret "  API key (sk-...): ")
        echo ""
        echo ""

        if [ -z "$API_KEY" ]; then
            echo -e "  ${YELLOW}⚠ No API key entered. You can add it later in Settings.${NC}"
        else
            sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${API_KEY}|" .env 2>/dev/null || true
            echo -e "  ${GREEN}✓${NC} OpenAI API key saved"
        fi
        ;;
    2)
        LLM_PROVIDER="openai"
        LLM_MODEL="gpt-4o-mini"
        echo -e "  ${BOLD}Enter your OpenAI API key${NC}"
        echo -e "  ${DIM}Get one at: https://platform.openai.com/api-keys${NC}"
        echo ""
        API_KEY=$(ask_secret "  API key (sk-...): ")
        echo ""
        echo ""

        if [ -z "$API_KEY" ]; then
            echo -e "  ${YELLOW}⚠ No API key entered. You can add it later in Settings.${NC}"
        else
            sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${API_KEY}|" .env 2>/dev/null || true
            echo -e "  ${GREEN}✓${NC} OpenAI API key saved"
        fi
        ;;
    3)
        LLM_PROVIDER="anthropic"
        LLM_MODEL="claude-sonnet-4-20250514"
        echo -e "  ${BOLD}Enter your Anthropic API key${NC}"
        echo -e "  ${DIM}Get one at: https://console.anthropic.com${NC}"
        echo ""
        API_KEY=$(ask_secret "  API key (sk-ant-...): ")
        echo ""
        echo ""

        if [ -z "$API_KEY" ]; then
            echo -e "  ${YELLOW}⚠ No API key entered. You can add it later in Settings.${NC}"
        else
            sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${API_KEY}|" .env 2>/dev/null || true
            echo -e "  ${GREEN}✓${NC} Anthropic API key saved"
        fi
        ;;
    4)
        LLM_PROVIDER="ollama"
        LLM_MODEL="llama3"
        OLLAMA=true
        echo -e "  ${GREEN}✓${NC} Ollama selected — ${BOLD}free, no API key needed!${NC}"
        ;;
    *)
        LLM_PROVIDER="openai"
        LLM_MODEL="gpt-4o"
        echo -e "  ${DIM}Invalid choice, using OpenAI GPT-4o as default${NC}"
        echo -e "  ${BOLD}Enter your OpenAI API key${NC}"
        echo ""
        API_KEY=$(ask_secret "  API key (sk-...): ")
        echo ""
        echo ""

        if [ -z "$API_KEY" ]; then
            echo -e "  ${YELLOW}⚠ No API key entered. You can add it later in Settings.${NC}"
        else
            sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${API_KEY}|" .env 2>/dev/null || true
            echo -e "  ${GREEN}✓${NC} OpenAI API key saved"
        fi
        ;;
esac

# Write config
sed -i "s|^AGENT_NAME=.*|AGENT_NAME=${AGENT_NAME}|" .env 2>/dev/null || true
sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=${LLM_PROVIDER}|" .env 2>/dev/null || true

echo ""
echo -e "  ${GREEN}✓${NC} Configuration saved"
echo ""
echo -e "  ${DIM}┌─────────────────────────────────────┐${NC}"
echo -e "  ${DIM}│${NC}  Agent:    ${BOLD}${AGENT_NAME}${NC}"
echo -e "  ${DIM}│${NC}  Model:    ${BOLD}${LLM_MODEL}${NC}"
echo -e "  ${DIM}│${NC}  Provider: ${BOLD}${LLM_PROVIDER}${NC}"
echo -e "  ${DIM}└─────────────────────────────────────┘${NC}"
echo ""

# ═══════════════════════════════════════════════
# Step 4: Build & Start
# ═══════════════════════════════════════════════
echo -e "${CYAN}[4/5]${NC} ${BOLD}Building & starting ${AGENT_NAME}...${NC}"
echo -e "  ${DIM}This takes 1-2 minutes on first run.${NC}"
echo ""

if [ "$OLLAMA" = true ]; then
    docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build 2>&1 | while IFS= read -r line; do
        # Filter out noise, show only important lines
        case "$line" in
            *"Created"*|*"Started"*|*"Building"*|*"Pulling"*)
                echo -e "  ${DIM}${line}${NC}"
                ;;
        esac
    done

    echo ""
    echo -e "  ${DIM}Downloading Llama 3 model (one-time, ~4GB)...${NC}"
    docker exec jarvis-ollama ollama pull llama3 2>&1 | tail -3
else
    docker compose up -d --build 2>&1 | while IFS= read -r line; do
        case "$line" in
            *"Created"*|*"Started"*|*"Building"*|*"Pulling"*)
                echo -e "  ${DIM}${line}${NC}"
                ;;
        esac
    done
fi

echo ""
echo -e "  ${GREEN}✓${NC} Containers running"
echo ""

# ═══════════════════════════════════════════════
# Step 5: Wait for Health
# ═══════════════════════════════════════════════
echo -e "${CYAN}[5/5]${NC} ${BOLD}Waiting for ${AGENT_NAME} to start...${NC}"
echo ""

HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    echo -n "."
    sleep 1
done
echo ""
echo ""

if [ "$HEALTHY" = true ]; then
    echo -e "${GREEN}"
    echo "  ═════════════════════════════════════════"
    echo "  ✅  ${AGENT_NAME} is ready!"
    echo "  ═════════════════════════════════════════"
    echo -e "${NC}"
    echo -e "  🌐 ${BOLD}Dashboard:${NC}  ${BLUE}http://localhost:8080${NC}"
    echo ""
    echo -e "  ${DIM}If running on a VPS, access from your computer with:${NC}"
    echo -e "  ${BOLD}ssh -L 8080:localhost:8080 root@your-server-ip${NC}"
    echo -e "  ${DIM}Then open http://localhost:8080 in your browser.${NC}"
    echo ""
    echo -e "  ${DIM}──────────────────────────────────────────${NC}"
    echo -e "  Stop:     ${DIM}docker compose down${NC}"
    echo -e "  Logs:     ${DIM}docker compose logs -f${NC}"
    echo -e "  Restart:  ${DIM}docker compose restart${NC}"
    echo -e "  Update:   ${DIM}git pull && docker compose up -d --build${NC}"
    echo -e "  ${DIM}──────────────────────────────────────────${NC}"
    echo ""

    # Auto-open browser (only works on desktop, not VPS)
    if command -v open &> /dev/null; then
        open http://localhost:8080 2>/dev/null || true
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8080 2>/dev/null || true
    fi
else
    echo -e "  ${YELLOW}⏳ ${AGENT_NAME} is still starting up.${NC}"
    echo -e "  ${DIM}Check progress: docker compose logs -f${NC}"
fi
