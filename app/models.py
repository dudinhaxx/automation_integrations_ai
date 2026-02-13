from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel


Context = Literal["PROSPECT", "COMERCIAL", "ENTREGA", "OPERACAO"]
Priority = Literal["ALTA", "MEDIA", "BAIXA"]
System = Literal["GHL", "MAKE", "ZAPIER"]
Impact = Literal["ALTO", "MEDIO", "BAIXO"]
IssueType = Literal["EXCESSO_AUTOMACAO", "FALHA_RECORRENTE"]


class AutomationFlowOutput(BaseModel):
    workflow_summary: str
    triggers: List[str]
    conditions: List[str]
    actions: List[str]
    systems_used: List[System]


class AutomationFixOutput(BaseModel):
    root_cause: str
    suggested_fix: str
    priority: Priority


class AutomationSimplificationOutput(BaseModel):
    area: Context
    issue: IssueType
    recommendation: str


class AutomationFlowDefined(BaseModel):
    request_id: str
    workflow_summary: str
    triggers: List[str]
    conditions: List[str]
    actions: List[str]
    systems_used: List[System]
    timestamp: str


class AutomationFixSuggested(BaseModel):
    error_id: str
    root_cause: str
    suggested_fix: str
    priority: Priority
    timestamp: str


class AutomationSimplificationRecommended(BaseModel):
    area: Context
    issue: IssueType
    recommendation: str
    timestamp: str


class Capability(BaseModel):
    agent_name: str
    mode: str
    consumes: List[str]
    produces: List[str]
