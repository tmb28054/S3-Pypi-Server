"""Pip and twine configuration helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def prompt_pip_credentials() -> tuple[str, str]:
    """Prompt the user for pip authentication credentials.

    Returns:
        Tuple of (username, password).
    """
    print("Authentication method:")
    print("  1) API key (__token__)")
    print("  2) Username / password (LDAP)")
    choice = input("Choose [1/2]: ").strip()

    if choice == "1":
        token = input("API key: ").strip()
        if not token:
            print("error: API key is required", file=sys.stderr)
            raise SystemExit(1)
        return "__token__", token

    if choice == "2":
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        if not username or not password:
            print("error: username and password are required", file=sys.stderr)
            raise SystemExit(1)
        return username, password

    print("error: invalid choice, enter 1 or 2", file=sys.stderr)
    raise SystemExit(2)


def prompt_twine_credentials() -> tuple[str, str]:
    """Prompt the user for twine authentication credentials.

    Returns:
        Tuple of (username, password).
    """
    print("Authentication method:")
    print("  1) API key (__token__) — requires read/write access")
    print("  2) Username / password (LDAP) — requires write entitlement group")
    choice = input("Choose [1/2]: ").strip()

    if choice == "1":
        token = input("API key (read/write): ").strip()
        if not token:
            print("error: API key is required", file=sys.stderr)
            raise SystemExit(1)
        return "__token__", token

    if choice == "2":
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        if not username or not password:
            print("error: username and password are required", file=sys.stderr)
            raise SystemExit(1)
        return username, password

    print("error: invalid choice, enter 1 or 2", file=sys.stderr)
    raise SystemExit(2)


def store_in_keyring(host: str, username: str, password: str) -> bool:
    """Store credentials in keyring.

    Returns:
        True if stored successfully, False otherwise.
    """
    try:
        import keyring  # pylint: disable=import-outside-toplevel
        keyring.set_password(host, username, password)
        print(f"\nCredentials stored in keyring (service: {host}, user: {username})")
        return True
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"\nwarning: failed to store in keyring: {exc}", file=sys.stderr)
        return False


def format_pip_config_keyring(cloudfront_url: str) -> str:
    """Format pip config that uses keyring for credentials."""
    lines = [
        "[global]",
        f"index-url = {cloudfront_url}",
        "extra-index-url = https://pypi.org/simple/",
    ]
    return "\n".join(lines)


def format_pip_config_inline(base_url: str, username: str, password: str) -> str:
    """Format pip config with credentials embedded in the URL."""
    index_url = build_authenticated_url(base_url, username, password)
    lines = [
        "[global]",
        f"index-url = {index_url}",
        "extra-index-url = https://pypi.org/simple/",
    ]
    return "\n".join(lines)


def format_pypirc(
    repository_url: str,
    username: str,
    use_keyring: bool,
) -> str:
    """Format a .pypirc configuration file.

    Args:
        repository_url: The upload URL for the private repository.
        username: The username (__token__ or LDAP user).
        use_keyring: If True, omit password (keyring will provide it).

    Returns:
        The .pypirc file content as a string.
    """
    lines = [
        "[distutils]",
        "index-servers =",
        "    pypi",
        "    private",
        "",
        "[pypi]",
        "repository = https://upload.pypi.org/legacy/",
        "",
        "[private]",
        f"repository = {repository_url}",
        f"username = {username}",
    ]
    if use_keyring:
        lines.append("# password retrieved from keyring automatically")
    else:
        lines.append("# keyring unavailable — set password here or use --save")
        lines.append("# password = <your-password-or-api-key>")

    return "\n".join(lines)


def get_pip_config_path() -> Path:
    """Get the platform-appropriate pip config file path."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "pip" / "pip.ini"
    return Path.home() / ".pip" / "pip.conf"


def extract_host(url: str) -> str:
    """Extract the host (with scheme) from a URL for keyring service name.

    Args:
        url: A URL like https://d123.cloudfront.net/simple/

    Returns:
        The scheme + host portion, e.g. https://d123.cloudfront.net
    """
    if "://" in url:
        scheme, rest = url.split("://", 1)
        host = rest.split("/", 1)[0]
        return f"{scheme}://{host}"
    return url.split("/", 1)[0]


def build_authenticated_url(base_url: str, username: str, password: str) -> str:
    """Insert credentials into a URL.

    Args:
        base_url: The base URL (e.g. https://d123.cloudfront.net/simple/).
        username: The username or __token__.
        password: The password or API key.

    Returns:
        URL with credentials embedded (e.g. https://user:pass@host/path/).
    """
    if "://" in base_url:
        scheme, rest = base_url.split("://", 1)
        return f"{scheme}://{username}:{password}@{rest}"
    return f"{username}:{password}@{base_url}"
