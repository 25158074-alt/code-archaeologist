from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4


class ArtifactType(str, Enum):
    PATTERN = "pattern"
    ANTI_PATTERN = "anti_pattern"
    IDIOM = "idiom"
    CONVENTION = "convention"
    ABSTRACTION = "abstraction"


class StratumType(str, Enum):
    FOUNDATION = "foundation"
    CORE = "core"
    FEATURE = "feature"
    INTEGRATION = "integration"
    PRESENTATION = "presentation"
    TEST = "test"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


class FossilType(str, Enum):
    DEAD_CODE = "dead_code"
    UNUSED_IMPORT = "unused_import"
    COMMENTED_OUT = "commented_out"
    DEPRECATED_API = "deprecated_api"
    ZOMBIE_TEST = "zombie_test"
    ORPHANED_MODULE = "orphaned_module"


class RuinType(str, Enum):
    GOD_CLASS = "god_class"
    SPAGHETTI_CODE = "spaghetti_code"
    COPY_PASTE = "copy_paste"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    LEAKY_ABSTRACTION = "leaky_abstraction"
    PREMATURE_OPTIMIZATION = "premature_optimization"
    MAGIC_NUMBERS = "magic_numbers"
    LONG_METHOD = "long_method"
    LONG_PARAMETER_LIST = "long_parameter_list"
    SHOTGUN_SURGERY = "shotgun_surgery"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass(slots=True)
class Location:
    file_path: str
    start_line: int
    end_line: int
    start_column: int = 0
    end_column: int = 0


@dataclass(slots=True)
class Artifact:
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    type: ArtifactType = ArtifactType.PATTERN
    name: str = ""
    description: str = ""
    locations: list[Location] = field(default_factory=list)
    confidence: float = 0.0
    tier: Literal["ultra", "super", "nano"] = "super"
    reasoning: str = ""
    discovered_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "locations": [
                {
                    "file": loc.file_path,
                    "lines": f"{loc.start_line}-{loc.end_line}",
                }
                for loc in self.locations
            ],
            "confidence": self.confidence,
            "tier": self.tier,
            "reasoning": self.reasoning,
            "discovered_at": self.discovered_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class Stratum:
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    type: StratumType = StratumType.UNKNOWN
    name: str = ""
    description: str = ""
    files: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    depth: int = 0
    stability_score: float = 0.0
    coupling_score: float = 0.0
    cohesion_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "file_count": len(self.files),
            "artifact_count": len(self.artifacts),
            "depth": self.depth,
            "stability_score": self.stability_score,
            "coupling_score": self.coupling_score,
            "cohesion_score": self.cohesion_score,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class Fossil:
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    type: FossilType = FossilType.DEAD_CODE
    name: str = ""
    description: str = ""
    location: Location | None = None
    last_modified: datetime | None = None
    estimated_age_days: int = 0
    severity: Severity = Severity.LOW
    reasoning: str = ""
    remediation: str = ""
    tier: Literal["ultra", "super", "nano"] = "nano"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "tier": self.tier,
            "location": (
                {
                    "file": self.location.file_path,
                    "lines": f"{self.location.start_line}-{self.location.end_line}",
                }
                if self.location
                else None
            ),
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "estimated_age_days": self.estimated_age_days,
            "severity": self.severity.value,
            "reasoning": self.reasoning,
            "remediation": self.remediation,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class Ruin:
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    type: RuinType = RuinType.SPAGHETTI_CODE
    name: str = ""
    description: str = ""
    locations: list[Location] = field(default_factory=list)
    severity: Severity = Severity.MEDIUM
    metrics: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""
    remediation: str = ""
    effort_estimate: Literal["trivial", "small", "medium", "large", "epic"] = "medium"
    tier: Literal["ultra", "super", "nano"] = "super"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "tier": self.tier,
            "locations": [
                {"file": loc.file_path, "lines": f"{loc.start_line}-{loc.end_line}"}
                for loc in self.locations
            ],
            "severity": self.severity.value,
            "metrics": self.metrics,
            "reasoning": self.reasoning,
            "remediation": self.remediation,
            "effort_estimate": self.effort_estimate,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ExcavationReport:
    site_name: str
    site_path: str
    excavated_at: datetime = field(default_factory=datetime.now)
    artifacts: list[Artifact] = field(default_factory=list)
    strata: list[Stratum] = field(default_factory=list)
    fossils: list[Fossil] = field(default_factory=list)
    ruins: list[Ruin] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_name": self.site_name,
            "site_path": self.site_path,
            "excavated_at": self.excavated_at.isoformat(),
            "artifacts": [a.to_dict() for a in self.artifacts],
            "strata": [s.to_dict() for s in self.strata],
            "fossils": [f.to_dict() for f in self.fossils],
            "ruins": [r.to_dict() for r in self.ruins],
            "summary": self.summary,
            "metadata": self.metadata,
        }

    def get_summary_stats(self) -> dict[str, int]:
        return {
            "total_artifacts": len(self.artifacts),
            "total_strata": len(self.strata),
            "total_fossils": len(self.fossils),
            "total_ruins": len(self.ruins),
            "critical_ruins": sum(1 for r in self.ruins if r.severity == Severity.CRITICAL),
            "high_ruins": sum(1 for r in self.ruins if r.severity == Severity.HIGH),
        }