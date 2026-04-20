from __future__ import annotations

import re
from typing import Any

import lancedb
import pyarrow as pa

from hermes.config import load_or_exit
from hermes.rag.embed import dim, embed

TABLE = "switching_and_wo"


def _db() -> lancedb.DBConnection:
    cfg = load_or_exit()
    cfg.lancedb_dir.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(cfg.lancedb_dir))


def _schema() -> pa.Schema:
    return pa.schema([
        pa.field("id", pa.string()),
        pa.field("kind", pa.string()),
        pa.field("substation_id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("source_path", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), dim())),
    ])


def write(rows: list[dict[str, Any]]) -> int:
    db = _db()
    texts = [r["text"] for r in rows]
    vectors = embed(texts)
    for r, v in zip(rows, vectors, strict=True):
        r["vector"] = v
    if TABLE in db.table_names():
        db.drop_table(TABLE)
    tbl = db.create_table(TABLE, schema=_schema())
    tbl.add(rows)
    return len(rows)


_SUB_TAG_RE = re.compile(r"\b(SUB-\d{2})\b")


def search(query: str, substation_id: str | None = None, k: int = 3) -> list[dict[str, Any]]:
    db = _db()
    if TABLE not in db.table_names():
        return []
    tbl = db.open_table(TABLE)
    qvec = embed([query])[0]
    search = tbl.search(qvec).limit(k * 4)
    if substation_id:
        search = search.where(f"substation_id = '{substation_id}'")
    rows = search.to_list()[:k]
    return [
        {
            "id": r["id"],
            "kind": r["kind"],
            "substation_id": r["substation_id"],
            "source_path": r["source_path"],
            "excerpt": r["text"][:600],
        }
        for r in rows
    ]
