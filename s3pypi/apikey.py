"""API key management for DynamoDB-backed authentication."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import boto3

VALID_ACCESS_LEVELS = ("read", "read/write")


def create_api_key(
    table_name: str,
    description: str | None = None,
    access: str = "read",
    dynamodb_client=None,
) -> str:
    """Generate a new API key and store it in DynamoDB.

    Args:
        table_name: Name of the DynamoDB table.
        description: Optional description for the key.
        access: Access level - 'read' or 'read/write'. Defaults to 'read'.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).

    Returns:
        The generated API key string.

    Raises:
        ValueError: If access is not a valid access level.
    """
    if access not in VALID_ACCESS_LEVELS:
        raise ValueError(
            f"Invalid access level: {access}. Must be one of: {VALID_ACCESS_LEVELS}"
        )

    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")

    api_key = str(uuid.uuid4())
    item: dict = {
        "api_key": {"S": api_key},
        "created_at": {"S": datetime.now(timezone.utc).isoformat()},
        "access": {"S": access},
    }
    if description:
        item["description"] = {"S": description}

    dynamodb_client.put_item(TableName=table_name, Item=item)
    return api_key


def list_api_keys(
    table_name: str,
    dynamodb_client=None,
) -> list[dict]:
    """List all API keys in the DynamoDB table.

    Args:
        table_name: Name of the DynamoDB table.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).

    Returns:
        A list of dicts with keys: api_key, description, created_at, access.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")

    response = dynamodb_client.scan(TableName=table_name)
    results = []
    for item in response.get("Items", []):
        record = {
            "api_key": item["api_key"]["S"],
            "created_at": item.get("created_at", {}).get("S", ""),
            "access": item.get("access", {}).get("S", "read"),
        }
        if "description" in item:
            record["description"] = item["description"]["S"]
        else:
            record["description"] = ""
        results.append(record)
    return results


def get_api_key(
    table_name: str,
    api_key: str,
    dynamodb_client=None,
) -> dict:
    """Retrieve a single API key record from DynamoDB.

    Args:
        table_name: Name of the DynamoDB table.
        api_key: The API key value to look up.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).

    Returns:
        A dict with keys: api_key, description, created_at, access.

    Raises:
        KeyError: If the API key does not exist in the table.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")

    response = dynamodb_client.get_item(
        TableName=table_name,
        Key={"api_key": {"S": api_key}},
    )
    if "Item" not in response:
        raise KeyError(f"API key not found: {api_key}")

    item = response["Item"]
    record = {
        "api_key": item["api_key"]["S"],
        "created_at": item.get("created_at", {}).get("S", ""),
        "access": item.get("access", {}).get("S", "read"),
    }
    if "description" in item:
        record["description"] = item["description"]["S"]
    else:
        record["description"] = ""
    return record


def update_api_key(
    table_name: str,
    api_key: str,
    access: str,
    dynamodb_client=None,
) -> None:
    """Update the access level of an API key in DynamoDB.

    Args:
        table_name: Name of the DynamoDB table.
        api_key: The API key value to update.
        access: New access level - 'read' or 'read/write'.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).

    Raises:
        KeyError: If the API key does not exist in the table.
        ValueError: If access is not a valid access level.
    """
    if access not in VALID_ACCESS_LEVELS:
        raise ValueError(
            f"Invalid access level: {access}. Must be one of: {VALID_ACCESS_LEVELS}"
        )

    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")

    # Check existence first
    response = dynamodb_client.get_item(
        TableName=table_name,
        Key={"api_key": {"S": api_key}},
    )
    if "Item" not in response:
        raise KeyError(f"API key not found: {api_key}")

    dynamodb_client.update_item(
        TableName=table_name,
        Key={"api_key": {"S": api_key}},
        UpdateExpression="SET #acc = :access",
        ExpressionAttributeNames={"#acc": "access"},
        ExpressionAttributeValues={":access": {"S": access}},
    )


def delete_api_key(
    table_name: str,
    api_key: str,
    dynamodb_client=None,
) -> None:
    """Delete an API key from DynamoDB.

    Args:
        table_name: Name of the DynamoDB table.
        api_key: The API key value to delete.
        dynamodb_client: Optional boto3 DynamoDB client (for testing).

    Raises:
        KeyError: If the API key does not exist in the table.
    """
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")

    # Check existence first
    response = dynamodb_client.get_item(
        TableName=table_name,
        Key={"api_key": {"S": api_key}},
    )
    if "Item" not in response:
        raise KeyError(f"API key not found: {api_key}")

    dynamodb_client.delete_item(
        TableName=table_name,
        Key={"api_key": {"S": api_key}},
    )
