PY := .venv/bin/python
PIP := .venv/bin/pip

# Keep the HF model cache on local disk. Some users have ~/.cache symlinked to
# a network mount (NFS/SMB) that doesn't support flock, which breaks
# huggingface_hub downloads. Overriding per-target is safe and explicit.
export HF_HOME ?= $(CURDIR)/.cache/hf
export HF_HUB_DISABLE_XET ?= 1

.PHONY: setup notebook record demo-replay demo-live eval lint clean help

help:
	@echo "setup         - create .venv and install deps"
	@echo "notebook      - rebuild and launch the showcase notebook"
	@echo "record        - re-record agent traces against the configured LLM provider"
	@echo "demo-replay   - Streamlit in replay mode (no LLM required)"
	@echo "demo-live     - Streamlit in live chat mode (LLM required)"
	@echo "eval          - run the eval harness"
	@echo "lint          - ruff check"
	@echo "clean         - remove venv, cache, lancedb"

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@echo ""
	@echo "Next: open notebook/otter-creek-showcase.ipynb, or"
	@echo "      make demo-replay  (Streamlit, no LLM)"
	@echo "      make demo-live    (Streamlit, requires Ollama + gemma4:e4b)"

notebook:
	$(PY) scripts/build_notebook.py
	$(PY) -m jupyter lab notebook/otter-creek-showcase.ipynb

record:
	$(PY) -m hermes.cli record --scenario all

demo-replay:
	$(PY) -m streamlit run hermes/ui/app.py

demo-live:
	$(PY) -m streamlit run hermes/ui/app.py

eval:
	$(PY) -m hermes.cli eval

lint:
	.venv/bin/ruff check hermes scripts evals

clean:
	rm -rf .venv .lancedb .cache __pycache__ **/__pycache__ *.egg-info
