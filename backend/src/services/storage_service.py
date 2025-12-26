"""Storage service for evidence file management with presigned URLs."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from botocore.exceptions import ClientError

from src.core.storage import get_storage_client


class StorageService:
    """Service for managing evidence file storage with presigned URLs.

    Handles presigned URL generation for upload/download and checksum computation.
    Uses existing StorageClient for actual S3/MinIO operations.
    """

    def __init__(self) -> None:
        """Initialize storage service."""
        self.client = get_storage_client()

    def _generate_evidence_path(
        self,
        org_id: UUID,
        filename: str,
    ) -> tuple[str, str]:
        """Generate storage path for evidence file.

        Args:
            org_id: Organization ID
            filename: Original filename

        Returns:
            Tuple of (storage_uri, extension)
            Format: evidence/{org_id}/{yyyy}/{mm}/{uuid}.{ext}
        """
        now = datetime.now(timezone.utc)
        file_id = uuid4()

        # Extract extension
        extension = "bin"
        if "." in filename:
            extension = filename.rsplit(".", 1)[1].lower()

        storage_uri = f"evidence/{org_id}/{now.year}/{now.month:02d}/{file_id}.{extension}"
        return storage_uri, extension

    def generate_upload_url(
        self,
        org_id: UUID,
        filename: str,
        mime_type: str,
        expires_in: int = 3600,
    ) -> tuple[str, str]:
        """Generate presigned URL for uploading a file.

        Args:
            org_id: Organization ID
            filename: Original filename
            mime_type: MIME type of the file
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Tuple of (presigned_upload_url, storage_uri)

        Raises:
            ClientError: If URL generation fails
        """
        storage_uri, _ = self._generate_evidence_path(org_id, filename)

        # Generate presigned POST URL for upload
        presigned_url = self.client._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.client._bucket,
                "Key": storage_uri,
                "ContentType": mime_type,
            },
            ExpiresIn=expires_in,
        )

        return presigned_url, storage_uri

    def generate_download_url(
        self,
        storage_uri: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate presigned URL for downloading a file.

        Args:
            storage_uri: Storage path of the file
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned download URL

        Raises:
            ClientError: If URL generation fails
        """
        return self.client.get_presigned_url(storage_uri, expires_in)

    def compute_checksum(self, storage_uri: str) -> str:
        """Compute SHA-256 checksum of a file in storage.

        Args:
            storage_uri: Storage path of the file

        Returns:
            SHA-256 hash as hex string

        Raises:
            ClientError: If file retrieval fails
        """
        # Download file content
        response = self.client._client.get_object(
            Bucket=self.client._bucket,
            Key=storage_uri,
        )

        # Compute checksum
        content = response["Body"].read()
        checksum = hashlib.sha256(content).hexdigest()

        return checksum

    def get_file_metadata(self, storage_uri: str) -> dict:
        """Get file metadata from storage.

        Args:
            storage_uri: Storage path of the file

        Returns:
            Dict with file metadata (size, content_type, checksum)

        Raises:
            ClientError: If file not found
        """
        response = self.client._client.head_object(
            Bucket=self.client._bucket,
            Key=storage_uri,
        )

        return {
            "file_size": response["ContentLength"],
            "mime_type": response.get("ContentType", "application/octet-stream"),
            "checksum_sha256": response.get("Metadata", {}).get("checksum-sha256", ""),
        }

    def file_exists(self, storage_uri: str) -> bool:
        """Check if file exists in storage.

        Args:
            storage_uri: Storage path of the file

        Returns:
            True if file exists, False otherwise
        """
        return self.client.file_exists(storage_uri)

    def delete_file(self, storage_uri: str) -> bool:
        """Delete file from storage.

        Args:
            storage_uri: Storage path of the file

        Returns:
            True if deleted successfully

        Raises:
            ClientError: If deletion fails
        """
        return self.client.delete_file(storage_uri)


# Singleton instance
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get storage service singleton instance.

    Returns:
        StorageService instance
    """
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
