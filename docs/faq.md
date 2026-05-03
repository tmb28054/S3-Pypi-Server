# FAQ

## General

**Q: Does this require any running servers or Lambda functions?**
No. The architecture is entirely serverless using S3 for storage, API Gateway for HTTP routing (with native S3 integration), and CloudFront for caching. There are no compute resources to manage.

**Q: How much does it cost?**
Costs are driven by S3 storage, API Gateway requests, and CloudFront data transfer. For a small team hosting a handful of private packages, expect costs well under $1/month. S3 storage is $0.023/GB, and API Gateway is $3.50 per million requests.

**Q: Is this PEP 503 compliant?**
Yes. All generated index pages follow the PEP 503 Simple Repository API specification, including proper HTML structure, repository version metadata, and normalized package names.

## Deployment

**Q: What AWS permissions do I need to deploy?**
You need permissions to create and manage: S3 buckets, API Gateway REST APIs, CloudFront distributions, and IAM roles. The `deploy.sh` script uses `--capabilities CAPABILITY_IAM` to acknowledge IAM resource creation.

**Q: Can I use a custom domain?**
Yes. Pass `DomainName` and `AcmCertificateArn` when deploying:

```bash
./deploy.sh my-pypi DomainName=pypi.example.org AcmCertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/abc-123
```

The ACM certificate must be in us-east-1 (CloudFront requirement). After deployment, create a CNAME or alias DNS record pointing your domain to the CloudFront distribution. When these parameters are omitted, the default `*.cloudfront.net` domain is used.

**Q: How do I tear down the stack?**
```bash
aws cloudformation delete-stack --stack-name <stack-name>
```
Note: The S3 bucket must be empty before the stack can be deleted.

## Usage

**Q: What file formats are supported?**
Wheels (`.whl`) and source distributions (`.tar.gz`).

**Q: Can I upload multiple versions of the same package?**
Yes. Each upload adds the file to S3 and regenerates the detail page to include all versions.

**Q: How long before an uploaded package is available?**
Immediately via the API Gateway endpoint. If using CloudFront, it depends on the cache TTL (default 300 seconds) unless you have a distribution ID configured (via `s3pypi configure` or `--cloudfront-distribution-id`) to trigger an invalidation.

**Q: Do I have to pass --bucket every time?**
No. Run `s3pypi configure --bucket <name>` once and it will be saved to `~/.s3pypi/config.json`. The same applies to `--cloudfront-distribution-id`. CLI flags override configured values when both are present.

**Q: Can I delete a package?**
Not through the CLI currently. You can delete the file directly from S3 and then re-upload any remaining package to trigger index regeneration, or manually delete the S3 objects and regenerate the index pages.
