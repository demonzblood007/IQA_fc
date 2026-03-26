"""Unit tests for WebhookClient."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from core.domain import IQAScore, JobStatus
from core.webhook_client import MAX_WEBHOOK_RETRIES, WebhookClient

WEBHOOK_URL = "https://example.com/webhook"
JOB_ID = "job-123"
SCORE = IQAScore(overall=0.9, sharpness=0.8, brightness=0.7, contrast=0.6)


def _make_response(status_code: int) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    return resp


@patch("time.sleep")
@patch("httpx.Client")
def test_successful_delivery(mock_client_cls: MagicMock, mock_sleep: MagicMock) -> None:
    """A 200 response means notify completes without error and POST is called once."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.return_value = _make_response(200)

    WebhookClient().notify(WEBHOOK_URL, JOB_ID, SCORE, JobStatus.COMPLETED)

    mock_client.post.assert_called_once_with(
        WEBHOOK_URL,
        json={
            "job_id": JOB_ID,
            "status": "COMPLETED",
            "score": {
                "overall": 0.9,
                "sharpness": 0.8,
                "brightness": 0.7,
                "contrast": 0.6,
            },
            "error": None,
        },
    )
    mock_sleep.assert_not_called()


@patch("time.sleep")
@patch("httpx.Client")
def test_retry_on_failure(mock_client_cls: MagicMock, mock_sleep: MagicMock) -> None:
    """RequestError on first 2 calls, success on 3rd → POST called 3 times total."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.side_effect = [
        httpx.RequestError("timeout"),
        httpx.RequestError("timeout"),
        _make_response(200),
    ]

    WebhookClient().notify(WEBHOOK_URL, JOB_ID, None, JobStatus.FAILED, error="oops")

    assert mock_client.post.call_count == 3
    # sleep called between attempt 0→1 and 1→2 (not after the successful 3rd)
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(1)  # 2**0
    mock_sleep.assert_any_call(2)  # 2**1


@patch("time.sleep")
@patch("httpx.Client")
def test_exhausted_retries_does_not_raise(
    mock_client_cls: MagicMock, mock_sleep: MagicMock
) -> None:
    """After MAX_WEBHOOK_RETRIES failures notify returns normally — no exception."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.side_effect = httpx.RequestError("connection refused")

    # Must not raise
    WebhookClient().notify(WEBHOOK_URL, JOB_ID, None, JobStatus.FAILED)

    assert mock_client.post.call_count == MAX_WEBHOOK_RETRIES


@patch("time.sleep")
@patch("httpx.Client")
def test_retry_on_non_2xx(mock_client_cls: MagicMock, mock_sleep: MagicMock) -> None:
    """500 on first call, 200 on second → POST called twice, no exception raised."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.side_effect = [
        _make_response(500),
        _make_response(200),
    ]

    WebhookClient().notify(WEBHOOK_URL, JOB_ID, SCORE, JobStatus.COMPLETED)

    assert mock_client.post.call_count == 2
    mock_sleep.assert_called_once_with(1)  # 2**0 between attempt 0 and 1
