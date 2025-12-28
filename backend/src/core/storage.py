"""S3/MinIO storage client for file attachments."""
import hashlib
from typing import BinaryIO
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.core.config import get_settings


class StorageClient:
    """S3/MinIO storage client for managing file attachments.

    Handles file upload, download, and deletion operations for
    AI system attachments stored in object storage.
    """

    def __init__(self) -> None:
        """Initialize storage client with MinIO/S3 configuration."""
        settings = get_settings()

        # Determine endpoint URL based on SSL setting
        protocol = "https" if settings.minio_use_ssl else "http"
        endpoint_url = f"{protocol}://{settings.minio_endpoint}"

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = settings.minio_bucket

    def _generate_path(
        self,
        org_id: UUID,
        system_id: UUID,
        file_id: UUID,
        extension: str,
    ) -> str:
        """Generate storage path for file.

        Args:
            org_id: Organization ID
            system_id: AI System ID
            file_id: Unique file identifier
            extension: File extension (without dot)

        Returns:
            Storage path in format: attachments/{org_id}/{system_id}/{file_id}.{ext}
        """
        return f"attachments/{org_id}/{system_id}/{file_id}.{extension}"

    def upload_file(
        self,
        file: BinaryIO,
        org_id: UUID,
        system_id: UUID,
        file_id: UUID,
        extension: str,
        content_type: str,
    ) -> tuple[str, str, int]:
        """Upload file to storage.

        Args:
            file: File-like object to upload
            org_id: Organization ID
            system_id: AI System ID
            file_id: Unique file identifier
            extension: File extension (without dot)
            content_type: MIME type of the file

        Returns:
            Tuple of (storage_uri, sha256_checksum, file_size)

        Raises:
            ClientError: If upload fails
        """
        storage_path = self._generate_path(org_id, system_id, file_id, extension)

        # Compute checksum and size without loading the whole file into memory
        file.seek(0)
        checksum_hasher = hashlib.sha256()
        file_size = 0
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            checksum_hasher.update(chunk)
            file_size += len(chunk)
        checksum = checksum_hasher.hexdigest()

        # Reset file position for upload
        file.seek(0)

        self._client.put_object(
            Bucket=self._bucket,
            Key=storage_path,
            Body=file,
            ContentLength=file_size,
            ContentType=content_type,
            Metadata={
                "checksum-sha256": checksum,
            },
        )

        # Reset for potential further reads by callers
        file.seek(0)

        return storage_path, checksum, file_size

    def get_presigned_url(
        self,
        storage_uri: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate presigned download URL.

        Args:
            storage_uri: Storage path of the file
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL for downloading the file

        Raises:
            ClientError: If URL generation fails
        """
        return self._client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": storage_uri,
            },
            ExpiresIn=expires_in,
        )

    def delete_file(self, storage_uri: str) -> bool:
        """Delete file from storage.

        Args:
            storage_uri: Storage path of the file

        Returns:
            True if deleted successfully

        Raises:
            ClientError: If deletion fails
        """
        try:
            self._client.delete_object(
                Bucket=self._bucket,
                Key=storage_uri,
            )
            return True
        except ClientError:
            return False

    def file_exists(self, storage_uri: str) -> bool:
        """Check if file exists in storage.

        Args:
            storage_uri: Storage path of the file

        Returns:
            True if file exists, False otherwise
        """
        try:
            self._client.head_object(
                Bucket=self._bucket,
                Key=storage_uri,
            )
            return True
        except ClientError:
            return False


# Singleton instance
_storage_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    """Get storage client singleton instance.

    Returns:
        StorageClient instance
    """
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client
