"""Smoke test: CloudFormation templates pass cfn-lint without errors."""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_cfnlint_no_errors():
    """Run cfn-lint on all CloudFormation templates and assert zero errors.

    Validates: CloudFormation standards
    """
    # The template is bundled inside the s3pypi package
    template_path = Path("s3pypi") / "template.yaml"
    assert template_path.is_file(), f"Template not found: {template_path}"

    result = subprocess.run(
        ["cfn-lint", str(template_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"cfn-lint reported errors (exit code {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
