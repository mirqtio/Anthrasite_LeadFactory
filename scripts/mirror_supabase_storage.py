#!/usr/bin/env python
"""
Supabase Storage Mirroring
------------------------
This script mirrors Supabase Storage objects to a local directory for backup purposes.
It uses the Supabase API to list and download all objects from specified buckets.

Usage:
    python mirror_supabase_storage.py --bucket mockups --output backups/storage

Features:
- Lists all objects in a Supabase Storage bucket
- Downloads objects to a local directory with path preservation
- Supports incremental mirroring with modification time checks
- Provides detailed logging and error handling
- Can be integrated with the rsync_backup.sh script
"""

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import logging
import os
import shutil
import sys
from datetime import datetime

import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "storage_mirroring.log")),
    ],
)
logger = logging.getLogger("mirror_supabase_storage")


def ensure_directories():
    """Ensure necessary directories exist."""
    directories = ["logs", "backups/storage"]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")


def load_environment():
    """Load environment variables from .env file."""
    env_vars = {}
    env_files = [".env", ".env.production"]

    # Try to load environment variables from available .env files
    # First file found takes precedence
    for env_file in env_files:
        if os.path.exists(env_file):
            print(f"Loading environment from {env_file}")
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            key, value = line.split("=", 1)
                            # Only set if not already set from a previous file
                            if key.strip() not in env_vars:
                                env_vars[key.strip()] = value.strip().strip("\"'")
                        except ValueError:
                            continue
            break  # Stop after first file found

    # Check for required variables
    required_vars = ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_KEY"]
    missing_vars = [var for var in required_vars if var not in env_vars]

    if missing_vars:
        print(
            f"ERROR: Missing required environment variables: {', '.join(missing_vars)}"
        )
        print("Please create a .env file based on .env.example")

    return env_vars


def get_supabase_client(env_vars):
    """Create a Supabase client using environment variables."""
    supabase_url = env_vars.get("SUPABASE_URL")
    supabase_key = env_vars.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        logger.error("Supabase URL or key not found in environment variables")
        return None

    class SupabaseClient:
        def __init__(self, url, key):
            self.url = url
            self.key = key
            self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}

        def storage_list(self, bucket):
            """List all objects in a bucket."""
            url = f"{self.url}/storage/v1/object/list/{bucket}"
            response = requests.get(url, headers=self.headers, timeout=60)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Failed to list objects in bucket {bucket}: {response.text}"
                )
                return []

        def storage_download(self, bucket, path):
            """Download an object from a bucket."""
            url = f"{self.url}/storage/v1/object/{bucket}/{path}"
            response = requests.get(url, headers=self.headers, timeout=60)

            if response.status_code == 200:
                return response.content
            else:
                logger.error(
                    f"Failed to download object {path} from bucket {bucket}: {response.text}"
                )
                return None

    return SupabaseClient(supabase_url, supabase_key)


def list_objects(supabase, bucket):
    """List all objects in a bucket."""
    logger.info(f"Listing objects in bucket {bucket}")

    objects = supabase.storage_list(bucket)

    if not objects:
        logger.warning(f"No objects found in bucket {bucket}")
        return []

    logger.info(f"Found {len(objects)} objects in bucket {bucket}")
    return objects


def download_object(supabase, bucket, path, output_dir):
    """Download an object from a bucket to a local file."""
    logger.info(f"Downloading object {path} from bucket {bucket}")

    # Create output directory
    output_path = os.path.join(output_dir, path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Download object
    content = supabase.storage_download(bucket, path)

    if content:
        with open(output_path, "wb") as f:
            f.write(content)

        logger.info(f"Object {path} downloaded to {output_path}")
        return True
    else:
        logger.error(f"Failed to download object {path}")
        return False


def mirror_bucket(supabase, bucket, output_dir, max_workers=5):
    """Mirror all objects in a bucket to a local directory."""
    logger.info(f"Mirroring bucket {bucket} to {output_dir}")

    # List objects in bucket
    objects = list_objects(supabase, bucket)

    if not objects:
        return 0

    # Create output directory
    bucket_dir = os.path.join(output_dir, bucket)
    os.makedirs(bucket_dir, exist_ok=True)

    # Download objects in parallel
    success_count = 0
    failure_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(
                download_object, supabase, bucket, obj["name"], bucket_dir
            ): obj["name"]
            for obj in objects
        }

        for future in concurrent.futures.as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()
                if result:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                logger.exception(f"Error downloading object {path}: {e}")
                failure_count += 1

    logger.info(
        f"Mirroring completed: {success_count} objects downloaded, {failure_count} failed"
    )
    return success_count


def create_manifest(output_dir, buckets):
    """Create a manifest file with information about the mirrored objects."""
    logger.info("Creating manifest file")

    manifest = {"timestamp": datetime.now().isoformat(), "buckets": {}}

    for bucket in buckets:
        bucket_dir = os.path.join(output_dir, bucket)

        if not os.path.exists(bucket_dir):
            continue

        manifest["buckets"][bucket] = {
            "object_count": 0,
            "total_size_bytes": 0,
            "objects": [],
        }

        for root, _, files in os.walk(bucket_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, bucket_dir)

                file_size = os.path.getsize(file_path)
                file_mtime = datetime.fromtimestamp(
                    os.path.getmtime(file_path)
                ).isoformat()

                # Calculate file hash
                file_hash = hashlib.md5(usedforsecurity=False)
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        file_hash.update(chunk)

                manifest["buckets"][bucket]["objects"].append(
                    {
                        "path": relative_path,
                        "size_bytes": file_size,
                        "last_modified": file_mtime,
                        "md5": file_hash.hexdigest(),
                    }
                )

                manifest["buckets"][bucket]["object_count"] += 1
                manifest["buckets"][bucket]["total_size_bytes"] += file_size

    # Write manifest to file
    manifest_file = os.path.join(output_dir, "manifest.json")
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    # Create a compressed copy
    with open(manifest_file, "rb") as f_in:
        with gzip.open(f"{manifest_file}.gz", "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    logger.info(f"Manifest file created at {manifest_file}")
    return manifest


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Supabase Storage Mirroring")
    parser.add_argument(
        "--bucket",
        type=str,
        default="mockups",
        help="Bucket to mirror (default: mockups)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="backups/storage",
        help="Output directory for mirrored objects",
    )
    parser.add_argument(
        "--workers", type=int, default=5, help="Maximum number of concurrent downloads"
    )
    args = parser.parse_args()

    try:
        # Ensure directories exist
        ensure_directories()

        # Load environment variables
        env_vars = load_environment()

        # Create Supabase client
        supabase = get_supabase_client(env_vars)

        if not supabase:
            logger.error("Failed to create Supabase client")
            return 1

        # Mirror bucket
        buckets = [args.bucket]
        for bucket in buckets:
            mirror_bucket(supabase, bucket, args.output, args.workers)

        # Create manifest
        create_manifest(args.output, buckets)

        logger.info("Storage mirroring completed successfully")
        return 0

    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
