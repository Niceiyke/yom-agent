"""Built-in storage tool for yom."""

from __future__ import annotations

import json

from yom.tools import tool


@tool(
    name="s3_put",
    description="""Store data in S3-compatible storage.
    
    Args:
        bucket: S3 bucket name
        key: Object key (file path)
        content: Content to store
        region: AWS region
        access_key: AWS access key (or set AWS_ACCESS_KEY_ID env var)
        secret_key: AWS secret key (or set AWS_SECRET_ACCESS_KEY env var)
        endpoint: Custom endpoint for S3-compatible services (MinIO, etc.)
    
    Returns:
        Success message with object URL.
    """,
    schema={
        "type": "object",
        "properties": {
            "bucket": {"type": "string", "description": "S3 bucket name"},
            "key": {"type": "string", "description": "Object key"},
            "content": {"type": "string", "description": "Content to store"},
            "region": {"type": "string", "description": "AWS region", "default": "us-east-1"},
            "access_key": {"type": "string", "description": "AWS access key"},
            "secret_key": {"type": "string", "description": "AWS secret key"},
            "endpoint": {"type": "string", "description": "Custom S3 endpoint (MinIO, etc.)"}
        },
        "required": ["bucket", "key", "content"]
    }
)
def s3_put(
    bucket: str,
    key: str,
    content: str,
    region: str = "us-east-1",
    access_key: str | None = None,
    secret_key: str | None = None,
    endpoint: str | None = None,
) -> str:
    """Store data in S3."""
    import os
    
    try:
        import boto3
    except ImportError:
        return "Error: boto3 not installed. Run: pip install boto3"

    access_key = access_key or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = secret_key or os.environ.get("AWS_SECRET_ACCESS_KEY")

    if not access_key or not secret_key:
        return "Error: AWS credentials required. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY env vars."

    try:
        kwargs = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": region,
        }
        if endpoint:
            kwargs["endpoint_url"] = endpoint

        s3 = boto3.client("s3", **kwargs)
        s3.put_object(Bucket=bucket, Key=key, Body=content.encode("utf-8"))

        url = f"s3://{bucket}/{key}"
        return f"Successfully stored at {url}"

    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


@tool(
    name="s3_get",
    description="""Retrieve data from S3-compatible storage.
    
    Args:
        bucket: S3 bucket name
        key: Object key
        region: AWS region
        access_key: AWS access key
        secret_key: AWS secret key
        endpoint: Custom endpoint
    
    Returns:
        Object content.
    """,
    schema={
        "type": "object",
        "properties": {
            "bucket": {"type": "string", "description": "S3 bucket name"},
            "key": {"type": "string", "description": "Object key"},
            "region": {"type": "string", "description": "AWS region"},
            "access_key": {"type": "string", "description": "AWS access key"},
            "secret_key": {"type": "string", "description": "AWS secret key"},
            "endpoint": {"type": "string", "description": "Custom S3 endpoint"}
        },
        "required": ["bucket", "key"]
    }
)
def s3_get(
    bucket: str,
    key: str,
    region: str = "us-east-1",
    access_key: str | None = None,
    secret_key: str | None = None,
    endpoint: str | None = None,
) -> str:
    """Retrieve data from S3."""
    import os

    try:
        import boto3
    except ImportError:
        return "Error: boto3 not installed. Run: pip install boto3"

    access_key = access_key or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = secret_key or os.environ.get("AWS_SECRET_ACCESS_KEY")

    if not access_key or not secret_key:
        return "Error: AWS credentials required."

    try:
        kwargs = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": region,
        }
        if endpoint:
            kwargs["endpoint_url"] = endpoint

        s3 = boto3.client("s3", **kwargs)
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        return content

    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


@tool(
    name="s3_list",
    description="""List objects in S3 bucket.
    
    Args:
        bucket: S3 bucket name
        prefix: Object key prefix filter
        max_items: Maximum number of items to return
        region: AWS region
        access_key: AWS access key
        secret_key: AWS secret key
        endpoint: Custom endpoint
    
    Returns:
        List of objects.
    """,
    schema={
        "type": "object",
        "properties": {
            "bucket": {"type": "string", "description": "S3 bucket name"},
            "prefix": {"type": "string", "description": "Key prefix filter"},
            "max_items": {"type": "integer", "description": "Max items to return"},
            "region": {"type": "string", "description": "AWS region"},
            "access_key": {"type": "string", "description": "AWS access key"},
            "secret_key": {"type": "string", "description": "AWS secret key"},
            "endpoint": {"type": "string", "description": "Custom endpoint"}
        },
        "required": ["bucket"]
    }
)
def s3_list(
    bucket: str,
    prefix: str = "",
    max_items: int = 100,
    region: str = "us-east-1",
    access_key: str | None = None,
    secret_key: str | None = None,
    endpoint: str | None = None,
) -> str:
    """List objects in S3 bucket."""
    import os

    try:
        import boto3
    except ImportError:
        return "Error: boto3 not installed."

    access_key = access_key or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = secret_key or os.environ.get("AWS_SECRET_ACCESS_KEY")

    try:
        kwargs = {
            "aws_access_key_id": access_key or "",
            "aws_secret_access_key": secret_key or "",
            "region_name": region,
        }
        if endpoint:
            kwargs["endpoint_url"] = endpoint

        s3 = boto3.client("s3", **kwargs)
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_items)

        objects = []
        if "Contents" in response:
            for obj in response["Contents"]:
                objects.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": str(obj["LastModified"])
                })

        return json.dumps({"bucket": bucket, "prefix": prefix, "objects": objects}, indent=2)

    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


__all__ = ["s3_put", "s3_get", "s3_list"]
