# Codex Context File

Load trusted local UTF-8 text files directly into a Codex turn without asking the
model to call a file-reading tool. Paths and shell-style glob patterns are
supported.

## Install

```sh
codex plugin marketplace add gaoyifan/codex-context-file
codex plugin add context-file@codex-context-file
```

Start a new Codex thread. On first use, review and trust the plugin hook.
The hook requires [`uv`](https://docs.astral.sh/uv/) on `PATH`; it uses uv to
provide its Python runtime.

## Use

```text
$context-file docs/architecture.md
Summarize this document.
```

Load several files:

```text
$context-file docs/*.md
Compare these documents.
```

Patterns support `*`, `?`, `[]`, and recursive `**`. Relative paths are resolved
from the active Codex working directory. Multiple files are loaded in sorted path
order, and each document is wrapped with markers containing its absolute path.

## How it works

The plugin registers a synchronous `UserPromptSubmit` hook. Codex sends the user
prompt and working directory to the hook over stdin. The hook extracts the path
or pattern, reads the matching files, and returns their contents as
`additionalContext` before the model runs.

Hook context uses the developer role, so only load trusted documents. Files must
also fit within the selected model's context window.

## Development

```sh
uv run -m unittest discover -s tests
uv run --with pyyaml ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/context-file
```
