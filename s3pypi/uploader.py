"""S3 upload and index regeneration orchestration."""

import os

import boto3

from s3pypi.index import generate_detail_page, generate_index_page
from s3pypi.packaging import normalize_name, parse_distribution_filename


class S3PyPIUploader:
    """Orchestrates package upload and index regeneration."""

    def __init__(self, bucket: str, s3_client=None):
        """Initialize with bucket name and optional S3 client (for testing)."""
        self.bucket = bucket
        self.s3_client = s3_client or boto3.client("s3")

    def upload(self, dist_path: str) -> None:
        """Upload a distribution file and regenerate affected index pages.

        Validates that the file exists, parses the package name from the
        filename, uploads to S3, and regenerates both the detail and root
        index pages.

        Raises:
            FileNotFoundError: If dist_path does not exist on the local filesystem.
            ValueError: If the filename format is not recognized.
            botocore.exceptions.ClientError: If any S3 operation fails.
        """
        if not os.path.isfile(dist_path):
            raise FileNotFoundError(f"Distribution file not found: {dist_path}")

        filename = os.path.basename(dist_path)
        name, _version, _ext = parse_distribution_filename(filename)
        normalized = normalize_name(name)

        s3_key = f"packages/{normalized}/{filename}"
        self._upload_file(dist_path, s3_key)

        self._regenerate_detail_page(normalized)
        self._regenerate_index_page()

    def _upload_file(self, local_path: str, s3_key: str) -> None:
        """Upload a single file to S3 using PutObject."""
        with open(local_path, "rb") as f:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=f.read(),
            )

    def _regenerate_detail_page(self, package_name: str) -> None:
        """List files for a package and regenerate its detail page.

        Lists all objects under ``packages/{package_name}/`` and writes
        the generated HTML to ``simple/{package_name}/index.html``.
        """
        prefix = f"packages/{package_name}/"
        filenames: list[str] = []

        paginator = self.s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                fname = key[len(prefix):]
                if fname:
                    filenames.append(fname)

        filenames.sort()

        html = generate_detail_page(package_name, filenames)
        detail_key = f"simple/{package_name}/index.html"
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=detail_key,
            Body=html.encode("utf-8"),
            ContentType="text/html",
        )

    def _regenerate_index_page(self) -> None:
        """List all packages and regenerate the root index page.

        Uses ``list_objects_v2`` with prefix ``packages/`` and delimiter ``/``
        to discover package "directories", then writes the generated HTML
        to ``simple/index.html``.
        """
        prefix = "packages/"
        package_names: list[str] = []

        paginator = self.s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.bucket, Prefix=prefix, Delimiter="/"
        ):
            for cp in page.get("CommonPrefixes", []):
                # CommonPrefixes entries look like "packages/my-package/"
                pkg = cp["Prefix"][len(prefix):].rstrip("/")
                if pkg:
                    package_names.append(pkg)

        package_names.sort()

        html = generate_index_page(package_names)
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key="simple/index.html",
            Body=html.encode("utf-8"),
            ContentType="text/html",
        )
