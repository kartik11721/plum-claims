from __future__ import annotations
import json
from pathlib import Path
import aiofiles

# Simple file-based persistence for the assessment.
# Each claim and trace stored as a JSON file in /tmp/plum_db/.
DB_DIR = Path("/tmp/plum_db")
DB_DIR.mkdir(parents=True, exist_ok=True)


async def save_claim_result(claim_id: str, result) -> None:
    path = DB_DIR / f"claim_{claim_id}.json"
    data = result.model_dump() if hasattr(result, "model_dump") else result
    async with aiofiles.open(path, "w") as f:
        await f.write(json.dumps(data, default=str))


async def get_claim_result(claim_id: str) -> dict | None:
    path = DB_DIR / f"claim_{claim_id}.json"
    if not path.exists():
        return None
    async with aiofiles.open(path) as f:
        return json.loads(await f.read())


async def save_trace(trace_id: str, trace, claim_id: str) -> None:
    path = DB_DIR / f"trace_{claim_id}.json"
    data = trace.model_dump() if hasattr(trace, "model_dump") else trace
    async with aiofiles.open(path, "w") as f:
        await f.write(json.dumps(data, default=str))


async def get_trace(claim_id: str) -> dict | None:
    path = DB_DIR / f"trace_{claim_id}.json"
    if not path.exists():
        return None
    async with aiofiles.open(path) as f:
        return json.loads(await f.read())
