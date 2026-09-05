# Validador de referencias con IA — Clínica Al Alba

Herramienta de apoyo para el área de **Referencia y Contrarreferencia**. Recibe la
historia clínica de un paciente remitido en **PDF**, la evalúa con **Gemini 3.8 Flash**
contra la matriz institucional de criterios de inclusión/exclusión
(`matriz_inclusion_exclusion_referencias.xlsx`) y devuelve un **veredicto estructurado**
con un resumen que explica las razones.

> ⚠️ El resultado es una **sugerencia**. La decisión final siempre requiere validación
> médica humana.

## Cómo funciona

1. Se cargan los criterios clínicos desde las hojas *Inclusiones* y *Exclusiones* del
   Excel (en runtime, con caché — editar el Excel actualiza la app sin tocar código).
2. El PDF se envía **de forma nativa** a Gemini (multimodal, hace OCR de escaneados).
3. Gemini responde con **salida estructurada** (JSON validado contra un esquema Pydantic):
   decisión, especialidad, complejidad, criterios INC/EXC coincidentes por ID, datos
   faltantes y resumen.

Decisiones posibles:
- **Potencialmente aceptable**
- **No aceptable**
- **Requiere aclaración** (información insuficiente en la historia)

## Instalación

Requiere Python 3.10+.

```bash
pip install -r requirements.txt
```

## Configuración de la API key

Copia el ejemplo y coloca tu clave:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edita .streamlit/secrets.toml -> GEMINI_API_KEY = "..."
```

Alternativamente, exporta la variable de entorno `GEMINI_API_KEY`.

## Ejecución

```bash
streamlit run app.py
```

Sube un PDF y pulsa **Evaluar referencia**.

## Estructura

| Archivo | Rol |
|---|---|
| `app.py` | Interfaz Streamlit y orquestación (punto de entrada) |
| `criteria.py` | Carga la matriz Excel → contexto de criterios (cacheado) |
| `prompts.py` | System instruction y reglas de decisión |
| `gemini_client.py` | Llamada a Gemini 3.8 Flash con salida estructurada |
| `schema.py` | Modelos Pydantic del veredicto |
| `matriz_inclusion_exclusion_referencias.xlsx` | Fuente de criterios (solo lectura) |
| `requirements.txt` | Dependencias para Streamlit Cloud / pip |
| `runtime.txt` | Versión de Python para Streamlit Cloud |
| `.streamlit/secrets.toml.example` | Plantilla de secretos (el real NO se sube al repo) |

## Despliegue en Streamlit Community Cloud

1. Sube este repositorio a GitHub (`git init`, `git add`, `git commit`, `git push`).
   El archivo `.streamlit/secrets.toml` real **no se sube** (está en `.gitignore`); solo
   se sube `secrets.toml.example` como referencia.
2. En [share.streamlit.io](https://share.streamlit.io), crea una nueva app apuntando a
   este repositorio, rama `main` y archivo principal `app.py`.
3. En **App settings → Secrets**, pega el contenido (formato TOML) con tu clave real:
   ```toml
   GEMINI_API_KEY = "tu_api_key_de_gemini"
   ```
4. Deploy. La app leerá la matriz Excel del propio repo y la clave desde `st.secrets`.

> Si luego rotas la API key, solo hay que actualizarla en Secrets del dashboard de
> Streamlit Cloud — no requiere un nuevo commit.

## Alcance actual y siguientes pasos

En esta versión el razonamiento usa **solo los criterios clínicos** (Inclusiones +
Exclusiones). Fuera de alcance por ahora: validación cruzada contra códigos CUPS,
procesamiento por lotes, persistencia/auditoría de decisiones y autenticación de usuarios.
