#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Jarvis OS — One-Line Installer
#
# Usage: curl -fsSL https://raw.githubusercontent.com/mitrescuvasile300/jarvis-os/main/install.sh | bash
#   or:  bash install.sh
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

# ── Input helpers (work with curl | bash) ─────────────────────

ask() {
  local prompt="$1"
  local default="$2"
  local REPLY=""
  if [ -t 0 ]; then
    read -p "$prompt" REPLY
  elif [ -e /dev/tty ]; then
    read -p "$prompt" REPLY < /dev/tty
  else
    # Non-interactive (CI) — use default
    REPLY="$default"
  fi
  [ -z "$REPLY" ] && [ -n "$default" ] && REPLY="$default"
  echo "$REPLY"
}

# Read API key with asterisk feedback
ask_key() {
  local prompt="$1"
  local key=""
  local char=""

  printf "%s" "$prompt"

  while true; do
    if [ -t 0 ]; then
      IFS= read -rsn1 char
    elif [ -e /dev/tty ]; then
      IFS= read -rsn1 char < /dev/tty
    else
      break  # Non-interactive, skip key input
    fi

    # Enter pressed
    if [[ "$char" == "" ]]; then
      break
    fi

    # Backspace
    if [[ "$char" == $'\x7f' ]] || [[ "$char" == $'\b' ]]; then
      if [ -n "$key" ]; then
        key="${key%?}"
        printf '\b \b'
      fi
      continue
    fi

    key="${key}${char}"
    printf '*'
  done

  echo "" >&2
  echo "$key"
}

mask_key() {
  local key="$1"
  local len=${#key}
  if [ $len -le 8 ]; then
    echo "••••••••"
  else
    echo "${key:0:5}$( printf '•%.0s' $(seq 1 $((len - 9))) )${key: -4}"
  fi
}

clear 2>/dev/null || true
echo ""
echo -e "${BLUE}"
cat << 'LOGO'
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
LOGO
echo -e "${NC}"
echo -e "  ${BOLD}Your Personal AI Operating System${NC}"
echo -e "  ${DIM}─────────────────────────────────────────${NC}"
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

DOCKER_VER=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "?")
echo -e "  ${GREEN}✓${NC} Docker v${DOCKER_VER}"

if ! docker compose version &> /dev/null 2>&1; then
    echo -e "  ${RED}✗ Docker Compose not found${NC}"
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
    echo -e "  ${DIM}Directory exists, pulling latest...${NC}"
    cd jarvis-os && git pull --quiet 2>/dev/null || true && cd ..
else
    git clone --quiet https://github.com/mitrescuvasile300/jarvis-os.git 2>/dev/null || {
        echo -e "  ${RED}✗ Failed to download. Check your internet connection.${NC}"
        exit 1
    }
fi
cd jarvis-os

if [ ! -f .env ]; then
    cp .env.example .env
fi

echo -e "  ${GREEN}✓${NC} Downloaded"
echo ""

# ═══════════════════════════════════════════════
# Step 3: Configure
# ═══════════════════════════════════════════════
echo -e "${CYAN}[3/5]${NC} ${BOLD}Let's configure your agent${NC}"
echo ""

# ── 3a: Agent Name ──
echo -e "  ${BOLD}What should your AI agent be called?${NC}"
AGENT_NAME=$(ask "  Agent name [Jarvis]: " "Jarvis")
echo -e "  ${GREEN}✓${NC} Name: ${BOLD}${AGENT_NAME}${NC}"
echo ""

# ── 3b: Provider ──
echo -e "  ${BOLD}Choose your AI provider:${NC}"
echo ""
echo -e "    ${GREEN}1)${NC} 🟢 ${BOLD}OpenAI${NC}         ${DIM}— GPT-4o, GPT-4.1, o3, o4-mini${NC}"
echo -e "    ${GREEN}2)${NC} 🟠 ${BOLD}Anthropic${NC}      ${DIM}— Claude Sonnet 4, Claude Haiku${NC}"
echo -e "    ${GREEN}3)${NC} 🔵 ${BOLD}Google${NC}         ${DIM}— Gemini 2.5 Pro, Gemini 2.0 Flash${NC}"
echo -e "    ${GREEN}4)${NC} 🟣 ${BOLD}Ollama (Local)${NC} ${DIM}— FREE, Llama 3, Mistral, DeepSeek${NC}"
echo ""
PROVIDER_CHOICE=$(ask "  Your choice [1]: " "1")
echo ""

OLLAMA=false
LLM_PROVIDER=""
LLM_MODEL=""

case $PROVIDER_CHOICE in
    1) LLM_PROVIDER="openai" ;;
    2) LLM_PROVIDER="anthropic" ;;
    3) LLM_PROVIDER="google" ;;
    4) LLM_PROVIDER="ollama"; OLLAMA=true ;;
    *) LLM_PROVIDER="openai" ;;
esac

# ── 3c: API Key (if not Ollama) ──
if [ "$OLLAMA" = false ]; then
    case $LLM_PROVIDER in
        openai)
            echo -e "  ${BOLD}Enter your OpenAI API key${NC}"
            echo -e "  ${DIM}Get one at: https://platform.openai.com/api-keys${NC}"
            ;;
        anthropic)
            echo -e "  ${BOLD}Enter your Anthropic API key${NC}"
            echo -e "  ${DIM}Get one at: https://console.anthropic.com${NC}"
            ;;
        google)
            echo -e "  ${BOLD}Enter your Google AI API key${NC}"
            echo -e "  ${DIM}Get one at: https://aistudio.google.com/apikey${NC}"
            ;;
    esac
    echo ""
    API_KEY=$(ask_key "  API key: ")

    if [ -z "$API_KEY" ]; then
        echo -e "  ${YELLOW}⚠ No key entered. Add it later in the Dashboard → Settings.${NC}"
    else
        MASKED=$(mask_key "$API_KEY")
        echo -e "  ${GREEN}✓${NC} Key saved: ${DIM}${MASKED}${NC}"

        case $LLM_PROVIDER in
            openai)    sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${API_KEY}|" .env ;;
            anthropic) sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${API_KEY}|" .env ;;
            google)    sed -i "s|^GOOGLE_API_KEY=.*|GOOGLE_API_KEY=${API_KEY}|" .env ;;
        esac
    fi
    echo ""
else
    echo -e "  ${GREEN}✓${NC} Ollama is ${BOLD}free${NC} — no API key needed!"
    echo ""
fi

# ── 3d: Model Selection ──
echo -e "  ${BOLD}Choose your model:${NC}"
echo ""

case $LLM_PROVIDER in
    openai)
        echo -e "    ${GREEN}1)${NC} ${BOLD}GPT-4o${NC}              ${DIM}— Best overall, great for agents${NC}"
        echo -e "    ${GREEN}2)${NC} ${BOLD}GPT-4o Mini${NC}         ${DIM}— Fast & cheap, good quality${NC}"
        echo -e "    ${GREEN}3)${NC} ${BOLD}GPT-4.1${NC}             ${DIM}— Latest, best coding & instruction following${NC}"
        echo -e "    ${GREEN}4)${NC} ${BOLD}GPT-4.1 Mini${NC}        ${DIM}— Latest budget model, very capable${NC}"
        echo -e "    ${GREEN}5)${NC} ${BOLD}GPT-4.1 Nano${NC}        ${DIM}— Fastest, lowest cost${NC}"
        echo -e "    ${GREEN}6)${NC} ${BOLD}o3${NC}                  ${DIM}— Reasoning model, best for complex tasks${NC}"
        echo -e "    ${GREEN}7)${NC} ${BOLD}o3-mini${NC}             ${DIM}— Reasoning, faster & cheaper${NC}"
        echo -e "    ${GREEN}8)${NC} ${BOLD}o4-mini${NC}             ${DIM}— Latest reasoning, multimodal${NC}"
        echo ""
        MODEL_CHOICE=$(ask "  Your choice [1]: " "1")
        case $MODEL_CHOICE in
            1) LLM_MODEL="gpt-4o" ;;
            2) LLM_MODEL="gpt-4o-mini" ;;
            3) LLM_MODEL="gpt-4.1" ;;
            4) LLM_MODEL="gpt-4.1-mini" ;;
            5) LLM_MODEL="gpt-4.1-nano" ;;
            6) LLM_MODEL="o3" ;;
            7) LLM_MODEL="o3-mini" ;;
            8) LLM_MODEL="o4-mini" ;;
            *) LLM_MODEL="gpt-4o" ;;
        esac
        ;;
    anthropic)
        echo -e "    ${GREEN}1)${NC} ${BOLD}Claude Sonnet 4${NC}     ${DIM}— Best quality, great for agents${NC}"
        echo -e "    ${GREEN}2)${NC} ${BOLD}Claude 3.5 Haiku${NC}    ${DIM}— Fast & cheap, still very good${NC}"
        echo -e "    ${GREEN}3)${NC} ${BOLD}Claude 3.5 Sonnet${NC}   ${DIM}— Previous gen, proven reliability${NC}"
        echo ""
        MODEL_CHOICE=$(ask "  Your choice [1]: " "1")
        case $MODEL_CHOICE in
            1) LLM_MODEL="claude-sonnet-4-20250514" ;;
            2) LLM_MODEL="claude-3-5-haiku-20241022" ;;
            3) LLM_MODEL="claude-3-5-sonnet-20241022" ;;
            *) LLM_MODEL="claude-sonnet-4-20250514" ;;
        esac
        ;;
    google)
        echo -e "    ${GREEN}1)${NC} ${BOLD}Gemini 2.5 Pro${NC}      ${DIM}— Most capable, complex reasoning${NC}"
        echo -e "    ${GREEN}2)${NC} ${BOLD}Gemini 2.5 Flash${NC}    ${DIM}— Fast & efficient, great value${NC}"
        echo -e "    ${GREEN}3)${NC} ${BOLD}Gemini 2.0 Flash${NC}    ${DIM}— Previous gen, reliable & fast${NC}"
        echo ""
        MODEL_CHOICE=$(ask "  Your choice [1]: " "1")
        case $MODEL_CHOICE in
            1) LLM_MODEL="gemini-2.5-pro" ;;
            2) LLM_MODEL="gemini-2.5-flash" ;;
            3) LLM_MODEL="gemini-2.0-flash" ;;
            *) LLM_MODEL="gemini-2.5-pro" ;;
        esac
        ;;
    ollama)
        echo -e "    ${GREEN}1)${NC} ${BOLD}Llama 3.1 8B${NC}       ${DIM}— Best open-source, 8GB RAM${NC}"
        echo -e "    ${GREEN}2)${NC} ${BOLD}Llama 3.1 70B${NC}      ${DIM}— Near GPT-4 quality, 48GB RAM${NC}"
        echo -e "    ${GREEN}3)${NC} ${BOLD}Mistral 7B${NC}          ${DIM}— Fast, good for general tasks, 8GB RAM${NC}"
        echo -e "    ${GREEN}4)${NC} ${BOLD}DeepSeek Coder V2${NC}   ${DIM}— Best for code, 8GB RAM${NC}"
        echo -e "    ${GREEN}5)${NC} ${BOLD}Phi-3 Mini${NC}          ${DIM}— Smallest, runs on 4GB RAM${NC}"
        echo ""
        MODEL_CHOICE=$(ask "  Your choice [1]: " "1")
        case $MODEL_CHOICE in
            1) LLM_MODEL="llama3.1" ;;
            2) LLM_MODEL="llama3.1:70b" ;;
            3) LLM_MODEL="mistral" ;;
            4) LLM_MODEL="deepseek-coder-v2" ;;
            5) LLM_MODEL="phi3:mini" ;;
            *) LLM_MODEL="llama3.1" ;;
        esac
        ;;
esac

echo ""

# ── Write config ──
sed -i "s|^AGENT_NAME=.*|AGENT_NAME=${AGENT_NAME}|" .env 2>/dev/null || true
sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=${LLM_PROVIDER}|" .env 2>/dev/null || true

# Add model to .env if not present
if grep -q "^LLM_MODEL=" .env 2>/dev/null; then
    sed -i "s|^LLM_MODEL=.*|LLM_MODEL=${LLM_MODEL}|" .env
else
    echo "LLM_MODEL=${LLM_MODEL}" >> .env
fi

echo -e "  ${GREEN}✓${NC} Configuration saved"
echo ""
echo -e "  ┌─────────────────────────────────────────┐"
echo -e "  │  Agent:    ${BOLD}${AGENT_NAME}${NC}                           "
echo -e "  │  Provider: ${BOLD}${LLM_PROVIDER}${NC}                        "
echo -e "  │  Model:    ${BOLD}${LLM_MODEL}${NC}                           "
echo -e "  └─────────────────────────────────────────┘"
echo ""

# ═══════════════════════════════════════════════
# Step 4: Build & Start
# ═══════════════════════════════════════════════
echo -e "${CYAN}[4/5]${NC} ${BOLD}Building & starting ${AGENT_NAME}...${NC}"
echo -e "  ${DIM}This takes 1-2 minutes on first run.${NC}"
echo ""

if [ "$OLLAMA" = true ]; then
    docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build 2>&1 | grep -E "Created|Started|Building|Pulling|done" | while IFS= read -r line; do
        echo -e "  ${DIM}${line}${NC}"
    done

    echo ""
    echo -e "  ${DIM}Downloading ${LLM_MODEL} model (one-time download)...${NC}"
    docker exec jarvis-ollama ollama pull "$LLM_MODEL" 2>&1 | tail -5
else
    docker compose up -d --build 2>&1 | grep -E "Created|Started|Building|Pulling|done" | while IFS= read -r line; do
        echo -e "  ${DIM}${line}${NC}"
    done
fi

echo ""
echo -e "  ${GREEN}✓${NC} Containers running"
echo ""

# ═══════════════════════════════════════════════
# Step 5: Wait for Health
# ═══════════════════════════════════════════════
echo -e "${CYAN}[5/5]${NC} ${BOLD}Starting ${AGENT_NAME}...${NC}"

HEALTHY=false
printf "  "
for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    printf "█"
    sleep 1
done
echo ""
echo ""

if [ "$HEALTHY" = true ]; then
    echo -e "${GREEN}"
    echo "  ╔═════════════════════════════════════════╗"
    echo "  ║   ✅  ${AGENT_NAME} is ready!                   ║"
    echo "  ╚═════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  🌐 ${BOLD}Open Dashboard:${NC}  ${BLUE}http://localhost:8080${NC}"
    echo ""
    echo -e "  ${DIM}Running on a VPS? Access from your computer:${NC}"
    echo -e "  ${BOLD}ssh -L 8080:localhost:8080 user@your-server-ip${NC}"
    echo -e "  ${DIM}Then open${NC} ${BLUE}http://localhost:8080${NC} ${DIM}in your browser${NC}"
    echo ""
    echo -e "  ${DIM}────────────────────────────────────────${NC}"
    echo -e "  ${DIM}Stop:${NC}     docker compose down"
    echo -e "  ${DIM}Logs:${NC}     docker compose logs -f"
    echo -e "  ${DIM}Restart:${NC}  docker compose restart"
    echo -e "  ${DIM}Update:${NC}   git pull && docker compose up -d --build"
    echo -e "  ${DIM}────────────────────────────────────────${NC}"
    echo ""

    # Auto-open browser (desktop only)
    command -v open &>/dev/null && open http://localhost:8080 2>/dev/null || true
    command -v xdg-open &>/dev/null && xdg-open http://localhost:8080 2>/dev/null || true
else
    echo -e "  ${YELLOW}⏳ ${AGENT_NAME} is still starting up.${NC}"
    echo -e "  ${DIM}Check progress: docker compose logs -f${NC}"
fi
