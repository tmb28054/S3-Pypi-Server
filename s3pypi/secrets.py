"""Secrets Manager operations for LDAP configuration."""

from __future__ import annotations

import json

import boto3


def update_ldap_secret(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    secret_arn: str,
    host: str,
    bind_user: str,
    bind_password: str,
    entitlement_group: str,
    write_entitlement_group: str = "",
    sm_client=None,
) -> None:
    """Update the LDAP configuration secret in Secrets Manager.

    Args:
        secret_arn: ARN of the Secrets Manager secret.
        host: LDAP/AD server hostname.
        bind_user: DN or username for the LDAP bind connection.
        bind_password: Password for the LDAP bind connection.
        entitlement_group: DN of the group used for read entitlement checks.
        write_entitlement_group: DN of the group used for write (upload)
            entitlement checks. Defaults to empty string.
        sm_client: Optional boto3 Secrets Manager client (for testing).

    Raises:
        botocore.exceptions.ClientError: If the Secrets Manager
            operation fails.
    """
    if sm_client is None:
        sm_client = boto3.client("secretsmanager")

    secret_value = json.dumps({
        "host": host,
        "bind_user": bind_user,
        "bind_password": bind_password,
        "entitlement_group": entitlement_group,
        "write_entitlement_group": write_entitlement_group,
    })

    sm_client.put_secret_value(
        SecretId=secret_arn,
        SecretString=secret_value,
    )
