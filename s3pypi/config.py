"""CLI configuration file management."""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".s3pypi"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config(config_file: Path = CONFIG_FILE) -> dict[str, str]:
    """Load configuration from the config file.

    Args:
        config_file: Path to the configuration file. Defaults to
            ``~/.s3pypi/config.json``.

    Returns:
        A dict of configuration values. Returns an empty dict if the
        file does not exist.

    Raises:
        ValueError: If the config file exists but contains invalid JSON.
    """
    if not config_file.is_file():
        return {}

    text = config_file.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid config file {config_file}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Invalid config file {config_file}: expected a JSON object")

    return data


def save_config(
    new_values: dict[str, str],
    config_file: Path = CONFIG_FILE,
) -> dict[str, str]:
    """Save configuration values, merging with any existing config.

    Creates the parent directory if it does not exist. Merges *new_values*
    into the existing configuration, preserving keys not present in
    *new_values*.

    Args:
        new_values: Key-value pairs to save. Only non-``None`` values
            are written.
        config_file: Path to the configuration file. Defaults to
            ``~/.s3pypi/config.json``.

    Returns:
        The full merged configuration dict after saving.
    """
    config = load_config(config_file)

    for key, value in new_values.items():
        if value is not None:
            config[key] = value

    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )

    return config
