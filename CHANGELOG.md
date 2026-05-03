# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-03

### Added

- `configure` subcommand to save default `--bucket` and `--cloudfront-distribution-id` to `~/.s3pypi/config.json`.
- Config fallback: `upload` reads bucket and distribution ID from config when CLI flags are omitted.
- `s3pypi/config.py` module for configuration file management.
- Optional `DomainName` and `AcmCertificateArn` CloudFormation parameters for custom domain support.
- Conditional CloudFront alias and ACM certificate configuration via `HasCustomDomain` condition.
- `PyPIEndpoint` output now returns the custom domain when provided.
- Project URLs (Homepage, Repository) in `pyproject.toml`.

### Changed

- `--bucket` is now optional on the `upload` subcommand (falls back to configured value).

## [0.1.1] - 2026-05-03

### Fixed

- Changed build backend from internal `setuptools.backends._legacy:_Backend` to `setuptools.build_meta`.
- Added `@pytest.mark.smoke` markers to pylint and bandit smoke tests so `pytest -m smoke` works.
- Registered `smoke` marker in `pyproject.toml` to suppress unknown marker warnings.

### Added

- `pytest-cov` added to test dependencies.
- `Name`, `Environment`, and `Project` tags on all taggable CloudFormation resources.

## [0.1.0] - 2026-05-03

### Added

- PEP 503 compliant package name normalization and distribution filename parsing.
- HTML index and detail page generation with round-trip parsing support.
- S3 uploader with automatic index page regeneration after each upload.
- CloudFront cache invalidation support for immediate index freshness.
- CLI entry point (`s3pypi upload`) with `--bucket` and `--cloudfront-distribution-id` flags.
- CloudFormation template for full AWS infrastructure: S3 bucket, API Gateway, CloudFront distribution.
- Deployment script (`deploy.sh`) wrapping `aws cloudformation deploy`.
- Property-based test suite using Hypothesis (5 properties).
- Unit test suite with 100% code coverage.
- Smoke tests for pylint and bandit validation.
- README with architecture overview, quickstart, CLI usage, and development setup.
- LICENSE (MIT).
- `docs/` folder with design documentation, user guide, and FAQ.
- `.gitignore` for Python projects.
- Git repository initialized.
