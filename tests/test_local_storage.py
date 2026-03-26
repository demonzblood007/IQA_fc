"""Unit tests for LocalStorageAdapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.local_storage import LocalStorageAdapter


class TestRoundtripFidelity:
    """load_image(save_image(job_id, bytes)) must return the original bytes."""

    def test_roundtrip_simple_bytes(self, tmp_path: Path) -> None:
        adapter = LocalStorageAdapter(base_dir=str(tmp_path))
        image_bytes = b"\x89PNG\r\n\x1a\nsome fake image data"
        path = adapter.save_image("job-001", image_bytes)
        assert adapter.load_image(path) == image_bytes

    def test_roundtrip_empty_bytes(self, tmp_path: Path) -> None:
        adapter = LocalStorageAdapter(base_dir=str(tmp_path))
        image_bytes = b""
        path = adapter.save_image("job-empty", image_bytes)
        assert adapter.load_image(path) == image_bytes

    def test_roundtrip_binary_data(self, tmp_path: Path) -> None:
        adapter = LocalStorageAdapter(base_dir=str(tmp_path))
        image_bytes = bytes(range(256)) * 100
        path = adapter.save_image("job-binary", image_bytes)
        assert adapter.load_image(path) == image_bytes


class TestDirectoryCreation:
    """base_dir must be created automatically on first save_image call."""

    def test_creates_nested_directory(self, tmp_path: Path) -> None:
        nested_dir = tmp_path / "a" / "b" / "c"
        assert not nested_dir.exists()
        adapter = LocalStorageAdapter(base_dir=str(nested_dir))
        adapter.save_image("job-001", b"data")
        assert nested_dir.exists()

    def test_does_not_fail_if_dir_already_exists(self, tmp_path: Path) -> None:
        tmp_path.mkdir(parents=True, exist_ok=True)
        adapter = LocalStorageAdapter(base_dir=str(tmp_path))
        # Should not raise even though directory already exists
        adapter.save_image("job-001", b"data")


class TestMultipleJobs:
    """Different job_ids must be stored independently without collision."""

    def test_two_jobs_stored_independently(self, tmp_path: Path) -> None:
        adapter = LocalStorageAdapter(base_dir=str(tmp_path))
        bytes_a = b"image data for job A"
        bytes_b = b"image data for job B"
        path_a = adapter.save_image("job-a", bytes_a)
        path_b = adapter.save_image("job-b", bytes_b)
        assert path_a != path_b
        assert adapter.load_image(path_a) == bytes_a
        assert adapter.load_image(path_b) == bytes_b

    def test_overwrite_same_job_id(self, tmp_path: Path) -> None:
        adapter = LocalStorageAdapter(base_dir=str(tmp_path))
        adapter.save_image("job-x", b"first write")
        path = adapter.save_image("job-x", b"second write")
        assert adapter.load_image(path) == b"second write"


class TestLoadExactBytes:
    """load_image must return exactly the bytes that were saved."""

    def test_exact_bytes_preserved(self, tmp_path: Path) -> None:
        adapter = LocalStorageAdapter(base_dir=str(tmp_path))
        original = b"\x00\xff\xfe\xfd" * 512
        path = adapter.save_image("job-exact", original)
        loaded = adapter.load_image(path)
        assert loaded == original
        assert len(loaded) == len(original)

    def test_no_trailing_bytes_added(self, tmp_path: Path) -> None:
        adapter = LocalStorageAdapter(base_dir=str(tmp_path))
        original = b"exact content"
        path = adapter.save_image("job-no-trail", original)
        loaded = adapter.load_image(path)
        assert loaded == original
