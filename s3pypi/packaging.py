"""Filename parsing and package name normalization."""

import re


def normalize_name(name: str) -> str:
    """Normalize a package name per PEP 503.

    Converts to lowercase and replaces runs of [-_.] with a single hyphen.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_distribution_filename(filename: str) -> tuple[str, str, str]:
    """Parse a distribution filename into (name, version, extension).

    Supports .whl and .tar.gz formats.
    Raises ValueError for unrecognized formats.
    """
    if filename.endswith(".whl"):
        # Wheel format: {distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl
        stem = filename[: -len(".whl")]
        parts = stem.split("-")
        # Minimum parts: distribution, version, python, abi, platform = 5
        # With optional build tag: distribution, version, build, python, abi, platform = 6
        if len(parts) < 5:
            raise ValueError(f"Invalid wheel filename: {filename}")
        name = parts[0]
        version = parts[1]
        return (name, version, ".whl")

    if filename.endswith(".tar.gz"):
        # Sdist format: {distribution}-{version}.tar.gz
        stem = filename[: -len(".tar.gz")]
        parts = stem.split("-")
        if len(parts) < 2:
            raise ValueError(f"Invalid sdist filename: {filename}")
        # The version is the last part; the name is everything before it
        version = parts[-1]
        name = "-".join(parts[:-1])
        return (name, version, ".tar.gz")

    raise ValueError(f"Unrecognized distribution filename format: {filename}")
