"""Knowledge graph linking changes -> product codes -> submission types."""
import json
from pathlib import Path

import networkx as nx


class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_analysis(self, event, analysis: dict):
        """Add a change node and edges to everything the analysis says it affects."""
        change_node = f"change:{event.id}"
        self.graph.add_node(
            change_node,
            kind="change",
            title=event.title,
            url=event.url,
            source=event.source,
            severity=analysis.get("severity"),
            change_type=analysis.get("change_type"),
        )
        for code in analysis.get("affected_product_codes", []) or []:
            node = f"product:{code}"
            self.graph.add_node(node, kind="product_code", code=code)
            self.graph.add_edge(change_node, node, relation="affects")
        for sub in analysis.get("affected_submission_types", []) or []:
            node = f"submission:{sub}"
            self.graph.add_node(node, kind="submission_type", name=sub)
            self.graph.add_edge(change_node, node, relation="affects")
        for cite in analysis.get("citations", []) or []:
            node = f"citation:{cite}"
            self.graph.add_node(node, kind="citation", ref=cite)
            self.graph.add_edge(change_node, node, relation="cites")
        return change_node

    def impacts_of(self, product_code: str):
        """Return change nodes affecting a product code."""
        node = f"product:{product_code}"
        if node not in self.graph:
            return []
        return [
            {"id": n, **self.graph.nodes[n]}
            for n in self.graph.predecessors(node)
            if self.graph.nodes[n].get("kind") == "change"
        ]

    def changes_affecting(self, node: str):
        """Return outgoing edges (what a change node affects/cites)."""
        if node not in self.graph:
            return []
        return [
            {"target": target, **self.graph.nodes[target], "relation": data.get("relation")}
            for _, target, data in self.graph.out_edges(node, data=True)
        ]

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(nx.node_link_data(self.graph), fh, indent=2)

    @classmethod
    def load(cls, path):
        kg = cls()
        with Path(path).open("r", encoding="utf-8") as fh:
            kg.graph = nx.node_link_graph(json.load(fh))
        return kg
