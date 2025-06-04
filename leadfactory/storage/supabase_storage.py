"""
Supabase storage implementation for LeadFactory.

This module provides file storage capabilities using Supabase Storage,
including PDF and PNG upload functionality with secure URL generation.
"""

import logging
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from supabase import Client, create_client

from leadfactory.config import get_env

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """
    Supabase storage implementation for file uploads and secure URL generation.

    Supports PDF reports, PNG images, and other file types with configurable
    expiration times for secure access.
    """

    def __init__(self, bucket_name: str = "reports"):
        """
        Initialize Supabase storage.

        Args:
            bucket_name: Name of the Supabase storage bucket to use
        """
        self.bucket_name = bucket_name

        # Get Supabase configuration
        self.supabase_url = get_env("SUPABASE_URL")
        self.supabase_key = get_env("SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY environment variables must be set"
            )

        # Create Supabase client
        self.client: Client = create_client(self.supabase_url, self.supabase_key)

        logger.info(f"Supabase storage initialized for bucket: {bucket_name}")

    def upload_file(
        self,
        file_path: Union[str, Path],
        storage_path: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to Supabase storage.

        Args:
            file_path: Local path to the file to upload
            storage_path: Path where the file will be stored in Supabase
            content_type: MIME type of the file (auto-detected if not provided)
            metadata: Additional metadata to store with the file

        Returns:
            Dict containing upload result information

        Raises:
            FileNotFoundError: If the file doesn't exist
            Exception: If upload fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Auto-detect content type if not provided
        if not content_type:
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"

        try:
            # Read file content
            with file_path.open("rb") as f:
                file_content = f.read()

            # Prepare file options
            file_options = {"content-type": content_type}
            if metadata:
                file_options["metadata"] = metadata

            # Upload to Supabase
            result = self.client.storage.from_(self.bucket_name).upload(
                path=storage_path, file=file_content, file_options=file_options
            )

            # Get file info
            file_info = {
                "storage_path": storage_path,
                "bucket": self.bucket_name,
                "size_bytes": len(file_content),
                "content_type": content_type,
                "uploaded_at": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
            }

            logger.info(f"Successfully uploaded file to {storage_path}")
            return file_info

        except Exception as e:
            logger.error(f"Failed to upload file {file_path} to {storage_path}: {e}")
            raise

    def upload_pdf_report(
        self,
        pdf_path: Union[str, Path],
        report_id: str,
        user_id: str,
        purchase_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a PDF report with standardized naming and metadata.

        Args:
            pdf_path: Local path to the PDF file
            report_id: Unique identifier for the report
            user_id: User who owns the report
            purchase_id: Optional purchase ID associated with the report

        Returns:
            Dict containing upload result and metadata
        """
        # Generate standardized storage path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        storage_path = f"reports/{user_id}/{report_id}_{timestamp}.pdf"

        # Prepare metadata
        metadata = {
            "report_id": report_id,
            "user_id": user_id,
            "upload_timestamp": timestamp,
            "file_type": "pdf_report",
        }

        if purchase_id:
            metadata["purchase_id"] = purchase_id

        return self.upload_file(
            file_path=pdf_path,
            storage_path=storage_path,
            content_type="application/pdf",
            metadata=metadata,
        )

    def upload_png_image(
        self, png_path: Union[str, Path], image_id: str, category: str = "images"
    ) -> Dict[str, Any]:
        """
        Upload a PNG image with standardized naming.

        Args:
            png_path: Local path to the PNG file
            image_id: Unique identifier for the image
            category: Category/folder for the image (default: "images")

        Returns:
            Dict containing upload result and metadata
        """
        # Generate standardized storage path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        storage_path = f"{category}/{image_id}_{timestamp}.png"

        # Prepare metadata
        metadata = {
            "image_id": image_id,
            "category": category,
            "upload_timestamp": timestamp,
            "file_type": "png_image",
        }

        return self.upload_file(
            file_path=png_path,
            storage_path=storage_path,
            content_type="image/png",
            metadata=metadata,
        )

    def generate_signed_url(
        self, storage_path: str, expires_in_seconds: int = 3600
    ) -> str:
        """
        Generate a signed URL for secure file access.

        Args:
            storage_path: Path to the file in Supabase storage
            expires_in_seconds: URL expiration time in seconds (default: 1 hour)

        Returns:
            Signed URL for file access

        Raises:
            Exception: If URL generation fails
        """
        try:
            result = self.client.storage.from_(self.bucket_name).create_signed_url(
                path=storage_path, expires_in=expires_in_seconds
            )

            if "signedURL" in result:
                signed_url = result["signedURL"]
                logger.info(
                    f"Generated signed URL for {storage_path} (expires in {expires_in_seconds}s)"
                )
                return signed_url
            else:
                raise Exception(f"Failed to generate signed URL: {result}")

        except Exception as e:
            logger.error(f"Failed to generate signed URL for {storage_path}: {e}")
            raise

    def generate_secure_report_url(
        self, storage_path: str, expires_in_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Generate a secure URL for report access with extended metadata.

        Args:
            storage_path: Path to the report in Supabase storage
            expires_in_hours: URL expiration time in hours (default: 24 hours)

        Returns:
            Dict containing signed URL and expiration info
        """
        expires_in_seconds = expires_in_hours * 3600
        signed_url = self.generate_signed_url(storage_path, expires_in_seconds)

        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        return {
            "signed_url": signed_url,
            "storage_path": storage_path,
            "expires_at": expires_at.isoformat(),
            "expires_in_hours": expires_in_hours,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def list_files(self, prefix: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """
        List files in the storage bucket.

        Args:
            prefix: Optional prefix to filter files
            limit: Maximum number of files to return

        Returns:
            List of file information dictionaries
        """
        try:
            result = self.client.storage.from_(self.bucket_name).list(
                path=prefix, limit=limit
            )

            logger.info(f"Listed {len(result)} files with prefix '{prefix}'")
            return result

        except Exception as e:
            logger.error(f"Failed to list files with prefix '{prefix}': {e}")
            raise

    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from storage.

        Args:
            storage_path: Path to the file in Supabase storage

        Returns:
            True if deletion was successful

        Raises:
            Exception: If deletion fails
        """
        try:
            result = self.client.storage.from_(self.bucket_name).remove([storage_path])

            logger.info(f"Successfully deleted file: {storage_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete file {storage_path}: {e}")
            raise

    def get_file_info(self, storage_path: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a file in storage.

        Args:
            storage_path: Path to the file in Supabase storage

        Returns:
            File information dict or None if file doesn't exist
        """
        try:
            # Get file info by listing with the exact path
            directory = str(Path(storage_path).parent)
            filename = Path(storage_path).name

            files = self.list_files(prefix=directory)

            for file_info in files:
                if file_info.get("name") == filename:
                    return file_info

            return None

        except Exception as e:
            logger.error(f"Failed to get file info for {storage_path}: {e}")
            return None
