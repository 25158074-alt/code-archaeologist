from __future__ import annotations

import asyncio
import hashlib
import re
import itertools
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import networkx as nx
from git import Repo

from code_archaeologist.core.config import get_settings
from code_archaeologist.core.nebius_client import NebiusClient, ModelTier
from code_archaeologist.models.findings import (
    Artifact,
    ArtifactType,
    ExcavationReport,
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
        self._site_path: Path | None = None
        self.artifacts: list[Artifact] = []
        self.strata: list[Stratum] = []
        self.fossils: list[Fossil] = []
        self.ruins: list[Ruin] = []

    EXCLUDED_DIRS = {
        ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__",
        "site-packages", "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
        ".cache", "target", "vendor", ".idea", ".vscode",
    }
    SOURCE_EXTENSIONS = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs")

    @staticmethod
    def _stable_id(kind: str, name: str, locations: list[Location]) -> str:
        key = "|".join([kind, name] + [f"{l.file_path}:{l.start_line}-{l.end_line}" for l in locations])
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]

    async def excavate(self, path: str | Path) -> dict[str, Any]:
        site_path = Path(path).resolve()
        site_name = site_path.name

        print(f"[*] Beginning excavation of {site_name} at {site_path}")

        await self._initialize_git(site_path)
        await self._discover_and_parse(site_path)
        await self._build_dependency_graph()
        await self._analyze_git_history()

        self.artifacts = await self._discover_artifacts()
        self.strata = await self._identify_strata()
        self.fossils = await self._excavate_fossils()
        self.ruins = await self._uncover_ruins()
        self._assign_stable_ids()

        report = self._compile_report(
            site_name, str(site_path), self.artifacts, self.strata, self.fossils, self.ruins
        )
        return report.to_dict()

    def _assign_stable_ids(self) -> None:
        """Deterministic IDs so `explain <id>` works across separate runs."""
        seen: set[str] = set()

        def unique(candidate: str) -> str:
            while candidate in seen:
                candidate = hashlib.sha1(candidate.encode()).hexdigest()[:8]
            seen.add(candidate)
            return candidate

        for a in self.artifacts:
            a.id = unique(self._stable_id(a.type.value, a.name, a.locations))
        for st in self.strata:
            st.id = unique(self._stable_id("stratum", st.name, [Location(f, 0, 0) for f in st.files[:5]]))
        for fo in self.fossils:
            fo.id = unique(self._stable_id(fo.type.value, fo.name, [fo.location] if fo.location else []))
        for r in self.ruins:
            r.id = unique(self._stable_id(r.type.value, r.name, r.locations))

    async def _initialize_git(self, path: Path) -> None:
        try:
            self._git_repo = Repo(path, search_parent_directories=False)
            self._site_path = path
        except Exception:
            self._git_repo = None

    async def _discover_and_parse(self, path: Path) -> None:
        path = Path(path).resolve()
        max_size = self.settings.analysis.max_file_size_kb * 1024
        files = []
        for f in sorted(path.rglob("*")):
            if f.suffix.lower() not in self.SOURCE_EXTENSIONS or not f.is_file():
                continue
            rel_parts = f.relative_to(path).parts[:-1]
            if any(p in self.EXCLUDED_DIRS or p.endswith(".egg-info") for p in rel_parts):
                continue
            try:
                if f.stat().st_size <= max_size:
                    files.append(f)
            except OSError:
                continue

        print(f"[*] Parsing {len(files)} source files...")

        semaphore = asyncio.Semaphore(self.settings.analysis.parallel_workers)

        def parse_sync(file_path: Path) -> None:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            parser = get_parser_for_file(str(file_path))
            if parser:
                rel_path = file_path.relative_to(path).as_posix()
                self.parsed_files[rel_path] = parser.parse(content, rel_path)

        async def parse_file(file_path: Path):
            async with semaphore:
                try:
                    await asyncio.to_thread(parse_sync, file_path)
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
        """Best-effort resolution of an import statement to a parsed file."""
        text = import_text.strip()
        modules: list[str] = []
        if text.startswith("from "):
            m = re.match(r"from\s+(\.*)([\w.]*)\s+import\s+(.+)", text, re.DOTALL)
            if not m:
                return None
            dots, module, names = m.groups()
            base = module
            if dots:
                base_dir = Path(from_file).parent
                for _ in range(len(dots) - 1):
                    base_dir = base_dir.parent
                prefix = base_dir.as_posix()
                prefix = "" if prefix == "." else prefix + "/"
                if module:
                    modules.append(prefix + module.replace(".", "/"))
                for name in re.findall(r"\w+", names):
                    modules.append(prefix + (module.replace(".", "/") + "/" if module else "") + name)
            else:
                modules.append(base.replace(".", "/"))
                for name in re.findall(r"\w+", names):
                    modules.append(base.replace(".", "/") + "/" + name)
        elif text.startswith("import "):
            for part in text[len("import "):].split(","):
                name = part.strip().split(" as ")[0].split()[0] if part.strip() else ""
                if name:
                    modules.append(name.replace(".", "/"))
        else:
            return None

        # Also try relative to the importing file's directory (sibling modules).
        sibling_dir = Path(from_file).parent.as_posix()
        sibling_dir = "" if sibling_dir == "." else sibling_dir + "/"
        candidates_roots = modules + [sibling_dir + m for m in modules if not m.startswith(sibling_dir)]
        for module in candidates_roots:
            for ext in (".py", ".js", ".ts", ".go", ".rs"):
                for candidate in (f"{module}{ext}", f"{module}/__init__{ext}", f"{module}/index{ext}"):
                    if candidate in self.parsed_files and candidate != from_file:
                        return candidate
        return None

    async def _analyze_git_history(self) -> None:
        if not self._git_repo:
            return

        for rel_path in self.parsed_files:
            try:
                abs_path = str((self._site_path / rel_path).resolve()) if self._site_path else rel_path
                commits = list(self._git_repo.iter_commits(paths=abs_path, max_count=1))
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
        parts = {part.lower() for part in Path(rel_path).parts}

        if parts & {"test", "tests", "spec", "__tests__"}:
            return StratumType.TEST
        if parts & {"infra", "infrastructure", "deploy", "docker", "k8s", "terraform", "ansible"}:
            return StratumType.INFRASTRUCTURE
        if parts & {"api", "routes", "route", "endpoint", "controller", "handlers", "handler"}:
            return StratumType.PRESENTATION
        if parts & {"service", "services", "usecase", "usecases", "interactor", "business"}:
            return StratumType.CORE
        if parts & {"model", "models", "entity", "entities", "domain", "schema", "schemas", "dto"}:
            return StratumType.FOUNDATION
        if parts & {"client", "clients", "adapter", "adapters", "gateway", "gateways", "integration", "integrations", "external"}:
            return StratumType.INTEGRATION
        if parts & {"feature", "features", "module", "modules", "component", "components", "plugin", "plugins"}:
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
            coupling_score=max(0.0, min(1.0, avg_coupling / max(len(self.parsed_files), 1))),
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
        return await asyncio.to_thread(self._find_dead_code_sync)

    def _find_dead_code_sync(self) -> list[Fossil]:
        fossils: list[Fossil] = []
        ignored = {"main", "setUp", "tearDown"}

        # Count textual call/reference sites for every identifier across the codebase.
        reference_counts: Counter[str] = Counter()
        for parsed in self.parsed_files.values():
            reference_counts.update(re.findall(r"[A-Za-z_]\w*", parsed.content))

        # Each definition contributes exactly one occurrence of its own name.
        definition_counts: Counter[str] = Counter()
        for parsed in self.parsed_files.values():
            for func in parsed.functions:
                definition_counts[func["name"]] += 1

        for rel_path, parsed in self.parsed_files.items():
            for func in parsed.functions:
                name = func["name"]
                if name in ignored or (name.startswith("__") and name.endswith("__")):
                    continue
                if name.startswith("test") or any(d.startswith("@") for d in func.get("decorators", [])):
                    continue
                if reference_counts[name] > definition_counts[name]:
                    continue
                fossils.append(Fossil(
                    type=FossilType.DEAD_CODE,
                    name=f"Dead Function: {name}",
                    description="Function appears to never be called",
                    location=Location(
                        file_path=rel_path,
                        start_line=func["start_line"],
                        end_line=func["end_line"],
                    ),
                    severity=Severity.MEDIUM,
                    reasoning="No references to this name were found outside its definition",
                    remediation="Verify if function is truly unused; remove if confirmed dead",
                ))
                if len(fossils) >= 20:
                    return fossils

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
            cycles = await asyncio.to_thread(lambda: list(itertools.islice(nx.simple_cycles(self.file_graph), 10)))
            for cycle in cycles:
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
        return await asyncio.to_thread(self._find_copy_paste_sync)

    def _find_copy_paste_sync(self) -> list[Ruin]:
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
    ) -> ExcavationReport:
        report = ExcavationReport(
            site_name=site_name,
            site_path=site_path,
            artifacts=artifacts,
            strata=strata,
            fossils=fossils,
            ruins=ruins,
            summary={
                "total_files": len(self.parsed_files),
                "total_files_analyzed": len(self.parsed_files),
                "total_functions": sum(len(p.functions) for p in self.parsed_files.values()),
                "total_classes": sum(len(p.classes) for p in self.parsed_files.values()),
                "total_lines_of_code": sum(p.lines_of_code for p in self.parsed_files.values()),
                "languages": list(set(p.language for p in self.parsed_files.values())),
                "artifact_counts": dict(Counter(a.type.value for a in artifacts)),
                "stratum_counts": dict(Counter(s.type.value for s in strata)),
                "fossil_counts": dict(Counter(f.type.value for f in fossils)),
                "ruin_counts": dict(Counter(r.type.value for r in ruins)),
                "ruin_severity": dict(Counter(r.severity.value for r in ruins)),
            },
        )

        return report
