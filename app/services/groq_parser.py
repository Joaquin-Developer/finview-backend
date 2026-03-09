import base64
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from pdf2image import convert_from_path
from PIL import Image
from openai import OpenAI

from ..config import get_settings


settings = get_settings()


class GroqParseError(Exception):
    pass


def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        if len(parts) >= 2:
            inner = parts[1]
            inner = inner.lstrip()
            if inner.lower().startswith("json"):
                inner = inner[4:]
            return inner.strip()
    return text


def _try_parse_json(text: str) -> dict | None:
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    cleaned = _clean_json_text(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    match = re.search(r'\{.+\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    brace_count = 0
    start_idx = None
    for i, c in enumerate(text):
        if c == '{':
            if start_idx is None:
                start_idx = i
            brace_count += 1
        elif c == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx is not None:
                try:
                    return json.loads(text[start_idx:i+1])
                except json.JSONDecodeError:
                    pass
    
    return None


def _pdf_to_base64_images(pdf_path: str) -> List[str]:
    images = convert_from_path(pdf_path, dpi=150)
    base64_images = []
    for img in images:
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        base64_images.append(img_b64)
    return base64_images


def parse_statement_pdf(pdf_path: str, user_categories: List[str]) -> Dict[str, Any]:
    if not settings.GROQ_API_KEY:
        raise GroqParseError("GROQ_API_KEY no está configurado")

    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    pdf_images_b64 = _pdf_to_base64_images(pdf_path)

    prompt = f"""
Analizá este estado de cuenta bancario y extraé todas las transacciones.
Devolvé ÚNICAMENTE un JSON válido con el siguiente esquema, sin texto adicional ni comentarios.

Las categorías disponibles del usuario son: {user_categories}
Asigná a cada transacción la categoría más apropiada de esa lista.
Si ninguna aplica, usá "Otros".

Detectá patrones de cuotas tipo "3/12", "Cuota 3 de 12", "Cuota 3/12" y completá
los campos installment_num e installment_tot en consecuencia.

Esquema JSON esperado:
{{
  "bank_name": "nombre del banco detectado",
  "card_last4": "últimos 4 dígitos si están disponibles, sino null",
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "currency": "UYU o USD",
  "transactions": [
    {{
      "date": "YYYY-MM-DD",
      "description": "descripción original del estado de cuenta",
      "merchant": "nombre limpio del comercio si se puede inferir",
      "amount": 1520.50,
      "currency": "UYU",
      "installment_num": null,
      "installment_tot": null,
      "suggested_category": "Comida"
    }}
  ]
}}
"""

    content = [{"type": "text", "text": prompt}]
    for img_b64 in pdf_images_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
        })

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        result = _try_parse_json(text)
        if result:
            return result
        
        raise GroqParseError(f"Respuesta inválida del modelo: {text[:200]}...")
    except GroqParseError:
        raise
    except Exception as exc:
        raise GroqParseError(f"Error al parsear PDF con Groq: {exc}") from exc
