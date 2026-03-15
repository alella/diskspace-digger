from __future__ import annotations

# Use absolute import so running via `python -m src.diskspace_digger` works cleanly
# with this repository's current package layout (`src` is a Python package).
from src.diskspace_digger.cli import cli


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
