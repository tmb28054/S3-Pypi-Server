"""PEP 503 HTML generation (index and detail pages)."""

from html.parser import HTMLParser

from s3pypi.packaging import normalize_name


def generate_index_page(package_names: list[str]) -> str:
    """Generate PEP 503 root index HTML listing all packages.

    Each package name is normalized and linked as an anchor element.
    Returns a complete HTML document string.
    """
    anchors = "\n".join(
        f'<a href="{normalize_name(name)}/">{normalize_name(name)}</a>'
        for name in package_names
    )
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        '<head><meta name="pypi:repository-version" content="1.0">'
        "<title>Simple Index</title></head>\n"
        "<body>\n"
        f"{anchors}\n"
        "</body>\n"
        "</html>"
    )


def generate_detail_page(package_name: str, filenames: list[str]) -> str:
    """Generate PEP 503 package detail HTML listing distribution files.

    Each filename is linked as an anchor element pointing to the download URL.
    Returns a complete HTML document string.
    """
    normalized = normalize_name(package_name)
    anchors = "\n".join(
        f'<a href="../../packages/{normalized}/{fn}">{fn}</a>'
        for fn in filenames
    )
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        '<head><meta name="pypi:repository-version" content="1.0">'
        f"<title>Links for {normalized}</title></head>\n"
        "<body>\n"
        f"<h1>Links for {normalized}</h1>\n"
        f"{anchors}\n"
        "</body>\n"
        "</html>"
    )


class _AnchorHrefParser(HTMLParser):
    """Extract href attribute values from <a> elements."""

    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr_name, attr_value in attrs:
                if attr_name == "href" and attr_value is not None:
                    self.hrefs.append(attr_value)


def parse_index_page(html: str) -> list[str]:
    """Parse a PEP 503 index page and extract package names from anchor hrefs."""
    parser = _AnchorHrefParser()
    parser.feed(html)
    # hrefs are like "my-package/", strip trailing slash to get the name
    return [href.rstrip("/") for href in parser.hrefs]


def parse_detail_page(html: str) -> list[str]:
    """Parse a PEP 503 detail page and extract filenames from anchor hrefs."""
    parser = _AnchorHrefParser()
    parser.feed(html)
    # hrefs are like "../../packages/my-package/filename.whl", extract the filename
    return [href.rsplit("/", 1)[-1] for href in parser.hrefs]
