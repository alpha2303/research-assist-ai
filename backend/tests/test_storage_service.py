"""Unit tests for S3 storage service."""

import hashlib
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.storage_service import StorageService


@pytest.fixture
def mock_s3_client():
    """Create mock S3 client."""
    return MagicMock()


@pytest.fixture
def settings():
    """Create test settings with required fields."""
    with patch("app.core.config.Settings.model_config", {"env_file": None, "env_file_encoding": "utf-8", "extra": "ignore"}):
        s = MagicMock()
        s.s3_bucket_name = "test-bucket"
        s.aws_region = "us-east-1"
        s.aws_profile = "default"
        return s


@pytest.fixture
def storage_service(mock_s3_client, settings):
    """Create storage service with mocked S3 client."""
    with patch("app.services.storage_service.boto3") as mock_boto3:
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_s3_client
        service = StorageService(settings)
        service.s3_client = mock_s3_client
        return service


class TestStorageService:
    """Test cases for StorageService."""

    def test_compute_file_hash(self, storage_service):
        """Test file hash computation."""
        test_data = b"test content for hashing"
        file_obj = BytesIO(test_data)

        file_hash = storage_service.compute_file_hash(file_obj)

        expected_hash = hashlib.sha256(test_data).hexdigest()
        assert file_hash == expected_hash
        # Verify file pointer is reset
        assert file_obj.tell() == 0

    def test_compute_file_hash_large_file(self, storage_service):
        """Test hash computation with large file (chunk-based reading)."""
        test_data = b"x" * (10 * 1024 * 1024)
        file_obj = BytesIO(test_data)

        file_hash = storage_service.compute_file_hash(file_obj)

        expected_hash = hashlib.sha256(test_data).hexdigest()
        assert file_hash == expected_hash

    def test_upload_file_success(self, storage_service, mock_s3_client):
        """Test successful file upload to S3."""
        test_data = b"test file content"
        file_obj = BytesIO(test_data)
        filename = "test-doc.pdf"

        mock_s3_client.upload_fileobj.return_value = None

        file_hash, s3_key = storage_service.upload_file(file_obj, filename)

        expected_hash = hashlib.sha256(test_data).hexdigest()
        assert file_hash == expected_hash
        assert s3_key == f"documents/{expected_hash}.pdf"
        mock_s3_client.upload_fileobj.assert_called_once()
        call_args = mock_s3_client.upload_fileobj.call_args
        assert call_args[0][1] == "test-bucket"

    def test_upload_file_with_content_type(self, storage_service, mock_s3_client):
        """Test file upload with explicit content type."""
        file_obj = BytesIO(b"content")
        filename = "doc.pdf"

        storage_service.upload_file(file_obj, filename, content_type="application/pdf")

        call_kwargs = mock_s3_client.upload_fileobj.call_args
        extra_args = call_kwargs[1].get("ExtraArgs") or call_kwargs[0][3] if len(call_kwargs[0]) > 3 else call_kwargs[1]["ExtraArgs"]
        assert extra_args["ContentType"] == "application/pdf"

    def test_upload_file_s3_error(self, storage_service, mock_s3_client):
        """Test S3 upload error handling (wrapped as RuntimeError)."""
        file_obj = BytesIO(b"content")
        filename = "doc.pdf"

        mock_s3_client.upload_fileobj.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "PutObject",
        )

        with pytest.raises(RuntimeError, match="Failed to upload file"):
            storage_service.upload_file(file_obj, filename)

    def test_download_file_success(self, storage_service, mock_s3_client):
        """Test successful file download from S3 returns bytes."""
        s3_key = "documents/test.pdf"
        test_content = b"downloaded content"

        body_mock = MagicMock()
        body_mock.read.return_value = test_content
        mock_s3_client.get_object.return_value = {"Body": body_mock}

        result = storage_service.download_file(s3_key)

        assert result == test_content
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key=s3_key
        )

    def test_download_file_not_found(self, storage_service, mock_s3_client):
        """Test download when file doesn't exist raises FileNotFoundError."""
        s3_key = "documents/nonexistent.pdf"

        mock_s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            "GetObject",
        )

        with pytest.raises(FileNotFoundError, match="File not found"):
            storage_service.download_file(s3_key)

    def test_download_file_other_error(self, storage_service, mock_s3_client):
        """Test download with non-404 error raises RuntimeError."""
        s3_key = "documents/error.pdf"

        mock_s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "GetObject",
        )

        with pytest.raises(RuntimeError, match="Failed to download"):
            storage_service.download_file(s3_key)

    def test_delete_file_success(self, storage_service, mock_s3_client):
        """Test successful file deletion from S3."""
        s3_key = "documents/to-delete.pdf"

        mock_s3_client.delete_object.return_value = {"DeleteMarker": True}

        storage_service.delete_file(s3_key)

        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key=s3_key
        )

    def test_delete_file_error(self, storage_service, mock_s3_client):
        """Test S3 delete error raises RuntimeError."""
        s3_key = "documents/doc.pdf"

        mock_s3_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "DeleteObject",
        )

        with pytest.raises(RuntimeError, match="Failed to delete"):
            storage_service.delete_file(s3_key)

    def test_generate_presigned_url_success(self, storage_service, mock_s3_client):
        """Test presigned URL generation."""
        s3_key = "documents/view.pdf"
        expiration = 3600
        expected_url = "https://test-bucket.s3.amazonaws.com/documents/view.pdf?signature=..."

        mock_s3_client.generate_presigned_url.return_value = expected_url

        url = storage_service.generate_presigned_url(s3_key, expiration)

        assert url == expected_url
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": s3_key},
            ExpiresIn=expiration,
        )

    def test_generate_presigned_url_default_expiration(self, storage_service, mock_s3_client):
        """Test presigned URL with default expiration."""
        s3_key = "documents/view.pdf"
        expected_url = "https://s3-url.com"

        mock_s3_client.generate_presigned_url.return_value = expected_url

        storage_service.generate_presigned_url(s3_key)

        call_kwargs = mock_s3_client.generate_presigned_url.call_args[1]
        assert call_kwargs["ExpiresIn"] == 3600

    def test_file_exists_true(self, storage_service, mock_s3_client):
        """Test file existence check when file exists."""
        s3_key = "documents/exists.pdf"

        mock_s3_client.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "application/pdf",
        }

        exists = storage_service.file_exists(s3_key)

        assert exists is True
        mock_s3_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key=s3_key
        )

    def test_file_exists_false(self, storage_service, mock_s3_client):
        """Test file existence check when file doesn't exist."""
        s3_key = "documents/notfound.pdf"

        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadObject",
        )

        exists = storage_service.file_exists(s3_key)

        assert exists is False

    def test_multiple_operations_sequence(self, storage_service, mock_s3_client):
        """Test sequence of multiple operations."""
        file_obj = BytesIO(b"test content")
        filename = "multi-op.pdf"

        # Upload
        storage_service.upload_file(file_obj, filename)

        # Check exists
        mock_s3_client.head_object.return_value = {"ContentLength": 12}
        exists = storage_service.file_exists("documents/some-key.pdf")
        assert exists is True

        # Generate URL
        mock_s3_client.generate_presigned_url.return_value = "https://url.com"
        url = storage_service.generate_presigned_url("documents/some-key.pdf")
        assert url == "https://url.com"

        # Delete
        storage_service.delete_file("documents/some-key.pdf")

        # Verify all operations called
        assert mock_s3_client.upload_fileobj.called
        assert mock_s3_client.head_object.called
        assert mock_s3_client.generate_presigned_url.called
        assert mock_s3_client.delete_object.called
