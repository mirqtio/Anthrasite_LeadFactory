"""
Enhanced Supabase PNG Upload Integration for Mockup Images.

Implements Task 7: Finalize Supabase PNG Upload Integration with:
- Reliable PNG upload to Supabase storage
- Proper error handling and retry logic
- Mockup images correctly linked to businesses
- CDN URL generation for uploaded images
- Cleanup for orphaned images
- Comprehensive error logging
"""

import asyncio
import hashlib
import io
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image

from leadfactory.storage import get_storage
from leadfactory.storage.supabase_storage import SupabaseStorage

logger = logging.getLogger(__name__)


@dataclass
class MockupUploadResult:
    """Result of mockup PNG upload operation."""

    success: bool
    storage_path: Optional[str] = None
    cdn_url: Optional[str] = None
    file_size: Optional[int] = None
    business_id: Optional[int] = None
    upload_duration: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class MockupImageMetadata:
    """Metadata for mockup images."""

    business_id: int
    mockup_type: str  # "homepage", "product", "contact", etc.
    generated_at: datetime
    original_dimensions: tuple
    optimized_dimensions: tuple
    file_size_bytes: int
    quality_score: Optional[float] = None


class MockupPNGUploader:
    """
    Enhanced PNG uploader for mockup images with comprehensive error handling.

    Features:
    - Retry logic with exponential backoff
    - Image validation and optimization
    - Orphaned image cleanup
    - CDN URL generation
    - Comprehensive error logging
    - Business linking and asset tracking
    """

    def __init__(self, bucket_name: str = "mockups"):
        """Initialize the mockup PNG uploader."""
        self.supabase_storage = SupabaseStorage(bucket_name)
        self.storage = get_storage()
        self.max_retries = 3
        self.retry_delay_base = 1.0  # seconds
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.supported_formats = {"PNG", "JPEG", "JPG"}

        logger.info(f"MockupPNGUploader initialized for bucket: {bucket_name}")

    def upload_mockup_png(
        self,
        png_path: Union[str, Path],
        business_id: int,
        mockup_type: str = "homepage",
        optimize: bool = True,
        max_width: int = 1920,
        quality: int = 85,
    ) -> MockupUploadResult:
        """
        Upload a mockup PNG with comprehensive error handling and retry logic.

        Args:
            png_path: Path to the PNG file
            business_id: ID of the business this mockup belongs to
            mockup_type: Type of mockup (homepage, product, etc.)
            optimize: Whether to optimize the image before upload
            max_width: Maximum width for optimization
            quality: JPEG quality for optimization (if converting)

        Returns:
            MockupUploadResult with success status and details
        """
        start_time = time.time()
        png_path = Path(png_path)

        # Validate path to prevent directory traversal
        try:
            png_path = png_path.resolve()
            # Ensure the file exists and is not a directory
            if not png_path.exists():
                raise ValueError(f"File not found: {png_path}")
            if png_path.is_dir():
                raise ValueError(f"Path is a directory, not a file: {png_path}")
            # Ensure file is within expected boundaries (optional additional check)
            # You can add checks here to ensure the path is within allowed directories
        except (ValueError, OSError) as e:
            result = MockupUploadResult(success=False, business_id=business_id)
            result.error_message = f"Invalid file path: {str(e)}"
            return result

        result = MockupUploadResult(success=False, business_id=business_id)

        try:
            # Validate input
            validation_error = self._validate_input(png_path, business_id)
            if validation_error:
                result.error_message = validation_error
                logger.error(f"Input validation failed: {validation_error}")
                return result

            # Validate and potentially optimize image
            processed_image_path = self._process_image(
                png_path, optimize, max_width, quality
            )

            # Generate metadata
            metadata = self._generate_metadata(
                processed_image_path, business_id, mockup_type
            )

            # Attempt upload with retry logic
            upload_result = self._upload_with_retry(
                processed_image_path, business_id, mockup_type, metadata
            )

            if upload_result["success"]:
                # Generate CDN URL
                cdn_url = self._generate_cdn_url(upload_result["storage_path"])

                # Link to business in database
                linking_success = self._link_to_business(
                    business_id, upload_result["storage_path"], cdn_url, metadata
                )

                if linking_success:
                    result.success = True
                    result.storage_path = upload_result["storage_path"]
                    result.cdn_url = cdn_url
                    result.file_size = upload_result["file_size"]
                    result.retry_count = upload_result["retry_count"]

                    logger.info(
                        f"Successfully uploaded mockup for business {business_id}: {cdn_url}"
                    )
                else:
                    # Upload succeeded but database linking failed
                    # Clean up the uploaded file
                    self._cleanup_orphaned_file(upload_result["storage_path"])
                    result.error_message = (
                        "Failed to link mockup to business in database"
                    )
            else:
                result.error_message = upload_result["error"]
                result.retry_count = upload_result["retry_count"]

            # Clean up processed image if it's different from original
            if processed_image_path != png_path:
                processed_image_path.unlink(missing_ok=True)

        except Exception as e:
            result.error_message = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error uploading mockup: {e}", exc_info=True)

        result.upload_duration = time.time() - start_time
        return result

    def _validate_input(self, png_path: Path, business_id: int) -> Optional[str]:
        """Validate input parameters."""
        if not png_path.exists():
            return f"File not found: {png_path}"

        if png_path.stat().st_size == 0:
            return f"File is empty: {png_path}"

        if png_path.stat().st_size > self.max_file_size:
            return f"File too large: {png_path.stat().st_size} bytes (max: {self.max_file_size})"

        if business_id <= 0:
            return f"Invalid business_id: {business_id}"

        # Check if business exists
        try:
            business = self.storage.get_business(business_id)
            if not business:
                return f"Business not found: {business_id}"
        except Exception as e:
            return f"Error validating business: {e}"

        return None

    def _process_image(
        self, image_path: Path, optimize: bool, max_width: int, quality: int
    ) -> Path:
        """Process and potentially optimize the image."""
        if not optimize:
            return image_path

        try:
            with Image.open(image_path) as img:
                # Validate format
                if img.format not in self.supported_formats:
                    raise ValueError(f"Unsupported format: {img.format}")

                original_size = img.size

                # Check if optimization is needed
                needs_resize = img.width > max_width
                needs_format_conversion = img.format != "PNG" or img.mode != "RGBA"

                if not needs_resize and not needs_format_conversion:
                    logger.info(f"Image already optimal: {image_path}")
                    return image_path

                # Create optimized version
                optimized_img = img.copy()

                # Resize if needed
                if needs_resize:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    optimized_img = optimized_img.resize(
                        (max_width, new_height), Image.Resampling.LANCZOS
                    )
                    logger.info(
                        f"Resized image from {original_size} to {optimized_img.size}"
                    )

                # Convert to PNG with RGBA mode for transparency support
                if optimized_img.mode != "RGBA":
                    optimized_img = optimized_img.convert("RGBA")

                # Save optimized version
                optimized_path = image_path.parent / f"{image_path.stem}_optimized.png"
                optimized_img.save(optimized_path, "PNG", optimize=True)

                logger.info(f"Optimized image saved: {optimized_path}")
                return optimized_path

        except Exception as e:
            logger.warning(f"Image optimization failed, using original: {e}")
            return image_path

    def _generate_metadata(
        self, image_path: Path, business_id: int, mockup_type: str
    ) -> MockupImageMetadata:
        """Generate comprehensive metadata for the mockup image."""
        try:
            with Image.open(image_path) as img:
                dimensions = img.size
                file_size = image_path.stat().st_size

                # Calculate quality score based on resolution and file size
                pixel_count = dimensions[0] * dimensions[1]
                bytes_per_pixel = file_size / pixel_count if pixel_count > 0 else 0
                quality_score = min(
                    1.0, bytes_per_pixel / 3.0
                )  # Rough quality estimation

                return MockupImageMetadata(
                    business_id=business_id,
                    mockup_type=mockup_type,
                    generated_at=datetime.utcnow(),
                    original_dimensions=dimensions,
                    optimized_dimensions=dimensions,
                    file_size_bytes=file_size,
                    quality_score=quality_score,
                )

        except Exception as e:
            logger.error(f"Error generating metadata: {e}")
            # Return basic metadata
            return MockupImageMetadata(
                business_id=business_id,
                mockup_type=mockup_type,
                generated_at=datetime.utcnow(),
                original_dimensions=(0, 0),
                optimized_dimensions=(0, 0),
                file_size_bytes=image_path.stat().st_size if image_path.exists() else 0,
            )

    def _upload_with_retry(
        self,
        image_path: Path,
        business_id: int,
        mockup_type: str,
        metadata: MockupImageMetadata,
    ) -> Dict[str, Any]:
        """Upload with exponential backoff retry logic."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                # Generate unique storage path
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                file_hash = self._calculate_file_hash(image_path)
                storage_path = f"mockups/{business_id}/{mockup_type}_{timestamp}_{file_hash[:8]}.png"

                # Prepare Supabase metadata
                supabase_metadata = {
                    "business_id": str(business_id),
                    "mockup_type": mockup_type,
                    "generated_at": metadata.generated_at.isoformat(),
                    "dimensions": f"{metadata.optimized_dimensions[0]}x{metadata.optimized_dimensions[1]}",
                    "file_size": str(metadata.file_size_bytes),
                    "quality_score": str(metadata.quality_score or 0),
                    "upload_attempt": str(attempt + 1),
                }

                # Attempt upload
                upload_result = self.supabase_storage.upload_file(
                    file_path=image_path,
                    storage_path=storage_path,
                    content_type="image/png",
                    metadata=supabase_metadata,
                )

                logger.info(
                    f"Upload successful on attempt {attempt + 1}: {storage_path}"
                )

                return {
                    "success": True,
                    "storage_path": storage_path,
                    "file_size": metadata.file_size_bytes,
                    "retry_count": attempt,
                }

            except Exception as e:
                last_error = e
                logger.warning(f"Upload attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries:
                    # Exponential backoff with jitter
                    delay = self.retry_delay_base * (2**attempt) + (time.time() % 1)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All upload attempts failed for business {business_id}"
                    )

        return {
            "success": False,
            "error": f"Upload failed after {self.max_retries + 1} attempts: {last_error}",
            "retry_count": self.max_retries + 1,
        }

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file for uniqueness."""
        hash_sha256 = hashlib.sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _generate_cdn_url(self, storage_path: str, expires_hours: int = 24) -> str:
        """Generate CDN URL with appropriate expiration."""
        try:
            url_result = self.supabase_storage.generate_secure_report_url(
                storage_path, expires_hours
            )
            return url_result["signed_url"]
        except Exception as e:
            logger.error(f"Failed to generate CDN URL: {e}")
            # Fallback to basic signed URL
            try:
                return self.supabase_storage.generate_signed_url(
                    storage_path, expires_hours * 3600
                )
            except Exception as e2:
                logger.error(f"Failed to generate fallback URL: {e2}")
                return ""

    def _link_to_business(
        self,
        business_id: int,
        storage_path: str,
        cdn_url: str,
        metadata: MockupImageMetadata,
    ) -> bool:
        """Link the uploaded mockup to the business in the database."""
        try:
            # Create asset record
            success = self.storage.create_asset(
                business_id=business_id,
                asset_type="mockup",
                file_path=storage_path,
                url=cdn_url,
                metadata={
                    "mockup_type": metadata.mockup_type,
                    "dimensions": f"{metadata.optimized_dimensions[0]}x{metadata.optimized_dimensions[1]}",
                    "file_size": metadata.file_size_bytes,
                    "quality_score": metadata.quality_score,
                    "generated_at": metadata.generated_at.isoformat(),
                },
            )

            if success:
                logger.info(f"Successfully linked mockup to business {business_id}")
                return True
            else:
                logger.error(
                    f"Failed to create asset record for business {business_id}"
                )
                return False

        except Exception as e:
            logger.error(f"Error linking mockup to business {business_id}: {e}")
            return False

    def _cleanup_orphaned_file(self, storage_path: str) -> bool:
        """Clean up orphaned file from storage."""
        try:
            success = self.supabase_storage.delete_file(storage_path)
            if success:
                logger.info(f"Cleaned up orphaned file: {storage_path}")
            return success
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned file {storage_path}: {e}")
            return False

    def cleanup_orphaned_images(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """
        Clean up orphaned mockup images that aren't linked to any business.

        Args:
            max_age_hours: Maximum age of orphaned files to clean up

        Returns:
            Dict with cleanup statistics
        """
        cleanup_stats = {
            "files_checked": 0,
            "orphaned_files_found": 0,
            "files_deleted": 0,
            "errors": [],
        }

        try:
            # Get all mockup files from Supabase
            mockup_files = self.supabase_storage.list_files(
                prefix="mockups/", limit=1000
            )
            cleanup_stats["files_checked"] = len(mockup_files)

            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

            for file_info in mockup_files:
                try:
                    file_name = file_info.get("name", "")
                    storage_path = f"mockups/{file_name}"

                    # Check if file is old enough for cleanup
                    created_at_str = file_info.get("created_at", "")
                    if created_at_str:
                        created_at = datetime.fromisoformat(
                            created_at_str.replace("Z", "+00:00")
                        )
                        if created_at > cutoff_time:
                            continue  # Skip recent files

                    # Check if file is linked to any business
                    is_linked = self._check_file_linked_to_business(storage_path)

                    if not is_linked:
                        cleanup_stats["orphaned_files_found"] += 1

                        # Delete orphaned file
                        if self._cleanup_orphaned_file(storage_path):
                            cleanup_stats["files_deleted"] += 1
                        else:
                            cleanup_stats["errors"].append(
                                f"Failed to delete {storage_path}"
                            )

                except Exception as e:
                    cleanup_stats["errors"].append(f"Error processing {file_info}: {e}")

            logger.info(
                f"Cleanup completed: {cleanup_stats['files_deleted']} orphaned files deleted"
            )

        except Exception as e:
            cleanup_stats["errors"].append(f"Cleanup process error: {e}")
            logger.error(f"Error during orphaned image cleanup: {e}")

        return cleanup_stats

    def _check_file_linked_to_business(self, storage_path: str) -> bool:
        """Check if a file is linked to any business."""
        try:
            # Query database for assets with this storage path
            # This would depend on the exact storage interface implementation
            # For now, we'll implement a basic check
            linked_assets = self.storage.get_assets_by_path(storage_path)
            return len(linked_assets) > 0
        except Exception as e:
            logger.warning(f"Error checking file linkage for {storage_path}: {e}")
            # In case of error, assume it's linked to avoid accidental deletion
            return True

    def get_business_mockups(self, business_id: int) -> List[Dict[str, Any]]:
        """Get all mockup images for a specific business."""
        try:
            assets = self.storage.get_business_assets(business_id, asset_type="mockup")

            mockup_list = []
            for asset in assets:
                # Refresh CDN URL if needed
                if asset.get("url") and self._is_url_expired(asset.get("created_at")):
                    fresh_url = self._generate_cdn_url(asset["file_path"])
                    asset["url"] = fresh_url
                    # Update in database
                    self.storage.update_asset_url(asset["id"], fresh_url)

                mockup_list.append(asset)

            return mockup_list

        except Exception as e:
            logger.error(f"Error getting mockups for business {business_id}: {e}")
            return []

    def _is_url_expired(self, created_at_str: str, expiry_hours: int = 20) -> bool:
        """Check if a CDN URL is likely expired."""
        try:
            created_at = datetime.fromisoformat(created_at_str)
            expiry_time = created_at + timedelta(hours=expiry_hours)
            return datetime.utcnow() > expiry_time
        except Exception:
            # If we can't parse the date, assume it's expired
            return True


# Global instance
mockup_uploader = MockupPNGUploader()


def upload_business_mockup(
    png_path: Union[str, Path], business_id: int, mockup_type: str = "homepage"
) -> MockupUploadResult:
    """
    Convenience function to upload a business mockup.

    Args:
        png_path: Path to the PNG file
        business_id: ID of the business
        mockup_type: Type of mockup

    Returns:
        MockupUploadResult with success status and details
    """
    return mockup_uploader.upload_mockup_png(png_path, business_id, mockup_type)


def cleanup_orphaned_mockups(max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Convenience function to clean up orphaned mockup images.

    Args:
        max_age_hours: Maximum age of orphaned files to clean up

    Returns:
        Dict with cleanup statistics
    """
    return mockup_uploader.cleanup_orphaned_images(max_age_hours)


if __name__ == "__main__":
    # Example usage and testing
    import tempfile

    from PIL import Image

    # Create a test PNG image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        test_image = Image.new("RGBA", (800, 600), (255, 0, 0, 128))
        test_image.save(tmp_file.name, "PNG")

        # Test upload (this would require valid business_id and Supabase config)
        print(f"Test image created at: {tmp_file.name}")
        print("To test upload, call: upload_business_mockup(png_path, business_id)")

        # Clean up test file
        Path(tmp_file.name).unlink()
