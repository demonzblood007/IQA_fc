"""Unit tests for IQAScoringEngine."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from core.scoring_engine import IQAScoringEngine
from core.exceptions import ImageDecodeError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_image_bytes(color: int = 128, size: tuple = (64, 64), fmt: str = "JPEG") -> bytes:
    img = Image.new("L", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def make_noise_image_bytes(size: tuple = (64, 64)) -> bytes:
    import random
    img = Image.new("L", size)
    pixels = [random.randint(0, 255) for _ in range(size[0] * size[1])]
    img.putdata(pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> IQAScoringEngine:
    return IQAScoringEngine()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestScoreBounds:
    """All score fields must be in [0.0, 1.0]."""

    def test_mid_grey_score_bounds(self, engine: IQAScoringEngine) -> None:
        score = engine.score(make_image_bytes(color=128))
        assert 0.0 <= score.overall <= 1.0
        assert 0.0 <= score.sharpness <= 1.0
        assert 0.0 <= score.brightness <= 1.0
        assert 0.0 <= score.contrast <= 1.0

    def test_solid_black_score_bounds(self, engine: IQAScoringEngine) -> None:
        score = engine.score(make_image_bytes(color=0))
        assert 0.0 <= score.overall <= 1.0
        assert 0.0 <= score.sharpness <= 1.0
        assert 0.0 <= score.brightness <= 1.0
        assert 0.0 <= score.contrast <= 1.0

    def test_solid_white_score_bounds(self, engine: IQAScoringEngine) -> None:
        score = engine.score(make_image_bytes(color=255))
        assert 0.0 <= score.overall <= 1.0
        assert 0.0 <= score.sharpness <= 1.0
        assert 0.0 <= score.brightness <= 1.0
        assert 0.0 <= score.contrast <= 1.0

    def test_noise_image_score_bounds(self, engine: IQAScoringEngine) -> None:
        score = engine.score(make_noise_image_bytes())
        assert 0.0 <= score.overall <= 1.0
        assert 0.0 <= score.sharpness <= 1.0
        assert 0.0 <= score.brightness <= 1.0
        assert 0.0 <= score.contrast <= 1.0


class TestOverallIsMeanOfDimensions:
    """overall must equal (sharpness + brightness + contrast) / 3.0."""

    def test_mid_grey_overall_is_mean(self, engine: IQAScoringEngine) -> None:
        score = engine.score(make_image_bytes(color=128))
        expected = (score.sharpness + score.brightness + score.contrast) / 3.0
        assert score.overall == pytest.approx(expected)

    def test_solid_black_overall_is_mean(self, engine: IQAScoringEngine) -> None:
        score = engine.score(make_image_bytes(color=0))
        expected = (score.sharpness + score.brightness + score.contrast) / 3.0
        assert score.overall == pytest.approx(expected)

    def test_solid_white_overall_is_mean(self, engine: IQAScoringEngine) -> None:
        score = engine.score(make_image_bytes(color=255))
        expected = (score.sharpness + score.brightness + score.contrast) / 3.0
        assert score.overall == pytest.approx(expected)

    def test_noise_image_overall_is_mean(self, engine: IQAScoringEngine) -> None:
        score = engine.score(make_noise_image_bytes())
        expected = (score.sharpness + score.brightness + score.contrast) / 3.0
        assert score.overall == pytest.approx(expected)


class TestImageDecodeError:
    """ImageDecodeError must be raised for invalid image bytes."""

    def test_raises_on_empty_bytes(self, engine: IQAScoringEngine) -> None:
        with pytest.raises(ImageDecodeError):
            engine.score(b"")

    def test_raises_on_random_text(self, engine: IQAScoringEngine) -> None:
        with pytest.raises(ImageDecodeError):
            engine.score(b"not an image")

    def test_raises_on_truncated_jpeg(self, engine: IQAScoringEngine) -> None:
        valid = make_image_bytes()
        with pytest.raises(ImageDecodeError):
            engine.score(valid[:20])  # truncated header


# ---------------------------------------------------------------------------
# Property-based tests (hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings
import hypothesis.strategies as st


@given(
    width=st.integers(min_value=1, max_value=128),
    height=st.integers(min_value=1, max_value=128),
    color=st.integers(min_value=0, max_value=255),
)
@settings(max_examples=50)
def test_score_bounds_property(width: int, height: int, color: int) -> None:
    """**Validates: Requirements 6.1** — all score fields in [0.0, 1.0] for any decodable image."""
    image_bytes = make_image_bytes(color=color, size=(width, height), fmt="PNG")
    engine = IQAScoringEngine()
    score = engine.score(image_bytes)
    assert 0.0 <= score.overall <= 1.0
    assert 0.0 <= score.sharpness <= 1.0
    assert 0.0 <= score.brightness <= 1.0
    assert 0.0 <= score.contrast <= 1.0
