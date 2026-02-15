---
name: code-execution
description: Execute Python code and shell commands for calculations, automation, and system tasks.
---

# Code Execution Tools

You can run Python code and shell commands directly.

## Available Functions

- `run_code(code)` — Execute Python code, returns stdout/stderr
- `shell_command(command)` — Execute shell command, returns output

## When to Use

- User asks for calculations or data processing
- User wants to generate or transform data
- User asks to install something or check system status
- Any task that's easier to solve with code than with words

## Best Practices

1. For complex tasks, write clean Python with comments
2. Print results explicitly — only stdout is captured
3. Shell commands have a 30-second timeout
4. Use `shell_command` for system tasks (ls, ps, curl, etc.)
5. Use `run_code` for data processing, math, parsing
6. Dangerous commands (rm -rf /, etc.) are blocked for safety

## Example

User: "what's 15% of 3847?"
1. `run_code(code="print(3847 * 0.15)")`
2. Return: 577.05
