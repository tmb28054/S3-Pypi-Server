"""Property-based and unit tests for s3pypi.index module."""

from hypothesis import given, settings
from hypothesis import strategies as st

from s3pypi.index import generate_index_page, parse_index_page
from s3pypi.packaging import normalize_name


# -- Hypothesis strategy for valid package names with unique normalized forms --

# Characters valid in Python package names (letters, digits, and separators)
_pkg_name_chars = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
)

_package_name = st.text(
    alphabet=_pkg_name_chars, min_size=1, max_size=30
).filter(
    # Normalized name must be non-empty and not just hyphens
    lambda n: normalize_name(n).strip("-") != ""
)


@st.composite
def unique_normalized_package_names(draw: st.DrawFn) -> list[str]:
    """Generate a list of package names whose normalized forms are all unique."""
    names = draw(st.lists(_package_name, min_size=0, max_size=50))
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        norm = normalize_name(name)
        if norm not in seen:
            seen.add(norm)
            unique.append(name)
    return unique


@given(names=unique_normalized_package_names())
@settings(max_examples=100)
def test_index_page_generation_round_trip(names: list[str]) -> None:
    """Feature: s3-pypi-server, Property 3: Index page generation round-trip

    Validates: Requirements 10.1, 5.5, 6.1
    """
    html = generate_index_page(names)
    parsed = parse_index_page(html)

    expected = [normalize_name(n) for n in names]

    assert parsed == expected, (
        f"Round-trip failed:\n"
        f"  Input names:      {names!r}\n"
        f"  Expected (norm):  {expected!r}\n"
        f"  Parsed from HTML: {parsed!r}"
    )


from s3pypi.index import generate_detail_page, parse_detail_page


# -- Hypothesis strategies for valid distribution filenames --

# Simple alphanumeric + underscore for name/version components (no hyphens to avoid
# ambiguity in wheel filename splitting, no "/" since these are bare filenames).
_ident_chars = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyz0123456789_")
)

_ident = st.text(alphabet=_ident_chars, min_size=1, max_size=20)

_version = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)

# Python/ABI/platform tags for wheel filenames (simple valid values)
_tag_component = st.sampled_from(["py3", "py2", "cp39", "cp310", "cp311", "cp312"])
_abi_tag = st.sampled_from(["none", "abi3", "cp39", "cp310"])
_platform_tag = st.sampled_from(["any", "linux_x86_64", "macosx_10_9_x86_64", "win_amd64"])


@st.composite
def wheel_filename(draw: st.DrawFn) -> str:
    """Generate a valid wheel filename: {name}-{version}-{python}-{abi}-{platform}.whl"""
    name = draw(_ident)
    version = draw(_version)
    python = draw(_tag_component)
    abi = draw(_abi_tag)
    platform = draw(_platform_tag)
    return f"{name}-{version}-{python}-{abi}-{platform}.whl"


@st.composite
def sdist_filename(draw: st.DrawFn) -> str:
    """Generate a valid sdist filename: {name}-{version}.tar.gz"""
    name = draw(_ident)
    version = draw(_version)
    return f"{name}-{version}.tar.gz"


_dist_filename = st.one_of(wheel_filename(), sdist_filename())


@st.composite
def unique_dist_filenames(draw: st.DrawFn) -> list[str]:
    """Generate a list of unique distribution filenames."""
    filenames = draw(st.lists(_dist_filename, min_size=0, max_size=50))
    seen: set[str] = set()
    unique: list[str] = []
    for fn in filenames:
        if fn not in seen:
            seen.add(fn)
            unique.append(fn)
    return unique


@given(filenames=unique_dist_filenames())
@settings(max_examples=100)
def test_detail_page_generation_round_trip(filenames: list[str]) -> None:
    """Feature: s3-pypi-server, Property 4: Detail page generation round-trip

    Validates: Requirements 10.2, 5.4, 6.2
    """
    package_name = "test-package"
    html = generate_detail_page(package_name, filenames)
    parsed = parse_detail_page(html)

    assert parsed == filenames, (
        f"Round-trip failed:\n"
        f"  Input filenames:  {filenames!r}\n"
        f"  Parsed from HTML: {parsed!r}"
    )

import re


@given(names=unique_normalized_package_names())
@settings(max_examples=100)
def test_index_page_pep503_structure(names: list[str]) -> None:
    """Feature: s3-pypi-server, Property 5: Generated HTML conforms to PEP 503 structure

    Validates: Requirements 5.6
    """
    html = generate_index_page(names)

    # Must contain DOCTYPE declaration
    assert "<!DOCTYPE html>" in html, "Missing <!DOCTYPE html> declaration"

    # Must contain PEP 503 repository-version meta tag
    assert '<meta name="pypi:repository-version" content="1.0">' in html, (
        "Missing <meta name=\"pypi:repository-version\" content=\"1.0\"> tag"
    )

    # Count <a elements — should be exactly one per input item
    anchor_count = len(re.findall(r"<a\s", html))
    assert anchor_count == len(names), (
        f"Expected {len(names)} <a> elements, found {anchor_count}"
    )

    # Every anchor must have a well-formed href attribute
    hrefs = re.findall(r'<a\s+href="([^"]*)"', html)
    assert len(hrefs) == len(names), (
        f"Expected {len(names)} href attributes, found {len(hrefs)}"
    )
    for href in hrefs:
        assert href.endswith("/"), f"Index page href should end with '/': {href!r}"


@given(filenames=unique_dist_filenames())
@settings(max_examples=100)
def test_detail_page_pep503_structure(filenames: list[str]) -> None:
    """Feature: s3-pypi-server, Property 5: Generated HTML conforms to PEP 503 structure

    Validates: Requirements 5.6
    """
    package_name = "test-package"
    html = generate_detail_page(package_name, filenames)

    # Must contain DOCTYPE declaration
    assert "<!DOCTYPE html>" in html, "Missing <!DOCTYPE html> declaration"

    # Must contain PEP 503 repository-version meta tag
    assert '<meta name="pypi:repository-version" content="1.0">' in html, (
        "Missing <meta name=\"pypi:repository-version\" content=\"1.0\"> tag"
    )

    # Count <a elements — should be exactly one per input item
    anchor_count = len(re.findall(r"<a\s", html))
    assert anchor_count == len(filenames), (
        f"Expected {len(filenames)} <a> elements, found {anchor_count}"
    )

    # Every anchor must have a well-formed href attribute
    hrefs = re.findall(r'<a\s+href="([^"]*)"', html)
    assert len(hrefs) == len(filenames), (
        f"Expected {len(filenames)} href attributes, found {len(hrefs)}"
    )
    for href in hrefs:
        assert "/" in href, f"Detail page href should contain '/': {href!r}"


# ---------------------------------------------------------------------------
# Unit tests for index module (Task 3.5)
# Validates: Requirements 8.4
# ---------------------------------------------------------------------------


class TestGenerateIndexPage:
    """Unit tests for generate_index_page."""

    def test_single_package(self) -> None:
        html = generate_index_page(["my-package"])
        assert "<!DOCTYPE html>" in html
        assert '<meta name="pypi:repository-version" content="1.0">' in html
        assert '<a href="my-package/">my-package</a>' in html

    def test_multiple_packages(self) -> None:
        html = generate_index_page(["alpha", "beta", "gamma"])
        assert '<a href="alpha/">alpha</a>' in html
        assert '<a href="beta/">beta</a>' in html
        assert '<a href="gamma/">gamma</a>' in html

    def test_normalizes_names(self) -> None:
        html = generate_index_page(["My_Package", "Some.Lib"])
        assert '<a href="my-package/">my-package</a>' in html
        assert '<a href="some-lib/">some-lib</a>' in html
        # Original un-normalized forms should NOT appear as hrefs
        assert 'href="My_Package/"' not in html
        assert 'href="Some.Lib/"' not in html

    def test_empty_list(self) -> None:
        html = generate_index_page([])
        assert "<!DOCTYPE html>" in html
        assert '<meta name="pypi:repository-version" content="1.0">' in html
        assert "<a " not in html

    def test_preserves_order(self) -> None:
        names = ["zeta", "alpha", "middle"]
        html = generate_index_page(names)
        pos_zeta = html.index("zeta")
        pos_alpha = html.index("alpha")
        pos_middle = html.index("middle")
        assert pos_zeta < pos_alpha < pos_middle


class TestGenerateDetailPage:
    """Unit tests for generate_detail_page."""

    def test_single_file(self) -> None:
        html = generate_detail_page("my-package", ["my_package-1.0.0-py3-none-any.whl"])
        assert "<!DOCTYPE html>" in html
        assert '<meta name="pypi:repository-version" content="1.0">' in html
        assert (
            '<a href="../../packages/my-package/my_package-1.0.0-py3-none-any.whl">'
            "my_package-1.0.0-py3-none-any.whl</a>"
        ) in html

    def test_multiple_files(self) -> None:
        filenames = [
            "my_package-1.0.0-py3-none-any.whl",
            "my_package-1.0.0.tar.gz",
        ]
        html = generate_detail_page("my-package", filenames)
        assert 'href="../../packages/my-package/my_package-1.0.0-py3-none-any.whl"' in html
        assert 'href="../../packages/my-package/my_package-1.0.0.tar.gz"' in html

    def test_normalizes_package_name_in_href(self) -> None:
        html = generate_detail_page("My_Package", ["file-1.0.0.tar.gz"])
        assert 'href="../../packages/my-package/file-1.0.0.tar.gz"' in html
        assert "Links for my-package" in html

    def test_empty_filenames(self) -> None:
        html = generate_detail_page("pkg", [])
        assert "<!DOCTYPE html>" in html
        assert '<meta name="pypi:repository-version" content="1.0">' in html
        assert "<a " not in html

    def test_preserves_order(self) -> None:
        filenames = ["z-2.0.0.tar.gz", "a-1.0.0.tar.gz"]
        html = generate_detail_page("pkg", filenames)
        pos_z = html.index("z-2.0.0.tar.gz")
        pos_a = html.index("a-1.0.0.tar.gz")
        assert pos_z < pos_a


class TestParseIndexPage:
    """Unit tests for parse_index_page."""

    def test_parses_known_html(self) -> None:
        html = (
            '<!DOCTYPE html>\n<html>\n'
            '<head><meta name="pypi:repository-version" content="1.0">'
            '<title>Simple Index</title></head>\n'
            '<body>\n'
            '<a href="alpha/">alpha</a>\n'
            '<a href="beta/">beta</a>\n'
            '</body>\n</html>'
        )
        assert parse_index_page(html) == ["alpha", "beta"]

    def test_empty_body(self) -> None:
        html = (
            '<!DOCTYPE html>\n<html>\n'
            '<head><meta name="pypi:repository-version" content="1.0">'
            '<title>Simple Index</title></head>\n'
            '<body>\n\n</body>\n</html>'
        )
        assert parse_index_page(html) == []

    def test_round_trip_single(self) -> None:
        names = ["requests"]
        html = generate_index_page(names)
        assert parse_index_page(html) == ["requests"]


class TestParseDetailPage:
    """Unit tests for parse_detail_page."""

    def test_parses_known_html(self) -> None:
        html = (
            '<!DOCTYPE html>\n<html>\n'
            '<head><meta name="pypi:repository-version" content="1.0">'
            '<title>Links for my-package</title></head>\n'
            '<body>\n'
            '<h1>Links for my-package</h1>\n'
            '<a href="../../packages/my-package/my_package-1.0.0-py3-none-any.whl">'
            'my_package-1.0.0-py3-none-any.whl</a>\n'
            '<a href="../../packages/my-package/my_package-1.0.0.tar.gz">'
            'my_package-1.0.0.tar.gz</a>\n'
            '</body>\n</html>'
        )
        result = parse_detail_page(html)
        assert result == [
            "my_package-1.0.0-py3-none-any.whl",
            "my_package-1.0.0.tar.gz",
        ]

    def test_empty_body(self) -> None:
        html = (
            '<!DOCTYPE html>\n<html>\n'
            '<head><meta name="pypi:repository-version" content="1.0">'
            '<title>Links for pkg</title></head>\n'
            '<body>\n<h1>Links for pkg</h1>\n\n</body>\n</html>'
        )
        assert parse_detail_page(html) == []

    def test_round_trip_single(self) -> None:
        filenames = ["thing-2.0.0.tar.gz"]
        html = generate_detail_page("thing", filenames)
        assert parse_detail_page(html) == filenames
