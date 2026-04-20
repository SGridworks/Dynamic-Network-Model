from __future__ import annotations

from collections.abc import Callable
from typing import Any

import litellm

from hermes.config import Config, load_or_exit

# Silence LiteLLM's per-call debug noise; explicit logging lives in the agent loop.
litellm.suppress_debug_info = True


def _model_string(cfg: Config) -> str:
    """Return a LiteLLM-compatible model identifier for the active provider."""
    if cfg.provider == "ollama":
        return f"ollama_chat/{cfg.model}"
    if cfg.provider == "vllm":
        return f"openai/{cfg.model}"
    if cfg.provider == "llama_cpp":
        return f"openai/{cfg.model}"
    if cfg.provider == "bedrock":
        return cfg.model if cfg.model.startswith("bedrock/") else f"bedrock/{cfg.model}"
    raise ValueError(f"Unhandled provider: {cfg.provider}")


def _extra_kwargs(cfg: Config) -> dict[str, Any]:
    if cfg.provider == "ollama":
        return {"api_base": cfg.ollama_api_base}
    if cfg.provider == "vllm":
        return {"api_base": cfg.vllm_api_base, "api_key": "unused"}
    if cfg.provider == "llama_cpp":
        return {"api_base": cfg.llama_cpp_api_base, "api_key": "unused"}
    if cfg.provider == "bedrock":
        kw: dict[str, Any] = {}
        if cfg.aws_region:
            kw["aws_region_name"] = cfg.aws_region
        if cfg.aws_endpoint_url_bedrock:
            kw["aws_bedrock_runtime_endpoint"] = cfg.aws_endpoint_url_bedrock
        return kw
    return {}


def get_client(cfg: Config | None = None) -> Callable[..., Any]:
    """Return a `completion(...)` callable pinned to the active provider.

    Callers pass `messages=`, `tools=`, etc. We inject model + provider kwargs.
    Single call site = single audit surface.
    """
    cfg = cfg or load_or_exit()
    model = _model_string(cfg)
    extra = _extra_kwargs(cfg)

    def completion(**kwargs: Any) -> Any:
        return litellm.completion(model=model, **extra, **kwargs)

    completion.cfg = cfg  # type: ignore[attr-defined]
    completion.model = model  # type: ignore[attr-defined]
    return completion
