#!/usr/bin/env python3
"""Read and check one SP&L structural feeder graph; never modifies the repo."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import networkx as nx


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--feeder", default="FDR-0001")
    args = parser.parse_args()
    repo = args.repo.resolve()
    require((repo / "demo_data/load_demo_data.py").is_file(), "SP&L loader not found")
    sys.path.insert(0, str(repo))
    from demo_data.load_demo_data import (
        load_customers, load_feeders, load_network_edges,
        load_network_nodes, load_substations, load_transformers,
    )

    subs, feeders = load_substations(), load_feeders()
    transformers, customers = load_transformers(), load_customers()
    nodes, edges = load_network_nodes(), load_network_edges()
    for name, frame in (("substations", subs), ("feeders", feeders),
                        ("transformers", transformers), ("customers", customers),
                        ("nodes", nodes), ("edges", edges)):
        require(frame.index.is_unique, f"Duplicate IDs in {name}")
    require(args.feeder in feeders.index, "Unknown feeder")
    require(feeders.substation_id.isin(subs.index).all(), "Unknown feeder parent")
    require(transformers.feeder_id.isin(feeders.index).all(), "Unknown transformer parent")
    require(customers.transformer_id.isin(transformers.index).all(), "Unknown customer parent")
    require(transformers.substation_id.eq(transformers.feeder_id.map(feeders.substation_id)).all(),
            "Transformer substation disagrees with feeder registry")
    for field in ("feeder_id", "substation_id"):
        require(customers[field].eq(customers.transformer_id.map(transformers[field])).all(),
                f"Customer {field} disagrees with transformer registry")
    for field in ("from_node_id", "to_node_id"):
        require(edges[field].isin(nodes.index).all(), f"Unknown endpoint: {field}")

    selected = edges[edges.feeder_id.eq(args.feeder) & edges.edge_type.ne("tie")]
    graph = nx.from_pandas_edgelist(selected, "from_node_id", "to_node_id", create_using=nx.MultiGraph())
    source = str(feeders.loc[args.feeder, "substation_id"])
    require(source in graph, "Substation missing from feeder graph")
    require(nx.is_tree(graph), "Structural feeder graph is not a tree")
    selected_transformers = transformers[transformers.feeder_id.eq(args.feeder)]
    require(selected_transformers.index.isin(list(graph.nodes)).all(), "Transformer absent from graph")
    result = {
        "feeder": args.feeder,
        "substation": source,
        "transformers": len(selected_transformers),
        "customers": int(customers.feeder_id.eq(args.feeder).sum()),
        "structural_nodes": graph.number_of_nodes(),
        "structural_edges": graph.number_of_edges(),
        "connected_and_cycle_free": True,
        "open_non_tie_edges": int(selected.status.eq("open").sum()),
        "interpretation": "Structural graph retains open tail segments; no electrical feasibility claim.",
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
