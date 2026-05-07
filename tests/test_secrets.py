"""Unit tests for s3pypi.secrets module."""

from __future__ import annotations

import json

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from s3pypi.secrets import update_ldap_secret

SECRET_ARN = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-ldap"


@pytest.fixture
def sm_client():
    """Create a mocked Secrets Manager client with a pre-existing secret."""
    with mock_aws():
        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(
            Name="test-ldap",
            SecretString='{"host":"","bind_user":"","bind_password":"","entitlement_group":""}',
        )
        yield client


class TestUpdateLdapSecret:
    """Tests for update_ldap_secret."""

    def test_writes_correct_json_structure(self, sm_client):
        """update_ldap_secret writes the correct JSON to the secret."""
        update_ldap_secret(
            secret_arn="test-ldap",
            host="ldap.example.com",
            bind_user="cn=admin,dc=example,dc=com",
            bind_password="s3cret",
            entitlement_group="cn=pypi-users,ou=groups,dc=example,dc=com",
            write_entitlement_group="cn=pypi-writers,ou=groups,dc=example,dc=com",
            sm_client=sm_client,
        )
        response = sm_client.get_secret_value(SecretId="test-ldap")
        data = json.loads(response["SecretString"])
        assert data["host"] == "ldap.example.com"
        assert data["bind_user"] == "cn=admin,dc=example,dc=com"
        assert data["bind_password"] == "s3cret"
        assert data["entitlement_group"] == "cn=pypi-users,ou=groups,dc=example,dc=com"
        assert data["write_entitlement_group"] == "cn=pypi-writers,ou=groups,dc=example,dc=com"

    def test_write_entitlement_group_defaults_empty(self, sm_client):
        """update_ldap_secret defaults write_entitlement_group to empty string."""
        update_ldap_secret(
            secret_arn="test-ldap",
            host="ldap.example.com",
            bind_user="admin",
            bind_password="pass",
            entitlement_group="group",
            sm_client=sm_client,
        )
        response = sm_client.get_secret_value(SecretId="test-ldap")
        data = json.loads(response["SecretString"])
        assert data["write_entitlement_group"] == ""

    def test_overwrites_existing_values(self, sm_client):
        """update_ldap_secret overwrites previous secret values."""
        update_ldap_secret(
            secret_arn="test-ldap",
            host="ldap1.example.com",
            bind_user="user1",
            bind_password="pass1",
            entitlement_group="group1",
            sm_client=sm_client,
        )
        update_ldap_secret(
            secret_arn="test-ldap",
            host="ldap2.example.com",
            bind_user="user2",
            bind_password="pass2",
            entitlement_group="group2",
            sm_client=sm_client,
        )
        response = sm_client.get_secret_value(SecretId="test-ldap")
        data = json.loads(response["SecretString"])
        assert data["host"] == "ldap2.example.com"
        assert data["bind_user"] == "user2"

    def test_propagates_client_error(self, sm_client):
        """update_ldap_secret propagates ClientError for invalid secret."""
        with pytest.raises(ClientError):
            update_ldap_secret(
                secret_arn="nonexistent-secret-arn",
                host="ldap.example.com",
                bind_user="admin",
                bind_password="pass",
                entitlement_group="group",
                sm_client=sm_client,
            )
