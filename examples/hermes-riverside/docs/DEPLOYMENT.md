# Deployment — Hermes at Riverside

Three deployment modes, in increasing order of coupling to outside infrastructure.

## Mode 1 — Air-gapped local (default)

This is what `make chat` gives you out of the box.

```bash
make setup
ollama pull gemma4:e4b
cp .env.example .env
make ingest
make chat
```

- Model runs in Ollama on the same machine as the agent.
- All data reads come from `data/sp_l/` (committed synthetic fixtures).
- LanceDB lives at `./.lancedb/` on local disk.
- No outbound network calls once `ollama pull` is done.

Verify: during a chat turn, `ss -tunp | grep python` shows traffic only to `localhost:11434`.

This is the mode most utility security teams will accept. Everything else is a conversation.

## Mode 2 — On-prem inference server (vLLM or llama.cpp)

Same agent, model hosted on a GPU server inside the utility's own network.

```bash
# On the GPU host
vllm serve google/gemma-4-e4b --port 8000

# On the agent host
export HERMES_LLM_PROVIDER=vllm
export VLLM_API_BASE=http://gpu-host.internal:8000/v1
export HERMES_LLM_MODEL=google/gemma-4-e4b
make chat
```

Same properties as Mode 1 — inference stays inside the utility — with higher throughput and the ability to serve multiple agent seats.

llama.cpp on a DIN-rail industrial PC (Jetson-class) follows the same pattern with `HERMES_LLM_PROVIDER=llama_cpp` and `LLAMA_CPP_API_BASE`.

## Mode 3 — Bedrock over VPC endpoint (gated)

Use this only when your utility has approved Claude via AWS Bedrock over a VPC endpoint as the inference path for CEII-adjacent workloads. This is the highest-quality option; it is also the only mode where data leaves the on-prem network, and it leaves only to a VPC and account the utility owns.

Before enabling, your security team should have:

- [ ] Added AWS Bedrock to the CIP-013 supply-chain vendor list
- [ ] Stood up a VPC endpoint for `bedrock-runtime` in the utility's AWS account
- [ ] Confirmed the endpoint DNS is `*.vpce.amazonaws.com`
- [ ] Confirmed model invocation logging is enabled on the Bedrock account
- [ ] Confirmed no public-internet egress route from the agent host
- [ ] Documented the data flow in the relevant CIP-005 / CIP-007 artifacts

Then:

```bash
export HERMES_LLM_PROVIDER=bedrock
export HERMES_BEDROCK_VPC_CONFIRMED=1
export AWS_REGION=us-east-1
export AWS_ENDPOINT_URL_BEDROCK=https://bedrock-runtime.us-east-1.vpce-abc123.vpce.amazonaws.com
export HERMES_LLM_MODEL=bedrock/anthropic.claude-sonnet-4-v1:0
make chat
```

Startup will abort if `HERMES_BEDROCK_VPC_CONFIRMED` is not `1` or if `AWS_ENDPOINT_URL_BEDROCK` does not end in `.vpce.amazonaws.com`. See [SECURITY.md](SECURITY.md) for the gate code.

## Eval mode

Run the 20 Q&A pairs in `evals/qa_pairs.yaml` under whichever provider is configured. Compare two runs side-by-side:

```bash
# Local run
HERMES_LLM_PROVIDER=ollama make eval
mv evals/results.md evals/results-ollama.md

# Bedrock run (only after the gate is satisfied)
HERMES_LLM_PROVIDER=bedrock make eval
mv evals/results.md evals/results-bedrock.md
```

The artifact you hand to a utility security team is the pair: here is what the fully-local model can answer; here is what Claude-over-VPC can answer; here is the quality delta you buy when you allow the gated path.

## Data

The SP&L adapter (`hermes/data/spl.py`) wraps the published [Dynamic Network Model](https://github.com/SGridworks/Dynamic-Network-Model) — a synthetic 238K-customer utility released under Apache-2.0. Point `DNM_REPO_PATH` at a DNM checkout and the adapter reads the 23 datasets directly.

When you port this POC to real utility data, the contract is: `hermes/data/spl.py` is the only place that reads files. Swap its internals for the utility's systems of record:

- **GIS / network model** — substation, feeder, transformer, and switch topology; nameplate data. Feeds `get_substation_summary`, `get_feeders`, `get_topology`.
- **OMS** — historical outage archive. Feeds `get_outage_history` and `get_outage`, which drive the two restoration scenarios.
- **Historian** (PI, Canary, OSIsoft) — 15-minute feeder load, voltage, and solar output. Feeds `get_load_snapshot` and `get_solar_snapshot`.
- **Interconnection tracker / DERMS** — DER inventory and microgrid attributes. Feeds `get_der_inventory`, `get_hosting_capacity`, and `get_microgrid`.
- **Weather service** (NWS, HRRR, private vendor) — direct API call from `get_weather`.

CMMS is deliberately not in the list for the five current scenarios. It becomes relevant when predictive-maintenance tools are added (DGA flagging, thermal-scan anomaly detection, work-order creation), which sit in a later phase. Every tool routes through the adapter, so adding CMMS is an additive change, not a rewrite.
