"""Storage service implementation for S3-compatible storage.

Provides file upload, download, deletion, presigned URLs, and deduplication
via SHA-256 hashing.  All S3 operations include:

- Structured logging on every error path.
- Automatic retry (with exponential backoff) for transient S3 errors
  (5xx, ``SlowDown``, ``RequestTimeout``).
- Translation of ``ClientError`` to domain exceptions (``RuntimeError``,
  ``FileNotFoundError``).
"""

import hashlib
import logging
import mimetypes
import time
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings

logger = logging.getLogger(__name__)

# S3 error codes considered transient (safe to retry)
_TRANSIENT_S3_CODES = frozenset({
    "InternalError",
    "ServiceUnavailable",
    "SlowDown",
    "RequestTimeout",
    "RequestTimeTooSkewed",
})

# Default retry configuration
_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 1.0


class StorageService:
    """
    Service for storing and retrieving files from S3.
    
    Handles file uploads, downloads, and deletion from S3-compatible storage.
    Supports both AWS S3 and LocalStack for development.
    """

    def __init__(self, settings: Settings):
        """
        Initialize the storage service.
        
        Args:
            settings: Application settings containing AWS and S3 configuration
        """
        self.settings = settings
        self.bucket_name = settings.s3_bucket_name
        
        # Initialize S3 client
        session = boto3.Session(
            profile_name=settings.aws_profile,
            region_name=settings.aws_region
        )
        client_kwargs: dict = {}
        if settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url
        self.s3_client = session.client("s3", **client_kwargs)

    # ------------------------------------------------------------------
    # Retry helper
    # ------------------------------------------------------------------

    @staticmethod
    def _is_transient(exc: ClientError) -> bool:
        """Return *True* if the S3 error is transient and safe to retry."""
        code = exc.response["Error"].get("Code", "")
        http_status = exc.response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode", 0,
        )
        return code in _TRANSIENT_S3_CODES or http_status >= 500

    def _retry_s3(self, operation, *args, **kwargs):
        """Execute *operation* with exponential-backoff retry on transient
        S3 errors.

        Returns the result of the operation on success.

        Raises:
            ClientError: on permanent S3 errors or after max retries.
        """
        last_exc: ClientError | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return operation(*args, **kwargs)
            except ClientError as exc:
                last_exc = exc
                if not self._is_transient(exc) or attempt == _MAX_RETRIES - 1:
                    raise
                delay = _INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                logger.warning(
                    "Transient S3 error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc.response["Error"].get("Code", ""),
                    delay,
                )
                time.sleep(delay)
        # Should never reach here, but satisfy the type checker
        assert last_exc is not None
        raise last_exc  # pragma: no cover

    def compute_file_hash(self, file: BinaryIO) -> str:
        """
        Compute SHA-256 hash of a file for deduplication.
        
        Args:
            file: Binary file object
            
        Returns:
            Hexadecimal string of the file's SHA-256 hash
        """
        sha256_hash = hashlib.sha256()
        
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: file.read(4096), b""):
            sha256_hash.update(byte_block)
        
        # Reset file pointer to beginning
        file.seek(0)
        
        return sha256_hash.hexdigest()

    def upload_file(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str | None = None
    ) -> tuple[str, str]:
        """
        Upload a file to S3 storage.
        
        Args:
            file: Binary file object to upload
            filename: Original filename
            content_type: MIME type of the file (auto-detected if not provided)
            
        Returns:
            Tuple of (file_hash, s3_key)
            
        Raises:
            ClientError: If S3 upload fails
        """
        # Compute file hash for deduplication
        file_hash = self.compute_file_hash(file)
        
        # Generate S3 key using hash (ensures uniqueness and deduplication)
        file_extension = Path(filename).suffix
        s3_key = f"documents/{file_hash}{file_extension}"
        
        # Auto-detect content type if not provided
        if content_type is None:
            content_type, _ = mimetypes.guess_type(filename)
            if content_type is None:
                content_type = "application/octet-stream"
        
        # Upload to S3
        extra_args = {
            "ContentType": content_type,
            "Metadata": {
                "original_filename": filename,
                "file_hash": file_hash
            }
        }
        
        try:
            self._retry_s3(
                self.s3_client.upload_fileobj,
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args,
            )
        except ClientError as e:
            logger.error(
                "S3 upload failed for %s (bucket=%s): %s",
                s3_key, self.bucket_name, e,
            )
            raise RuntimeError(f"Failed to upload file to S3: {e}") from e
        
        return file_hash, s3_key

    def download_file(self, s3_key: str) -> bytes:
        """
        Download a file from S3 storage.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            File contents as bytes
            
        Raises:
            ClientError: If S3 download fails or file doesn't exist
        """
        try:
            response = self._retry_s3(
                self.s3_client.get_object,
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning("S3 file not found: %s", s3_key)
                raise FileNotFoundError(f"File not found in S3: {s3_key}") from e
            logger.error("S3 download failed for %s: %s", s3_key, e)
            raise RuntimeError(f"Failed to download file from S3: {e}") from e

    def delete_file(self, s3_key: str) -> None:
        """
        Delete a file from S3 storage.
        
        Args:
            s3_key: S3 object key
            
        Raises:
            ClientError: If S3 deletion fails
        """
        try:
            self._retry_s3(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=s3_key,
            )
        except ClientError as e:
            logger.error("S3 delete failed for %s: %s", s3_key, e)
            raise RuntimeError(f"Failed to delete file from S3: {e}") from e

    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate a presigned URL for temporary file access.
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string
            
        Raises:
            ClientError: If presigned URL generation fails
        """
        try:
            url = self._retry_s3(
                self.s3_client.generate_presigned_url,
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": s3_key,
                },
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            logger.error("S3 presigned URL generation failed for %s: %s", s3_key, e)
            raise RuntimeError(f"Failed to generate presigned URL: {e}") from e

    def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3 storage.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self._retry_s3(
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.error("S3 head_object failed for %s: %s", s3_key, e)
            raise RuntimeError(f"Failed to check file existence: {e}") from e

    def get_file_size(self, s3_key: str) -> int:
        """
        Get the size of a file in S3 storage.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            File size in bytes
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ClientError: If S3 operation fails
        """
        try:
            response = self._retry_s3(
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return response["ContentLength"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.warning("S3 file not found (get_file_size): %s", s3_key)
                raise FileNotFoundError(f"File not found in S3: {s3_key}") from e
            logger.error("S3 head_object failed for %s: %s", s3_key, e)
            raise RuntimeError(f"Failed to get file size: {e}") from e
