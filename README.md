# Saldo Comercial · Argentina

Aplicación web para consultar series de **comercio exterior argentino** publicadas por el INDEC en el informe mensual de *Intercambio Comercial Argentino (ICA)*, junto con datos de Balance de Pagos, Balance Cambiario y series relacionadas.

**Stack:** FastAPI · SQLite · Chart.js · Render

---

## Estructura del repositorio

```
econsur_saldo_comercial/
├── main.py                  # Backend FastAPI
├── check_data.py            # Script de verificación de las bases
├── requirements.txt
├── render.yaml              # Configuración de deploy en Render
├── .gitignore
├── data/
│   ├── saldo_comercial1.db  # Cuadros 1–9: ICA — Comercio de bienes
│   └── saldo_comercial2.db  # Cuadros 10–36: Precios, BOP, Cambiario
└── static/
    └── index.html           # Frontend (HTML + JS + Chart.js)
```

---

## Bases de datos

| Archivo | Tabla | Hojas / Fuentes | Registros aprox. |
|---|---|---|---|
| `saldo_comercial1.db` | `saldo_comercial` | Cuadros 1, 2, 3, 7, 8, 9 | ~151 000 |
| `saldo_comercial2.db` | `series_datos` | Cuadros 10–36 | ~60 000 |

**Esquema de ambas tablas:**

| Columna | Tipo | Descripción |
|---|---|---|
| `periodo_raw` | TEXT | Período en formato original (ej: `2024T1`, `Ene-24`) |
| `serie_nombre` | TEXT | Nombre de la serie |
| `valor` | REAL | Valor numérico |
| `periodo` | TEXT | Fecha ISO normalizada (`YYYY-MM-DD`) |
| `frecuencia` | TEXT | `Anual` / `Trimestral` / `Mensual` (DB1) o `ANUAL` / `TRIMESTRAL` / `MENSUAL` (DB2) |
| `hoja_origen` | TEXT | Identificador de cuadro/hoja (ej: `1. ICA`, `14.a Bce Pagos 6-17`) |

---

## Endpoints de la API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Estado de las bases de datos |
| GET | `/api/debug` | Información de diagnóstico |
| GET | `/api/fuentes` | Lista de cuadros disponibles |
| GET | `/api/frecuencias?fuente=` | Frecuencias disponibles para una fuente |
| GET | `/api/series?fuente=&frecuencia=` | Series disponibles |
| GET | `/api/periodos?fuente=&frecuencia=&serie=` | Rango de períodos |
| GET | `/api/datos?fuente=&frecuencia=&serie=&desde=&hasta=` | Datos de una serie |
| GET | `/api/export/csv?...` | Exportación en CSV |

---

## Cuadros disponibles

### Dataset 1 — `saldo_comercial1.db`
| Cuadro | Nombre |
|---|---|
| CUADRO 1 | Intercambio Comercial Argentino |
| CUADRO 2 | Exportaciones FOB por Rubro |
| CUADRO 3 | Importaciones CIF por Uso Económico |
| CUADRO 7 | Exportaciones FOB por Países y Regiones |
| CUADRO 8 | Importaciones CIF por Regiones y Países |
| CUADRO 9 | Saldo Comercial por Países y Regiones |

### Dataset 2 — `saldo_comercial2.db`
| Cuadro | Nombre |
|---|---|
| CUADRO 10 | Índices de Exportaciones de Bienes (valor, precio, cantidad) |
| CUADRO 11 | Índices de Importaciones de Bienes (valor, precio, cantidad) |
| CUADRO 12 | Índices de Términos del Intercambio |
| CUADRO 13 | Poder de Compra de las Exportaciones |
| CUADRO 14 | Estimación del Balance de Pagos |
| CUADRO 15 | Deuda Externa Bruta por Sector Residente |
| CUADRO 34 | Encuesta de Turismo Internacional (ETI) |
| CUADRO 18 | Índice de Precios de Materias Primas (IPMP) |
| CUADRO 20 | Balance Cambiario |
| CUADRO 21 | Cobros y Pagos por Bienes — Modalidad |
| CUADRO 22 | Cobros y Pagos por Bienes — Sector |
| CUADRO 23 | Cobros y Pagos por Tipo de Servicio |
| CUADRO 36 | Liquidaciones CIARA-CEC |

---

## Instalación local

```bash
# Clonar el repo
git clone https://github.com/TU_USUARIO/econsur_saldo_comercial.git
cd econsur_saldo_comercial

# Instalar dependencias
pip install -r requirements.txt

# Copiar las bases de datos (si no están en el repo)
cp /ruta/a/saldo_comercial1.db data/
cp /ruta/a/saldo_comercial2.db data/

# Verificar las bases
python check_data.py

# Levantar el servidor
uvicorn main:app --reload
```

La app estará disponible en `http://localhost:8000`.

---

## Deploy en Render

1. Crear un nuevo **Web Service** apuntando a este repositorio.
2. Render detecta el `render.yaml` automáticamente y configura el build.
3. **Importante:** las bases `.db` deben estar presentes en el repositorio o subirse al disco persistente (`data-disk`, montado en `/opt/render/project/src/data`).
4. Para verificar el estado: `GET /api/health` y `GET /api/debug`.

### Actualización de datos

Para actualizar los datos, reemplazá los archivos `.db` en la carpeta `data/` y hacé un nuevo commit/push. Render redesplegará automáticamente.

---

## Fuente de datos

- **INDEC** — [Intercambio Comercial Argentino](https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-2-40)
- **BCRA** — Balance Cambiario
- **CIARA-CEC** — Liquidaciones de oleaginosas y cereales
