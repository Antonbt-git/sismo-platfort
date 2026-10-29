# Sismo Platform — Monitoreo sismico, analitica y alertas

Plataforma empresarial para consolidar eventos sismicos observados, analizar patrones
historicos, ejecutar experimentos de Machine Learning claramente etiquetados y distribuir
alertas operativas trazables.

> **Aviso importante:** el sistema **no predice terremotos**. La ciencia actual no permite
> predecir de forma fiable fecha, hora, lugar y magnitud de un sismo. Aqui conviven tres
> conceptos diferenciados: **eventos observados** (reportados por la fuente), **estimaciones
> experimentales** (ML, con incertidumbre y version) y **alertas oficiales** (solo difusion
> de mensajes verificados). El sistema no sustituye a INDECI, IGP ni proteccion civil.

## Arquitectura

| Capa | Tecnologia |
|---|---|
| Frontend | React + TypeScript + Vite, Tailwind CSS, Recharts, Leaflet |
| API | Python + FastAPI + Pydantic (JWT, OpenAPI automatico) |
| ML / Analitica | pandas, NumPy, scikit-learn, joblib |
| Persistencia | PostgreSQL (SQLite solo para pruebas) |
| Ingesta | Conector oficial IGP / CENSIS (API JSON), daemon opcional |
| Despliegue | Docker Compose, Nginx, CI (GitHub Actions) |

## Funcionalidades clave

- **Tiempo real**: canal SSE (`GET /api/v1/events/stream`) que consulta la base de datos cada
  ~3 s; el Dashboard, Eventos y Mapa se refrescan solos y un indicador `EN VIVO` en la barra
  superior avisa de la conexion (con reconexion automatica). Funciona igual si los eventos los
  inserta el daemon, una sincronizacion manual u otro proceso.
- **Fuentes de datos administrables**: alta de fuentes desde el modulo Fuentes (accion auditada
  `source.create`, con rechazo de duplicados y de URLs no http(s)); el daemon `sync.py --loop`
  sincroniza **todas las fuentes habilitadas** en cada ciclo, de modo que una fuente recien
  creada empieza a actualizarse sola sin tocar el daemon.
- **Dashboard filtrable por periodo**: chips *Ultimos 7 dias / 30 dias / 1 anio* que aplican
  `date_from`/`date_to` a los KPIs y a las graficas (serie temporal e histograma), con las
  estadisticas del periodo (`period_max_magnitude`, `period_avg_depth`) en el resumen.

## Estructura del monorepo

```
sismo-platform/
├── apps/web/              # React + TypeScript (13 modulos funcionales)
├── services/
│   ├── api/               # FastAPI: routers, modelos, seguridad, auditoria
│   ├── ingestion/         # conector IGP/CENSIS + sincronizacion idempotente
│   └── ml/                # datasets, entrenamiento, evaluacion, registro
├── database/migrations/   # Alembic (migraciones versionadas)
├── tests/                 # (pruebas en services/api/tests)
├── infra/docker/          # Dockerfiles y nginx
├── docs/                  # alcance, operacion, checklist de aceptacion
└── docker-compose.yml
```

## Puesta en marcha rapida (Docker)

```bash
cp .env.example .env        # cambie SECRET_KEY y SEED_ADMIN_PASSWORD
docker compose up --build
```

- Web: http://localhost:8080
- API + OpenAPI: http://localhost:8000/docs
- Login inicial: `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` del `.env` (cambielo tras el primer acceso).

La base de datos se crea al arrancar la API. Para produccion use migraciones (desde la raiz del
proyecto): `alembic upgrade head` (ver `docs/operacion.md`).

### Migrar datos de SQLite a PostgreSQL (p. ej. Supabase)

`services/migrate_to_supabase.py` copia todo el contenido de `var/dev.sqlite3` a la base definida en
`TARGET_DATABASE_URL` (crea las tablas si faltan y omite registros ya existentes, por lo que puede
reejecutarse sin duplicar):

```bash
TARGET_DATABASE_URL="postgresql+psycopg://usuario:clave@host:5432/postgres" \
  python services/migrate_to_supabase.py
```

Basta con que `DATABASE_URL` del `.env` apunte a esa base para que API e ingesta trabajen contra ella.

## Desarrollo local

Backend (requiere Python >= 3.11):

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r services/api/requirements.txt
pip install -e services/api
cd services/api
uvicorn app.main:app --reload
```

Sincronizacion de eventos (fuente oficial IGP / CENSIS):

```bash
cd services
python ingestion/sync.py --hours 168               # todas las fuentes habilitadas
python ingestion/sync.py --source-id <uuid>        # una fuente concreta
python ingestion/sync.py --loop --interval 300     # daemon: todas las habilitadas; relee el intervalo
```

En modo daemon se sincroniza **cada fuente habilitada** en cada ciclo (una fuente con error se
registra en `ingestion_runs` pero no detiene a las demas). Las fuentes se administran desde el
modulo Fuentes de datos o via `POST /api/v1/sources`.

Entrenamiento ML:

```bash
# desde la API: POST /api/v1/ml/experiments (ejecuta services/ml/train.py en background)
# o directo por CLI tras crear el experimento:
python services/ml/train.py --experiment-id <uuid>
```

Frontend (requiere Node >= 20):

```bash
cd apps/web
npm install
npm run dev      # http://localhost:5173 (proxy /api -> localhost:8000)
```

Pruebas (Fase 9):

```bash
cd services/api
pytest -q
```

## Secuencia de fases (del plan de desarrollo)

| Fase | Contenido | Estado en este repositorio |
|---|---|---|
| 0 Descubrimiento | Alcance, fuentes, riesgos, backlog | `docs/Fase0_alcance.md` |
| 1 Base tecnica | Monorepo, React, FastAPI, PostgreSQL, Docker | Estructura completa, compose e infra |
| 2 Identidad y auditoria | JWT, roles/permisos, bitacora inmutable | `app/security.py`, `app/audit.py`, modulos usuarios/auditoria |
| 3 Ingesta | Conector IGP/CENSIS, normalizacion, dedupe, runs | `services/ingestion/` + modulo Fuentes |
| 4 Dashboard/mapa/analisis | KPIs, series, histogramas, mapa, dispersion | modulos Dashboard, Mapa, Analisis |
| 5 Calidad y datasets | Versionado, informe de calidad | `datasets` router + modulo Preparacion |
| 6 ML supervisado | Clasificacion/regresion, baseline, metricas | `services/ml/` + modulo Modelos y Estimaciones |
| 7 Alertas | Reglas, dedupe, aprobacion, entregas | `app/alerts_engine.py` + modulo Alertas |
| 8 Reportes y admin | CSV/XLSX/PDF con corte/filtros, usuarios, configuracion | modulos Reportes, Usuarios y Configuracion |
| 9 Seguridad/pruebas | pytest, CI, checklists, operacion | `services/api/tests/`, CI, `docs/Fase9_checklist.md` |

## Documentacion

- `docs/Fase0_alcance.md` — alcance, fuente elegida, politica de alertas, backlog.
- `docs/operacion.md` — despliegue, backup, restauracion, configuracion operativa, incidentes.
- `docs/despliegue.md` — publicar la web en Vercel y la API/ingesta en Render (Supabase como BD).
- `docs/Fase9_checklist.md` — criterios de aceptacion del MVP con su estado.
- API OpenAPI interactiva en `/docs` (estandar `/api/v1`, paginacion, filtros validados).
