"""Central configuration. Everything is read from the environment (or a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _default_data_dir() -> Path:
    configured = _env("VERDICT_DATA_DIR")
    if configured:
        return Path(configured)
    hhgoa = ROOT / "data" / "hhgoa"
    return hhgoa if hhgoa.exists() else ROOT / "data" / "synthetic"


def _default_policy_file() -> Path:
    configured = _env("VERDICT_POLICY")
    if configured:
        return Path(configured)
    name = "hhgoa.yaml" if _default_data_dir().name == "hhgoa" else "policy.yaml"
    return ROOT / "verdict" / "policy" / name


@dataclass(frozen=True)
class Settings:
    # TigerGraph
    tg_host: str = field(default_factory=lambda: _env("TG_HOST", "http://localhost"))
    tg_graph: str = field(default_factory=lambda: _env("TG_GRAPHNAME", "Verdict"))
    tg_user: str = field(default_factory=lambda: _env("TG_USERNAME", "tigergraph"))
    tg_password: str = field(default_factory=lambda: _env("TG_PASSWORD", "tigergraph"))
    tg_restpp_port: str = field(default_factory=lambda: _env("TG_RESTPP_PORT", "14240"))
    tg_gs_port: str = field(default_factory=lambda: _env("TG_GS_PORT", "14240"))
    tg_api_token: str = field(default_factory=lambda: _env("TG_API_TOKEN", ""))
    # Separate least-privilege profile for the investigator (read-only role)
    tg_investigator_user: str = field(default_factory=lambda: _env("TG_INVESTIGATOR_USERNAME", ""))
    tg_investigator_password: str = field(default_factory=lambda: _env("TG_INVESTIGATOR_PASSWORD", ""))

    # Data
    # real dataset goes in data/hhgoa; until it exists we fall back to the synthetic stand-in
    data_dir: Path = field(default_factory=_default_data_dir)
    work_dir: Path = field(default_factory=lambda: Path(_env("VERDICT_WORK_DIR", str(ROOT / "artifacts"))))
    schema_map: Path = field(default_factory=lambda: Path(_env("VERDICT_SCHEMA_MAP", str(ROOT / "verdict" / "data" / "schema_map.yaml"))))
    policy_file: Path = field(default_factory=_default_policy_file)
    answers_dir: Path = field(default_factory=lambda: Path(_env("VERDICT_ANSWERS_DIR", "")) if _env("VERDICT_ANSWERS_DIR") else None)

    # LLM
    llm_mode: str = field(default_factory=lambda: _env("VERDICT_LLM", "auto"))  # auto | anthropic | offline
    model: str = field(default_factory=lambda: _env("VERDICT_MODEL", "claude-opus-5"))
    worker_model: str = field(default_factory=lambda: _env("VERDICT_WORKER_MODEL", "claude-haiku-4-5"))
    anthropic_key_present: bool = field(default_factory=lambda: bool(_env("ANTHROPIC_API_KEY")))
    max_tool_calls: int = field(default_factory=lambda: int(_env("VERDICT_MAX_TOOL_CALLS", "10")))

    # Graph access path for the agent: "mcp" (official tigergraph-mcp over stdio) or "direct" (pyTigerGraph)
    graph_access: str = field(default_factory=lambda: _env("VERDICT_GRAPH_ACCESS", "mcp"))

    # Embeddings: "lsa" (offline TF-IDF+SVD, default) or "fastembed"
    embedder: str = field(default_factory=lambda: _env("VERDICT_EMBEDDER", "lsa"))
    emb_dim: int = field(default_factory=lambda: int(_env("VERDICT_EMB_DIM", "128")))

    def __post_init__(self):
        if self.answers_dir is None:  # synthetic runs never overwrite the submission answers
            sub = "synthetic" if self.data_dir.name == "synthetic" else "hhgoa"
            object.__setattr__(self, "answers_dir", ROOT / "outputs" / sub / "answers")

    @property
    def use_llm(self) -> bool:
        if self.llm_mode == "offline":
            return False
        if self.llm_mode == "anthropic":
            return True
        return self.anthropic_key_present


settings = Settings()
