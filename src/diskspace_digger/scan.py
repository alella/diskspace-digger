from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Callable, Optional

from .model import Node, ScanResult, ScanStats


ProgressCallback = Callable[[Path, int, int], None]
"""(current_path, dirs_visited, files_visited) -> None"""


_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]{0,3})\s*$")


def parse_size_threshold(value: str) -> int:
    """Parse values like '500MB', '1GB', '10GiB' into bytes."""

    m = _SIZE_RE.match(value)
    if not m:
        raise ValueError(f"Invalid size: {value!r}")

    number = float(m.group(1))
    unit = m.group(2).upper() or "B"

    if unit in {"B", "BYTE", "BYTES"}:
        return int(number)

    # Normalize common variants
    unit = unit.replace("IB", "I")  # GiB -> GI

    # Decimal
    dec = {"KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4, "PB": 1000**5}
    # Binary
    bin_ = {"KI": 1024, "MI": 1024**2, "GI": 1024**3, "TI": 1024**4, "PI": 1024**5}

    if unit in dec:
        return int(number * dec[unit])
    if unit in bin_:
        return int(number * bin_[unit])

    raise ValueError(f"Invalid size unit: {unit!r}")


def scan_path(
    root: Path,
    *,
    threshold_bytes: int,
    max_depth: Optional[int] = None,
    progress: Optional[ProgressCallback] = None,
) -> ScanResult:
    """Scan `root` (never follow symlinks; stay on same filesystem)."""

    root = root.absolute()
    if root.is_symlink():
        raise ValueError(f"Root path is a symlink (not allowed): {root}")

    root_dev = os.stat(root, follow_symlinks=False).st_dev

    dirs_visited = 0
    files_visited = 0
    errors = 0

    last_report_t = 0.0

    def report(p: Path) -> None:
        nonlocal last_report_t
        if progress is None:
            return
        now = time.monotonic()
        # throttle updates
        if now - last_report_t < 0.10:
            return
        last_report_t = now
        progress(p, dirs_visited, files_visited)

    def scan_dir(path: Path, depth: int) -> tuple[Optional[Node], int]:
        nonlocal dirs_visited, files_visited, errors

        dirs_visited += 1
        report(path)

        total = 0
        rendered_children: list[Node] = []

        try:
            it = os.scandir(path)
        except OSError:
            errors += 1
            return None, 0

        with it:
            for entry in it:
                try:
                    if entry.is_symlink():
                        continue

                    st = entry.stat(follow_symlinks=False)
                    if st.st_dev != root_dev:
                        continue

                    if entry.is_file(follow_symlinks=False):
                        files_visited += 1
                        total += st.st_size
                        if st.st_size >= threshold_bytes:
                            rendered_children.append(
                                Node(path=Path(entry.path), is_dir=False, size_bytes=st.st_size)
                            )
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        if max_depth is not None and (depth + 1) > max_depth:
                            # Depth exceeded: don't descend, can't compute size reliably.
                            continue

                        child_rendered, child_total = scan_dir(Path(entry.path), depth + 1)
                        total += child_total
                        if child_rendered is not None:
                            rendered_children.append(child_rendered)
                        continue

                except OSError:
                    errors += 1
                    continue

        # Render directory if it is big enough OR it contains rendered descendants.
        if total >= threshold_bytes or rendered_children:
            rendered_children.sort(key=lambda n: (-n.size_bytes, str(n.path).lower()))
            return Node(path=path, is_dir=True, size_bytes=total, children=rendered_children), total

        return None, total

    rendered_root, root_total = scan_dir(root, 0)
    if rendered_root is None:
        rendered_root = Node(path=root, is_dir=True, size_bytes=root_total, children=[])
    else:
        rendered_root.size_bytes = root_total

    # Assign IDs to rendered nodes (excluding root)
    next_id = 1
    id_to_path: dict[int, Path] = {}

    stack: list[Node] = [rendered_root]
    while stack:
        node = stack.pop()
        for child in reversed(node.children):
            if child.node_id is None:
                child.node_id = next_id
                id_to_path[next_id] = child.path
                next_id += 1
            stack.append(child)

    stats = ScanStats(dirs_visited=dirs_visited, files_visited=files_visited, errors=errors)
    return ScanResult(
        root=rendered_root, id_to_path=id_to_path, stats=stats, threshold_bytes=threshold_bytes
    )


def compute_render_tree_and_ids(
    full_tree: Node,
    *,
    threshold_bytes: int,
) -> tuple[Node, dict[int, Path]]:
    """Kept for parity with the design doc.

    In the current implementation, scanning already returns a rendered/pruned tree.
    """

    # This is a no-op for now.
    id_to_path: dict[int, Path] = {}
    next_id = 1
    stack = [full_tree]
    while stack:
        node = stack.pop()
        for child in reversed(node.children):
            if child.node_id is None:
                child.node_id = next_id
                id_to_path[next_id] = child.path
                next_id += 1
            stack.append(child)
    return full_tree, id_to_path
