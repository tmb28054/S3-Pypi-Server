"""CloudFront invalidation creation."""

import uuid

import boto3


def create_invalidation(distribution_id: str, paths: list[str]) -> str:
    """Create a CloudFront invalidation for the given paths.

    Uses the boto3 CloudFront client to invalidate cached objects so that
    updated index pages are served immediately.

    Args:
        distribution_id: The CloudFront distribution ID to invalidate.
        paths: A list of URL paths to invalidate (e.g. ["/simple/", "/simple/my-package/"]).

    Returns:
        The invalidation ID from the CloudFront response.

    Raises:
        botocore.exceptions.ClientError: If the CloudFront API call fails.
    """
    client = boto3.client("cloudfront")

    response = client.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            "Paths": {
                "Quantity": len(paths),
                "Items": paths,
            },
            "CallerReference": str(uuid.uuid4()),
        },
    )

    return response["Invalidation"]["Id"]
