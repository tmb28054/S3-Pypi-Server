"""Smoke test: all YAML files pass yamllint without errors."""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_yamllint_no_errors():
    """Run yamllint on all YAML files in the project and assert zero errors.

    Rule overrides are handled via inline comments in each YAML file
    (e.g. '# yamllint disable rule:line-length') rather than a
    separate .yamllint config file.

    Validates: YAML formatting standards
    """
    root = Path(".")
    yaml_files = sorted(
        str(p) for p in root.rglob("*.yaml")
        if ".git" not in p.parts and "__pycache__" not in p.parts
    )
    yml_files = sorted(
        str(p) for p in root.rglob("*.yml")
        if ".git" not in p.parts and "__pycache__" not in p.parts
    )
    all_files = yaml_files + yml_files
    assert all_files, "No YAML files found in the project"

    result = subprocess.run(
        ["yamllint", "-d", "default", *all_files],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"yamllint reported errors (exit code {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
