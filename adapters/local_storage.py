"""Filesystem-backed StoragePort implementation."""

from pathlib import Path

from core.ports import StoragePort


class LocalStorageAdapter(StoragePort):
    """StoragePort implementation that persists image bytes to the local filesystem.

    Files are stored under a configurable base directory, one file per job,
    named by job_id. Suitable for PoC and single-node deployments only.
    """

    def __init__(self, base_dir: str = "/temp_images") -> None:
        """Initialize the adapter with a base directory for image storage.

        Args:
            base_dir: Absolute or relative path to the root directory where
                image files will be stored. Defaults to ``/temp_images``.
        """
        self._base_dir = Path(base_dir)

    def save_image(self, job_id: str, image_bytes: bytes) -> str:
        """Persist raw image bytes to disk under the base directory.

        Creates the base directory (and any parents) if it does not exist.
        The file is named after ``job_id`` with no extension.

        Args:
            job_id: Unique identifier for the job; used as the filename.
            image_bytes: Raw binary content of the image to persist.

        Returns:
            Absolute string path to the saved file, suitable for passing
            to ``load_image``.
        """
        self._base_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._base_dir / job_id
        file_path.write_bytes(image_bytes)
        return str(file_path)

    def load_image(self, image_path: str) -> bytes:
        """Load raw image bytes from a previously saved file path.

        Args:
            image_path: Filesystem path returned by a prior ``save_image`` call.

        Returns:
            Raw binary content of the image file.

        Raises:
            FileNotFoundError: If no file exists at ``image_path``.
        """
        return Path(image_path).read_bytes()
