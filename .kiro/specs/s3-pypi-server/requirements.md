# Requirements Document

## Introduction

This document defines the requirements for a private PyPI server infrastructure deployed on AWS. The system uses an S3 bucket as the package repository backend, API Gateway as the HTTP front-end implementing the PyPI Simple Repository API, and CloudFront as a CDN cache layer. The entire infrastructure is defined as CloudFormation and deployed via the AWS CLI. A Python CLI tool is provided for uploading Python packages to the S3 bucket. The project follows the MIT license, validates with pylint and bandit, and includes comprehensive documentation and unit tests.

## Glossary

- **S3_Bucket**: An Amazon S3 bucket that stores Python package distribution files and the PyPI Simple Repository API index pages.
- **API_Gateway**: An Amazon API Gateway (REST API) that serves HTTP requests for the PyPI Simple Repository API by proxying to the S3_Bucket.
- **CloudFront_Distribution**: An Amazon CloudFront distribution that caches responses from the API_Gateway to reduce latency and load.
- **CloudFormation_Stack**: An AWS CloudFormation stack defined in a YAML template that provisions all AWS resources (S3_Bucket, API_Gateway, CloudFront_Distribution, IAM roles, and related resources).
- **Upload_CLI**: A Python command-line tool that uploads Python package distribution files (.tar.gz, .whl) to the S3_Bucket and regenerates the Simple Repository API index pages.
- **Simple_Repository_API**: The PyPI Simple Repository API (PEP 503) that provides a standardized interface for pip to discover and download packages.
- **Package_Index_Page**: An HTML page listing all available packages, served at the repository root path.
- **Package_Detail_Page**: An HTML page listing all distribution files for a specific package, served at the package name path.
- **Distribution_File**: A Python package archive file in .tar.gz (sdist) or .whl (bdist_wheel) format.
- **Stack_Deployer**: The CloudFormation deployment process that uses the AWS CLI to create or update the CloudFormation_Stack.
- **Configuration_File**: A JSON file at `~/.s3pypi/config.json` that stores default CLI settings (bucket name, CloudFront distribution ID).
- **ACM_Certificate**: An AWS Certificate Manager certificate used to enable HTTPS with a custom domain on the CloudFront_Distribution.

## Requirements

### Requirement 1: S3 Bucket Package Storage

**User Story:** As a DevOps engineer, I want Python packages stored in an S3 bucket, so that I have durable, scalable storage for my private package repository.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL provision an S3_Bucket with a unique bucket name derived from the stack name.
2. THE CloudFormation_Stack SHALL configure the S3_Bucket with server-side encryption enabled using AES-256.
3. THE CloudFormation_Stack SHALL configure the S3_Bucket to block all public access.
4. THE CloudFormation_Stack SHALL configure the S3_Bucket with versioning enabled.

### Requirement 2: API Gateway PyPI Interface

**User Story:** As a developer, I want an API Gateway that implements the PyPI Simple Repository API, so that pip can discover and install packages from my private repository.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL provision an API_Gateway REST API that proxies GET requests to the S3_Bucket.
2. WHEN a GET request is received at the root path, THE API_Gateway SHALL return the Package_Index_Page from the S3_Bucket.
3. WHEN a GET request is received at a package name path, THE API_Gateway SHALL return the Package_Detail_Page for that package from the S3_Bucket.
4. WHEN a GET request is received for a Distribution_File path, THE API_Gateway SHALL return the binary Distribution_File from the S3_Bucket with the correct content type.
5. IF a requested resource does not exist in the S3_Bucket, THEN THE API_Gateway SHALL return an HTTP 404 response.
6. THE CloudFormation_Stack SHALL provision an IAM role that grants the API_Gateway read-only access to the S3_Bucket.
7. THE API_Gateway SHALL set the Content-Type response header to "text/html" for Package_Index_Page and Package_Detail_Page responses.

### Requirement 3: CloudFront Caching Layer

**User Story:** As a DevOps engineer, I want CloudFront to cache responses from the API Gateway, so that package downloads are fast and API Gateway load is reduced.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL provision a CloudFront_Distribution with the API_Gateway as its origin.
2. THE CloudFront_Distribution SHALL cache responses from the API_Gateway with a default TTL of 300 seconds.
3. THE CloudFront_Distribution SHALL forward the Host header to the API_Gateway origin.
4. WHEN a cached resource is updated in the S3_Bucket, THE Upload_CLI SHALL create a CloudFront invalidation for the affected Package_Index_Page and Package_Detail_Page paths.
5. THE CloudFront_Distribution SHALL use the default CloudFront domain name (no custom domain required).
6. THE CloudFormation_Stack SHALL configure the CloudFront_Distribution to use TLS 1.2 as the minimum protocol version.

### Requirement 12: Custom Domain and ACM Certificate

**User Story:** As a DevOps engineer, I want to optionally use a custom domain name (e.g., `pypi.example.org`) with an ACM certificate for my private PyPI server, so that my team can access it via a memorable, branded URL.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL accept an optional `DomainName` parameter for a custom CloudFront CNAME (e.g., `pypi.example.org`).
2. THE CloudFormation_Stack SHALL accept an optional `AcmCertificateArn` parameter for an AWS Certificate Manager certificate ARN.
3. WHEN both `DomainName` and `AcmCertificateArn` are provided, THE CloudFront_Distribution SHALL be configured with the domain as an alias and the ACM certificate for TLS.
4. WHEN `DomainName` or `AcmCertificateArn` are not provided, THE CloudFront_Distribution SHALL use the default CloudFront domain name and default certificate (existing behavior).
5. THE CloudFormation_Stack SHALL use CloudFormation conditions to conditionally apply the custom domain and certificate configuration.
6. THE CloudFormation_Stack SHALL output the effective endpoint domain — the custom `DomainName` if provided, otherwise the default CloudFront domain.

### Requirement 4: CloudFormation Deployment

**User Story:** As a DevOps engineer, I want the entire infrastructure defined as CloudFormation and deployed via the AWS CLI, so that I can reproducibly provision and tear down the environment.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL define all AWS resources (S3_Bucket, API_Gateway, CloudFront_Distribution, IAM roles) in a single YAML template file.
2. THE CloudFormation_Stack SHALL export the CloudFront_Distribution domain name as a stack output named "PyPIEndpoint".
3. THE CloudFormation_Stack SHALL export the S3_Bucket name as a stack output named "BucketName".
4. THE Stack_Deployer SHALL use the AWS CLI `cloudformation deploy` command to create or update the stack.
5. THE Stack_Deployer SHALL accept a stack name parameter to allow multiple independent deployments.
6. IF the CloudFormation deployment fails, THEN THE Stack_Deployer SHALL report the failure reason from CloudFormation events.
7. THE CloudFormation_Stack SHALL use parameters for configurable values including stack name prefix and cache TTL.

### Requirement 5: Python Upload CLI

**User Story:** As a developer, I want a Python CLI tool to upload packages to the S3 bucket, so that I can publish private packages without manual S3 operations.

#### Acceptance Criteria

1. THE Upload_CLI SHALL accept a Distribution_File path as a required positional argument.
2. THE Upload_CLI SHALL accept a bucket name as a required argument via the `--bucket` flag.
3. WHEN a Distribution_File is provided, THE Upload_CLI SHALL upload the file to the S3_Bucket under the path `packages/{package_name}/{filename}`.
4. WHEN a Distribution_File is uploaded, THE Upload_CLI SHALL regenerate the Package_Detail_Page for the affected package by listing all Distribution_Files for that package in the S3_Bucket.
5. WHEN a Distribution_File is uploaded, THE Upload_CLI SHALL regenerate the Package_Index_Page by listing all packages in the S3_Bucket.
6. THE Upload_CLI SHALL generate Package_Index_Page and Package_Detail_Page HTML that conforms to PEP 503 Simple Repository API format.
7. IF the specified Distribution_File does not exist on the local filesystem, THEN THE Upload_CLI SHALL exit with a non-zero exit code and print an error message to stderr.
8. IF the S3 upload operation fails, THEN THE Upload_CLI SHALL exit with a non-zero exit code and print the error details to stderr.
9. THE Upload_CLI SHALL extract the package name from the Distribution_File filename using standard Python packaging naming conventions.
10. THE Upload_CLI SHALL accept an optional `--cloudfront-distribution-id` flag and, WHEN provided, create a CloudFront invalidation for the updated index pages.
11. WHEN `--bucket` or `--cloudfront-distribution-id` are not provided on the `upload` subcommand, THE Upload_CLI SHALL fall back to values stored in the configuration file if one exists.

### Requirement 11: CLI Configuration

**User Story:** As a developer, I want to save my default bucket and CloudFront distribution ID so that I don't have to specify them on every upload command.

#### Acceptance Criteria

1. THE Upload_CLI SHALL provide a `configure` subcommand that persists default settings to a configuration file.
2. THE `configure` subcommand SHALL accept `--bucket` and `--cloudfront-distribution-id` flags and save their values.
3. THE configuration file SHALL be stored at `~/.s3pypi/config.json`.
4. THE configuration file SHALL use JSON format with keys `bucket` and `cloudfront_distribution_id`.
5. WHEN the `configure` subcommand is run, THE Upload_CLI SHALL create the `~/.s3pypi/` directory if it does not exist.
6. WHEN the `configure` subcommand is run with a subset of flags, THE Upload_CLI SHALL merge the new values with any existing configuration, preserving values not explicitly overridden.
7. WHEN the `upload` subcommand is run without `--bucket`, THE Upload_CLI SHALL read the bucket from the configuration file. IF neither the flag nor the configuration file provides a bucket, THE Upload_CLI SHALL exit with a non-zero exit code and print an error message to stderr.
8. WHEN the `upload` subcommand is run without `--cloudfront-distribution-id`, THE Upload_CLI SHALL read the distribution ID from the configuration file if present.
9. THE `configure` subcommand SHALL print the saved configuration to stdout after writing.

### Requirement 6: PEP 503 Compliance

**User Story:** As a developer, I want the repository to comply with PEP 503, so that standard pip commands work without modification.

#### Acceptance Criteria

1. THE Package_Index_Page SHALL contain an HTML anchor element for each package, with the href attribute set to the normalized package name path.
2. THE Package_Detail_Page SHALL contain an HTML anchor element for each Distribution_File, with the href attribute set to the Distribution_File download URL.
3. THE Upload_CLI SHALL normalize package names by converting to lowercase and replacing any runs of underscores, hyphens, or periods with a single hyphen, per PEP 503.
4. WHEN a pip client requests packages using `--index-url` pointed at the CloudFront_Distribution domain, THE Simple_Repository_API SHALL serve valid responses that allow pip to discover and download packages.

### Requirement 7: Package Build Configuration

**User Story:** As a developer, I want the project to use pyproject.toml for build configuration, so that the project follows modern Python packaging standards.

#### Acceptance Criteria

1. THE project SHALL define build configuration in a pyproject.toml file.
2. THE pyproject.toml SHALL specify the MIT license.
3. THE pyproject.toml SHALL list "Topaz Bott" with email "topaz@topazhome.net" as the author.
4. THE pyproject.toml SHALL declare all runtime dependencies required by the Upload_CLI.
5. THE pyproject.toml SHALL define a console script entry point for the Upload_CLI.

### Requirement 8: Code Quality and Testing

**User Story:** As a developer, I want all code validated by pylint and bandit with comprehensive tests, so that the codebase maintains high quality and security standards.

#### Acceptance Criteria

1. THE project SHALL include unit tests for all Upload_CLI functions.
2. THE project SHALL include a smoke test that confirms all Python source files pass pylint validation.
3. THE project SHALL include a smoke test that confirms all Python source files pass bandit validation.
4. THE project SHALL include unit tests for Package_Index_Page and Package_Detail_Page HTML generation.
5. THE project SHALL include unit tests for package name normalization logic.
6. THE project SHALL include unit tests for Distribution_File filename parsing logic.

### Requirement 9: Documentation

**User Story:** As a user of the system, I want comprehensive documentation, so that I can understand, deploy, operate, and use the private PyPI server.

#### Acceptance Criteria

1. THE project SHALL include a README.md with an overview, quickstart guide, and architecture summary.
2. THE project SHALL include design documentation with architecture diagrams showing the relationship between CloudFront_Distribution, API_Gateway, and S3_Bucket.
3. THE project SHALL include end-user documentation describing how to install packages from the private repository using pip.
4. THE project SHALL include operational documentation describing how to deploy, update, monitor, and tear down the CloudFormation_Stack.
5. THE project SHALL include a CHANGELOG.md following the Keep a Changelog 1.1.0 format.
6. THE project SHALL include documentation describing how to use the Upload_CLI to publish packages.

### Requirement 10: Index Page Generation — Round-Trip Property

**User Story:** As a developer, I want index page generation to be verifiably correct, so that generated HTML always round-trips through parsing without data loss.

#### Acceptance Criteria

1. FOR ALL valid lists of package names, generating a Package_Index_Page and then parsing the HTML to extract package names SHALL produce the original list of normalized package names.
2. FOR ALL valid lists of Distribution_File filenames for a package, generating a Package_Detail_Page and then parsing the HTML to extract filenames SHALL produce the original list of filenames.
