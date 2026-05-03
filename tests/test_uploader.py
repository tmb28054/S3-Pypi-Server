"""Unit tests for s3pypi.uploader module.

Validates: Requirements 8.1
"""

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from s3pypi.index import parse_detail_page, parse_index_page
from s3pypi.uploader import S3PyPIUploader

BUCKET = "test-pypi-bucket"


@pytest.fixture
def s3_client():
    """Create a mocked S3 client with a pre-created bucket."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture
def uploader(s3_client):
    """Create an S3PyPIUploader wired to the mocked S3 client."""
    return S3PyPIUploader(bucket=BUCKET, s3_client=s3_client)


class TestUploadPlacesFileAtCorrectKey:
    """Test that upload places file at correct S3 key packages/{normalized_name}/{filename}."""

    def test_wheel_upload_key(self, uploader, s3_client, tmp_path):
        dist = tmp_path / "my_package-1.0.0-py3-none-any.whl"
        dist.write_bytes(b"fake wheel content")

        uploader.upload(str(dist))

        obj = s3_client.get_object(
            Bucket=BUCKET,
            Key="packages/my-package/my_package-1.0.0-py3-none-any.whl",
        )
        assert obj["Body"].read() == b"fake wheel content"

    def test_sdist_upload_key(self, uploader, s3_client, tmp_path):
        dist = tmp_path / "my_package-2.0.0.tar.gz"
        dist.write_bytes(b"fake sdist content")

        uploader.upload(str(dist))

        obj = s3_client.get_object(
            Bucket=BUCKET,
            Key="packages/my-package/my_package-2.0.0.tar.gz",
        )
        assert obj["Body"].read() == b"fake sdist content"

    def test_normalized_name_in_key(self, uploader, s3_client, tmp_path):
        """Package name with underscores is normalized to hyphens in the S3 key."""
        dist = tmp_path / "My_Cool_Package-0.1.0-py3-none-any.whl"
        dist.write_bytes(b"content")

        uploader.upload(str(dist))

        obj = s3_client.get_object(
            Bucket=BUCKET,
            Key="packages/my-cool-package/My_Cool_Package-0.1.0-py3-none-any.whl",
        )
        assert obj["Body"].read() == b"content"


class TestDetailPageRegeneration:
    """Test that detail page is regenerated after upload with correct file listing."""

    def test_detail_page_created(self, uploader, s3_client, tmp_path):
        dist = tmp_path / "my_package-1.0.0-py3-none-any.whl"
        dist.write_bytes(b"whl")

        uploader.upload(str(dist))

        obj = s3_client.get_object(
            Bucket=BUCKET, Key="simple/my-package/index.html"
        )
        html = obj["Body"].read().decode("utf-8")
        filenames = parse_detail_page(html)
        assert filenames == ["my_package-1.0.0-py3-none-any.whl"]

    def test_detail_page_lists_multiple_files(self, uploader, s3_client, tmp_path):
        whl = tmp_path / "my_package-1.0.0-py3-none-any.whl"
        whl.write_bytes(b"whl")
        sdist = tmp_path / "my_package-1.0.0.tar.gz"
        sdist.write_bytes(b"sdist")

        uploader.upload(str(whl))
        uploader.upload(str(sdist))

        obj = s3_client.get_object(
            Bucket=BUCKET, Key="simple/my-package/index.html"
        )
        html = obj["Body"].read().decode("utf-8")
        filenames = parse_detail_page(html)
        assert "my_package-1.0.0-py3-none-any.whl" in filenames
        assert "my_package-1.0.0.tar.gz" in filenames

    def test_detail_page_content_type(self, uploader, s3_client, tmp_path):
        dist = tmp_path / "pkg-1.0.0.tar.gz"
        dist.write_bytes(b"data")

        uploader.upload(str(dist))

        obj = s3_client.get_object(
            Bucket=BUCKET, Key="simple/pkg/index.html"
        )
        assert obj["ContentType"] == "text/html"


class TestRootIndexPageRegeneration:
    """Test that root index page is regenerated after upload with correct package listing."""

    def test_root_index_created(self, uploader, s3_client, tmp_path):
        dist = tmp_path / "my_package-1.0.0-py3-none-any.whl"
        dist.write_bytes(b"whl")

        uploader.upload(str(dist))

        obj = s3_client.get_object(
            Bucket=BUCKET, Key="simple/index.html"
        )
        html = obj["Body"].read().decode("utf-8")
        packages = parse_index_page(html)
        assert "my-package" in packages

    def test_root_index_lists_multiple_packages(self, uploader, s3_client, tmp_path):
        pkg_a = tmp_path / "alpha-1.0.0.tar.gz"
        pkg_a.write_bytes(b"a")
        pkg_b = tmp_path / "beta-2.0.0.tar.gz"
        pkg_b.write_bytes(b"b")

        uploader.upload(str(pkg_a))
        uploader.upload(str(pkg_b))

        obj = s3_client.get_object(
            Bucket=BUCKET, Key="simple/index.html"
        )
        html = obj["Body"].read().decode("utf-8")
        packages = parse_index_page(html)
        assert "alpha" in packages
        assert "beta" in packages

    def test_root_index_content_type(self, uploader, s3_client, tmp_path):
        dist = tmp_path / "pkg-1.0.0.tar.gz"
        dist.write_bytes(b"data")

        uploader.upload(str(dist))

        obj = s3_client.get_object(
            Bucket=BUCKET, Key="simple/index.html"
        )
        assert obj["ContentType"] == "text/html"


class TestFileNotFoundError:
    """Test FileNotFoundError raised for non-existent dist file."""

    def test_nonexistent_file(self, uploader):
        with pytest.raises(FileNotFoundError, match="Distribution file not found"):
            uploader.upload("/nonexistent/path/fake-1.0.0.tar.gz")

    def test_directory_instead_of_file(self, uploader, tmp_path):
        with pytest.raises(FileNotFoundError, match="Distribution file not found"):
            uploader.upload(str(tmp_path))


class TestS3ErrorPropagation:
    """Test S3 error propagation."""

    def test_upload_to_nonexistent_bucket(self, tmp_path):
        with mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            # Don't create the bucket — S3 operations should fail
            uploader = S3PyPIUploader(bucket="nonexistent-bucket", s3_client=client)

            dist = tmp_path / "pkg-1.0.0.tar.gz"
            dist.write_bytes(b"data")

            with pytest.raises(ClientError):
                uploader.upload(str(dist))
