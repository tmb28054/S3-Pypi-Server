"""CLI entry point for s3pypi."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from s3pypi.apikey import (
    create_api_key,
    delete_api_key,
    get_api_key,
    list_api_keys,
    update_api_key,
)
from s3pypi.config import load_config, save_config
from s3pypi.deploy import DeployError, deploy_stack
from s3pypi.invalidation import create_invalidation
from s3pypi.packaging import normalize_name, parse_distribution_filename
from s3pypi.secrets import update_ldap_secret
from s3pypi.uploader import S3PyPIUploader


def main(argv: list[str] | None = None) -> None:
    """Console script entry point for s3pypi.

    Parses command-line arguments and dispatches to the upload, configure,
    apikey, configure-ldap, or deploy workflow. Exits with code 1 for
    runtime errors and code 2 for argument errors (argparse default).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_usage(sys.stderr)
        raise SystemExit(2)

    if args.command == "configure":
        _handle_configure(args)
    elif args.command == "upload":
        _handle_upload(args)
    elif args.command == "apikey":
        _handle_apikey(args)
    elif args.command == "configure-ldap":
        _handle_configure_ldap(args)
    elif args.command == "deploy":
        _handle_deploy(args)
    elif args.command == "pip":
        _handle_pip(args)
    elif args.command == "twine":
        _handle_twine(args)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="s3pypi",
        description="Upload Python packages to a private S3-backed PyPI server.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # -- upload subcommand --
    upload_parser = subparsers.add_parser(
        "upload",
        help="Upload a distribution file and regenerate index pages.",
    )
    upload_parser.add_argument(
        "dist_file",
        help="Path to the distribution file (.whl or .tar.gz) to upload.",
    )
    upload_parser.add_argument(
        "--bucket",
        default=None,
        help="Name of the S3 bucket to upload to. Falls back to configured value.",
    )
    upload_parser.add_argument(
        "--cloudfront-distribution-id",
        default=None,
        help="CloudFront distribution ID to invalidate after upload.",
    )

    # -- configure subcommand --
    configure_parser = subparsers.add_parser(
        "configure",
        help="Save default settings for bucket and CloudFront distribution ID.",
    )
    configure_parser.add_argument(
        "--bucket",
        default=None,
        help="Default S3 bucket name.",
    )
    configure_parser.add_argument(
        "--cloudfront-distribution-id",
        default=None,
        help="Default CloudFront distribution ID.",
    )
    configure_parser.add_argument(
        "--api-key-table-name",
        default=None,
        help="Default DynamoDB table name for API keys.",
    )
    configure_parser.add_argument(
        "--ldap-secret-arn",
        default=None,
        help="Default Secrets Manager ARN for LDAP configuration.",
    )
    configure_parser.add_argument(
        "--from-stack",
        default=None,
        help="Import configuration from a CloudFormation stack's outputs.",
    )
    configure_parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile to use with --from-stack.",
    )
    configure_parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region to use with --from-stack (default: us-east-1).",
    )

    # -- apikey subcommand --
    apikey_parser = subparsers.add_parser(
        "apikey",
        help="Manage API keys in DynamoDB.",
    )
    apikey_parser.add_argument(
        "--table-name",
        default=None,
        help="DynamoDB table name. Falls back to configured value.",
    )
    apikey_subparsers = apikey_parser.add_subparsers(dest="action")

    apikey_create_parser = apikey_subparsers.add_parser(
        "create",
        help="Create a new API key.",
    )
    apikey_create_parser.add_argument(
        "--description",
        default=None,
        help="Optional description for the API key.",
    )
    apikey_create_parser.add_argument(
        "--access",
        default="read",
        choices=["read", "read/write"],
        help="Access level: 'read' (default) or 'read/write'.",
    )

    apikey_subparsers.add_parser(
        "list",
        help="List all API keys.",
    )

    apikey_get_parser = apikey_subparsers.add_parser(
        "get",
        help="Get details of an API key.",
    )
    apikey_get_parser.add_argument(
        "key",
        help="The API key value to look up.",
    )

    apikey_delete_parser = apikey_subparsers.add_parser(
        "delete",
        help="Delete an API key.",
    )
    apikey_delete_parser.add_argument(
        "key",
        help="The API key value to delete.",
    )

    apikey_update_parser = apikey_subparsers.add_parser(
        "update",
        help="Update an API key's access level.",
    )
    apikey_update_parser.add_argument(
        "key",
        help="The API key value to update.",
    )
    apikey_update_parser.add_argument(
        "--access",
        required=True,
        choices=["read", "read/write"],
        help="New access level: 'read' or 'read/write'.",
    )

    # -- configure-ldap subcommand --
    ldap_parser = subparsers.add_parser(
        "configure-ldap",
        help="Set or update LDAP configuration in Secrets Manager.",
    )
    ldap_parser.add_argument(
        "--secret-arn",
        default=None,
        help="Secrets Manager secret ARN. Falls back to configured value.",
    )
    ldap_parser.add_argument(
        "--host",
        required=True,
        help="LDAP/AD server hostname.",
    )
    ldap_parser.add_argument(
        "--bind-user",
        required=True,
        help="DN or username for the LDAP bind connection.",
    )
    ldap_parser.add_argument(
        "--bind-password",
        required=True,
        help="Password for the LDAP bind connection.",
    )
    ldap_parser.add_argument(
        "--entitlement-group",
        required=True,
        help="DN of the group used for read entitlement checks.",
    )
    ldap_parser.add_argument(
        "--write-entitlement-group",
        default="",
        help="DN of the group used for write (upload) entitlement checks.",
    )

    # -- deploy subcommand --
    _add_deploy_subparser(subparsers)

    # -- pip subcommand --
    pip_parser = subparsers.add_parser(
        "pip",
        help="Generate pip configuration for the private PyPI server.",
    )
    pip_parser.add_argument(
        "--save",
        action="store_true",
        default=False,
        help="Save the pip config to the user's home directory.",
    )

    # -- twine subcommand --
    twine_parser = subparsers.add_parser(
        "twine",
        help="Generate twine configuration for uploading to the private PyPI server.",
    )
    twine_parser.add_argument(
        "--save",
        action="store_true",
        default=False,
        help="Save the .pypirc config to the user's home directory.",
    )

    return parser


def _add_deploy_subparser(subparsers) -> None:  # pylint: disable=too-many-statements
    """Add the deploy subcommand parser with all its arguments."""
    deploy_parser = subparsers.add_parser(
        "deploy",
        help="Deploy the CloudFormation stack.",
    )
    deploy_parser.add_argument(
        "--stack-name",
        default=None,
        help="Name of the CloudFormation stack.",
    )
    deploy_parser.add_argument(
        "--update",
        default=None,
        metavar="STACK_NAME",
        help="Update an existing stack, prompting with current parameter values.",
    )
    deploy_parser.add_argument(
        "--profile",
        default=None,
        help="AWS CLI / boto3 named profile.",
    )
    deploy_parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1).",
    )
    deploy_parser.add_argument(
        "--stack-name-prefix",
        default=None,
        help="Prefix used for naming resources (default: s3-pypi).",
    )
    deploy_parser.add_argument(
        "--cache-ttl",
        default=None,
        help="CloudFront default cache TTL in seconds (default: 300).",
    )
    deploy_parser.add_argument(
        "--domain-name",
        default=None,
        help="Optional custom domain name for CloudFront.",
    )
    deploy_parser.add_argument(
        "--acm-certificate-arn",
        default=None,
        help="Optional ACM certificate ARN for the custom domain.",
    )
    deploy_parser.add_argument(
        "--enable-kms-encryption",
        default=None,
        choices=["true", "false"],
        help="Enable KMS encryption at rest (default: false).",
    )
    deploy_parser.add_argument(
        "--enable-authorizer",
        default=None,
        choices=["true", "false"],
        help="Enable API Gateway authorizer (default: false).",
    )
    deploy_parser.add_argument(
        "--subnet-ids",
        default=None,
        help="Comma-separated subnet IDs for Lambda VPC placement.",
    )
    deploy_parser.add_argument(
        "--vpc-id",
        default=None,
        help="VPC ID for Lambda VPC placement.",
    )


def _handle_configure(args: argparse.Namespace) -> None:
    """Handle the configure subcommand."""
    # If --from-stack is provided, import config from stack outputs
    if args.from_stack:
        new_values = _configure_from_stack(args.from_stack, args.region, args.profile)
    else:
        new_values = {
            "bucket": args.bucket,
            "cloudfront_distribution_id": args.cloudfront_distribution_id,
            "api_key_table_name": args.api_key_table_name,
            "ldap_secret_arn": args.ldap_secret_arn,
        }

        # If no flags provided, enter interactive mode
        if all(v is None for v in new_values.values()):
            new_values = _interactive_configure()

    try:
        merged = save_config(new_values)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(merged, indent=2))


def _configure_from_stack(
    stack_name: str,
    region: str,
    profile: str | None,
) -> dict[str, str | None]:
    """Import configuration from a CloudFormation stack's outputs.

    Args:
        stack_name: Name of the CloudFormation stack.
        region: AWS region.
        profile: Optional boto3 named profile.

    Returns:
        A dict of configuration values from the stack outputs.
    """
    from s3pypi.deploy import _get_stack_outputs  # pylint: disable=import-outside-toplevel

    session_kwargs: dict = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    session = boto3.Session(**session_kwargs)
    cf_client = session.client("cloudformation")

    try:
        result = _get_stack_outputs(cf_client, stack_name)
    except ClientError as exc:
        print(f"error: failed to describe stack '{stack_name}': {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if not result:
        print(f"warning: no recognized outputs found in stack '{stack_name}'",
              file=sys.stderr)

    return result


def _interactive_configure() -> dict[str, str | None]:
    """Prompt the user interactively for each configuration value.

    Displays the current value in brackets. Empty input keeps the
    existing value.

    Returns:
        A dict of configuration values (None for unchanged keys).
    """
    try:
        existing = load_config()
    except ValueError:
        existing = {}

    prompts = [
        ("bucket", "S3 bucket name"),
        ("cloudfront_distribution_id", "CloudFront distribution ID"),
        ("api_key_table_name", "DynamoDB API key table name"),
        ("ldap_secret_arn", "Secrets Manager LDAP secret ARN"),
    ]

    new_values: dict[str, str | None] = {}
    for key, label in prompts:
        current = existing.get(key, "")
        if current:
            response = input(f"{label} [{current}]: ")
        else:
            response = input(f"{label}: ")

        if response.strip():
            new_values[key] = response.strip()
        else:
            new_values[key] = None

    return new_values


def _handle_upload(args: argparse.Namespace) -> None:
    """Handle the upload subcommand."""
    bucket = args.bucket
    cf_distribution_id = args.cloudfront_distribution_id

    # Fall back to config for missing values
    if bucket is None or cf_distribution_id is None:
        try:
            config = load_config()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

        if bucket is None:
            bucket = config.get("bucket")
        if cf_distribution_id is None:
            cf_distribution_id = config.get("cloudfront_distribution_id")

    if bucket is None:
        print(
            "error: --bucket is required (not provided and not found in config)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        uploader = S3PyPIUploader(bucket=bucket)
        uploader.upload(args.dist_file)

        if cf_distribution_id:
            filename = os.path.basename(args.dist_file)
            name, _version, _ext = parse_distribution_filename(filename)
            normalized = normalize_name(name)
            paths = ["/simple/", f"/simple/{normalized}/"]
            create_invalidation(cf_distribution_id, paths)

    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    except ClientError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


def _handle_apikey(args: argparse.Namespace) -> None:
    """Handle the apikey subcommand."""
    if args.action is None:
        print(
            "error: apikey requires an action (create, list, get, delete, update)",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # Resolve table name
    table_name = args.table_name
    if table_name is None:
        try:
            config = load_config()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
        table_name = config.get("api_key_table_name")

    if table_name is None:
        print(
            "error: --table-name is required (not provided and not found in config)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        _dispatch_apikey_action(args, table_name)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    except ClientError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


def _dispatch_apikey_action(args: argparse.Namespace, table_name: str) -> None:
    """Dispatch to the appropriate apikey action handler."""
    if args.action == "create":
        key = create_api_key(table_name, description=args.description, access=args.access)
        print(key)
    elif args.action == "list":
        keys = list_api_keys(table_name)
        if not keys:
            print("No API keys found.")
        else:
            fmt = "{:<38} {:<12} {:<24} {}"
            print(fmt.format("API_KEY", "ACCESS", "CREATED_AT", "DESCRIPTION"))
            print(fmt.format("-" * 36, "-" * 10, "-" * 22, "-" * 30))
            for record in keys:
                print(fmt.format(
                    record["api_key"],
                    record["access"],
                    record["created_at"][:22],
                    record["description"],
                ))
    elif args.action == "get":
        record = get_api_key(table_name, args.key)
        print(json.dumps(record, indent=2))
    elif args.action == "delete":
        delete_api_key(table_name, args.key)
        print(f"Deleted API key: {args.key}")
    elif args.action == "update":
        update_api_key(table_name, args.key, access=args.access)
        print(f"Updated API key: {args.key} (access: {args.access})")


def _handle_configure_ldap(args: argparse.Namespace) -> None:
    """Handle the configure-ldap subcommand."""
    # Resolve secret ARN
    secret_arn = args.secret_arn
    if secret_arn is None:
        try:
            config = load_config()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
        secret_arn = config.get("ldap_secret_arn")

    if secret_arn is None:
        print(
            "error: --secret-arn is required (not provided and not found in config)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        update_ldap_secret(
            secret_arn=secret_arn,
            host=args.host,
            bind_user=args.bind_user,
            bind_password=args.bind_password,
            entitlement_group=args.entitlement_group,
            write_entitlement_group=args.write_entitlement_group,
        )
        print("LDAP configuration updated successfully.")
    except ClientError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


def _handle_deploy(args: argparse.Namespace) -> None:
    """Handle the deploy subcommand."""
    stack_name = args.stack_name
    region = args.region
    profile = args.profile
    parameters = _collect_deploy_parameters(args)

    # --update mode: fetch current params and prompt for changes
    if args.update:
        stack_name = args.update
        stack_name, region, profile, parameters = _interactive_update(
            stack_name, region, profile, parameters,
        )
    elif stack_name is None:
        # No stack-name provided, enter interactive mode for new deploy
        stack_name, region, profile, parameters = _interactive_deploy(
            region, profile, parameters,
        )

    print(f"Deploying stack '{stack_name}' in {region}...")

    try:
        outputs = deploy_stack(
            stack_name=stack_name,
            region=region,
            profile=profile,
            parameters=parameters,
        )
    except DeployError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    # Save outputs to config
    try:
        merged = save_config(outputs)
    except (OSError, ValueError) as exc:
        print(f"warning: failed to save config: {exc}", file=sys.stderr)
        merged = outputs

    print(f"Stack '{stack_name}' deployed successfully.")
    print("")
    print("Configuration saved:")
    print(json.dumps(merged, indent=2))


# Map CLI flag names to CloudFormation parameter keys
_DEPLOY_PARAM_MAP = {
    "stack_name_prefix": "StackNamePrefix",
    "cache_ttl": "CacheTTL",
    "domain_name": "DomainName",
    "acm_certificate_arn": "AcmCertificateArn",
    "enable_kms_encryption": "EnableKMSEncryption",
    "enable_authorizer": "EnableAuthorizer",
    "subnet_ids": "SubnetIds",
    "vpc_id": "VpcId",
}

# Template parameter defaults for interactive prompts
_TEMPLATE_DEFAULTS = {
    "StackNamePrefix": "s3-pypi",
    "CacheTTL": "300",
    "DomainName": "",
    "AcmCertificateArn": "",
    "EnableKMSEncryption": "false",
    "EnableAuthorizer": "false",
    "SubnetIds": "",
    "VpcId": "",
}


def _collect_deploy_parameters(args: argparse.Namespace) -> dict[str, str]:
    """Collect CloudFormation parameters from CLI flags."""
    parameters: dict[str, str] = {}
    for attr, cfn_key in _DEPLOY_PARAM_MAP.items():
        value = getattr(args, attr, None)
        if value is not None:
            parameters[cfn_key] = value
    return parameters


def _interactive_deploy(
    region: str,
    profile: str | None,
    parameters: dict[str, str],
) -> tuple[str, str, str | None, dict[str, str]]:
    """Prompt the user interactively for deploy settings.

    Returns:
        Tuple of (stack_name, region, profile, parameters).
    """
    stack_name = input("Stack name (required): ").strip()
    if not stack_name:
        print("error: stack name is required", file=sys.stderr)
        raise SystemExit(2)

    response = input(f"AWS region [{region}]: ").strip()
    if response:
        region = response

    response = input(f"AWS profile [{profile or ''}]: ").strip()
    if response:
        profile = response

    # Prompt for each template parameter
    prompts = [
        ("StackNamePrefix", "Stack name prefix"),
        ("CacheTTL", "Cache TTL (seconds)"),
        ("DomainName", "Custom domain name"),
        ("AcmCertificateArn", "ACM certificate ARN"),
        ("EnableKMSEncryption", "Enable KMS encryption (true/false)"),
        ("EnableAuthorizer", "Enable authorizer (true/false)"),
        ("SubnetIds", "Subnet IDs (comma-separated)"),
        ("VpcId", "VPC ID"),
    ]

    for cfn_key, label in prompts:
        # Use already-set value or template default
        current = parameters.get(cfn_key, _TEMPLATE_DEFAULTS.get(cfn_key, ""))
        if current:
            response = input(f"{label} [{current}]: ").strip()
        else:
            response = input(f"{label}: ").strip()

        if response:
            parameters[cfn_key] = response
        # Empty input means use template default — don't include in parameters

    return stack_name, region, profile, parameters


def _interactive_update(
    stack_name: str,
    region: str,
    profile: str | None,
    parameters: dict[str, str],
) -> tuple[str, str, str | None, dict[str, str]]:
    """Prompt the user to update an existing stack's parameters.

    Fetches current parameter values from the stack and uses them as
    defaults in the prompts. Empty input keeps the current value.

    Returns:
        Tuple of (stack_name, region, profile, parameters).
    """
    # Fetch current parameters from the stack
    session_kwargs: dict = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile

    cf_client = boto3.Session(**session_kwargs).client("cloudformation")

    try:
        response = cf_client.describe_stacks(StackName=stack_name)
    except ClientError as exc:
        print(f"error: failed to describe stack '{stack_name}': {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    stacks = response.get("Stacks", [])
    if not stacks:
        print(f"error: stack '{stack_name}' not found", file=sys.stderr)
        raise SystemExit(1)

    # Build current values from stack parameters
    current_params: dict[str, str] = {}
    for param in stacks[0].get("Parameters", []):
        current_params[param["ParameterKey"]] = param["ParameterValue"]

    print(f"Updating stack '{stack_name}' — press Enter to keep current values.")
    print("")

    # Prompt for each template parameter using current stack values as defaults
    prompts = [
        ("StackNamePrefix", "Stack name prefix"),
        ("CacheTTL", "Cache TTL (seconds)"),
        ("DomainName", "Custom domain name"),
        ("AcmCertificateArn", "ACM certificate ARN"),
        ("EnableKMSEncryption", "Enable KMS encryption (true/false)"),
        ("EnableAuthorizer", "Enable authorizer (true/false)"),
        ("SubnetIds", "Subnet IDs (comma-separated)"),
        ("VpcId", "VPC ID"),
    ]

    for cfn_key, label in prompts:
        # CLI flag overrides take priority, then current stack value, then template default
        current = parameters.get(
            cfn_key,
            current_params.get(cfn_key, _TEMPLATE_DEFAULTS.get(cfn_key, "")),
        )
        if current:
            response = input(f"{label} [{current}]: ").strip()
        else:
            response = input(f"{label}: ").strip()

        if response:
            parameters[cfn_key] = response
        elif current:
            # Keep the current value
            parameters[cfn_key] = current

    return stack_name, region, profile, parameters


def _handle_pip(args: argparse.Namespace) -> None:  # pylint: disable=too-many-locals
    """Generate pip configuration using keyring for credential storage."""
    from s3pypi.pip_config import (  # pylint: disable=import-outside-toplevel
        extract_host,
        format_pip_config_inline,
        format_pip_config_keyring,
        get_pip_config_path,
        prompt_pip_credentials,
        store_in_keyring,
    )

    try:
        config = load_config()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    cloudfront_url = config.get("cloudfront_url", "")
    if not cloudfront_url:
        print(
            "error: cloudfront_url not found in config. "
            "Run 's3pypi deploy' or 's3pypi configure --from-stack <name>' first.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    username, password = prompt_pip_credentials()
    host = extract_host(cloudfront_url)
    keyring_ok = store_in_keyring(host, username, password)

    if keyring_ok:
        pip_config = format_pip_config_keyring(cloudfront_url)
    else:
        pip_config = format_pip_config_inline(cloudfront_url, username, password)

    if args.save:
        pip_config_path = get_pip_config_path()
        pip_config_path.parent.mkdir(parents=True, exist_ok=True)
        pip_config_path.write_text(pip_config + "\n", encoding="utf-8")
        print(f"\nSaved to {pip_config_path}")
    else:
        print("")
        print(f"# Add the following to {get_pip_config_path()} :")
        print("")
        print(pip_config)


def _handle_twine(args: argparse.Namespace) -> None:
    """Generate twine (.pypirc) configuration using keyring for credentials."""
    from s3pypi.pip_config import (  # pylint: disable=import-outside-toplevel
        extract_host,
        format_pypirc,
        prompt_twine_credentials,
        store_in_keyring,
    )

    try:
        config = load_config()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    # Use API Gateway URL directly for uploads (bypasses CloudFront)
    upload_url = config.get("api_gateway_url", "")
    if not upload_url:
        # Fall back to cloudfront_url if api_gateway_url not available
        upload_url = config.get("cloudfront_url", "")
    if not upload_url:
        print(
            "error: api_gateway_url or cloudfront_url not found in config. "
            "Run 's3pypi deploy' or 's3pypi configure --from-stack <name>' first.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    username, password = prompt_twine_credentials()
    host = extract_host(upload_url)
    keyring_ok = store_in_keyring(host, username, password)

    pypirc_content = format_pypirc(upload_url, username, keyring_ok)

    if args.save:
        pypirc_path = Path.home() / ".pypirc"
        pypirc_path.write_text(pypirc_content + "\n", encoding="utf-8")
        pypirc_path.chmod(0o600)
        print(f"\nSaved to {pypirc_path} (permissions: 600)")
    else:
        print("")
        print(f"# Add the following to {Path.home() / '.pypirc'} :")
        print("")
        print(pypirc_content)

    print("")
    print("# Upload with:")
    print("#   twine upload --repository private dist/*")
