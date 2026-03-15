from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .render import build_rich_tree
from .scan import parse_size_threshold, scan_path
from .scriptgen import generate_delete_script
from .selection import parse_id_spec, validate_ids


def _validate_threshold(_ctx: click.Context, _param: click.Parameter, value: str) -> int:
    """Validate/parse the --threshold option.

    We keep the CLI user-facing value as a human-friendly string (e.g. '1GB'),
    but convert it to bytes early so invalid values fail fast with a clear
    message.
    """

    try:
        threshold_bytes = parse_size_threshold(value)
    except ValueError as ex:
        raise click.BadParameter(
            f"{ex}. "
            "Expected a size like '500MB', '1GB', or '10GiB'. "
            "Supported units: B, KB, MB, GB, TB, PB, KiB, MiB, GiB, TiB, PiB."
        ) from ex

    if threshold_bytes <= 0:
        raise click.BadParameter("Threshold must be > 0 bytes")

    return threshold_bytes


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


@click.group()
def cli() -> None:
    """Find large files/directories and generate a deletion script."""


@cli.command()
@click.argument("path", type=click.Path(path_type=Path, exists=True, file_okay=False))
@click.option(
    "--threshold",
    "threshold_bytes",
    default="1GB",
    show_default=True,
    callback=_validate_threshold,
    help=(
        "Only include items >= this size (e.g. '500MB', '1GB', '10GiB'). "
        "Units: B, KB, MB, GB, TB, PB, KiB, MiB, GiB, TiB, PiB."
    ),
)
@click.option("--max-depth", type=int, default=None)
@click.option("--output", type=click.Path(path_type=Path), default=None)
def scan(
    path: Path, threshold_bytes: int, max_depth: Optional[int], output: Optional[Path]
) -> None:
    """Scan disk usage and show a pruned tree of large items."""

    out_path = output
    if out_path is None:
        out_path = Path.cwd() / f"diskspace-digger-report-{_timestamp()}.txt"

    console = Console()

    scanned = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}[/bold]"),
        TextColumn("dirs={task.fields[dirs]} files={task.fields[files]}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        task_id = progress.add_task("Scanning...", dirs=0, files=0)

        def on_progress(p: Path, dirs: int, files: int) -> None:
            progress.update(task_id, description=str(p), dirs=dirs, files=files)

        scanned = scan_path(
            path,
            threshold_bytes=threshold_bytes,
            max_depth=max_depth,
            progress=on_progress,
        )

    tree = build_rich_tree(scanned.root)
    console.print(tree)

    # Write to file by default.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        file_console = Console(file=f, force_terminal=False, color_system=None, width=120)
        file_console.print(tree)

    console.print(f"\nWrote report: [bold]{out_path}[/bold]")
    console.print(
        f"Scan stats: dirs={scanned.stats.dirs_visited} files={scanned.stats.files_visited} errors={scanned.stats.errors}"
    )

    valid_ids = set(scanned.id_to_path.keys())
    if not valid_ids:
        console.print("No nodes met the threshold; nothing to select.")
        return

    # Phase 2: always interactive
    prompt = "Enter node ids to mark for deletion (e.g. 1 2 5-9), or empty to skip"
    while True:
        spec = click.prompt(prompt, default="", show_default=False)
        if not spec.strip():
            console.print("No selections. Done.")
            return

        try:
            selected = parse_id_spec(spec)
        except ValueError as ex:
            console.print(f"Invalid selection: {ex}")
            continue

        good, bad = validate_ids(selected, valid_ids)
        if bad:
            console.print(f"Unknown ids: {', '.join(str(i) for i in sorted(bad))}")
            continue
        if not good:
            console.print("No valid ids selected.")
            continue

        script_path = Path.cwd() / f"diskspace-digger-delete-{_timestamp()}.sh"
        generate_delete_script(scan=scanned, selected_ids=good, output_path=script_path)
        console.print(f"Generated delete script: [bold]{script_path}[/bold]")
        return
