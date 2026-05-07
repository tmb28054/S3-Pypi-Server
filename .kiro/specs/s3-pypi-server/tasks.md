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

- [x] 18. Add optional KMS encryption support to CloudFormation template
  - [x] 18.1 Add `EnableKMSEncryption` parameter and condition to `template.yaml`
    - Add `EnableKMSEncryption` parameter (String, AllowedValues `true`/`false`, default `false`)
    - Add `KMSEnabled` condition: true when `EnableKMSEncryption` equals `true`
    - _Requirements: 13.1, 13.7_

  - [x] 18.2 Create KMS Key resource in `template.yaml`
    - Define `PyPIKMSKey` (AWS::KMS::Key) with condition `KMSEnabled`
    - Set key policy granting account root (`arn:aws:iam::${AWS::AccountId}:root`) full access
    - Define `PyPIKMSKeyAlias` (AWS::KMS::Alias) with condition `KMSEnabled`, alias name derived from stack prefix
    - _Requirements: 13.2_

  - [x] 18.3 Update S3 bucket encryption to conditionally use KMS
    - Use `Fn::If` on the S3 bucket `BucketEncryption` property
    - When `KMSEnabled` is true: use `aws:kms` with the KMS key ARN
    - When `KMSEnabled` is false: use `AES256` (existing behavior)
    - _Requirements: 13.3, 13.6_

  - [x] 18.4 Validate template with `cfn-lint`
    - Run `cfn-lint template.yaml` and fix any issues
    - _Requirements: (CloudFormation standards)_

- [x] 19. Add optional API Gateway authorizer support
  - [x] 19.1 Add `EnableAuthorizer` parameter and condition to `template.yaml`
    - Add `EnableAuthorizer` parameter (String, AllowedValues `true`/`false`, default `false`)
    - Add `AuthorizerEnabled` condition: true when `EnableAuthorizer` equals `true`
    - _Requirements: 14.1, 14.5_

  - [x] 19.2 Create Authorizer Lambda function and execution role
    - Define `AuthorizerLambdaRole` (AWS::IAM::Role) with condition `AuthorizerEnabled`
    - Grant permissions: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
    - Grant permissions: `secretsmanager:GetSecretValue` on the LDAP secret
    - Grant permissions: `dynamodb:GetItem` on the API key table
    - Define `AuthorizerLambda` (AWS::Lambda::Function) with condition `AuthorizerEnabled`
    - Runtime: `python3.12`, handler: `index.handler`
    - Inline code implementing dual auth (Bearer token → DynamoDB lookup, Basic auth → LDAP bind)
    - Environment variables: `LDAP_SECRET_ARN`, `API_KEY_TABLE_NAME`
    - _Requirements: 14.2, 14.6, 15.2, 15.3, 15.4, 15.5, 16.2, 16.3, 16.4, 16.5_

  - [x] 19.3 Create API Gateway Authorizer resource
    - Define `PyPIAuthorizer` (AWS::ApiGateway::Authorizer) with condition `AuthorizerEnabled`
    - Type: `REQUEST`, authorizer URI pointing to `AuthorizerLambda`
    - Identity source: `method.request.header.Authorization`
    - _Requirements: 14.3_

  - [x] 19.4 Update API Gateway methods to conditionally use authorizer
    - Use `Fn::If` on each method's `AuthorizationType` property
    - When `AuthorizerEnabled` is true: set `AuthorizationType: CUSTOM` and `AuthorizerId` to the authorizer
    - When `AuthorizerEnabled` is false: set `AuthorizationType: NONE` (existing behavior)
    - _Requirements: 14.3, 14.4_

  - [x] 19.5 Create LDAP Secret in Secrets Manager
    - Define `LDAPSecret` (AWS::SecretsManager::Secret) with condition `AuthorizerEnabled`
    - Initial secret value: JSON with keys `host`, `bind_user`, `bind_password`, `entitlement_group` (empty strings)
    - When `KMSEnabled` is true, encrypt with the KMS key
    - _Requirements: 15.1_

  - [x] 19.6 Create DynamoDB API Key Table
    - Define `APIKeyTable` (AWS::DynamoDB::Table) with condition `AuthorizerEnabled`
    - Partition key: `api_key` (String)
    - BillingMode: PAY_PER_REQUEST
    - When `KMSEnabled` is true, configure SSESpecification with the KMS key
    - _Requirements: 16.1, 13.4_

  - [x] 19.7 Validate template with `cfn-lint`
    - Run `cfn-lint template.yaml` and fix any issues
    - _Requirements: (CloudFormation standards)_

- [x] 20. Add optional VPC support for Lambda functions
  - [x] 20.1 Add VPC parameters and condition to `template.yaml`
    - Add `SubnetIds` parameter (CommaDelimitedList, default `""`)
    - Add `VpcId` parameter (String, default `""`)
    - Add `VPCEnabled` condition: true when both `SubnetIds` and `VpcId` are non-empty
    - _Requirements: 19.1, 19.5_

  - [x] 20.2 Create Security Group resource
    - Define `LambdaSecurityGroup` (AWS::EC2::SecurityGroup) with condition `VPCEnabled`
    - Allow all outbound traffic (egress only)
    - VpcId: `!Ref VpcId`
    - _Requirements: 19.2_

  - [x] 20.3 Update Lambda functions with conditional VPC configuration
    - Use `Fn::If` on each Lambda function's `VpcConfig` property
    - When `VPCEnabled` is true: set `SubnetIds` and `SecurityGroupIds` (using the created Security Group)
    - When `VPCEnabled` is false: omit VpcConfig (existing behavior)
    - _Requirements: 19.3, 19.4_

  - [x] 20.4 Update Lambda execution role with VPC permissions
    - When `VPCEnabled` is true, add `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface` permissions
    - Use a conditional policy statement or separate policy with condition
    - _Requirements: 19.6_

  - [x] 20.5 Validate template with `cfn-lint`
    - Run `cfn-lint template.yaml` and fix any issues
    - _Requirements: (CloudFormation standards)_

- [x] 21. Add Lambda LogGroups and API Gateway access logging
  - [x] 21.1 Create Lambda LogGroups in `template.yaml`
    - Define a `AWS::Logs::LogGroup` for each Lambda function in the stack
    - Name pattern: `/aws/lambda/{function-name}` using `!Sub`
    - Retention: 30 days
    - When `KMSEnabled` is true, set `KmsKeyId` to the KMS key ARN
    - _Requirements: 20.1, 20.2, 20.3, 20.4_

  - [x] 21.2 Create API Gateway access log group and configure stage logging
    - Define `ApiGatewayLogGroup` (AWS::Logs::LogGroup) with 30-day retention
    - When `KMSEnabled` is true, set `KmsKeyId` to the KMS key ARN
    - Update `PyPIApiStage` to include `AccessLogSetting` with the log group ARN
    - Configure access log format: `requestId`, `ip`, `requestTime`, `httpMethod`, `resourcePath`, `status`, `responseLength`
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_

  - [x] 21.3 Add CloudFormation outputs for new resources
    - Output `KMSKeyArn` (conditional on `KMSEnabled`)
    - Output `LDAPSecretArn` (conditional on `AuthorizerEnabled`)
    - Output `APIKeyTableName` (conditional on `AuthorizerEnabled`)
    - _Requirements: (operational visibility)_

  - [x] 21.4 Validate template with `cfn-lint`
    - Run `cfn-lint template.yaml` and fix any issues
    - _Requirements: (CloudFormation standards)_

- [x] 22. Implement CLI API Key management subcommand
  - [x] 22.1 Implement `s3pypi/apikey.py` module
    - Implement `create_api_key(table_name: str, description: str = None, dynamodb_client=None) -> str` that generates a UUID API key, stores it in DynamoDB with optional description and created_at timestamp, returns the key
    - Implement `list_api_keys(table_name: str, dynamodb_client=None) -> list[dict]` that scans the table and returns all records
    - Implement `get_api_key(table_name: str, api_key: str, dynamodb_client=None) -> dict` that retrieves a single record, raises `KeyError` if not found
    - Implement `delete_api_key(table_name: str, api_key: str, dynamodb_client=None) -> None` that deletes the record, raises `KeyError` if not found
    - _Requirements: 17.2, 17.3, 17.4, 17.5, 17.6, 17.7_

  - [x] 22.2 Add `apikey` subcommand to `s3pypi/cli.py`
    - Add `apikey` subparser with actions: `create`, `list`, `get`, `delete`
    - Add `--table-name` flag, falling back to config file value
    - `create`: optional `--description` flag, prints generated key to stdout
    - `list`: prints all keys with descriptions in tabular format
    - `get`: requires key value as positional argument, prints record
    - `delete`: requires key value as positional argument, prints confirmation
    - Handle `KeyError` from module: print error to stderr, exit code 1
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8_

  - [x] 22.3 Update `s3pypi/config.py` to support new config keys
    - Add `api_key_table_name` and `ldap_secret_arn` as recognized config keys
    - Update `save_config` and `load_config` to handle the new keys
    - _Requirements: 17.8, 18.3_

  - [x] 22.4 Write unit tests for apikey module
    - Use `moto` to mock DynamoDB
    - Test `create_api_key` generates a valid UUID key and stores it
    - Test `create_api_key` with description stores description alongside key
    - Test `list_api_keys` returns all stored keys
    - Test `get_api_key` returns the correct record
    - Test `get_api_key` raises `KeyError` for non-existent key
    - Test `delete_api_key` removes the key
    - Test `delete_api_key` raises `KeyError` for non-existent key
    - _Requirements: 8.1_

  - [x] 22.5 Write unit tests for apikey CLI subcommand
    - Test `apikey create` prints a key to stdout
    - Test `apikey create --description "CI key"` stores description
    - Test `apikey list` prints all keys
    - Test `apikey get <key>` prints the record
    - Test `apikey get <nonexistent>` exits with code 1
    - Test `apikey delete <key>` prints confirmation
    - Test `apikey delete <nonexistent>` exits with code 1
    - Test `--table-name` flag overrides config value
    - Test fallback to config when `--table-name` not provided
    - _Requirements: 8.1_

- [x] 23. Implement CLI Secrets Manager configuration subcommand
  - [x] 23.1 Implement `s3pypi/secrets.py` module
    - Implement `update_ldap_secret(secret_arn: str, host: str, bind_user: str, bind_password: str, entitlement_group: str, sm_client=None) -> None` that updates the secret value as JSON
    - Propagate boto3 `ClientError` on failure
    - _Requirements: 18.4, 18.6_

  - [x] 23.2 Add `configure-ldap` subcommand to `s3pypi/cli.py`
    - Add `configure-ldap` subparser with required flags: `--host`, `--bind-user`, `--bind-password`, `--entitlement-group`
    - Add `--secret-arn` flag, falling back to config file value
    - On success, print confirmation message to stdout
    - On failure, print error to stderr and exit with code 1
    - If required flags are missing, argparse exits with code 2
    - _Requirements: 18.1, 18.2, 18.3, 18.5, 18.6, 18.7_

  - [x] 23.3 Write unit tests for secrets module
    - Use `moto` to mock Secrets Manager
    - Test `update_ldap_secret` writes correct JSON structure
    - Test `update_ldap_secret` propagates errors
    - _Requirements: 8.1_

  - [x] 23.4 Write unit tests for configure-ldap CLI subcommand
    - Test with all required flags succeeds and prints confirmation
    - Test missing `--host` exits with code 2
    - Test missing `--bind-user` exits with code 2
    - Test `--secret-arn` flag overrides config value
    - Test fallback to config when `--secret-arn` not provided
    - Test Secrets Manager error prints to stderr and exits with code 1
    - _Requirements: 8.1_

- [x] 24. Checkpoint
  - Run full test suite including new apikey and secrets tests
  - Run pylint and bandit on new modules
  - Validate template with cfn-lint
  - Ensure all tests pass

- [x] 25. Update documentation for new features
  - [x] 25.1 Update `README.md`
    - Add KMS encryption section to deployment options
    - Add authorizer section explaining LDAP and API key auth methods
    - Add `apikey` and `configure-ldap` subcommands to CLI usage
    - Add VPC deployment example
    - Update CloudFormation parameters table with new parameters
    - _Requirements: 9.1, 9.6_

  - [x] 25.2 Update `docs/design.md`
    - Add architecture diagram showing Lambda authorizer, DynamoDB, Secrets Manager
    - Document KMS encryption flow
    - Document VPC placement design decision
    - Document authorizer authentication flow (Bearer → DynamoDB, Basic → LDAP)
    - _Requirements: 9.2_

  - [x] 25.3 Update `docs/user-guide.md`
    - Add section on enabling KMS encryption
    - Add section on enabling and configuring the authorizer
    - Add section on managing API keys via CLI
    - Add section on configuring LDAP via CLI
    - Add section on VPC deployment
    - Add pip configuration examples for authenticated access (Basic auth and Bearer token)
    - _Requirements: 9.3, 9.4_

  - [x] 25.4 Update `docs/faq.md`
    - Add FAQ entries for KMS encryption, authorizer, API keys, LDAP, and VPC
    - _Requirements: 9.3_

  - [x] 25.5 Update `CHANGELOG.md`
    - Add entries under `[Unreleased]` for all new features:
      - Optional KMS encryption support
      - Optional API Gateway authorizer with LDAP/AD and API key methods
      - `apikey` CLI subcommand for CRUD operations on DynamoDB API keys
      - `configure-ldap` CLI subcommand for Secrets Manager configuration
      - Optional VPC support for Lambda functions
      - Lambda LogGroups with 30-day retention
      - API Gateway access logging with 30-day retention
    - _Requirements: 9.5_

- [x] 26. Final checkpoint
  - Run full test suite, pylint, bandit, cfn-lint
  - Verify `pytest -m smoke` selects all smoke tests
  - Verify coverage remains at or above 80%
  - Verify all new CloudFormation parameters have defaults that maintain backward compatibility

- [x] 27. Update authorizer for `__token__` convention and access levels
  - [x] 27.1 Update Authorizer Lambda inline code in `template.yaml`
    - Change authentication flow: check Basic Auth header for `__token__` username → DynamoDB API key lookup using the password
    - For non-`__token__` Basic Auth usernames → LDAP/AD authentication
    - Remove Bearer token support (replaced by `__token__` Basic Auth convention)
    - When API key found in DynamoDB, read the `access` attribute (`read` or `read/write`)
    - Return Allow policy scoped to GET methods for `read` access
    - Return Allow policy scoped to GET and POST methods for `read/write` access
    - For LDAP auth: check membership in `entitlement_group` for read access
    - For LDAP auth: check membership in `write_entitlement_group` for write access (GET + POST)
    - _Requirements: 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 15.3, 15.4_

  - [x] 27.2 Update LDAP Secret initial value in `template.yaml`
    - Add `write_entitlement_group` key to the initial empty JSON structure
    - _Requirements: 15.1_

  - [x] 27.3 Validate template with `cfn-lint`
    - Run `cfn-lint template.yaml` and fix any issues

- [x] 28. Add API key access level support to CLI and DynamoDB module
  - [x] 28.1 Update `s3pypi/apikey.py` module
    - Add `access` parameter to `create_api_key()` with default value `read`, allowed values `read` or `read/write`
    - Store `access` attribute in DynamoDB item
    - Include `access` in records returned by `list_api_keys()` and `get_api_key()`
    - Implement `update_api_key(table_name: str, api_key: str, access: str, dynamodb_client=None) -> None` that updates the access level, raises `KeyError` if not found
    - _Requirements: 17.2, 17.4, 17.5, 17.6, 17.8_

  - [x] 28.2 Update `apikey` CLI subcommand in `s3pypi/cli.py`
    - Add `--access` flag to `apikey create` (choices: `read`, `read/write`, default: `read`)
    - Add `update` action to `apikey` subparser requiring key positional argument and `--access` flag
    - Update `list` output format to include the access level column
    - _Requirements: 17.1, 17.4, 17.8, 17.9_

  - [x] 28.3 Write unit tests for updated apikey module
    - Test `create_api_key` with default access stores `read`
    - Test `create_api_key` with `--access read/write` stores `read/write`
    - Test `list_api_keys` includes access level in output
    - Test `get_api_key` includes access level in output
    - Test `update_api_key` changes the access level
    - Test `update_api_key` raises `KeyError` for non-existent key
    - _Requirements: 8.1_

  - [x] 28.4 Write unit tests for updated apikey CLI subcommand
    - Test `apikey create --access read/write` stores correct access level
    - Test `apikey update <key> --access read/write` updates access level
    - Test `apikey update <nonexistent>` exits with code 1
    - Test `apikey list` output includes ACCESS column
    - _Requirements: 8.1_

- [x] 29. Update `configure-ldap` CLI for write entitlement group
  - [x] 29.1 Update `s3pypi/secrets.py` module
    - Add `write_entitlement_group` parameter to `update_ldap_secret()` (optional, default `""`)
    - Include `write_entitlement_group` in the JSON written to Secrets Manager
    - _Requirements: 18.3, 18.5_

  - [x] 29.2 Update `configure-ldap` CLI subcommand in `s3pypi/cli.py`
    - Add optional `--write-entitlement-group` flag
    - Pass the value to `update_ldap_secret()`
    - _Requirements: 18.1, 18.2, 18.3_

  - [x] 29.3 Write unit tests for updated secrets module and CLI
    - Test `update_ldap_secret` includes `write_entitlement_group` in JSON
    - Test `configure-ldap --write-entitlement-group` passes value correctly
    - Test `configure-ldap` without `--write-entitlement-group` stores empty string
    - _Requirements: 8.1_

- [x] 30. Add Upload Lambda for twine-compatible package publishing
  - [x] 30.1 Create Upload Lambda resource in `template.yaml`
    - Define `UploadLambdaRole` (AWS::IAM::Role) with condition `AuthorizerEnabled`
    - Grant permissions: `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on the PyPI bucket
    - Grant permissions: `cloudfront:CreateInvalidation` (if CloudFront distribution exists)
    - Grant permissions: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
    - Define `UploadLambda` (AWS::Lambda::Function) with condition `AuthorizerEnabled`
    - Runtime: `python3.12`, handler: `index.handler`, timeout: 60s, memory: 512MB
    - Inline code that parses multipart/form-data, extracts the distribution file, uploads to S3, and regenerates index pages
    - Environment variables: `BUCKET_NAME`, `CLOUDFRONT_DISTRIBUTION_ID` (if available)
    - Apply VPC config conditionally (same as authorizer)
    - _Requirements: 22.1, 22.3, 22.4, 22.8_

  - [x] 30.2 Add POST method to API Gateway `/simple/` resource
    - Define POST method on `SimpleResource` integrated with `UploadLambda` via `AWS_PROXY`
    - Apply authorizer conditionally (same as GET methods)
    - The authorizer must verify write access before allowing the POST
    - _Requirements: 22.2, 22.5_

  - [x] 30.3 Create Upload Lambda LogGroup
    - Define `UploadLambdaLogGroup` (AWS::Logs::LogGroup) with condition `AuthorizerEnabled`
    - Retention: 30 days
    - When `KMSEnabled` is true, set `KmsKeyId` to the KMS key ARN
    - _Requirements: 22.9, 22.10_

  - [x] 30.4 Add Lambda Permission for API Gateway to invoke Upload Lambda
    - Define `UploadLambdaPermission` (AWS::Lambda::Permission) with condition `AuthorizerEnabled`
    - Allow `apigateway.amazonaws.com` to invoke the function
    - _Requirements: 22.2_

  - [x] 30.5 Update `PyPIApiDeployment` DependsOn
    - Add the new POST method to the DependsOn list
    - _Requirements: (CloudFormation correctness)_

  - [x] 30.6 Validate template with `cfn-lint`
    - Run `cfn-lint template.yaml` and fix any issues

- [x] 31. Checkpoint
  - Run full test suite including updated apikey and secrets tests
  - Run pylint and bandit on modified modules
  - Validate template with cfn-lint
  - Ensure all tests pass

- [x] 32. Update documentation for new features
  - [x] 32.1 Update `README.md`
    - Document `__token__` username convention for API key auth
    - Document `--access` flag on `apikey create`
    - Document `apikey update` action
    - Document `--write-entitlement-group` on `configure-ldap`
    - Add twine upload section with `~/.pypirc` configuration example
    - _Requirements: 9.1, 9.6, 23.1, 23.2, 23.3_

  - [x] 32.2 Update `docs/design.md`
    - Update authorizer authentication flow diagram for `__token__` convention
    - Document read vs write access control model
    - Document Upload Lambda architecture
    - _Requirements: 9.2_

  - [x] 32.3 Update `docs/user-guide.md`
    - Add section on configuring twine for uploads
    - Add `~/.pypirc` example with `__token__` username
    - Add section on access levels (read vs read/write)
    - Update LDAP configuration section with `--write-entitlement-group`
    - Update API key section with `--access` flag
    - _Requirements: 9.3, 23.1, 23.2, 23.3, 23.4_

  - [x] 32.4 Update `docs/faq.md`
    - Add FAQ entries for twine upload, `__token__` convention, access levels
    - _Requirements: 9.3_

  - [x] 32.5 Update `CHANGELOG.md`
    - Add entries under `[Unreleased]` for:
      - `__token__` username convention for API key authentication
      - Read/write access levels on API keys
      - `apikey update` action for changing access levels
      - `--write-entitlement-group` on `configure-ldap`
      - Twine-compatible package upload via POST to API Gateway
      - Upload Lambda for server-side package processing
    - _Requirements: 9.5_

- [x] 33. Final checkpoint
  - Run full test suite, pylint, bandit, cfn-lint
  - Verify `pytest -m smoke` selects all smoke tests
  - Verify coverage remains at or above 80%
  - Verify all new CloudFormation parameters have defaults that maintain backward compatibility

- [x] 34. Add interactive prompts to `configure` subcommand
  - [x] 34.1 Update `_handle_configure` in `s3pypi/cli.py`
    - When no flags are provided, enter interactive mode instead of exiting with error
    - Prompt for each config key: bucket, cloudfront_distribution_id, api_key_table_name, ldap_secret_arn
    - Display current value (from existing config) in brackets as default
    - Accept empty input to keep existing value unchanged
    - Save all collected values via `save_config`
    - Print the saved configuration to stdout
    - _Requirements: 11.10_

  - [x] 34.2 Write unit tests for interactive configure
    - Test interactive mode is triggered when no flags are provided
    - Test prompts display current values from existing config
    - Test empty input preserves existing values
    - Test new input overwrites existing values
    - Test mixed input (some empty, some new) works correctly
    - _Requirements: 8.1_

  - [x] 34.3 Update documentation
    - Update README configure section to mention interactive mode
    - Update docs/user-guide.md with interactive configure example
    - _Requirements: 9.1, 9.6_

- [x] 35. Change BucketName and APIKeyTableName to CloudFormation auto-naming
  - [x] 35.1 Remove explicit `BucketName` from S3 bucket in `template.yaml`
    - Remove the `BucketName` property so CloudFormation generates a unique name
    - The `BucketName` stack output still references `!Ref PyPIBucket` (returns the generated name)
    - _Requirements: 1.1_

  - [x] 35.2 Remove explicit `TableName` from DynamoDB table in `template.yaml`
    - Remove the `TableName` property so CloudFormation generates a unique name
    - The `APIKeyTableName` stack output still references `!Ref APIKeyTable` (returns the generated name)
    - _Requirements: 16.1_

  - [x] 35.3 Update all documentation
    - Update README to note names are randomly generated and retrieved from stack outputs
    - Update docs/design.md with auto-naming details
    - Update docs/user-guide.md with stack output retrieval instructions
    - Update docs/faq.md with FAQ about finding names
    - Update CHANGELOG with the change
    - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [x] 36. Bundle CloudFormation template in Python package and add `deploy` subcommand
  - [x] 36.1 Move `template.yaml` into the `s3pypi` package directory
    - Move `template.yaml` to `s3pypi/template.yaml`
    - Update `pyproject.toml` to include `template.yaml` as package data
    - Remove `deploy.sh` from the project root
    - _Requirements: 4.1, 4.11_

  - [x] 36.2 Implement `s3pypi/deploy.py` module
    - Implement `deploy_stack(stack_name: str, region: str, profile: str | None, parameters: dict[str, str]) -> dict[str, str]`
    - Use boto3 CloudFormation client to create/update the stack (create_change_set + execute or deploy equivalent)
    - Load the template from the package data path (`importlib.resources` or `__file__` relative)
    - Wait for stack completion using CloudFormation waiters
    - On success, retrieve stack outputs and return them as a dict
    - On failure, query stack events for failure reasons and raise an exception with details
    - _Requirements: 4.4, 4.5, 4.6, 4.9, 4.10_

  - [x] 36.3 Add `deploy` subcommand to `s3pypi/cli.py`
    - Add `deploy` subparser with required `--stack-name` argument
    - Add optional `--profile` argument (boto3 named profile)
    - Add optional `--region` argument (default: `us-east-1`)
    - Accept positional arguments as `Key=Value` CloudFormation parameter overrides
    - On success, call `save_config` with the stack outputs (bucket, cloudfront_distribution_id, api_key_table_name, ldap_secret_arn)
    - Print the saved configuration and stack outputs to stdout
    - On failure, print error to stderr and exit with code 1
    - _Requirements: 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10_

  - [x] 36.4 Write unit tests for deploy module
    - Test that template is loadable from package data
    - Test parameter override parsing (`Key=Value` format)
    - Test that stack outputs are correctly mapped to config keys
    - Test error handling for failed deployments
    - Use moto or mock boto3 CloudFormation client
    - _Requirements: 8.1_

  - [x] 36.5 Write unit tests for deploy CLI subcommand
    - Test `deploy --stack-name my-stack` invokes deploy_stack correctly
    - Test `--profile` and `--region` are passed through
    - Test parameter overrides are parsed and passed
    - Test successful deploy saves outputs to config
    - Test failed deploy exits with code 1 and prints error
    - _Requirements: 8.1_

  - [x] 36.6 Update all documentation
    - Update README: replace `deploy.sh` references with `s3pypi deploy` command
    - Update README: add `deploy` to CLI usage section
    - Update docs/user-guide.md: replace deploy.sh with `s3pypi deploy`
    - Update docs/design.md: note template is bundled in package
    - Update docs/faq.md: update deployment FAQ entries
    - Update CHANGELOG: add deploy subcommand, remove deploy.sh
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 36.7 Validate and run full test suite
    - Run pylint and bandit on new/modified modules
    - Run full test suite with coverage >= 80%
    - Verify `pytest -m smoke` still works

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Smoke tests for pylint and bandit are NOT optional (per project rules requiring all code validate with both tools)
- All Python code targets the virtual environment at `/Users/topazb/python/py314/`
- The `moto` library is used for realistic AWS service mocking in tests
