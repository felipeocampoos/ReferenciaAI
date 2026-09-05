"""Genera reportes en PDF institucionales a partir de un Veredicto.

Cada página lleva encabezado con marca de la Clínica Al Alba y pie con paginación
y aviso legal. El cuerpo incluye tabla de metadatos (archivo, fecha, ID de
evaluación, modelo), banner de decisión con fondo de color y secciones de
resumen, criterios y datos faltantes.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from schema import Veredicto

INSTITUCION = "Clínica Al Alba"
UNIDAD = "Referencia y Contrarreferencia"

_PRIMARIO = colors.HexColor("#0F6AB4")
_MUTED = colors.HexColor("#5A6A78")
_LINEA = colors.HexColor("#D6E1EA")
_TEXTO = colors.HexColor("#1B2733")

_DECISION_BG = {
    "Potencialmente aceptable": colors.HexColor("#1E7E34"),
    "No aceptable": colors.HexColor("#B02A37"),
    "Requiere aclaración": colors.HexColor("#B8860B"),
}

_MARGIN_LEFT = 2 * cm
_MARGIN_RIGHT = 2 * cm
_MARGIN_TOP = 3 * cm
_MARGIN_BOTTOM = 2.2 * cm


# --------------------------------------------------------------------------- #
# Estilos
# --------------------------------------------------------------------------- #

def _styles():
    s = getSampleStyleSheet()
    if "TituloSeccion" not in s:
        s.add(
            ParagraphStyle(
                name="TituloSeccion",
                fontName="Helvetica-Bold",
                fontSize=11,
                textColor=_PRIMARIO,
                spaceBefore=10,
                spaceAfter=4,
                leading=14,
            )
        )
    if "Cuerpo" not in s:
        s.add(
            ParagraphStyle(
                name="Cuerpo",
                fontName="Helvetica",
                fontSize=10,
                textColor=_TEXTO,
                leading=14,
                alignment=TA_LEFT,
            )
        )
    if "CuerpoItalico" not in s:
        s.add(
            ParagraphStyle(
                name="CuerpoItalico",
                fontName="Helvetica-Oblique",
                fontSize=9,
                textColor=_MUTED,
                leading=12,
            )
        )
    if "Etiqueta" not in s:
        s.add(
            ParagraphStyle(
                name="Etiqueta",
                fontName="Helvetica",
                fontSize=9,
                textColor=_MUTED,
                leading=12,
            )
        )
    if "Aviso" not in s:
        s.add(
            ParagraphStyle(
                name="Aviso",
                fontName="Helvetica-Oblique",
                fontSize=9,
                textColor=_MUTED,
                leading=12,
                alignment=TA_CENTER,
            )
        )
    return s


# --------------------------------------------------------------------------- #
# Encabezado y pie de página
# --------------------------------------------------------------------------- #

def _header_footer(canvas: Canvas, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    ancho, alto = letter

    # Franja superior
    canvas.setFillColor(_PRIMARIO)
    canvas.rect(0, alto - 1.2 * cm, ancho, 1.2 * cm, fill=1, stroke=0)

    # Textos del encabezado (dentro de la franja)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(_MARGIN_LEFT, alto - 0.75 * cm, INSTITUCION)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(_MARGIN_LEFT, alto - 1.05 * cm, UNIDAD)

    # Fecha del reporte a la derecha
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(ancho - _MARGIN_RIGHT, alto - 0.75 * cm, "Reporte generado")
    canvas.drawRightString(ancho - _MARGIN_RIGHT, alto - 1.05 * cm, fecha)

    # Título de la herramienta (bajo la franja)
    canvas.setFillColor(_PRIMARIO)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(_MARGIN_LEFT, alto - 1.75 * cm, "Validador de referencias asistido por IA")

    # Línea separadora
    canvas.setStrokeColor(_LINEA)
    canvas.setLineWidth(0.5)
    canvas.line(_MARGIN_LEFT, alto - 1.95 * cm, ancho - _MARGIN_RIGHT, alto - 1.95 * cm)

    # Pie de página
    canvas.setFillColor(_MUTED)
    canvas.setFont("Helvetica-Oblique", 8)
    canvas.drawString(
        _MARGIN_LEFT,
        1.2 * cm,
        "Reporte generado por IA. Requiere validación médica humana antes de decidir la referencia.",
    )
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(
        ancho - _MARGIN_RIGHT,
        1.2 * cm,
        f"Página {doc.page}",
    )
    canvas.setStrokeColor(_LINEA)
    canvas.line(_MARGIN_LEFT, 1.5 * cm, ancho - _MARGIN_RIGHT, 1.5 * cm)

    canvas.restoreState()


def _build_doc(buffer: io.BytesIO) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=_MARGIN_LEFT,
        rightMargin=_MARGIN_RIGHT,
        topMargin=_MARGIN_TOP,
        bottomMargin=_MARGIN_BOTTOM,
        title="Reporte de evaluación de referencia",
        author=INSTITUCION,
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="cuerpo",
    )
    doc.addPageTemplates([PageTemplate(id="con_encabezado", frames=[frame], onPage=_header_footer)])
    return doc


# --------------------------------------------------------------------------- #
# Componentes del cuerpo
# --------------------------------------------------------------------------- #

def _tabla_metadatos(archivo: str, eval_id: str, styles) -> Table:
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    data = [
        ["Archivo evaluado", archivo],
        ["Fecha de evaluación", fecha],
        ["ID de evaluación", eval_id],
        ["Evaluado por", "Validador asistido por IA"],
    ]
    tabla = Table(data, colWidths=[4.5 * cm, 12 * cm])
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F6FA")),
                ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
                ("TEXTCOLOR", (1, 0), (1, -1), _TEXTO),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, _LINEA),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tabla


def _banner_decision(decision: str) -> Table:
    bg = _DECISION_BG.get(decision, colors.HexColor("#6C757D"))
    p = Paragraph(
        f'<font color="white" size="13"><b>Decisión: {decision}</b></font>',
        ParagraphStyle(name="banner", fontName="Helvetica-Bold", fontSize=13, textColor=colors.white),
    )
    tabla = Table([[p]], colWidths=[16.5 * cm])
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return tabla


def _tabla_metricas(archivo: str, especialidad: str, complejidad: str) -> Table:
    data = [
        ["Especialidad sugerida", especialidad or "—"],
        ["Complejidad", complejidad],
    ]
    tabla = Table(data, colWidths=[4.5 * cm, 12 * cm])
    tabla.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
                ("TEXTCOLOR", (1, 0), (1, -1), _TEXTO),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, _LINEA),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tabla


def _story_paciente(archivo: str, v: Veredicto | None, error: str | None, styles) -> list:
    story: list = []
    eval_id = uuid.uuid4().hex[:12].upper()

    story.append(_tabla_metadatos(archivo, eval_id, styles))
    story.append(Spacer(1, 12))

    if v is None:
        story.append(
            _banner_decision("Error de evaluación")
            if False
            else Paragraph(
                '<font color="#B02A37" size="13"><b>No fue posible evaluar este archivo</b></font>',
                styles["Cuerpo"],
            )
        )
        story.append(Spacer(1, 8))
        story.append(Paragraph(error or "Error desconocido.", styles["Cuerpo"]))
        story.append(Spacer(1, 10))
        story.append(
            Paragraph(
                "Este reporte forma parte de la evaluación asistida por IA para el área "
                "de Referencia y Contrarreferencia. Requiere validación médica humana.",
                styles["Aviso"],
            )
        )
        return story

    story.append(_banner_decision(v.decision))
    story.append(Spacer(1, 12))
    story.append(_tabla_metricas(archivo, v.especialidad_sugerida, v.complejidad))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Resumen clínico", styles["TituloSeccion"]))
    story.append(Paragraph(v.resumen, styles["Cuerpo"]))

    if v.criterios_inclusion:
        story.append(
            Paragraph(
                f"Criterios de inclusión coincidentes ({len(v.criterios_inclusion)})",
                styles["TituloSeccion"],
            )
        )
        for c in v.criterios_inclusion:
            story.append(Paragraph(f"<b>{c.id}</b> — {c.condicion}", styles["Cuerpo"]))
            story.append(Paragraph(c.justificacion, styles["Etiqueta"]))
            story.append(Spacer(1, 4))

    if v.criterios_exclusion:
        story.append(
            Paragraph(
                f"Criterios de exclusión coincidentes ({len(v.criterios_exclusion)})",
                styles["TituloSeccion"],
            )
        )
        for c in v.criterios_exclusion:
            story.append(Paragraph(f"<b>{c.id}</b> — {c.condicion}", styles["Cuerpo"]))
            story.append(Paragraph(c.justificacion, styles["Etiqueta"]))
            story.append(Spacer(1, 4))

    if v.datos_faltantes:
        story.append(Paragraph("Datos faltantes en la historia", styles["TituloSeccion"]))
        for d in v.datos_faltantes:
            story.append(Paragraph(f"• {d}", styles["Cuerpo"]))

    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            "Resultado sugerido por IA. Requiere validación médica humana antes de "
            "decidir la referencia.",
            styles["Aviso"],
        )
    )
    return story


# --------------------------------------------------------------------------- #
# Portada del lote
# --------------------------------------------------------------------------- #

def _story_portada_lote(resultados: list[dict], styles) -> list:
    total = len(resultados)
    aceptables = sum(1 for r in resultados if r.get("veredicto") and r["veredicto"].decision == "Potencialmente aceptable")
    no_aceptables = sum(1 for r in resultados if r.get("veredicto") and r["veredicto"].decision == "No aceptable")
    aclaracion = sum(1 for r in resultados if r.get("veredicto") and r["veredicto"].decision == "Requiere aclaración")
    errores = sum(1 for r in resultados if r.get("veredicto") is None)

    story: list = []
    story.append(Paragraph("Reporte consolidado del lote", styles["TituloSeccion"]))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            f"Se evaluaron {total} historia(s) clínica(s) contra la matriz institucional "
            f"de inclusión y exclusión.",
            styles["Cuerpo"],
        )
    )
    story.append(Spacer(1, 10))

    header = [
        "Total",
        "Potencialmente aceptables",
        "No aceptables",
        "Requieren aclaración",
        "Errores",
    ]
    valores = [str(total), str(aceptables), str(no_aceptables), str(aclaracion), str(errores)]
    tabla = Table([header, valores], colWidths=[3.3 * cm] * 5)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _PRIMARIO),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, 1), 16),
                ("TEXTCOLOR", (0, 1), (-1, 1), _TEXTO),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F2F6FA")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, _LINEA),
            ]
        )
    )
    story.append(tabla)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Detalle por paciente", styles["TituloSeccion"]))
    detalle_data = [["#", "Archivo", "Decisión", "Especialidad", "Complejidad"]]
    for i, r in enumerate(resultados, start=1):
        v: Veredicto | None = r.get("veredicto")
        if v is not None:
            detalle_data.append(
                [str(i), r["archivo"], v.decision, v.especialidad_sugerida or "—", v.complejidad]
            )
        else:
            detalle_data.append([str(i), r["archivo"], "Error", "—", "—"])

    tabla_detalle = Table(detalle_data, colWidths=[0.8 * cm, 6 * cm, 4.4 * cm, 3.2 * cm, 2.1 * cm])
    tabla_detalle.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _PRIMARIO),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.3, _LINEA),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(tabla_detalle)
    return story


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #

def generar_reporte_pdf(archivo: str, v: Veredicto) -> bytes:
    """Genera el PDF del reporte de un único paciente y devuelve sus bytes."""
    buffer = io.BytesIO()
    doc = _build_doc(buffer)
    styles = _styles()
    doc.build(_story_paciente(archivo, v, None, styles))
    return buffer.getvalue()


def generar_reporte_lote_pdf(resultados: list[dict]) -> bytes:
    """Genera un PDF combinado: portada del lote + una página por paciente."""
    buffer = io.BytesIO()
    doc = _build_doc(buffer)
    styles = _styles()
    story: list = []

    story.extend(_story_portada_lote(resultados, styles))
    if resultados:
        story.append(PageBreak())

    for i, r in enumerate(resultados):
        story.extend(_story_paciente(r["archivo"], r.get("veredicto"), r.get("error"), styles))
        if i < len(resultados) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buffer.getvalue()
