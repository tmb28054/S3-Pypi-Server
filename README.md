# s3-pypi-server

A private PyPI server backed by AWS S3, API Gateway, and CloudFront. Upload Python packages to S3 and install them with `pip` using a PEP 503 compliant simple repository interface.

## Architecture

```
pip install ──▶ CloudFront ──▶ API Gateway ──▶ S3 Bucket
                 (cache)        (REST API)     (storage)
```

- **S3** stores distribution files under `packages/{name}/` and HTML index pages under `simple/`.
- **API Gateway** maps `/simple/` URL paths to S3 objects, serving HTML indexes and binary downloads.
- **CloudFront** caches responses and provides HTTPS with TLS 1.2+.
- **CLI** uploads packages to S3 and regenerates PEP 503 index pages automatically.

See [docs/design.md](docs/design.md) for detailed architecture documentation.

## Quickstart

### 1. Deploy the infrastructure

```bash
./deploy.sh my-pypi
```

This creates the S3 bucket, API Gateway, and CloudFront distribution. The script prints the CloudFront domain and bucket name on success.

### 2. Upload a package

```bash
# Build your package
python -m build

# Save your defaults (one-time setup)
s3pypi configure --bucket <bucket-name> --cloudfront-distribution-id <distribution-id>

# Upload to your private PyPI
s3pypi upload dist/my_package-1.0.0-py3-none-any.whl
```

Or pass flags explicitly without configuring:

```bash
s3pypi upload dist/my_package-1.0.0-py3-none-any.whl --bucket <bucket-name>
```

### 3. Install from your private PyPI

```bash
pip install my-package --index-url https://<cloudfront-domain>/simple/
```

## CLI Usage

```
s3pypi configure [--bucket <bucket>] [--cloudfront-distribution-id <id>]
s3pypi upload <dist_file> [--bucket <bucket>] [--cloudfront-distribution-id <id>]
```

### configure

Save default settings so you don't need to pass `--bucket` and `--cloudfront-distribution-id` on every upload. Settings are stored in `~/.s3pypi/config.json`.

```bash
s3pypi configure --bucket my-pypi-bucket --cloudfront-distribution-id E1234567890
```

### upload

| Argument | Required | Description |
|---|---|---|
| `dist_file` | Yes | Path to `.whl` or `.tar.gz` distribution file |
| `--bucket` | No* | S3 bucket name. Falls back to configured value. |
| `--cloudfront-distribution-id` | No | CloudFront distribution ID to invalidate. Falls back to configured value. |

\* Required if not previously saved via `s3pypi configure`.

Exit codes: `0` success, `1` runtime error, `2` argument error.

## Configuration

### CLI defaults

Run `s3pypi configure` once to save your bucket and distribution ID:

```bash
s3pypi configure --bucket my-pypi-bucket --cloudfront-distribution-id E1234567890
```

After that, uploads only need the file path:

```bash
s3pypi upload dist/my_package-1.0.0-py3-none-any.whl
```

### CloudFormation parameters

The CloudFormation stack accepts these parameters:

| Parameter | Default | Description |
|---|---|---|
| `StackNamePrefix` | `s3-pypi` | Prefix for resource naming |
| `CacheTTL` | `300` | CloudFront default cache TTL in seconds |
| `DomainName` | *(empty)* | Optional custom domain (e.g. `pypi.example.org`) |
| `AcmCertificateArn` | *(empty)* | ACM certificate ARN for the custom domain |

Override during deployment:

```bash
./deploy.sh my-pypi StackNamePrefix=team-pypi CacheTTL=600
```

### Custom domain

To use a custom domain like `pypi.example.org`:

1. Request (or import) an ACM certificate in **us-east-1** for your domain.
2. Deploy with both parameters:

```bash
./deploy.sh my-pypi DomainName=pypi.example.org AcmCertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/abc-123
```

3. Create a CNAME or alias DNS record pointing `pypi.example.org` to the CloudFront distribution domain.

When neither `DomainName` nor `AcmCertificateArn` is provided, the stack uses the default `*.cloudfront.net` domain.

## Development

### Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with test dependencies
pip install -e ".[test]"
```

### Running tests

```bash
# Full test suite
pytest

# With coverage
pytest --cov=s3pypi --cov-fail-under=80

# Smoke tests only
pytest -m smoke
```

### Linting

```bash
pylint s3pypi/
bandit -r s3pypi/
```

## License

MIT — see [LICENSE](LICENSE) for details.
