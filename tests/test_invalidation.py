"""Unit tests for s3pypi.invalidation module.

Validates: Requirements 8.1
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from s3pypi.invalidation import create_invalidation

DISTRIBUTION_ID = "E1234567890ABC"


@pytest.fixture
def mock_cf_client():
    """Create a mock CloudFront client that returns a successful invalidation response."""
    client = MagicMock()
    client.create_invalidation.return_value = {
        "Invalidation": {
            "Id": "INV123456",
            "Status": "InProgress",
        }
    }
    return client


class TestInvalidationCreatedWithCorrectPaths:
    """Test that invalidation is created with correct paths."""

    def test_single_path(self, mock_cf_client):
        with patch("s3pypi.invalidation.boto3.client", return_value=mock_cf_client):
            result = create_invalidation(DISTRIBUTION_ID, ["/simple/"])

        assert result == "INV123456"
        call_args = mock_cf_client.create_invalidation.call_args
        assert call_args.kwargs["DistributionId"] == DISTRIBUTION_ID
        batch = call_args.kwargs["InvalidationBatch"]
        assert batch["Paths"]["Quantity"] == 1
        assert batch["Paths"]["Items"] == ["/simple/"]

    def test_multiple_paths(self, mock_cf_client):
        paths = ["/simple/", "/simple/my-package/"]
        with patch("s3pypi.invalidation.boto3.client", return_value=mock_cf_client):
            result = create_invalidation(DISTRIBUTION_ID, paths)

        assert result == "INV123456"
        call_args = mock_cf_client.create_invalidation.call_args
        batch = call_args.kwargs["InvalidationBatch"]
        assert batch["Paths"]["Quantity"] == 2
        assert batch["Paths"]["Items"] == ["/simple/", "/simple/my-package/"]

    def test_caller_reference_is_unique(self, mock_cf_client):
        """Each call should use a unique CallerReference (UUID)."""
        references = []

        def capture_call(**kwargs):
            references.append(kwargs["InvalidationBatch"]["CallerReference"])
            return {"Invalidation": {"Id": "INV1", "Status": "InProgress"}}

        mock_cf_client.create_invalidation.side_effect = capture_call

        with patch("s3pypi.invalidation.boto3.client", return_value=mock_cf_client):
            create_invalidation(DISTRIBUTION_ID, ["/simple/"])
            create_invalidation(DISTRIBUTION_ID, ["/simple/"])

        assert len(references) == 2
        assert references[0] != references[1]

    def test_returns_invalidation_id(self, mock_cf_client):
        mock_cf_client.create_invalidation.return_value = {
            "Invalidation": {"Id": "CUSTOM_ID_789", "Status": "InProgress"}
        }
        with patch("s3pypi.invalidation.boto3.client", return_value=mock_cf_client):
            result = create_invalidation(DISTRIBUTION_ID, ["/simple/"])

        assert result == "CUSTOM_ID_789"

    def test_creates_cloudfront_client(self, mock_cf_client):
        """Verify that boto3.client is called with 'cloudfront'."""
        with patch("s3pypi.invalidation.boto3.client", return_value=mock_cf_client) as mock_boto:
            create_invalidation(DISTRIBUTION_ID, ["/simple/"])

        mock_boto.assert_called_once_with("cloudfront")


class TestErrorPropagation:
    """Test error propagation for CloudFront failures."""

    def test_client_error_propagates(self):
        mock_client = MagicMock()
        mock_client.create_invalidation.side_effect = ClientError(
            error_response={"Error": {"Code": "NoSuchDistribution", "Message": "Distribution not found"}},
            operation_name="CreateInvalidation",
        )

        with patch("s3pypi.invalidation.boto3.client", return_value=mock_client):
            with pytest.raises(ClientError, match="NoSuchDistribution"):
                create_invalidation("INVALID_DIST_ID", ["/simple/"])

    def test_access_denied_error_propagates(self):
        mock_client = MagicMock()
        mock_client.create_invalidation.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            operation_name="CreateInvalidation",
        )

        with patch("s3pypi.invalidation.boto3.client", return_value=mock_client):
            with pytest.raises(ClientError, match="AccessDenied"):
                create_invalidation(DISTRIBUTION_ID, ["/simple/"])
