"""Genera reportes en PDF a partir de un Veredicto, para descarga individual
por paciente (o combinada para todo un lote)."""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from schema import Veredicto

_DECISION_COLORS = {
    "Potencialmente aceptable": colors.HexColor("#1e7e34"),
    "No aceptable": colors.HexColor("#b02a37"),
    "Requiere aclaración": colors.HexColor("#b8860b"),
}

_MARGINS = dict(topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm)


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(name="TituloReporte", fontSize=16, leading=20, spaceAfter=6, alignment=TA_CENTER)
    )
    styles.add(ParagraphStyle(name="Etiqueta", fontSize=9, textColor=colors.grey))
    styles.add(ParagraphStyle(name="Cuerpo", fontSize=10, leading=14))
    styles.add(ParagraphStyle(name="Aviso", fontSize=9, textColor=colors.HexColor("#555555")))
    return styles


def _build_story(archivo: str, v: Veredicto | None, error: str | None, styles) -> list:
    story: list = []
    story.append(Paragraph("Validador de referencias — Clínica Al Alba", styles["TituloReporte"]))
    story.append(Paragraph(f"Reporte generado: {datetime.now():%Y-%m-%d %H:%M}", styles["Etiqueta"]))
    story.append(Paragraph(f"Archivo evaluado: {archivo}", styles["Etiqueta"]))
    story.append(Spacer(1, 12))

    if v is None:
        story.append(Paragraph("No fue posible evaluar este archivo.", styles["Heading3"]))
        story.append(Paragraph(error or "Error desconocido.", styles["Cuerpo"]))
        return story

    color = _DECISION_COLORS.get(v.decision, colors.black)
    decision_style = ParagraphStyle(name="Decision", parent=styles["Heading2"], textColor=color)
    story.append(Paragraph(f"Decisión: {v.decision}", decision_style))
    story.append(Spacer(1, 6))

    tabla = Table(
        [
            ["Especialidad sugerida", v.especialidad_sugerida or "—"],
            ["Complejidad", v.complejidad],
        ],
        colWidths=[6 * cm, 10 * cm],
    )
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(tabla)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Resumen", styles["Heading3"]))
    story.append(Paragraph(v.resumen, styles["Cuerpo"]))
    story.append(Spacer(1, 10))

    if v.criterios_inclusion:
        story.append(
            Paragraph(f"Criterios de inclusión coincidentes ({len(v.criterios_inclusion)})", styles["Heading3"])
        )
        for c in v.criterios_inclusion:
            story.append(Paragraph(f"<b>{c.id}</b> — {c.condicion}", styles["Cuerpo"]))
            story.append(Paragraph(c.justificacion, styles["Etiqueta"]))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 6))

    if v.criterios_exclusion:
        story.append(
            Paragraph(f"Criterios de exclusión coincidentes ({len(v.criterios_exclusion)})", styles["Heading3"])
        )
        for c in v.criterios_exclusion:
            story.append(Paragraph(f"<b>{c.id}</b> — {c.condicion}", styles["Cuerpo"]))
            story.append(Paragraph(c.justificacion, styles["Etiqueta"]))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 6))

    if v.datos_faltantes:
        story.append(Paragraph("Datos faltantes", styles["Heading3"]))
        for d in v.datos_faltantes:
            story.append(Paragraph(f"• {d}", styles["Cuerpo"]))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Resultado sugerido por IA. Requiere validación médica humana antes de decidir la referencia.",
            styles["Aviso"],
        )
    )
    return story


def generar_reporte_pdf(archivo: str, v: Veredicto) -> bytes:
    """Genera el PDF del reporte de un único paciente y devuelve sus bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, **_MARGINS)
    doc.build(_build_story(archivo, v, None, _styles()))
    return buffer.getvalue()


def generar_reporte_lote_pdf(resultados: list[dict]) -> bytes:
    """Genera un único PDF con el reporte de cada paciente evaluado en el lote."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, **_MARGINS)
    styles = _styles()
    story: list = []
    for i, r in enumerate(resultados):
        story.extend(_build_story(r["archivo"], r.get("veredicto"), r.get("error"), styles))
        if i < len(resultados) - 1:
            story.append(PageBreak())
    doc.build(story)
    return buffer.getvalue()
