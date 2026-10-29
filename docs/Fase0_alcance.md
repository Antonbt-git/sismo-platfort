# Fase 0 — Descubrimiento y viabilidad

**Proyecto:** Sistema empresarial de monitoreo sísmico, análisis predictivo y alertas
**Versión del documento:** 1.0 (base: Plan de desarrollo técnico, 13/10/2026)
**Fecha de esta versión:** 22/10/2026

## 1. Usuarios y roles del sistema

| Rol | Perfil | Necesidad principal |
|---|---|---|
| Administrador | Responsable de plataforma | Gestionar usuarios, fuentes, configuración y retención |
| Analista | Científico de datos / sismólogo junior | Explorar datos, preparar datasets, entrenar y revisar modelos |
| Operador de alertas | Personal de sala de operaciones | Definir reglas, probarlas, aprobar y consultar entregas |
| Auditor | Control interno / cumplimiento | Consultar bitácora inmutable y trazabilidad sin editar |
| Solo lectura | Dirección, prensa interna | Ver dashboard, mapa y reportes publicados |

## 2. Cobertura geográfica inicial

- **Primera cobertura: Perú** (zona de subducción Nazca–Sudamericana, costa, sierra y selva).
- Zonas configurables por bbox y polígono; la fuente IGP/CENSIS reporta eventos del territorio peruano, que se filtran por `region`/coordenadas a la zona de interés sin descartar el registro original (trazabilidad).

## 3. Fuente de datos elegida (Fase 0)

| Campo | Decisión |
|---|---|
| Proveedor inicial | **IGP / CENSIS — Centro Sismológico Nacional** (Instituto Geofísico del Perú) |
| Endpoint | `https://censis.igp.gob.pe/api/ultimo-sismo/sismos` (catálogo JSON del año en curso) |
| Endpoints relacionados | `/api/ultimo-sismo` (último evento), `/api/ultimo-sismo/sismo/{codigo}` (reporte), `/api/ultimo-sismo/inicio` (estadísticas) |
| Licencia | Información oficial del Estado peruano: citar fuente y enlace de procedencia en toda salida |
| Frecuencia | Cada 5 minutos (la API entrega el catálogo del año; el filtro por ventana se aplica localmente) |
| Volumen esperado | ~750 eventos/año reportados para el Perú; magnitud típica 2.5–6 |
| Campos disponibles | `codigo`, `fecha_hora` (UTC), `latitud`, `longitud`, `magnitud`, `profundidad` (km), `referencia`, `intensidades`, `tipo_evento` (P/S), `simulacro` |
| Cobertura | Eventos del territorio peruano reportados por la Red Sísmica Nacional |
| Reglas del conector | Excluye simulacros, normaliza profundidad al rango CHECK [0, 800] km y construye la URL de procedencia `censis.igp.gob.pe/evento/{codigo}` |

> La fuente USGS fue retirada del sistema: la plataforma opera únicamente con el canal oficial del IGP.
> Los proveedores, endpoints, licencias y protocolos de emergencia se reconfirman antes del despliegue productivo. La plataforma **no sustituye** a INDECI, IGP ni organismos de protección civil.

## 4. Política de alertas acordada

1. Los eventos **observados** (reportados por la fuente) se diferencian visual y semánticamente de las **estimaciones experimentales** y de los **comunicados oficiales**.
2. Toda alerta derivada de una regla operativa se etiqueta como «Aviso operativo basado en evento reportado por {fuente}», con enlace de procedencia.
3. Ningún mensaje del sistema puede afirmar predicción de fecha, hora, lugar o magnitud de un sismo futuro.
4. Reglas con severidad alta requieren **aprobación humana** antes del envío externo.
5. Canales MVP: `console` (bandeja interna) y `email` (SMTP configurable). Canales externos (SMS, redes) requieren integración validada posteriores.
6. Deduplicación por `(evento, regla, canal)` y cooldown por regla para evitar reenvíos.

## 5. Preguntas de ML aceptadas (validadas con criterio técnico)

| Pregunta | Tarea | Límite declarado |
|---|---|---|
| ¿A qué rango de magnitud pertenece un evento ya reportado según sus metadatos? | Clasificación (bandas <4.5 / 4.5–6 / ≥6) | Descriptor de registros existentes; **no** anticipa sismos futuros |
| ¿Se puede estimar la profundidad reportada a partir de ubicación y magnitud? | Regresión (MAE/RMSE/R² vs baseline de media) | Ejercicio didáctico de asociación numérica; sin causalidad |

Ambas preguntas usan solo información disponible al momento del reporte, con **partición temporal** para evitar fuga de datos.

## 6. Riesgos identificados y mitigación

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Malinterpretación de estimaciones como predicciones oficiales | Alto (reputación, pánico) | Etiquetado explícito, disclaimers en API y UI, aprobación humana |
| Caída o lentitud de la fuente externa | Medio | Registro de ejecuciones, latencia, reintentos con backoff, estado de conectores visible |
| Duplicados por re-sincronización | Medio | Unique `(external_id, source_id)` + upsert idempotente |
| Fuga de datos en ML | Alto (métricas infladas) | Split temporal, features solo del momento del reporte, semilla fijada |
| Acceso no autorizado | Alto | JWT + roles, autorización en backend, auditoría de acciones críticas |
| Incumplimiento de licencia de datos | Medio | Ficha de fuente con licencia y contacto; secretos fuera del repositorio |

## 7. Criterios de aceptación del MVP (resumen del §14 del plan)

- Desplegable desde instrucciones documentadas (Docker Compose).
- Eventos con proveedor, hora UTC, ubicación, magnitud, profundidad y enlace de procedencia.
- Ingesta sin duplicados al repetirse; cada ejecución y error registrada.
- Dashboard, mapa y gráficas respetan filtros y coinciden con la API.
- Modelos registran dataset, periodo, features, versión, métricas y limitaciones.
- Estimaciones experimentales no se confunden con alertas oficiales.
- Reglas de alertas permiten probar, evitar duplicados y consultar entrega.
- Roles bloquean funciones en interfaz y API.
- Reportes muestran fecha de corte, filtros, fuente y solicitante.
- Pruebas automatizadas, backup probado, guía de operación y procedimiento de incidente.

## 8. Backlog priorizado (mapeo a fases)

| # | Historia | Fase |
|---|---|---|
| B-01 | Como administrador, quiero el esqueleto desplegable (Docker, DB, API, web) | 1 |
| B-02 | Como operador, quiero iniciar sesión con rol para acceder a funciones protegidas | 2 |
| B-03 | Como auditor, quiero consultar la bitácora de acciones críticas | 2 |
| B-04 | Como analista, quiero sincronizar la fuente IGP/CENSIS y ver eventos persistidos sin duplicados | 3 |
| B-05 | Como director, quiero un dashboard con KPIs, series y estado de fuentes | 4 |
| B-06 | Como analista, quiero un mapa sísmico con filtros y leyenda por magnitud | 4 |
| B-07 | Como analista, quiero análisis estadístico (serie, histograma, dispersión, regiones) | 4 |
| B-08 | Como analista, quiero datasets versionados con informe de calidad | 5 |
| B-09 | Como analista, quiero entrenar y comparar modelos de clasificación/regresión | 6 |
| B-10 | Como analista, quiero publicar estimaciones experimentales etiquetadas | 6/7 |
| B-11 | Como operador, quiero crear/reglas de alerta y simular su disparo | 7 |
| B-12 | Como operador, quiero aprobar, enviar y rastrear alertas y sus entregas | 7 |
| B-13 | Como director, quiero reportes exportables con fecha de corte y filtros | 8 |
| B-14 | Como administrador, quiero gestionar usuarios, roles y retención | 8 |
| B-15 | Como responsable técnico, quiero pruebas, checklist y plan de recuperación | 9 |
