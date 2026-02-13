# automation_integrations_ai

Automacao & Integracoes AI (engenharia de fluxos) for DMA Digital.

## Purpose
Desenhar, validar e otimizar automacoes entre GHL, Make e Zapier.

## Endpoints
- `GET /health`
- `GET /capabilities`
- `POST /handle_event` (consumes `AUTOMATION_REQUEST`, `AUTOMATION_ERROR_DETECTED`)

## Events
Consumes:
- `AUTOMATION_REQUEST`
- `AUTOMATION_ERROR_DETECTED`

Produces:
- `AUTOMATION_FLOW_DEFINED`
- `AUTOMATION_FIX_SUGGESTED`
- `AUTOMATION_SIMPLIFICATION_RECOMMENDED`

## Run
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8021
```

## Example input (request)
```json
{
  "id": "uuid",
  "trace_id": "uuid",
  "name": "AUTOMATION_REQUEST",
  "source": "maestro_ceo_ai",
  "location_id": "loc-1",
  "contact_id": "contact-1",
  "payload": {
    "request_id": "req-1",
    "context": "COMERCIAL",
    "goal": "Disparar follow-up apos lead quente",
    "systems": ["GHL", "MAKE"],
    "priority": "ALTA",
    "timestamp": "2026-02-10T15:00:00Z"
  }
}
```

## Example input (error)
```json
{
  "id": "uuid",
  "trace_id": "uuid",
  "name": "AUTOMATION_ERROR_DETECTED",
  "source": "monitoring",
  "location_id": "loc-1",
  "contact_id": "contact-1",
  "payload": {
    "error_id": "err-1",
    "source": "MAKE",
    "description": "Webhook nao respondeu",
    "impact": "ALTO",
    "timestamp": "2026-02-10T15:05:00Z"
  }
}
```
