from __future__ import annotations

import importlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from app.audit import write_audit_log
from app.config import Settings
from app.idempotency import IdempotencyStore
from app.models import (
    AutomationFixSuggested,
    AutomationFlowDefined,
    AutomationSimplificationRecommended,
)
from app.openai_brain import generate_fix, generate_flow, generate_simplification
from app.planner import build_fix, build_flow, build_simplification
from app.publisher import MaestroPublisher
from app.utils import model_validate


SUPPORTED_EVENTS = {"AUTOMATION_REQUEST", "AUTOMATION_ERROR_DETECTED"}


def _load_dma_rules() -> Any:
    try:
        return importlib.import_module("dma_rules")
    except ModuleNotFoundError as exc:
        class Event(BaseModel):
            id: str
            trace_id: str
            name: str
            source: str
            location_id: str
            contact_id: Optional[str] = None
            payload: Dict[str, Any] = Field(default_factory=dict)

        class EventDraft(BaseModel):
            name: str
            source: str
            location_id: str
            contact_id: Optional[str] = None
            payload: Dict[str, Any] = Field(default_factory=dict)

        class AgentResult(BaseModel):
            trace_id: str
            event_id: str
            handler: str
            status: str
            next_events: List[Dict[str, Any]] = Field(default_factory=list)
            evidence: Dict[str, Any] = Field(default_factory=dict)
            errors: List[str] = Field(default_factory=list)
            duration_ms: int = 0

        def action_key(event_name: str, trace_id: str, payload: Dict[str, Any]) -> str:
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            base = f"{event_name}|{trace_id}|{canonical}"
            return uuid.uuid5(uuid.NAMESPACE_URL, base).hex

        return SimpleNamespace(Event=Event, EventDraft=EventDraft, AgentResult=AgentResult, action_key=action_key)


def _event_name_allowed(dma_rules: Any, name: str) -> bool:
    event_enum = getattr(dma_rules, "EventName", None)
    if event_enum is None:
        return True
    values = set()
    if hasattr(event_enum, "__members__"):
        values = {member.value for member in event_enum.__members__.values()}
    else:
        try:
            values = {member.value for member in event_enum}
        except TypeError:
            values = set()
    return name in values


def _build_event_draft(
    *,
    name: str,
    trace_id: str,
    contact_id: Optional[str],
    location_id: str,
    source: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    enriched_payload = dict(payload)
    if trace_id and "trace_id" not in enriched_payload:
        enriched_payload["trace_id"] = trace_id
    return {
        "name": name,
        "source": source,
        "location_id": location_id,
        "contact_id": contact_id,
        "payload": enriched_payload,
    }


def _build_agent_result(
    *,
    dma_rules: Any,
    handler: str,
    trace_id: str,
    event_id: str,
    status: str,
    next_events: List[Dict[str, Any]],
    evidence: Dict[str, Any],
    errors: Optional[List[str]] = None,
    duration_ms: int = 0,
) -> Dict[str, Any]:
    payload = {
        "trace_id": trace_id,
        "event_id": event_id,
        "handler": handler,
        "status": status,
        "next_events": next_events,
        "evidence": evidence,
        "errors": errors or [],
        "duration_ms": duration_ms,
    }
    model = getattr(dma_rules, "AgentResult", None)
    if model is None:
        raise RuntimeError("dma_rules.AgentResult not found")
    model_validate(model, payload)
    return payload


def _persist_report(reports_dir: str, trace_id: str, payload: Dict[str, Any]) -> str:
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"automation_{trace_id}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
    return path


def _build_context_text(context: Dict[str, Any]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in context.items())


def _send_via_make(settings: Settings, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.make_webhook_url:
        return {"attempted": False, "provider": "MAKE", "success": False, "reason": "missing_make_webhook_url"}

    headers = {"Content-Type": "application/json"}
    if settings.make_webhook_token:
        headers["Authorization"] = f"Bearer {settings.make_webhook_token}"

    try:
        response = requests.post(
            settings.make_webhook_url,
            json=payload,
            headers=headers,
            timeout=settings.request_timeout,
        )
        return {
            "attempted": True,
            "provider": "MAKE",
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "response": response.text[:500],
        }
    except requests.RequestException as exc:
        return {"attempted": True, "provider": "MAKE", "success": False, "error": str(exc)}


def _send_via_ghl(settings: Settings, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.ghl_token:
        return {"attempted": False, "provider": "GHL", "success": False, "reason": "missing_ghl_token"}

    base_url = settings.ghl_base_url.rstrip("/")
    path = settings.ghl_whatsapp_path
    location_id = payload.get("location_id") or ""
    if "{location_id}" in path:
        path = path.format(location_id=location_id)
    url = f"{base_url}/{path.lstrip('/')}"

    headers = {
        "Authorization": f"Bearer {settings.ghl_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": settings.ghl_api_version,
    }

    body = {
        "contactId": payload.get("contact_id"),
        "locationId": location_id,
        "message": payload.get("message_text"),
        "type": "WhatsApp",
        "channel": "whatsapp",
        "messageType": 0,
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=settings.request_timeout)
        return {
            "attempted": True,
            "provider": "GHL",
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "response": response.text[:500],
            "url": url,
        }
    except requests.RequestException as exc:
        return {
            "attempted": True,
            "provider": "GHL",
            "success": False,
            "error": str(exc),
            "url": url,
        }


def _dispatch_outbound_message(settings: Settings, event_dict: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    message_text = str(context.get("message_text") or context.get("text") or "").strip()
    contact_id = event_dict.get("contact_id")
    location_id = event_dict.get("location_id")

    if not message_text:
        return {"attempted": False, "success": False, "reason": "missing_message_text"}
    if not contact_id:
        return {"attempted": False, "success": False, "reason": "missing_contact_id"}
    if not location_id:
        return {"attempted": False, "success": False, "reason": "missing_location_id"}

    if settings.agent_mode.upper() != "EXECUTE":
        return {"attempted": False, "success": False, "reason": "agent_mode_not_execute"}

    outbound_payload = {
        "trace_id": event_dict.get("trace_id"),
        "request_id": context.get("request_id"),
        "contact_id": contact_id,
        "location_id": location_id,
        "channel": context.get("channel") or "WHATSAPP",
        "message_text": message_text,
        "source": context.get("source") or event_dict.get("name"),
    }

    make_result = _send_via_make(settings, outbound_payload)
    if make_result.get("success"):
        return {"attempted": True, "success": True, "provider": "MAKE", "details": make_result}

    ghl_result = _send_via_ghl(settings, outbound_payload)
    if ghl_result.get("success"):
        return {"attempted": True, "success": True, "provider": "GHL", "details": ghl_result}

    return {
        "attempted": bool(make_result.get("attempted") or ghl_result.get("attempted")),
        "success": False,
        "provider": "NONE",
        "make": make_result,
        "ghl": ghl_result,
    }


def handle_event(settings: Settings, event_data: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.perf_counter()
    dma_rules = _load_dma_rules()
    event_model = getattr(dma_rules, "Event", None)
    if event_model is None:
        raise RuntimeError("dma_rules.Event not found")
    event = model_validate(event_model, event_data)
    event_dict = event.model_dump() if hasattr(event, "model_dump") else event.dict()

    event_name = str(event_dict.get("name", "")).upper()
    if event_name not in SUPPORTED_EVENTS:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return _build_agent_result(
            dma_rules=dma_rules,
            handler=settings.agent_name,
            trace_id=event_dict.get("trace_id", ""),
            event_id=event_dict.get("id", ""),
            status="skipped",
            next_events=[],
            evidence={"reason": "unsupported_event", "summary": "Evento nao suportado."},
            duration_ms=duration_ms,
        )

    action_key = dma_rules.action_key(
        event_dict.get("name", ""),
        event_dict.get("trace_id", ""),
        event_dict.get("payload", {}),
    )

    idempotency = IdempotencyStore(settings.data_dir)
    if idempotency.is_processed(action_key):
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return _build_agent_result(
            dma_rules=dma_rules,
            handler=settings.agent_name,
            trace_id=event_dict.get("trace_id", ""),
            event_id=event_dict.get("id", ""),
            status="skipped",
            next_events=[],
            evidence={"reason": "idempotent", "summary": "Evento ja processado."},
            duration_ms=duration_ms,
        )

    payload = event_dict.get("payload", {})
    context = dict(payload)

    now_iso = datetime.now(timezone.utc).isoformat()
    publisher = MaestroPublisher(settings.maestro_base_url)
    next_events: List[Dict[str, Any]] = []

    if event_name == "AUTOMATION_REQUEST":
        delivery_result = _dispatch_outbound_message(settings, event_dict, context)
        flow = build_flow(context)
        if settings.brain_enabled and settings.openai_api_key:
            flow = generate_flow(settings, context=_build_context_text(context))

        flow_payload = AutomationFlowDefined(
            request_id=str(context.get("request_id") or ""),
            workflow_summary=flow.workflow_summary,
            triggers=flow.triggers,
            conditions=flow.conditions,
            actions=flow.actions,
            systems_used=flow.systems_used,
            timestamp=now_iso,
        ).model_dump()
        flow_draft = _build_event_draft(
            name="AUTOMATION_FLOW_DEFINED",
            trace_id=event_dict.get("trace_id", ""),
            contact_id=event_dict.get("contact_id"),
            location_id=event_dict.get("location_id", ""),
            source=settings.agent_name,
            payload=flow_payload,
        )
        if _event_name_allowed(dma_rules, "AUTOMATION_FLOW_DEFINED"):
            publisher.publish_event(flow_draft, dma_rules)
            next_events.append(flow_draft)

        report_path = _persist_report(
            settings.reports_dir,
            event_dict.get("trace_id", ""),
            {
                "trace_id": event_dict.get("trace_id", ""),
                "event": event_dict.get("name"),
                "decision": flow_payload,
                "payload": payload,
                "delivery_result": delivery_result,
            },
        )

        write_audit_log(
            settings.audit_log_path,
            {
                "trace_id": event_dict.get("trace_id", ""),
                "action": "automation_flow_defined",
                "action_key": action_key,
                "report_path": report_path,
                "event": event_dict.get("name"),
            },
        )

        idempotency.mark_processed(action_key)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return _build_agent_result(
            dma_rules=dma_rules,
            handler=settings.agent_name,
            trace_id=event_dict.get("trace_id", ""),
            event_id=event_dict.get("id", ""),
            status="success",
            next_events=next_events,
            evidence={"report_path": report_path, **flow_payload, "delivery_result": delivery_result},
            duration_ms=duration_ms,
        )

    fix = build_fix(context)
    simplification = build_simplification(context)
    if settings.brain_enabled and settings.openai_api_key:
        fix = generate_fix(settings, context=_build_context_text(context))
        simplification = generate_simplification(settings, context=_build_context_text(context))

    fix_payload = AutomationFixSuggested(
        error_id=str(context.get("error_id") or ""),
        root_cause=fix.root_cause,
        suggested_fix=fix.suggested_fix,
        priority=fix.priority,
        timestamp=now_iso,
    ).model_dump()
    fix_draft = _build_event_draft(
        name="AUTOMATION_FIX_SUGGESTED",
        trace_id=event_dict.get("trace_id", ""),
        contact_id=event_dict.get("contact_id"),
        location_id=event_dict.get("location_id", ""),
        source=settings.agent_name,
        payload=fix_payload,
    )
    if _event_name_allowed(dma_rules, "AUTOMATION_FIX_SUGGESTED"):
        publisher.publish_event(fix_draft, dma_rules)
        next_events.append(fix_draft)

    simplification_payload = AutomationSimplificationRecommended(
        area=simplification.area,
        issue=simplification.issue,
        recommendation=simplification.recommendation,
        timestamp=now_iso,
    ).model_dump()
    simplification_draft = _build_event_draft(
        name="AUTOMATION_SIMPLIFICATION_RECOMMENDED",
        trace_id=event_dict.get("trace_id", ""),
        contact_id=event_dict.get("contact_id"),
        location_id=event_dict.get("location_id", ""),
        source=settings.agent_name,
        payload=simplification_payload,
    )
    if _event_name_allowed(dma_rules, "AUTOMATION_SIMPLIFICATION_RECOMMENDED"):
        publisher.publish_event(simplification_draft, dma_rules)
        next_events.append(simplification_draft)

    report_path = _persist_report(
        settings.reports_dir,
        event_dict.get("trace_id", ""),
        {
            "trace_id": event_dict.get("trace_id", ""),
            "event": event_dict.get("name"),
            "decision": {
                "fix": fix_payload,
                "simplification": simplification_payload,
            },
            "payload": payload,
        },
    )

    write_audit_log(
        settings.audit_log_path,
        {
            "trace_id": event_dict.get("trace_id", ""),
            "action": "automation_fix_suggested",
            "action_key": action_key,
            "report_path": report_path,
            "event": event_dict.get("name"),
        },
    )

    idempotency.mark_processed(action_key)

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    evidence = {"report_path": report_path, **fix_payload}
    return _build_agent_result(
        dma_rules=dma_rules,
        handler=settings.agent_name,
        trace_id=event_dict.get("trace_id", ""),
        event_id=event_dict.get("id", ""),
        status="success",
        next_events=next_events,
        evidence=evidence,
        duration_ms=duration_ms,
    )
