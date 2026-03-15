from __future__ import annotations

from rich.filesize import decimal
from rich.text import Text
from rich.tree import Tree

from .model import Node


def _node_label(node: Node) -> Text:
    size = decimal(node.size_bytes)
    name = node.path.name or str(node.path)
    if node.node_id is None:
        return Text(f"{size}  {name}")
    return Text.assemble(
        (f"[{node.node_id}] ", "bold cyan"),
        (f"{size:>9}  ", "green"),
        (name, "default"),
    )


def build_rich_tree(root: Node) -> Tree:
    """Convert Node tree into a Rich Tree with `[id] size name` lines."""

    tree = Tree(
        Text.assemble(
            (f"{decimal(root.size_bytes):>9}  ", "green"),
            (str(root.path), "bold"),
        )
    )

    def add(parent: Tree, node: Node) -> None:
        for child in node.children:
            branch = parent.add(_node_label(child))
            if child.children:
                add(branch, child)

    add(tree, root)
    return tree
