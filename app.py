"""App Streamlit: validador de referencias con IA (Gemini 3.8 Flash).

Interfaz institucional para el área de Referencia y Contrarreferencia. Permite
subir una o varias historias clínicas en PDF y evaluar cada una contra la matriz
de criterios de inclusión/exclusión, con un dashboard del lote y descarga de
reportes en PDF.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from criteria import MATRIZ_PATH, load_criterios
from gemini_client import GeminiError, evaluar_referencia, is_configured
from report_pdf import generar_reporte_lote_pdf, generar_reporte_pdf
from schema import Veredicto

APP_VERSION = "1.1.0"
COLOR_PRIMARIO = "#0F6AB4"
COLOR_TEXTO = "#1B2733"
COLOR_MUTED = "#5A6A78"
COLOR_FONDO_SUAVE = "#F2F6FA"

st.set_page_config(
    page_title="Validador de referencias — Clínica Al Alba",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

DECISION_META = {
    "Potencialmente aceptable": {"icono": "✅", "color": "#1E7E34", "banner": st.success},
    "No aceptable": {"icono": "⛔", "color": "#B02A37", "banner": st.error},
    "Requiere aclaración": {"icono": "⚠️", "color": "#B8860B", "banner": st.warning},
}

if "resultados" not in st.session_state:
    st.session_state.resultados = []  # list[dict]: archivo, veredicto | None, error | None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

@st.cache_data(show_spinner=False)
def _fecha_matriz(path_str: str) -> str | None:
    """Extrae la fecha de elaboración desde la hoja Resumen del Excel."""
    try:
        df = pd.read_excel(Path(path_str), sheet_name="Resumen", header=None)
        for _, row in df.iterrows():
            for j, cell in enumerate(row.tolist()):
                if isinstance(cell, str) and "fecha de elaboración" in cell.lower():
                    val = row.tolist()[j + 1] if j + 1 < len(row) else None
                    if hasattr(val, "strftime"):
                        return val.strftime("%Y-%m-%d")
                    if val:
                        return str(val)
        return None
    except Exception:
        return None


def _inject_estilo() -> None:
    """Estilos CSS mínimos para el branding institucional."""
    st.markdown(
        f"""
        <style>
        .app-header {{
            background: linear-gradient(135deg, {COLOR_PRIMARIO} 0%, #1583D4 100%);
            padding: 1.4rem 1.8rem 1.2rem 1.8rem;
            border-radius: 10px;
            color: #FFFFFF;
            margin-bottom: 1.5rem;
        }}
        .app-header .brand {{
            font-size: 0.85rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.85;
        }}
        .app-header .brand strong {{
            font-weight: 700;
        }}
        .app-header .titulo {{
            font-size: 1.7rem;
            font-weight: 700;
            margin: 0.35rem 0 0.15rem 0;
            line-height: 1.2;
        }}
        .app-header .subtitulo {{
            font-size: 0.95rem;
            opacity: 0.9;
        }}
        .app-header .chip {{
            display: inline-block;
            margin-top: 0.7rem;
            padding: 0.2rem 0.7rem;
            font-size: 0.75rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.18);
            color: #FFFFFF;
        }}
        .empty-state {{
            padding: 2rem 1.5rem;
            border: 1px dashed #C7D3DE;
            border-radius: 10px;
            background: {COLOR_FONDO_SUAVE};
            color: {COLOR_MUTED};
            text-align: center;
        }}
        .empty-state h4 {{
            color: {COLOR_TEXTO};
            margin-bottom: 0.4rem;
        }}
        .patient-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.8rem;
        }}
        .patient-header .archivo {{
            font-weight: 600;
            color: {COLOR_TEXTO};
            font-size: 1.05rem;
            overflow-wrap: anywhere;
        }}
        .decision-pill {{
            display: inline-block;
            padding: 0.25rem 0.8rem;
            border-radius: 999px;
            font-weight: 600;
            font-size: 0.85rem;
            color: #FFFFFF;
            white-space: nowrap;
        }}
        .footer-note {{
            color: {COLOR_MUTED};
            font-size: 0.8rem;
            text-align: center;
            margin-top: 2rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <div class="brand"><strong>Clínica Al Alba</strong> · Referencia y Contrarreferencia</div>
            <div class="titulo">Validador de referencias asistido por IA</div>
            <div class="subtitulo">Evaluación automatizada de historias clínicas contra la matriz institucional de inclusión y exclusión.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar(criterios, api_ok: bool) -> None:
    with st.sidebar:
        st.markdown("### Estado del sistema")
        st.markdown(f"- **Motor de IA:** {'✅ conectado' if api_ok else '⚠️ no configurado'}")
        fecha = _fecha_matriz(str(MATRIZ_PATH))
        st.markdown(f"- **Matriz:** {fecha or 'sin fecha registrada'}")
        st.markdown(
            f"- **Cobertura:** {criterios.total_inclusiones} inclusiones · "
            f"{criterios.total_exclusiones} exclusiones"
        )
        st.markdown(f"- **Especialidades base:** {len(criterios.especialidades)}")

        st.divider()
        st.markdown("### Cómo usar")
        st.markdown(
            "1. Sube una o varias historias clínicas en PDF.\n"
            "2. Pulsa **Evaluar referencias**.\n"
            "3. Revisa el dashboard y descarga el reporte del paciente o del lote."
        )

        st.divider()
        st.markdown("### Aviso")
        st.info(
            "El resultado es **sugerido** por IA. Requiere siempre validación médica "
            "humana antes de decidir la referencia."
        )

        st.divider()
        st.markdown("### Soporte")
        st.markdown(
            f"- **Versión:** {APP_VERSION}\n"
            "- **Contacto:** referencia@clinicaalalba.co"
        )


# --------------------------------------------------------------------------- #
# Evaluación
# --------------------------------------------------------------------------- #

def _evaluar_lote(pdfs, criterios) -> list[dict]:
    resultados: list[dict] = []
    total = len(pdfs)
    with st.status(f"Evaluando {total} historia(s) clínica(s)…", expanded=True) as status:
        for i, pdf in enumerate(pdfs, start=1):
            status.write(f"📄 Procesando **{pdf.name}** ({i}/{total})")
            try:
                veredicto = evaluar_referencia(pdf.getvalue(), criterios)
                resultados.append({"archivo": pdf.name, "veredicto": veredicto, "error": None})
            except GeminiError as exc:
                resultados.append({"archivo": pdf.name, "veredicto": None, "error": str(exc)})
            except Exception as exc:
                resultados.append(
                    {"archivo": pdf.name, "veredicto": None, "error": f"Error inesperado: {exc}"}
                )
        status.update(label="Evaluación completa", state="complete", expanded=False)
    return resultados


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

def _render_metricas(resultados: list[dict]) -> None:
    total = len(resultados)
    aceptables = sum(1 for r in resultados if r["veredicto"] and r["veredicto"].decision == "Potencialmente aceptable")
    no_aceptables = sum(1 for r in resultados if r["veredicto"] and r["veredicto"].decision == "No aceptable")
    aclaracion = sum(1 for r in resultados if r["veredicto"] and r["veredicto"].decision == "Requiere aclaración")
    errores = sum(1 for r in resultados if r["veredicto"] is None)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total evaluado", total)
    c2.metric("✅ Aceptables", aceptables)
    c3.metric("⛔ No aceptables", no_aceptables)
    c4.metric("⚠️ Requieren aclaración", aclaracion)
    c5.metric("⚙️ Errores", errores)


def _render_tabla(resultados: list[dict]) -> None:
    filas = []
    for r in resultados:
        v: Veredicto | None = r["veredicto"]
        if v is not None:
            meta = DECISION_META.get(v.decision, {"icono": "ℹ️"})
            filas.append(
                {
                    "Estado": f"{meta['icono']} {v.decision}",
                    "Archivo": r["archivo"],
                    "Especialidad sugerida": v.especialidad_sugerida or "—",
                    "Complejidad": v.complejidad,
                    "Criterios INC": len(v.criterios_inclusion),
                    "Criterios EXC": len(v.criterios_exclusion),
                }
            )
        else:
            filas.append(
                {
                    "Estado": "⚙️ Error",
                    "Archivo": r["archivo"],
                    "Especialidad sugerida": "—",
                    "Complejidad": "—",
                    "Criterios INC": 0,
                    "Criterios EXC": 0,
                }
            )
    st.dataframe(
        pd.DataFrame(filas),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Estado": st.column_config.TextColumn("Estado", width="medium"),
            "Archivo": st.column_config.TextColumn("Archivo", width="large"),
            "Criterios INC": st.column_config.NumberColumn("INC", width="small"),
            "Criterios EXC": st.column_config.NumberColumn("EXC", width="small"),
        },
    )


def _render_patient_card(archivo: str, v: Veredicto, key_suffix: str) -> None:
    meta = DECISION_META.get(v.decision, {"icono": "ℹ️", "color": "#6C757D"})
    st.markdown(
        f"""
        <div class="patient-header">
            <div class="archivo">📄 {archivo}</div>
            <span class="decision-pill" style="background:{meta['color']};">
                {meta['icono']} {v.decision}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    col1.markdown(f"**Especialidad sugerida**  \n{v.especialidad_sugerida or '—'}")
    col2.markdown(f"**Complejidad**  \n{v.complejidad}")

    st.markdown("**Resumen clínico**")
    st.write(v.resumen)

    n_inc = len(v.criterios_inclusion)
    n_exc = len(v.criterios_exclusion)
    n_faltantes = len(v.datos_faltantes)
    tab_labels = [
        f"Inclusiones ({n_inc})",
        f"Exclusiones ({n_exc})",
        f"Datos faltantes ({n_faltantes})",
    ]
    tab_inc, tab_exc, tab_dat = st.tabs(tab_labels)

    with tab_inc:
        if v.criterios_inclusion:
            for c in v.criterios_inclusion:
                st.markdown(f"**{c.id} — {c.condicion}**")
                st.caption(c.justificacion)
        else:
            st.caption("Sin criterios de inclusión coincidentes.")

    with tab_exc:
        if v.criterios_exclusion:
            for c in v.criterios_exclusion:
                st.markdown(f"**{c.id} — {c.condicion}**")
                st.caption(c.justificacion)
        else:
            st.caption("Sin criterios de exclusión coincidentes.")

    with tab_dat:
        if v.datos_faltantes:
            for d in v.datos_faltantes:
                st.markdown(f"- {d}")
        else:
            st.caption("No se identificaron datos faltantes.")

    nombre_base = os.path.splitext(archivo)[0]
    _, col_btn = st.columns([3, 1])
    col_btn.download_button(
        "⬇️ Descargar reporte (PDF)",
        data=generar_reporte_pdf(archivo, v),
        file_name=f"reporte_{nombre_base}.pdf",
        mime="application/pdf",
        key=f"download_{key_suffix}",
        use_container_width=True,
    )


def _render_error_card(archivo: str, error: str) -> None:
    st.markdown(
        f"""
        <div class="patient-header">
            <div class="archivo">📄 {archivo}</div>
            <span class="decision-pill" style="background:#6C757D;">⚙️ Error</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.error(error)


def _render_dashboard(resultados: list[dict]) -> None:
    st.subheader("Resumen del lote")
    _render_metricas(resultados)
    st.markdown("")
    _render_tabla(resultados)

    st.divider()
    st.subheader("Reportes por paciente")

    for idx, r in enumerate(resultados):
        with st.container(border=True):
            if r["error"] is not None:
                _render_error_card(r["archivo"], r["error"])
            else:
                _render_patient_card(r["archivo"], r["veredicto"], key_suffix=f"{idx}_{r['archivo']}")

    st.divider()
    col_lote, col_limpiar = st.columns([2, 1])
    col_lote.download_button(
        f"⬇️ Descargar los {len(resultados)} reportes en un solo PDF",
        data=generar_reporte_lote_pdf(resultados),
        file_name="reportes_lote.pdf",
        mime="application/pdf",
        key="download_lote",
        use_container_width=True,
        type="primary",
    )
    if col_limpiar.button("🗑️ Limpiar resultados", use_container_width=True):
        st.session_state.resultados = []
        st.rerun()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    _inject_estilo()
    _render_header()

    api_ok = is_configured()
    try:
        criterios = load_criterios()
    except Exception as exc:
        st.error(f"No se pudo cargar la matriz de criterios: {exc}")
        st.stop()

    _render_sidebar(criterios, api_ok)

    if not api_ok:
        st.warning(
            "El motor de IA no está configurado. Contacte al administrador de la "
            "aplicación para completar la configuración antes de evaluar."
        )

    st.subheader("1. Cargar historias clínicas")
    pdfs = st.file_uploader(
        "Historias clínicas del paciente en PDF (puedes seleccionar varias a la vez)",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if pdfs:
        st.caption(f"{len(pdfs)} archivo(s) seleccionado(s).")

    st.subheader("2. Evaluar")
    if st.button(
        "Evaluar referencias",
        type="primary",
        disabled=not pdfs or not api_ok,
    ):
        st.session_state.resultados = _evaluar_lote(pdfs, criterios)

    st.divider()

    if st.session_state.resultados:
        _render_dashboard(st.session_state.resultados)
    else:
        st.markdown(
            """
            <div class="empty-state">
                <h4>📥 Aún no hay evaluaciones</h4>
                Sube una o varias historias clínicas en PDF y pulsa <em>Evaluar referencias</em>
                para obtener el veredicto y descargar los reportes por paciente.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div class='footer-note'>Clínica Al Alba · Referencia y Contrarreferencia · "
        f"v{APP_VERSION}</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
