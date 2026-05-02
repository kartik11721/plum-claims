from __future__ import annotations
import asyncio
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..config import UPLOAD_DIR, load_policy
from ..models.claim import ClaimSubmission, UploadedDoc
from ..models.decision import FinalDecision, EarlyStopResult
from ..orchestrator import ClaimOrchestrator
from ..db import save_claim_result, get_claim_result, save_trace, get_trace

router = APIRouter(prefix="/api/claims", tags=["claims"])


def get_orchestrator() -> ClaimOrchestrator:
    return ClaimOrchestrator(load_policy())


async def _attach_files(submission: ClaimSubmission, files: list[UploadFile]) -> None:
    """Attach uploaded file bytes to submission documents, creating entries if needed."""
    if files and not submission.documents:
        for i, f in enumerate(files):
            submission.documents.append(UploadedDoc(
                file_id=f"upload_{i}",
                file_name=f.filename or f"file_{i}",
                mime_type=f.content_type or "image/jpeg",
                file_bytes=await f.read(),
            ))
    else:
        file_map = {f.filename or f"file_{i}": f for i, f in enumerate(files)}
        for doc in submission.documents:
            matched = next(
                (f for name, f in file_map.items() if name == doc.file_name or name == doc.file_id),
                None,
            )
            if matched:
                doc.file_bytes = await matched.read()
                doc.mime_type = matched.content_type or "image/jpeg"


@router.post("", response_model=FinalDecision)
async def submit_claim(
    metadata: Annotated[str, Form()],
    files: list[UploadFile] = File(default=[]),
    orchestrator: ClaimOrchestrator = Depends(get_orchestrator),
):
    """Submit a claim with metadata JSON and optional file uploads."""
    try:
        submission_data = json.loads(metadata)
        submission = ClaimSubmission.model_validate(submission_data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid claim metadata: {exc}")

    await _attach_files(submission, files)

    claim_id = str(uuid.uuid4())
    result, trace = await orchestrator.process(submission, claim_id=claim_id)

    await save_claim_result(claim_id, result)
    await save_trace(trace_id=trace.trace_id, trace=trace, claim_id=claim_id)

    return result


@router.post("/eval", response_model=FinalDecision)
async def eval_claim(
    submission: ClaimSubmission,
    orchestrator: ClaimOrchestrator = Depends(get_orchestrator),
):
    """Submit a pre-parsed test case (eval mode — no file uploads needed)."""
    claim_id = str(uuid.uuid4())
    result, trace = await orchestrator.process(submission, claim_id=claim_id)

    await save_claim_result(claim_id, result)
    await save_trace(trace_id=trace.trace_id, trace=trace, claim_id=claim_id)

    return result


@router.post("/stream")
async def submit_claim_stream(
    metadata: Annotated[str, Form()],
    files: list[UploadFile] = File(default=[]),
    orchestrator: ClaimOrchestrator = Depends(get_orchestrator),
):
    """SSE endpoint — streams step-by-step progress then redirects to the result."""
    try:
        submission = ClaimSubmission.model_validate(json.loads(metadata))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid claim metadata: {exc}")

    await _attach_files(submission, files)

    claim_id = str(uuid.uuid4())
    progress_queue: asyncio.Queue = asyncio.Queue()

    async def generate():
        task = asyncio.create_task(
            orchestrator.process(submission, claim_id=claim_id, progress_queue=progress_queue)
        )
        try:
            while not task.done():
                try:
                    event = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    continue

            # Drain any remaining events emitted before task.done() was noticed
            while not progress_queue.empty():
                event = progress_queue.get_nowait()
                yield f"data: {json.dumps(event)}\n\n"

            result, trace = await task
            await save_claim_result(claim_id, result)
            await save_trace(trace_id=trace.trace_id, trace=trace, claim_id=claim_id)
            yield f"data: {json.dumps({'type': 'complete', 'claim_id': claim_id})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{claim_id}", response_model=FinalDecision)
async def get_claim(claim_id: str):
    result = await get_claim_result(claim_id)
    if not result:
        raise HTTPException(status_code=404, detail="Claim not found")
    return result


@router.get("/{claim_id}/trace")
async def get_claim_trace(claim_id: str):
    trace = await get_trace(claim_id=claim_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace
