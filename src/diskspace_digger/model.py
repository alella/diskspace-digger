from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True, slots=True)
class ScanStats:
    dirs_visited: int = 0
    files_visited: int = 0
    errors: int = 0


@dataclass(slots=True)
class Node:
    path: Path
    is_dir: bool
    size_bytes: int
    children: list["Node"] = field(default_factory=list)
    # Assigned only for nodes that are actually rendered (root uses None).
    node_id: Optional[int] = None


@dataclass(slots=True)
class ScanResult:
    root: Node
    id_to_path: dict[int, Path]
    stats: ScanStats
    threshold_bytes: int
