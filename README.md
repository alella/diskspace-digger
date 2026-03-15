# diskspace-digger

Find large files/directories and generate a deletion script.

## Installation

This project uses **pipenv**.

Install dependencies:

```bash
pipenv install
pipenv install --dev
```

## Usage

Run via Python module (from the repo root):

```bash
pipenv run python -m src.diskspace_digger --help
```

### Scan

```bash
pipenv run python -m src.diskspace_digger scan PATH [OPTIONS]
```

Common options:

- `--threshold`: Only include items >= this size.
  - Examples: `500MB`, `1GB`, `10GiB`
  - Supported units: `B`, `KB`, `MB`, `GB`, `TB`, `PB`, `KiB`, `MiB`, `GiB`, `TiB`, `PiB`
- `--max-depth`: Limit recursion depth (useful for huge trees)
- `--output`: Where to write the text report (defaults to a timestamped file in the current directory)

Example:

```bash
pipenv run python -m src.diskspace_digger scan /Users/ash/github --threshold 1GB --max-depth 20
```

After the scan completes, the tool:

1. Prints a pruned tree of large items.
2. Writes a report file (by default: `./diskspace-digger-report-<timestamp>.txt`).
3. Prompts you to select node ids to delete.
4. Generates a shell script (by default: `./diskspace-digger-delete-<timestamp>.sh`).

Safety note: always open/review the generated delete script before running it.

## Running Tests

To run the tests for this project, navigate to the project directory and use the following command:

```bash
pipenv run pytest
```