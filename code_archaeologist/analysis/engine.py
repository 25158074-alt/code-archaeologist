from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
from git import Repo
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

from code_archaeologist.core.config import get_settings
from code_archaeologist.core.nebius_client import NebiusClient, ModelTier
from code_archaeologist.models.findings import (
    Artifact,
    ArtifactType,
    Fossil,
    FossilType,
    Location,
    Ruin,
    RuinType,
    Severity,
    Stratum,
    StratumType,
)
from code_archaeologist.parsers.treesitter_parsers import ParsedFile, get_parser_for_file


class ExcavationEngine:
    def __init__(self, client: NebiusClient | None = None):
        self.client = client
        self.settings = get_settings()
        self.parsed_files: dict[str, ParsedFile] = {}
        self.file_graph: nx.DiGraph = nx.DiGraph()
        self._git_repo: Repo | None = None

    async def excavate(self, path: str | Path) -> dict[str, Any]:
        site_path = Path(path).resolve()
        site_name = site_path.name

        print(f"[*] Beginning excavation of {site_name} at {site_path}")

        await self._initialize_git(site_path)
        await self._discover_and_parse(site_path)
        await self._build_dependency_graph()
        await self._analyze_git_history()

        artifacts = await self._discover_artifacts()
        strata = await self._identify_strata()
        fossils = await self._excavate_fossils()
        ruins = await self._uncover_ruins()

        report = self._compile_report(site_name, str(site_path), artifacts, strata, fossils, ruins)
        return report.to_dict()

    async def _initialize_git(self, path: Path) -> None:
        try:
            self._git_repo = Repo(path, search_parent_directories=True)
        except Exception:
            self._git_repo = None

    async def _discover_and_parse(self, path: Path) -> None:
        files = []
        for ext in [".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs"]:
            files.extend(path.rglob(f"*{ext}"))

        max_size = self.settings.analysis.max_file_size_kb * 1024
        files = [f for f in files if f.stat().st_size <= max_size]

        print(f"[*] Parsing {len(files)} source files...")

        semaphore = asyncio.Semaphore(self.settings.analysis.parallel_workers)

        async def parse_file(file_path: Path):
            async with semaphore:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    parser = get_parser_for_file(str(file_path))
                    if parser:
                        rel_path = file_path.relative_to(path).as_posix()
                        parsed = parser.parse(content, rel_path)
                        self.parsed_files[rel_path] = parsed
                except Exception as e:
                    print(f"[WARN] Failed to parse {file_path}: {e}")

        await asyncio.gather(*[parse_file(f) for f in files])

    async def _build_dependency_graph(self) -> None:
        self.file_graph.clear()

        for rel_path, parsed in self.parsed_files.items():
            self.file_graph.add_node(rel_path, parsed=parsed)

        for rel_path, parsed in self.parsed_files.items():
            for imp in parsed.imports:
                imported = self._resolve_import(imp["text"], rel_path)
                if imported and imported in self.parsed_files:
                    self.file_graph.add_edge(rel_path, imported)

    def _resolve_import(self, import_text: str, from_file: str) -> str | None:
        import_text = import_text.strip()
        if import_text.startswith(("import ", "from ")):
            parts = import_text.replace("from ", "").replace("import ", "").split()
            if parts:
                module = parts[0].replace(".", "/")
                base_dir = Path(from_file).parent
                for ext in [".py", ".js", ".ts", ".go", ".rs"]:
                    candidate = (base_dir / f"{module}{ext}").as_posix()
                    if candidate in self.parsed_files:
                        return candidate
                    candidate = (base_dir / module / f"__init__{ext}").as_posix()
                    if candidate in self.parsed_files:
                        return candidate
        return None

    async def _analyze_git_history(self) -> None:
        if not self._git_repo:
            return

        for rel_path in self.parsed_files:
            try:
                commits = list(self._git_repo.iter_commits(paths=rel_path, max_count=1))
                if commits:
                    last_commit = commits[0]
                    self.parsed_files[rel_path].last_modified = datetime.fromtimestamp(
                        last_commit.committed_date
                    )
                    self.parsed_files[rel_path].author = last_commit.author.name
            except Exception:
                pass

    async def _discover_artifacts(self) -> list[Artifact]:
        artifacts = []

        pattern_artifacts = await self._find_patterns()
        artifacts.extend(pattern_artifacts)

        idiom_artifacts = await self._find_idioms()
        artifacts.extend(idiom_artifacts)

        convention_artifacts = await self._find_conventions()
        artifacts.extend(convention_artifacts)

        abstraction_artifacts = await self._find_abstractions()
        artifacts.extend(abstraction_artifacts)

        return artifacts

    async def _find_patterns(self) -> list[Artifact]:
        artifacts = []

        pattern_signatures = {
            "factory": ["create", "make", "build", "factory"],
            "singleton": ["instance", "get_instance", "_instance"],
            "observer": ["subscribe", "notify", "observer", "listener"],
            "strategy": ["strategy", "policy", "algorithm"],
            "decorator": ["decorator", "wrap", "wrapper"],
            "adapter": ["adapter", "adapt", "convert"],
            "facade": ["facade", "simplify", "unified"],
            "repository": ["repository", "find_by", "save", "delete"],
            "unit_of_work": ["unit_of_work", "commit", "rollback"],
            "circuit_breaker": ["circuit_breaker", "failure_threshold", "timeout"],
        }

        for rel_path, parsed in self.parsed_files.items():
            content_lower = parsed.content.lower()

            for pattern_name, keywords in pattern_signatures.items():
                matches = sum(1 for kw in keywords if kw in content_lower)
                if matches >= 2:
                    confidence = min(0.5 + (matches * 0.1), 0.95)
                    if confidence >= self.settings.analysis.min_artifact_confidence:
                        artifacts.append(Artifact(
                            type=ArtifactType.PATTERN,
                            name=f"{pattern_name.capitalize()} Pattern",
                            description=f"Detected {pattern_name} pattern implementation",
                            locations=[Location(
                                file_path=rel_path,
                                start_line=1,
                                end_line=parsed.lines_of_code,
                            )],
                            confidence=confidence,
                            tier="nano",
                            reasoning=f"Found {matches} pattern keywords: {', '.join(keywords[:matches])}",
                        ))

        return artifacts

    async def _find_idioms(self) -> list[Artifact]:
        artifacts = []
        language_idioms = {
            "python": [
                ("context_manager", "__enter__", "__exit__"),
                ("property", "@property"),
                ("dataclass", "@dataclass"),
                ("protocol", "Protocol"),
                ("type_hints", "typing."),
            ],
            "javascript": [
                ("async_await", "async ", "await "),
                ("destructuring", "const {", "const ["),
                ("modules", "export ", "import "),
                ("arrow_functions", "=>"),
            ],
            "typescript": [
                ("generics", "<T>"),
                ("interfaces", "interface "),
                ("type_guards", "is "),
                ("mapped_types", "keyof "),
            ],
            "go": [
                ("error_handling", "if err != nil"),
                ("interfaces", "interface{}"),
                ("goroutines", "go "),
                ("channels", "chan "),
            ],
            "rust": [
                ("result_handling", "Result<", "Option<"),
                ("pattern_matching", "match "),
                ("traits", "trait "),
                ("lifetimes", "'a"),
            ],
        }

        for rel_path, parsed in self.parsed_files.items():
            idioms = language_idioms.get(parsed.language, [])
            for idiom_name, *markers in idioms:
                if all(marker in parsed.content for marker in markers):
                    artifacts.append(Artifact(
                        type=ArtifactType.IDIOM,
                        name=idiom_name.replace("_", " ").title(),
                        description=f"Codebase uses {idiom_name.replace('_', ' ')} idiom",
                        locations=[Location(file_path=rel_path, start_line=1, end_line=10)],
                        confidence=0.8,
                        tier="nano",
                        reasoning=f"Found idiom markers: {', '.join(markers)}",
                    ))

        return artifacts

    async def _find_conventions(self) -> list[Artifact]:
        artifacts = []

        naming_patterns = Counter()
        for rel_path, parsed in self.parsed_files.items():
            for func in parsed.functions:
                naming_patterns[func["name"]] += 1
            for cls in parsed.classes:
                naming_patterns[cls["name"]] += 1

        common_prefixes = Counter()
        for name, count in naming_patterns.items():
            if count >= 3:
                parts = name.split("_")
                if len(parts) > 1:
                    common_prefixes[parts[0]] += count

        for prefix, count in common_prefixes.most_common(10):
            if count >= 5:
                artifacts.append(Artifact(
                    type=ArtifactType.CONVENTION,
                    name=f"{prefix}_* Convention",
                    description=f"Naming convention: {prefix}_* used {count} times",
                    locations=[],
                    confidence=min(0.6 + count * 0.02, 0.9),
                    tier="nano",
                    reasoning=f"Prefix '{prefix}' appears in {count} identifiers",
                ))

        return artifacts

    async def _find_abstractions(self) -> list[Artifact]:
        artifacts = []

        abstract_classes = []
        interfaces = []
        protocols = []

        for rel_path, parsed in self.parsed_files.items():
            for cls in parsed.classes:
                cls_name = cls["name"].lower()
                if any(kw in cls_name for kw in ["abstract", "base", "interface", "protocol"]):
                    abstract_classes.append((rel_path, cls))
                if parsed.language in ("typescript", "go", "rust") and "interface" in cls.get("type", "").lower():
                    interfaces.append((rel_path, cls))
                if parsed.language == "python" and "protocol" in str(cls.get("bases", [])).lower():
                    protocols.append((rel_path, cls))

        for rel_path, cls in abstract_classes:
            artifacts.append(Artifact(
                type=ArtifactType.ABSTRACTION,
                name=f"Abstract Base: {cls['name']}",
                description="Abstract base class providing common interface",
                locations=[Location(file_path=rel_path, start_line=cls["start_line"], end_line=cls["end_line"])],
                confidence=0.85,
                tier="super",
                reasoning="Class name suggests abstraction role",
            ))

        return artifacts

    async def _identify_strata(self) -> list[Stratum]:
        strata = []

        layer_files = defaultdict(list)
        for rel_path, parsed in self.parsed_files.items():
            layer = self._classify_layer(rel_path, parsed)
            layer_files[layer].append(rel_path)

        for layer_type, files in layer_files.items():
            if len(files) >= self.settings.analysis.min_strata_size:
                stratum = await self._analyze_stratum(layer_type, files)
                strata.append(stratum)

        return strata

    def _classify_layer(self, rel_path: str, parsed: ParsedFile) -> StratumType:
        path_lower = rel_path.lower()

        if any(x in path_lower for x in ["test", "spec", "__test__"]):
            return StratumType.TEST
        if any(x in path_lower for x in ["infra", "deploy", "docker", "k8s", "terraform", "ansible"]):
            return StratumType.INFRASTRUCTURE
        if any(x in path_lower for x in ["api", "route", "endpoint", "controller", "handler"]):
            return StratumType.PRESENTATION
        if any(x in path_lower for x in ["service", "usecase", "interactor", "business"]):
            return StratumType.CORE
        if any(x in path_lower for x in ["model", "entity", "domain", "schema", "dto"]):
            return StratumType.FOUNDATION
        if any(x in path_lower for x in ["client", "adapter", "gateway", "integration", "external"]):
            return StratumType.INTEGRATION
        if any(x in path_lower for x in ["feature", "module", "component", "plugin"]):
            return StratumType.FEATURE

        return StratumType.UNKNOWN

    async def _analyze_stratum(self, layer_type: StratumType, files: list[str]) -> Stratum:
        artifacts_in_stratum = []
        total_complexity = 0
        total_coupling = 0

        for rel_path in files:
            parsed = self.parsed_files[rel_path]
            total_complexity += parsed.complexity
            total_coupling += self.file_graph.out_degree(rel_path) + self.file_graph.in_degree(rel_path)

        avg_complexity = total_complexity / len(files) if files else 0
        avg_coupling = total_coupling / len(files) if files else 0

        stability = max(0.0, 1.0 - (avg_coupling / max(len(files), 1)))
        cohesion = max(0.0, 1.0 - (avg_complexity / 100))

        return Stratum(
            type=layer_type,
            name=layer_type.value.title(),
            description=f"{layer_type.value.title()} layer with {len(files)} files",
            files=files,
            depth=self._get_layer_depth(layer_type),
            stability_score=stability,
            coupling_score=avg_coupling,
            cohesion_score=cohesion,
        )

    def _get_layer_depth(self, layer: StratumType) -> int:
        depths = {
            StratumType.FOUNDATION: 0,
            StratumType.CORE: 1,
            StratumType.FEATURE: 2,
            StratumType.INTEGRATION: 2,
            StratumType.PRESENTATION: 3,
            StratumType.TEST: 4,
            StratumType.INFRASTRUCTURE: 5,
            StratumType.UNKNOWN: 10,
        }
        return depths.get(layer, 10)

    async def _excavate_fossils(self) -> list[Fossil]:
        fossils = []
        now = datetime.now()
        threshold = timedelta(days=self.settings.analysis.fossil_threshold_days)

        for rel_path, parsed in self.parsed_files.items():
            if hasattr(parsed, "last_modified") and parsed.last_modified:
                age = now - parsed.last_modified
                if age > threshold:
                    fossils.append(Fossil(
                        type=FossilType.ORPHANED_MODULE,
                        name=f"Stale Module: {rel_path}",
                        description=f"Not modified for {age.days} days",
                        location=Location(file_path=rel_path, start_line=1, end_line=parsed.lines_of_code),
                        last_modified=parsed.last_modified,
                        estimated_age_days=age.days,
                        severity=Severity.LOW if age.days < 365 else Severity.MEDIUM,
                        reasoning=f"Last commit by {getattr(parsed, 'author', 'unknown')} on {parsed.last_modified.date()}",
                        remediation="Review if module is still needed; consider archiving or removing",
                    ))

        dead_code_fossils = await self._find_dead_code()
        fossils.extend(dead_code_fossils)

        return fossils

    async def _find_dead_code(self) -> list[Fossil]:
        fossils = []

        all_functions = set()
        called_functions = set()

        for rel_path, parsed in self.parsed_files.items():
            for func in parsed.functions:
                all_functions.add(f"{rel_path}:{func['name']}")

        for rel_path, parsed in self.parsed_files.items():
            content = parsed.content
            for func_name in all_functions:
                short_name = func_name.split(":")[-1]
                if f"{short_name}(" in content and not content.strip().startswith(f"def {short_name}"):
                    called_functions.add(func_name)

        dead_functions = all_functions - called_functions
        for dead_func in list(dead_functions)[:20]:
            file_path, func_name = dead_func.split(":", 1)
            parsed = self.parsed_files.get(file_path)
            if parsed:
                for func in parsed.functions:
                    if func["name"] == func_name:
                        fossils.append(Fossil(
                            type=FossilType.DEAD_CODE,
                            name=f"Dead Function: {func_name}",
                            description=f"Function appears to never be called",
                            location=Location(
                                file_path=file_path,
                                start_line=func["start_line"],
                                end_line=func["end_line"],
                            ),
                            severity=Severity.MEDIUM,
                            reasoning="Static analysis suggests this function is never invoked",
                            remediation="Verify if function is truly unused; remove if confirmed dead",
                        ))
                        break

        return fossils

    async def _uncover_ruins(self) -> list[Ruin]:
        ruins = []

        god_classes = await self._find_god_classes()
        ruins.extend(god_classes)

        long_methods = await self._find_long_methods()
        ruins.extend(long_methods)

        circular_deps = await self._find_circular_dependencies()
        ruins.extend(circular_deps)

        copy_paste = await self._find_copy_paste()
        ruins.extend(copy_paste)

        magic_numbers = await self._find_magic_numbers()
        ruins.extend(magic_numbers)

        spaghetti = await self._find_spaghetti_code()
        ruins.extend(spaghetti)

        return ruins

    async def _find_god_classes(self) -> list[Ruin]:
        ruins = []
        threshold = 20

        for rel_path, parsed in self.parsed_files.items():
            for cls in parsed.classes:
                method_count = len(cls.get("methods", []))
                if method_count >= threshold:
                    ruins.append(Ruin(
                        type=RuinType.GOD_CLASS,
                        name=f"God Class: {cls['name']}",
                        description=f"Class has {method_count} methods (threshold: {threshold})",
                        locations=[Location(
                            file_path=rel_path,
                            start_line=cls["start_line"],
                            end_line=cls["end_line"],
                        )],
                        severity=Severity.HIGH if method_count > 30 else Severity.MEDIUM,
                        metrics={"method_count": method_count, "threshold": threshold},
                        reasoning="Class violates Single Responsibility Principle",
                        remediation="Extract cohesive methods into separate classes; apply SRP",
                        effort_estimate="large" if method_count > 30 else "medium",
                    ))

        return ruins

    async def _find_long_methods(self) -> list[Ruin]:
        ruins = []
        threshold = 50

        for rel_path, parsed in self.parsed_files.items():
            for func in parsed.functions:
                length = func["end_line"] - func["start_line"] + 1
                if length >= threshold:
                    ruins.append(Ruin(
                        type=RuinType.LONG_METHOD,
                        name=f"Long Method: {func['name']}",
                        description=f"Method spans {length} lines (threshold: {threshold})",
                        locations=[Location(
                            file_path=rel_path,
                            start_line=func["start_line"],
                            end_line=func["end_line"],
                        )],
                        severity=Severity.HIGH if length > 100 else Severity.MEDIUM,
                        metrics={"lines": length, "threshold": threshold},
                        reasoning="Method does too much; hard to understand and test",
                        remediation="Extract smaller methods; apply Extract Method refactoring",
                        effort_estimate="medium",
                    ))

        return ruins

    async def _find_circular_dependencies(self) -> list[Ruin]:
        ruins = []

        try:
            cycles = list(nx.simple_cycles(self.file_graph))
            for cycle in cycles[:10]:
                if len(cycle) > 1:
                    ruins.append(Ruin(
                        type=RuinType.CIRCULAR_DEPENDENCY,
                        name=f"Circular Dependency ({len(cycle)} files)",
                        description=" -> ".join(cycle) + " -> " + cycle[0],
                        locations=[Location(file_path=f, start_line=1, end_line=1) for f in cycle],
                        severity=Severity.HIGH,
                        metrics={"cycle_length": len(cycle)},
                        reasoning="Circular dependencies prevent independent deployment and testing",
                        remediation="Introduce interfaces/events to break cycles; apply Dependency Inversion",
                        effort_estimate="large",
                    ))
        except Exception:
            pass

        return ruins

    async def _find_copy_paste(self) -> list[Ruin]:
        ruins = []

        code_blocks = []
        for rel_path, parsed in self.parsed_files.items():
            lines = parsed.content.splitlines()
            for i in range(len(lines) - 5):
                block = "\n".join(lines[i:i+6]).strip()
                if len(block) > 50:
                    hash_val = hashlib.md5(block.encode()).hexdigest()[:12]
                    code_blocks.append((hash_val, rel_path, i+1, i+6, block))

        block_map = defaultdict(list)
        for hash_val, rel_path, start, end, block in code_blocks:
            block_map[hash_val].append((rel_path, start, end))

        for hash_val, occurrences in block_map.items():
            if len(occurrences) >= 3:
                ruins.append(Ruin(
                    type=RuinType.COPY_PASTE,
                    name=f"Duplicated Code Block ({len(occurrences)} occurrences)",
                    description=f"Identical 6-line block found in {len(occurrences)} locations",
                    locations=[Location(file_path=loc[0], start_line=loc[1], end_line=loc[2]) for loc in occurrences],
                    severity=Severity.MEDIUM,
                    metrics={"occurrences": len(occurrences), "block_hash": hash_val},
                    reasoning="Code duplication increases maintenance burden and bug risk",
                    remediation="Extract common logic into shared function/module",
                    effort_estimate="small",
                ))

        return ruins

    async def _find_magic_numbers(self) -> list[Ruin]:
        ruins = []

        for rel_path, parsed in self.parsed_files.items():
            import re
            numbers = re.findall(r'\b\d{2,}\b', parsed.content)
            unique_numbers = set(numbers)
            suspicious = [n for n in unique_numbers if int(n) not in (0, 1, 2, 10, 100, 1000, 1024, 2048, 4096, 8080, 3000, 5000, 8000, 8080, 8888, 9000)]

            if len(suspicious) > 10:
                ruins.append(Ruin(
                    type=RuinType.MAGIC_NUMBERS,
                    name=f"Magic Numbers in {rel_path}",
                    description=f"Found {len(suspicious)} suspicious numeric literals",
                    locations=[Location(file_path=rel_path, start_line=1, end_line=parsed.lines_of_code)],
                    severity=Severity.LOW,
                    metrics={"count": len(suspicious)},
                    reasoning="Hard-coded numbers reduce readability and maintainability",
                    remediation="Extract to named constants with descriptive names",
                    effort_estimate="trivial",
                ))

        return ruins

    async def _find_spaghetti_code(self) -> list[Ruin]:
        ruins = []

        for rel_path, parsed in self.parsed_files.items():
            if parsed.complexity > self.settings.analysis.ruin_complexity_threshold:
                ruins.append(Ruin(
                    type=RuinType.SPAGHETTI_CODE,
                    name=f"Spaghetti Code: {rel_path}",
                    description=f"File has cyclomatic complexity of {parsed.complexity}",
                    locations=[Location(file_path=rel_path, start_line=1, end_line=parsed.lines_of_code)],
                    severity=Severity.HIGH if parsed.complexity > 100 else Severity.MEDIUM,
                    metrics={"complexity": parsed.complexity, "threshold": self.settings.analysis.ruin_complexity_threshold},
                    reasoning="High complexity indicates tangled control flow",
                    remediation="Refactor into smaller functions; reduce nesting; apply Guard Clauses",
                    effort_estimate="medium",
                ))

        return ruins

    def _compile_report(
        self,
        site_name: str,
        site_path: str,
        artifacts: list[Artifact],
        strata: list[Stratum],
        fossils: list[Fossil],
        ruins: list[Ruin],
    ) -> dict:
        from code_archaeologist.models.findings import ExcavationReport

        report = ExcavationReport(
            site_name=site_name,
            site_path=site_path,
            artifacts=artifacts,
            strata=strata,
            fossils=fossils,
            ruins=ruins,
            summary={
                "total_files_analyzed": len(self.parsed_files),
                "total_lines_of_code": sum(p.lines_of_code for p in self.parsed_files.values()),
                "languages": list(set(p.language for p in self.parsed_files.values())),
                "artifact_counts": Counter(a.type.value for a in artifacts),
                "stratum_counts": Counter(s.type.value for s in strata),
                "fossil_counts": Counter(f.type.value for f in fossils),
                "ruin_counts": Counter(r.type.value for r in ruins),
                "ruin_severity": Counter(r.severity.value for r in ruins),
            },
        )

        return report.to_dict()