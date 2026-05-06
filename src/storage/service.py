"""Storage service for Supabase file operations."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, BinaryIO

from src.common.exceptions import StorageError
from src.storage.config import storage_settings

try:
    from supabase._async.client import AsyncClient as SupabaseAsyncClient
except ImportError:
    # Fallback for different supabase-py versions
    from supabase.client import AsyncClient as SupabaseAsyncClient

try:
    from supabase.lib.client_options import ClientOptions
except ImportError:
    from supabase.lib.options import ClientOptions

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StorageUploadResponse:
    """Response from a storage upload operation."""

    path: str
    full_path: str | None = None


class StorageService:
    """Async Supabase storage service with connection pooling.

    This service provides:
    - Async storage operations (upload, download, delete, get_public_url)
    - Connection pooling for efficient concurrent operations
    - Comprehensive error handling for network and storage failures

    Usage:
        >>> service = await StorageService.from_service_role()
        >>> await service.upload_file("documents", "user123/file.pdf", file_data)
        >>> url = await service.get_public_url("documents", "user123/file.pdf")
    """

    def __init__(self, client: SupabaseAsyncClient) -> None:
        """Initialize with an existing Supabase async client.

        Args:
            client: Configured SupabaseAsyncClient instance.
        """
        self._client = client
        self._storage = client.storage

    @classmethod
    async def from_service_role(
        cls,
        supabase_url: str | None = None,
        supabase_service_key: str | None = None,
    ) -> StorageService:
        """Factory method to create service from service role credentials.

        Loads credentials from settings if not provided explicitly.

        Args:
            supabase_url: Supabase project URL. If None, loaded from settings.
            supabase_service_key: Service role key. If None, loaded from settings.

        Returns:
            Configured StorageService instance.

        Raises:
            StorageError: If client creation fails.
        """
        url = supabase_url or storage_settings.SUPABASE_URL
        key = supabase_service_key or storage_settings.SUPABASE_SERVICE_KEY

        if not url or not key:
            raise StorageError(
                "Missing Supabase credentials. "
                "Set STORAGE_SUPABASE_URL and STORAGE_SUPABASE_SERVICE_KEY in environment."
            )

        try:
            # Configure client options with connection pooling
            options = ClientOptions(
                postgrest_client_timeout=30,
                storage_client_timeout=60,
                schema="public",
            )

            client = await SupabaseAsyncClient.create(
                supabase_url=url,
                supabase_key=key,
                options=options,
            )

            logger.debug("StorageService initialized with service role")
            return cls(client)

        except Exception as e:
            logger.exception("Failed to create StorageService client")
            raise StorageError(f"Failed to create StorageService client: {e}") from e

    @asynccontextmanager
    async def _storage_bucket(self, bucket_name: str) -> AsyncGenerator[Any, None]:
        """Context manager for accessing a storage bucket safely.

        Args:
            bucket_name: Name of the storage bucket.

        Yields:
            Storage bucket interface.

        Raises:
            StorageError: If bucket access fails.
        """
        try:
            bucket = self._storage.from_(bucket_name)
            yield bucket
        except Exception as e:
            logger.exception("Storage bucket operation failed: %s", bucket_name)
            raise StorageError(f"Storage bucket '{bucket_name}' error: {e}") from e

    async def upload_file(
        self,
        bucket_name: str,
        file_path: str,
        file_data: BinaryIO | bytes | str,
        content_type: str | None = None,
        upsert: bool = False,
    ) -> StorageUploadResponse:
        """Upload a file to Supabase Storage.

        Args:
            bucket_name: Storage bucket name (e.g., 'documents').
            file_path: Path within the bucket (e.g., 'user123/file.pdf').
            file_data: File content as bytes, string, or binary stream.
            content_type: MIME type of the file. Auto-detected if not provided.
            upsert: If True, overwrite existing file at the same path.

        Returns:
            StorageUploadResponse with the stored path information.

        Raises:
            StorageError: If upload fails due to network or permission issues.
        """
        file_options: dict[str, Any] = {"upsert": upsert}
        if content_type:
            file_options["content-type"] = content_type

        try:
            async with self._storage_bucket(bucket_name) as bucket:
                response = await bucket.upload(
                    path=file_path,
                    file=file_data,
                    file_options=file_options if file_options else None,
                )

                # Response is a Response object from httpx
                response_data = response.json()

                logger.info("File uploaded successfully: %s/%s", bucket_name, file_path)

                return StorageUploadResponse(
                    path=response_data.get("path", file_path),
                    full_path=response_data.get("fullPath"),
                )

        except StorageError:
            raise
        except Exception as e:
            logger.exception("Failed to upload file: %s/%s", bucket_name, file_path)
            raise StorageError(f"Failed to upload file to {bucket_name}/{file_path}: {e}") from e

    async def download_file(
        self,
        bucket_name: str,
        file_path: str,
    ) -> bytes:
        """Download a file from Supabase Storage.

        Args:
            bucket_name: Storage bucket name.
            file_path: Path to the file within the bucket.

        Returns:
            File content as bytes.

        Raises:
            StorageError: If download fails or file not found.
        """
        try:
            async with self._storage_bucket(bucket_name) as bucket:
                response = await bucket.download(path=file_path)

                logger.info("File downloaded successfully: %s/%s", bucket_name, file_path)
                return response

        except StorageError:
            raise
        except Exception as e:
            logger.exception("Failed to download file: %s/%s", bucket_name, file_path)
            raise StorageError(
                f"Failed to download file from {bucket_name}/{file_path}: {e}"
            ) from e

    async def delete_file(
        self,
        bucket_name: str,
        file_paths: str | Sequence[str],
    ) -> list[str]:
        """Delete one or more files from Supabase Storage.

        Args:
            bucket_name: Storage bucket name.
            file_paths: Single path or list of paths to delete.

        Returns:
            List of successfully deleted file paths.

        Raises:
            StorageError: If deletion fails.
        """
        paths = [file_paths] if isinstance(file_paths, str) else list(file_paths)

        try:
            async with self._storage_bucket(bucket_name) as bucket:
                response = await bucket.remove(paths)
                response_data = response.json() if hasattr(response, "json") else {}

                deleted = response_data if isinstance(response_data, list) else paths
                logger.info("Deleted %d files from bucket '%s'", len(deleted), bucket_name)
                return deleted

        except StorageError:
            raise
        except Exception as e:
            logger.exception("Failed to delete files from bucket: %s", bucket_name)
            raise StorageError(f"Failed to delete files from {bucket_name}: {e}") from e

    def get_public_url(
        self,
        bucket_name: str,
        file_path: str,
    ) -> str:
        """Get the public URL for a file in Supabase Storage.

        Args:
            bucket_name: Storage bucket name.
            file_path: Path to the file within the bucket.

        Returns:
            Public URL string for accessing the file.

        Raises:
            StorageError: If URL generation fails.
        """
        try:
            bucket = self._storage.from_(bucket_name)
            url = bucket.get_public_url(file_path)

            logger.debug("Generated public URL for %s/%s", bucket_name, file_path)
            return url

        except Exception as e:
            logger.exception("Failed to generate public URL: %s/%s", bucket_name, file_path)
            raise StorageError(
                f"Failed to generate public URL for {bucket_name}/{file_path}: {e}"
            ) from e


__all__ = [
    "StorageService",
    "StorageUploadResponse",
]
