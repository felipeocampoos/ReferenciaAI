"""Carga los criterios clínicos desde la matriz Excel y los convierte en bloques
de texto compactos para incrustar en el prompt de Gemini.

Solo se usan las hojas *Inclusiones* y *Exclusiones* (razonamiento clínico) más
la lista de especialidades base de *Catalogos*. Las columnas pesadas de CUPS se
descartan para mantener el prompt liviano.

La lectura se hace en runtime (con caché) para que editar el Excel se refleje sin
tocar código.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

MATRIZ_PATH = Path(__file__).with_name("matriz_inclusion_exclusion_referencias.xlsx")

# Columnas clínicas que queremos de cada hoja (por etiqueta amigable -> subcadena
# normalizada a buscar en el encabezado real). Se usa coincidencia flexible para
# tolerar diferencias de acentos/espacios.
_INCLUSION_COLS = {
    "ID": "id",
    "Eje clínico": "eje clinico",
    "Especialidad líder": "especialidad lider",
    "Condición de inclusión": "condicion de inclusion",
    "Diagnósticos / palabras clave": "diagnosticos",
    "Complejidad esperada": "complejidad esperada",
    "Prioridad clínica": "prioridad clinica",
    "Criterios mínimos de aceptación": "criterios minimos",
    "Alertas / validación diferencial": "alertas",
}

_EXCLUSION_COLS = {
    "ID": "id",
    "Eje clínico": "eje clinico",
    "Condición de exclusión": "condicion de exclusion",
    "Diagnósticos / palabras clave": "diagnosticos",
    "Motivo de exclusión": "motivo de exclusion",
    "Excepción posible": "excepcion posible",
    "Resultado sugerido": "resultado sugerido",
}


@dataclass
class Criterios:
    inclusiones_texto: str
    exclusiones_texto: str
    especialidades: list[str]
    total_inclusiones: int
    total_exclusiones: int


def _normalize(text: str) -> str:
    """Minúsculas sin acentos ni espacios extra, para comparar encabezados."""
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split())


def _resolve_columns(df: pd.DataFrame, wanted: dict[str, str]) -> dict[str, str]:
    """Mapea etiqueta amigable -> nombre real de columna presente en el df."""
    norm_to_real = {_normalize(c): c for c in df.columns}
    resolved: dict[str, str] = {}
    for label, needle in wanted.items():
        match = None
        # coincidencia exacta primero, luego por subcadena
        if needle in norm_to_real:
            match = norm_to_real[needle]
        else:
            for norm, real in norm_to_real.items():
                if needle in norm:
                    match = real
                    break
        if match is not None:
            resolved[label] = match
    return resolved


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return " ".join(str(value).split())


def _rows_to_text(df: pd.DataFrame, cols: dict[str, str]) -> str:
    """Convierte cada fila en un bloque legible etiqueta: valor."""
    id_col = cols.get("ID")
    blocks: list[str] = []
    for _, row in df.iterrows():
        if id_col and not _clean(row.get(id_col)):
            continue  # saltar filas vacías / de relleno
        lines: list[str] = []
        for label, real in cols.items():
            val = _clean(row.get(real))
            if val:
                lines.append(f"- {label}: {val}")
        if lines:
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _load(path: Path = MATRIZ_PATH) -> Criterios:
    inc = pd.read_excel(path, sheet_name="Inclusiones", header=0)
    exc = pd.read_excel(path, sheet_name="Exclusiones", header=0)

    inc_cols = _resolve_columns(inc, _INCLUSION_COLS)
    exc_cols = _resolve_columns(exc, _EXCLUSION_COLS)

    inclusiones_texto = _rows_to_text(inc, inc_cols)
    exclusiones_texto = _rows_to_text(exc, exc_cols)

    # Especialidades base desde Catalogos (columna "Especialidades").
    especialidades: list[str] = []
    try:
        cat = pd.read_excel(path, sheet_name="Catalogos", header=0)
        esp_cols = _resolve_columns(cat, {"Especialidades": "especialidades"})
        if "Especialidades" in esp_cols:
            especialidades = [
                _clean(v)
                for v in cat[esp_cols["Especialidades"]].tolist()
                if _clean(v)
            ]
    except Exception:
        especialidades = []

    total_inc = sum(1 for b in inclusiones_texto.split("\n\n") if b.strip())
    total_exc = sum(1 for b in exclusiones_texto.split("\n\n") if b.strip())

    return Criterios(
        inclusiones_texto=inclusiones_texto,
        exclusiones_texto=exclusiones_texto,
        especialidades=especialidades,
        total_inclusiones=total_inc,
        total_exclusiones=total_exc,
    )


def load_criterios(path: Path = MATRIZ_PATH) -> Criterios:
    """Carga los criterios, con caché de Streamlit si está disponible.

    Se usa un import perezoso de streamlit para que el módulo sea usable (y
    testeable) fuera de una app Streamlit.
    """
    try:
        import streamlit as st

        @st.cache_data(show_spinner=False)
        def _cached(p: str) -> Criterios:
            return _load(Path(p))

        return _cached(str(path))
    except Exception:
        return _load(path)


if __name__ == "__main__":
    c = load_criterios()
    print(f"Inclusiones: {c.total_inclusiones} | Exclusiones: {c.total_exclusiones}")
    print(f"Especialidades: {len(c.especialidades)}")
    print("\n--- PRIMERA INCLUSIÓN ---")
    print(c.inclusiones_texto.split("\n\n")[0])
    print("\n--- PRIMERA EXCLUSIÓN ---")
    print(c.exclusiones_texto.split("\n\n")[0])
