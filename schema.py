"""Modelos Pydantic que definen el contrato de salida del validador.

Se pasan como `response_schema` a Gemini para forzar una respuesta JSON
estructurada y validada. Los `Literal` se traducen a `enum` en el schema del
modelo, de modo que Gemini solo puede devolver valores permitidos (alineados con
la hoja *Catalogos* de la matriz).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal[
    "Potencialmente aceptable",
    "No aceptable",
    "Requiere aclaración",
]

Complejidad = Literal[
    "Baja",
    "Mediana",
    "Mediana / Alta",
    "Alta",
    "No determinada",
]


class CriterioCoincidente(BaseModel):
    """Un criterio de la matriz (inclusión o exclusión) que aplica al caso."""

    id: str = Field(description='Identificador del criterio, p.ej. "INC-001" o "EXC-012".')
    condicion: str = Field(description="Texto de la condición de la matriz que coincide.")
    justificacion: str = Field(
        description="Por qué aplica este criterio según la historia clínica del PDF."
    )


class Veredicto(BaseModel):
    """Resultado estructurado de la evaluación de una referencia."""

    decision: Decision = Field(
        description="Decisión sugerida para la referencia."
    )
    especialidad_sugerida: str = Field(
        description=(
            "Especialidad institucional relacionada con el caso, tomada de la lista "
            "de especialidades base. Usar 'No aplica' si ninguna corresponde."
        )
    )
    complejidad: Complejidad = Field(
        description="Complejidad clínica estimada del caso."
    )
    criterios_inclusion: list[CriterioCoincidente] = Field(
        default_factory=list,
        description="Criterios de inclusión (INC-###) que coinciden con la historia.",
    )
    criterios_exclusion: list[CriterioCoincidente] = Field(
        default_factory=list,
        description="Criterios de exclusión (EXC-###) que coinciden con la historia.",
    )
    datos_faltantes: list[str] = Field(
        default_factory=list,
        description=(
            "Información clínica ausente en el PDF que impide o condiciona la decisión. "
            "Debe poblarse cuando la decisión sea 'Requiere aclaración'."
        ),
    )
    resumen: str = Field(
        description="Párrafo corto en español explicando las razones de la decisión."
    )
    requiere_validacion_humana: bool = Field(
        default=True,
        description="Siempre verdadero: la decisión final es del equipo médico.",
    )
