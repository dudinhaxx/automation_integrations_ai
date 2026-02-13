from fastapi import Depends, FastAPI, HTTPException

from app.automation_integrations_agent import handle_event
from app.config import get_settings
from app.models import Capability
from app.security import verify_internal_key

app = FastAPI(title="automation_integrations_ai", version="1.0.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/capabilities")
async def capabilities() -> Capability:
    settings = get_settings()
    return Capability(
        agent_name=settings.agent_name,
        mode=settings.agent_mode,
        consumes=["AUTOMATION_REQUEST", "AUTOMATION_ERROR_DETECTED"],
        produces=[
            "AUTOMATION_FLOW_DEFINED",
            "AUTOMATION_FIX_SUGGESTED",
            "AUTOMATION_SIMPLIFICATION_RECOMMENDED",
        ],
    )


@app.post("/handle_event", dependencies=[Depends(verify_internal_key)])
async def handle_event_route(event: dict) -> dict:
    settings = get_settings()
    try:
        return handle_event(settings, event)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
