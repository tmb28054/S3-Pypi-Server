# User Guide

This guide walks through deploying the s3-pypi-server infrastructure and using it to host private Python packages.

## Prerequisites

- AWS CLI configured with appropriate credentials.
- Python 3.10 or later.
- The `s3pypi` package installed (`pip install -e .`).

## Step 1: Deploy the AWS Infrastructure

Run the deployment script with a stack name of your choice:

```bash
./deploy.sh my-pypi
```

You can customize parameters:

```bash
./deploy.sh my-pypi StackNamePrefix=team-pypi CacheTTL=600
```

To deploy with a custom domain (e.g., `pypi.example.org`):

```bash
./deploy.sh my-pypi \
    DomainName=pypi.example.org \
    AcmCertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/abc-123
```

The ACM certificate must be in **us-east-1** (required for CloudFront). After deployment, create a CNAME or alias DNS record pointing your domain to the CloudFront distribution.

On success, the script prints the endpoint domain and S3 bucket name. Save these — you'll need them for uploading and installing packages.

## Step 2: Build Your Package

Use standard Python build tools:

```bash
pip install build
python -m build
```

This creates distribution files in the `dist/` directory (e.g., `dist/my_package-1.0.0-py3-none-any.whl`).

## Step 3: Upload to Your Private PyPI

First, save your defaults so you don't need to repeat them:

```bash
s3pypi configure --bucket <bucket-name> --cloudfront-distribution-id <distribution-id>
```

Then upload:

```bash
s3pypi upload dist/my_package-1.0.0-py3-none-any.whl
```

The CLI will:
1. Upload the file to S3.
2. Regenerate the package's detail page.
3. Regenerate the root index page.
4. Invalidate the CloudFront cache (if a distribution ID is configured or passed).

You can also pass flags explicitly without configuring:

```bash
s3pypi upload dist/my_package-1.0.0-py3-none-any.whl \
    --bucket <bucket-name> \
    --cloudfront-distribution-id <distribution-id>
```

CLI flags always override configured values.

## Step 4: Install from Your Private PyPI

Use `pip` with the `--index-url` flag:

```bash
pip install my-package --index-url https://<cloudfront-domain>/simple/
```

To configure this permanently, add to your `pip.conf`:

```ini
[global]
index-url = https://<cloudfront-domain>/simple/
```

Or use `--extra-index-url` to search both your private server and the public PyPI:

```bash
pip install my-package --extra-index-url https://<cloudfront-domain>/simple/
```

## Uploading Source Distributions

Source distributions (`.tar.gz`) work the same way:

```bash
s3pypi upload dist/my_package-1.0.0.tar.gz
```

## Verifying the Repository

You can browse the repository index directly:

```bash
curl https://<cloudfront-domain>/simple/
curl https://<cloudfront-domain>/simple/my-package/
```

Both should return valid HTML pages with package links.
