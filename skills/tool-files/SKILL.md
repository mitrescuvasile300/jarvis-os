---
name: file-operations
description: Read, write, list, and search files. Use for creating scripts, configs, reading data.
---

# File Operation Tools

You have full filesystem access within your workspace.

## Available Functions

- `read_file(path)` — Read file contents (truncated at 10K chars)
- `write_file(path, content)` — Write/create a file (creates directories)
- `list_files(path, pattern)` — List directory contents with optional glob
- `search_files(pattern, path, file_type)` — Grep/search for patterns in files

## When to Use

- User asks to create a file, script, or config
- User asks to read or check a file
- User asks to find something in code
- Saving generated content (reports, configs, scripts)

## Best Practices

1. Always check if a file exists before overwriting (use `read_file` first)
2. Use `list_files` to explore directories before assuming paths
3. Use `search_files` to find specific code or config values
4. Created files persist in the workspace across conversations

## File Locations

- `/app/knowledge/` — Your persistent knowledge files
- `/app/data/` — Database and vector store
- `/app/data/uploads/` — Uploaded/generated files (accessible via /api/uploads/)
