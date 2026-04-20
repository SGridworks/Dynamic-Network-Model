from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import streamlit as st

from hermes.agent.loop import ToolTrace, run
from hermes.agent.prompts import system_message
from hermes.config import load_or_exit
from hermes.showcase.trace import Trace, load_all

st.set_page_config(page_title="Otter Creek — Riverside copilot", layout="wide")

cfg = load_or_exit()
TRACE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "traces"

st.title("Otter — Riverside (SUB-001) copilot")
st.caption(
    f"provider=`{cfg.provider}`  ·  model=`{cfg.model}`  ·  "
    "SP&L data from Dynamic-Network-Model  ·  Rung 2 (Shadow)"
)

# --- Sidebar: mode selector --------------------------------------------------

with st.sidebar:
    st.subheader("Mode")
    mode = st.radio(
        "—",
        ("Replay recorded scenario", "Live chat"),
        index=0,
        label_visibility="collapsed",
    )
    st.divider()
    st.caption(
        "Replay mode renders pre-recorded agent traces from `fixtures/traces/`. "
        "No LLM call is made.\n\n"
        "Live mode runs the agent loop against the configured provider."
    )

# --- Replay mode -------------------------------------------------------------

if mode == "Replay recorded scenario":
    traces = load_all(TRACE_DIR) if TRACE_DIR.exists() else []
    if not traces:
        st.warning(
            f"No traces found at `{TRACE_DIR}`. Run:\n\n"
            "```bash\n.venv/bin/python -m hermes.cli record --scenario all\n```"
        )
    else:
        choice = st.selectbox(
            "Scenario",
            options=[t.scenario_id for t in traces],
            format_func=lambda sid: f"{sid} — " + next(t.title for t in traces if t.scenario_id == sid),
        )
        trace = next(t for t in traces if t.scenario_id == choice)

        left, right = st.columns([2, 1])
        with left:
            st.subheader(trace.title)
            with st.chat_message("user"):
                st.write(trace.query)
            with st.chat_message("assistant"):
                st.write(trace.final_text)
            st.caption(
                f"Recorded against {trace.provider} / `{trace.model}` "
                f"in {trace.elapsed_seconds:.1f}s" if trace.elapsed_seconds else
                f"Recorded against {trace.provider} / `{trace.model}`"
            )
        with right:
            st.subheader(f"Tool trace ({len(trace.tool_calls)})")
            for i, tc in enumerate(trace.tool_calls, 1):
                args = json.dumps(tc.arguments) if tc.arguments else "{}"
                with st.expander(f"{i}. {tc.name}({args[:60]}{'…' if len(args) > 60 else ''})"):
                    st.json({"arguments": tc.arguments, "result": tc.result})

# --- Live chat mode ----------------------------------------------------------

else:
    if "history" not in st.session_state:
        st.session_state.history = [system_message()]
    if "turns" not in st.session_state:
        st.session_state.turns = []  # list of (user_text, final_text, [ToolTrace])

    left, right = st.columns([2, 1])
    with left:
        st.subheader("Chat")
        for u, a, _ in st.session_state.turns:
            with st.chat_message("user"):
                st.write(u)
            with st.chat_message("assistant"):
                st.write(a)

        user_text = st.chat_input("ask about Riverside feeders, hosting capacity, outages, the microgrid…")
        if user_text:
            with st.chat_message("user"):
                st.write(user_text)
            traces_acc: list[ToolTrace] = []
            with st.chat_message("assistant"):
                with st.spinner("thinking…"):
                    turn = run(
                        user_text,
                        history=st.session_state.history,
                        on_trace=traces_acc.append,
                    )
                st.write(turn.final_text or "(no content)")
            st.session_state.turns.append((user_text, turn.final_text, traces_acc))
            st.rerun()

    with right:
        st.subheader("Tool trace")
        if not st.session_state.turns:
            st.caption("No tool calls yet. Ask a question on the left.")
        for i, (_, _, traces) in enumerate(reversed(st.session_state.turns)):
            if not traces:
                continue
            st.markdown(f"**Turn {len(st.session_state.turns) - i}**")
            for t in traces:
                with st.expander(f"{t.name}({json.dumps(t.arguments)[:60]}…)", expanded=False):
                    st.json(asdict(t))

st.divider()
st.caption(
    "All context treated as CEII. No inference leaves this machine unless the "
    "Bedrock-VPC compliance gate in `docs/SECURITY.md` is satisfied."
)
