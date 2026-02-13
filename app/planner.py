from __future__ import annotations

from typing import Any, Dict

from app.models import AutomationFixOutput, AutomationFlowOutput, AutomationSimplificationOutput


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def build_flow(payload: Dict[str, Any]) -> AutomationFlowOutput:
    goal = _safe_text(payload.get("goal")) or "Automacao solicitada"
    context = _safe_text(payload.get("context")) or "OPERACAO"
    systems = payload.get("systems") or ["GHL"]
    triggers = [f"Evento {context} recebido", "Tag aplicada no GHL"]
    conditions = ["Dados minimos presentes", "Nao duplicar execucao"]
    actions = ["Atualizar campo no GHL", "Disparar webhook para Make"]
    return AutomationFlowOutput(
        workflow_summary=f"Fluxo para {goal} no contexto {context}.",
        triggers=triggers,
        conditions=conditions,
        actions=actions,
        systems_used=[str(s).upper() for s in systems if s],
    )


def build_fix(payload: Dict[str, Any]) -> AutomationFixOutput:
    source = _safe_text(payload.get("source")) or "GHL"
    desc = _safe_text(payload.get("description")) or "Falha de integracao"
    impact = _safe_text(payload.get("impact")).upper() or "MEDIO"
    priority = "ALTA" if impact == "ALTO" else "MEDIA"
    return AutomationFixOutput(
        root_cause=f"Falha detectada em {source}: {desc}.",
        suggested_fix="Revisar credenciais e mapeamento de campos no fluxo.",
        priority=priority,
    )


def build_simplification(payload: Dict[str, Any]) -> AutomationSimplificationOutput:
    context = _safe_text(payload.get("context")) or "OPERACAO"
    return AutomationSimplificationOutput(
        area=context,
        issue="EXCESSO_AUTOMACAO",
        recommendation="Reduzir o numero de gatilhos e consolidar etapas do fluxo.",
    )
