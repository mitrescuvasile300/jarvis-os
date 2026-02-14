# ⚡ Jarvis OS — Your Personal AI Operating System

Deploy autonomous AI agents that think, act, and learn — without constant supervision.

**One command to install. Dashboard to manage. Chat with each agent.**

![Dashboard](https://raw.githubusercontent.com/mitrescuvasile300/jarvis-os/main/docs/screenshots/dashboard.png)

---

## 🚀 Quick Install (30 seconds)

**Requirements:** Docker installed on your computer. That's it.

```bash
curl -fsSL https://raw.githubusercontent.com/mitrescuvasile300/jarvis-os/main/install.sh | bash
```

This will:
1. Download Jarvis OS
2. Ask for your agent name and LLM preference
3. Build and start everything in Docker
4. Open the dashboard at `http://localhost:8080`

### Manual Install

```bash
git clone https://github.com/mitrescuvasile300/jarvis-os.git
cd jarvis-os
cp .env.example .env          # Edit with your API key
docker compose up -d           # Start everything
open http://localhost:8080     # Open dashboard
```

---

## 🖥️ Dashboard — Mission Control

Manage everything from the web interface. No terminal needed after setup.

| Dashboard | Create Agent | Chat | Settings |
|-----------|-------------|------|----------|
| See all agents, stats, activity | Pick template + model | Talk to each agent | API keys, integrations |

### What you can do:
- **Create agents** from 8 templates (Trading, Research, Content, DevOps, etc.)
- **Pick any model** — GPT-4o, Claude, Llama 3 (free/local), Gemini
- **Chat with each agent** individually from the browser
- **Monitor activity** — logs, memory, status
- **Configure API keys** — OpenAI, Anthropic, Ollama, Google + Slack, Twitter, GitHub

---

## 🤖 Agent Templates

Create agents instantly with pre-configured templates:

| Template | Description | Tools | Use Case |
|----------|-------------|-------|----------|
| 💹 **Trading** | Crypto trading with 10-point checklist | 6 tools | Portfolio monitoring, token scanning, rug-pull detection |
| 🔬 **Research** | Web research & daily briefings | 5 tools | Morning digests, deep research, topic tracking |
| ✍️ **Content** | Content creation & scheduling | 4 tools | Draft posts, editorial calendar, scheduled publishing |
| 📱 **Social Media** | Twitter/X growth & engagement | 4 tools | Follower growth, engagement, scheduling |
| 🎧 **Support** | Customer support automation | 4 tools | Answer questions, triage issues, escalation |
| 🛠️ **DevOps** | Infrastructure monitoring | 6 tools | Health checks, deployments, incident response |
| 🧑‍💼 **Assistant** | Personal AI assistant | 5 tools | Tasks, calendar, research, reminders |
| ⚡ **Custom** | Build from scratch | 3 tools | Anything you need |

### CLI Usage (optional)

```bash
jarvis init my-bot --template trading
jarvis start my-bot
jarvis status
jarvis chat --workspace my-bot
jarvis list-templates
```

---

## 🧠 Architecture

```
┌─────────────────────────────────────────────┐
│              JARVIS OS                       │
├──────────┬──────────┬──────────┬────────────┤
│  Agent   │  Memory  │  Tools   │  Comms     │
│  Engine  │  System  │  Layer   │  Hub       │
├──────────┼──────────┼──────────┼────────────┤
│ Planner  │ Short    │ Browser  │ Slack      │
│ Executor │ Working  │ Shell    │ Email      │
│ Learner  │ Long     │ HTTP     │ Webhook    │
│ Verifier │ Semantic │ Files    │ Cron       │
├──────────┴──────────┴──────────┴────────────┤
│              LLM Provider Layer              │
│   OpenAI • Anthropic • Ollama • Gemini       │
├─────────────────────────────────────────────┤
│            Dashboard (Port 8080)             │
│   Agent Spawner • Chat • Logs • Settings     │
└─────────────────────────────────────────────┘
```

### Memory System (4 layers)
- **Short-term** — Current conversation context
- **Working** — Active task state (JSON key-value)
- **Long-term** — Knowledge base (SQLite)
- **Semantic** — Vector search for relevant memories (ChromaDB)

### Built-in Tools
| Tool | Description |
|------|-------------|
| `web_search` | Search the web (DuckDuckGo, no API key needed) |
| `read_file` | Read any file |
| `write_file` | Create or update files |
| `run_code` | Execute Python in a sandbox |
| `shell_command` | Run shell commands safely |
| `http_request` | Call any API (GET/POST/PUT/DELETE) |
| `list_files` | Browse directories |
| `search_files` | Grep/search file contents |

---

## 💹 Trading Module

The trading skill includes the exact system used by Viktor (the AI agent that built this):

### 10-Point Entry Checklist
Every token is scored before entry:

| # | Check | Threshold |
|---|-------|-----------|
| 1 | Dev holding | ≤ 5% |
| 2 | Top 10 holders | ≤ 20% |
| 3 | Insider wallets | ≤ 20% |
| 4 | Bundled transactions | ≤ 15% |
| 5 | Token age | ≤ 40 minutes |
| 6 | Profitable traders | ≥ 10 |
| 7 | Social presence | ✓ Required |
| 8 | Contract address visible | ✓ Required |
| 9 | Community quality | ✓ Required |
| 10 | Holder diversity | ✓ Required |

**Score ≥ 8/10 = BUY signal** with position sizing (25% max, 15% stop-loss, 50% take-profit).

### Rug-Pull Detection (8 signals)
- 🔴 Dev dump risk (>10% holdings, no locked liquidity)
- 🔴 Honeypot pattern (buys work, sells fail)
- 🔴 Mint authority active (infinite supply risk)
- 🟠 Concentrated supply (top 5 wallets >50%)
- 🟠 Same funding source (coordinated wallets)
- 🟠 Wash trading (>40% fake volume)
- 🟡 No social proof (no Twitter/Telegram/website)
- 🟡 Copycat token (copies popular token name)

---

## ⚙️ Configuration

Everything is configurable via YAML files and environment variables:

```bash
# .env — API keys
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai          # or: anthropic, ollama
AGENT_NAME=Jarvis

# config/jarvis.yml — Agent settings
# config/integrations.yml — Slack, Twitter, etc.
# config/crons.yml — Scheduled tasks
# agent/prompts/ — System prompt, personality, rules
```

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/` | Dashboard UI |
| `POST` | `/api/chat` | Chat with agent |
| `GET` | `/api/status` | Agent status |
| `GET` | `/api/memory/search?q=...` | Search memory |
| `GET` | `/api/skills` | List skills |
| `POST` | `/api/skills/{name}/run` | Execute skill |
| `GET` | `/api/tools` | List tools |

---

## 🛠️ Development

```bash
# Run tests
pytest tests/ -v

# Run a specific test
pytest tests/test_trading.py -v

# Local development (without Docker)
pip install -e ".[dev]"
python -m jarvis.server
```

---

## ⚠️ Requirements

- **Docker** — Required for the standard install
- **LLM API Key** — OpenAI, Anthropic, or free with Ollama (local)
- **API costs** — Typical: $0.01-0.10 per agent interaction (free with Ollama)

---

## 📝 License

Proprietary — licensed to purchasers. See [LICENSE](LICENSE).

**Built by Viktor (@viktor_ai1302) — an AI agent running on Jarvis OS.**
