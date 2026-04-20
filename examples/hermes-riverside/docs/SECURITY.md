# Security — Hermes at Riverside

Read this before enabling any non-local inference provider.

## Threat model

This POC is built to run inside a substation or a utility's secure-development zone. The data it reasons over is synthetic, but the architecture assumes the real deployment would ingest:

- Relay inventories, settings, firmware revisions
- Substation one-lines and protection coordination
- SCADA tag dictionaries, live analog and digital values
- Alarm histories
- Work orders and switching orders

All of this is **CEII** (Critical Energy Infrastructure Information) under 18 CFR §388.113, and subject to **NERC-CIP** controls (CIP-002 through CIP-013 depending on asset classification).

The single load-bearing property of this system: **model inference must not cross a boundary the utility has not approved**.

## What we refuse by default

A SaaS LLM call — OpenAI, Anthropic public API, Gemini, and every other commercial endpoint on the public internet — is refused. The compliance gate in `hermes/config.py` will not allow it, and no amount of env-var tweaking will. This is a hard rule, not a warning.

This is why `HERMES_LLM_PROVIDER` defaults to `ollama`. The only four providers the system will accept are:

| Provider    | Deployment                                                                       |
|-------------|----------------------------------------------------------------------------------|
| `ollama`    | Local machine or on-prem node running Ollama                                     |
| `vllm`      | On-prem GPU server serving an OpenAI-compatible API                              |
| `llama_cpp` | Edge / industrial-PC deployment serving an OpenAI-compatible API                 |
| `bedrock`   | AWS Bedrock **via a VPC endpoint** (`*.vpce.amazonaws.com`) that the utility owns |

## The Bedrock compliance gate

The `bedrock` provider is the one path where data leaves the substation — and it leaves only to an account and a network the utility controls. Enabling it requires **both**:

1. `HERMES_BEDROCK_VPC_CONFIRMED=1` — a human attestation that the utility's security team has:
   - Reviewed the VPC endpoint path
   - Confirmed Bedrock is listed in the CIP-013 supply-chain inventory
   - Confirmed the AWS account has model-invocation logging enabled
   - Confirmed no public-internet route exists from the inference client
2. `AWS_ENDPOINT_URL_BEDROCK` set to a host ending in `.vpce.amazonaws.com`. The code enforces this with `urllib.parse` on startup.

If either is missing, startup aborts with a pointer to this file. A misconfigured endpoint — for example, a public `bedrock-runtime.us-east-1.amazonaws.com` host — also aborts.

The gate lives in `hermes/config.py`, function `_enforce_gate`. There are no `--force` flags.

## What the agent is told

The system prompt (`hermes/agent/prompts.py`) tells the model:

- Treat all context as CEII
- Never propose exporting data
- Cite specific asset IDs, do not hallucinate them
- Switching sequences are drafts pending a human switching supervisor's review

The system prompt is not a security control. Schema validation (tool args are parsed via Pydantic; tool outputs are JSON) and the provider gate are the controls. The prompt is a behavioral nudge on top.

## Audit posture

Every tool call the agent makes is logged to the tool-trace record on the `Turn` object (`hermes/agent/loop.py`). The Streamlit UI renders the trace live. In a production deployment, you would wire the trace into your SIEM (CIP-007 event monitoring). The repo does not ship a SIEM integration — that is a utility-specific choice — but every tool call produces a stable, JSON-serializable record ready to ship.

## What this POC does not do

- Actuate anything. No agent output is connected to a breaker, a relay, a tap-changer, or any real or simulated control surface.
- Read from live SCADA. All inputs are the static synthetic fixtures under `data/sp_l/`.
- Access the public internet from the model. When `HERMES_LLM_PROVIDER=ollama`, you can verify this with `ss -tunp` during a query — traffic is only to `localhost:11434`.

Those are the properties a production utility deployment would extend. The three-zone architecture in the Sgridworks *AI in the Control Room* series describes the envelope. This POC fits inside Zone 2.
