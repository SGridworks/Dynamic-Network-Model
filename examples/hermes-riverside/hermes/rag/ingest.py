from __future__ import annotations

import re

from hermes.data import loader as L
from hermes.rag.store import write

_SUB_RE = re.compile(r"\b(SUB-\d{2})\b")


def _substation_from_text(text: str, default: str | None = None) -> str:
    m = _SUB_RE.search(text)
    return m.group(1) if m else (default or "")


def build_rows() -> list[dict]:
    rows: list[dict] = []

    for so in L.switching_orders():
        rows.append({
            "id": so.order_id,
            "kind": "switching_order",
            "substation_id": _substation_from_text(so.body),
            "text": so.body,
            "source_path": so.path,
        })

    for wo in L.work_orders():
        text = f"{wo.title}\n\n{wo.narrative}\n\nAsset: {wo.asset}\nCraft: {wo.craft}\nType: {wo.wo_type}\nPriority: {wo.priority}"
        rows.append({
            "id": wo.wo_id,
            "kind": "work_order",
            "substation_id": wo.substation_id,
            "text": text,
            "source_path": f"data/sp_l/work_orders.csv#{wo.wo_id}",
        })

    return rows


def run() -> int:
    rows = build_rows()
    n = write(rows)
    return n
