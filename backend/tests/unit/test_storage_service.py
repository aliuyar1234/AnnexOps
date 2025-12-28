"""Unit tests for storage service.

Tests SHA-256 checksum computation and presigned URL generation.
"""

import hashlib
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from src.services.storage_service import StorageService


class TestStorageService:
    """Unit tests for StorageService class."""

    @pytest.fixture
    def mock_storage_client(self):
        """Create a mock storage client."""
        mock = Mock()
        mock._bucket = "test-bucket"
        mock._client = Mock()
        return mock

    @pytest.fixture
    def storage_service(self, mock_storage_client):
        """Create a storage service with mocked client."""
        with patch(
            "src.services.storage_service.get_storage_client",
            return_value=mock_storage_client,
        ):
            service = StorageService()
            return service

    def test_generate_evidence_path_format(self, storage_service):
        """Test evidence path generation follows correct format."""
        org_id = uuid4()
        filename = "test-document.pdf"

        storage_uri, extension = storage_service._generate_evidence_path(org_id, filename)

        # Should follow format: evidence/{org_id}/{yyyy}/{mm}/{uuid}.{ext}
        assert storage_uri.startswith(f"evidence/{org_id}/")
        assert storage_uri.endswith(".pdf")
        assert extension == "pdf"

        # Verify it contains year and month
        parts = storage_uri.split("/")
        assert len(parts) == 5  # evidence, org_id, year, month, file
        assert parts[0] == "evidence"
        assert str(org_id) in storage_uri

    def test_generate_evidence_path_extracts_extension(self, storage_service):
        """Test extension extraction from filename."""
        org_id = uuid4()

        # Test various extensions
        test_cases = [
            ("document.pdf", "pdf"),
            ("spreadsheet.xlsx", "xlsx"),
            ("image.PNG", "png"),  # Should be lowercase
            ("file.tar.gz", "gz"),  # Takes last extension
            ("noextension", "bin"),  # Default to bin
        ]

        for filename, expected_ext in test_cases:
            _, extension = storage_service._generate_evidence_path(org_id, filename)
            assert extension == expected_ext

    def test_generate_upload_url_returns_tuple(self, storage_service):
        """Test generate_upload_url returns presigned URL and storage URI."""
        org_id = uuid4()
        filename = "test.pdf"
        mime_type = "application/pdf"

        # Mock the presigned URL generation
        storage_service.client._client.generate_presigned_url.return_value = (
            "https://minio.test/upload-url"
        )

        upload_url, storage_uri = storage_service.generate_upload_url(org_id, filename, mime_type)

        assert isinstance(upload_url, str)
        assert isinstance(storage_uri, str)
        assert upload_url == "https://minio.test/upload-url"
        assert storage_uri.startswith(f"evidence/{org_id}/")
        assert storage_uri.endswith(".pdf")

    def test_generate_upload_url_calls_client_correctly(self, storage_service):
        """Test generate_upload_url calls storage client with correct parameters."""
        org_id = uuid4()
        filename = "test.pdf"
        mime_type = "application/pdf"

        storage_service.client._client.generate_presigned_url.return_value = (
            "https://minio.test/upload-url"
        )

        storage_service.generate_upload_url(org_id, filename, mime_type)

        # Verify the client was called with correct parameters
        storage_service.client._client.generate_presigned_url.assert_called_once()
        call_args = storage_service.client._client.generate_presigned_url.call_args

        assert call_args[0][0] == "put_object"
        assert call_args[1]["Params"]["Bucket"] == "test-bucket"
        assert call_args[1]["Params"]["ContentType"] == mime_type
        assert "Key" in call_args[1]["Params"]
        assert call_args[1]["ExpiresIn"] == 3600

    def test_generate_download_url_delegates_to_client(self, storage_service):
        """Test generate_download_url delegates to storage client."""
        storage_uri = "evidence/org-id/2025/12/file.pdf"

        storage_service.client.get_presigned_url.return_value = "https://minio.test/download-url"

        download_url = storage_service.generate_download_url(storage_uri)

        assert download_url == "https://minio.test/download-url"
        storage_service.client.get_presigned_url.assert_called_once_with(storage_uri, 3600)

    def test_compute_checksum_returns_sha256_hash(self, storage_service):
        """Test compute_checksum returns SHA-256 hash of file content."""
        storage_uri = "evidence/org-id/2025/12/file.pdf"
        file_content = b"Test file content for checksum computation"

        # Mock the S3 response
        mock_response = {"Body": Mock()}
        mock_response["Body"].read.side_effect = [file_content, b""]
        storage_service.client._client.get_object.return_value = mock_response

        checksum = storage_service.compute_checksum(storage_uri)

        # Verify checksum matches expected SHA-256 hash
        expected_checksum = hashlib.sha256(file_content).hexdigest()
        assert checksum == expected_checksum
        assert len(checksum) == 64  # SHA-256 produces 64 hex characters

    def test_compute_checksum_calls_get_object(self, storage_service):
        """Test compute_checksum calls get_object with correct parameters."""
        storage_uri = "evidence/org-id/2025/12/file.pdf"

        mock_response = {"Body": Mock()}
        mock_response["Body"].read.side_effect = [b"content", b""]
        storage_service.client._client.get_object.return_value = mock_response

        storage_service.compute_checksum(storage_uri)

        storage_service.client._client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=storage_uri,
        )

    def test_compute_checksum_with_different_content(self, storage_service):
        """Test compute_checksum produces different hashes for different content."""
        storage_uri = "evidence/org-id/2025/12/file.pdf"

        # First call with content A
        mock_response1 = {"Body": Mock()}
        mock_response1["Body"].read.side_effect = [b"Content A", b""]
        storage_service.client._client.get_object.return_value = mock_response1
        checksum1 = storage_service.compute_checksum(storage_uri)

        # Second call with content B
        mock_response2 = {"Body": Mock()}
        mock_response2["Body"].read.side_effect = [b"Content B", b""]
        storage_service.client._client.get_object.return_value = mock_response2
        checksum2 = storage_service.compute_checksum(storage_uri)

        assert checksum1 != checksum2

    def test_get_file_metadata_returns_dict(self, storage_service):
        """Test get_file_metadata returns file metadata dict."""
        storage_uri = "evidence/org-id/2025/12/file.pdf"

        mock_response = {
            "ContentLength": 1024,
            "ContentType": "application/pdf",
            "Metadata": {"checksum-sha256": "abc123"},
        }
        storage_service.client._client.head_object.return_value = mock_response

        metadata = storage_service.get_file_metadata(storage_uri)

        assert isinstance(metadata, dict)
        assert metadata["file_size"] == 1024
        assert metadata["mime_type"] == "application/pdf"
        assert metadata["checksum_sha256"] == "abc123"

    def test_get_file_metadata_handles_missing_metadata(self, storage_service):
        """Test get_file_metadata handles missing Metadata field."""
        storage_uri = "evidence/org-id/2025/12/file.pdf"

        mock_response = {
            "ContentLength": 2048,
            "ContentType": "text/plain",
        }
        storage_service.client._client.head_object.return_value = mock_response

        metadata = storage_service.get_file_metadata(storage_uri)

        assert metadata["file_size"] == 2048
        assert metadata["mime_type"] == "text/plain"
        assert metadata["checksum_sha256"] == ""  # Empty when Metadata missing

    def test_file_exists_delegates_to_client(self, storage_service):
        """Test file_exists delegates to storage client."""
        storage_uri = "evidence/org-id/2025/12/file.pdf"

        storage_service.client.file_exists.return_value = True
        exists = storage_service.file_exists(storage_uri)

        assert exists is True
        storage_service.client.file_exists.assert_called_once_with(storage_uri)

    def test_delete_file_delegates_to_client(self, storage_service):
        """Test delete_file delegates to storage client."""
        storage_uri = "evidence/org-id/2025/12/file.pdf"

        storage_service.client.delete_file.return_value = True
        result = storage_service.delete_file(storage_uri)

        assert result is True
        storage_service.client.delete_file.assert_called_once_with(storage_uri)


class TestStorageServiceIntegration:
    """Integration tests for storage service with realistic data."""

    @pytest.fixture
    def storage_service(self):
        """Create storage service with mocked client."""
        mock_client = Mock()
        mock_client._bucket = "annexops-evidence"
        mock_client._client = Mock()

        with patch("src.services.storage_service.get_storage_client", return_value=mock_client):
            return StorageService()

    def test_full_upload_workflow(self, storage_service):
        """Test complete upload workflow from URL generation to checksum."""
        org_id = uuid4()
        filename = "risk_assessment.pdf"
        mime_type = "application/pdf"
        file_content = b"Risk assessment document content for AI system compliance"

        # Step 1: Generate upload URL
        storage_service.client._client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/upload-url"
        )

        upload_url, storage_uri = storage_service.generate_upload_url(org_id, filename, mime_type)

        assert "upload-url" in upload_url
        assert storage_uri.startswith(f"evidence/{org_id}/")

        # Step 2: Verify file exists
        storage_service.client.file_exists.return_value = True
        assert storage_service.file_exists(storage_uri) is True

        # Step 3: Get file metadata
        mock_metadata = {
            "ContentLength": len(file_content),
            "ContentType": mime_type,
            "Metadata": {},
        }
        storage_service.client._client.head_object.return_value = mock_metadata

        metadata = storage_service.get_file_metadata(storage_uri)
        assert metadata["file_size"] == len(file_content)
        assert metadata["mime_type"] == mime_type

        # Step 4: Compute checksum
        mock_response = {"Body": Mock()}
        mock_response["Body"].read.side_effect = [file_content, b""]
        storage_service.client._client.get_object.return_value = mock_response

        checksum = storage_service.compute_checksum(storage_uri)
        expected_checksum = hashlib.sha256(file_content).hexdigest()
        assert checksum == expected_checksum
