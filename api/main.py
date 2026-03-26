"""FastAPI ingestion layer for the IQA Async Microservice."""
from __future__ import annotations

import ipaddress
import socket
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from adapters.local_queue import LocalQueueAdapter
from adapters.local_storage import LocalStorageAdapter
from adapters.sqlite_db import SQLiteDBAdapter
from core.domain import IQAScore, Job, JobStatus
from core.job_service import JobService

# --- Constants ---
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_SCHEMES = {"http", "https"}

# RFC-1918 private ranges + loopback
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

# Module-level singleton — created once at import time
_job_service: Optional[JobService] = None


def _create_default_job_service() -> JobService:
    storage = LocalStorageAdapter(base_dir="/tmp/iqa_images")
    database = SQLiteDBAdapter(db_path="./iqa_jobs.db")
    queue = LocalQueueAdapter()
    return JobService(storage=storage, database=database, queue=queue)


def get_job_service() -> JobService:
    """FastAPI dependency that returns the singleton JobService."""
    global _job_service
    if _job_service is None:
        _job_service = _create_default_job_service()
    return _job_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Eagerly initialise the singleton on startup
    get_job_service()
    yield


app = FastAPI(title="IQA Async Microservice", lifespan=lifespan)


# --- SSRF validation ---

def _is_private_ip(host: str) -> bool:
    """Return True if *host* resolves to a private/loopback address."""
    # Reject well-known hostnames directly
    if host.lower() in {"localhost"}:
        return True
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        # Not a bare IP — try DNS resolution
        try:
            resolved = socket.getaddrinfo(host, None)
            for _family, _type, _proto, _canonname, sockaddr in resolved:
                ip_str = sockaddr[0]
                try:
                    addr = ipaddress.ip_address(ip_str)
                    if any(addr in net for net in _PRIVATE_NETWORKS):
                        return True
                except ValueError:
                    continue
        except OSError:
            pass
    return False


def validate_webhook_url(webhook_url: str) -> None:
    """Raise HTTPException(422) if *webhook_url* fails SSRF checks."""
    parsed = urlparse(webhook_url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise HTTPException(
            status_code=422,
            detail=f"webhook_url scheme '{parsed.scheme}' is not allowed; use http or https.",
        )

    host = parsed.hostname or ""
    if not host:
        raise HTTPException(status_code=422, detail="webhook_url has no host.")

    if _is_private_ip(host):
        raise HTTPException(
            status_code=422,
            detail=f"webhook_url host '{host}' resolves to a private/loopback address (SSRF protection).",
        )


# --- Response models ---

class JobSubmitResponse(BaseModel):
    job_id: str


class IQAScoreResponse(BaseModel):
    overall: float
    sharpness: float
    brightness: float
    contrast: float


class JobStatusResponse(BaseModel):
    job_id: str
    image_path: str
    webhook_url: str
    status: JobStatus
    score: Optional[IQAScoreResponse] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def _job_to_response(job: Job) -> JobStatusResponse:
    score_resp: Optional[IQAScoreResponse] = None
    if job.score is not None:
        score_resp = IQAScoreResponse(
            overall=job.score.overall,
            sharpness=job.score.sharpness,
            brightness=job.score.brightness,
            contrast=job.score.contrast,
        )
    return JobStatusResponse(
        job_id=job.job_id,
        image_path=job.image_path,
        webhook_url=job.webhook_url,
        status=job.status,
        score=score_resp,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# --- Endpoints ---

@app.post("/jobs", status_code=202, response_model=JobSubmitResponse)
async def submit_job(
    image: UploadFile = File(...),
    webhook_url: str = Form(...),
    job_service: JobService = Depends(get_job_service),
) -> JobSubmitResponse:
    """Accept an image upload and enqueue an IQA job."""
    # MIME type validation
    content_type = image.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported image type '{content_type}'. Allowed: {sorted(ALLOWED_MIME_TYPES)}",
        )

    # SSRF validation
    validate_webhook_url(webhook_url)

    # Read and size-check
    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds maximum allowed size of {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    job_id = job_service.submit_job(image_bytes, webhook_url)
    return JobSubmitResponse(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> JobStatusResponse:
    """Return current status of an IQA job."""
    job = job_service.get_job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return _job_to_response(job)
