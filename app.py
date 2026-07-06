"""App Streamlit: validador de referencias con IA (Gemini 2.5 Flash).

Sube una historia clínica en PDF, la evalúa contra la matriz de criterios de
inclusión/exclusión y muestra un veredicto estructurado con su justificación.
"""

from __future__ import annotations

import json

import streamlit as st

from criteria import load_criterios
from gemini_client import GeminiError, evaluar_referencia, get_api_key
from schema import Veredicto

st.set_page_config(
    page_title="Validador de referencias",
    page_icon="🏥",
    layout="centered",
)

_BANNER = {
    "Potencialmente aceptable": ("✅", st.success),
    "No aceptable": ("⛔", st.error),
    "Requiere aclaración": ("⚠️", st.warning),
}


def _render_veredicto(v: Veredicto) -> None:
    icono, banner = _BANNER.get(v.decision, ("ℹ️", st.info))
    banner(f"{icono}  **{v.decision}**")

    col1, col2 = st.columns(2)
    col1.metric("Especialidad sugerida", v.especialidad_sugerida or "—")
    col2.metric("Complejidad", v.complejidad)

    st.subheader("Resumen")
    st.write(v.resumen)

    if v.criterios_inclusion:
        with st.expander(f"Criterios de inclusión coincidentes ({len(v.criterios_inclusion)})", expanded=True):
            for c in v.criterios_inclusion:
                st.markdown(f"**{c.id} — {c.condicion}**")
                st.caption(c.justificacion)

    if v.criterios_exclusion:
        with st.expander(f"Criterios de exclusión coincidentes ({len(v.criterios_exclusion)})", expanded=True):
            for c in v.criterios_exclusion:
                st.markdown(f"**{c.id} — {c.condicion}**")
                st.caption(c.justificacion)

    if v.datos_faltantes:
        st.subheader("Datos faltantes")
        for d in v.datos_faltantes:
            st.markdown(f"- {d}")

    st.info(
        "🔒 Resultado **sugerido** por IA. Requiere validación médica humana antes "
        "de decidir la referencia."
    )

    st.download_button(
        "Descargar veredicto (JSON)",
        data=json.dumps(v.model_dump(), ensure_ascii=False, indent=2),
        file_name="veredicto_referencia.json",
        mime="application/json",
    )


def main() -> None:
    st.title("🏥 Validador de referencias")
    st.caption(
        "Clínica Al Alba · Referencia y contrarreferencia — evaluación asistida por IA "
        "de historias clínicas contra la matriz de inclusión/exclusión."
    )

    # Estado de la API key.
    if not get_api_key():
        st.warning(
            "No se detectó `GEMINI_API_KEY`. Configúrala en "
            "`.streamlit/secrets.toml` o como variable de entorno para poder evaluar."
        )

    # Carga de criterios (cacheada).
    try:
        criterios = load_criterios()
    except Exception as exc:
        st.error(f"No se pudo cargar la matriz de criterios: {exc}")
        st.stop()

    st.caption(
        f"Matriz cargada: {criterios.total_inclusiones} inclusiones · "
        f"{criterios.total_exclusiones} exclusiones · "
        f"{len(criterios.especialidades)} especialidades base."
    )

    pdf = st.file_uploader("Historia clínica del paciente (PDF)", type=["pdf"])

    if st.button("Evaluar referencia", type="primary", disabled=pdf is None):
        pdf_bytes = pdf.getvalue() if pdf is not None else b""
        with st.spinner("Analizando la historia clínica con Gemini 2.5 Flash…"):
            try:
                veredicto = evaluar_referencia(pdf_bytes, criterios)
            except GeminiError as exc:
                st.error(str(exc))
                return
            except Exception as exc:
                st.error(f"Error inesperado: {exc}")
                return
        st.divider()
        _render_veredicto(veredicto)


if __name__ == "__main__":
    main()
