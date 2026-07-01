"""Central configuration: paths, domain configs, and tunable thresholds."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOMAINS_DIR = ROOT / "domains"
EVAL_DIR = ROOT / "eval"

# --- Tunable thresholds (see capstone doc, Section 2.2) -------------------
# Above ROUTE_CONFIDENT we route silently; between AMBIGUOUS and CONFIDENT we
# autosuggest a domain chip; below AMBIGUOUS we ask the user to pick.
ROUTE_CONFIDENT = 0.55
ROUTE_AMBIGUOUS = 0.28
TOP_K = 4               # chunks retrieved per query
RERANK_KEEP = 4         # chunks kept after re-ranking
CHUNK_TARGET_CHARS = 700
CHUNK_OVERLAP_CHARS = 120


@dataclass
class DomainConfig:
    key: str
    label: str
    emoji: str
    persona: str
    routing_keywords: List[str] = field(default_factory=list)
    guardrails: dict = field(default_factory=dict)
    clarify: dict = field(default_factory=dict)
    follow_ups: List[str] = field(default_factory=list)
    cross_domain_hint: List[dict] = field(default_factory=list)


def load_domains() -> Dict[str, DomainConfig]:
    domains: Dict[str, DomainConfig] = {}
    for path in sorted(DOMAINS_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        domains[raw["key"]] = DomainConfig(
            key=raw["key"],
            label=raw["label"],
            emoji=raw.get("emoji", ""),
            persona=raw.get("persona", "").strip(),
            routing_keywords=raw.get("routing_keywords", []),
            guardrails=raw.get("guardrails", {}),
            clarify=raw.get("clarify", {}),
            follow_ups=raw.get("follow_ups", []),
            cross_domain_hint=raw.get("cross_domain_hint", []),
        )
    return domains


def llm_settings() -> dict:
    """Read LLM settings from env. Empty api_key => offline extractive mode."""
    return {
        "provider": os.getenv("PF_LLM_PROVIDER", "openai"),  # openai | azure
        "api_key": os.getenv("PF_LLM_API_KEY", "").strip(),
        "model": os.getenv("PF_LLM_MODEL", "gpt-4o-mini"),
        "azure_endpoint": os.getenv("PF_AZURE_ENDPOINT", "").strip(),
        "azure_api_version": os.getenv("PF_AZURE_API_VERSION", "2024-06-01"),
    }
