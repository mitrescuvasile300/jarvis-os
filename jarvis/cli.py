"""Jarvis CLI — interactive chat from the terminal.

Usage:
    python -m jarvis.cli chat              # Interactive chat
    python -m jarvis.cli status            # Agent status
    python -m jarvis.cli memory search Q   # Search memory
    python -m jarvis.cli skill list        # List skills
    python -m jarvis.cli skill run NAME    # Run a skill action
"""

import argparse
import asyncio
import sys

from jarvis.agent import JarvisAgent
from jarvis.config import load_config


async def chat_loop(agent: JarvisAgent):
    """Interactive chat with Jarvis."""
    print(f"\n🤖 {agent.name} is ready! Type 'quit' to exit.\n")

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


async def show_status(agent: JarvisAgent):
    """Show agent status."""
    from datetime import datetime
    uptime = int((datetime.now() - agent.started_at).total_seconds())
    memory_count = await agent.memory.count()

    print(f"""
🤖 {agent.name} — Status
{'─' * 40}
Version:      1.0.0
LLM:          {agent.config['agent']['llm']['provider']} / {agent.config['agent']['llm']['model']}
Memory:       {memory_count} entries
Skills:       {', '.join(agent.skills.keys()) or 'none'}
Integrations: {', '.join(agent.integrations.keys()) or 'none'}
Uptime:       {uptime}s
""")


async def search_memory(agent: JarvisAgent, query: str):
    """Search agent memory."""
    results = await agent.memory.search(query, limit=10)
    if not results:
        print("No results found.")
        return

    print(f"\n🔍 Memory search: '{query}' — {len(results)} results\n")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['type']}] (relevance: {r.get('relevance', '?')}) {r['content'][:100]}")
    print()


async def list_skills(agent: JarvisAgent):
    """List available skills."""
    if not agent.skills:
        print("No skills loaded.")
        return

    print(f"\n📦 Skills ({len(agent.skills)}):\n")
    for name, skill in agent.skills.items():
        actions = ", ".join(skill.actions.keys()) if skill.actions else "no actions"
        print(f"  • {name}: {skill.description}")
        print(f"    Actions: {actions}")
    print()


async def main():
    parser = argparse.ArgumentParser(description="Jarvis OS CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Chat command
    subparsers.add_parser("chat", help="Interactive chat")

    # Status command
    subparsers.add_parser("status", help="Show agent status")

    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Memory operations")
    memory_sub = memory_parser.add_subparsers(dest="memory_cmd")
    search_parser = memory_sub.add_parser("search", help="Search memory")
    search_parser.add_argument("query", help="Search query")

    # Skill commands
    skill_parser = subparsers.add_parser("skill", help="Skill operations")
    skill_sub = skill_parser.add_subparsers(dest="skill_cmd")
    skill_sub.add_parser("list", help="List skills")
    run_parser = skill_sub.add_parser("run", help="Run a skill action")
    run_parser.add_argument("name", help="Skill name")
    run_parser.add_argument("--action", default="default", help="Action name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    config = load_config()
    agent = JarvisAgent(config)
    await agent.initialize()

    try:
        if args.command == "chat":
            await chat_loop(agent)
        elif args.command == "status":
            await show_status(agent)
        elif args.command == "memory":
            if args.memory_cmd == "search":
                await search_memory(agent, args.query)
        elif args.command == "skill":
            if args.skill_cmd == "list":
                await list_skills(agent)
            elif args.skill_cmd == "run":
                result = await agent.run_skill(args.name, args.action, {})
                print(f"Result: {result}")
    finally:
        await agent.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
