import pytest

from src.diskspace_digger.scan import parse_size_threshold


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1B", 1),
        ("1KB", 1000),
        ("1MB", 1000**2),
        ("1GB", 1000**3),
        ("1KiB", 1024),
        ("1MiB", 1024**2),
        ("1GiB", 1024**3),
        ("  1.5  GB ", int(1.5 * 1000**3)),
    ],
)
def test_parse_size_threshold_valid(value: str, expected: int) -> None:
    assert parse_size_threshold(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "abc",
        "10GG",
        "1GIBB",
        "-1GB",  # negative doesn't match current regex
    ],
)
def test_parse_size_threshold_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        parse_size_threshold(value)
