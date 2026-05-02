from fastapi import APIRouter
from ..config import load_policy

router = APIRouter(prefix="/api", tags=["policy"])


@router.get("/policy")
async def get_policy():
    policy = load_policy()
    return {
        "policy_id": policy.get("policy_id"),
        "policy_name": policy.get("policy_name"),
        "coverage": policy.get("coverage"),
        "opd_categories": policy.get("opd_categories"),
        "waiting_periods": policy.get("waiting_periods"),
        "exclusions": policy.get("exclusions"),
        "network_hospitals": policy.get("network_hospitals"),
    }


@router.get("/members/{member_id}")
async def get_member(member_id: str):
    policy = load_policy()
    member = next((m for m in policy.get("members", []) if m["member_id"] == member_id), None)
    if not member:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Member not found")
    return member
