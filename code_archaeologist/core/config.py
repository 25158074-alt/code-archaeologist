from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env explicitly at module import time
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Nebius API
    nebius_api_key: str = Field(default="", description="Nebius API key")
    nebius_base_url: str = Field(
        default="https://api.tokenfactory.us-central1.nebius.com/v1/",
        description="Nebius/NVIDIA API base URL",
    )
    nebius_timeout: float = Field(default=60.0, description="Request timeout in seconds")
    nebius_max_retries: int = Field(default=3, description="Max retry attempts")

    # Models
    ultra_model: str = Field(
        default="nvidia/nemotron-3-ultra-550b-a55b",
        description="Nemotron 3 Ultra for deep reasoning",
    )
    super_model: str = Field(
        default="nvidia/nemotron-3-super-120b-a12b",
        description="Nemotron 3 Super for balanced tasks",
    )
    nano_model: str = Field(
        default="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        description="Nemotron 3 Nano for fast everyday calls",
    )
    ultra_temperature: float = Field(default=0.3, description="Temperature for deep reasoning")
    super_temperature: float = Field(default=0.5, description="Temperature for balanced tasks")
    nano_temperature: float = Field(default=0.7, description="Temperature for fast calls")
    max_tokens_ultra: int = Field(default=8192, description="Max tokens for ultra")
    max_tokens_super: int = Field(default=4096, description="Max tokens for super")
    max_tokens_nano: int = Field(default=2048, description="Max tokens for nano")

    # Analysis
    min_artifact_confidence: float = Field(default=0.6, description="Minimum confidence for artifact detection")
    min_strata_size: int = Field(default=3, description="Minimum files to form a stratum")
    fossil_threshold_days: int = Field(default=180, description="Days since last change to consider fossil")
    ruin_complexity_threshold: int = Field(default=50, description="Cyclomatic complexity threshold for ruins")
    max_file_size_kb: int = Field(default=500, description="Max file size to analyze in KB")
    parallel_workers: int = Field(default=4, description="Parallel analysis workers")

    # General
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    cache_dir: Path = Field(default=Path(".cache/code-archaeologist"))
    output_dir: Path = Field(default=Path("./archaeology-reports"))

    @model_validator(mode="after")
    def create_dirs(self) -> Settings:
        # Don't crash on read-only / unwritable filesystems (common in hosted containers).
        for d in (self.cache_dir, self.output_dir):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        return self

    # Properties for backward compatibility
    @property
    def nebius(self) -> "NebiusSettingsProxy":
        return NebiusSettingsProxy(self)

    @property
    def models(self) -> "ModelSettingsProxy":
        return ModelSettingsProxy(self)

    @property
    def analysis(self) -> "AnalysisSettingsProxy":
        return AnalysisSettingsProxy(self)


class NebiusSettingsProxy:
    def __init__(self, settings: Settings):
        self._s = settings

    @property
    def api_key(self) -> str:
        return self._s.nebius_api_key

    @property
    def base_url(self) -> str:
        return self._s.nebius_base_url

    @property
    def timeout(self) -> float:
        return self._s.nebius_timeout

    @property
    def max_retries(self) -> int:
        return self._s.nebius_max_retries


class ModelSettingsProxy:
    def __init__(self, settings: Settings):
        self._s = settings

    @property
    def ultra_model(self) -> str:
        return self._s.ultra_model

    @property
    def super_model(self) -> str:
        return self._s.super_model

    @property
    def nano_model(self) -> str:
        return self._s.nano_model

    @property
    def ultra_temperature(self) -> float:
        return self._s.ultra_temperature

    @property
    def super_temperature(self) -> float:
        return self._s.super_temperature

    @property
    def nano_temperature(self) -> float:
        return self._s.nano_temperature

    @property
    def max_tokens_ultra(self) -> int:
        return self._s.max_tokens_ultra

    @property
    def max_tokens_super(self) -> int:
        return self._s.max_tokens_super

    @property
    def max_tokens_nano(self) -> int:
        return self._s.max_tokens_nano


class AnalysisSettingsProxy:
    def __init__(self, settings: Settings):
        self._s = settings

    @property
    def min_artifact_confidence(self) -> float:
        return self._s.min_artifact_confidence

    @property
    def min_strata_size(self) -> int:
        return self._s.min_strata_size

    @property
    def fossil_threshold_days(self) -> int:
        return self._s.fossil_threshold_days

    @property
    def ruin_complexity_threshold(self) -> int:
        return self._s.ruin_complexity_threshold

    @property
    def max_file_size_kb(self) -> int:
        return self._s.max_file_size_kb

    @property
    def parallel_workers(self) -> int:
        return self._s.parallel_workers


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()