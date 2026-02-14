"""Jarvis OS CLI — the main command-line interface.

Usage:
    jarvis init <name> --template <template>   # Create new agent
    jarvis start <name> [--daemon]             # Start an agent
    jarvis status                              # Show running agents
    jarvis chat [--workspace <name>]           # Interactive chat
    jarvis list-templates                      # Show available templates
    jarvis memory search <query>               # Search agent memory
    jarvis skill list                          # List available skills
"""

import argparse
import asyncio
import json
import sys
import os
from pathlib import Path


def cmd_init(args):
    """Create a new agent workspace."""
    from jarvis.init_command import create_agent_workspace, list_templates

    name = args.name
    template = args.template

    print(f"\n🤖 Creating agent '{name}' from template '{template}'...\n")

    try:
        workspace_path = create_agent_workspace(name, template)
        print(f"✅ Agent workspace created: {workspace_path}/\n")
        print(f"📁 Structure:")
        for item in sorted(Path(workspace_path).rglob("*")):
            if item.is_file():
                rel = item.relative_to(workspace_path)
                print(f"   {rel}")
        print(f"\n📋 Next steps:")
        print(f"   1. cd {name}")
        print(f"   2. Edit .env — add your OPENAI_API_KEY")
        print(f"   3. jarvis start {name}")
        print()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)


def cmd_start(args):
    """Start an agent."""
    name = args.name
    workspace = Path(name)

    if not workspace.exists():
        print(f"❌ Agent workspace '{name}' not found. Run: jarvis init {name}")
        sys.exit(1)

    config_file = workspace / "agent.config.json"
    if not config_file.exists():
        print(f"❌ No agent.config.json found in {name}/")
        sys.exit(1)

    config = json.loads(config_file.read_text())
    print(f"\n🤖 Starting {config['name']}...")
    print(f"   Template: {config.get('template', 'custom')}")
    print(f"   Model: {config['model']}")
    print(f"   Tools: {', '.join(config.get('tools', []))}")
    print(f"   Skills: {', '.join(config.get('skills', []))}")

    if args.daemon:
        print(f"   Mode: daemon (background)")
        print(f"\n🚀 Agent running in background. Use 'jarvis status' to check.")
    else:
        print(f"   Mode: foreground")
        print(f"\n🚀 Starting server...\n")

    # Set workspace env for the server
    os.environ["JARVIS_WORKSPACE"] = str(workspace.absolute())
    os.environ["AGENT_NAME"] = config["name"]

    from jarvis.server import main as server_main
    server_main()


def cmd_list_templates(args):
    """List available templates."""
    from jarvis.init_command import TEMPLATES

    print("\n📋 Available templates:\n")
    for name, tmpl in TEMPLATES.items():
        print(f"  • {name:<22} {tmpl['description']}")
    print(f"\nUsage: jarvis init my-agent --template <template>")
    print()


async def cmd_chat(args):
    """Interactive chat with an agent."""
    from jarvis.agent import JarvisAgent
    from jarvis.config import load_config

    workspace = args.workspace or "."
    config = load_config(os.path.join(workspace, "config"))
    agent = JarvisAgent(config)

    # Initialize with reduced features for CLI mode
    print(f"\n🤖 Initializing {agent.name}...")
    await agent.initialize()
    print(f"✅ {agent.name} is ready! Type 'quit' to exit.\n")

    conversation_id = "cli"
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print(f"\n{agent.name}: Goodbye! 👋")
            break

        response = await agent.chat(user_input, conversation_id=conversation_id)
        print(f"\n{agent.name}: {response['text']}")
        if response.get("tools_used"):
            print(f"  🔧 Tools used: {', '.join(response['tools_used'])}")
        print()

    await agent.shutdown()


async def cmd_status(args):
    """Show agent status."""
    import httpx

    port = int(os.getenv("AGENT_PORT", "8080"))
    url = f"http://localhost:{port}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{url}/health")
            if resp.status_code == 200:
                data = resp.json()
                print(f"\n🤖 {data['agent']} — Running")
                print(f"   Version: {data.get('version', '?')}")
                print(f"   Uptime: {data.get('uptime_seconds', 0)}s")
                print(f"   Memory: {data.get('memory_entries', 0)} entries")
                print(f"   Skills: {data.get('skills_loaded', 0)} loaded")
                print()
            else:
                print(f"\n⚠️ Agent responded with HTTP {resp.status_code}")
    except Exception:
        print(f"\n❌ No agent running on port {port}")
        print(f"   Start one with: jarvis start <agent-name>")
    print()


async def cmd_memory_search(args):
    """Search agent memory."""
    from jarvis.agent import JarvisAgent
    from jarvis.config import load_config

    config = load_config("config")
    agent = JarvisAgent(config)
    await agent.initialize()

    results = await agent.memory.search(args.query, limit=10)
    if not results:
        print("No results found.")
    else:
        print(f"\n🔍 Memory search: '{args.query}' — {len(results)} results\n")
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['type']}] {r['content'][:120]}")
    print()
    await agent.shutdown()


async def cmd_skill_list(args):
    """List skills."""
    from jarvis.agent import JarvisAgent
    from jarvis.config import load_config

    config = load_config("config")
    agent = JarvisAgent(config)
    await agent.initialize()

    if not agent.skills:
        print("No skills loaded.")
    else:
        print(f"\n📦 Skills ({len(agent.skills)}):\n")
        for name, skill in agent.skills.items():
            actions = ", ".join(skill.actions.keys()) if skill.actions else "no actions"
            print(f"  • {name}: {skill.description}")
            print(f"    Actions: {actions}")
    print()
    await agent.shutdown()


async def main():
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Jarvis OS — Your Personal AI Operating System",
    )
    subparsers = parser.add_subparsers(dest="command")

    # init
    init_parser = subparsers.add_parser("init", help="Create a new agent workspace")
    init_parser.add_argument("name", help="Agent name")
    init_parser.add_argument("--template", "-t", default="custom", help="Template to use")

    # start
    start_parser = subparsers.add_parser("start", help="Start an agent")
    start_parser.add_argument("name", help="Agent workspace name")
    start_parser.add_argument("--daemon", "-d", action="store_true", help="Run in background")

    # status
    subparsers.add_parser("status", help="Show agent status")

    # chat
    chat_parser = subparsers.add_parser("chat", help="Interactive chat")
    chat_parser.add_argument("--workspace", "-w", help="Agent workspace path")

    # list-templates
    subparsers.add_parser("list-templates", help="Show available templates")

    # memory
    memory_parser = subparsers.add_parser("memory", help="Memory operations")
    memory_sub = memory_parser.add_subparsers(dest="memory_cmd")
    search_parser = memory_sub.add_parser("search", help="Search memory")
    search_parser.add_argument("query", help="Search query")

    # skill
    skill_parser = subparsers.add_parser("skill", help="Skill operations")
    skill_sub = skill_parser.add_subparsers(dest="skill_cmd")
    skill_sub.add_parser("list", help="List skills")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Sync commands
    if args.command == "init":
        cmd_init(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "list-templates":
        cmd_list_templates(args)
    # Async commands
    elif args.command == "status":
        await cmd_status(args)
    elif args.command == "chat":
        await cmd_chat(args)
    elif args.command == "memory":
        if args.memory_cmd == "search":
            await cmd_memory_search(args)
    elif args.command == "skill":
        if args.skill_cmd == "list":
            await cmd_skill_list(args)


if __name__ == "__main__":
    asyncio.run(main())
