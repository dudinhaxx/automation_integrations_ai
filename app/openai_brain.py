from __future__ import annotations

from typing import Any, Dict

from openai import OpenAI

from app.config import Settings
from app.models import AutomationFixOutput, AutomationFlowOutput, AutomationSimplificationOutput
from app.prompts import SYSTEM_PROMPT, build_user_prompt


def _enforce_no_additional_properties(schema: Any) -> None:
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema.setdefault("additionalProperties", False)
            properties = schema.get("properties", {})
            if isinstance(properties, dict):
                schema["required"] = list(properties.keys())
                for prop_schema in properties.values():
                    _enforce_no_additional_properties(prop_schema)

        for key in ("items", "anyOf", "allOf", "oneOf", "not"):
            value = schema.get(key)
            if isinstance(value, list):
                for entry in value:
                    _enforce_no_additional_properties(entry)
            elif isinstance(value, dict):
                _enforce_no_additional_properties(value)

        for defs_key in ("$defs", "definitions"):
            defs = schema.get(defs_key)
            if isinstance(defs, dict):
                for entry in defs.values():
                    _enforce_no_additional_properties(entry)
    elif isinstance(schema, list):
        for entry in schema:
            _enforce_no_additional_properties(entry)


def _build_json_schema(model: Any) -> Dict[str, Any]:
    schema = model.model_json_schema()
    _enforce_no_additional_properties(schema)
    return {
        "name": model.__name__,
        "schema": schema,
        "strict": True,
    }


def generate_flow(settings: Settings, *, context: str) -> AutomationFlowOutput:
    client = OpenAI(api_key=settings.openai_api_key)
    json_schema = _build_json_schema(AutomationFlowOutput)
    response = client.responses.create(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_output_tokens=settings.openai_max_output_tokens,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(context)},
        ],
        text={"format": {"type": "json_schema", **json_schema}},
    )
    output_text = response.output_text
    return AutomationFlowOutput.model_validate_json(output_text)


def generate_fix(settings: Settings, *, context: str) -> AutomationFixOutput:
    client = OpenAI(api_key=settings.openai_api_key)
    json_schema = _build_json_schema(AutomationFixOutput)
    response = client.responses.create(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_output_tokens=settings.openai_max_output_tokens,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(context)},
        ],
        text={"format": {"type": "json_schema", **json_schema}},
    )
    output_text = response.output_text
    return AutomationFixOutput.model_validate_json(output_text)


def generate_simplification(settings: Settings, *, context: str) -> AutomationSimplificationOutput:
    client = OpenAI(api_key=settings.openai_api_key)
    json_schema = _build_json_schema(AutomationSimplificationOutput)
    response = client.responses.create(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_output_tokens=settings.openai_max_output_tokens,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(context)},
        ],
        text={"format": {"type": "json_schema", **json_schema}},
    )
    output_text = response.output_text
    return AutomationSimplificationOutput.model_validate_json(output_text)
