#!/bin/bash
# Jarvis OS - One-Line Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/mitrescuvasile300/jarvis-os/main/install.sh | bash
#   or:  bash install.sh

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

# --- Detect usable terminal ---
HAS_TTY=false
if [ -t 0 ]; then
  HAS_TTY=true
elif (echo "" > /dev/tty) 2>/dev/null; then
  HAS_TTY=true
fi

# --- Input helper: prompt with default ---
ask() {
  local prompt="$1"
  local default="$2"
  local REPLY=""

  if [ -t 0 ]; then
    read -p "$prompt" REPLY
  elif [ "$HAS_TTY" = true ]; then
    read -p "$prompt" REPLY < /dev/tty
  else
    printf "%s%s\n" "$prompt" "$default"
    REPLY="$default"
  fi

  [ -z "$REPLY" ] && [ -n "$default" ] && REPLY="$default"
  echo "$REPLY"
}

# --- Input helper: API key with asterisk feedback ---
ask_key() {
  local prompt="$1"
  local key=""
  local char=""

  printf "%s" "$prompt"

  # Non-interactive: read whole line from stdin
  if [ "$HAS_TTY" = false ] && ! [ -t 0 ]; then
    read -r key 2>/dev/null || true
    [ -n "$key" ] && printf '%*s' "${#key}" '' | tr ' ' '*'
    echo "" >&2
    echo "$key"
    return
  fi

  # Interactive: read char by char with asterisks
  while true; do
    if [ -t 0 ]; then
      IFS= read -rsn1 char
    else
      IFS= read -rsn1 char < /dev/tty
    fi

    # Enter
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

# --- Mask API key for display ---
mask_key() {
  local key="$1"
  local len=${#key}
  if [ $len -le 8 ]; then
    echo "********"
  else
    local mid=$((len - 9))
    local dots=""
    for i in $(seq 1 $mid); do dots="${dots}*"; done
    echo "${key:0:5}${dots}${key: -4}"
  fi
}

# =========================================
# Banner
# =========================================
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
echo -e "  ${DIM}------------------------------------------${NC}"
echo ""

# =========================================
# Step 1: Check Docker
# =========================================
echo -e "${CYAN}[1/5]${NC} ${BOLD}Checking requirements...${NC}"
echo ""

if ! command -v docker &> /dev/null; then
    echo -e "  ${RED}x Docker is not installed${NC}"
    echo ""
    echo "  Install Docker first:"
    echo -e "    macOS:   ${BOLD}brew install --cask docker${NC}"
    echo -e "    Linux:   ${BOLD}curl -fsSL https://get.docker.com | sh${NC}"
    echo -e "    Windows: ${BOLD}https://docs.docker.com/desktop/install/windows-install/${NC}"
    echo ""
    exit 1
fi

DOCKER_VER=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "?")
echo -e "  ${GREEN}ok${NC} Docker v${DOCKER_VER}"

if ! docker compose version &> /dev/null 2>&1; then
    echo -e "  ${RED}x Docker Compose not found${NC}"
    exit 1
fi
echo -e "  ${GREEN}ok${NC} Docker Compose"
echo ""

# =========================================
# Step 2: Download
# =========================================
echo -e "${CYAN}[2/5]${NC} ${BOLD}Downloading Jarvis OS...${NC}"
echo ""

if [ -d "jarvis-os" ]; then
    echo -e "  ${DIM}Directory exists, pulling latest...${NC}"
    cd jarvis-os && git pull --quiet 2>/dev/null || true && cd ..
else
    git clone --quiet https://github.com/mitrescuvasile300/jarvis-os.git 2>/dev/null || {
        echo -e "  ${RED}x Failed to download. Check your connection.${NC}"
        exit 1
    }
fi
cd jarvis-os

if [ ! -f .env ]; then
    cp .env.example .env
fi

echo -e "  ${GREEN}ok${NC} Downloaded"
echo ""

# =========================================
# Step 3: Configure
# =========================================
echo -e "${CYAN}[3/5]${NC} ${BOLD}Let's configure your agent${NC}"
echo ""

# --- 3a: Agent Name ---
echo -e "  ${BOLD}What should your AI agent be called?${NC}"
AGENT_NAME=$(ask "  Agent name [Jarvis]: " "Jarvis")
echo -e "  ${GREEN}ok${NC} Name: ${BOLD}${AGENT_NAME}${NC}"
echo ""

# --- 3b: Provider ---
echo -e "  ${BOLD}Choose your AI provider:${NC}"
echo ""
echo -e "    ${GREEN}1)${NC} ${BOLD}OpenAI${NC}           ${DIM}GPT-4o, GPT-4.1, o3, o4-mini${NC}"
echo -e "    ${GREEN}2)${NC} ${BOLD}Anthropic${NC}        ${DIM}Claude Sonnet 4, Claude Haiku${NC}"
echo -e "    ${GREEN}3)${NC} ${BOLD}Google${NC}           ${DIM}Gemini 2.5 Pro, Gemini 2.0 Flash${NC}"
echo -e "    ${GREEN}4)${NC} ${BOLD}Ollama (Local)${NC}   ${DIM}FREE - Llama 3, Mistral, DeepSeek${NC}"
echo ""
PROVIDER_CHOICE=$(ask "  Your choice [1]: " "1")
echo ""

OLLAMA=false

case $PROVIDER_CHOICE in
    1) LLM_PROVIDER="openai" ;;
    2) LLM_PROVIDER="anthropic" ;;
    3) LLM_PROVIDER="google" ;;
    4) LLM_PROVIDER="ollama"; OLLAMA=true ;;
    *) LLM_PROVIDER="openai" ;;
esac

# --- 3c: API Key ---
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
        echo -e "  ${YELLOW}! No key entered. Add it later in Dashboard > Settings.${NC}"
    else
        MASKED=$(mask_key "$API_KEY")
        echo -e "  ${GREEN}ok${NC} Key saved: ${DIM}${MASKED}${NC}"

        case $LLM_PROVIDER in
            openai)    sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${API_KEY}|" .env ;;
            anthropic) sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${API_KEY}|" .env ;;
            google)    sed -i "s|^GOOGLE_API_KEY=.*|GOOGLE_API_KEY=${API_KEY}|" .env ;;
        esac
    fi
    echo ""
else
    echo -e "  ${GREEN}ok${NC} Ollama is ${BOLD}free${NC} - no API key needed!"
    echo ""
fi

# --- 3d: Model Selection ---
echo -e "  ${BOLD}Choose your model:${NC}"
echo ""

case $LLM_PROVIDER in
    openai)
        echo -e "    ${DIM}--- GPT-5 Series (Latest) ---${NC}"
        echo -e "    ${GREEN} 1)${NC} ${BOLD}GPT-5.2${NC}             ${DIM}Latest and most capable${NC}"
        echo -e "    ${GREEN} 2)${NC} ${BOLD}GPT-5.2 Pro${NC}         ${DIM}Enhanced quality (higher cost)${NC}"
        echo -e "    ${GREEN} 3)${NC} ${BOLD}GPT-5.1${NC}             ${DIM}Previous gen, excellent quality${NC}"
        echo -e "    ${GREEN} 4)${NC} ${BOLD}GPT-5${NC}               ${DIM}Base GPT-5, great all-rounder${NC}"
        echo -e "    ${GREEN} 5)${NC} ${BOLD}GPT-5 Mini${NC}          ${DIM}Fast and affordable${NC}"
        echo -e "    ${GREEN} 6)${NC} ${BOLD}GPT-5 Nano${NC}          ${DIM}Fastest, lowest cost${NC}"
        echo -e "    ${DIM}--- Codex (Code-Optimized) ---${NC}"
        echo -e "    ${GREEN} 7)${NC} ${BOLD}GPT-5.2 Codex${NC}       ${DIM}Best for code generation${NC}"
        echo -e "    ${GREEN} 8)${NC} ${BOLD}GPT-5.1 Codex Max${NC}   ${DIM}Max context code model${NC}"
        echo -e "    ${DIM}--- Reasoning Models ---${NC}"
        echo -e "    ${GREEN} 9)${NC} ${BOLD}o4-mini${NC}             ${DIM}Latest reasoning, multimodal${NC}"
        echo -e "    ${GREEN}10)${NC} ${BOLD}o3-pro${NC}              ${DIM}Most powerful reasoning${NC}"
        echo -e "    ${GREEN}11)${NC} ${BOLD}o3${NC}                  ${DIM}Advanced reasoning${NC}"
        echo -e "    ${GREEN}12)${NC} ${BOLD}o3-mini${NC}             ${DIM}Reasoning, faster and cheaper${NC}"
        echo -e "    ${DIM}--- Previous Gen ---${NC}"
        echo -e "    ${GREEN}13)${NC} ${BOLD}GPT-4.1${NC}             ${DIM}Previous gen, still great${NC}"
        echo -e "    ${GREEN}14)${NC} ${BOLD}GPT-4o${NC}              ${DIM}Proven reliability${NC}"
        echo ""
        MODEL_CHOICE=$(ask "  Your choice [1]: " "1")
        case $MODEL_CHOICE in
            1) LLM_MODEL="gpt-5.2" ;;
            2) LLM_MODEL="gpt-5.2-pro" ;;
            3) LLM_MODEL="gpt-5.1" ;;
            4) LLM_MODEL="gpt-5" ;;
            5) LLM_MODEL="gpt-5-mini" ;;
            6) LLM_MODEL="gpt-5-nano" ;;
            7) LLM_MODEL="gpt-5.2-codex" ;;
            8) LLM_MODEL="gpt-5.1-codex-max" ;;
            9) LLM_MODEL="o4-mini" ;;
            10) LLM_MODEL="o3-pro" ;;
            11) LLM_MODEL="o3" ;;
            12) LLM_MODEL="o3-mini" ;;
            13) LLM_MODEL="gpt-4.1" ;;
            14) LLM_MODEL="gpt-4o" ;;
            *) LLM_MODEL="gpt-5.2" ;;
        esac
        ;;
    anthropic)
        echo -e "    ${DIM}--- Opus (Most Powerful) ---${NC}"
        echo -e "    ${GREEN}1)${NC} ${BOLD}Claude Opus 4.6${NC}     ${DIM}Latest, most capable (highest cost)${NC}"
        echo -e "    ${GREEN}2)${NC} ${BOLD}Claude Opus 4.5${NC}     ${DIM}Previous, excellent quality${NC}"
        echo -e "    ${DIM}--- Sonnet (Best Balance) ---${NC}"
        echo -e "    ${GREEN}3)${NC} ${BOLD}Claude Sonnet 4.5${NC}   ${DIM}Latest balanced model${NC}"
        echo -e "    ${GREEN}4)${NC} ${BOLD}Claude Sonnet 4${NC}     ${DIM}Previous gen, proven${NC}"
        echo -e "    ${DIM}--- Haiku (Fast & Cheap) ---${NC}"
        echo -e "    ${GREEN}5)${NC} ${BOLD}Claude Haiku 4.5${NC}    ${DIM}Fastest, great value${NC}"
        echo ""
        MODEL_CHOICE=$(ask "  Your choice [1]: " "1")
        case $MODEL_CHOICE in
            1) LLM_MODEL="claude-opus-4-6" ;;
            2) LLM_MODEL="claude-opus-4-5-20251101" ;;
            3) LLM_MODEL="claude-sonnet-4-5-20250929" ;;
            4) LLM_MODEL="claude-sonnet-4-20250514" ;;
            5) LLM_MODEL="claude-haiku-4-5-20251001" ;;
            *) LLM_MODEL="claude-opus-4-6" ;;
        esac
        ;;
    google)
        echo -e "    ${DIM}--- Gemini 3 (Latest) ---${NC}"
        echo -e "    ${GREEN}1)${NC} ${BOLD}Gemini 3 Pro${NC}        ${DIM}Latest, most capable${NC}"
        echo -e "    ${GREEN}2)${NC} ${BOLD}Gemini 3 Flash${NC}      ${DIM}Latest, fast and efficient${NC}"
        echo -e "    ${DIM}--- Gemini 2.5 ---${NC}"
        echo -e "    ${GREEN}3)${NC} ${BOLD}Gemini 2.5 Pro${NC}      ${DIM}Complex reasoning, proven${NC}"
        echo -e "    ${GREEN}4)${NC} ${BOLD}Gemini 2.5 Flash${NC}    ${DIM}Great value, reliable${NC}"
        echo -e "    ${GREEN}5)${NC} ${BOLD}Gemini 2.0 Flash${NC}    ${DIM}Previous gen, budget friendly${NC}"
        echo ""
        MODEL_CHOICE=$(ask "  Your choice [1]: " "1")
        case $MODEL_CHOICE in
            1) LLM_MODEL="gemini-3-pro" ;;
            2) LLM_MODEL="gemini-3-flash" ;;
            3) LLM_MODEL="gemini-2.5-pro" ;;
            4) LLM_MODEL="gemini-2.5-flash" ;;
            5) LLM_MODEL="gemini-2.0-flash" ;;
            *) LLM_MODEL="gemini-3-pro" ;;
        esac
        ;;
    ollama)
        echo -e "    ${GREEN}1)${NC} ${BOLD}Llama 3.1 8B${NC}       ${DIM}Best open-source, needs 8GB RAM${NC}"
        echo -e "    ${GREEN}2)${NC} ${BOLD}Llama 3.1 70B${NC}      ${DIM}Near GPT-4 quality, needs 48GB RAM${NC}"
        echo -e "    ${GREEN}3)${NC} ${BOLD}Mistral 7B${NC}          ${DIM}Fast, good for general tasks${NC}"
        echo -e "    ${GREEN}4)${NC} ${BOLD}DeepSeek Coder V2${NC}   ${DIM}Best for code generation${NC}"
        echo -e "    ${GREEN}5)${NC} ${BOLD}Phi-3 Mini${NC}          ${DIM}Smallest, runs on 4GB RAM${NC}"
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

# --- Write config ---
sed -i "s|^AGENT_NAME=.*|AGENT_NAME=${AGENT_NAME}|" .env 2>/dev/null || true
sed -i "s|^LLM_PROVIDER=.*|LLM_PROVIDER=${LLM_PROVIDER}|" .env 2>/dev/null || true

if grep -q "^LLM_MODEL=" .env 2>/dev/null; then
    sed -i "s|^LLM_MODEL=.*|LLM_MODEL=${LLM_MODEL}|" .env
else
    echo "LLM_MODEL=${LLM_MODEL}" >> .env
fi

echo -e "  ${GREEN}ok${NC} Configuration saved"
echo ""
echo "  +-------------------------------------------+"
printf "  |  Agent:    %-30s|\n" "$AGENT_NAME"
printf "  |  Provider: %-30s|\n" "$LLM_PROVIDER"
printf "  |  Model:    %-30s|\n" "$LLM_MODEL"
echo "  +-------------------------------------------+"
echo ""

# =========================================
# Step 4: Build & Start
# =========================================
echo -e "${CYAN}[4/5]${NC} ${BOLD}Building and starting ${AGENT_NAME}...${NC}"
echo -e "  ${DIM}This takes 1-2 minutes on first run.${NC}"
echo ""

if [ "$OLLAMA" = true ]; then
    docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build 2>&1 | \
        grep -E "Created|Started|Building|Pulling|done" | \
        while IFS= read -r line; do echo -e "  ${DIM}${line}${NC}"; done

    echo ""
    echo -e "  ${DIM}Downloading ${LLM_MODEL} model (one-time)...${NC}"
    docker exec jarvis-ollama ollama pull "$LLM_MODEL" 2>&1 | tail -5
else
    docker compose up -d --build 2>&1 | \
        grep -E "Created|Started|Building|Pulling|done" | \
        while IFS= read -r line; do echo -e "  ${DIM}${line}${NC}"; done
fi

echo ""
echo -e "  ${GREEN}ok${NC} Containers running"
echo ""

# =========================================
# Step 5: Wait for Health
# =========================================
echo -e "${CYAN}[5/5]${NC} ${BOLD}Starting ${AGENT_NAME}...${NC}"

HEALTHY=false
printf "  "
for i in $(seq 1 90); do
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    printf "."
    sleep 2
done
echo ""
echo ""

if [ "$HEALTHY" = true ]; then
    echo -e "${GREEN}"
    echo "  ================================================"
    echo "     ${AGENT_NAME} is ready!"
    echo "  ================================================"
    echo -e "${NC}"
    echo -e "  Dashboard:  ${BOLD}${BLUE}http://localhost:8080${NC}"
    echo ""
    echo -e "  ${DIM}Running on a VPS? Access from your computer:${NC}"
    echo -e "  ${BOLD}ssh -L 8080:localhost:8080 user@your-server-ip${NC}"
    echo -e "  ${DIM}Then open http://localhost:8080 in your browser${NC}"
    echo ""
    echo -e "  ${DIM}--------------------------------------------${NC}"
    echo -e "  Stop:     ${DIM}docker compose down${NC}"
    echo -e "  Logs:     ${DIM}docker compose logs -f${NC}"
    echo -e "  Restart:  ${DIM}docker compose restart${NC}"
    echo -e "  Update:   ${DIM}git pull && docker compose up -d --build${NC}"
    echo -e "  ${DIM}--------------------------------------------${NC}"
    echo ""

    # Auto-open browser (desktop only, silent fail on VPS)
    command -v open &>/dev/null && open http://localhost:8080 2>/dev/null || true
    command -v xdg-open &>/dev/null && xdg-open http://localhost:8080 2>/dev/null || true
else
    echo -e "  ${YELLOW}${AGENT_NAME} is still starting up.${NC}"
    echo -e "  ${DIM}Check progress: docker compose logs -f${NC}"
fi
