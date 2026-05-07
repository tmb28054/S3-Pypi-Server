"""CloudFormation stack deployment for s3-pypi-server."""

from __future__ import annotations

from pathlib import Path

import boto3
from botocore.exceptions import ClientError, WaiterError


TEMPLATE_PATH = Path(__file__).parent / "template.yaml"

# Map stack output keys to config keys
OUTPUT_KEY_MAP = {
    "BucketName": "bucket",
    "PyPIEndpoint": "pypi_endpoint",
    "CloudFrontDistributionId": "cloudfront_distribution_id",
    "CloudFrontURL": "cloudfront_url",
    "ApiGatewayURL": "api_gateway_url",
    "APIKeyTableName": "api_key_table_name",
    "LDAPSecretArn": "ldap_secret_arn",
    "KMSKeyArn": "kms_key_arn",
}


class DeployError(Exception):
    """Raised when a CloudFormation deployment fails."""


def load_template() -> str:
    """Load the CloudFormation template from package data.

    Returns:
        The template body as a string.

    Raises:
        FileNotFoundError: If the template file is not found.
    """
    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def deploy_stack(
    stack_name: str,
    region: str = "us-east-1",
    profile: str | None = None,
    parameters: dict[str, str] | None = None,
) -> dict[str, str]:
    """Deploy the CloudFormation stack.

    Args:
        stack_name: Name of the CloudFormation stack.
        region: AWS region. Defaults to us-east-1.
        profile: Optional boto3 named profile.
        parameters: Optional dict of CloudFormation parameter overrides.

    Returns:
        A dict mapping config keys to stack output values.

    Raises:
        DeployError: If the deployment fails.
    """
    session_kwargs: dict = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    cf_client = boto3.Session(**session_kwargs).client("cloudformation")

    kwargs = _build_stack_kwargs(stack_name, parameters)
    _execute_deploy(cf_client, stack_name, kwargs)

    return _get_stack_outputs(cf_client, stack_name)


def _build_stack_kwargs(
    stack_name: str,
    parameters: dict[str, str] | None,
) -> dict:
    """Build the kwargs dict for create_stack/update_stack."""
    kwargs: dict = {
        "StackName": stack_name,
        "TemplateBody": load_template(),
        "Capabilities": ["CAPABILITY_IAM"],
    }
    if parameters:
        kwargs["Parameters"] = [
            {"ParameterKey": k, "ParameterValue": v}
            for k, v in parameters.items()
        ]
    return kwargs


def _execute_deploy(cf_client, stack_name: str, kwargs: dict) -> None:
    """Execute the create or update stack operation and wait."""
    stack_exists = _stack_exists(cf_client, stack_name)

    try:
        if stack_exists:
            cf_client.update_stack(**kwargs)
            waiter = cf_client.get_waiter("stack_update_complete")
        else:
            cf_client.create_stack(**kwargs)
            waiter = cf_client.get_waiter("stack_create_complete")

        waiter.wait(
            StackName=stack_name,
            WaiterConfig={"Delay": 10, "MaxAttempts": 120},
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "ValidationError" and "No updates" in str(exc):
            return
        failure_reasons = _get_failure_reasons(cf_client, stack_name)
        raise DeployError(
            f"Deployment failed: {exc}\n{failure_reasons}"
        ) from exc
    except WaiterError as exc:
        failure_reasons = _get_failure_reasons(cf_client, stack_name)
        raise DeployError(
            f"Deployment timed out or failed:\n{failure_reasons}"
        ) from exc


def _stack_exists(cf_client, stack_name: str) -> bool:
    """Check if a CloudFormation stack exists."""
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        stacks = response.get("Stacks", [])
        if stacks:
            status = stacks[0].get("StackStatus", "")
            # REVIEW_IN_PROGRESS means it was created but never executed
            return status != "REVIEW_IN_PROGRESS"
        return False
    except ClientError:
        return False


def _get_failure_reasons(cf_client, stack_name: str) -> str:
    """Get failure reasons from stack events."""
    try:
        response = cf_client.describe_stack_events(StackName=stack_name)
        failures = []
        for event in response.get("StackEvents", []):
            status = event.get("ResourceStatus", "")
            if "FAILED" in status:
                reason = event.get("ResourceStatusReason", "Unknown")
                resource = event.get("LogicalResourceId", "Unknown")
                failures.append(f"  {resource}: {reason}")
        return "\n".join(failures[:10]) if failures else "No failure details available"
    except ClientError:
        return "Unable to retrieve failure details"


def _get_stack_outputs(cf_client, stack_name: str) -> dict[str, str]:
    """Retrieve stack outputs and map them to config keys."""
    response = cf_client.describe_stacks(StackName=stack_name)
    stacks = response.get("Stacks", [])
    if not stacks:
        return {}

    outputs = stacks[0].get("Outputs", [])
    result = {}
    for output in outputs:
        key = output["OutputKey"]
        value = output["OutputValue"]
        if key in OUTPUT_KEY_MAP:
            result[OUTPUT_KEY_MAP[key]] = value

    return result
