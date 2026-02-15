#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Jarvis OS — Native Setup (no Docker)
#
# Run once on a fresh Ubuntu/Debian VPS:
#   chmod +x setup-native.sh && ./setup-native.sh
#
# After setup, start with:
#   ./start.sh
#
# After code changes:
#   git pull && ./start.sh  (2 seconds)
# ═══════════════════════════════════════════════════════════════

set -e

WORKSPACE="/root/jarvis/workspace"

echo "🤖 Jarvis OS — Native Setup"
echo "═══════════════════════════════"
echo "  Repo:      $(pwd)"
echo "  Workspace: ${WORKSPACE}"
echo ""

# ── 1. System dependencies (Chromium for Playwright) ──────
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    fonts-liberation fonts-noto-color-emoji \
    curl git
echo "✅ System deps installed"

# ── 2. Python virtual environment ────────────────────────
echo ""
echo "🐍 Setting up Python venv..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Created .venv"
else
    echo "✓ .venv already exists"
fi

source .venv/bin/activate

# ── 3. Python dependencies ───────────────────────────────
echo ""
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install -e ".[dev]"
pip install playwright
echo "✅ Python packages installed"

# ── 4. Playwright browser ────────────────────────────────
echo ""
echo "🌐 Installing Chromium browser..."
playwright install chromium
echo "✅ Chromium installed"

# ── 5. Create workspace ──────────────────────────────────
echo ""
echo "📁 Creating workspace at ${WORKSPACE}..."
mkdir -p "${WORKSPACE}/knowledge"
mkdir -p "${WORKSPACE}/data/agents"
mkdir -p "${WORKSPACE}/data/chroma"
mkdir -p "${WORKSPACE}/settings"
mkdir -p "${WORKSPACE}/uploads"
mkdir -p "${WORKSPACE}/projects"
mkdir -p "${WORKSPACE}/research"
mkdir -p "${WORKSPACE}/scripts"
mkdir -p "${WORKSPACE}/logs"
echo "✅ Workspace created"

# ── 6. Create .env if missing ────────────────────────────
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Jarvis OS — Environment Variables
# Add your API keys here or configure them in the Settings UI

# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# Workspace (where Jarvis stores his data, separate from repo)
JARVIS_WORKSPACE=/root/jarvis/workspace

# Server port (default 8080)
AGENT_PORT=8080
EOF
    echo "✅ Created .env"
else
    echo "✓ .env already exists"
fi

# ── 7. Create start script ──────────────────────────────
cat > start.sh << 'STARTEOF'
#!/bin/bash
# Start Jarvis OS natively

cd "$(dirname "$0")"

# Activate venv
source .venv/bin/activate

# Load .env
if [ -f .env ]; then
    set -a; source .env; set +a
fi

# Load saved settings (API keys from the UI)
SETTINGS="${JARVIS_WORKSPACE:-/root/jarvis/workspace}/settings/keys.env"
if [ -f "$SETTINGS" ]; then
    set -a; source "$SETTINGS"; set +a
fi

echo "🤖 Starting Jarvis OS on port ${AGENT_PORT:-8080}..."
echo "   Dashboard:  http://localhost:${AGENT_PORT:-8080}"
echo "   Workspace:  ${JARVIS_WORKSPACE:-/root/jarvis/workspace}"
echo "   Press Ctrl+C to stop"
echo ""

exec python -m jarvis.server
STARTEOF
chmod +x start.sh

# ── 8. Create systemd service ────────────────────────────
JARVIS_DIR="$(pwd)"
JARVIS_USER="$(whoami)"

cat > jarvis-os.service << SVCEOF
[Unit]
Description=Jarvis OS — AI Operating System
After=network.target

[Service]
Type=simple
User=${JARVIS_USER}
WorkingDirectory=${JARVIS_DIR}
ExecStart=${JARVIS_DIR}/start.sh
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=JARVIS_WORKSPACE=${WORKSPACE}

[Install]
WantedBy=multi-user.target
SVCEOF

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ Setup complete!"
echo ""
echo "  Repo (code):       $(pwd)"
echo "  Workspace (data):  ${WORKSPACE}"
echo ""
echo "🚀 Start Jarvis:"
echo "   ./start.sh"
echo ""
echo "🔄 After code changes:"
echo "   git pull && ./start.sh    (2 seconds)"
echo ""
echo "🔧 Background service (auto-restart on reboot):"
echo "   sudo cp jarvis-os.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable --now jarvis-os"
echo "   journalctl -u jarvis-os -f"
echo ""
echo "🌐 Dashboard: http://YOUR_VPS_IP:8080"
echo "═══════════════════════════════════════════════════════════"
