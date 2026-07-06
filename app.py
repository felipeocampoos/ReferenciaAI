"""App Streamlit: validador de referencias con IA (Gemini 2.5 Flash).

Sube una o varias historias clínicas en PDF; cada una se evalúa contra la matriz
de criterios de inclusión/exclusión y se muestra un veredicto estructurado
individual con su justificación.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from criteria import load_criterios
from gemini_client import GeminiError, evaluar_referencia, get_api_key
from report_pdf import generar_reporte_lote_pdf, generar_reporte_pdf
from schema import Veredicto

st.set_page_config(
    page_title="Validador de referencias",
    page_icon="🏥",
    layout="wide",
)

_BANNER = {
    "Potencialmente aceptable": ("✅", st.success),
    "No aceptable": ("⛔", st.error),
    "Requiere aclaración": ("⚠️", st.warning),
}

if "resultados" not in st.session_state:
    st.session_state.resultados = []  # list[dict]: archivo, veredicto | None, error | None


def _evaluar_lote(pdfs, criterios) -> list[dict]:
    resultados: list[dict] = []
    total = len(pdfs)
    progreso = st.progress(0.0, text="Iniciando evaluación…")
    for i, pdf in enumerate(pdfs, start=1):
        progreso.progress((i - 1) / total, text=f"Evaluando {pdf.name} ({i}/{total})…")
        try:
            veredicto = evaluar_referencia(pdf.getvalue(), criterios)
            resultados.append({"archivo": pdf.name, "veredicto": veredicto, "error": None})
        except GeminiError as exc:
            resultados.append({"archivo": pdf.name, "veredicto": None, "error": str(exc)})
        except Exception as exc:
            resultados.append(
                {"archivo": pdf.name, "veredicto": None, "error": f"Error inesperado: {exc}"}
            )
    progreso.progress(1.0, text="Evaluación completa.")
    progreso.empty()
    return resultados


def _render_resumen_tabla(resultados: list[dict]) -> None:
    filas = []
    for r in resultados:
        v: Veredicto | None = r["veredicto"]
        if v is not None:
            filas.append(
                {
                    "Archivo": r["archivo"],
                    "Decisión": v.decision,
                    "Especialidad": v.especialidad_sugerida,
                    "Complejidad": v.complejidad,
                }
            )
        else:
            filas.append(
                {
                    "Archivo": r["archivo"],
                    "Decisión": "⚠️ Error",
                    "Especialidad": "—",
                    "Complejidad": "—",
                }
            )
    st.subheader("Resumen del lote")
    st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)


def _render_veredicto(archivo: str, v: Veredicto, key_suffix: str) -> None:
    icono, banner = _BANNER.get(v.decision, ("ℹ️", st.info))
    banner(f"{icono}  **{v.decision}**")

    col1, col2 = st.columns(2)
    col1.metric("Especialidad sugerida", v.especialidad_sugerida or "—")
    col2.metric("Complejidad", v.complejidad)

    st.markdown("**Resumen**")
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
        st.markdown("**Datos faltantes**")
        for d in v.datos_faltantes:
            st.markdown(f"- {d}")

    st.info(
        "🔒 Resultado **sugerido** por IA. Requiere validación médica humana antes "
        "de decidir la referencia."
    )

    nombre_base = os.path.splitext(archivo)[0]
    st.download_button(
        "Descargar reporte del paciente (PDF)",
        data=generar_reporte_pdf(archivo, v),
        file_name=f"reporte_{nombre_base}.pdf",
        mime="application/pdf",
        key=f"download_{key_suffix}",
    )


def _render_lote(resultados: list[dict]) -> None:
    st.divider()
    _render_resumen_tabla(resultados)

    st.subheader("Reportes individuales")
    expandir_todo = len(resultados) == 1
    for idx, r in enumerate(resultados):
        with st.expander(f"📄 {r['archivo']}", expanded=expandir_todo):
            if r["error"] is not None:
                st.error(r["error"])
            else:
                _render_veredicto(r["archivo"], r["veredicto"], key_suffix=f"{idx}_{r['archivo']}")

    st.download_button(
        f"Descargar los {len(resultados)} reportes en un solo PDF",
        data=generar_reporte_lote_pdf(resultados),
        file_name="reportes_lote.pdf",
        mime="application/pdf",
        key="download_lote",
    )


def main() -> None:
    st.title("🏥 Validador de referencias")
    st.caption(
        "Clínica Al Alba · Referencia y contrarreferencia — evaluación asistida por IA "
        "de historias clínicas contra la matriz de inclusión/exclusión."
    )

    if not get_api_key():
        st.warning(
            "No se detectó `GEMINI_API_KEY`. Configúrala en "
            "`.streamlit/secrets.toml` o como variable de entorno para poder evaluar."
        )

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

    pdfs = st.file_uploader(
        "Historias clínicas de los pacientes (PDF) — puedes seleccionar varias a la vez",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if pdfs:
        st.caption(f"{len(pdfs)} archivo(s) seleccionado(s).")

    if st.button("Evaluar referencia(s)", type="primary", disabled=not pdfs):
        st.session_state.resultados = _evaluar_lote(pdfs, criterios)

    if st.session_state.resultados:
        _render_lote(st.session_state.resultados)


if __name__ == "__main__":
    main()
