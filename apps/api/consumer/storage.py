"""Storage backend abstraction for test recordings.

Swap between local filesystem and S3 via the STORAGE_BACKEND env var — the
rest of the codebase only depends on the StorageBackend interface.
"""

import asyncio
import shutil
from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    """Common interface for all storage backends"""

    @abstractmethod
    async def upload(self, source: Path, key: str) -> str:
        """
        Upload a file and return a URL to access it.

        Args:
            source: Local path of the file to upload.
            key:    Destination identifier (e.g. "run-abc.webm").

        Returns:
            A URL string the frontend can use to access the file.
        """


# ---------------------------------------------------------------------------
# Local filesystem — for development
# ---------------------------------------------------------------------------

class LocalStorageBackend(StorageBackend):
    """
    Copies files into a local directory and serves them via the BE's
    /recordings static mount.

    Switch to S3StorageBackend for production by changing STORAGE_BACKEND=s3.
    """

    def __init__(self, recordings_dir: Path, base_url: str) -> None:
        self._dir = recordings_dir
        self._base_url = base_url.rstrip("/")
        self._dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, source: Path, key: str) -> str:
        dest = self._dir / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, source, dest)
        return f"{self._base_url}/recordings/{key}"


# ---------------------------------------------------------------------------
# S3 — for production (stub until credentials are available)
# ---------------------------------------------------------------------------

class S3StorageBackend(StorageBackend):
    """
    Uploads recordings to an S3 bucket.

    TODO: implement with aiobotocore once S3 credentials are available.
    Install: pip install aiobotocore
    """

    def __init__(self, bucket: str, region: str) -> None:
        self._bucket = bucket
        self._region = region

    async def upload(self, source: Path, key: str) -> str:
        # Example implementation (uncomment and adjust when ready):
        #
        # import aiobotocore.session
        # session = aiobotocore.session.get_session()
        # async with session.create_client("s3", region_name=self._region) as s3:
        #     with source.open("rb") as f:
        #         await s3.put_object(Bucket=self._bucket, Key=key, Body=f)
        # return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"
        raise NotImplementedError("S3 backend is not yet configured")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_storage_backend(
    backend: str,
    recordings_dir: Path,
    base_url: str,
    s3_bucket: str = "",
    s3_region: str = "us-east-1",
) -> StorageBackend:
    """Instantiate the correct backend based on the STORAGE_BACKEND config value"""
    if backend == "local":
        return LocalStorageBackend(recordings_dir=recordings_dir, base_url=base_url)
    if backend == "s3":
        return S3StorageBackend(bucket=s3_bucket, region=s3_region)
    raise ValueError(f"Unknown storage backend: {backend!r}. Expected 'local' or 's3'.")
