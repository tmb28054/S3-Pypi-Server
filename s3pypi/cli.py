"""CLI entry point for s3pypi."""

from __future__ import annotations

import argparse
import json
import os
import sys

from botocore.exceptions import ClientError

from s3pypi.config import load_config, save_config
from s3pypi.invalidation import create_invalidation
from s3pypi.packaging import normalize_name, parse_distribution_filename
from s3pypi.uploader import S3PyPIUploader


def main(argv: list[str] | None = None) -> None:
    """Console script entry point for s3pypi.

    Parses command-line arguments and dispatches to the upload or
    configure workflow. Exits with code 1 for runtime errors and
    code 2 for argument errors (argparse default).
    """
    parser = argparse.ArgumentParser(
        prog="s3pypi",
        description="Upload Python packages to a private S3-backed PyPI server.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # -- upload subcommand --
    upload_parser = subparsers.add_parser(
        "upload",
        help="Upload a distribution file and regenerate index pages.",
    )
    upload_parser.add_argument(
        "dist_file",
        help="Path to the distribution file (.whl or .tar.gz) to upload.",
    )
    upload_parser.add_argument(
        "--bucket",
        default=None,
        help="Name of the S3 bucket to upload to. Falls back to configured value.",
    )
    upload_parser.add_argument(
        "--cloudfront-distribution-id",
        default=None,
        help="CloudFront distribution ID to invalidate after upload.",
    )

    # -- configure subcommand --
    configure_parser = subparsers.add_parser(
        "configure",
        help="Save default settings for bucket and CloudFront distribution ID.",
    )
    configure_parser.add_argument(
        "--bucket",
        default=None,
        help="Default S3 bucket name.",
    )
    configure_parser.add_argument(
        "--cloudfront-distribution-id",
        default=None,
        help="Default CloudFront distribution ID.",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_usage(sys.stderr)
        raise SystemExit(2)

    if args.command == "configure":
        _handle_configure(args)
    elif args.command == "upload":
        _handle_upload(args)


def _handle_configure(args: argparse.Namespace) -> None:
    """Handle the configure subcommand."""
    if args.bucket is None and args.cloudfront_distribution_id is None:
        print(
            "error: at least one of --bucket or --cloudfront-distribution-id is required",
            file=sys.stderr,
        )
        raise SystemExit(2)

    new_values: dict[str, str | None] = {
        "bucket": args.bucket,
        "cloudfront_distribution_id": args.cloudfront_distribution_id,
    }

    try:
        merged = save_config(new_values)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(merged, indent=2))


def _handle_upload(args: argparse.Namespace) -> None:
    """Handle the upload subcommand."""
    bucket = args.bucket
    cf_distribution_id = args.cloudfront_distribution_id

    # Fall back to config for missing values
    if bucket is None or cf_distribution_id is None:
        try:
            config = load_config()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

        if bucket is None:
            bucket = config.get("bucket")
        if cf_distribution_id is None:
            cf_distribution_id = config.get("cloudfront_distribution_id")

    if bucket is None:
        print(
            "error: --bucket is required (not provided and not found in config)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        uploader = S3PyPIUploader(bucket=bucket)
        uploader.upload(args.dist_file)

        if cf_distribution_id:
            filename = os.path.basename(args.dist_file)
            name, _version, _ext = parse_distribution_filename(filename)
            normalized = normalize_name(name)
            paths = ["/simple/", f"/simple/{normalized}/"]
            create_invalidation(cf_distribution_id, paths)

    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    except ClientError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
