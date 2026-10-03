# Hackathon Submission Package

## Project

**Code Archaeologist** treats a software repository as an archaeological site. It discovers the useful patterns worth preserving, maps architectural layers, identifies stale or dead code, and surfaces technical debt that needs remediation.

### Features and functionality

- **Excavate:** runs a full repository analysis and produces artifacts, strata, fossils, and ruins.
- **Scan:** performs a faster health assessment with language, LOC, complexity, and hotspot metrics.
- **Explain:** uses deep reasoning to explain an individual finding in context.
- **Remediation:** generates a prioritized technical-debt plan with concrete refactoring steps.
- **Predict:** forecasts likely architecture evolution over a 6–12 month horizon.
- **Output formats:** JSON, Markdown, and HTML reports for humans and CI/CD workflows.
- **Web API:** exposes health, scan, excavation jobs, job status, and OpenAPI documentation.
- **Public demo mode:** the hosted demo runs a bundled, credential-free fixture so judges can verify the interaction immediately; live scans use the configured model service.

## Required URLs

- **Public code repository:** https://github.com/25158074-alt/code-archaeologist
- **Working demo:** https://8000-i93fdw1al0xqxynuxp89l-25bd32c6.sg2.manus.computer
- **Demonstration video on YouTube:** `ADD_PUBLIC_YOUTUBE_URL`

## Recommended track

**Generative AI / AI Applications** (select the closest equivalent track shown by the hackathon submission form). The project uses foundation models as an active part of software analysis, not merely as a chat interface: model tiers are routed to fast scans, file intent, architectural reasoning, remediation planning, and evolution prediction.

## NVIDIA, Token Factory, and Nebius usage

- **NVIDIA Nemotron:** the project routes analysis work across Nemotron Nano, Super, and Ultra tiers. Nano handles quick health scoring and recommendations; Super handles file intent and focused refactoring guidance; Ultra handles architecture analysis, remediation plans, and evolution forecasts.
- **Token Factory:** the workflow uses model-tier routing and bounded prompts so inexpensive fast passes handle broad repository triage before deeper reasoning is requested. This reduces unnecessary context and token usage while keeping higher-capability reasoning for the findings that need it.
- **Nebius / NVIDIA API endpoint:** the client is configured through `NEBIUS_BASE_URL` and `NEBIUS_API_KEY`, with the default endpoint documented in `.env.example`.
- **Nebius Serverless:** `deploy/nebius-serverless.yaml` documents an HTTP deployment shape for the API.
- **Nebius Serverless Jobs:** `deploy/nebius-jobs.yaml` documents scheduled weekly deep excavations and daily hotspot checks.
- **Containers:** `deploy/Dockerfile`, `deploy/Dockerfile.web`, and `deploy/docker-compose.yml` provide reproducible deployment options.
- **Tree-sitter:** parses Python, JavaScript, TypeScript, Go, and Rust source into structural signals before model reasoning.

## Setup and run instructions

```bash
# Clone
 git clone https://github.com/25158074-alt/code-archaeologist.git
 cd code-archaeologist

# Install
python -m pip install -e ".[dev,web]"

# Configure credentials locally; never commit .env
cp .env.example .env
# Set NEBIUS_API_KEY in .env

# CLI examples
code-archaeologist scan ./test_project
code-archaeologist excavate ./test_project --deep --fast --format html

# Start the API and public demo page
python code_archaeologist/deploy/web_api.py
# Open http://localhost:8000
# API docs: http://localhost:8000/docs
```

The hosted public demo uses `/` and `/demo` with the bundled fixture and does not accept arbitrary filesystem paths. Live `/scan` and `/excavate` requests require a server-side Nebius API key.

## Demonstration video plan

The final YouTube video must be **under three minutes** and should show:

1. The project landing page opening on the target device.
2. The sample excavation button returning a report from the running API.
3. The findings summary, health score, and complexity hotspots.
4. The repository README and CLI commands briefly showing how to run a live scan.
5. A short explanation of the Nemotron tier routing and the Nebius deployment files.

Use only original screen capture, project-generated visuals, narration, and/or royalty-free audio. Do not include third-party logos, copyrighted music, or unrelated trademarks.

## Nebius and NVIDIA feedback

**Token Factory:** Tiered model routing is a strong fit for repository analysis because it lets a fast pass classify the whole codebase before expensive reasoning is spent on a small set of high-value findings. Helpful improvements would include clearer per-request token/cost telemetry and an easy way to compare quality across Nemotron tiers.

**Nebius AI Cloud:** The API-oriented workflow is straightforward to containerize and makes it practical to separate interactive scans from scheduled jobs. Helpful improvements would include a small judge-facing starter template for public demos and more explicit examples for secrets, logs, and serverless observability.

**NVIDIA Nemotron:** The separation between quick triage and deep architectural reasoning maps well to the product workflow. Structured JSON output and stable schema adherence are especially valuable for report generation. Helpful improvements would include reference prompt recipes for code analysis and stronger structured-output guarantees for multi-part remediation plans.

## Prior-work disclosure

This repository was assembled for the submission and contains the project implementation, deployment configuration, sample project, and documentation. If any component existed before the official Submission Period, replace this paragraph with a factual explanation of the substantial changes made during the Submission Period (for example: Nemotron integration, model-tier routing, Tree-sitter parsing, the web API, deployment configuration, or the public demo interface).

## Final checklist

- [x] Public repository on GitHub
- [x] Open-source MIT license included and detectable
- [x] README with setup and run instructions
- [x] Source code, deployment configuration, and sample project included
- [x] NVIDIA Nemotron and Nebius usage explained
- [x] Token Factory workflow contribution explained
- [x] Credential-free working demo path included
- [ ] Hosted demo URL added to this document and the submission form
- [ ] Under-three-minute demonstration video uploaded publicly to YouTube
- [ ] YouTube URL added to this document and the submission form
- [ ] Exact hackathon track selected on the submission form
- [ ] Prior-work disclosure finalized if applicable
