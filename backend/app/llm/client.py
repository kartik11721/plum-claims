from __future__ import annotations
import base64
import json
from typing import Any

from ..config import (
    ANTHROPIC_API_KEY,
    AZURE_DEPLOYMENT_LLM,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT,
    CLAUDE_MODEL,
)


def _use_azure() -> bool:
    return bool(AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_DEPLOYMENT_LLM)


# ── Anthropic ────────────────────────────────────────────────────────────────

def get_client():
    if _use_azure():
        from openai import AsyncAzureOpenAI
        return AsyncAzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
        )
    import anthropic
    return anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def structured_completion(
    system: str,
    user: str,
    response_schema: dict,
    client=None,
    model: str = CLAUDE_MODEL,
) -> dict[str, Any]:
    c = client or get_client()
    if _use_azure():
        return await _azure_structured_completion(c, system, user, response_schema)
    return await _anthropic_structured_completion(c, system, user, response_schema, model)


async def vision_completion(
    system: str,
    user_text: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    response_schema: dict | None = None,
    client=None,
    model: str = CLAUDE_MODEL,
) -> dict[str, Any]:
    c = client or get_client()
    if _use_azure():
        return await _azure_vision_completion(c, system, user_text, image_bytes, mime_type, response_schema)
    return await _anthropic_vision_completion(c, system, user_text, image_bytes, mime_type, response_schema, model)


# ── Anthropic implementations ────────────────────────────────────────────────

async def _anthropic_structured_completion(client, system: str, user: str, response_schema: dict, model: str) -> dict[str, Any]:
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": user + f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_schema, indent=2)}",
        }],
    )
    return _parse_json(response.content[0].text)


async def _anthropic_vision_completion(client, system: str, user_text: str, image_bytes: bytes, mime_type: str, response_schema: dict | None, model: str) -> dict[str, Any]:
    image_bytes, mime_type = _normalise_image(image_bytes, mime_type)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    user_content: list[dict] = [
        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}},
        {"type": "text", "text": user_text},
    ]
    if response_schema:
        user_content.append({
            "type": "text",
            "text": f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_schema, indent=2)}",
        })
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_content}],
    )
    return _parse_json(response.content[0].text)


# ── Azure OpenAI implementations ─────────────────────────────────────────────

async def _azure_structured_completion(client, system: str, user: str, response_schema: dict) -> dict[str, Any]:
    response = await client.chat.completions.create(
        model=AZURE_DEPLOYMENT_LLM,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user + f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_schema, indent=2)}"},
        ],
    )
    return _parse_json(response.choices[0].message.content)


async def _azure_vision_completion(client, system: str, user_text: str, image_bytes: bytes, mime_type: str, response_schema: dict | None) -> dict[str, Any]:
    image_bytes, mime_type = _normalise_image(image_bytes, mime_type)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    user_content: list[dict] = [
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
        {"type": "text", "text": user_text},
    ]
    if response_schema:
        user_content.append({
            "type": "text",
            "text": f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_schema, indent=2)}",
        })
    response = await client.chat.completions.create(
        model=AZURE_DEPLOYMENT_LLM,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    return _parse_json(response.choices[0].message.content)


# ── Shared ───────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _pdf_to_jpeg(pdf_bytes: bytes) -> bytes:
    """Render the first page of a PDF to JPEG bytes."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    return pix.tobytes("jpeg")


def _normalise_image(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Convert PDF to JPEG so vision APIs always receive a supported image type."""
    if mime_type == "application/pdf":
        return _pdf_to_jpeg(image_bytes), "image/jpeg"
    return image_bytes, mime_type
