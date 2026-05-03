# Implementation Plan: S3 PyPI Server

## Overview

This plan implements a private PyPI server on AWS using S3 for storage, API Gateway as the HTTP front-end, and CloudFront as a caching layer. The implementation proceeds bottom-up: project scaffolding and build config first, then pure-logic modules (packaging, index generation), then AWS-interacting modules (uploader, invalidation), then the CLI entry point, then the CloudFormation template and deploy script, and finally documentation. Each coding step builds on the previous ones so there is no orphaned code.

## Tasks

- [x] 1. Set up project structure and build configuration
  - [x] 1.1 Create `pyproject.toml` with build configuration
    - Define `[build-system]` using setuptools
    - Set project name to `s3-pypi-server`, version `0.1.0`, MIT license
    - List author as `Topaz Bott <topaz@topazhome.net>`
    - Declare runtime dependencies: `boto3`
    - Declare optional test dependencies: `pytest`, `hypothesis`, `moto`, `pylint`, `bandit`
    - Define console script entry point: `s3pypi = s3pypi.cli:main`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 1.2 Create package directory structure and `__init__.py` files
    - Create `s3pypi/` package directory with `__init__.py`
    - Create empty module files: `cli.py`, `uploader.py`, `index.py`, `packaging.py`, `invalidation.py`
    - Create `tests/` directory with `__init__.py`
    - _Requirements: 7.1_

- [x] 2. Implement packaging module (name normalization and filename parsing)
  - [x] 2.1 Implement `s3pypi/packaging.py`
    - Implement `normalize_name(name: str) -> str` per PEP 503: lowercase, replace runs of `[-_.]` with single hyphen
    - Implement `parse_distribution_filename(filename: str) -> tuple[str, str, str]` supporting `.whl` and `.tar.gz` formats
    - Raise `ValueError` for unrecognized filename formats
    - _Requirements: 6.3, 5.9_

  - [x] 2.2 Write property test: Name normalization is idempotent and well-formed
    - **Property 1: Name normalization is idempotent and well-formed**
    - Use Hypothesis to generate arbitrary string inputs
    - Assert `normalize_name(normalize_name(x)) == normalize_name(x)`
    - Assert output is lowercase with no consecutive separator runs
    - **Validates: Requirements 6.3**

  - [x] 2.3 Write property test: Distribution filename parsing extracts correct package name
    - **Property 2: Distribution filename parsing extracts the correct package name**
    - Use Hypothesis composite strategies to generate valid wheel and sdist filenames
    - Assert parsed name, when normalized, equals the normalized name component from the filename
    - **Validates: Requirements 5.9**

  - [x] 2.4 Write unit tests for packaging module
    - Test `normalize_name` with specific examples: `My_Package` → `my-package`, `some.lib` → `some-lib`, `UPPER__CASE` → `upper-case`
    - Test `parse_distribution_filename` with known wheel and sdist filenames
    - Test `parse_distribution_filename` raises `ValueError` for invalid formats (e.g., `.zip`, `.exe`, no version)
    - _Requirements: 8.5, 8.6_

- [x] 3. Implement index page generation module
  - [x] 3.1 Implement `s3pypi/index.py`
    - Implement `generate_index_page(package_names: list[str]) -> str` producing PEP 503 root index HTML
    - Implement `generate_detail_page(package_name: str, filenames: list[str]) -> str` producing PEP 503 detail HTML
    - Implement `parse_index_page(html: str) -> list[str]` extracting package names from anchor hrefs
    - Implement `parse_detail_page(html: str) -> list[str]` extracting filenames from anchor hrefs
    - Include `<!DOCTYPE html>`, `<meta name="pypi:repository-version" content="1.0">`, and proper `<a>` elements
    - _Requirements: 6.1, 6.2, 5.5, 5.4, 5.6_

  - [x] 3.2 Write property test: Index page generation round-trip
    - **Property 3: Index page generation round-trip**
    - Use Hypothesis to generate lists of valid package names
    - Assert `parse_index_page(generate_index_page(names))` equals the list of normalized names
    - **Validates: Requirements 10.1, 5.5, 6.1**

  - [x] 3.3 Write property test: Detail page generation round-trip
    - **Property 4: Detail page generation round-trip**
    - Use Hypothesis to generate lists of valid distribution filenames
    - Assert `parse_detail_page(generate_detail_page(name, filenames))` equals the original filenames
    - **Validates: Requirements 10.2, 5.4, 6.2**

  - [x] 3.4 Write property test: Generated HTML conforms to PEP 503 structure
    - **Property 5: Generated HTML conforms to PEP 503 structure**
    - Use Hypothesis to generate valid inputs for both index and detail pages
    - Assert output contains `<!DOCTYPE html>`, `<meta name="pypi:repository-version" content="1.0">`, and one `<a>` per input item
    - **Validates: Requirements 5.6**

  - [x] 3.5 Write unit tests for index module
    - Test `generate_index_page` with known package lists and verify HTML structure
    - Test `generate_detail_page` with known filenames and verify anchor hrefs point to `../../packages/{name}/{file}`
    - Test `parse_index_page` and `parse_detail_page` with sample HTML
    - Test empty input lists produce valid HTML with no anchors
    - _Requirements: 8.4_

- [x] 4. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement S3 uploader module
  - [x] 5.1 Implement `s3pypi/uploader.py`
    - Implement `S3PyPIUploader.__init__(self, bucket: str, s3_client=None)` accepting optional S3 client for testing
    - Implement `upload(self, dist_path: str) -> None` that validates file existence, parses filename, uploads to `packages/{normalized_name}/{filename}`, and regenerates index pages
    - Implement `_upload_file(self, local_path: str, s3_key: str) -> None` for S3 PutObject
    - Implement `_regenerate_detail_page(self, package_name: str) -> None` listing files under `packages/{normalized_name}/` and writing detail HTML to `simple/{normalized_name}/index.html`
    - Implement `_regenerate_index_page(self) -> None` listing all package prefixes and writing root HTML to `simple/index.html`
    - Raise `FileNotFoundError` if dist file does not exist; propagate boto3 `ClientError` for S3 failures
    - _Requirements: 5.1, 5.3, 5.4, 5.5, 5.7, 5.8_

  - [x] 5.2 Write unit tests for uploader module
    - Use `moto` to mock S3 and test full upload workflow
    - Test that upload places file at correct S3 key `packages/{normalized_name}/{filename}`
    - Test that detail page is regenerated after upload with correct file listing
    - Test that root index page is regenerated after upload with correct package listing
    - Test `FileNotFoundError` raised for non-existent dist file
    - Test S3 error propagation
    - _Requirements: 8.1_

- [x] 6. Implement CloudFront invalidation module
  - [x] 6.1 Implement `s3pypi/invalidation.py`
    - Implement `create_invalidation(distribution_id: str, paths: list[str]) -> str` using boto3 CloudFront client
    - Return the invalidation ID on success
    - Propagate boto3 `ClientError` on failure
    - _Requirements: 3.4, 5.10_

  - [x] 6.2 Write unit tests for invalidation module
    - Use `moto` or mock boto3 CloudFront client
    - Test that invalidation is created with correct paths
    - Test error propagation for CloudFront failures
    - _Requirements: 8.1_

- [x] 7. Implement CLI entry point
  - [x] 7.1 Implement `s3pypi/cli.py`
    - Implement `main()` function as the console script entry point
    - Use `argparse` to define `upload` subcommand with positional `dist_file` argument
    - Add required `--bucket` flag and optional `--cloudfront-distribution-id` flag
    - Wire argument parsing to `S3PyPIUploader.upload()` and optionally `create_invalidation()`
    - Handle errors: print to stderr, exit with code 1 for runtime errors, code 2 for argument errors (argparse default)
    - _Requirements: 5.1, 5.2, 5.7, 5.8, 5.9, 5.10_

  - [x] 7.2 Write unit tests for CLI module
    - Test argument parsing: valid upload command, missing `--bucket`, missing dist file
    - Test error handling: non-existent file prints to stderr and exits with code 1
    - Test that `--cloudfront-distribution-id` triggers invalidation
    - Test that no subcommand prints usage and exits with code 2
    - _Requirements: 8.1_

- [x] 8. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement smoke tests for pylint and bandit
  - [x] 9.1 Create `tests/test_smoke_pylint.py`
    - Discover all `.py` files under `s3pypi/`
    - Run pylint programmatically or via subprocess and assert zero errors
    - _Requirements: 8.2_

  - [x] 9.2 Create `tests/test_smoke_bandit.py`
    - Discover all `.py` files under `s3pypi/`
    - Run bandit programmatically or via subprocess and assert zero issues
    - _Requirements: 8.3_

- [x] 10. Create CloudFormation template and deploy script
  - [x] 10.1 Create `template.yaml` CloudFormation template
    - Define parameters: `StackNamePrefix` (String, default `s3-pypi`), `CacheTTL` (Number, default `300`)
    - Define `PyPIBucket` S3 resource with AES-256 encryption, versioning, public access blocked, name derived from stack prefix
    - Define `ApiGatewayRole` IAM role granting `s3:GetObject` on the bucket
    - Define `PyPIApi` REST API with resource tree: `/simple/`, `/simple/{package}/`, `/simple/{package}/{file}`
    - Configure AWS service integration methods mapping URL paths to S3 object keys
    - Configure integration responses including 404 handling for missing S3 objects
    - Set `Content-Type: text/html` for index and detail page responses, binary passthrough for distribution files
    - Define `PyPIApiDeployment` and `PyPIApiStage` (stage name `prod`)
    - Define `CloudFrontDistribution` with API Gateway origin, HTTPS only, TLS 1.2 minimum, default TTL from parameter, Host header forwarding
    - Define outputs: `PyPIEndpoint` (CloudFront domain), `BucketName` (S3 bucket name)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.5, 3.6, 4.1, 4.2, 4.3, 4.7_

  - [x] 10.2 Create `deploy.sh` deployment script
    - Accept stack name as first positional argument
    - Run `aws cloudformation deploy` with `--template-file template.yaml`, `--capabilities CAPABILITY_IAM`, and `--parameter-overrides`
    - On failure, query `describe-stack-events` for `CREATE_FAILED` or `UPDATE_FAILED` events and print failure reasons
    - Make script executable with `set -euo pipefail`
    - _Requirements: 4.4, 4.5, 4.6_

- [x] 11. Create documentation
  - [x] 11.1 Create `README.md`
    - Include project overview, architecture summary with component diagram reference
    - Include quickstart guide: deploy stack, upload a package, install with pip
    - Include sections on configuration, CLI usage, and development setup
    - _Requirements: 9.1, 9.3, 9.4, 9.6_

  - [x] 11.2 Create `CHANGELOG.md`
    - Follow Keep a Changelog 1.1.0 format
    - Add initial `[0.1.0]` entry with Added section listing all features
    - _Requirements: 9.5_

- [x] 12. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Implement CLI configuration module
  - [x] 13.1 Implement `s3pypi/config.py`
    - Implement `load_config() -> dict[str, str]` that reads `~/.s3pypi/config.json` and returns its contents as a dict; returns empty dict if file does not exist
    - Implement `save_config(config: dict[str, str]) -> None` that creates `~/.s3pypi/` if needed, merges new values with existing config, and writes to `config.json`
    - Use JSON format with keys `bucket` and `cloudfront_distribution_id`
    - _Requirements: 11.3, 11.4, 11.5, 11.6_

  - [x] 13.2 Write unit tests for config module
    - Test `load_config` returns empty dict when file does not exist
    - Test `load_config` returns saved values when file exists
    - Test `save_config` creates directory and file when they do not exist
    - Test `save_config` merges new values with existing config (preserves keys not overridden)
    - Test `save_config` overwrites existing keys with new values
    - Use `tmp_path` fixture to avoid touching the real home directory
    - _Requirements: 8.1_

- [x] 14. Add `configure` subcommand and config fallback to CLI
  - [x] 14.1 Add `configure` subcommand to `s3pypi/cli.py`
    - Add `configure` subparser with optional `--bucket` and `--cloudfront-distribution-id` flags
    - When invoked, call `save_config` with the provided values
    - Print the saved configuration to stdout after writing
    - Exit with code 2 if no flags are provided
    - _Requirements: 11.1, 11.2, 11.9_

  - [x] 14.2 Update `upload` subcommand to fall back to config
    - Change `--bucket` from required to optional on the `upload` subparser
    - When `--bucket` is not provided, read from config via `load_config()`
    - When `--cloudfront-distribution-id` is not provided, read from config via `load_config()`
    - If bucket is still not resolved (neither flag nor config), print error to stderr and exit with code 1
    - _Requirements: 11.7, 11.8, 5.11_

  - [x] 14.3 Write unit tests for configure subcommand and config fallback
    - Test `configure` saves bucket and distribution ID to config file
    - Test `configure` with only `--bucket` preserves existing distribution ID
    - Test `configure` with no flags exits with code 2
    - Test `upload` without `--bucket` falls back to configured value
    - Test `upload` without `--bucket` and no config exits with code 1
    - Test `upload` without `--cloudfront-distribution-id` falls back to configured value
    - Test CLI flag overrides config value when both are present
    - _Requirements: 8.1_

- [x] 15. Add custom domain and ACM certificate support to CloudFormation template
  - [x] 15.1 Update `template.yaml` with new parameters and conditions
    - Add `DomainName` parameter (String, default `""`, description: optional custom domain for CloudFront)
    - Add `AcmCertificateArn` parameter (String, default `""`, description: optional ACM certificate ARN)
    - Add `HasCustomDomain` condition: true when both `DomainName` and `AcmCertificateArn` are non-empty
    - _Requirements: 12.1, 12.2, 12.5_

  - [x] 15.2 Update CloudFront distribution for conditional custom domain
    - When `HasCustomDomain` is true, set `Aliases` to `[!Ref DomainName]` and `ViewerCertificate` to use the ACM certificate with SNI
    - When `HasCustomDomain` is false, keep existing behavior (default CloudFront certificate)
    - Use `Fn::If` to conditionally apply `Aliases` and `ViewerCertificate`
    - _Requirements: 12.3, 12.4_

  - [x] 15.3 Update `PyPIEndpoint` output to reflect custom domain
    - Use `Fn::If` to output `DomainName` when `HasCustomDomain` is true, otherwise output the CloudFront distribution domain name
    - _Requirements: 12.6_

  - [x] 15.4 Validate template with `cfn-lint`
    - Run `cfn-lint template.yaml` and fix any issues
    - _Requirements: (CloudFormation standards)_

- [x] 16. Update documentation
  - [x] 16.1 Update `README.md`
    - Add `configure` subcommand to CLI usage section
    - Add custom domain deployment example to quickstart
    - Update configuration table with new CloudFormation parameters
    - _Requirements: 9.1, 9.6_

  - [x] 16.2 Update `docs/` documentation
    - Update `docs/user-guide.md` with configure workflow and custom domain setup
    - Update `docs/design.md` if any architectural details changed
    - Update `docs/faq.md` with custom domain questions
    - _Requirements: 9.3, 9.4_

  - [x] 16.3 Update `CHANGELOG.md`
    - Add entries under `[Unreleased]` for configure subcommand, config fallback, and custom domain support
    - _Requirements: 9.5_

- [x] 17. Final checkpoint
  - Run full test suite, pylint, bandit, cfn-lint
  - Verify `pytest -m smoke` selects all smoke tests
  - Verify coverage remains at or above 80%

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Smoke tests for pylint and bandit are NOT optional (per project rules requiring all code validate with both tools)
- All Python code targets the virtual environment at `/Users/topazb/python/py314/`
- The `moto` library is used for realistic AWS service mocking in tests
