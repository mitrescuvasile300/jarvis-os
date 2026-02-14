"""Jarvis init — create a new agent workspace from a template.

Usage:
    jarvis init my-agent --template trading
    jarvis init my-bot --template research
    jarvis init my-assistant --template personal-assistant
"""

import json
import os
import shutil
from pathlib import Path

# Available templates and their configurations
TEMPLATES = {
    "trading": {
        "description": "Autonomous crypto trading agent — portfolio monitoring, market scanning, trade execution",
        "personality": "Disciplined quantitative trader. Data-driven, risk-aware, never emotional. Reports with numbers, not opinions.",
        "model": "gpt-4o",
        "tools": ["web_search", "http_request", "run_code", "read_file", "write_file", "shell_command"],
        "skills": ["trading"],
        "triggers": {
            "cron": "*/5 * * * *",
            "slack": "direct_message",
        },
        "safety": {
            "max_spend_per_trade": 0.5,
            "require_approval": ["trades_over_1_sol"],
            "kill_switch": True,
        },
        "crons": [
            {"name": "market_scan", "schedule": "*/5 * * * *", "skill": "trading", "action": "scan_market", "params": {}},
            {"name": "portfolio_check", "schedule": "*/30 * * * *", "skill": "trading", "action": "check_portfolio", "params": {"alert_threshold": 5}},
        ],
        "extra_skills": {
            "trading": {
                "checklist": {
                    "min_score": 8,
                    "criteria": [
                        {"name": "dev_holding", "max_pct": 5, "weight": 1},
                        {"name": "top10_holders", "max_pct": 20, "weight": 1},
                        {"name": "insider_pct", "max_pct": 20, "weight": 1},
                        {"name": "bundler_pct", "max_pct": 15, "weight": 1},
                        {"name": "token_age_minutes", "max_value": 40, "weight": 1},
                        {"name": "min_profit_traders", "min_value": 10, "weight": 1},
                        {"name": "social_presence", "required": True, "weight": 1},
                        {"name": "contract_address_visible", "required": True, "weight": 1},
                        {"name": "community_quality", "min_members": 50, "weight": 1},
                        {"name": "holder_diversity", "required": True, "weight": 1},
                    ],
                },
                "risk_management": {
                    "max_position_pct": 25,
                    "stop_loss_pct": 15,
                    "take_profit_pct": 50,
                    "max_concurrent_positions": 3,
                },
                "platforms": ["pump_fun", "raydium", "jupiter"],
            },
        },
    },
    "research": {
        "description": "Web research and analysis agent — daily briefings, deep dives, topic monitoring",
        "personality": "Thorough researcher. Verifies facts from multiple sources. Presents findings clearly with citations.",
        "model": "gpt-4o",
        "tools": ["web_search", "http_request", "read_file", "write_file", "run_code"],
        "skills": ["research"],
        "triggers": {
            "cron": "0 8 * * *",
            "slack": "direct_message",
        },
        "safety": {
            "max_spend_per_trade": 0,
            "require_approval": [],
            "kill_switch": False,
        },
        "crons": [
            {"name": "morning_briefing", "schedule": "0 8 * * *", "skill": "research", "action": "daily_briefing", "params": {"topics": ["AI", "crypto", "tech"]}},
        ],
    },
    "content": {
        "description": "Content creation and social media agent — drafts, scheduling, engagement",
        "personality": "Creative content strategist. Writes engaging, authentic posts. Adapts tone per platform.",
        "model": "gpt-4o",
        "tools": ["web_search", "http_request", "read_file", "write_file"],
        "skills": ["content"],
        "triggers": {
            "cron": "0 10,14,18 * * *",
            "slack": "direct_message",
        },
        "safety": {
            "max_spend_per_trade": 0,
            "require_approval": ["publish_post"],
            "kill_switch": False,
        },
        "crons": [
            {"name": "scheduled_post", "schedule": "0 10,14,18 * * *", "skill": "content", "action": "check_scheduled", "params": {"platforms": ["twitter"]}},
        ],
    },
    "social-media": {
        "description": "Social media management agent — Twitter/X automation, engagement, growth",
        "personality": "Social media expert. Engages authentically, grows followers organically. Never spammy.",
        "model": "gpt-4o",
        "tools": ["web_search", "http_request", "read_file", "write_file"],
        "skills": ["content"],
        "triggers": {
            "cron": "0 */2 * * *",
            "slack": "direct_message",
        },
        "safety": {
            "max_spend_per_trade": 0,
            "require_approval": [],
            "kill_switch": False,
        },
        "crons": [],
    },
    "support": {
        "description": "Customer support agent — answers questions, triages issues, escalates when needed",
        "personality": "Patient, empathetic support agent. Always helpful, never dismissive. Escalates complex issues.",
        "model": "gpt-4o",
        "tools": ["web_search", "read_file", "search_files", "http_request"],
        "skills": ["research"],
        "triggers": {
            "slack": "direct_message",
        },
        "safety": {
            "max_spend_per_trade": 0,
            "require_approval": [],
            "kill_switch": False,
        },
        "crons": [],
    },
    "devops": {
        "description": "DevOps agent — monitors infrastructure, deploys code, handles incidents",
        "personality": "Calm under pressure SRE. Follows runbooks precisely. Documents everything.",
        "model": "gpt-4o",
        "tools": ["shell_command", "http_request", "read_file", "write_file", "run_code", "search_files"],
        "skills": ["code"],
        "triggers": {
            "cron": "*/10 * * * *",
            "slack": "direct_message",
        },
        "safety": {
            "max_spend_per_trade": 0,
            "require_approval": ["deploy", "restart_service"],
            "kill_switch": True,
        },
        "crons": [
            {"name": "health_check", "schedule": "*/10 * * * *", "skill": "code", "action": "memory_cleanup", "params": {}},
        ],
    },
    "personal-assistant": {
        "description": "Personal AI assistant — manages tasks, calendar, reminders, research",
        "personality": "Proactive personal assistant. Anticipates needs, stays organized, remembers everything important.",
        "model": "gpt-4o",
        "tools": ["web_search", "http_request", "read_file", "write_file", "run_code"],
        "skills": ["research", "content", "code"],
        "triggers": {
            "cron": "0 8 * * *",
            "slack": "direct_message",
        },
        "safety": {
            "max_spend_per_trade": 0,
            "require_approval": [],
            "kill_switch": False,
        },
        "crons": [
            {"name": "morning_briefing", "schedule": "0 8 * * *", "skill": "research", "action": "daily_briefing", "params": {"topics": ["calendar", "tasks", "news"]}},
        ],
    },
    "custom": {
        "description": "Blank agent — configure everything yourself",
        "personality": "Helpful AI assistant.",
        "model": "gpt-4o",
        "tools": ["web_search", "read_file", "write_file"],
        "skills": [],
        "triggers": {},
        "safety": {
            "max_spend_per_trade": 0,
            "require_approval": [],
            "kill_switch": False,
        },
        "crons": [],
    },
}


def create_agent_workspace(name: str, template: str = "custom", target_dir: str = ".") -> str:
    """Create a new agent workspace directory with all necessary files.

    Args:
        name: Agent name (used as directory name)
        template: Template to use (trading, research, content, etc.)
        target_dir: Parent directory to create the workspace in

    Returns:
        Path to the created workspace
    """
    if template not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Unknown template '{template}'. Available: {available}")

    tmpl = TEMPLATES[template]
    workspace = Path(target_dir) / name
    workspace.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    (workspace / "skills").mkdir(exist_ok=True)
    (workspace / "scripts").mkdir(exist_ok=True)
    (workspace / "logs").mkdir(exist_ok=True)
    (workspace / "data").mkdir(exist_ok=True)
    (workspace / "data" / "memory").mkdir(exist_ok=True)

    # Create .env
    env_content = f"""# {name} — Environment Configuration
# LLM Provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here

# Agent
AGENT_NAME={name}
AGENT_PORT=8080
AGENT_API_KEY=change-me

# Integrations (optional)
SLACK_BOT_TOKEN=
SLACK_APP_TOKEN=
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=
GITHUB_TOKEN=
"""
    (workspace / ".env").write_text(env_content)

    # Create agent.config.json (as shown in PDF)
    config = {
        "name": name,
        "template": template,
        "description": tmpl["description"],
        "model": tmpl["model"],
        "personality": tmpl["personality"],
        "tools": tmpl["tools"],
        "skills": tmpl["skills"],
        "triggers": tmpl.get("triggers", {}),
        "safety": tmpl.get("safety", {}),
    }

    # Add template-specific config
    if "extra_skills" in tmpl:
        config["skill_config"] = tmpl["extra_skills"]

    (workspace / "agent.config.json").write_text(json.dumps(config, indent=2))

    # Create crons config
    if tmpl.get("crons"):
        try:
            import yaml
            crons_config = {"jobs": tmpl["crons"]}
            (workspace / "crons.yml").write_text(yaml.dump(crons_config, default_flow_style=False))
        except ImportError:
            # Fallback: write as JSON
            crons_config = {"jobs": tmpl["crons"]}
            (workspace / "crons.json").write_text(json.dumps(crons_config, indent=2))

    # Create initial SKILL.md
    skill_content = f"""---
name: {name}
description: {tmpl['description']}
template: {template}
created: auto
---

# {name}

Agent created from the `{template}` template.

## Configuration
- Model: {tmpl['model']}
- Tools: {', '.join(tmpl['tools'])}
- Skills: {', '.join(tmpl['skills']) if tmpl['skills'] else 'none'}

## Learnings
(The agent will record what it learns here)

## Decisions
(Important decisions will be logged here)
"""
    (workspace / "skills" / "SKILL.md").write_text(skill_content)

    # Create README
    readme = f"""# {name}

> {tmpl['description']}

Created with Jarvis OS using the `{template}` template.

## Quick Start

```bash
# Configure your API key
nano .env  # Set OPENAI_API_KEY

# Start the agent
jarvis start {name}

# Or run directly
cd .. && python -m jarvis.server --workspace {name}
```

## Files

- `agent.config.json` — Agent configuration (personality, tools, safety rules)
- `skills/` — Agent memory (SKILL.md files, learnings, knowledge)
- `scripts/` — Reusable automation scripts
- `logs/` — Execution logs
- `.env` — API keys and secrets
- `crons.yml` — Scheduled tasks

## Safety Rules

```json
{json.dumps(tmpl.get('safety', {}), indent=2)}
```
"""
    (workspace / "README.md").write_text(readme)

    return str(workspace)


def list_templates() -> dict:
    """Return available templates with descriptions."""
    return {name: tmpl["description"] for name, tmpl in TEMPLATES.items()}
