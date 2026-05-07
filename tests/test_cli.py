"""Unit tests for s3pypi.cli module.

Validates: Requirements 8.1
"""

import sys
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

        with patch("s3pypi.cli.load_config", return_value={}):
            with patch("s3pypi.cli.S3PyPIUploader", return_value=mock_uploader) as mock_cls:
                main(["upload", str(dist), "--bucket", "my-bucket"])

        mock_cls.assert_called_once_with(bucket="my-bucket")
        mock_uploader.upload.assert_called_once_with(str(dist))

    def test_valid_sdist_upload(self, tmp_path):
        dist = tmp_path / "pkg-2.0.0.tar.gz"
        dist.write_bytes(b"fake sdist")

        mock_uploader = MagicMock()

        with patch("s3pypi.cli.load_config", return_value={}):
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
            patch("s3pypi.cli.load_config", return_value={}),
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

    def test_configure_no_flags_enters_interactive_mode(self, capsys, monkeypatch):
        inputs = iter(["my-bucket", "E123", "my-table", "arn:secret"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        with patch("s3pypi.cli.load_config", return_value={}):
            with patch("s3pypi.cli.save_config", return_value={
                "bucket": "my-bucket",
                "cloudfront_distribution_id": "E123",
                "api_key_table_name": "my-table",
                "ldap_secret_arn": "arn:secret",
            }) as mock_save:
                main(["configure"])

        call_args = mock_save.call_args[0][0]
        assert call_args["bucket"] == "my-bucket"
        assert call_args["cloudfront_distribution_id"] == "E123"
        assert call_args["api_key_table_name"] == "my-table"
        assert call_args["ldap_secret_arn"] == "arn:secret"

    def test_configure_interactive_shows_current_values(self, capsys, monkeypatch):
        prompts_received = []

        def mock_input(prompt):
            prompts_received.append(prompt)
            return ""

        monkeypatch.setattr("builtins.input", mock_input)
        with patch("s3pypi.cli.load_config", return_value={"bucket": "old-bucket"}):
            with patch("s3pypi.cli.save_config", return_value={"bucket": "old-bucket"}):
                main(["configure"])

        # Should show current value in brackets
        assert any("[old-bucket]" in p for p in prompts_received)

    def test_configure_interactive_empty_input_preserves_values(self, capsys, monkeypatch):
        inputs = iter(["", "", "", ""])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        with patch("s3pypi.cli.load_config", return_value={"bucket": "existing"}):
            with patch("s3pypi.cli.save_config", return_value={"bucket": "existing"}) as mock_save:
                main(["configure"])

        call_args = mock_save.call_args[0][0]
        # All None means no changes
        assert call_args["bucket"] is None
        assert call_args["cloudfront_distribution_id"] is None

    def test_configure_interactive_new_input_overwrites(self, capsys, monkeypatch):
        inputs = iter(["new-bucket", "", "new-table", ""])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        with patch("s3pypi.cli.load_config", return_value={"bucket": "old"}):
            with patch("s3pypi.cli.save_config", return_value={
                "bucket": "new-bucket", "api_key_table_name": "new-table",
            }) as mock_save:
                main(["configure"])

        call_args = mock_save.call_args[0][0]
        assert call_args["bucket"] == "new-bucket"
        assert call_args["cloudfront_distribution_id"] is None
        assert call_args["api_key_table_name"] == "new-table"
        assert call_args["ldap_secret_arn"] is None

    def test_configure_prints_merged_config(self, capsys):
        merged = {"bucket": "new", "cloudfront_distribution_id": "old-id"}
        with patch("s3pypi.cli.save_config", return_value=merged):
            main(["configure", "--bucket", "new"])

        captured = capsys.readouterr()
        assert '"bucket": "new"' in captured.out
        assert '"cloudfront_distribution_id": "old-id"' in captured.out

    def test_configure_from_stack_imports_outputs(self, capsys):
        mock_client = MagicMock()
        mock_client.describe_stacks.return_value = {
            "Stacks": [{"Outputs": [
                {"OutputKey": "BucketName", "OutputValue": "stack-bucket"},
                {"OutputKey": "CloudFrontURL", "OutputValue": "https://d.cf.net/simple/"},
                {"OutputKey": "APIKeyTableName", "OutputValue": "stack-table"},
            ]}]
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("s3pypi.cli.boto3.Session", return_value=mock_session):
            with patch("s3pypi.cli.save_config", return_value={
                "bucket": "stack-bucket",
            }) as mock_save:
                main(["configure", "--from-stack", "my-stack"])

        call_args = mock_save.call_args[0][0]
        assert call_args["bucket"] == "stack-bucket"
        assert call_args["cloudfront_url"] == "https://d.cf.net/simple/"
        assert call_args["api_key_table_name"] == "stack-table"

    def test_configure_from_stack_with_profile_and_region(self, capsys):
        mock_client = MagicMock()
        mock_client.describe_stacks.return_value = {
            "Stacks": [{"Outputs": [
                {"OutputKey": "BucketName", "OutputValue": "b"},
            ]}]
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("s3pypi.cli.boto3.Session", return_value=mock_session) as mock_sess:
            with patch("s3pypi.cli.save_config", return_value={}):
                main(["configure", "--from-stack", "s", "--profile", "prod", "--region", "eu-west-1"])

        mock_sess.assert_called_once_with(region_name="eu-west-1", profile_name="prod")

    def test_configure_from_stack_not_found_exits_1(self, capsys):
        mock_client = MagicMock()
        mock_client.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
            "DescribeStacks",
        )
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("s3pypi.cli.boto3.Session", return_value=mock_session):
            with pytest.raises(SystemExit) as exc_info:
                main(["configure", "--from-stack", "nonexistent"])

        assert exc_info.value.code == 1


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


class TestApiKeySubcommand:
    """Tests for the apikey subcommand."""

    def test_apikey_create_prints_key(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.create_api_key", return_value="test-uuid-key"):
                main(["apikey", "--table-name", "my-table", "create"])

        captured = capsys.readouterr()
        assert "test-uuid-key" in captured.out

    def test_apikey_create_with_description(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.create_api_key", return_value="key-123") as mock_create:
                main(["apikey", "--table-name", "t", "create", "--description", "CI key"])

        mock_create.assert_called_once_with("t", description="CI key", access="read")

    def test_apikey_list_prints_keys(self, capsys):
        keys = [
            {"api_key": "key-1", "created_at": "2026-01-01T00:00:00", "description": "desc1", "access": "read"},
            {"api_key": "key-2", "created_at": "2026-01-02T00:00:00", "description": "", "access": "read/write"},
        ]
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.list_api_keys", return_value=keys):
                main(["apikey", "--table-name", "t", "list"])

        captured = capsys.readouterr()
        assert "key-1" in captured.out
        assert "key-2" in captured.out
        assert "desc1" in captured.out

    def test_apikey_get_prints_record(self, capsys):
        record = {"api_key": "key-1", "created_at": "2026-01-01", "description": "test"}
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.get_api_key", return_value=record):
                main(["apikey", "--table-name", "t", "get", "key-1"])

        captured = capsys.readouterr()
        assert "key-1" in captured.out

    def test_apikey_get_nonexistent_exits_1(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.get_api_key", side_effect=KeyError("API key not found: bad")):
                with pytest.raises(SystemExit) as exc_info:
                    main(["apikey", "--table-name", "t", "get", "bad"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "API key not found" in captured.err

    def test_apikey_delete_prints_confirmation(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.delete_api_key"):
                main(["apikey", "--table-name", "t", "delete", "key-1"])

        captured = capsys.readouterr()
        assert "Deleted API key: key-1" in captured.out

    def test_apikey_delete_nonexistent_exits_1(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.delete_api_key", side_effect=KeyError("API key not found: bad")):
                with pytest.raises(SystemExit) as exc_info:
                    main(["apikey", "--table-name", "t", "delete", "bad"])

        assert exc_info.value.code == 1

    def test_apikey_table_name_from_config(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "config-table"}):
            with patch("s3pypi.cli.create_api_key", return_value="k") as mock_create:
                main(["apikey", "create"])

        mock_create.assert_called_once_with("config-table", description=None, access="read")

    def test_apikey_flag_overrides_config(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "config-table"}):
            with patch("s3pypi.cli.create_api_key", return_value="k") as mock_create:
                main(["apikey", "--table-name", "flag-table", "create"])

        mock_create.assert_called_once_with("flag-table", description=None, access="read")

    def test_apikey_no_table_name_exits_1(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={}):
            with pytest.raises(SystemExit) as exc_info:
                main(["apikey", "create"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--table-name is required" in captured.err

    def test_apikey_no_action_exits_2(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["apikey", "--table-name", "t"])

        assert exc_info.value.code == 2

    def test_apikey_create_with_access_readwrite(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.create_api_key", return_value="k") as mock_create:
                main(["apikey", "--table-name", "t", "create", "--access", "read/write"])

        mock_create.assert_called_once_with("t", description=None, access="read/write")

    def test_apikey_update_success(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.update_api_key") as mock_update:
                main(["apikey", "--table-name", "t", "update", "key-1", "--access", "read/write"])

        mock_update.assert_called_once_with("t", "key-1", access="read/write")
        captured = capsys.readouterr()
        assert "Updated API key: key-1" in captured.out

    def test_apikey_update_nonexistent_exits_1(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.update_api_key", side_effect=KeyError("API key not found: bad")):
                with pytest.raises(SystemExit) as exc_info:
                    main(["apikey", "--table-name", "t", "update", "bad", "--access", "read"])

        assert exc_info.value.code == 1

    def test_apikey_list_shows_access_column(self, capsys):
        keys = [
            {"api_key": "k1", "created_at": "2026-01-01", "description": "d", "access": "read"},
            {"api_key": "k2", "created_at": "2026-01-02", "description": "", "access": "read/write"},
        ]
        with patch("s3pypi.cli.load_config", return_value={"api_key_table_name": "t"}):
            with patch("s3pypi.cli.list_api_keys", return_value=keys):
                main(["apikey", "--table-name", "t", "list"])

        captured = capsys.readouterr()
        assert "ACCESS" in captured.out
        assert "read/write" in captured.out


class TestConfigureLdapSubcommand:
    """Tests for the configure-ldap subcommand."""

    def test_configure_ldap_success(self, capsys):
        with patch("s3pypi.cli.update_ldap_secret") as mock_update:
            main([
                "configure-ldap",
                "--secret-arn", "arn:aws:secretsmanager:us-east-1:123:secret:test",
                "--host", "ldap.example.com",
                "--bind-user", "cn=admin,dc=example,dc=com",
                "--bind-password", "secret",
                "--entitlement-group", "cn=users,dc=example,dc=com",
            ])

        mock_update.assert_called_once_with(
            secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:test",
            host="ldap.example.com",
            bind_user="cn=admin,dc=example,dc=com",
            bind_password="secret",
            entitlement_group="cn=users,dc=example,dc=com",
            write_entitlement_group="",
        )
        captured = capsys.readouterr()
        assert "updated successfully" in captured.out

    def test_configure_ldap_missing_host_exits_2(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([
                "configure-ldap",
                "--secret-arn", "arn:test",
                "--bind-user", "user",
                "--bind-password", "pass",
                "--entitlement-group", "group",
            ])

        assert exc_info.value.code == 2

    def test_configure_ldap_missing_bind_user_exits_2(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([
                "configure-ldap",
                "--secret-arn", "arn:test",
                "--host", "ldap.example.com",
                "--bind-password", "pass",
                "--entitlement-group", "group",
            ])

        assert exc_info.value.code == 2

    def test_configure_ldap_secret_arn_from_config(self, capsys):
        config = {"ldap_secret_arn": "arn:from:config"}
        with patch("s3pypi.cli.load_config", return_value=config):
            with patch("s3pypi.cli.update_ldap_secret") as mock_update:
                main([
                    "configure-ldap",
                    "--host", "h",
                    "--bind-user", "u",
                    "--bind-password", "p",
                    "--entitlement-group", "g",
                ])

        assert mock_update.call_args[1]["secret_arn"] == "arn:from:config"

    def test_configure_ldap_with_write_group(self, capsys):
        with patch("s3pypi.cli.update_ldap_secret") as mock_update:
            main([
                "configure-ldap",
                "--secret-arn", "arn:test",
                "--host", "h",
                "--bind-user", "u",
                "--bind-password", "p",
                "--entitlement-group", "readers",
                "--write-entitlement-group", "writers",
            ])

        assert mock_update.call_args[1]["write_entitlement_group"] == "writers"

    def test_configure_ldap_without_write_group_defaults_empty(self, capsys):
        with patch("s3pypi.cli.update_ldap_secret") as mock_update:
            main([
                "configure-ldap",
                "--secret-arn", "arn:test",
                "--host", "h",
                "--bind-user", "u",
                "--bind-password", "p",
                "--entitlement-group", "g",
            ])

        assert mock_update.call_args[1]["write_entitlement_group"] == ""

    def test_configure_ldap_flag_overrides_config(self, capsys):
        config = {"ldap_secret_arn": "arn:from:config"}
        with patch("s3pypi.cli.load_config", return_value=config):
            with patch("s3pypi.cli.update_ldap_secret") as mock_update:
                main([
                    "configure-ldap",
                    "--secret-arn", "arn:from:flag",
                    "--host", "h",
                    "--bind-user", "u",
                    "--bind-password", "p",
                    "--entitlement-group", "g",
                ])

        assert mock_update.call_args[1]["secret_arn"] == "arn:from:flag"

    def test_configure_ldap_no_secret_arn_exits_1(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={}):
            with pytest.raises(SystemExit) as exc_info:
                main([
                    "configure-ldap",
                    "--host", "h",
                    "--bind-user", "u",
                    "--bind-password", "p",
                    "--entitlement-group", "g",
                ])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--secret-arn is required" in captured.err

    def test_configure_ldap_client_error_exits_1(self, capsys):
        error = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            operation_name="PutSecretValue",
        )
        with patch("s3pypi.cli.update_ldap_secret", side_effect=error):
            with pytest.raises(SystemExit) as exc_info:
                main([
                    "configure-ldap",
                    "--secret-arn", "arn:test",
                    "--host", "h",
                    "--bind-user", "u",
                    "--bind-password", "p",
                    "--entitlement-group", "g",
                ])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "ResourceNotFoundException" in captured.err


class TestDeploySubcommand:
    """Tests for the deploy subcommand."""

    def test_deploy_invokes_deploy_stack(self, capsys):
        outputs = {"bucket": "my-bucket", "cloudfront_distribution_id": "d.cf.net"}
        with patch("s3pypi.cli.deploy_stack", return_value=outputs) as mock_deploy:
            with patch("s3pypi.cli.save_config", return_value=outputs):
                main(["deploy", "--stack-name", "my-stack"])

        mock_deploy.assert_called_once_with(
            stack_name="my-stack",
            region="us-east-1",
            profile=None,
            parameters={},
        )
        captured = capsys.readouterr()
        assert "deployed successfully" in captured.out

    def test_deploy_passes_profile_and_region(self, capsys):
        with patch("s3pypi.cli.deploy_stack", return_value={}) as mock_deploy:
            with patch("s3pypi.cli.save_config", return_value={}):
                main(["deploy", "--stack-name", "s", "--profile", "prod", "--region", "eu-west-1"])

        mock_deploy.assert_called_once_with(
            stack_name="s",
            region="eu-west-1",
            profile="prod",
            parameters={},
        )

    def test_deploy_passes_template_parameters_from_flags(self, capsys):
        with patch("s3pypi.cli.deploy_stack", return_value={}) as mock_deploy:
            with patch("s3pypi.cli.save_config", return_value={}):
                main([
                    "deploy", "--stack-name", "s",
                    "--cache-ttl", "600",
                    "--enable-kms-encryption", "true",
                    "--vpc-id", "vpc-123",
                ])

        call_params = mock_deploy.call_args[1]["parameters"]
        assert call_params["CacheTTL"] == "600"
        assert call_params["EnableKMSEncryption"] == "true"
        assert call_params["VpcId"] == "vpc-123"

    def test_deploy_all_template_flags(self, capsys):
        with patch("s3pypi.cli.deploy_stack", return_value={}) as mock_deploy:
            with patch("s3pypi.cli.save_config", return_value={}):
                main([
                    "deploy", "--stack-name", "s",
                    "--stack-name-prefix", "team",
                    "--cache-ttl", "60",
                    "--domain-name", "pypi.example.com",
                    "--acm-certificate-arn", "arn:acm:cert",
                    "--enable-kms-encryption", "true",
                    "--enable-authorizer", "true",
                    "--subnet-ids", "subnet-1,subnet-2",
                    "--vpc-id", "vpc-abc",
                ])

        call_params = mock_deploy.call_args[1]["parameters"]
        assert call_params == {
            "StackNamePrefix": "team",
            "CacheTTL": "60",
            "DomainName": "pypi.example.com",
            "AcmCertificateArn": "arn:acm:cert",
            "EnableKMSEncryption": "true",
            "EnableAuthorizer": "true",
            "SubnetIds": "subnet-1,subnet-2",
            "VpcId": "vpc-abc",
        }

    def test_deploy_saves_outputs_to_config(self, capsys):
        outputs = {"bucket": "b", "api_key_table_name": "t"}
        with patch("s3pypi.cli.deploy_stack", return_value=outputs):
            with patch("s3pypi.cli.save_config", return_value=outputs) as mock_save:
                main(["deploy", "--stack-name", "s"])

        mock_save.assert_called_once_with(outputs)

    def test_deploy_failure_exits_1(self, capsys):
        from s3pypi.deploy import DeployError
        with patch("s3pypi.cli.deploy_stack", side_effect=DeployError("Stack failed")):
            with pytest.raises(SystemExit) as exc_info:
                main(["deploy", "--stack-name", "bad"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Stack failed" in captured.err

    def test_deploy_interactive_mode_when_no_stack_name(self, capsys, monkeypatch):
        inputs = iter([
            "my-stack",     # stack name
            "",             # region (keep default)
            "",             # profile (keep default)
            "",             # StackNamePrefix
            "",             # CacheTTL
            "",             # DomainName
            "",             # AcmCertificateArn
            "true",         # EnableKMSEncryption
            "",             # EnableAuthorizer
            "",             # SubnetIds
            "",             # VpcId
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        outputs = {"bucket": "b"}
        with patch("s3pypi.cli.deploy_stack", return_value=outputs) as mock_deploy:
            with patch("s3pypi.cli.save_config", return_value=outputs):
                main(["deploy"])

        call_kwargs = mock_deploy.call_args[1]
        assert call_kwargs["stack_name"] == "my-stack"
        assert call_kwargs["parameters"]["EnableKMSEncryption"] == "true"
        # Empty inputs should not be in parameters
        assert "CacheTTL" not in call_kwargs["parameters"]

    def test_deploy_interactive_empty_stack_name_exits_2(self, capsys, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        with pytest.raises(SystemExit) as exc_info:
            main(["deploy"])

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "stack name is required" in captured.err

    def test_deploy_update_fetches_current_params(self, capsys, monkeypatch):
        mock_cf_client = MagicMock()
        mock_cf_client.describe_stacks.return_value = {
            "Stacks": [{
                "Parameters": [
                    {"ParameterKey": "StackNamePrefix", "ParameterValue": "my-prefix"},
                    {"ParameterKey": "CacheTTL", "ParameterValue": "600"},
                    {"ParameterKey": "EnableAuthorizer", "ParameterValue": "true"},
                ],
                "Outputs": [],
            }]
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_cf_client

        # All empty inputs = keep current values
        inputs = iter(["", "", "", "", "", "", "", ""])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        outputs = {"bucket": "b"}
        with patch("s3pypi.cli.boto3.Session", return_value=mock_session):
            with patch("s3pypi.cli.deploy_stack", return_value=outputs) as mock_deploy:
                with patch("s3pypi.cli.save_config", return_value=outputs):
                    main(["deploy", "--update", "my-stack"])

        call_params = mock_deploy.call_args[1]["parameters"]
        assert call_params["StackNamePrefix"] == "my-prefix"
        assert call_params["CacheTTL"] == "600"
        assert call_params["EnableAuthorizer"] == "true"

    def test_deploy_update_allows_changing_params(self, capsys, monkeypatch):
        mock_cf_client = MagicMock()
        mock_cf_client.describe_stacks.return_value = {
            "Stacks": [{
                "Parameters": [
                    {"ParameterKey": "CacheTTL", "ParameterValue": "300"},
                    {"ParameterKey": "EnableKMSEncryption", "ParameterValue": "false"},
                ],
                "Outputs": [],
            }]
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_cf_client

        # Change CacheTTL, keep everything else
        inputs = iter(["", "900", "", "", "true", "", "", ""])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        with patch("s3pypi.cli.boto3.Session", return_value=mock_session):
            with patch("s3pypi.cli.deploy_stack", return_value={}) as mock_deploy:
                with patch("s3pypi.cli.save_config", return_value={}):
                    main(["deploy", "--update", "my-stack"])

        call_params = mock_deploy.call_args[1]["parameters"]
        assert call_params["CacheTTL"] == "900"
        assert call_params["EnableKMSEncryption"] == "true"

    def test_deploy_update_stack_not_found_exits_1(self, capsys):
        mock_cf_client = MagicMock()
        mock_cf_client.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
            "DescribeStacks",
        )
        mock_session = MagicMock()
        mock_session.client.return_value = mock_cf_client

        with patch("s3pypi.cli.boto3.Session", return_value=mock_session):
            with pytest.raises(SystemExit) as exc_info:
                main(["deploy", "--update", "nonexistent"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "failed to describe stack" in captured.err


class TestPipSubcommand:
    """Tests for the pip subcommand."""

    def test_pip_with_token_auth_keyring(self, capsys, monkeypatch):
        config = {"cloudfront_url": "https://d123.cloudfront.net/simple/"}
        inputs = iter(["1", "my-api-key-123"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        mock_keyring = MagicMock()
        with patch("s3pypi.cli.load_config", return_value=config):
            with patch.dict(sys.modules, {"keyring": mock_keyring}):
                main(["pip"])

        mock_keyring.set_password.assert_called_once_with(
            "https://d123.cloudfront.net", "__token__", "my-api-key-123"
        )
        captured = capsys.readouterr()
        assert "index-url = https://d123.cloudfront.net/simple/" in captured.out
        assert "extra-index-url = https://pypi.org/simple/" in captured.out

    def test_pip_with_ldap_auth_keyring(self, capsys, monkeypatch):
        config = {"cloudfront_url": "https://d123.cloudfront.net/simple/"}
        inputs = iter(["2", "myuser", "mypass"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        mock_keyring = MagicMock()
        with patch("s3pypi.cli.load_config", return_value=config):
            with patch.dict(sys.modules, {"keyring": mock_keyring}):
                main(["pip"])

        mock_keyring.set_password.assert_called_once_with(
            "https://d123.cloudfront.net", "myuser", "mypass"
        )
        captured = capsys.readouterr()
        assert "index-url = https://d123.cloudfront.net/simple/" in captured.out

    def test_pip_fallback_when_keyring_fails(self, capsys, monkeypatch):
        config = {"cloudfront_url": "https://d123.cloudfront.net/simple/"}
        inputs = iter(["1", "my-key"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        mock_keyring = MagicMock()
        mock_keyring.set_password.side_effect = RuntimeError("No backend")

        with patch("s3pypi.cli.load_config", return_value=config):
            with patch.dict(sys.modules, {"keyring": mock_keyring}):
                main(["pip"])

        captured = capsys.readouterr()
        assert "failed to store in keyring" in captured.err
        assert "index-url = https://__token__:my-key@d123.cloudfront.net/simple/" in captured.out

    def test_pip_no_cloudfront_url_exits_1(self, capsys, monkeypatch):
        with patch("s3pypi.cli.load_config", return_value={}):
            with pytest.raises(SystemExit) as exc_info:
                main(["pip"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "cloudfront_url not found" in captured.err

    def test_pip_invalid_choice_exits_2(self, capsys, monkeypatch):
        config = {"cloudfront_url": "https://d123.cloudfront.net/simple/"}
        inputs = iter(["3"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        with patch("s3pypi.cli.load_config", return_value=config):
            with pytest.raises(SystemExit) as exc_info:
                main(["pip"])

        assert exc_info.value.code == 2

    def test_pip_empty_token_exits_1(self, capsys, monkeypatch):
        config = {"cloudfront_url": "https://d123.cloudfront.net/simple/"}
        inputs = iter(["1", ""])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        with patch("s3pypi.cli.load_config", return_value=config):
            with pytest.raises(SystemExit) as exc_info:
                main(["pip"])

        assert exc_info.value.code == 1


class TestPipSaveOption:
    """Tests for the pip --save option."""

    def test_pip_save_writes_config_file(self, capsys, monkeypatch, tmp_path):
        config = {"cloudfront_url": "https://d123.cloudfront.net/simple/"}
        inputs = iter(["1", "my-key"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        pip_conf = tmp_path / "pip.conf"
        mock_keyring = MagicMock()

        with patch("s3pypi.cli.load_config", return_value=config):
            with patch("s3pypi.pip_config.get_pip_config_path", return_value=pip_conf):
                with patch.dict(sys.modules, {"keyring": mock_keyring}):
                    main(["pip", "--save"])

        assert pip_conf.exists()
        content = pip_conf.read_text()
        assert "[global]" in content
        assert "index-url = https://d123.cloudfront.net/simple/" in content
        assert "extra-index-url = https://pypi.org/simple/" in content
        captured = capsys.readouterr()
        assert "Saved to" in captured.out

    def test_pip_without_save_prints_config(self, capsys, monkeypatch):
        config = {"cloudfront_url": "https://d123.cloudfront.net/simple/"}
        inputs = iter(["1", "my-key"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        mock_keyring = MagicMock()

        with patch("s3pypi.cli.load_config", return_value=config):
            with patch.dict(sys.modules, {"keyring": mock_keyring}):
                main(["pip"])

        captured = capsys.readouterr()
        assert "[global]" in captured.out
        assert "Saved to" not in captured.out


class TestTwineSubcommand:
    """Tests for the twine subcommand."""

    def test_twine_with_token_auth_keyring(self, capsys, monkeypatch):
        config = {
            "cloudfront_url": "https://d123.cloudfront.net/simple/",
            "api_gateway_url": "https://abc.execute-api.us-east-1.amazonaws.com/prod/simple/",
        }
        inputs = iter(["1", "my-rw-key"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        mock_keyring = MagicMock()

        with patch("s3pypi.cli.load_config", return_value=config):
            with patch.dict(sys.modules, {"keyring": mock_keyring}):
                main(["twine"])

        mock_keyring.set_password.assert_called_once_with(
            "https://abc.execute-api.us-east-1.amazonaws.com", "__token__", "my-rw-key"
        )
        captured = capsys.readouterr()
        assert "[private]" in captured.out
        assert "repository = https://abc.execute-api.us-east-1.amazonaws.com/prod/simple/" in captured.out
        assert "username = __token__" in captured.out

    def test_twine_with_ldap_auth(self, capsys, monkeypatch):
        config = {
            "api_gateway_url": "https://abc.execute-api.us-east-1.amazonaws.com/prod/simple/",
        }
        inputs = iter(["2", "myuser", "mypass"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        mock_keyring = MagicMock()

        with patch("s3pypi.cli.load_config", return_value=config):
            with patch.dict(sys.modules, {"keyring": mock_keyring}):
                main(["twine"])

        captured = capsys.readouterr()
        assert "username = myuser" in captured.out

    def test_twine_save_writes_pypirc(self, capsys, monkeypatch, tmp_path):
        config = {
            "api_gateway_url": "https://abc.execute-api.us-east-1.amazonaws.com/prod/simple/",
        }
        inputs = iter(["1", "my-key"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        mock_keyring = MagicMock()

        with patch("s3pypi.cli.load_config", return_value=config):
            with patch("s3pypi.cli.Path.home", return_value=tmp_path):
                with patch.dict(sys.modules, {"keyring": mock_keyring}):
                    main(["twine", "--save"])

        pypirc = tmp_path / ".pypirc"
        assert pypirc.exists()
        content = pypirc.read_text()
        assert "[private]" in content
        assert "username = __token__" in content
        captured = capsys.readouterr()
        assert "Saved to" in captured.out

    def test_twine_no_url_exits_1(self, capsys):
        with patch("s3pypi.cli.load_config", return_value={}):
            with pytest.raises(SystemExit) as exc_info:
                main(["twine"])

        assert exc_info.value.code == 1

    def test_twine_invalid_choice_exits_2(self, capsys, monkeypatch):
        config = {"cloudfront_url": "https://d123.cloudfront.net/simple/"}
        inputs = iter(["9"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        with patch("s3pypi.cli.load_config", return_value=config):
            with pytest.raises(SystemExit) as exc_info:
                main(["twine"])

        assert exc_info.value.code == 2

    def test_twine_shows_upload_command(self, capsys, monkeypatch):
        config = {"cloudfront_url": "https://d123.cloudfront.net/simple/"}
        inputs = iter(["1", "key"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        mock_keyring = MagicMock()

        with patch("s3pypi.cli.load_config", return_value=config):
            with patch.dict(sys.modules, {"keyring": mock_keyring}):
                main(["twine"])

        captured = capsys.readouterr()
        assert "twine upload --repository private" in captured.out
