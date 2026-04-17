"""
Saldo Comercial Argentina — Consulta Integrada
Datasets: saldo_comercial1.db · saldo_comercial2.db
Backend: FastAPI + SQLite x2
Fuente: INDEC — Intercambio Comercial Argentino (ICA)
"""

import sqlite3
import io
import shutil
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"

DATA_DIR.mkdir(exist_ok=True)

# ── CORRECCIÓN: Crear carpeta static/ y copiar index.html si no existe ─────
# El index.html puede estar en la raíz del repo (fuera de static/).
# Este bloque garantiza que static/index.html siempre esté disponible.
STATIC_DIR.mkdir(exist_ok=True)
_html_candidates = [
    BASE_DIR / "index.html",          # raíz del repo
    BASE_DIR / "static" / "index.html",  # ubicación canónica
]
if not (STATIC_DIR / "index.html").exists():
    for _candidate in _html_candidates:
        if _candidate.exists() and _candidate != STATIC_DIR / "index.html":
            shutil.copy(_candidate, STATIC_DIR / "index.html")
            log.info(f"index.html copiado desde {_candidate} → {STATIC_DIR / 'index.html'}")
            break
    else:
        log.warning("index.html no encontrado. El frontend no estará disponible.")

DB1_PATH = DATA_DIR / "saldo_comercial1.db"
DB2_PATH = DATA_DIR / "saldo_comercial2.db"

DB_PATHS = {1: DB1_PATH, 2: DB2_PATH}

# ── Metadata por DB: tabla y columna fuente ────────────────────────────────
DB_META = {
    1: {"table": "saldo_comercial",  "col_fuente": "hoja_origen"},
    2: {"table": "series_datos",     "col_fuente": "hoja_origen"},
}

# ── Catálogo de fuentes ────────────────────────────────────────────────────
# (hoja_origen, cuadro, nombre_cuadro, descripcion, db_num)
FUENTES_CATALOG = [
    # ── Dataset 1: ICA — Comercio de bienes ──────────────────────────────
    (
        "1. ICA",
        "CUADRO 1",
        "Intercambio Comercial Argentino",
        "Exportaciones, importaciones y saldo del intercambio comercial total de Argentina (series anuales, trimestrales y mensuales)",
        1,
    ),
    (
        "2. X Rubro",
        "CUADRO 2",
        "Exportaciones FOB por Rubro",
        "Exportaciones F.O.B. de Argentina desagregadas por rubro (Productos primarios, MOA, MOI, Combustibles y energía)",
        1,
    ),
    (
        "3. M usos",
        "CUADRO 3",
        "Importaciones CIF por Uso Económico",
        "Importaciones CIF de Argentina clasificadas por uso económico (Bienes de capital, Bienes intermedios, Combustibles, Bienes de consumo, Resto)",
        1,
    ),
    (
        "7. X Paises",
        "CUADRO 7",
        "Exportaciones FOB por Países y Regiones",
        "Exportaciones FOB de Argentina desagregadas por país y región de destino",
        1,
    ),
    (
        "8. M Paises",
        "CUADRO 8",
        "Importaciones CIF por Regiones y Países",
        "Importaciones CIF de Argentina desagregadas por país y región de origen",
        1,
    ),
    (
        "9. Saldo Paises",
        "CUADRO 9",
        "Saldo Comercial por Países y Regiones (FOB-CIF)",
        "Saldo del intercambio comercial de Argentina por país y región (diferencia FOB-CIF)",
        1,
    ),
    # ── Dataset 2: Precios, Balance de Pagos, Servicios ──────────────────
    (
        "10. X pyq",
        "CUADRO 10",
        "Índices de Exportaciones de Bienes (valor, precio, cantidad)",
        "Índices de valor, precio y cantidad de las exportaciones de bienes de Argentina",
        2,
    ),
    (
        "11. M pyq",
        "CUADRO 11",
        "Índices de Importaciones de Bienes (valor, precio, cantidad)",
        "Índices de valor, precio y cantidad de las importaciones de bienes de Argentina",
        2,
    ),
    (
        "12. TdI",
        "CUADRO 12",
        "Índices de Términos del Intercambio",
        "Evolución de los términos del intercambio: relación entre precios de exportaciones e importaciones",
        2,
    ),
    (
        "13. Poder de Compra X",
        "CUADRO 13",
        "Poder de Compra de las Exportaciones",
        "Poder de compra de las exportaciones de bienes y ganancia (o pérdida) del intercambio",
        2,
    ),
    (
        "14.a Bce Pagos 6-17",
        "CUADRO 14",
        "Estimación del Balance de Pagos",
        "Balance de Pagos de Argentina: cuenta corriente, cuenta capital y cuenta financiera",
        2,
    ),
    (
        "15.a Deuda Ext. Bruta x S. 6-17",
        "CUADRO 15",
        "Deuda Externa Bruta por Sector Residente",
        "Estimación de la Deuda Externa Bruta de Argentina a valor nominal, desagregada por sector residente",
        2,
    ),
    (
        "17. ETI",
        "CUADRO 34",
        "Encuesta de Turismo Internacional (ETI)",
        "Turismo receptivo y emisivo — Total Aéreo. Aeropuerto Internacional de Ezeiza y Aeroparque Jorge Newbery",
        2,
    ),
    (
        "18. IPMP",
        "CUADRO 18",
        "Índice de Precios de Materias Primas (IPMP)",
        "Índice de precios de las principales materias primas de exportación argentina",
        2,
    ),
    (
        "20.Balance cambiario",
        "CUADRO 20",
        "Balance Cambiario",
        "Cobros y pagos en moneda extranjera registrados en el mercado de cambios de Argentina",
        2,
    ),
    (
        "21.Bienes por modalidad de pago",
        "CUADRO 21",
        "Cobros y Pagos por Bienes — Modalidad",
        "Cobros y pagos por bienes clasificados por modalidad de pago — Balance Cambiario",
        2,
    ),
    (
        "22.Bienes por sector",
        "CUADRO 22",
        "Cobros y Pagos por Bienes — Sector",
        "Cobros y pagos por bienes clasificados por sector de actividad — Balance Cambiario",
        2,
    ),
    (
        "23.Servicios por tipo",
        "CUADRO 23",
        "Cobros y Pagos por Tipo de Servicio",
        "Cobros y pagos clasificados por tipo de servicio — Balance Cambiario",
        2,
    ),
    (
        "35. Liquidaciones OyC CIARA-CEC",
        "CUADRO 36",
        "Liquidaciones de Oleaginosas y Cereales — CIARA-CEC",
        "Liquidación de divisas por exportaciones de oleaginosas y cereales (CIARA-CEC)",
        2,
    ),
]

# Lookup rápido: hoja_origen → db_num
FUENTE_DB: dict[str, int] = {f[0]: f[4] for f in FUENTES_CATALOG}

# Lookup: hoja_origen → cuadro, nombre, descripcion
FUENTE_INFO: dict[str, dict] = {
    f[0]: {"cuadro": f[1], "nombre_cuadro": f[2], "descripcion": f[3]}
    for f in FUENTES_CATALOG
}


# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Saldo Comercial Argentina",
    description="Consulta integrada de series de comercio exterior — INDEC / ICA",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DB connection ──────────────────────────────────────────────────────────
def get_conn(db_num: int) -> sqlite3.Connection:
    path = DB_PATHS.get(db_num)
    if not path:
        raise HTTPException(400, detail=f"db_num={db_num} inválido.")
    if not path.exists():
        raise HTTPException(
            503,
            detail=(
                f"Base de datos '{path.name}' no disponible. "
                "El archivo debe estar en la carpeta data/ del repositorio."
            ),
        )
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def get_table(db_num: int) -> str:
    return DB_META[db_num]["table"]


# ── Normalización de frecuencias ───────────────────────────────────────────
# DB1 usa title case, DB2 usa uppercase. Normalizamos a Title Case para el
# catálogo unificado y reconvertimos al formato nativo antes de cada query.

_FREQ_NORMALIZE = {
    "ANUAL": "Anual", "TRIMESTRAL": "Trimestral",
    "MENSUAL": "Mensual", "SEMESTRAL": "Semestral",
    "Anual": "Anual", "Trimestral": "Trimestral",
    "Mensual": "Mensual", "Semestral": "Semestral",
}

_FREQ_ORDER = {"Anual": 0, "Semestral": 1, "Trimestral": 2, "Mensual": 3}


def normalize_freq(raw: str) -> str:
    """Title-case normalización para display unificado."""
    return _FREQ_NORMALIZE.get(raw, raw.title())


def db_freq(frecuencia: str, db_num: int) -> str:
    """Devuelve la frecuencia en el formato nativo de cada DB."""
    if db_num == 2:
        return frecuencia.upper()
    return frecuencia  # DB1 ya usa title case


# ── API: Diagnóstico ───────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    db_status = {f"db{i}_ok": DB_PATHS[i].exists() for i in (1, 2)}
    all_ok = all(db_status.values())
    return {"status": "ok" if all_ok else "degraded", **db_status}


@app.get("/api/debug")
def debug():
    archivos = [f.name for f in DATA_DIR.iterdir()] if DATA_DIR.exists() else []
    counts = {}
    for i in (1, 2):
        if DB_PATHS[i].exists():
            try:
                conn = sqlite3.connect(str(DB_PATHS[i]))
                table = get_table(i)
                counts[f"db{i}_series"] = conn.execute(
                    f"SELECT COUNT(DISTINCT serie_nombre) FROM {table}"
                ).fetchone()[0]
                counts[f"db{i}_rows"] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                conn.close()
            except Exception as e:
                counts[f"db{i}_error"] = str(e)
    return {
        "version": "1.0.0",
        "base_dir": str(BASE_DIR),
        "data_dir": str(DATA_DIR),
        "static_dir": str(STATIC_DIR),
        "static_exists": STATIC_DIR.exists(),
        "index_html_exists": (STATIC_DIR / "index.html").exists(),
        "archivos_data": archivos,
        "fuentes_catalogo": len(FUENTES_CATALOG),
        **{f"db{i}_exists": DB_PATHS[i].exists() for i in (1, 2)},
        **counts,
    }


# ── API: Catálogos ─────────────────────────────────────────────────────────
@app.get("/api/fuentes")
def get_fuentes():
    """Lista completa de fuentes/hojas disponibles con su DB de origen."""
    return [
        {
            "fuente":        f[0],
            "cuadro":        f[1],
            "fuente_nombre": f[2],
            "descripcion":   f[3],
            "db_num":        f[4],
        }
        for f in FUENTES_CATALOG
        if DB_PATHS[f[4]].exists()
    ]


@app.get("/api/frecuencias")
def get_frecuencias(fuente: str = Query(...)):
    db_num = FUENTE_DB.get(fuente)
    if db_num is None:
        raise HTTPException(404, detail=f"Fuente '{fuente}' no encontrada.")
    conn = get_conn(db_num)
    table = get_table(db_num)
    try:
        rows = conn.execute(
            f"SELECT DISTINCT frecuencia FROM {table} WHERE hoja_origen=? ORDER BY frecuencia",
            [fuente],
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        raise HTTPException(404, detail=f"No hay frecuencias para la fuente '{fuente}'.")
    # Normalizar y ordenar
    normed = sorted(
        set(normalize_freq(r["frecuencia"]) for r in rows),
        key=lambda f: _FREQ_ORDER.get(f, 99),
    )
    return normed


@app.get("/api/series")
def get_series(fuente: str = Query(...), frecuencia: str = Query(...)):
    db_num = FUENTE_DB.get(fuente)
    if db_num is None:
        raise HTTPException(404, detail=f"Fuente '{fuente}' no encontrada.")
    conn = get_conn(db_num)
    table = get_table(db_num)
    freq_native = db_freq(frecuencia, db_num)
    try:
        rows = conn.execute(
            f"""SELECT DISTINCT serie_nombre
               FROM {table}
               WHERE hoja_origen=? AND frecuencia=? AND serie_nombre != ''
               ORDER BY serie_nombre""",
            [fuente, freq_native],
        ).fetchall()
    finally:
        conn.close()
    return [{"serie_nombre": r["serie_nombre"]} for r in rows]


@app.get("/api/periodos")
def get_periodos(
    fuente: str = Query(...),
    frecuencia: str = Query(...),
    serie: str = Query(...),
):
    db_num = FUENTE_DB.get(fuente)
    if db_num is None:
        raise HTTPException(404, detail=f"Fuente '{fuente}' no encontrada.")
    conn = get_conn(db_num)
    table = get_table(db_num)
    freq_native = db_freq(frecuencia, db_num)
    try:
        rows = conn.execute(
            f"""SELECT periodo FROM {table}
               WHERE hoja_origen=? AND frecuencia=? AND serie_nombre=?
               ORDER BY periodo""",
            [fuente, freq_native, serie],
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return {"desde": None, "hasta": None}
    periodos = [r["periodo"][:10] for r in rows if r["periodo"]]
    return {"desde": min(periodos), "hasta": max(periodos)}


@app.get("/api/datos/")
@app.get("/api/datos")
def get_datos(
    fuente: str = Query(...),
    frecuencia: str = Query(...),
    serie: str = Query(...),
    desde: str = Query(...),
    hasta: str = Query(...),
):
    if desde > hasta:
        raise HTTPException(400, detail="'desde' debe ser ≤ 'hasta'.")
    db_num = FUENTE_DB.get(fuente)
    if db_num is None:
        raise HTTPException(404, detail=f"Fuente '{fuente}' no encontrada.")
    conn = get_conn(db_num)
    table = get_table(db_num)
    freq_native = db_freq(frecuencia, db_num)
    info = FUENTE_INFO.get(fuente, {})
    try:
        rows = conn.execute(
            f"""SELECT periodo_raw, periodo, valor, serie_nombre, frecuencia, hoja_origen
               FROM {table}
               WHERE hoja_origen=? AND frecuencia=? AND serie_nombre=?
                 AND periodo >= ? AND periodo <= ?
               ORDER BY periodo""",
            [fuente, freq_native, serie, desde, hasta],
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return {"datos": [], "meta": {}}

    first = dict(rows[0])
    meta = {
        "serie_nombre":    first["serie_nombre"],
        "fuente":          first["hoja_origen"],
        "cuadro":          info.get("cuadro", ""),
        "nombre_cuadro":   info.get("nombre_cuadro", ""),
        "frecuencia":      frecuencia,
        "db_num":          db_num,
        "total_registros": len(rows),
    }
    datos = [
        {
            "periodo_raw": r["periodo_raw"],
            "periodo":     r["periodo"][:10] if r["periodo"] else None,
            "valor":       r["valor"],
        }
        for r in rows
    ]
    return {"datos": datos, "meta": meta}


@app.get("/api/export/csv")
def export_csv(
    fuente: str = Query(...),
    frecuencia: str = Query(...),
    serie: str = Query(...),
    desde: str = Query(...),
    hasta: str = Query(...),
):
    result = get_datos(
        fuente=fuente, frecuencia=frecuencia,
        serie=serie, desde=desde, hasta=hasta,
    )
    datos, meta = result["datos"], result["meta"]

    buf = io.StringIO()
    buf.write(f"# Serie: {meta.get('serie_nombre', '')}\n")
    buf.write(f"# Cuadro: {meta.get('cuadro', '')} — {meta.get('nombre_cuadro', '')}\n")
    buf.write(f"# Fuente: {meta.get('fuente', '')}\n")
    buf.write(f"# Frecuencia: {meta.get('frecuencia', '')}\n")
    buf.write(f"# Fuente original: INDEC — Intercambio Comercial Argentino\n")
    buf.write("periodo,periodo_raw,valor\n")
    for row in datos:
        buf.write(f"{row['periodo']},{row['periodo_raw']},{row['valor']}\n")
    buf.seek(0)

    fname = (
        f"ICA_{meta.get('cuadro', fuente)[:20]}_{serie[:30]}"
        f"_{desde}_{hasta}.csv"
    ).replace(" ", "_").replace("/", "-").replace(".", "-")

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


# ── Frontend ───────────────────────────────────────────────────────────────
# CORRECCIÓN: Montamos StaticFiles sólo si el directorio existe, para evitar
# RuntimeError en import-time que tumba todo el proceso antes de abrir el puerto.
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    log.warning("Carpeta static/ no encontrada — los assets estáticos no estarán disponibles.")


@app.get("/", response_class=HTMLResponse)
def root():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse(
            "<h2>Frontend no disponible. Asegurate de que static/index.html exista.</h2>",
            status_code=503,
        )
    return HTMLResponse(index_path.read_text(encoding="utf-8"))
