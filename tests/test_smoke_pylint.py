"""Smoke test: pylint validation passes with 10/10 on all source files."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_pylint_no_errors():
    """Run pylint on all .py files under s3pypi/ and assert a 10/10 score.

    Validates: Requirements 8.2
    """
    source_dir = Path("s3pypi")
    py_files = sorted(str(p) for p in source_dir.rglob("*.py"))
    assert py_files, "No .py files found under s3pypi/"

    result = subprocess.run(
        [sys.executable, "-m", "pylint", *py_files],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"pylint did not pass with 10/10 (exit code {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
