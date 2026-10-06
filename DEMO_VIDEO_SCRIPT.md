# Code Archaeologist — 3-Minute Demo Video Script

**Target length:** 2:40–2:55
**Format:** screen recording with narration
**Audio:** narration plus optional royalty-free or original low-volume ambience only
**Do not include:** third-party trademarks, copyrighted music, private API keys, or unpublished credentials

## Recording setup

- Open the live demo: https://25158074-alt.github.io/code-archaeologist/
- Use a clean browser window at approximately 1440×900 or 1920×1080.
- Hide personal bookmarks, notifications, account details, and unrelated tabs.
- Keep the browser zoom at 100%.
- Use the credential-free fixture mode for the main demonstration.
- If showing the repository, open only the public GitHub repository and README.
- Do not display `.env`, API keys, terminal secrets, or private repository URLs.

## Script and shot list

### 0:00–0:12 — Opening: the problem

**Screen:** Start on the live Code Archaeologist landing page. Keep the 3D excavation viewport visible.

**Narration:**

> Most code analysis tools give you a flat list of warnings. Code Archaeologist treats a repository like an archaeological site. It shows what is worth preserving, which architectural layers are stable, what has fossilized, and where technical debt is creating risk.

**On-screen action:** Move the cursor slowly across the 3D stratigraphy scene without clicking yet.

### 0:12–0:32 — Introduce the product interface

**Screen:** Show the dashboard header, metrics, and the interactive 3D viewport.

**Narration:**

> This is the credential-free product demo for a sample project called `test_project`. The dashboard summarizes files, source lines, artifacts, strata, fossilized code, ruins, and an overall health score. The viewport is a 3D stratigraphy map of the project’s architecture.

**On-screen action:** Briefly point to the health score, strata count, and risk-signal metrics.

### 0:32–0:55 — Demonstrate 3D interaction

**Screen:** Use the pointer to drag across the 3D viewport and orbit the excavation site.

**Narration:**

> I can orbit the site to inspect its depth. Each layer represents a different architectural responsibility, from foundation primitives through the core domain, feature surface, integration boundary, and test stratum.

**On-screen action:** Drag left and right, then slightly up and down. Hover over a layer so its depth and color separation are visible.

### 0:55–1:18 — Surface a finding

**Screen:** Click the `God Class: UserService` marker, then click the `Repository pattern` marker.

**Narration:**

> Findings are attached to the structure instead of being disconnected warnings. This ruin identifies a God Class that combines persistence, validation, caching, orchestration, and notifications. The same excavation also surfaces a positive artifact: a repository pattern that keeps persistence behind a narrow interface.

**On-screen action:** Let the selected-signal readout update after each click. Pause briefly on both states.

### 1:18–1:38 — Explain the model routing

**Screen:** Scroll to the Smart Routing Log or model-routing panel.

**Narration:**

> The analysis uses tiered model routing through Nebius Token Factory. Nemotron Nano handles fast health and hotspot triage. Nemotron Super maps file intent and architectural strata. Nemotron Ultra is reserved for high-value architectural explanations, remediation planning, and evolution forecasting.

**On-screen action:** Point to the Nano, Super, and Ultra rows and their latency/token telemetry.

### 1:38–1:58 — Show findings and filtering

**Screen:** Use the dashboard tabs or filters to show Artifacts, Strata, Fossils, and Ruins.

**Narration:**

> The four finding categories make the report actionable. Artifacts show useful patterns to preserve. Strata show the architecture. Fossils identify stale or dead code. Ruins highlight technical debt and risky boundaries. Judges can filter the findings by category and severity.

**On-screen action:** Click two category tabs or filters. Keep the transitions quick and readable.

### 1:58–2:18 — Open remediation

**Screen:** Click `Generate remediation plan` or the remediation action.

**Narration:**

> The platform does not stop at diagnosis. It turns the highest-value findings into a prioritized remediation plan. For this project, the first step is to split UserService responsibilities, followed by API contract tests and cleanup of fossilized code paths.

**On-screen action:** Open the remediation modal and pause on the three prioritized steps.

### 2:18–2:34 — Show the developer workflow

**Screen:** Open the public GitHub repository README, or show a prepared terminal with the commands already typed but not exposing secrets.

**Narration:**

> The repository includes the CLI, web API, Tree-sitter parsers, deployment files, tests, a sample project, and setup instructions. A developer can run a fast scan or request a deeper excavation and export JSON, Markdown, or HTML reports.

**On-screen action:** Show the public repository URL and briefly highlight the Quick Start commands. Do not spend more than 16 seconds on the README.

### 2:34–2:52 — Nebius and NVIDIA value proposition

**Screen:** Return to the live demo or show the model-routing section again.

**Narration:**

> Nemotron provides the reasoning tiers, while Token Factory makes the workflow practical by using fast passes for broad triage and reserving deeper reasoning for the findings that need it most. The result is an explainable code archaeology workflow rather than another static warning list.

### 2:52–2:58 — Closing

**Screen:** Return to the top of the live demo with the 3D viewport visible.

**Narration:**

> This is Code Archaeologist: excavate the story inside your codebase, preserve what works, and rebuild what has become a ruin.

**On-screen action:** Hold on the live demo for the final two seconds, then end the recording.

## Optional shorter closing if the recording is running long

> Code Archaeologist combines Tree-sitter structure, tiered Nemotron reasoning, and Nebius Token Factory routing to turn a repository into an explainable architectural map.

## Final pre-upload checklist

- [ ] Total runtime is below 3:00; target 2:40–2:55.
- [ ] The live project is shown functioning on the target device.
- [ ] The 3D viewport is visibly orbited and at least one finding marker is clicked.
- [ ] Nemotron and Nebius Token Factory usage is explained on screen or in narration.
- [ ] The public repository and README are shown briefly.
- [ ] No API key, `.env` file, private URL, personal notification, or account detail is visible.
- [ ] No third-party trademarks are shown unnecessarily.
- [ ] Music is original, royalty-free, or omitted.
- [ ] The final video is uploaded publicly to YouTube.
- [ ] The YouTube URL is added to the hackathon submission form.
