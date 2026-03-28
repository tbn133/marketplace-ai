# AI Tools Marketplace

A Claude Code plugin marketplace hosting AI-powered tools for code intelligence and audio processing.

## Plugins

| Plugin | Description | Python | Version |
|---|---|---|---|
| [code](plugins/code/) | AST-based code indexing, call graph analysis, semantic search, and persistent business memory | 3.12+ | 0.1.0 |
| [ai-voice-cover](plugins/ai-voice-cover/) | AI voice cover generator from YouTube URLs using RVC voice models | 3.10 | 0.1.0 |

## Installation

### Add marketplace to Claude Code

```bash
claude plugin marketplace add github.com/tabi4/code-intelligence-system
```

### Install a plugin

```bash
# From marketplace
claude plugin install code@code-intelligence-system --scope project
claude plugin install ai-voice-cover@code-intelligence-system --scope project

# From local path (development)
claude plugin install ./plugins/code --scope project
claude plugin install ./plugins/ai-voice-cover --scope project

# Uninstall
claude plugin uninstall code --scope project
```

---

## code plugin

### What it does

```text
Source Code  ->  tree-sitter AST  ->  Call Graph  (NetworkX)
                                  ->  Embeddings  (FAISS)
                                  ->  Memory      (SQLite)
```

- **Index** codebases using tree-sitter (no LLM) — extracts functions, classes, imports, call relationships
- **Multi-language** — Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, PHP
- **Search** by semantic similarity with automatic call graph expansion
- **Trace** call graphs — who calls a function, what it calls, full dependency chain
- **Remember** business rules, incidents, architecture decisions — persisted across sessions
- **Multi-project isolation** — all data partitioned by `project_id`

### Requirements

- Python 3.12+
- No external services needed (local mode uses NetworkX + FAISS + SQLite)

### Quick Start

```bash
cd plugins/code
pip install -r requirements.txt

# Index a codebase
python -m cmd.cli index ./my-project --project myapp

# Search code
python -m cmd.cli search --project myapp "authentication logic"

# Call graph
python -m cmd.cli graph --project myapp "myapp::auth/handler.py::verify_token"

# Save a business rule
python -m cmd.cli add-memory --project myapp --type business_rule "Orders over $500 require approval"

# Search memory
python -m cmd.cli search-memory --project myapp --query "approval"

# Validate plugin structure
python -m cmd.cli validate-plugin
```

### Skills

After installing the plugin, the following slash commands become available in Claude Code:

| Command | Auto-trigger | Description |
|---|---|---|
| `/code:init` | No | Index a codebase using tree-sitter AST (multi-language) |
| `/code:search` | When asking about code | Semantic search + call graph expansion |
| `/code:graph` | When analyzing functions | Call graph — callers/callees |
| `/code:remember` | When saying "remember this" | Save business rule / incident / note |
| `/code:recall` | When asking about past knowledge | Retrieve saved memories |
| `/code:analyze` | When doing deep analysis | Combines search + graph + memory |

### MCP Tools

Automatically available after install. Claude calls them directly:

| Tool | Description |
|---|---|
| `search_code` | Vector similarity search + call graph expansion |
| `get_call_graph` | Callers/callees traversal, configurable depth |
| `search_memory` | Query persistent memory by text and type |
| `add_memory` | Store business rules, incidents, notes with tags |

### Typical Workflow

```text
1. /code:init . --project myapp              <- one-time index
2. "Where is authentication handled?"       <- auto search
3. "What calls verify_token?"               <- auto graph
4. "Remember: JWT tokens expire after 1 hour" <- auto remember
5. "What are the auth rules?"               <- auto recall
```

### Architecture

Hexagonal (Ports & Adapters) with dual storage backend:

| Component | Local (default) | Production |
|---|---|---|
| Graph | NetworkX | Neo4j |
| Vectors | FAISS | Qdrant |
| Memory | SQLite | PostgreSQL |
| Cache | In-memory dict | Redis |

```text
plugins/code/
  app/
    domain/          # Models (FunctionNode, Memory...) + port interfaces
    services/        # IndexingService, SearchService, MemoryService
    indexer/         # tree-sitter parser, extractor, graph builder
    infrastructure/  # Port implementations (local + production)
    api/             # FastAPI REST server
    mcp/             # MCP server (stdio)
    config.py        # Env-based configuration
    container.py     # Dependency injection root
  cmd/cli.py         # Click CLI
  skills/            # 6 SKILL.md files
  data/              # Runtime data (gitignored)
```

### REST API

```bash
python -m cmd.cli serve
```

| Method | Path | Description |
|---|---|---|
| GET | `/search?project_id=X&query=Y&top_k=10` | Semantic code search |
| GET | `/graph?project_id=X&function_id=Y&depth=2` | Call graph |
| GET | `/function/{id}?project_id=X` | Function details |
| POST | `/memory` | Add memory `{project_id, type, content, tags}` |
| GET | `/memory/search?project_id=X&query=Y` | Search memory |
| DELETE | `/memory/{id}` | Delete memory |
| GET | `/health` | Health check |

### Docker (Production)

```bash
cd plugins/code
docker compose up -d
docker compose run --rm cli index /repos/myproject --project myproject
```

### Configuration

All via environment variables (defaults in `app/config.py`):

| Variable | Default | Description |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` or `production` |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant connection |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `EMBEDDING_DIM` | `128` | Vector dimension |
| `LOG_LEVEL` | `INFO` | Logging level |

Full documentation: [plugins/code/GUIDE.md](plugins/code/GUIDE.md)

---

## ai-voice-cover plugin

### What it does

```text
YouTube URL  ->  yt-dlp       ->  audio.wav
             ->  audio-sep    ->  vocal.wav + instrumental.wav
             ->  rvc-python   ->  ai_vocal.wav
             ->  FFmpeg blend  ->  blended × 3 (different ratios)
             ->  FFmpeg mix    ->  final × 3
             ->  evaluator    ->  best output
```

- **5-step pipeline** — download, separate, convert, blend, mix
- **Multiple versions** — generates 3+ outputs with different blend ratios
- **Auto-evaluation** — rule-based selection (no clipping, optimal loudness, target -14 dBFS)
- **Style presets** — vietnamese_soft, kpop_bright, deep_male, female_high, neutral
- **Model management** — download RVC models from HuggingFace or direct URLs
- **Local processing** — no cloud APIs, everything runs locally

### Requirements

- **Python 3.10** (required — rvc-python depends on faiss-cpu==1.7.3, no wheel for 3.11+)
- **FFmpeg** on PATH
- **RVC voice model** (.pth file)

Python packages installed automatically: yt-dlp, audio-separator, rvc-python, huggingface_hub, onnxruntime.

### Quick Start

```bash
cd plugins/ai-voice-cover

# 1. Install Python 3.10
brew install python@3.10          # macOS
# pyenv install 3.10.14           # or via pyenv

# 2. Setup venv (auto-detects python3.10, pins pip==23.3.2)
bash setup-venv.sh .

# 3. Download a voice model
export VOICE_COVER_RVC_MODEL_DIR="$HOME/.ai-voice-cover/models"
bash run.sh download-model --source "https://huggingface.co/user/model" --name "singer_a"

# 4. Generate cover
bash run.sh cover --url "https://youtube.com/watch?v=xxx" --voice "singer_a" --style auto

# Other commands
bash run.sh list-models           # List downloaded models
bash run.sh list-styles           # List available styles
bash run.sh check-tools           # Validate installations
```

### Skills

| Command | Auto-trigger | Description |
|---|---|---|
| `/voice:cover` | When asking to create a voice cover | Generate AI voice cover from YouTube URL |
| `/voice:download-model` | When asking to download a voice model | Download RVC model from HuggingFace or URL |

### Output

```json
{
  "best_audio": "~/.ai-voice-cover/output/cover_20260328/cover_neutral_0.30.wav",
  "versions": ["...0.20.wav", "...0.30.wav", "...0.40.wav"],
  "meta": {
    "style": "neutral",
    "params": { "blend_values": [0.2, 0.3, 0.4], "pitch_shift": 0 },
    "title": "Song Title",
    "evaluation": "Best loudness match (score=1.23)"
  }
}
```

### Style Presets

| Style | Blend | Pitch | Description |
|---|---|---|---|
| `vietnamese_soft` | 0.3 | -1 | Soft Vietnamese vocal |
| `kpop_bright` | 0.25 | 0 | Bright K-pop vocal |
| `deep_male` | 0.4 | -3 | Deep male conversion |
| `female_high` | 0.35 | +4 | High female conversion |
| `neutral` | 0.3 | 0 | No pitch adjustment |

Custom styles can be added to `styles.yaml`.

### Architecture

Pipeline pattern (planner -> executor -> evaluator):

```text
plugins/ai-voice-cover/
  plugin.py           # Entry: run(input) -> dict
  planner.py          # Style + parameter planning
  executor.py         # Pipeline orchestration
  evaluator.py        # Rule-based output selection
  config.py           # Env-based configuration
  styles.yaml         # Style presets
  steps/
    download.py       # yt-dlp Python API
    separate.py       # audio-separator Python API
    convert.py        # rvc-python Python API
    blend.py          # FFmpeg subprocess
    mix.py            # FFmpeg subprocess
    download_model.py # HuggingFace / URL downloader
  skills/             # 2 SKILL.md files
  setup-venv.sh       # Python 3.10 venv setup (+ pip pin)
  run.sh              # CLI wrapper with venv resolution
  cli.py              # argparse CLI
```

### Configuration

All via environment variables (defaults in `config.py`):

| Variable | Default | Description |
|---|---|---|
| `VOICE_COVER_RVC_MODEL_DIR` | — | **Required.** Path to RVC model directory |
| `VOICE_COVER_RVC_DEVICE` | `cpu` | `cpu` or `cuda:0` |
| `VOICE_COVER_RVC_F0_METHOD` | `rmvpe` | Pitch extraction method |
| `VOICE_COVER_FFMPEG_PATH` | `ffmpeg` | Path to FFmpeg |
| `VOICE_COVER_OUTPUT_DIR` | `~/.ai-voice-cover/output` | Output directory |
| `VOICE_COVER_TEMP_DIR` | `~/.ai-voice-cover/tmp` | Temp directory |
| `VOICE_COVER_KEEP_TEMP` | `false` | Keep temp files for debug |

### Known Constraints

- **Python 3.10 only**: rvc-python pins faiss-cpu==1.7.3 (no wheel for 3.11+)
- **pip==23.3.2**: omegaconf==2.0.6 uses legacy specifier `>=5.1.*` rejected by pip 24+. `setup-venv.sh` handles this automatically.
- **FFmpeg is system dependency**: Only tool not installable via pip

Full documentation: [plugins/ai-voice-cover/GUIDE.md](plugins/ai-voice-cover/GUIDE.md)

---

## Marketplace Structure

```text
code-intelligence-system/
├── .claude-plugin/
│   └── marketplace.json              # Marketplace manifest
├── plugins/
│   ├── code/                         # Plugin 1: Code intelligence
│   │   ├── .claude-plugin/plugin.json
│   │   ├── app/
│   │   ├── cmd/
│   │   ├── skills/
│   │   ├── mcp-servers.json
│   │   └── requirements.txt
│   └── ai-voice-cover/              # Plugin 2: Voice cover
│       ├── .claude-plugin/plugin.json
│       ├── plugin.py
│       ├── steps/
│       ├── skills/
│       ├── setup-venv.sh
│       └── requirements.txt
├── README.md
├── CLAUDE.md
└── .gitignore
```

## Adding a New Plugin

1. Create `plugins/<plugin-name>/` with a `.claude-plugin/plugin.json`
2. Add skills, MCP servers, or agents as needed
3. Register in `.claude-plugin/marketplace.json`:

```json
{
  "plugins": [
    { "name": "code", "source": "./plugins/code" },
    { "name": "ai-voice-cover", "source": "./plugins/ai-voice-cover" },
    { "name": "new-plugin", "source": "./plugins/new-plugin", "description": "..." }
  ]
}
```

4. Users update with: `claude plugin marketplace update`

## License

MIT
