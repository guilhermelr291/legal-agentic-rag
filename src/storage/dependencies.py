"""Storage domain dependencies."""

from typing import Annotated

from fastapi import Depends

from src.storage.service import StorageService


async def get_storage_service() -> StorageService:
    """Factory dependency for StorageService."""
    return await StorageService.from_service_role()


StorageDep = Annotated[StorageService, Depends(get_storage_service)]
