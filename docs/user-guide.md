# User Guide

This guide walks through deploying the s3-pypi-server infrastructure and using it to host private Python packages.

## Prerequisites

- AWS CLI configured with appropriate credentials.
- Python 3.10 or later.
- The `s3pypi` package installed (`pip install -e .`).

## Step 1: Deploy the AWS Infrastructure

Deploy the stack with a single command:

```bash
s3pypi deploy --stack-name my-pypi
```

Or run without arguments for interactive mode (press Enter to accept defaults):

```bash
$ s3pypi deploy
Stack name (required): my-pypi
AWS region [us-east-1]:
AWS profile []:
Stack name prefix [s3-pypi]:
Cache TTL (seconds) [300]:
...
```

You can customize parameters via flags:

```bash
s3pypi deploy --stack-name my-pypi --stack-name-prefix team-pypi --cache-ttl 600
```

On success, the stack outputs (bucket name, endpoint, table name, secret ARN) are automatically saved to `~/.s3pypi/config.json`. You can verify with:

```bash
cat ~/.s3pypi/config.json
```

### Deploy with a custom domain

```bash
s3pypi deploy --stack-name my-pypi \
    --domain-name pypi.example.org \
    --acm-certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/abc-123
```

The ACM certificate must be in **us-east-1** (required for CloudFront). After deployment, create a CNAME or alias DNS record pointing your domain to the CloudFront distribution.

### Deploy with KMS encryption

```bash
s3pypi deploy --stack-name my-pypi --enable-kms-encryption true
```

This creates a Customer Managed KMS key and encrypts the S3 bucket, DynamoDB table (if authorizer is enabled), and all CloudWatch Log Groups at rest.

### Deploy with the authorizer

```bash
s3pypi deploy --stack-name my-pypi --enable-authorizer true
```

This creates:
- A Lambda authorizer on all API Gateway routes
- A DynamoDB table for API keys
- A Secrets Manager secret for LDAP configuration
- Dedicated CloudWatch Log Groups with 30-day retention

### Deploy with VPC support

When your LDAP/AD server is on a private network:

```bash
s3pypi deploy --stack-name my-pypi \
    --enable-authorizer true \
    --vpc-id vpc-abc123 \
    --subnet-ids subnet-111,subnet-222
```

This places the authorizer Lambda inside the VPC with a Security Group allowing all outbound traffic.

### Full security deployment

```bash
s3pypi deploy --stack-name my-pypi \
    --enable-kms-encryption true \
    --enable-authorizer true \
    --vpc-id vpc-abc123 \
    --subnet-ids subnet-111,subnet-222 \
    --domain-name pypi.example.org \
    --acm-certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/abc-123
```

## Step 2: Configure the CLI

Save your defaults so you don't need to repeat them on every command. Run `configure` without flags for interactive mode:

```bash
$ s3pypi configure
S3 bucket name: my-pypi-bucket
CloudFront distribution ID: E1234567890
DynamoDB API key table name: s3-pypi-api-keys
Secrets Manager LDAP secret ARN: arn:aws:secretsmanager:us-east-1:123:secret:s3-pypi-ldap-config
```

If you already have values configured, they appear in brackets. Press Enter to keep them:

```bash
$ s3pypi configure
S3 bucket name [my-pypi-bucket]:
CloudFront distribution ID [E1234567890]:
DynamoDB API key table name [s3-pypi-api-keys]:
Secrets Manager LDAP secret ARN [arn:...]:
```

Or pass flags directly to skip prompts:

```bash
s3pypi configure \
    --bucket <bucket-name> \
    --cloudfront-distribution-id <distribution-id> \
    --api-key-table-name <table-name> \
    --ldap-secret-arn <secret-arn>
```

Settings are stored in `~/.s3pypi/config.json`. You can provide any subset of flags — existing values are preserved.

## Step 3: Configure LDAP (if authorizer is enabled)

CloudFormation creates the Secrets Manager secret with empty values. Use the CLI to populate it:

```bash
s3pypi configure-ldap \
    --host ldap.example.com \
    --bind-user "cn=admin,dc=example,dc=com" \
    --bind-password "s3cret" \
    --entitlement-group "cn=pypi-users,ou=groups,dc=example,dc=com"
```

The `--secret-arn` flag is optional if you've already configured it via `s3pypi configure`.

## Step 4: Manage API Keys (if authorizer is enabled)

Create API keys for CI/CD pipelines and automated systems:

```bash
# Create a new key
s3pypi apikey create --description "GitHub Actions"
# Output: a3f7b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c

# List all keys
s3pypi apikey list

# Get details of a specific key
s3pypi apikey get a3f7b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c

# Revoke a key
s3pypi apikey delete a3f7b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c
```

## Step 5: Build Your Package

Use standard Python build tools:

```bash
pip install build
python -m build
```

This creates distribution files in the `dist/` directory (e.g., `dist/my_package-1.0.0-py3-none-any.whl`).

## Step 6: Upload to Your Private PyPI

```bash
s3pypi upload dist/my_package-1.0.0-py3-none-any.whl
```

The CLI will:
1. Upload the file to S3.
2. Regenerate the package's detail page.
3. Regenerate the root index page.
4. Invalidate the CloudFront cache (if a distribution ID is configured or passed).

You can also pass flags explicitly:

```bash
s3pypi upload dist/my_package-1.0.0-py3-none-any.whl \
    --bucket <bucket-name> \
    --cloudfront-distribution-id <distribution-id>
```

CLI flags always override configured values.

## Step 7: Install from Your Private PyPI

### Without authentication

```bash
pip install my-package --index-url https://<endpoint>/simple/
```

### With Bearer token (API key)

```bash
pip install my-package \
    --index-url https://<endpoint>/simple/ \
    --header "Authorization: Bearer <api-key>"
```

### With Basic Auth (LDAP credentials)

```bash
pip install my-package \
    --index-url https://username:password@<endpoint>/simple/
```

### Permanent pip configuration

Add to `~/.pip/pip.conf` or `pip.conf` in your project:

```ini
[global]
extra-index-url = https://<endpoint>/simple/
```

For authenticated access, use a netrc file or environment variables for credentials.

## Uploading Source Distributions

Source distributions (`.tar.gz`) work the same way:

```bash
s3pypi upload dist/my_package-1.0.0.tar.gz
```

## Verifying the Repository

You can browse the repository index directly:

```bash
curl https://<endpoint>/simple/
curl https://<endpoint>/simple/my-package/
```

With authentication:

```bash
curl -H "Authorization: Bearer <api-key>" https://<endpoint>/simple/
```

Both should return valid HTML pages with package links.
