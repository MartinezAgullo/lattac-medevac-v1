# LATACC MEDEVAC

Multi-agent system for NATO medical evacuation operations. Monitors the Common Medical Operational Picture (CMOP) and supports evacuation decision-making per AJMedP-2 doctrine.

## Project Structure

```
LATACC_Medevac/
├── packages/
│   ├── latacc_common/      # Shared models, tool registry, tracing utils
│   └── cmop_observer/      # Agent 1 — CMOP situational awareness
└── pyproject.toml           # uv workspace root
```

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for package management
- [Ollama](https://ollama.ai/) running locally with `qwen2.5:14b-instruct` (or set `CMOP_MODEL`)
- cmop_map API running at `http://localhost:3000` (or set `CMOP_API_BASE`)

## Setup

```bash
cd LATACC_Medevac
uv sync
```

## Usage

```bash
# Run with defaults
uv run cmop-observer

# Override settings via environment variables
CMOP_MODEL=llama3:70b CMOP_API_BASE=http://10.0.0.5:3000 uv run cmop-observer
```

## Configuration

All settings can be overridden via environment variables with the `CMOP_` prefix:

| Variable | Default | Description |
|---|---|---|
| `CMOP_API_BASE` | `http://localhost:3000` | CMOP Map API URL |
| `CMOP_MODEL` | `qwen2.5:14b-instruct` | Ollama model name |
| `CMOP_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `CMOP_REQUEST_TIMEOUT` | `30.0` | API request timeout (seconds) |
| `CMOP_MAX_ITERATIONS` | `15` | Max agent reasoning iterations |

## License

Proprietary — LATACC project.