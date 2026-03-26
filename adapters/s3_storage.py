"""S3StorageAdapter — future AWS S3 implementation stub."""
from __future__ import annotations

from core.ports import StoragePort


class S3StorageAdapter(StoragePort):
    """Stub for future AWS S3 storage adapter.

    Replace this with a real boto3-backed implementation when migrating
    from the PoC to cloud infrastructure. No changes to core/ are required.
    """

    def save_image(self, job_id: str, image_bytes: bytes) -> str:
        raise NotImplementedError("S3StorageAdapter is not yet implemented.")

    def load_image(self, image_path: str) -> bytes:
        raise NotImplementedError("S3StorageAdapter is not yet implemented.")
