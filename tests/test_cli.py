"""Unit tests for s3pypi.cli module.

Validates: Requirements 8.1
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from s3pypi.cli import main


class TestValidUploadCommand:
    """Test argument parsing for a valid upload command."""

    def test_valid_upload_invokes_uploader(self, tmp_path):
        dist = tmp_path / "my_package-1.0.0-py3-none-any.whl"
        dist.write_bytes(b"fake wheel")

        mock_uploader = MagicMock()

        with patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader) as mock_cls:
            main(["upload", str(dist), "--bucket", "my-bucket"])

        mock_cls.assert_called_once_with(bucket="my-bucket")
        mock_uploader.upload.assert_called_once_with(str(dist))

    def test_valid_sdist_upload(self, tmp_path):
        dist = tmp_path / "pkg-2.0.0.tar.gz"
        dist.write_bytes(b"fake sdist")

        mock_uploader = MagicMock()

        with patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader):
            main(["upload", str(dist), "--bucket", "test-bucket"])

        mock_uploader.upload.assert_called_once_with(str(dist))


class TestMissingBucket:
    """Test that missing --bucket without config causes exit code 1."""

    def test_missing_bucket_no_config_exits_1(self, tmp_path, capsys):
        dist = tmp_path / "pkg-1.0.0.tar.gz"
        dist.write_bytes(b"data")

        with patch("s3pypi.cli.load_config", return_value={}):
            with pytest.raises(SystemExit) as exc_info:
                main(["upload", str(dist)])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--bucket is required" in captured.err


class TestMissingDistFile:
    """Test that missing dist_file argument causes exit code 2."""

    def test_missing_dist_file_exits_2(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["upload", "--bucket", "my-bucket"])

        assert exc_info.value.code == 2


class TestNonExistentFileError:
    """Test error handling: non-existent file prints to stderr and exits with code 1."""

    def test_nonexistent_file_exits_1(self, capsys):
        mock_uploader = MagicMock()
        mock_uploader.upload.side_effect = FileNotFoundError(
            "Distribution file not found: /no/such/file.whl"
        )

        with patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader):
            with pytest.raises(SystemExit) as exc_info:
                main(["upload", "/no/such/file.whl", "--bucket", "b"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Distribution file not found" in captured.err

    def test_value_error_exits_1(self, capsys):
        """Unrecognized filename format also exits with code 1."""
        mock_uploader = MagicMock()
        mock_uploader.upload.side_effect = ValueError(
            "Unrecognized distribution filename format: bad.zip"
        )

        with patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader):
            with pytest.raises(SystemExit) as exc_info:
                main(["upload", "bad.zip", "--bucket", "b"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Unrecognized distribution filename format" in captured.err

    def test_client_error_exits_1(self, capsys):
        """S3 ClientError also exits with code 1."""
        mock_uploader = MagicMock()
        mock_uploader.upload.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            operation_name="PutObject",
        )

        with patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader):
            with pytest.raises(SystemExit) as exc_info:
                main(["upload", "pkg-1.0.0.tar.gz", "--bucket", "b"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "AccessDenied" in captured.err


class TestCloudfrontInvalidation:
    """Test that --cloudfront-distribution-id triggers invalidation."""

    def test_invalidation_called_when_flag_provided(self, tmp_path):
        dist = tmp_path / "my_package-1.0.0-py3-none-any.whl"
        dist.write_bytes(b"wheel data")

        mock_uploader = MagicMock()

        with (
            patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader),
            patch("s3pypi.cli.create_invalidation") as mock_invalidate,
        ):
            main([
                "upload", str(dist),
                "--bucket", "my-bucket",
                "--cloudfront-distribution-id", "E1234567890ABC",
            ])

        mock_invalidate.assert_called_once_with(
            "E1234567890ABC",
            ["/simple/", "/simple/my-package/"],
        )

    def test_no_invalidation_without_flag(self, tmp_path):
        dist = tmp_path / "my_package-1.0.0-py3-none-any.whl"
        dist.write_bytes(b"wheel data")

        mock_uploader = MagicMock()

        with (
            patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader),
            patch("s3pypi.cli.create_invalidation") as mock_invalidate,
        ):
            main(["upload", str(dist), "--bucket", "my-bucket"])

        mock_invalidate.assert_not_called()

    def test_invalidation_uses_normalized_name(self, tmp_path):
        """Package name from filename is normalized for invalidation paths."""
        dist = tmp_path / "My_Cool_Package-0.1.0-py3-none-any.whl"
        dist.write_bytes(b"data")

        mock_uploader = MagicMock()

        with (
            patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader),
            patch("s3pypi.cli.create_invalidation") as mock_invalidate,
        ):
            main([
                "upload", str(dist),
                "--bucket", "b",
                "--cloudfront-distribution-id", "EDIST",
            ])

        mock_invalidate.assert_called_once_with(
            "EDIST",
            ["/simple/", "/simple/my-cool-package/"],
        )


class TestNoSubcommand:
    """Test that no subcommand prints usage and exits with code 2."""

    def test_no_subcommand_exits_2(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([])

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "usage:" in captured.err.lower()

    def test_no_args_exits_2(self, capsys):
        """Calling main with no arguments at all exits with code 2."""
        with pytest.raises(SystemExit) as exc_info:
            main([])

        assert exc_info.value.code == 2


class TestConfigureSubcommand:
    """Tests for the configure subcommand."""

    def test_configure_saves_bucket(self, capsys):
        with patch("s3pypi.cli.save_config", return_value={"bucket": "my-bucket"}) as mock_save:
            main(["configure", "--bucket", "my-bucket"])

        mock_save.assert_called_once()
        call_args = mock_save.call_args[0][0]
        assert call_args["bucket"] == "my-bucket"
        captured = capsys.readouterr()
        assert "my-bucket" in captured.out

    def test_configure_saves_distribution_id(self, capsys):
        with patch("s3pypi.cli.save_config", return_value={"cloudfront_distribution_id": "E123"}) as mock_save:
            main(["configure", "--cloudfront-distribution-id", "E123"])

        call_args = mock_save.call_args[0][0]
        assert call_args["cloudfront_distribution_id"] == "E123"

    def test_configure_saves_both(self, capsys):
        expected = {"bucket": "b", "cloudfront_distribution_id": "E1"}
        with patch("s3pypi.cli.save_config", return_value=expected):
            main(["configure", "--bucket", "b", "--cloudfront-distribution-id", "E1"])

        captured = capsys.readouterr()
        assert "b" in captured.out
        assert "E1" in captured.out

    def test_configure_no_flags_exits_2(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["configure"])

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "at least one of" in captured.err

    def test_configure_prints_merged_config(self, capsys):
        merged = {"bucket": "new", "cloudfront_distribution_id": "old-id"}
        with patch("s3pypi.cli.save_config", return_value=merged):
            main(["configure", "--bucket", "new"])

        captured = capsys.readouterr()
        assert '"bucket": "new"' in captured.out
        assert '"cloudfront_distribution_id": "old-id"' in captured.out


class TestConfigFallback:
    """Tests for upload falling back to configured values."""

    def test_upload_falls_back_to_config_bucket(self, tmp_path):
        dist = tmp_path / "pkg-1.0.0-py3-none-any.whl"
        dist.write_bytes(b"data")

        mock_uploader = MagicMock()
        config = {"bucket": "config-bucket"}

        with (
            patch("s3pypi.cli.load_config", return_value=config),
            patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader) as mock_cls,
        ):
            main(["upload", str(dist)])

        mock_cls.assert_called_once_with(bucket="config-bucket")

    def test_upload_falls_back_to_config_distribution_id(self, tmp_path):
        dist = tmp_path / "pkg-1.0.0-py3-none-any.whl"
        dist.write_bytes(b"data")

        mock_uploader = MagicMock()
        config = {"bucket": "b", "cloudfront_distribution_id": "E999"}

        with (
            patch("s3pypi.cli.load_config", return_value=config),
            patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader),
            patch("s3pypi.cli.create_invalidation") as mock_inv,
        ):
            main(["upload", str(dist)])

        mock_inv.assert_called_once()
        assert mock_inv.call_args[0][0] == "E999"

    def test_cli_flag_overrides_config(self, tmp_path):
        dist = tmp_path / "pkg-1.0.0-py3-none-any.whl"
        dist.write_bytes(b"data")

        mock_uploader = MagicMock()
        config = {"bucket": "config-bucket"}

        with (
            patch("s3pypi.cli.load_config", return_value=config),
            patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader) as mock_cls,
        ):
            main(["upload", str(dist), "--bucket", "flag-bucket"])

        mock_cls.assert_called_once_with(bucket="flag-bucket")

    def test_upload_no_bucket_anywhere_exits_1(self, tmp_path, capsys):
        dist = tmp_path / "pkg-1.0.0.tar.gz"
        dist.write_bytes(b"data")

        with patch("s3pypi.cli.load_config", return_value={}):
            with pytest.raises(SystemExit) as exc_info:
                main(["upload", str(dist)])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--bucket is required" in captured.err

    def test_corrupt_config_exits_1(self, tmp_path, capsys):
        dist = tmp_path / "pkg-1.0.0.tar.gz"
        dist.write_bytes(b"data")

        with patch("s3pypi.cli.load_config", side_effect=ValueError("Invalid config")):
            with pytest.raises(SystemExit) as exc_info:
                main(["upload", str(dist)])

        assert exc_info.value.code == 1
