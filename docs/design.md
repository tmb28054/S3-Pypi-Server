# Design Documentation

## Overview

s3-pypi-server implements a PEP 503 compliant Python package repository using AWS managed services. The design prioritizes simplicity, low operational overhead, and cost efficiency by avoiding any compute resources (no Lambda, no EC2).

## Architecture

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌───────────┐
│   pip    │────▶│  CloudFront  │────▶│ API Gateway │────▶│  S3       │
│  client  │     │  (CDN/TLS)   │     │  (REST API) │     │  (store)  │
└──────────┘     └──────────────┘     └─────────────┘     └───────────┘

┌──────────┐                                               ┌───────────┐
│  s3pypi  │──────────────────────────────────────────────▶│  S3       │
│   CLI    │──────────────────────────────────────────────▶│CloudFront │
└──────────┘          upload + invalidate                  └───────────┘
```

### Components

**S3 Bucket** — Stores two types of objects:
- `packages/{normalized_name}/{filename}` — Distribution files (wheels, sdists).
- `simple/{normalized_name}/index.html` — PEP 503 detail pages listing files for a package.
- `simple/index.html` — PEP 503 root index listing all packages.

Encryption (AES-256), versioning, and public access blocking are enabled by default.

**API Gateway** — REST API with AWS service integration (no Lambda). Maps:
- `GET /simple/` → `s3://bucket/simple/index.html`
- `GET /simple/{package}/` → `s3://bucket/simple/{package}/index.html`
- `GET /simple/{package}/{file}` → `s3://bucket/packages/{package}/{file}`

Returns `text/html` for index pages and binary passthrough for distribution files.

**CloudFront** — CDN layer providing:
- HTTPS termination with TLS 1.2 minimum.
- Caching with configurable TTL (default 300s).
- Origin pointed at the API Gateway `prod` stage.

**CLI (`s3pypi`)** — Command-line tool that:
1. Uploads a distribution file to the correct S3 key.
2. Regenerates the package's detail page by listing files in S3.
3. Regenerates the root index page by listing all package prefixes.
4. Optionally creates a CloudFront invalidation for immediate cache refresh.

## Key Design Decisions

### No Lambda
API Gateway's native S3 integration handles all read operations. This eliminates cold starts, reduces cost, and simplifies the deployment to a single CloudFormation template.

### Index regeneration on upload
Rather than generating index pages on-the-fly per request, the CLI regenerates static HTML files in S3 after each upload. This means reads are a single S3 GetObject — fast and cheap.

### PEP 503 compliance
All generated HTML follows PEP 503 (Simple Repository API) including:
- `<!DOCTYPE html>` declaration
- `<meta name="pypi:repository-version" content="1.0">` tag
- Normalized package names in URLs (lowercase, hyphens)

### Package name normalization
Follows PEP 503: lowercase, replace runs of `[-_.]` with a single hyphen. This is applied consistently in S3 keys, HTML generation, and URL routing.

## Data Flow: Upload

1. User runs `s3pypi upload my_pkg-1.0.0.whl --bucket my-bucket`.
2. CLI parses filename → `(my_pkg, 1.0.0, .whl)`.
3. Normalizes name → `my-pkg`.
4. Uploads file to `s3://my-bucket/packages/my-pkg/my_pkg-1.0.0.whl`.
5. Lists all files under `packages/my-pkg/` and writes detail page to `simple/my-pkg/index.html`.
6. Lists all package prefixes under `packages/` and writes root index to `simple/index.html`.
7. If `--cloudfront-distribution-id` is provided, invalidates `/simple/` and `/simple/my-pkg/`.

## Data Flow: Install

1. `pip` requests `GET /simple/` → CloudFront → API Gateway → S3 `simple/index.html`.
2. `pip` finds the package link and requests `GET /simple/my-pkg/` → detail page.
3. `pip` finds the file link and requests `GET /simple/my-pkg/my_pkg-1.0.0.whl` → binary download from `packages/my-pkg/my_pkg-1.0.0.whl`.
