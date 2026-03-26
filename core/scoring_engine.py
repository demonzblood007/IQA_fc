"""IQA Scoring Engine — pure Pillow-based image quality assessment."""

from __future__ import annotations

import io

from PIL import Image, ImageFilter, ImageStat

from core.domain import IQAScore
from core.exceptions import ImageDecodeError

SHARPNESS_NORM_FACTOR: float = 500.0
CONTRAST_NORM_FACTOR: float = 128.0


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class IQAScoringEngine:
    """Pure domain logic. No I/O. Stateless."""

    def score(self, image_bytes: bytes) -> IQAScore:
        """
        Runs lightweight quality assessment on raw image bytes.

        Returns IQAScore with per-dimension scores in [0.0, 1.0].
        Raises ImageDecodeError if image_bytes cannot be decoded.
        """
        try:
            image: Image.Image = Image.open(io.BytesIO(image_bytes))
            image.load()
        except Exception as exc:
            raise ImageDecodeError(f"Failed to decode image: {exc}") from exc

        gray: Image.Image = image.convert("L")

        # Sharpness: Laplacian variance via FIND_EDGES filter
        edges: Image.Image = gray.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        sharpness = _clamp(edge_stat.var[0] / SHARPNESS_NORM_FACTOR)

        # Brightness: mean pixel intensity normalised to [0, 1]
        gray_stat = ImageStat.Stat(gray)
        brightness = _clamp(gray_stat.mean[0] / 255.0)

        # Contrast: std deviation of pixel intensities normalised to [0, 1]
        contrast = _clamp(gray_stat.stddev[0] / CONTRAST_NORM_FACTOR)

        overall = (sharpness + brightness + contrast) / 3.0

        return IQAScore(
            overall=overall,
            sharpness=sharpness,
            brightness=brightness,
            contrast=contrast,
        )
