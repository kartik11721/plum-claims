from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.claims import router as claims_router
from .api.policy import router as policy_router

app = FastAPI(
    title="Plum Claims Processing System",
    description="Multi-agent health insurance claims processing with full audit trace",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims_router)
app.include_router(policy_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
