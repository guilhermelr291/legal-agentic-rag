"""Async Supabase client wrapper with connection pooling and RLS awareness.

This module provides a high-level async interface to Supabase storage and database
operations with proper error handling and connection management.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, BinaryIO

from supabase._async.client import AsyncClient as SupabaseAsyncClient
from supabase.lib.client_options import ClientOptions

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

logger = logging.getLogger(__name__)


class SupabaseError(Exception):
    """Base exception for Supabase client errors."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class StorageError(SupabaseError):
    """Exception for storage-related errors (upload, download, delete)."""


class DatabaseError(SupabaseError):
    """Exception for database-related errors (insert, upsert, select, update)."""


@dataclass(frozen=True, slots=True)
class StorageUploadResponse:
    """Response from a storage upload operation."""

    path: str
    full_path: str | None = None


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Result from a database query operation."""

    data: list[dict[str, Any]]
    count: int | None = None


class SupabaseClient:
    """Async Supabase client wrapper with connection pooling and RLS awareness.

    This client provides:
    - Async storage operations (upload, download, delete)
    - Async database operations with automatic user_id filtering for RLS
    - Connection pooling for efficient concurrent operations
    - Comprehensive error handling for network and storage failures

    Usage:
        >>> client = await SupabaseClient.from_service_role()
        >>> await client.upload_file("documents", "user123/file.pdf", file_data)
        >>> result = await client.select("documents", user_id="user123")
    """

    def __init__(self, client: SupabaseAsyncClient) -> None:
        """Initialize with an existing Supabase async client.

        Args:
            client: Configured SupabaseAsyncClient instance.
        """
        self._client = client
        self._storage = client.storage
        self._db = client.postgrest

    @classmethod
    async def from_service_role(
        cls,
        supabase_url: str | None = None,
        supabase_service_role_key: str | None = None,
    ) -> SupabaseClient:
        """Factory method to create client from service role credentials.

        Loads credentials from settings if not provided explicitly.

        Args:
            supabase_url: Supabase project URL. If None, loaded from settings.
            supabase_service_role_key: Service role key. If None, loaded from settings.

        Returns:
            Configured SupabaseClient instance.

        Raises:
            SupabaseError: If client creation fails.
        """
        from my_agent.config.settings import get_settings

        settings = get_settings()

        url = supabase_url or settings.supabase_url
        key = supabase_service_role_key or settings.supabase_service_role_key

        if not url or not key:
            raise SupabaseError(
                "Missing Supabase credentials. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in environment."
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

            logger.debug("Supabase client initialized with service role")
            return cls(client)

        except Exception as e:
            logger.exception("Failed to create Supabase client")
            raise SupabaseError(f"Failed to create Supabase client: {e}", e) from e

    @asynccontextmanager
    async def _storage_bucket(
        self, bucket_name: str
    ) -> AsyncGenerator[Any, None]:
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
            raise StorageError(f"Storage bucket '{bucket_name}' error: {e}", e) from e

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

                logger.info(
                    "File uploaded successfully: %s/%s", bucket_name, file_path
                )

                return StorageUploadResponse(
                    path=response_data.get("path", file_path),
                    full_path=response_data.get("fullPath"),
                )

        except StorageError:
            raise
        except Exception as e:
            logger.exception("Failed to upload file: %s/%s", bucket_name, file_path)
            raise StorageError(
                f"Failed to upload file to {bucket_name}/{file_path}: {e}", e
            ) from e

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

                logger.info(
                    "File downloaded successfully: %s/%s", bucket_name, file_path
                )
                return response

        except StorageError:
            raise
        except Exception as e:
            logger.exception("Failed to download file: %s/%s", bucket_name, file_path)
            raise StorageError(
                f"Failed to download file from {bucket_name}/{file_path}: {e}", e
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
                logger.info(
                    "Deleted %d files from bucket '%s'", len(deleted), bucket_name
                )
                return deleted

        except StorageError:
            raise
        except Exception as e:
            logger.exception("Failed to delete files from bucket: %s", bucket_name)
            raise StorageError(
                f"Failed to delete files from {bucket_name}: {e}", e
            ) from e

    def _apply_rls_filter(
        self, query: Any, user_id: str | None, table_name: str
    ) -> Any:
        """Apply user_id filter for RLS awareness if provided.

        Args:
            query: PostgREST query builder.
            user_id: User ID to filter by. If None, no filter applied.
            table_name: Name of the table for logging purposes.

        Returns:
            Modified query with RLS filter applied.
        """
        if user_id:
            query = query.eq("user_id", user_id)
            logger.debug("Applied RLS filter for user_id: %s on table: %s", user_id, table_name)
        return query

    async def insert(
        self,
        table_name: str,
        data: dict[str, Any] | Sequence[dict[str, Any]],
        user_id: str | None = None,
    ) -> QueryResult:
        """Insert one or more rows into a table.

        Automatically applies user_id filter for RLS compliance when provided.

        Args:
            table_name: Name of the table to insert into.
            data: Single row or list of rows to insert.
            user_id: User ID for RLS filtering (recommended for user tables).

        Returns:
            QueryResult with inserted data.

        Raises:
            DatabaseError: If insert fails.
        """
        try:
            # Ensure user_id is set in data for RLS compliance
            if user_id:
                if isinstance(data, dict):
                    data = {**data, "user_id": user_id}
                else:
                    data = [{**row, "user_id": user_id} for row in data]

            query = self._db.table(table_name).insert(data)
            response = await query.execute()

            result_data = response.data if hasattr(response, "data") else []
            count = response.count if hasattr(response, "count") else None

            logger.debug("Inserted %d rows into %s", len(result_data), table_name)
            return QueryResult(data=result_data, count=count)

        except Exception as e:
            logger.exception("Insert failed on table: %s", table_name)
            raise DatabaseError(f"Insert failed on {table_name}: {e}", e) from e

    async def upsert(
        self,
        table_name: str,
        data: dict[str, Any] | Sequence[dict[str, Any]],
        on_conflict: str | None = None,
        user_id: str | None = None,
    ) -> QueryResult:
        """Upsert (insert or update) rows into a table.

        Automatically applies user_id filter for RLS compliance when provided.

        Args:
            table_name: Name of the table.
            data: Single row or list of rows to upsert.
            on_conflict: Column(s) to use for conflict resolution (e.g., 'id').
            user_id: User ID for RLS filtering.

        Returns:
            QueryResult with upserted data.

        Raises:
            DatabaseError: If upsert fails.
        """
        try:
            # Ensure user_id is set in data for RLS compliance
            if user_id:
                if isinstance(data, dict):
                    data = {**data, "user_id": user_id}
                else:
                    data = [{**row, "user_id": user_id} for row in data]

            query = self._db.table(table_name).upsert(
                data,
                on_conflict=on_conflict if on_conflict else "",
            )
            response = await query.execute()

            result_data = response.data if hasattr(response, "data") else []
            count = response.count if hasattr(response, "count") else None

            logger.debug("Upserted %d rows into %s", len(result_data), table_name)
            return QueryResult(data=result_data, count=count)

        except Exception as e:
            logger.exception("Upsert failed on table: %s", table_name)
            raise DatabaseError(f"Upsert failed on {table_name}: {e}", e) from e

    async def select(
        self,
        table_name: str,
        columns: str = "*",
        user_id: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: tuple[str, str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        count: str | None = None,
    ) -> QueryResult:
        """Select rows from a table with optional filtering.

        Automatically applies user_id filter for RLS compliance when provided.

        Args:
            table_name: Name of the table to query.
            columns: Comma-separated column names or '*' for all.
            user_id: User ID for RLS filtering (filters rows by user_id column).
            filters: Additional column filters as {column: value} or {column: (op, value)}.
            order_by: Tuple of (column, direction) where direction is 'asc' or 'desc'.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            count: Count option ('exact', 'planned', 'estimated') for total count.

        Returns:
            QueryResult with selected data.

        Raises:
            DatabaseError: If query fails.
        """
        try:
            query = self._db.table(table_name).select(columns, count=count)

            # Apply RLS filter first
            query = self._apply_rls_filter(query, user_id, table_name)

            # Apply additional filters
            if filters:
                for column, value in filters.items():
                    if isinstance(value, tuple) and len(value) == 2:
                        op, val = value
                        query = self._apply_filter(query, column, op, val)
                    else:
                        query = query.eq(column, value)

            if order_by:
                column, direction = order_by
                if direction.lower() == "desc":
                    query = query.order(column, desc=True)
                else:
                    query = query.order(column)

            if limit:
                query = query.limit(limit)

            if offset:
                query = query.offset(offset)

            response = await query.execute()

            result_data = response.data if hasattr(response, "data") else []
            result_count = response.count if hasattr(response, "count") else None

            logger.debug("Selected %d rows from %s", len(result_data), table_name)
            return QueryResult(data=result_data, count=result_count)

        except Exception as e:
            logger.exception("Select failed on table: %s", table_name)
            raise DatabaseError(f"Select failed on {table_name}: {e}", e) from e

    def _apply_filter(
        self, query: Any, column: str, op: str, value: Any
    ) -> Any:
        """Apply a filter operator to the query.

        Args:
            query: PostgREST query builder.
            column: Column name to filter.
            op: Operator (eq, neq, gt, gte, lt, lte, like, ilike, in, is, etc.).
            value: Value to compare against.

        Returns:
            Modified query with filter applied.
        """
        op = op.lower()

        match op:
            case "eq" | "=":
                return query.eq(column, value)
            case "neq" | "!=" | "<>":
                return query.neq(column, value)
            case "gt" | ">":
                return query.gt(column, value)
            case "gte" | ">=":
                return query.gte(column, value)
            case "lt" | "<":
                return query.lt(column, value)
            case "lte" | "<=":
                return query.lte(column, value)
            case "like":
                return query.like(column, value)
            case "ilike":
                return query.ilike(column, value)
            case "in":
                return query.in_(column, value)
            case "is":
                return query.is_(column, value)
            case _:
                # Fallback to eq for unknown operators
                logger.warning("Unknown filter operator '%s', using eq", op)
                return query.eq(column, value)

    async def update(
        self,
        table_name: str,
        data: dict[str, Any],
        user_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Update rows in a table.

        WARNING: Always provide user_id or filters to avoid updating all rows.
        Automatically applies user_id filter for RLS compliance when provided.

        Args:
            table_name: Name of the table.
            data: Data to update (key-value pairs).
            user_id: User ID for RLS filtering (required for user tables).
            filters: Additional filters to identify rows to update.

        Returns:
            QueryResult with updated data.

        Raises:
            DatabaseError: If update fails or no filters provided.
        """
        # Safety check: require some form of filtering
        if not user_id and not filters:
            raise DatabaseError(
                f"Update on {table_name} requires user_id or filters to prevent "
                "accidental full table updates."
            )

        try:
            query = self._db.table(table_name).update(data)

            # Apply RLS filter
            query = self._apply_rls_filter(query, user_id, table_name)

            # Apply additional filters
            if filters:
                for column, value in filters.items():
                    if isinstance(value, tuple) and len(value) == 2:
                        op, val = value
                        query = self._apply_filter(query, column, op, val)
                    else:
                        query = query.eq(column, value)

            response = await query.execute()

            result_data = response.data if hasattr(response, "data") else []
            count = response.count if hasattr(response, "count") else None

            logger.debug("Updated %d rows in %s", len(result_data), table_name)
            return QueryResult(data=result_data, count=count)

        except Exception as e:
            logger.exception("Update failed on table: %s", table_name)
            raise DatabaseError(f"Update failed on {table_name}: {e}", e) from e

    async def delete(
        self,
        table_name: str,
        user_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Delete rows from a table.

        WARNING: Always provide user_id or filters to avoid deleting all rows.
        Automatically applies user_id filter for RLS compliance when provided.

        Args:
            table_name: Name of the table.
            user_id: User ID for RLS filtering (required for user tables).
            filters: Additional filters to identify rows to delete.

        Returns:
            QueryResult with deleted data.

        Raises:
            DatabaseError: If delete fails or no filters provided.
        """
        # Safety check: require some form of filtering
        if not user_id and not filters:
            raise DatabaseError(
                f"Delete on {table_name} requires user_id or filters to prevent "
                "accidental full table deletion."
            )

        try:
            query = self._db.table(table_name).delete()

            # Apply RLS filter
            query = self._apply_rls_filter(query, user_id, table_name)

            # Apply additional filters
            if filters:
                for column, value in filters.items():
                    if isinstance(value, tuple) and len(value) == 2:
                        op, val = value
                        query = self._apply_filter(query, column, op, val)
                    else:
                        query = query.eq(column, value)

            response = await query.execute()

            result_data = response.data if hasattr(response, "data") else []
            count = response.count if hasattr(response, "count") else None

            logger.debug("Deleted %d rows from %s", len(result_data), table_name)
            return QueryResult(data=result_data, count=count)

        except Exception as e:
            logger.exception("Delete failed on table: %s", table_name)
            raise DatabaseError(f"Delete failed on {table_name}: {e}", e) from e

    async def rpc(
        self,
        function_name: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call a PostgreSQL stored procedure (RPC).

        Args:
            function_name: Name of the PostgreSQL function to call.
            params: Parameters to pass to the function.

        Returns:
            Result from the RPC call.

        Raises:
            DatabaseError: If RPC call fails.
        """
        try:
            query = self._db.rpc(function_name, params or {})
            response = await query.execute()
            return response.data if hasattr(response, "data") else response

        except Exception as e:
            logger.exception("RPC call failed: %s", function_name)
            raise DatabaseError(f"RPC call '{function_name}' failed: {e}", e) from e


__all__ = [
    "SupabaseClient",
    "SupabaseError",
    "StorageError",
    "DatabaseError",
    "StorageUploadResponse",
    "QueryResult",
]
