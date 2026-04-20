from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

LOCAL_PROVIDERS = {"ollama", "vllm", "llama_cpp"}
GATED_PROVIDERS = {"bedrock"}
ALL_PROVIDERS = LOCAL_PROVIDERS | GATED_PROVIDERS

REPO_ROOT = Path(__file__).resolve().parent.parent
SECURITY_DOC = REPO_ROOT / "docs" / "SECURITY.md"


class ComplianceError(RuntimeError):
    """Raised when a gated provider is selected without the required attestations."""


@dataclass(frozen=True)
class Config:
    provider: str
    model: str
    ollama_api_base: str
    vllm_api_base: str | None
    llama_cpp_api_base: str | None
    aws_region: str | None
    aws_endpoint_url_bedrock: str | None
    bedrock_vpc_confirmed: bool
    data_dir: Path
    lancedb_dir: Path


def _require_vpce_host(endpoint: str | None) -> None:
    """Bedrock endpoint must resolve to AWS PrivateLink (*.vpce.amazonaws.com).

    This is the load-bearing check for the 'no public-internet inference' promise.
    A misspelled or public endpoint here would silently route CEII over the open
    internet. We fail closed.
    """
    if not endpoint:
        raise ComplianceError(
            "Bedrock provider requires AWS_ENDPOINT_URL_BEDROCK to be set.\n"
            f"See {SECURITY_DOC} for the VPC endpoint requirement."
        )
    host = urlparse(endpoint).hostname or ""
    if not host.endswith(".vpce.amazonaws.com"):
        raise ComplianceError(
            f"Bedrock endpoint host '{host}' is not a VPC endpoint.\n"
            "The host must end in '.vpce.amazonaws.com' (AWS PrivateLink).\n"
            f"See {SECURITY_DOC} for why this is enforced."
        )


def _enforce_gate(provider: str, cfg_raw: dict[str, str | None]) -> None:
    if provider not in GATED_PROVIDERS:
        return
    if cfg_raw.get("HERMES_BEDROCK_VPC_CONFIRMED") != "1":
        raise ComplianceError(
            "Bedrock provider requires HERMES_BEDROCK_VPC_CONFIRMED=1.\n"
            "Set this only after your utility's security team has confirmed\n"
            "a VPC endpoint path to Bedrock and approved CEII data flowing over it.\n"
            f"See {SECURITY_DOC}."
        )
    _require_vpce_host(cfg_raw.get("AWS_ENDPOINT_URL_BEDROCK"))


def load() -> Config:
    load_dotenv(override=False)

    provider = (os.getenv("HERMES_LLM_PROVIDER") or "ollama").strip().lower()
    if provider not in ALL_PROVIDERS:
        raise ComplianceError(
            f"Unknown HERMES_LLM_PROVIDER '{provider}'. "
            f"Valid providers: {sorted(ALL_PROVIDERS)}."
        )

    raw = {
        "HERMES_BEDROCK_VPC_CONFIRMED": os.getenv("HERMES_BEDROCK_VPC_CONFIRMED"),
        "AWS_ENDPOINT_URL_BEDROCK": os.getenv("AWS_ENDPOINT_URL_BEDROCK"),
    }
    _enforce_gate(provider, raw)

    model = os.getenv("HERMES_LLM_MODEL") or _default_model(provider)

    return Config(
        provider=provider,
        model=model,
        ollama_api_base=os.getenv("OLLAMA_API_BASE", "http://localhost:11434"),
        vllm_api_base=os.getenv("VLLM_API_BASE"),
        llama_cpp_api_base=os.getenv("LLAMA_CPP_API_BASE"),
        aws_region=os.getenv("AWS_REGION"),
        aws_endpoint_url_bedrock=raw["AWS_ENDPOINT_URL_BEDROCK"],
        bedrock_vpc_confirmed=raw["HERMES_BEDROCK_VPC_CONFIRMED"] == "1",
        data_dir=REPO_ROOT / "data" / "sp_l",
        lancedb_dir=REPO_ROOT / ".lancedb",
    )


def _default_model(provider: str) -> str:
    if provider == "bedrock":
        return "bedrock/anthropic.claude-sonnet-4-v1:0"
    return "gemma4:e4b"


def load_or_exit() -> Config:
    """CLI entry point: print the compliance error and exit non-zero."""
    try:
        return load()
    except ComplianceError as e:
        print(f"\n[otter] compliance gate blocked startup:\n\n{e}\n", file=sys.stderr)
        sys.exit(2)
