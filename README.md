# 🏛️ Code Archaeologist

> **Excavate codebases as archaeological sites** — Discover artifacts, identify strata, uncover fossils, and expose ruins using NVIDIA Nemotron models on Nebius.

## 🎯 What Makes This Unique

Unlike traditional static analyzers that just dump metrics, Code Archaeologist treats your codebase as an **archaeological site** with:

- **🏺 Artifacts** — Patterns, idioms, conventions, abstractions (the *good* stuff)
- **🏗️ Strata** — Architectural layers with stability, coupling, cohesion scores
- **💀 Fossils** — Dead code, stale modules, deprecated APIs (the *dead* stuff)
- **🏚️ Ruins** — Technical debt, god classes, circular deps, copy-paste (the *dangerous* stuff)

## 🧠 Dual-Model Intelligence

| Model | Tier | Purpose |
|-------|------|---------|
| **Nemotron 3 Ultra** | Deep Reasoning | Architecture analysis, remediation planning, evolution prediction |
| **Nemotron 3 Super** | Balanced | File intent analysis, refactoring suggestions, documentation |
| **Nemotron 3 Nano** | Fast | Quick scans, health checks, hotspot identification |

**Smart routing**: Simple tasks → Nano, Moderate → Super, Complex → Ultra. Credits stretch further.

## 🚀 Quick Start

```bash
# Install
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your NEBIUS_API_KEY from https://tokenfactory.nebius.com

# Excavate a codebase
code-archaeologist excavate ./my-project --deep --fast

# Quick scan
code-archaeologist scan ./my-project

# Generate remediation plan
code-archaeologist remediation ./my-project

# Predict evolution
code-archaeologist predict ./my-project
```

## 📋 Commands

| Command | Description |
|---------|-------------|
| `excavate` | Full archaeological excavation with all findings |
| `scan` | Quick health check + hotspot detection (Nano/Super) |
| `explain` | Deep explanation of a specific finding (Ultra) |
| `remediation` | Prioritized technical debt remediation plan (Ultra) |
| `predict` | 6-12 month architecture evolution forecast (Ultra) |

## 📊 Output Formats

- **JSON** — Machine-readable, for CI/CD integration
- **Markdown** — Human-readable reports
- **HTML** — Shareable reports with styling

## 🌐 Web API (Nebius Serverless)

Deploy as a serverless endpoint:

```bash
# Build and deploy
nebius serverless deploy --config code_archaeologist/deploy/nebius-serverless.yaml

# Or run locally
pip install -e ".[web]"
python -m code_archaeologist.deploy.web_api
```

**API Endpoints:**
- `POST /excavate` — Start async excavation job
- `GET /jobs/{id}` — Check job status/results
- `POST /scan` — Quick synchronous scan
- `GET /health` — Health check

### Public judging demo

The API also serves a credential-free interactive product demo at `/`. The fixture includes non-empty artifacts, strata, fossils, and ruins plus model-tier badges, latency/token telemetry, explain panels, remediation steps, a 6–12 month forecast, a stratigraphy cross-section, exports, issue handoff, onboarding brief, CI snippet, severity filters, and highlighted code. Live `/scan` and `/excavate` requests use the Nebius Token Factory endpoint and require `NEBIUS_API_KEY` on the server.

The repository includes the standalone demo page under `site/`; it accepts a GitHub URL or ZIP upload and clearly labels fixture/demo mode versus live requests. The API root serves the same page when the `site/` directory is present.

See [`SUBMISSION.md`](SUBMISSION.md) for the hackathon description, required URLs, model/tool disclosure, video plan, feedback, and final submission checklist.

## ⚙️ Background Jobs (Nebius Serverless Jobs)

Schedule recurring excavations:

```bash
nebius jobs create --config code_archaeologist/deploy/nebius-jobs.yaml
```

Features:
- Weekly full scans with deep reasoning
- Daily hotspot checks
- Webhook notifications
- S3/Nebius storage for reports

## 🔧 Configuration

All settings via `.env` or environment variables:

```bash
NEBIUS_API_KEY=your-key          # Required
NEBIUS_BASE_URL=https://.../v1   # Optional, must include /v1
FOSSIL_THRESHOLD_DAYS=180
RUIN_COMPLEXITY_THRESHOLD=50
ARCHAEOLOGIST_ALLOWED_ROOT=./data  # web API: only this directory can be scanned
LOG_LEVEL=INFO
```

## 🏗️ Architecture

```
code_archaeologist/
├── core/           # Config, Nebius client
├── parsers/        # Tree-sitter parsers (Py/JS/TS/Go/Rust)
├── models/         # Finding data models
├── analysis/
│   ├── engine.py       # Excavation engine (static + git analysis)
│   ├── deep_reasoning.py   # Nemotron 3 Ultra reasoning
│   └── fast_analysis.py    # Nemotron Nano/Super fast paths
├── cli/            # Typer CLI with Rich output
└── deploy/         # Docker, Nebius Serverless configs
```

## 🎨 Example Output

```
🏛️ Excavation Complete
╭────────────────────────────────────────────╮
│ Site: my-service                          │
│ Path: /home/user/my-service               │
│ Excavated: 2026-10-03T10:30:45            │
╰────────────────────────────────────────────╯

📊 Discovery Summary
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Category          ┃ Count ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Artifacts         │  47   │
│ Strata            │   6   │
│ Fossils           │  12   │
│ Ruins             │  23   │
└────────────────────┴───────┘

🏚️ Ruins by Severity
┏━━━━━━━━━━━┳━━━━━━━┓
┃ Severity  ┃ Count ┃
┡━━━━━━━━━━━╇━━━━━━━┩
│ Critical  │   2   │
│ High      │   5   │
│ Medium    │  11   │
│ Low       │   5   │
└───────────┴───────┘

⚡ Fast Health Assessment
╭──────────────────────────────────────────────╮
│ Health Score: 67/100                         │
│ Risk Level: MEDIUM                           │
│ Top Concerns: God classes, Circular deps,    │
│               Long methods, Magic numbers    │
╰──────────────────────────────────────────────╯
```

## 🧪 Deep Reasoning Example

With `--deep`, Nemotron 3 Ultra provides:

```json
{
  "architectural_style": "Layered monolith with leaking boundaries",
  "health_score": 67,
  "technical_debt_index": 72,
  "key_insights": [
    "Presentation layer directly accesses Foundation layer (violates layering)",
    "Core stratum has 40% coupling to Integration stratum",
    "3 God Classes control 60% of business logic",
    "Test stratum is disconnected (0% coupling to other layers)"
  ],
  "strategic_recommendations": [
    "Introduce Application Services layer between Presentation and Core",
    "Extract God Classes using Strangler Fig pattern",
    "Implement Dependency Inversion for external integrations",
    "Reconnect Test stratum with contract testing"
  ]
}
```

## 📦 Nebius Deployment

### Serverless Endpoint (API)
```yaml
# code_archaeologist/deploy/nebius-serverless.yaml
resources:
  cpu: "2"
  memory: "4Gi"
scaling:
  min_replicas: 0
  max_replicas: 10
```

### Serverless Jobs (Background)
```yaml
# code_archaeologist/deploy/nebius-jobs.yaml
template:
  resources:
    cpu: "4"
    memory: "8Gi"
  timeout: 1800
schedules:
  - cron: "0 2 * * 0"  # Weekly deep scan
```

## 🤝 Contributing

```bash
# Dev setup
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
mypy code_archaeologist
```

## 📄 License

MIT License — Build something amazing with it.

---

**Powered by NVIDIA Nemotron on Nebius** 🚀
