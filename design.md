# diskspace-digger — Design (Phase 1 + Phase 2)

## Problem statement

I want a CLI tool that helps me quickly understand **what is taking up space on disk** by:

1. Scanning a directory recursively.
2. Producing an **annotated tree** of directories/files that are **≥ a size threshold** (e.g., `1GB`).
3. Displaying **human-readable sizes** on each printed tree node.
4. Showing a **progress indicator** during scanning.
5. Assigning a stable **identifier** to every printed node.

This is **Phase 1**.

In **Phase 2**, after presenting the tree, the tool prompts for identifiers to “mark for deletion” and generates a **separate deletion script** (does not delete anything itself).

---

## Goals and non-goals

### Goals

**Phase 1**

- Recursively scan directories and compute sizes.
- Apply a size threshold so the resulting output focuses on big items.
- Print a tree view with:
  - Node identifier
  - Human-readable size
  - Path / name
- Show progress while scanning.

**Phase 2**

- Ask user for one or more node identifiers to mark.
- Generate a deletion script that the user can manually review/execute.

### Non-goals (for these phases)

- No automatic deletion.
- No background daemon or GUI.
- No filesystem indexing database (scan is on-demand).
- No cross-host orchestration.

---

## Target environments

- Primary: macOS (developer machine)
- Secondary: Linux

Windows compatibility is desirable but not required for Phase 1/2.

---

## Dependencies (do not reinvent the wheel)

### Runtime dependencies

- **`click`**: CLI entrypoints, options, prompts, validation.
- **`rich`**: progress bars/spinners and tree rendering (`rich.progress`, `rich.tree`, `rich.console`).

Notes:

- `rich` already includes utilities for formatting sizes (via `rich.filesize.decimal` / `rich.filesize.pick_unit_and_suffix` depending on desired style). If we need stricter parsing/formatting rules later, we can add `humanfriendly` or `python-humanize`, but the initial approach should rely on `rich`.

### Dev dependencies (already present)

From the current repo:

- `pytest`, `pytest-cov`, `coverage`
- `black`, `pylint`

---

## CLI UX (proposed)

Command name (module/console-script):

- `diskspace-digger` (or `dsd`) — final name to be decided.

Primary command:

```bash
diskspace-digger scan /path/to/scan --threshold 1GB --max-depth 15
```

Key options:

- `PATH` (argument): root folder to scan.
- `--threshold TEXT`: size threshold (e.g., `500MB`, `1GB`, `10GiB`).
  - Default: `1GB`.
  - Parsing supports suffixes (`KB/MB/GB/TB`, and optionally `KiB/MiB/GiB/TiB`).
- `--max-depth INT`: cap traversal depth.
  - Default: unlimited (or a safe default like 25).
- Symlinks are **never followed** (hard rule; no flag).
- The scan is constrained to **one filesystem** (hard rule; no flag).
- `--output PATH`: write rendered tree to file.
  - Default: write a report file in the current working directory:
    `diskspace-digger-report-YYYYMMDD-HHMMSS.txt`
  - The tree is also printed to the console.
- `--json PATH`: optional later; dump the node graph for tooling.

Phase 2 is triggered after scan:

- The tool is **always interactive** (Phase 2 prompt always appears).

---

## Conceptual model

We build an in-memory tree/graph of “interesting” nodes.

### Definitions

- **Node**: A directory or file.
- **Size**:
  - For files: `st_size`.
  - For directories: sum of sizes of descendants.
- **Interesting node**: A node whose computed size is `>= threshold`.
  - Directories can become interesting by containing large descendants.

### Node identifier

Each printed node gets an identifier that is:

- Easy to type
- Deterministic within a single run
- Unique in the output

Proposed format:

- Use a simple incrementing integer in pre-order as nodes are added to the “render tree”.
  - Example IDs: `1`, `2`, `3`, ...
  - Display as `[12]` in the output.

We keep a mapping:

```text
id -> absolute_path
```

Phase 2 uses that mapping to select items.

---

## Tree output format (console)

Use `rich.tree.Tree` so output is readable, collapsible-looking, and colored.

Each node line includes:

- `[id]`
- `size` (human-readable)
- name (basename or full path depending on level)

Example:

```text
/Users/ash
├── [1]  42.1 GB  Movies
│   ├── [2]  39.9 GB  FinalCutProjects
│   └── [3]   2.2 GB  Clips
└── [4]   8.7 GB  Library
    └── [5]   7.9 GB  Application Support
```

### Human-readable sizes

Use `rich.filesize.decimal(bytes)` (base-10) or binary formatting depending on preference.

Decision:

- Default to **decimal** (GB = 10^9) because many disk tools/reporting use decimal.
- Option: `--binary` to display GiB.

---

## Phase 1 scanning design

### Traversal strategy

Primary approach: depth-first traversal using `os.scandir()`.

Rationale:

- `os.scandir()` is faster than `os.listdir()` + `os.stat()` because it yields `DirEntry` objects that can cache stat results.

Pseudo:

1. Start at root path.
2. For each directory:
   - Iterate entries with `os.scandir()`.
   - For files: add `st_size`.
   - For subdirectories: recurse, accumulate returned child directory size.
3. Directory size = sum(files + subdir sizes).
4. Decide which nodes are “interesting” based on threshold.

### Pruning / threshold application

We still need to compute directory sizes, but we can **prune the rendered output**.

Render rules (proposed):

- A **file** is rendered only if `size >= threshold`.
- A **directory** is rendered if:
  - `dir_size >= threshold`, OR
  - it contains at least one rendered child (to preserve context).

This yields a compact “large items” tree while still showing parent folders that lead to them.

### Handling errors and special cases

- Permission denied: collect and optionally show a warning summary at end.
- Broken symlink: skip.
- Symlink loops: impossible because we never follow symlinks.
- Crossing filesystem boundaries: prevented by checking device id (see below).
- Very large directories: keep recursion stack safe (Python recursion depth) by:
  - Prefer iterative traversal later if needed.
  - Or ensure depth is bounded (`--max-depth`).

Filesystem constraint implementation:

- Record `root_dev = os.stat(root_path).st_dev`.
- For each directory entry, use `entry.stat(follow_symlinks=False)`.
- If `stat.st_dev != root_dev`, skip that subtree/entry.

### Progress indicator

Progress cannot be a perfect “percent” without knowing total work upfront.

Use `rich.progress.Progress` with:

- A spinner
- Counts of visited directories/files
- Current path being scanned
- Elapsed time

Example columns:

- `SpinnerColumn()`
- `TextColumn("{task.description}")` (current path)
- `MofNCompleteColumn()` is not applicable without totals
- `TextColumn("dirs={task.fields[dirs]} files={task.fields[files]}")`
- `TimeElapsedColumn()`

Implementation note:

- Update counters on every N entries to avoid slowing down traversal.

---

## Phase 2 selection + deletion script generation

### Prompt flow

The tool is always interactive:

1. Show the tree.
2. Prompt:
   - `Enter node ids to mark for deletion (e.g. 1 2 5-9), or empty to skip:`
3. Parse input into a set of IDs.
4. Validate:
   - Unknown IDs -> show error and re-prompt.
   - If a parent and child are both selected, parent selection wins (optional simplification).

### Output

Generate a script file (default name includes timestamp):

- `diskspace-digger-delete-YYYYMMDD-HHMMSS.sh`

Script properties:

- Starts with `#!/usr/bin/env bash` and `set -euo pipefail`.
- Contains `rm -rf -- "..."` lines for each selected absolute path.
- Includes comments with original ID + size.
- Script is not executed.

Safety:

- Quote paths correctly.
- Use `--` to prevent option injection.

---

## Proposed repo structure

Current repo already has `src/` and `test/`.

Proposed modules:

```text
src/
  diskspace_digger/
    __init__.py
    cli.py            # click commands and options
    scan.py           # traversal + sizing
    model.py          # Node dataclass, ID mapping
    render.py         # rich Tree rendering
    selection.py      # parse id specs: "1 2 5-7"
    scriptgen.py      # generate deletion script
```

---

## Proposed API (function/class signatures)

The following signatures are the intended public “shape” of the codebase. Exact details can change during implementation, but these provide a concrete starting point.

### `src/diskspace_digger/model.py`

```python
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
    children: list[Node] = field(default_factory=list)
    # assigned only for nodes that are actually rendered
    node_id: Optional[int] = None


@dataclass(slots=True)
class ScanResult:
    root: Node
    id_to_path: dict[int, Path]
    stats: ScanStats
    threshold_bytes: int
```

### `src/diskspace_digger/scan.py`

```python
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .model import Node, ScanResult


ProgressCallback = Callable[[Path, int, int], None]
"""(current_path, dirs_visited, files_visited) -> None"""


def parse_size_threshold(value: str) -> int:
    """Parse values like '500MB', '1GB', '10GiB' into bytes."""


def scan_path(
    root: Path,
    *,
    threshold_bytes: int,
    max_depth: Optional[int] = None,
    progress: Optional[ProgressCallback] = None,
) -> ScanResult:
    """Scan `root` (never follow symlinks; stay on same filesystem).

    Returns a ScanResult containing a pruned Node tree suitable for rendering,
    plus an id->path mapping for interactive selection.
    """


def compute_render_tree_and_ids(
    full_tree: Node,
    *,
    threshold_bytes: int,
) -> tuple[Node, dict[int, Path]]:
    """Prune the full tree to only the nodes to render, assign node IDs."""
```

### `src/diskspace_digger/render.py`

```python
from __future__ import annotations

from rich.console import Console
from rich.tree import Tree

from .model import Node


def build_rich_tree(root: Node) -> Tree:
    """Convert Node tree into a Rich Tree with `[id] size name` lines."""


def render_tree(console: Console, root: Node) -> None:
    """Render the tree to the console."""
```

### `src/diskspace_digger/selection.py`

```python
from __future__ import annotations


def parse_id_spec(spec: str) -> set[int]:
    """Parse an id spec like '1 2 5-9,12' into a set of ints."""


def validate_ids(selected: set[int], valid: set[int]) -> tuple[set[int], set[int]]:
    """Return (valid_selected, invalid_selected)."""
```

### `src/diskspace_digger/scriptgen.py`

```python
from __future__ import annotations

from pathlib import Path

from .model import ScanResult


def generate_delete_script(
    *,
    scan: ScanResult,
    selected_ids: set[int],
    output_path: Path,
) -> None:
    """Write a bash script with `rm -rf -- ...` lines for selected nodes."""
```

### `src/diskspace_digger/cli.py`

```python
from __future__ import annotations

from pathlib import Path

import click


@click.group()
def cli() -> None:
    ...


@cli.command()
@click.argument("path", type=click.Path(path_type=Path, exists=True, file_okay=False))
@click.option("--threshold", default="1GB", show_default=True)
@click.option("--max-depth", type=int, default=None)
@click.option("--output", type=click.Path(path_type=Path), default=None)
def scan(path: Path, threshold: str, max_depth: int | None, output: Path | None) -> None:
    """Scan disk usage and show a pruned tree of large items."""

    # Note: if `output` is None, the CLI chooses a timestamped report path in the
    # current working directory.
```

---

## Success criteria

Phase 1 is successful when:

- Scanning a directory prints a readable tree of only large items.
- Output includes node IDs and human-readable sizes.
- A progress indicator is visible during scan.

Phase 2 is successful when:

- User can enter IDs and receive a generated `*.sh` deletion script.
- The tool never deletes files directly.
