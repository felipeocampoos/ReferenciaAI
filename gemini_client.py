"""Wrapper de la llamada al modelo de IA con salida estructurada.

Usa **Vertex AI** (proyecto de Google Cloud con cuota dedicada) cuando hay
credenciales de service account disponibles; si no las encuentra, cae a la
API key de AI Studio (Gemini Developer API) como respaldo.

Envía el PDF de la historia clínica de forma nativa (inline) junto con los
criterios y devuelve una instancia validada de `Veredicto`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from google import genai
from google.genai import types

from criteria import Criterios
from prompts import SYSTEM_INSTRUCTION, build_task_prompt
from schema import Veredicto

MODEL = "gemini-3.1-flash-lite"
VERTEX_LOCATION_DEFAULT = "global"
# Límite práctico para envío inline; por encima se usa la File API.
_INLINE_MAX_BYTES = 18 * 1024 * 1024
_LOCAL_SA_KEY_PATH = Path(__file__).parent / ".streamlit" / "vertex-sa-key.json"


class GeminiError(RuntimeError):
    """Error al invocar el modelo o al parsear su respuesta."""


def _get_secret(name: str):
    try:
        import streamlit as st

        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return None


def get_api_key() -> str | None:
    """Obtiene la API key de AI Studio (respaldo) desde st.secrets o env."""
    val = _get_secret("GEMINI_API_KEY")
    if val:
        return val
    return os.environ.get("GEMINI_API_KEY")


def _vertex_credentials_and_project():
    """Construye credenciales de Vertex AI desde, en orden de prioridad:

    1. `st.secrets["gcp_service_account"]` (tabla TOML con el JSON del SA).
    2. Archivo JSON local en `.streamlit/vertex-sa-key.json`.
    3. Variable de entorno `GOOGLE_APPLICATION_CREDENTIALS`.

    Devuelve (credentials, project, location) o (None, None, None) si no hay
    ninguna fuente disponible.
    """
    from google.oauth2 import service_account

    info = None
    sa_secret = _get_secret("gcp_service_account")
    if sa_secret:
        info = dict(sa_secret)
    elif _LOCAL_SA_KEY_PATH.exists():
        info = json.loads(_LOCAL_SA_KEY_PATH.read_text())
    else:
        env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if env_path and Path(env_path).exists():
            info = json.loads(Path(env_path).read_text())

    if not info:
        return None, None, None

    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    project = (
        info.get("project_id")
        or _get_secret("VERTEX_PROJECT")
        or os.environ.get("VERTEX_PROJECT")
    )
    location = (
        _get_secret("VERTEX_LOCATION")
        or os.environ.get("VERTEX_LOCATION")
        or VERTEX_LOCATION_DEFAULT
    )
    return credentials, project, location


def is_configured() -> bool:
    """True si hay credenciales de Vertex AI o una API key disponibles."""
    credentials, project, _ = _vertex_credentials_and_project()
    if credentials and project:
        return True
    return bool(get_api_key())


def _build_client() -> genai.Client:
    """Construye el cliente: Vertex AI si hay credenciales, si no la API key."""
    credentials, project, location = _vertex_credentials_and_project()
    if credentials and project:
        return genai.Client(
            vertexai=True,
            credentials=credentials,
            project=project,
            location=location,
        )

    key = get_api_key()
    if key:
        return genai.Client(api_key=key)

    raise GeminiError(
        "No se encontró configuración del motor de IA. Contacte al "
        "administrador para completar la configuración."
    )


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

    Lanza GeminiError si falta la configuración, falla la llamada o la
    respuesta no es válida. `api_key` permite forzar el uso de AI Studio en
    vez de Vertex AI (útil para pruebas puntuales).
    """
    if not pdf_bytes:
        raise GeminiError("El PDF está vacío o no se pudo leer.")

    try:
        client = genai.Client(api_key=api_key) if api_key else _build_client()
    except GeminiError:
        raise
    except Exception as exc:
        raise GeminiError(f"No se pudo inicializar el motor de IA: {exc}") from exc

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
        raise GeminiError(f"Error al invocar el motor de IA: {exc}") from exc

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
