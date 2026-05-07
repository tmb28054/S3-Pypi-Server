"""Unit tests for s3pypi.apikey module."""

from __future__ import annotations

import uuid

import boto3
import pytest
from moto import mock_aws

from s3pypi.apikey import create_api_key, delete_api_key, get_api_key, list_api_keys, update_api_key

TABLE_NAME = "test-api-keys"


@pytest.fixture
def dynamodb_table():
    """Create a mocked DynamoDB table for testing."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "api_key", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "api_key", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client


class TestCreateApiKey:
    """Tests for create_api_key."""

    def test_creates_valid_uuid_key(self, dynamodb_table):
        """create_api_key generates a valid UUID and stores it."""
        key = create_api_key(TABLE_NAME, dynamodb_client=dynamodb_table)
        # Should be a valid UUID
        uuid.UUID(key)
        # Should exist in the table
        response = dynamodb_table.get_item(
            TableName=TABLE_NAME, Key={"api_key": {"S": key}}
        )
        assert "Item" in response
        assert response["Item"]["api_key"]["S"] == key
        assert "created_at" in response["Item"]
        assert response["Item"]["access"]["S"] == "read"

    def test_creates_key_with_description(self, dynamodb_table):
        """create_api_key stores description alongside the key."""
        key = create_api_key(
            TABLE_NAME, description="CI pipeline key", dynamodb_client=dynamodb_table
        )
        response = dynamodb_table.get_item(
            TableName=TABLE_NAME, Key={"api_key": {"S": key}}
        )
        assert response["Item"]["description"]["S"] == "CI pipeline key"

    def test_creates_key_without_description(self, dynamodb_table):
        """create_api_key omits description field when not provided."""
        key = create_api_key(TABLE_NAME, dynamodb_client=dynamodb_table)
        response = dynamodb_table.get_item(
            TableName=TABLE_NAME, Key={"api_key": {"S": key}}
        )
        assert "description" not in response["Item"]

    def test_creates_key_with_readwrite_access(self, dynamodb_table):
        """create_api_key stores read/write access level."""
        key = create_api_key(TABLE_NAME, access="read/write", dynamodb_client=dynamodb_table)
        response = dynamodb_table.get_item(
            TableName=TABLE_NAME, Key={"api_key": {"S": key}}
        )
        assert response["Item"]["access"]["S"] == "read/write"

    def test_creates_key_with_default_read_access(self, dynamodb_table):
        """create_api_key defaults to read access."""
        key = create_api_key(TABLE_NAME, dynamodb_client=dynamodb_table)
        response = dynamodb_table.get_item(
            TableName=TABLE_NAME, Key={"api_key": {"S": key}}
        )
        assert response["Item"]["access"]["S"] == "read"


class TestListApiKeys:
    """Tests for list_api_keys."""

    def test_returns_empty_list_when_no_keys(self, dynamodb_table):
        """list_api_keys returns empty list for empty table."""
        result = list_api_keys(TABLE_NAME, dynamodb_client=dynamodb_table)
        assert result == []

    def test_returns_all_stored_keys(self, dynamodb_table):
        """list_api_keys returns all keys in the table."""
        key1 = create_api_key(
            TABLE_NAME, description="Key 1", dynamodb_client=dynamodb_table
        )
        key2 = create_api_key(
            TABLE_NAME, description="Key 2", access="read/write", dynamodb_client=dynamodb_table
        )
        result = list_api_keys(TABLE_NAME, dynamodb_client=dynamodb_table)
        keys = {r["api_key"] for r in result}
        assert key1 in keys
        assert key2 in keys
        assert len(result) == 2

    def test_includes_access_level(self, dynamodb_table):
        """list_api_keys includes access level in results."""
        create_api_key(TABLE_NAME, access="read/write", dynamodb_client=dynamodb_table)
        result = list_api_keys(TABLE_NAME, dynamodb_client=dynamodb_table)
        assert result[0]["access"] == "read/write"


class TestGetApiKey:
    """Tests for get_api_key."""

    def test_returns_correct_record(self, dynamodb_table):
        """get_api_key returns the matching record."""
        key = create_api_key(
            TABLE_NAME, description="test key", access="read/write", dynamodb_client=dynamodb_table
        )
        record = get_api_key(TABLE_NAME, key, dynamodb_client=dynamodb_table)
        assert record["api_key"] == key
        assert record["description"] == "test key"
        assert record["created_at"] != ""
        assert record["access"] == "read/write"

    def test_raises_key_error_for_nonexistent(self, dynamodb_table):
        """get_api_key raises KeyError for non-existent key."""
        with pytest.raises(KeyError, match="API key not found"):
            get_api_key(TABLE_NAME, "nonexistent-key", dynamodb_client=dynamodb_table)


class TestDeleteApiKey:
    """Tests for delete_api_key."""

    def test_removes_existing_key(self, dynamodb_table):
        """delete_api_key removes the key from the table."""
        key = create_api_key(TABLE_NAME, dynamodb_client=dynamodb_table)
        delete_api_key(TABLE_NAME, key, dynamodb_client=dynamodb_table)
        # Verify it's gone
        response = dynamodb_table.get_item(
            TableName=TABLE_NAME, Key={"api_key": {"S": key}}
        )
        assert "Item" not in response

    def test_raises_key_error_for_nonexistent(self, dynamodb_table):
        """delete_api_key raises KeyError for non-existent key."""
        with pytest.raises(KeyError, match="API key not found"):
            delete_api_key(
                TABLE_NAME, "nonexistent-key", dynamodb_client=dynamodb_table
            )


class TestUpdateApiKey:
    """Tests for update_api_key."""

    def test_updates_access_level(self, dynamodb_table):
        """update_api_key changes the access level."""
        key = create_api_key(TABLE_NAME, access="read", dynamodb_client=dynamodb_table)
        update_api_key(TABLE_NAME, key, access="read/write", dynamodb_client=dynamodb_table)
        record = get_api_key(TABLE_NAME, key, dynamodb_client=dynamodb_table)
        assert record["access"] == "read/write"

    def test_raises_key_error_for_nonexistent(self, dynamodb_table):
        """update_api_key raises KeyError for non-existent key."""
        with pytest.raises(KeyError, match="API key not found"):
            update_api_key(
                TABLE_NAME, "nonexistent-key", access="read/write",
                dynamodb_client=dynamodb_table,
            )
