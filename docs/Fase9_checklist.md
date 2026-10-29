# Fase 9 — Criterios de aceptacion del MVP

Checklist basado en el §14 del plan de desarrollo. `[x]` = implementado y verificado con pruebas.

## Despliegue y configuracion
- [x] La aplicacion se despliega desde instrucciones documentadas (`docker compose up --build`; `README.md`).
- [x] Configuracion de entorno por `.env.example` (sin secretos en el repositorio).

## Eventos y procedencia
- [x] Los eventos muestran proveedor, hora UTC, ubicacion, magnitud, profundidad y enlace de procedencia
      (tabla de eventos + ficha detalle + API `GET /api/v1/events`).
- [x] La ingesta no duplica registros al repetirse (upsert por `external_id + source_id`;
      restriccion unica en BD; ver `tests/test_events_alerts.py::test_ingestion_dedup_logic`).
- [x] Cada ejecucion y error de ingesta queda registrado (`ingestion_runs`, modulo Fuentes).
- [x] Actualizacion en vivo sin recargar la pagina: canal SSE (`GET /api/v1/events/stream`, cursor
      por `received_at`) con indicador `EN VIVO`; Dashboard, Eventos y Mapa se refrescan solos al
      llegar eventos (`tests/test_realtime_sources.py::test_event_stream_greeting_frame` y
      `::test_event_stream_emits_inserted_event`).

## Analitica verificable
- [x] Dashboard, mapa y graficas respetan filtros y coinciden con la API
      (los datos provienen unicamente de `GET /api/v1/*`; `tests` de filtros por magnitud).
- [x] Cada grafica muestra unidad, periodo, muestra y fuente en su cabecera.
- [x] El dashboard filtra por periodo (*Ultimos 7 dias / 30 dias / 1 anio*) aplicando
      `date_from`/`date_to` a los KPIs y a las graficas; el resumen expone las estadisticas del
      periodo (`period_max_magnitude`, `period_avg_depth`) y es coherente con la API de eventos
      (`tests/test_realtime_sources.py::test_dashboard_summary_period_stats`).

## Machine Learning
- [x] Los modelos registran dataset, periodo, features, version, semilla, librerias, metricas y limitaciones
      (`ml_experiments` + `tests/test_ml_pipeline.py`).
- [x] Existe baseline (`dummy`) comparado bajo la misma particion temporal.
- [x] Las estimaciones experimentales no se confunden visual ni sematicamente con alertas oficiales
      (etiqueta `ESTIMACION EXPERIMENTAL`, disclaimer en API y UI, badge y colores distintos).

## Alertas
- [x] Las reglas permiten probar condiciones, evitar duplicados (dedupe evento+regla, cooldown)
      y consultar la entrega (`alert_deliveries` con intentos y error).
- [x] Aprobacion humana obligatoria para reglas de severidad alta (por defecto `requires_approval`).
- [x] Mensajes con fuente y enlace del evento; declaracion explicita de que no es prediccion.

## Seguridad y roles
- [x] Los roles bloquean funciones en la interfaz (sidebar condicional) y en la API
      (`require(perm)` por endpoint; `tests/test_auth_users_audit.py` verifica 403 para viewer).
- [x] Auditoria de logins, creaciones, aprobaciones, cambios de reglas y descargas (`audit_logs`).

## Reportes
- [x] Los reportes muestran fecha de corte, filtros, fuente y usuario solicitante (cabecera CSV/XLSX/PDF +
      `report_jobs.requested_by`; `tests/test_reports_datasets.py` y `tests/test_config_reports.py`).
- [x] Exportacion en CSV, XLSX y PDF segun permisos (`format` en `POST /api/v1/reports`;
      verificado con eventos reales del IGP: 98 registros en los tres formatos).
- [x] Vigencia de reportes configurable (`report_retention_days`) y aplicada al generar.

## Configuracion y trazabilidad (§6.13)
- [x] Panel de configuracion operativa con valor por defecto visible, rango y fecha de modificacion
      (modulo Configuracion; `GET /api/v1/config`).
- [x] Cambios validados (clave desconocida o fuera de rango -> `400`) y registrados en auditoria con
      antes/despues (`tests/test_config_reports.py`).
- [x] Los parametros operativos se aplican de verdad: daemon de ingesta (relee el intervalo en cada
      ciclo), filtro de magnitud, ventana de busqueda y retencion de reportes.

## Fuente de datos
- [x] Unica fuente operativa: **IGP / CENSIS** (canal oficial del Instituto Geofisico del Peru),
      con exclusion de simulacros y deduplicacion del catalogo (`services/ingestion/igp.py`).
- [x] Conector verificado contra la API real (~880 eventos normalizados en 365 dias, sin duplicados).
- [x] Alta de fuentes desde el modulo Fuentes de datos: `POST /api/v1/sources` con permiso
      `sources:write`, auditoria `source.create`, rechazo de duplicados (`409`) y de URLs no
      http(s) (`422`); sin secretos en claro (`tests/test_realtime_sources.py::test_create_source_*`).
- [x] El daemon sincroniza todas las fuentes habilitadas en cada ciclo: una fuente recien creada
      empieza a actualizarse sola y una fuente con error no detiene a las demas
      (`resolve_sources` en `services/ingestion/sync.py`).

## Pruebas y continuidad
- [x] Pruebas automatizadas de API, ingesta, alertas y ML (`services/api/tests/`).
- [x] CI que corre backend (pytest) y build de frontend (`.github/workflows/ci.yml`).
- [x] Guia de operacion y procedimiento de incidente (`docs/operacion.md`).
- [ ] Backup automatizado programado y simulacro de restauracion ejecutado en el entorno objetivo
      (comandos documentados; requiere ejecucion en infraestructura real).

## Pendiente para produccion (validacion externa)
- [ ] Confirmar con IGP/INDECI canales oficiales, licencias y lenguaje autorizado (Fase 0).
- [ ] Habilitar HTTPS en el ingress y secret manager.
- [ ] Integracion SMTP real (hoy canal `email` es un stub trazable).
