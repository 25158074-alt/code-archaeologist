from __future__ import annotations

import json
from typing import Any

from code_archaeologist.core.nebius_client import NebiusClient, ModelTier
from code_archaeologist.models.findings import Artifact, Fossil, Ruin, Stratum
from code_archaeologist.parsers.treesitter_parsers import ParsedFile


class FastAnalysisEngine:
    def __init__(self, client: NebiusClient):
        self.client = client

    async def quick_scan(self, parsed_files: dict[str, ParsedFile]) -> dict[str, Any]:
        summary = self._generate_summary(parsed_files)
        health = await self._assess_health(summary)
        hotspots = await self._identify_hotspots(parsed_files)
        recommendations = await self._quick_recommendations(summary, hotspots)

        return {
            "summary": summary,
            "health_score": health,
            "hotspots": hotspots,
            "quick_recommendations": recommendations,
        }

    def _generate_summary(self, parsed_files: dict[str, ParsedFile]) -> dict[str, Any]:
        languages = {}
        total_loc = 0
        total_complexity = 0
        total_functions = 0
        total_classes = 0

        for parsed in parsed_files.values():
            lang = parsed.language
            if lang not in languages:
                languages[lang] = {"files": 0, "loc": 0, "complexity": 0}
            languages[lang]["files"] += 1
            languages[lang]["loc"] += parsed.lines_of_code
            languages[lang]["complexity"] += parsed.complexity
            total_loc += parsed.lines_of_code
            total_complexity += parsed.complexity
            total_functions += len(parsed.functions)
            total_classes += len(parsed.classes)

        return {
            "total_files": len(parsed_files),
            "total_lines_of_code": total_loc,
            "total_complexity": total_complexity,
            "avg_complexity_per_file": total_complexity / len(parsed_files) if parsed_files else 0,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "languages": languages,
        }

    async def _assess_health(self, summary: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
Quickly assess codebase health from these metrics:

{json.dumps(summary, indent=2)}

Provide JSON with:
1. "overall_score": 0-100
2. "complexity_score": 0-100
3. "size_score": 0-100
4. "structure_score": 0-100
5. "risk_level": "low|medium|high|critical"
6. "top_concerns": list of 3 strings
"""
        response = await self.client.complete(
            messages=[
                {"role": "system", "content": "You are a code health assessor. Be concise. Output JSON only."},
                {"role": "user", "content": prompt},
            ],
            tier=ModelTier.NANO,
            temperature=0.3,
            max_tokens=512,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"overall_score": 50, "risk_level": "medium", "error": "Parse failed"}

    async def _identify_hotspots(self, parsed_files: dict[str, ParsedFile]) -> list[dict[str, Any]]:
        sorted_files = sorted(
            parsed_files.items(),
            key=lambda x: x[1].complexity,
            reverse=True
        )[:10]

        hotspots = []
        for rel_path, parsed in sorted_files:
            if parsed.complexity > 20:
                hotspots.append({
                    "file": rel_path,
                    "complexity": parsed.complexity,
                    "lines": parsed.lines_of_code,
                    "functions": len(parsed.functions),
                    "classes": len(parsed.classes),
                    "language": parsed.language,
                })

        return hotspots

    async def _quick_recommendations(
        self,
        summary: dict[str, Any],
        hotspots: list[dict[str, Any]],
    ) -> list[str]:
        prompt = f"""
Give 5 quick actionable recommendations for this codebase:

SUMMARY:
{json.dumps(summary, indent=2)}

HOTSPOTS:
{json.dumps(hotspots[:5], indent=2)}

Output JSON array of 5 strings, each a specific actionable recommendation.
"""
        response = await self.client.complete(
            messages=[
                {"role": "system", "content": "Senior dev giving quick wins. Output JSON array only."},
                {"role": "user", "content": prompt},
            ],
            tier=ModelTier.NANO,
            temperature=0.5,
            max_tokens=512,
            response_format={"type": "json_object"},
        )

        try:
            data = json.loads(response.content)
            return data if isinstance(data, list) else data.get("recommendations", [])
        except json.JSONDecodeError:
            return [
                "Add type hints to improve maintainability",
                "Extract long methods into smaller functions",
                "Remove dead code identified in analysis",
                "Standardize error handling patterns",
                "Add integration tests for critical paths",
            ]

    async def analyze_file_intent(self, parsed: ParsedFile) -> dict[str, Any]:
        content_preview = parsed.content[:3000]

        prompt = f"""
Analyze this {parsed.language} file's intent and design:

FILE: {parsed.path}
LINES: {parsed.lines_of_code}
FUNCTIONS: {len(parsed.functions)}
CLASSES: {len(parsed.classes)}
COMPLEXITY: {parsed.complexity}

CONTENT PREVIEW:
{content_preview}

Output JSON with:
1. "primary_purpose": one sentence
2. "design_patterns": list of detected patterns
3. "responsibilities": list of key responsibilities
4. "coupling_indicators": list of external dependencies
5. "quality_concerns": list of issues
6. "refactoring_suggestions": list of specific improvements
"""
        response = await self.client.complete(
            messages=[
                {"role": "system", "content": "Code analyzer. Output JSON only."},
                {"role": "user", "content": prompt},
            ],
            tier=ModelTier.SUPER,
            temperature=0.3,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse", "primary_purpose": "Unknown"}

    async def batch_analyze_intents(
        self,
        parsed_files: dict[str, ParsedFile],
        file_paths: list[str],
    ) -> dict[str, dict[str, Any]]:
        results = {}
        for path in file_paths:
            if path in parsed_files:
                results[path] = await self.analyze_file_intent(parsed_files[path])
        return results

    async def suggest_refactoring(self, ruin: Ruin, context: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
Suggest specific refactoring for this ruin:

RUIN:
- Type: {ruin.type.value}
- Name: {ruin.name}
- Description: {ruin.description}
- Severity: {ruin.severity.value}
- Locations: {[f"{l.file_path}:{l.start_line}-{l.end_line}" for l in ruin.locations]}
- Metrics: {json.dumps(ruin.metrics)}
- Current Reasoning: {ruin.reasoning}

CONTEXT:
{json.dumps(context, indent=2)}

Output JSON with:
1. "refactoring_type": specific refactoring name
2. "steps": list of concrete steps
3. "code_example_before": string
4. "code_example_after": string
5. "tests_needed": list of test types
6. "risk_level": "low|medium|high"
7. "estimated_hours": number
"""
        response = await self.client.complete(
            messages=[
                {"role": "system", "content": "Refactoring expert. Give concrete, actionable steps. Output JSON only."},
                {"role": "user", "content": prompt},
            ],
            tier=ModelTier.SUPER,
            temperature=0.4,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse refactoring suggestion"}

    async def generate_documentation(self, parsed: ParsedFile, style: str = "docstring") -> str:
        content_preview = parsed.content[:2000]

        prompt = f"""
Generate {style} documentation for this {parsed.language} file:

FILE: {parsed.path}
FUNCTIONS: {[f['name'] for f in parsed.functions]}
CLASSES: {[c['name'] for c in parsed.classes]}

CONTENT:
{content_preview}

Generate clear, useful documentation following {style} conventions.
"""
        response = await self.client.complete(
            messages=[
                {"role": "system", "content": f"Documentation generator. Produce {style} format."},
                {"role": "user", "content": prompt},
            ],
            tier=ModelTier.NANO,
            temperature=0.3,
            max_tokens=1024,
        )

        return response.content