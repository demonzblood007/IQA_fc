"""Custom exceptions for the IQA core domain."""


class DuplicateJobError(Exception):
    """Raised when create_job is called with a job_id that already exists."""


class ImageDecodeError(Exception):
    """Raised when image bytes cannot be decoded as a valid image."""
