<p align="center">
  <img src="https://img.shields.io/badge/Jarvis_OS-v1.0-00ff88?style=for-the-badge&labelColor=0a0a0f" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge" />
</p>

<h1 align="center">🤖 Jarvis OS — Your Personal AI Operating System</h1>

<p align="center">
  <strong>Deploy your own autonomous AI agent in minutes. One command. Full control.</strong>
</p>

---

## What is Jarvis OS?

Jarvis OS is a **self-hosted AI agent framework** that gives you a personal AI assistant capable of:

- 🧠 **Persistent Memory** — Remembers conversations, decisions, preferences across sessions
- 🔧 **Tool Usage** — Browses the web, writes code, manages files, calls APIs
- ⚡ **Autonomous Execution** — Runs scheduled tasks, monitors data, acts on triggers
- 🔌 **Integrations** — Slack, Twitter/X, GitHub, email, and custom webhooks
- 📦 **Extensible Skills** — Add new capabilities via simple YAML+Python skills

Think of it as your own private AI coworker that runs 24/7 on your infrastructure.

---

## Quick Start

### Prerequisites

- Docker & Docker Compose installed
- An OpenAI API key (or Anthropic, or local LLM via Ollama)
- (Optional) Integration API keys for Slack, Twitter, etc.

### 1. Clone & Configure

```bash
git clone https://github.com/mitrescuvasile300/jarvis-os.git
cd jarvis-os
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# Required — at least one LLM provider
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
# or use local Ollama (no key needed)
LLM_PROVIDER=ollama

# Optional integrations
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
TWITTER_API_KEY=...
GITHUB_TOKEN=ghp_...
```

### 2. Launch

```bash
docker compose up -d
```

That's it. Jarvis is running.

### 3. Talk to Jarvis

**Via CLI:**
```bash
docker exec -it jarvis-agent python -m jarvis.cli chat
```

**Via Slack** (if configured):
Just DM your Jarvis bot.

**Via API:**
```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Jarvis, what can you do?"}'
```

---

## Architecture

```
jarvis-os/
├── agent/                    # Core agent engine
│   ├── core.py              # Main agent loop (perceive → think → act)
│   ├── prompts/             # System prompts & personality config
│   │   ├── system.md        # Base system prompt
│   │   ├── personality.yml  # Personality traits & style
│   │   └── rules.yml        # Safety rules & boundaries
│   ├── tools/               # Built-in tool implementations
│   │   ├── web_browse.py    # Web browsing & scraping
│   │   ├── code_exec.py     # Code execution (sandboxed)
│   │   ├── file_ops.py      # File read/write/search
│   │   ├── api_call.py      # Generic HTTP API calls
│   │   └── shell.py         # Shell command execution
│   └── memory/              # Memory subsystem
│       ├── store.py         # Memory store (SQLite + vector)
│       ├── short_term.py    # Conversation context
│       ├── long_term.py     # Persistent knowledge
│       └── semantic.py      # Semantic search & retrieval
├── skills/                   # Extensible skill modules
│   ├── trading/             # Crypto/trading automation
│   ├── research/            # Web research & analysis
│   ├── content/             # Content creation & social media
│   └── code/                # Code generation & review
├── config/
│   ├── jarvis.yml           # Main configuration
│   ├── integrations.yml     # Integration settings
│   └── crons.yml            # Scheduled tasks
├── scripts/                  # Utility scripts
│   ├── setup.sh             # First-time setup wizard
│   └── healthcheck.py       # Health monitoring
├── docker/
│   ├── Dockerfile           # Agent container
│   └── Dockerfile.ollama    # Local LLM container
├── docker-compose.yml        # Full stack orchestration
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
└── tests/                   # Test suite
    ├── test_agent.py        # Agent core tests
    ├── test_memory.py       # Memory system tests
    ├── test_tools.py        # Tool tests
    └── test_skills.py       # Skill tests
```

---

## Configuration

### `config/jarvis.yml` — Main Config

```yaml
agent:
  name: "Jarvis"
  version: "1.0"
  llm:
    provider: "openai"          # openai | anthropic | ollama
    model: "gpt-4o"             # or claude-sonnet-4-20250514, llama3, etc.
    temperature: 0.7
    max_tokens: 4096

memory:
  backend: "sqlite"             # sqlite | postgres
  vector_store: "chromadb"      # chromadb | pinecone
  retention_days: 365

server:
  host: "0.0.0.0"
  port: 8080
  api_key: ""                   # Set for production

skills:
  enabled:
    - trading
    - research
    - content
    - code
```

### `config/crons.yml` — Scheduled Tasks

```yaml
jobs:
  - name: "morning_briefing"
    schedule: "0 8 * * *"         # 8 AM daily
    skill: "research"
    action: "daily_briefing"
    params:
      topics: ["crypto", "AI", "tech"]

  - name: "portfolio_check"
    schedule: "*/30 * * * *"      # Every 30 min
    skill: "trading"
    action: "check_portfolio"

  - name: "tweet_scheduler"
    schedule: "0 10,14,18 * * *"  # 10AM, 2PM, 6PM
    skill: "content"
    action: "scheduled_post"
```

---

## Skills System

Skills are self-contained modules that extend Jarvis's capabilities. Each skill has:

```
skills/{skill-name}/
├── SKILL.yml          # Metadata, triggers, description
├── actions.py         # Python implementation
├── prompts/           # Skill-specific prompts
└── tests/             # Skill tests
```

### Example: Creating a Custom Skill

```yaml
# skills/my-skill/SKILL.yml
name: my-custom-skill
description: "Monitors HackerNews for AI articles"
version: "1.0"

triggers:
  - type: cron
    schedule: "0 */2 * * *"
  - type: command
    pattern: "check hackernews"

tools_required:
  - web_browse
  - file_ops
```

```python
# skills/my-skill/actions.py
from jarvis.skills import BaseSkill, action

class MySkill(BaseSkill):
    @action("check_hackernews")
    async def check(self, params: dict) -> str:
        html = await self.tools.web_browse("https://news.ycombinator.com")
        articles = self.parse_hn(html)
        ai_articles = [a for a in articles if "AI" in a["title"]]

        if ai_articles:
            summary = await self.llm.summarize(ai_articles)
            await self.notify(f"📰 {len(ai_articles)} AI articles found:\n{summary}")

        return f"Checked HN: {len(ai_articles)} relevant articles"
```

---

## Integrations

### Slack

1. Create a Slack App at [api.slack.com/apps](https://api.slack.com/apps)
2. Add Bot Token Scopes: `chat:write`, `im:history`, `im:write`, `app_mentions:read`
3. Enable Socket Mode and get an App-Level Token
4. Add tokens to `.env`

### Twitter/X

1. Create a Developer App at [developer.x.com](https://developer.x.com)
2. Get API Key, Secret, Access Token, Access Secret
3. Add to `.env`

### GitHub

1. Create a Personal Access Token at [github.com/settings/tokens](https://github.com/settings/tokens)
2. Scopes: `repo`, `workflow`
3. Add to `.env`

See `config/integrations.yml` for full configuration options.

---

## Memory System

Jarvis uses a 4-layer memory architecture:

| Layer | Purpose | Retention | Backend |
|-------|---------|-----------|---------|
| **Short-term** | Current conversation context | Session | In-memory |
| **Working** | Active task state & variables | Until task complete | SQLite |
| **Long-term** | Facts, decisions, preferences | Configurable (default 1yr) | SQLite |
| **Semantic** | Searchable knowledge base | Permanent | ChromaDB vectors |

Memory is automatically managed — important information is promoted from short-term to long-term based on relevance scoring.

---

## Testing

```bash
# Run all tests
docker exec -it jarvis-agent pytest tests/ -v

# Test specific component
docker exec -it jarvis-agent pytest tests/test_memory.py -v

# Test with coverage
docker exec -it jarvis-agent pytest tests/ --cov=jarvis --cov-report=html
```

---

## Updating

```bash
git pull origin main
docker compose down
docker compose build --no-cache
docker compose up -d
```

You keep all your data — memory, skills, and config persist in Docker volumes.

---

## FAQ

**Q: How much does it cost to run?**
A: The only cost is your LLM API usage. With GPT-4o, typical usage is $5-15/month. With Ollama (local), it's free.

**Q: Can I use a local LLM?**
A: Yes! Set `LLM_PROVIDER=ollama` in `.env`. The included `docker-compose.ollama.yml` runs Llama 3 locally.

**Q: Is my data private?**
A: 100%. Everything runs on your machine. No data leaves your infrastructure except LLM API calls.

**Q: Can I run multiple agents?**
A: Yes — duplicate the config with different names and ports. Each agent has its own memory.

---

## Support

- 📧 Email: support@jarvis-os.dev
- 💬 Discord: [discord.gg/jarvis-os](https://discord.gg/jarvis-os)
- 🐛 Issues: Use this repo's Issues tab

---

<p align="center">
  <strong>Built with ❤️ for builders who want AI that actually works.</strong>
</p>
