# Guia de operacion (Fase 9)

## 1. Despliegue

1. Requisitos: Docker + Docker Compose.
2. `cp .env.example .env`; definir `SECRET_KEY` (cadena aleatoria larga) y `SEED_ADMIN_PASSWORD`.
3. `docker compose up -d --build`
4. Verificar: `GET /health` debe responder `{"status":"ok"}`; el contenedor `ingesta` debe registrar
   `Sincronizacion ok` en `docker compose logs -f ingesta`.
5. Ingresar a http://localhost:8080 y cambiar la contraseña del administrador.

### Migraciones (produccion)

La API crea el esquema automaticamente al arrancar (comodidad de desarrollo). En produccion,
desde la raiz del proyecto:

```bash
alembic upgrade head
```

Las migraciones viven en `database/migrations/versions/` y se versionan en Git. Revisar cada
migracion antes de aplicarla; nunca editar una migracion ya aplicada.

## 2. Copias de seguridad y restauracion

Backup diario de PostgreSQL:

```bash
docker compose exec db pg_dump -U sismo sismodb | gzip > backup_$(date +%F).sql.gz
```

Restauracion (simulacro trimestral):

```bash
gunzip -c backup_2026-10-22.sql.gz | docker compose exec -T db psql -U sismo -d sismodb
```

Artefactos ML (`var/artifacts`) y reportes (`var/reports`) deben incluirse en la copia del volumen
`./var`. La vigencia de los reportes es un parametro operativo (`report_retention_days`, por defecto
7 dias) editable en el modulo Configuracion; los artefactos son regenerables reentrenando.

## 3. Monitorizacion

- **Fuentes**: modulo Fuentes de datos (estado, ultimo exito, latencia, errores por ejecucion).
- **Ingesta**: tabla `ingestion_runs` (vista en el modulo); alertarse si `last_success_at` supera
  3 veces la frecuencia configurada. El daemon `ingesta` sincroniza **todas las fuentes
  habilitadas** en cada ciclo: una fuente recien creada (alta en el modulo o via
  `POST /api/v1/sources`) entra sola en el siguiente ciclo, y una fuente con error se registra
  con `status=error` sin detener a las demas.
- **Tiempo real**: el canal SSE (`GET /api/v1/events/stream`) consulta la BD cada ~3 s; el
  indicador `EN VIVO` de la barra superior refleja la conexion y se reconecta solo a los 3 s si
  la API se reinicia. No requiere configuracion adicional.
- **API**: logs estandar de uvicorn; revisar respuestas 5xx y latencia.
- **Alertas**: bandeja con estados fallida/cancelada; las entregas registran intentos y errores.

## 4. Procedimiento de incidente

1. **Impacto**: identificar si es datos (fuente caida), API, entrega de alertas o seguridad.
2. **Contencion**: deshabilitar la fuente afectada (`PATCH /api/v1/sources/{id}/status?enabled=false`)
   o pausar el contenedor `ingesta`.
3. **Comunicacion interna**: usar el canal definido en la Fase 0; NUNCA emitir mensajes de peligro
   publico desde el sistema sin validacion del organismo competente.
4. **Restauracion**: desde el ultimo backup verificado si hubo corrupcion; validar con
   `GET /api/v1/analytics/quality`.
5. **Post-mortem**: registrar en la bitacora (`audit_logs`) las acciones correctivas y generar el
   reporte de alertas del periodo.

## 5. Configuracion operativa (§6.13)

El modulo **Configuracion** (solo administradores escriben; auditoria consulta) expone los
parametros operativos vigentes con su valor por defecto, rango permitido y fecha de ultima
modificacion. API: `GET /api/v1/config` y `PUT /api/v1/config` con
`{"values": {"<clave>": <valor>}}`.

| Clave | Default | Rango | Efecto |
|---|---|---|---|
| `ingesta_interval_seconds` | 300 | 60–86400 | Frecuencia del daemon `ingesta` (se relee en cada ciclo) |
| `ingesta_lookback_hours` | 24 | 1–8760 | Ventana revisada por sincronizacion |
| `ingesta_min_magnitude` | 2.5 | 0–10 | Filtro de magnitud del conector IGP/CENSIS |
| `report_retention_days` | 7 | 1–90 | Vigencia de los reportes exportados |
| `alert_cooldown_default_seconds` | 1800 | 0–86400 | Enfriamiento por defecto de reglas |
| `audit_retention_days` | 365 | 30–3650 | Retencion de la bitacora |

Claves fuera del catalogo o fuera de rango se rechazan con `400`; toda modificacion correcta queda
en `audit_logs` (`action=config.update`) con valores antes/despues. Los secretos **no** se gestionan
aqui: siguen en variables de entorno o secret manager.

## 6. Seguridad operativa

- HTTPS obligatorio en produccion (terminar en proxy/ingress); el Nginx de la imagen `web` es HTTP
  interno.
- Secretos solo via variables de entorno o secret manager; jamas en el repositorio ni en
  `audit_logs`/`data_sources.config_ref` en texto plano.
- Rotar `SECRET_KEY` invalida sesiones JWT (comunicarlo a los usuarios).
- Revisar trimestralmente roles asignados (principio de minimo privilegio).
