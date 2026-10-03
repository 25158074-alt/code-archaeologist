from __future__ import annotations

from code_archaeologist.core.config import get_settings, Settings
from code_archaeologist.core.nebius_client import NebiusClient, ModelTier, CompletionResponse
from code_archaeologist.models.findings import (
    Artifact,
    ArtifactType,
    Fossil,
    FossilType,
    Ruin,
    RuinType,
    Stratum,
    StratumType,
    Severity,
    Location,
    ExcavationReport,
)

__version__ = "1.0.0"

__all__ = [
    "get_settings",
    "Settings",
    "NebiusClient",
    "ModelTier",
    "CompletionResponse",
    "Artifact",
    "ArtifactType",
    "Fossil",
    "FossilType",
    "Ruin",
    "RuinType",
    "Stratum",
    "StratumType",
    "Severity",
    "Location",
    "ExcavationReport",
]