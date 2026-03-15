from __future__ import annotations

import re


_ID_OR_RANGE_RE = re.compile(r"\d+(?:\s*-\s*\d+)?")


def parse_id_spec(spec: str) -> set[int]:
    """Parse an id spec like '1 2 5-9,12' into a set of ints."""

    cleaned = spec.strip()
    if not cleaned:
        return set()

    # Allow only digits, commas, whitespace and hyphens.
    illegal = re.sub(r"[\d\s,-]", "", cleaned)
    if illegal:
        raise ValueError(f"Invalid characters in id spec: {illegal!r}")

    ids: set[int] = set()
    for token in _ID_OR_RANGE_RE.findall(cleaned):
        token = token.strip()
        if "-" not in token:
            ids.add(int(token))
            continue

        a, b = (part.strip() for part in token.split("-", 1))
        start = int(a)
        end = int(b)
        if end < start:
            raise ValueError(f"Invalid id range: {token!r}")
        ids.update(range(start, end + 1))

    return ids


def validate_ids(selected: set[int], valid: set[int]) -> tuple[set[int], set[int]]:
    """Return (valid_selected, invalid_selected)."""

    good = {i for i in selected if i in valid}
    bad = selected - good
    return good, bad
