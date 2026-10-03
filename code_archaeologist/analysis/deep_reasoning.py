from __future__ import annotations

import json
from typing import Any

from code_archaeologist.core.nebius_client import NebiusClient, ModelTier
from code_archaeologist.models.findings import Artifact, Fossil, Ruin, Stratum


class DeepReasoningEngine:
    def __init__(self, client: NebiusClient):
        self.client = client

    async def analyze_architecture(
        self,
        artifacts: list[Artifact],
        strata: list[Stratum],
        fossils: list[Fossil],
        ruins: list[Ruin],
        site_context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = self._build_architecture_prompt(artifacts, strata, fossils, ruins, site_context)

        response = await self.client.complete(
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            tier=ModelTier.ULTRA,
            temperature=0.2,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse reasoning response", "raw": response.content}

    async def generate_remediation_plan(
        self,
        ruins: list[Ruin],
        strata: list[Stratum],
        site_context: dict[str, Any],
    ) -> dict[str, Any]:
        critical_ruins = [r for r in ruins if r.severity.value in ("critical", "high")]

        prompt = f"""
Analyze these critical architectural ruins and create a prioritized remediation plan:

CRITICAL RUINS:
{self._format_ruins(critical_ruins)}

STRATA CONTEXT:
{self._format_strata(strata)}

SITE CONTEXT:
{json.dumps(site_context, indent=2)}

Provide a JSON response with:
1. "priority_order": list of ruin IDs in remediation priority order
2. "phases": list of remediation phases with:
   - "phase": number
   - "name": descriptive name
   - "ruins": list of ruin IDs
   - "estimated_effort": "trivial|small|medium|large|epic"
   - "dependencies": list of phase numbers that must complete first
   - "risk_mitigation": string
3. "architectural_vision": string describing target architecture
4. "quick_wins": list of ruin IDs that can be fixed quickly
5. "strategic_investments": list of ruin IDs requiring significant investment
"""
        response = await self.client.complete(
            messages=[
                {"role": "system", "content": self._get_remediation_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            tier=ModelTier.ULTRA,
            temperature=0.3,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse remediation plan", "raw": response.content}

    async def explain_finding(self, finding: Artifact | Fossil | Ruin, context: dict[str, Any]) -> str:
        finding_type = type(finding).__name__
        finding_json = json.dumps(finding.to_dict() if hasattr(finding, 'to_dict') else finding.__dict__, indent=2)

        prompt = f"""
Explain this {finding_type} finding in plain language for a developer:

FINDING:
{finding_json}

CONTEXT:
{json.dumps(context, indent=2)}

Provide:
1. What this means in practical terms
2. Why it matters (business/technical impact)
3. Concrete examples of problems it causes
4. Specific steps to address it
5. Related patterns/best practices

Keep it concise but thorough. Use developer-friendly language.
"""
        response = await self.client.complete(
            messages=[
                {"role": "system", "content": "You are a senior software architect explaining code findings to developers."},
                {"role": "user", "content": prompt},
            ],
            tier=ModelTier.SUPER,
            temperature=0.4,
            max_tokens=2048,
        )

        return response.content

    async def predict_evolution(
        self,
        strata: list[Stratum],
        artifacts: list[Artifact],
        site_context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = f"""
Predict how this codebase architecture will evolve over the next 6-12 months:

CURRENT STRATA:
{self._format_strata(strata)}

KEY ARTIFACTS (patterns/conventions):
{self._format_artifacts(artifacts)}

SITE CONTEXT:
{json.dumps(site_context, indent=2)}

Provide JSON with:
1. "trajectory": "improving|stable|degrading|critical"
2. "predicted_ruins": list of likely new ruin types with probabilities
3. "stratum_evolution": dict mapping stratum types to predicted changes
4. "recommended_investments": list of areas to proactively improve
5. "risk_factors": list of architectural risks with likelihood/impact
6. "modernization_opportunities": list of opportunities with effort/value
"""
        response = await self.client.complete(
            messages=[
                {"role": "system", "content": "You are a software architecture futurist predicting codebase evolution."},
                {"role": "user", "content": prompt},
            ],
            tier=ModelTier.ULTRA,
            temperature=0.4,
            max_tokens=3072,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse prediction", "raw": response.content}

    def _get_system_prompt(self) -> str:
        return """You are an expert software archaeologist and architect. You analyze codebases as archaeological sites, discovering:
- ARTIFACTS: Patterns, idioms, conventions, abstractions (positive findings)
- STRATA: Architectural layers with stability/cohesion metrics
- FOSSILS: Dead code, stale modules, deprecated APIs (negative findings)
- RUINS: Technical debt, anti-patterns, architectural violations (critical findings)

Provide deep architectural reasoning. Output valid JSON only."""

    def _get_remediation_system_prompt(self) -> str:
        return """You are a principal architect creating remediation plans for technical debt.
Prioritize by: business impact, risk reduction, effort, dependencies.
Output valid JSON only."""

    def _build_architecture_prompt(
        self,
        artifacts: list[Artifact],
        strata: list[Stratum],
        fossils: list[Fossil],
        ruins: list[Ruin],
        site_context: dict[str, Any],
    ) -> str:
        return f"""
Perform deep architectural analysis of this excavated codebase:

SITE CONTEXT:
{json.dumps(site_context, indent=2)}

ARTIFACTS ({len(artifacts)} total):
{self._format_artifacts(artifacts[:20])}

STRATA ({len(strata)} layers):
{self._format_strata(strata)}

FOSSILS ({len(fossils)} total):
{self._format_fossils(fossils[:15])}

RUINS ({len(ruins)} total):
{self._format_ruins(ruins[:20])}

Provide JSON analysis with:
1. "architectural_style": identified style (layered, hexagonal, microservices, monolith, etc.)
2. "health_score": 0-100 overall architectural health
3. "dominant_patterns": top 5 patterns with confidence
4. "architectural_smells": list of systemic issues
5. "boundary_violations": stratum boundary violations detected
6. "coupling_analysis": coupling hotspots and recommendations
7. "cohesion_analysis": low cohesion areas
8. "technical_debt_index": 0-100 debt score with breakdown
9. "modernization_readiness": 0-100 with blockers
10. "key_insights": list of 5-7 most important findings
11. "strategic_recommendations": list of 3-5 high-impact actions
"""

    def _format_artifacts(self, artifacts: list[Artifact]) -> str:
        return "\n".join([
            f"  - {a.type.value}: {a.name} (confidence: {a.confidence:.2f}) - {a.reasoning[:100]}"
            for a in artifacts
        ])

    def _format_strata(self, strata: list[Stratum]) -> str:
        return "\n".join([
            f"  - {s.type.value}: {len(s.files)} files, stability={s.stability_score:.2f}, coupling={s.coupling_score:.1f}, cohesion={s.cohesion_score:.2f}"
            for s in strata
        ])

    def _format_fossils(self, fossils: list[Fossil]) -> str:
        return "\n".join([
            f"  - {f.type.value}: {f.name} (age: {f.estimated_age_days}d, severity: {f.severity.value})"
            for f in fossils
        ])

    def _format_ruins(self, ruins: list[Ruin]) -> str:
        return "\n".join([
            f"  - {r.type.value}: {r.name} (severity: {r.severity.value}, effort: {r.effort_estimate}) - {r.reasoning[:80]}"
            for r in ruins
        ])