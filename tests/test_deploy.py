"""Unit tests for s3pypi.deploy module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from s3pypi.deploy import DeployError, deploy_stack, load_template, TEMPLATE_PATH


class TestLoadTemplate:
    """Tests for load_template."""

    def test_template_exists_in_package(self):
        """The template file exists at the expected package path."""
        assert TEMPLATE_PATH.is_file()

    def test_load_template_returns_string(self):
        """load_template returns the template as a string."""
        content = load_template()
        assert isinstance(content, str)
        assert "AWSTemplateFormatVersion" in content
        assert "Resources" in content

    def test_load_template_raises_if_missing(self, tmp_path):
        """load_template raises FileNotFoundError if template is missing."""
        with patch("s3pypi.deploy.TEMPLATE_PATH", tmp_path / "nonexistent.yaml"):
            with pytest.raises(FileNotFoundError):
                load_template()


class TestDeployStack:
    """Tests for deploy_stack."""

    def test_creates_stack_when_not_exists(self):
        """deploy_stack calls create_stack for new stacks."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        # First call: _stack_exists → not found
        # Second call: _get_stack_outputs → returns outputs
        mock_client.describe_stacks.side_effect = [
            ClientError({"Error": {"Code": "ValidationError", "Message": "not exist"}}, "DescribeStacks"),
            {"Stacks": [{"Outputs": [
                {"OutputKey": "BucketName", "OutputValue": "my-bucket-123"},
                {"OutputKey": "PyPIEndpoint", "OutputValue": "d123.cloudfront.net"},
            ]}]},
        ]
        mock_client.get_waiter.return_value.wait.return_value = None

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("s3pypi.deploy.boto3.Session", return_value=mock_session):
            result = deploy_stack("test-stack", region="us-east-1")

        mock_client.create_stack.assert_called_once()
        assert result["bucket"] == "my-bucket-123"

    def test_updates_stack_when_exists(self):
        """deploy_stack calls update_stack for existing stacks."""
        mock_client = MagicMock()
        mock_client.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE", "Outputs": [
                {"OutputKey": "BucketName", "OutputValue": "bucket-abc"},
            ]}]
        }
        mock_client.get_waiter.return_value.wait.return_value = None

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("s3pypi.deploy.boto3.Session", return_value=mock_session):
            result = deploy_stack("test-stack")

        mock_client.update_stack.assert_called_once()
        assert result["bucket"] == "bucket-abc"

    def test_passes_parameters(self):
        """deploy_stack passes parameter overrides to CloudFormation."""
        mock_client = MagicMock()
        mock_client.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE", "Outputs": []}]
        }
        mock_client.get_waiter.return_value.wait.return_value = None

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("s3pypi.deploy.boto3.Session", return_value=mock_session):
            deploy_stack("s", parameters={"CacheTTL": "600"})

        call_kwargs = mock_client.update_stack.call_args[1]
        assert {"ParameterKey": "CacheTTL", "ParameterValue": "600"} in call_kwargs["Parameters"]

    def test_passes_profile_and_region(self):
        """deploy_stack creates session with profile and region."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_client.describe_stacks.side_effect = [
            ClientError({"Error": {"Code": "ValidationError", "Message": "not exist"}}, "DescribeStacks"),
            {"Stacks": [{"Outputs": []}]},
        ]
        mock_client.get_waiter.return_value.wait.return_value = None

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("s3pypi.deploy.boto3.Session", return_value=mock_session) as mock_sess_cls:
            deploy_stack("s", region="eu-west-1", profile="myprofile")

        mock_sess_cls.assert_called_once_with(region_name="eu-west-1", profile_name="myprofile")

    def test_raises_deploy_error_on_failure(self):
        """deploy_stack raises DeployError when deployment fails."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_client.describe_stacks.side_effect = [
            ClientError({"Error": {"Code": "ValidationError", "Message": "not exist"}}, "DescribeStacks"),
        ]
        mock_client.create_stack.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Template error"}},
            "CreateStack",
        )
        mock_client.describe_stack_events.return_value = {"StackEvents": []}

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("s3pypi.deploy.boto3.Session", return_value=mock_session):
            with pytest.raises(DeployError, match="Template error"):
                deploy_stack("bad-stack")

    def test_maps_outputs_to_config_keys(self):
        """deploy_stack maps CloudFormation output keys to config keys."""
        mock_client = MagicMock()
        mock_client.describe_stacks.return_value = {
            "Stacks": [{"StackStatus": "CREATE_COMPLETE", "Outputs": [
                {"OutputKey": "BucketName", "OutputValue": "b"},
                {"OutputKey": "PyPIEndpoint", "OutputValue": "d.cloudfront.net"},
                {"OutputKey": "CloudFrontDistributionId", "OutputValue": "E1234567890ABC"},
                {"OutputKey": "CloudFrontURL", "OutputValue": "https://d.cloudfront.net/simple/"},
                {"OutputKey": "ApiGatewayURL", "OutputValue": "https://api.execute-api.us-east-1.amazonaws.com/prod/simple/"},
                {"OutputKey": "APIKeyTableName", "OutputValue": "table-xyz"},
                {"OutputKey": "LDAPSecretArn", "OutputValue": "arn:secret"},
                {"OutputKey": "KMSKeyArn", "OutputValue": "arn:kms:key"},
            ]}]
        }
        mock_client.get_waiter.return_value.wait.return_value = None

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("s3pypi.deploy.boto3.Session", return_value=mock_session):
            result = deploy_stack("s")

        assert result == {
            "bucket": "b",
            "pypi_endpoint": "d.cloudfront.net",
            "cloudfront_distribution_id": "E1234567890ABC",
            "cloudfront_url": "https://d.cloudfront.net/simple/",
            "api_gateway_url": "https://api.execute-api.us-east-1.amazonaws.com/prod/simple/",
            "api_key_table_name": "table-xyz",
            "ldap_secret_arn": "arn:secret",
            "kms_key_arn": "arn:kms:key",
        }
