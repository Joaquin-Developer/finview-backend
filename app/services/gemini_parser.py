import json
from pathlib import Path
from typing import Any, Dict, List

import google.generativeai as genai

from ..config import get_settings


settings = get_settings()


class GeminiParseError(Exception):
    pass


def _clean_json_text(text: str) -> str:
    """
    Limpia posibles fences ```json ... ``` que Gemini pueda devolver.
    """
    text = text.strip()
    if text.startswith("```"):
        # remover el primer fence
        parts = text.split("```", 2)
        if len(parts) >= 2:
            inner = parts[1]
            # si empieza con "json" o similar, quitarlo
            inner = inner.lstrip()
            if inner.lower().startswith("json"):
                inner = inner[4:]
            return inner.strip()
    return text


def parse_statement_pdf(pdf_path: str, user_categories: List[str]) -> Dict[str, Any]:
    if not settings.GEMINI_API_KEY:
        raise GeminiParseError("GEMINI_API_KEY no está configurado")

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    pdf_bytes = Path(pdf_path).read_bytes()

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

    # Primer intento
    try:
        response = model.generate_content(
            [
                {"mime_type": "application/pdf", "data": pdf_bytes},
                prompt,
            ]
        )
        text = _clean_json_text(response.text or "")
        return json.loads(text)
    except Exception as exc:  # noqa: BLE001
        # Segundo intento con prompt simplificado
        try:
            simple_prompt = """
Extraé todas las transacciones de este estado de cuenta bancario.
Devolvé únicamente un JSON válido siguiendo exactamente este esquema:
<ESQUEMA_JSON>
"""
            response = model.generate_content(
                [
                    {"mime_type": "application/pdf", "data": pdf_bytes},
                    simple_prompt,
                ]
            )
            text = _clean_json_text(response.text or "")
            return json.loads(text)
        except Exception as exc2:  # noqa: BLE001
            raise GeminiParseError(f"Error al parsear PDF con Gemini: {exc2}") from exc

