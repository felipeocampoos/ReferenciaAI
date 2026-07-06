"""Wrapper de la llamada a Gemini 2.5 Flash con salida estructurada.

Envía el PDF de la historia clínica de forma nativa (inline) junto con los
criterios y devuelve una instancia validada de `Veredicto`.
"""

from __future__ import annotations

import os

from google import genai
from google.genai import types

from criteria import Criterios
from prompts import SYSTEM_INSTRUCTION, build_task_prompt
from schema import Veredicto

MODEL = "gemini-2.5-flash"
# Límite práctico para envío inline; por encima se usa la File API.
_INLINE_MAX_BYTES = 18 * 1024 * 1024


class GeminiError(RuntimeError):
    """Error al invocar el modelo o al parsear su respuesta."""


def get_api_key() -> str | None:
    """Obtiene la API key desde st.secrets o variable de entorno."""
    try:
        import streamlit as st

        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def _pdf_part(client: genai.Client, pdf_bytes: bytes) -> types.Part:
    """Crea la parte del PDF: inline si es pequeño, si no vía File API."""
    if len(pdf_bytes) <= _INLINE_MAX_BYTES:
        return types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    import io

    uploaded = client.files.upload(
        file=io.BytesIO(pdf_bytes),
        config=types.UploadFileConfig(mime_type="application/pdf"),
    )
    return uploaded


def evaluar_referencia(
    pdf_bytes: bytes,
    criterios: Criterios,
    api_key: str | None = None,
) -> Veredicto:
    """Evalúa una historia clínica en PDF y devuelve el veredicto estructurado.

    Lanza GeminiError si falta la key, falla la llamada o la respuesta no es válida.
    """
    key = api_key or get_api_key()
    if not key:
        raise GeminiError(
            "No se encontró la API key de Gemini. Configura GEMINI_API_KEY en "
            ".streamlit/secrets.toml o como variable de entorno."
        )
    if not pdf_bytes:
        raise GeminiError("El PDF está vacío o no se pudo leer.")

    client = genai.Client(api_key=key)

    try:
        pdf_part = _pdf_part(client, pdf_bytes)
        task_prompt = build_task_prompt(criterios)

        response = client.models.generate_content(
            model=MODEL,
            contents=[task_prompt, pdf_part],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=Veredicto,
                temperature=0.1,
            ),
        )
    except Exception as exc:  # errores de red/API
        raise GeminiError(f"Error al invocar Gemini: {exc}") from exc

    veredicto = getattr(response, "parsed", None)
    if isinstance(veredicto, Veredicto):
        veredicto.requiere_validacion_humana = True  # política fija
        return veredicto

    # Fallback: parsear el texto JSON manualmente.
    try:
        veredicto = Veredicto.model_validate_json(response.text)
        veredicto.requiere_validacion_humana = True
        return veredicto
    except Exception as exc:
        raise GeminiError(
            f"La respuesta del modelo no cumple el formato esperado: {exc}"
        ) from exc
