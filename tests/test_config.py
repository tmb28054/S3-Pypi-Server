"""Unit tests for s3pypi.config module.

Validates: Requirements 8.1, 11.3, 11.4, 11.5, 11.6
"""

from __future__ import annotations

import json

import pytest

from s3pypi.config import load_config, save_config


class TestLoadConfig:
    """Tests for load_config."""

    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        config_file = tmp_path / ".s3pypi" / "config.json"
        result = load_config(config_file)
        assert result == {}

    def test_returns_saved_values(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"bucket": "my-bucket", "cloudfront_distribution_id": "E123"}),
            encoding="utf-8",
        )
        result = load_config(config_file)
        assert result == {"bucket": "my-bucket", "cloudfront_distribution_id": "E123"}

    def test_raises_on_invalid_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid config file"):
            load_config(config_file)

    def test_raises_on_non_object_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="expected a JSON object"):
            load_config(config_file)


class TestSaveConfig:
    """Tests for save_config."""

    def test_creates_directory_and_file(self, tmp_path):
        config_file = tmp_path / ".s3pypi" / "config.json"
        result = save_config({"bucket": "new-bucket"}, config_file)
        assert config_file.is_file()
        assert result == {"bucket": "new-bucket"}
        stored = json.loads(config_file.read_text(encoding="utf-8"))
        assert stored == {"bucket": "new-bucket"}

    def test_merges_with_existing_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"bucket": "old-bucket", "cloudfront_distribution_id": "E111"}),
            encoding="utf-8",
        )
        result = save_config({"bucket": "new-bucket"}, config_file)
        assert result == {"bucket": "new-bucket", "cloudfront_distribution_id": "E111"}

    def test_overwrites_existing_key(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"bucket": "old-bucket"}),
            encoding="utf-8",
        )
        result = save_config({"bucket": "replaced"}, config_file)
        assert result["bucket"] == "replaced"

    def test_skips_none_values(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"bucket": "keep-me"}),
            encoding="utf-8",
        )
        result = save_config({"bucket": None, "cloudfront_distribution_id": "E999"}, config_file)
        assert result == {"bucket": "keep-me", "cloudfront_distribution_id": "E999"}

    def test_returns_full_merged_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        save_config({"bucket": "b1"}, config_file)
        result = save_config({"cloudfront_distribution_id": "E1"}, config_file)
        assert result == {"bucket": "b1", "cloudfront_distribution_id": "E1"}
