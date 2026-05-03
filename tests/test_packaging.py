"""Property-based and unit tests for s3pypi.packaging module."""

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from s3pypi.packaging import normalize_name


@given(name=st.text())
@settings(max_examples=100)
def test_normalize_name_idempotent_and_well_formed(name: str) -> None:
    """Feature: s3-pypi-server, Property 1: Name normalization is idempotent and well-formed

    Validates: Requirements 6.3
    """
    once = normalize_name(name)
    twice = normalize_name(once)

    # Idempotence: normalizing twice gives the same result as normalizing once
    assert twice == once, (
        f"normalize_name is not idempotent: "
        f"normalize_name({name!r}) = {once!r}, "
        f"normalize_name({once!r}) = {twice!r}"
    )

    # Output is entirely lowercase
    assert once == once.lower(), (
        f"normalize_name({name!r}) = {once!r} is not lowercase"
    )

    # No consecutive runs of separator characters [-_.]
    assert not re.search(r"[-_.]{2,}", once), (
        f"normalize_name({name!r}) = {once!r} contains consecutive separator runs"
    )

from s3pypi.packaging import parse_distribution_filename


# -- Hypothesis strategies for generating valid distribution filenames --

# Characters valid in a Python distribution name component (no hyphens for wheel names)
_name_alphabet = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.")
)

# Simple version strings like "1.0.0", "2.3", "0.1.0a1"
_version_strategy = st.from_regex(r"[0-9]+(\.[0-9]+){0,3}", fullmatch=True)

# Python tag, ABI tag, platform tag for wheel filenames
_python_tag = st.from_regex(r"(py[23]|cp3[0-9]{1,2})", fullmatch=True)
_abi_tag = st.sampled_from(["none", "cp39", "cp310", "cp311", "cp312", "abi3"])
_platform_tag = st.sampled_from(
    ["any", "linux_x86_64", "manylinux1_x86_64", "win_amd64", "macosx_10_9_x86_64"]
)


@st.composite
def wheel_filenames(draw: st.DrawFn) -> tuple[str, str]:
    """Generate a (filename, expected_name) tuple for a valid wheel file.

    Wheel format: {distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl
    The distribution name in a wheel MUST NOT contain hyphens (they are separators).
    """
    name = draw(
        st.text(alphabet=_name_alphabet, min_size=1, max_size=30).filter(
            lambda n: not n.startswith(".") and not n.endswith(".")
        )
    )
    version = draw(_version_strategy)
    python = draw(_python_tag)
    abi = draw(_abi_tag)
    platform = draw(_platform_tag)
    include_build = draw(st.booleans())

    parts = [name, version]
    if include_build:
        parts.append("1")  # simple build tag
    parts.extend([python, abi, platform])

    filename = "-".join(parts) + ".whl"
    return filename, name


@st.composite
def sdist_filenames(draw: st.DrawFn) -> tuple[str, str]:
    """Generate a (filename, expected_name) tuple for a valid sdist file.

    Sdist format: {distribution}-{version}.tar.gz
    The distribution name in an sdist CAN contain hyphens.
    """
    # Generate name segments and join with hyphens to allow multi-segment names
    segment = st.text(alphabet=_name_alphabet, min_size=1, max_size=15).filter(
        lambda s: not s.startswith(".") and not s.endswith(".")
    )
    segments = draw(st.lists(segment, min_size=1, max_size=3))
    name = "-".join(segments)
    version = draw(_version_strategy)

    filename = f"{name}-{version}.tar.gz"
    return filename, name


@given(
    data=st.one_of(wheel_filenames(), sdist_filenames()),
)
@settings(max_examples=100)
def test_parse_distribution_filename_extracts_correct_name(
    data: tuple[str, str],
) -> None:
    """Feature: s3-pypi-server, Property 2: Distribution filename parsing extracts the correct package name

    Validates: Requirements 5.9
    """
    filename, expected_name = data

    parsed_name, _version, _ext = parse_distribution_filename(filename)

    assert normalize_name(parsed_name) == normalize_name(expected_name), (
        f"parse_distribution_filename({filename!r}) returned name {parsed_name!r}, "
        f"which normalizes to {normalize_name(parsed_name)!r}, "
        f"but expected name {expected_name!r} normalizes to {normalize_name(expected_name)!r}"
    )


# ---------------------------------------------------------------------------
# Unit tests for packaging module (Task 2.4)
# ---------------------------------------------------------------------------

import pytest


class TestNormalizeName:
    """Unit tests for normalize_name with specific examples.

    Validates: Requirements 8.5
    """

    def test_underscore_and_mixed_case(self) -> None:
        assert normalize_name("My_Package") == "my-package"

    def test_dot_separator(self) -> None:
        assert normalize_name("some.lib") == "some-lib"

    def test_uppercase_with_consecutive_underscores(self) -> None:
        assert normalize_name("UPPER__CASE") == "upper-case"

    def test_already_normalized(self) -> None:
        assert normalize_name("already-normal") == "already-normal"

    def test_empty_string(self) -> None:
        assert normalize_name("") == ""

    def test_mixed_separators(self) -> None:
        assert normalize_name("a-_.b") == "a-b"


class TestParseDistributionFilename:
    """Unit tests for parse_distribution_filename with known filenames.

    Validates: Requirements 8.6
    """

    # -- Valid wheel filenames --

    def test_simple_wheel(self) -> None:
        name, version, ext = parse_distribution_filename(
            "my_package-1.0.0-py3-none-any.whl"
        )
        assert name == "my_package"
        assert version == "1.0.0"
        assert ext == ".whl"

    def test_wheel_with_build_tag(self) -> None:
        name, version, ext = parse_distribution_filename(
            "my_package-2.3.1-1-cp311-cp311-linux_x86_64.whl"
        )
        assert name == "my_package"
        assert version == "2.3.1"
        assert ext == ".whl"

    # -- Valid sdist filenames --

    def test_simple_sdist(self) -> None:
        name, version, ext = parse_distribution_filename(
            "my_package-1.0.0.tar.gz"
        )
        assert name == "my_package"
        assert version == "1.0.0"
        assert ext == ".tar.gz"

    def test_sdist_with_hyphenated_name(self) -> None:
        name, version, ext = parse_distribution_filename(
            "my-cool-package-0.2.0.tar.gz"
        )
        assert name == "my-cool-package"
        assert version == "0.2.0"
        assert ext == ".tar.gz"

    # -- Invalid filenames --

    def test_zip_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized"):
            parse_distribution_filename("package-1.0.0.zip")

    def test_exe_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized"):
            parse_distribution_filename("package-1.0.0.exe")

    def test_wheel_missing_parts_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid wheel"):
            parse_distribution_filename("package-1.0.0.whl")

    def test_sdist_no_version_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid sdist"):
            parse_distribution_filename("package.tar.gz")
