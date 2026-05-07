# FAQ

## General

**Q: Does this require any running servers or Lambda functions?**
The core read path (S3 → API Gateway → CloudFront) is entirely serverless with no compute. If you enable the authorizer (`EnableAuthorizer=true`), a Lambda function is added to validate requests, but it only runs on-demand with no servers to manage.

**Q: How much does it cost?**
Costs are driven by S3 storage, API Gateway requests, and CloudFront data transfer. For a small team hosting a handful of private packages, expect costs well under $1/month. S3 storage is $0.023/GB, and API Gateway is $3.50 per million requests. The optional KMS key adds $1/month plus $0.03 per 10,000 API calls.

**Q: Is this PEP 503 compliant?**
Yes. All generated index pages follow the PEP 503 Simple Repository API specification, including proper HTML structure, repository version metadata, and normalized package names.

## Deployment

**Q: What AWS permissions do I need to deploy?**
You need permissions to create and manage: S3 buckets, API Gateway REST APIs, CloudFront distributions, IAM roles, and optionally KMS keys, DynamoDB tables, Secrets Manager secrets, Lambda functions, and VPC Security Groups. The `deploy` command uses `CAPABILITY_IAM` to acknowledge IAM resource creation.

**Q: Can I use a custom domain?**
Yes. Pass `DomainName` and `AcmCertificateArn` when deploying:

```bash
./deploy.sh my-pypi DomainName=pypi.example.org AcmCertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/abc-123
```

The ACM certificate must be in us-east-1 (CloudFront requirement). After deployment, create a CNAME or alias DNS record pointing your domain to the CloudFront distribution. When these parameters are omitted, the default `*.cloudfront.net` domain is used.

**Q: How do I find the bucket and table names?**
The `s3pypi deploy` command automatically saves all stack outputs (including bucket and table names) to `~/.s3pypi/config.json`. You can also query them manually:

```bash
aws cloudformation describe-stacks --stack-name <stack-name> \
  --query "Stacks[0].Outputs" --output table
```

The relevant outputs are `BucketName` and `APIKeyTableName`.

**Q: How do I tear down the stack?**
```bash
aws cloudformation delete-stack --stack-name <stack-name>
```
Note: The S3 bucket must be empty before the stack can be deleted. If KMS encryption is enabled, the KMS key will be scheduled for deletion (30-day waiting period).

**Q: Can I enable features after initial deployment?**
Yes. All optional features (KMS, authorizer, VPC) use CloudFormation conditions. You can update an existing stack to enable them:

```bash
./deploy.sh my-pypi EnableKMSEncryption=true EnableAuthorizer=true
```

## KMS Encryption

**Q: What does KMS encryption protect?**
When `EnableKMSEncryption=true`, a Customer Managed Key encrypts:
- S3 bucket objects (server-side encryption)
- DynamoDB API key table (if authorizer is enabled)
- All CloudWatch Log Groups

**Q: Can I use my own existing KMS key?**
Not currently. The stack creates and manages its own key. The key policy grants the account root full access, so you can add additional key policies via IAM.

**Q: Does KMS encryption affect performance?**
No measurable impact. AWS handles KMS encryption transparently for S3, DynamoDB, and CloudWatch Logs.

## Authorizer

**Q: What authentication methods are supported?**
Two methods:
1. **Bearer token** — API keys stored in DynamoDB. Best for CI/CD pipelines.
2. **Basic Auth** — Username/password validated against LDAP/AD. Best for developers.

The authorizer checks Bearer tokens first, then falls back to Basic Auth.

**Q: How do I configure LDAP after deployment?**
CloudFormation creates the Secrets Manager secret with empty values. Use the CLI to populate it:

```bash
s3pypi configure-ldap \
    --host ldap.example.com \
    --bind-user "cn=admin,dc=example,dc=com" \
    --bind-password "s3cret" \
    --entitlement-group "cn=pypi-users,ou=groups,dc=example,dc=com"
```

**Q: How do I create API keys?**
```bash
s3pypi apikey create --description "CI pipeline"
```

The command prints the generated key. Store it securely — it cannot be retrieved later (only listed).

**Q: Can I revoke an API key?**
Yes:
```bash
s3pypi apikey delete <key-value>
```

The key is immediately removed from DynamoDB and will be rejected on the next request.

**Q: What happens if LDAP is unreachable?**
The authorizer returns a Deny policy and logs the error. It does not fall through to allow unauthenticated access.

**Q: Can I use the authorizer without LDAP?**
Yes. You can use only API keys (Bearer tokens) and leave the LDAP secret unconfigured. Basic Auth requests will be denied since the LDAP host is empty.

## VPC

**Q: When do I need VPC support?**
Only when your LDAP/AD server is on a private network that isn't reachable from the public internet. If your LDAP server has a public endpoint, VPC placement is unnecessary.

**Q: What subnets should I use?**
Use private subnets with a NAT Gateway for outbound internet access. The Lambda needs outbound access to reach AWS services (Secrets Manager, DynamoDB, CloudWatch Logs) unless you have VPC endpoints configured.

**Q: Does VPC placement add latency?**
There may be a slight cold-start penalty (~1-2 seconds) for the first request after the Lambda scales down. Subsequent requests within the same execution environment are unaffected.

## Usage

**Q: What file formats are supported?**
Wheels (`.whl`) and source distributions (`.tar.gz`).

**Q: Can I upload multiple versions of the same package?**
Yes. Each upload adds the file to S3 and regenerates the detail page to include all versions.

**Q: How long before an uploaded package is available?**
Immediately via the API Gateway endpoint. If using CloudFront, it depends on the cache TTL (default 300 seconds) unless you have a distribution ID configured (via `s3pypi configure` or `--cloudfront-distribution-id`) to trigger an invalidation.

**Q: Do I have to pass --bucket every time?**
No. Run `s3pypi configure --bucket <name>` once and it will be saved to `~/.s3pypi/config.json`. The same applies to `--cloudfront-distribution-id`, `--api-key-table-name`, and `--ldap-secret-arn`. CLI flags override configured values when both are present.

**Q: Can I delete a package?**
Not through the CLI currently. You can delete the file directly from S3 and then re-upload any remaining package to trigger index regeneration, or manually delete the S3 objects and regenerate the index pages.

**Q: Where can I see API Gateway access logs?**
Access logs are written to a CloudWatch Log Group named `/aws/apigateway/<stack-prefix>-access-logs` with 30-day retention. Each log entry includes request ID, source IP, request time, HTTP method, resource path, status code, and response length.
