# Hackathon Submission Package

## 1. Project

**Code Archaeologist** treats a software repository as an archaeological site. It discovers useful patterns worth preserving, maps architectural layers, identifies stale or dead code, and surfaces technical debt that needs remediation.

### Features and functionality

- **Excavate:** performs a full repository analysis and produces artifacts, strata, fossils, and ruins.
- **Scan:** performs a fast health assessment with language, lines-of-code, complexity, and hotspot metrics.
- **Explain:** provides contextual reasoning for an individual finding.
- **Remediation:** generates a prioritized technical-debt plan with concrete refactoring steps.
- **Predict:** forecasts likely architecture evolution over a 6–12 month horizon.
- **Finding categories:** artifacts, strata, fossils, and ruins organize positive patterns, architecture, stale code, and technical debt.
- **Output formats:** JSON, Markdown, and HTML reports for humans and CI/CD workflows.
- **Web API:** provides health, scan, excavation-job, job-status, and OpenAPI endpoints.
- **Interactive demo:** demonstrates model-tier routing, finding filters, explanations, remediation, forecasting, exports, issue handoff, onboarding, CI snippets, highlighted code, and a stratigraphy cross-section.

## 2. Required URLs

- **Working demo:** https://25158074-alt.github.io/code-archaeologist/
- **Public code repository:** https://github.com/25158074-alt/code-archaeologist
- **License:** MIT, visible in the repository as [`LICENSE`](LICENSE) and detected by GitHub as MIT.
- **Demonstration video:** intentionally omitted; the entrant will provide the public YouTube URL separately.

> **Deployment status:** GitHub Pages is enabled for this repository using the `main` branch and `/` root. The live demo is available at the URL above.

## 3. Track

**Generative AI / AI Applications** — select the closest equivalent track shown by the hackathon submission form.

Code Archaeologist uses foundation models as an active part of software analysis rather than as a chat-only interface. Model tiers are routed to fast scans, file-intent analysis, architectural reasoning, remediation planning, and evolution prediction.

## 4. Repository and project requirements

The project satisfies the non-video submission requirements as follows:

- **Required developer tools and project:** implemented as a Python package with CLI, web API, Tree-sitter parsers, model clients, analysis engine, deployment configuration, and a bundled sample project.
- **Working demo URL:** provided above; the static product demo is in [`site/`](site/).
- **Text description:** provided in this document and the repository [`README.md`](README.md).
- **Public code repository:** GitHub repository is public and available at the URL above.
- **Complete source and assets:** source code, demo assets, sample project, deployment files, tests, and setup files are included in the repository.
- **Open-source license:** MIT license is included in [`LICENSE`](LICENSE); GitHub identifies the repository license as MIT.
- **Setup guidance:** installation, environment configuration, CLI commands, API startup, and deployment instructions are in [`README.md`](README.md).
- **NVIDIA/Nebius disclosure:** model usage, Token Factory workflow, and Nebius services are described below.

## 5. Setup and run instructions

```bash
# Clone
git clone https://github.com/25158074-alt/code-archaeologist.git
cd code-archaeologist

# Install the package, development tools, and web API dependencies
python -m pip install -e ".[dev,web]"

# Configure credentials locally; never commit .env
cp .env.example .env
# Set NEBIUS_API_KEY in .env

# Run a quick scan against the included sample project
code-archaeologist scan ./test_project

# Run a deeper analysis and create an HTML report
code-archaeologist excavate ./test_project --deep --fast --format html

# Start the API and demo page locally
python -m code_archaeologist.deploy.web_api
# Open http://localhost:8000
# API documentation: http://localhost:8000/docs
```

The credential-free demo uses the bundled fixture and does not require an API key. Live `/scan` and `/excavate` requests require a server-side `NEBIUS_API_KEY`.

## 6. NVIDIA Nemotron, Token Factory, and Nebius usage

### NVIDIA Nemotron

The application routes analysis work across three Nemotron capability tiers:

- **Nemotron Nano:** fast health scoring, repository triage, and hotspot identification.
- **Nemotron Super:** balanced file-intent analysis and focused refactoring suggestions.
- **Nemotron Ultra:** deep architectural analysis, remediation planning, and evolution forecasting.

The implementation is in [`code_archaeologist/analysis/`](code_archaeologist/analysis/) and [`code_archaeologist/core/nebius_client.py`](code_archaeologist/core/nebius_client.py).

### Token Factory acceleration

Token Factory accelerated the workflow by enabling a tiered analysis pipeline: inexpensive fast passes classify the repository first, then higher-capability reasoning is reserved for the most valuable findings and planning tasks. Bounded prompts and structured JSON outputs reduce unnecessary context while making the results usable by the CLI, API, reports, and demo.

The default endpoint is configured in [`code_archaeologist/core/config.py`](code_archaeologist/core/config.py) and [`.env.example`](.env.example) as:

```text
https://api.tokenfactory.us-central1.nebius.com/v1/
```

### Other Nebius and NVIDIA-related tools and services

- **Nebius Token Factory:** OpenAI-compatible model endpoint used by the analysis client.
- **Nebius Serverless:** HTTP deployment shape documented in [`code_archaeologist/deploy/nebius-serverless.yaml`](code_archaeologist/deploy/nebius-serverless.yaml).
- **Nebius Serverless Jobs:** scheduled weekly deep excavations and daily hotspot checks documented in [`code_archaeologist/deploy/nebius-jobs.yaml`](code_archaeologist/deploy/nebius-jobs.yaml).
- **Containers:** reproducible deployment through [`Dockerfile`](Dockerfile), [`code_archaeologist/deploy/Dockerfile.web`](code_archaeologist/deploy/Dockerfile.web), and [`code_archaeologist/deploy/docker-compose.yml`](code_archaeologist/deploy/docker-compose.yml).
- **Tree-sitter:** structural parsing for Python, JavaScript, TypeScript, Go, and Rust before model reasoning.

## 7. Nebius and NVIDIA feedback

**Nebius Token Factory:** Tiered model routing is a strong fit for repository analysis because a fast pass can classify the whole codebase before expensive reasoning is spent on a small set of high-value findings. Helpful improvements would include clearer per-request token/cost telemetry and an easy way to compare quality across Nemotron tiers.

**Nebius AI Cloud:** The API-oriented workflow is straightforward to containerize and makes it practical to separate interactive scans from scheduled jobs. Helpful improvements would include a judge-facing starter template for public demos and more explicit examples for secrets, logs, and serverless observability.

**NVIDIA Nemotron:** Separating quick triage from deep architectural reasoning maps well to the product workflow. Structured JSON output and stable schema adherence are especially valuable for report generation. Helpful improvements would include reference prompt recipes for code analysis and stronger structured-output guarantees for multi-part remediation plans.

## 8. Prior-work disclosure

Code Archaeologist is submitted as an open-source project developed for this hackathon submission. The submission package includes the implementation, Nemotron/Token Factory integration, tiered model routing, Tree-sitter parsing, the web API, deployment configuration, sample project, tests, and interactive demo. If the entrant's official records identify any component as having existed before the Submission Period, this paragraph should be replaced with a factual account of the substantial Submission Period updates before submitting the form.

## 9. Verification checklist (video intentionally excluded)

- [x] Project built with the required developer tools and project requirements
- [x] Working demo URL documented
- [x] Text description of features and functionality included
- [x] Public GitHub repository provided
- [x] Source code, assets, and functional instructions included
- [x] Public repository confirmed
- [x] MIT open-source license included and GitHub-detectable
- [x] README includes setup and run guidance
- [x] NVIDIA Nemotron usage explained
- [x] Token Factory workflow acceleration explained
- [x] Nebius tools and services identified
- [x] Track identified: Generative AI / AI Applications
- [x] Feedback on Nebius Token Factory, Nebius AI Cloud, and NVIDIA Nemotron included
- [x] GitHub Pages enabled in repository settings from `main` and `/` root
- [ ] Demonstration video uploaded to YouTube and added to the submission form — intentionally left for the entrant

## 10. Copy-ready submission summary

**Code Archaeologist** is an AI-powered software archaeology platform that analyzes codebases with NVIDIA Nemotron models through Nebius Token Factory. It discovers patterns worth preserving, maps architectural strata, identifies stale code fossils, and surfaces technical-debt ruins. Users can run quick scans or deep excavations through the CLI and web API, then receive structured JSON, Markdown, or HTML reports. A credential-free interactive demo shows the complete product workflow, including finding categories, model-tier routing, explanations, remediation plans, evolution forecasts, exports, and architecture visualization.

**Repository:** https://github.com/25158074-alt/code-archaeologist
**Demo:** https://25158074-alt.github.io/code-archaeologist/
**Track:** Generative AI / AI Applications
**License:** MIT
