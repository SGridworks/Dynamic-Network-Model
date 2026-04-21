"""OLLAMA_API_KEY reaches the litellm call when set; absent when unset."""

from __future__ import annotations

from unittest.mock import patch

from hermes.config import load
from hermes.llm import _extra_kwargs


def test_config_has_ollama_api_key_field() -> None:
    with patch.dict(
        "os.environ",
        {
            "HERMES_LLM_PROVIDER": "ollama",
            "HERMES_LLM_MODEL": "gemma3:27b",
            "OLLAMA_API_BASE": "https://ollama.com",
            "OLLAMA_API_KEY": "test_key_xyz",
        },
        clear=False,
    ):
        cfg = load()
    assert cfg.provider == "ollama"
    assert cfg.model == "gemma3:27b"
    assert cfg.ollama_api_base == "https://ollama.com"
    assert cfg.ollama_api_key == "test_key_xyz"


def test_config_ollama_api_key_absent_when_unset() -> None:
    env = {
        "HERMES_LLM_PROVIDER": "ollama",
        "HERMES_LLM_MODEL": "gemma4:e4b",
        "OLLAMA_API_BASE": "http://localhost:11434",
    }
    # Remove OLLAMA_API_KEY from the environment if it's set from a shell session.
    with patch.dict("os.environ", env, clear=True):
        cfg = load()
    assert cfg.ollama_api_key is None


def test_extra_kwargs_includes_api_key_when_set() -> None:
    """Proves the api_key actually makes it into the litellm call kwargs."""
    from hermes.config import Config

    cfg = Config(
        provider="ollama",
        model="gemma3:27b",
        ollama_api_base="https://ollama.com",
        ollama_api_key="test_key_xyz",
        vllm_api_base=None,
        llama_cpp_api_base=None,
        aws_region=None,
        aws_endpoint_url_bedrock=None,
        bedrock_vpc_confirmed=False,
        data_dir=None,  # type: ignore[arg-type]
        lancedb_dir=None,  # type: ignore[arg-type]
    )
    kw = _extra_kwargs(cfg)
    assert kw["api_base"] == "https://ollama.com"
    assert kw["api_key"] == "test_key_xyz"


def test_extra_kwargs_omits_api_key_when_absent() -> None:
    """Local-ollama default path should NOT leak an api_key= into the call."""
    from hermes.config import Config

    cfg = Config(
        provider="ollama",
        model="gemma4:e4b",
        ollama_api_base="http://localhost:11434",
        ollama_api_key=None,
        vllm_api_base=None,
        llama_cpp_api_base=None,
        aws_region=None,
        aws_endpoint_url_bedrock=None,
        bedrock_vpc_confirmed=False,
        data_dir=None,  # type: ignore[arg-type]
        lancedb_dir=None,  # type: ignore[arg-type]
    )
    kw = _extra_kwargs(cfg)
    assert kw == {"api_base": "http://localhost:11434"}
    assert "api_key" not in kw
