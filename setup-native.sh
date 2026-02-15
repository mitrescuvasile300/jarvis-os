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
#   git pull && ./start.sh
# ═══════════════════════════════════════════════════════════════

set -e

echo "🤖 Jarvis OS — Native Setup"
echo "═══════════════════════════════"
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

# ── 5. Create persistent directories ─────────────────────
echo ""
echo "📁 Creating data directories..."
mkdir -p data knowledge settings data/uploads logs
echo "✅ Directories created"

# ── 6. Create .env if missing ────────────────────────────
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Jarvis OS — Environment Variables
# Add your API keys here or configure them in the Settings UI

# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# Server port (default 8080)
AGENT_PORT=8080
EOF
    echo "✅ Created .env (add your API keys there or use the Settings UI)"
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
if [ -f settings/keys.env ]; then
    set -a; source settings/keys.env; set +a
fi

# Ensure dirs exist
mkdir -p data knowledge settings data/uploads logs

echo "🤖 Starting Jarvis OS on port ${AGENT_PORT:-8080}..."
echo "   Dashboard: http://localhost:${AGENT_PORT:-8080}"
echo "   Press Ctrl+C to stop"
echo ""

exec python -m jarvis.server
STARTEOF
chmod +x start.sh

# ── 8. Create systemd service (optional) ─────────────────
JARVIS_DIR="$(pwd)"
JARVIS_USER="$(whoami)"

cat > jarvis-os.service << SVCEOF
# Jarvis OS — systemd service
# Install:  sudo cp jarvis-os.service /etc/systemd/system/
#           sudo systemctl daemon-reload
#           sudo systemctl enable --now jarvis-os
#
# Logs:     journalctl -u jarvis-os -f
# Restart:  sudo systemctl restart jarvis-os

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

[Install]
WantedBy=multi-user.target
SVCEOF

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ Setup complete!"
echo ""
echo "🚀 Start Jarvis:"
echo "   ./start.sh"
echo ""
echo "🔄 After code changes:"
echo "   git pull && ./start.sh"
echo ""
echo "🔧 Run as background service (auto-restart on reboot):"
echo "   sudo cp jarvis-os.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable --now jarvis-os"
echo "   journalctl -u jarvis-os -f    # view logs"
echo ""
echo "🌐 Dashboard: http://YOUR_VPS_IP:8080"
echo "═══════════════════════════════════════════════════════════"
