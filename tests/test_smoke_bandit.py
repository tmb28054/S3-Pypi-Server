"""Smoke test: bandit validation passes with zero issues on all source files."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_bandit_no_issues():
    """Run bandit on all .py files under s3pypi/ and assert zero security issues.

    Validates: Requirements 8.3
    """
    source_dir = Path("s3pypi")
    py_files = sorted(str(p) for p in source_dir.rglob("*.py"))
    assert py_files, "No .py files found under s3pypi/"

    result = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", "s3pypi/", "-f", "json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"bandit reported security issues (exit code {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
