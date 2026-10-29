# Despliegue: Vercel (web) + Render (API e ingesta)

Arquitectura del despliegue:

```
Navegador
  └─ Vercel  ── apps/web (React + Vite, sitio estático)
       └─ VITE_API_URL ──► Render ── sismo-api (FastAPI + Docker)
                                │
                                ├─ Supabase (PostgreSQL, datos)
                                └─ Render ── sismo-ingesta (worker IGP/CENSIS)
```

La base de datos ya vive en Supabase, así que solo se despliegan el frontend y los dos procesos de
`services/` (API y daemon de ingesta).

## 0. Requisitos previos

- Repositorio en GitHub (el proyecto local aún no es un repo git):

  ```bash
  cd sismo-platform
  git init && git branch -M main
  git add . && git commit -m "Plataforma de monitoreo sismico IGP/CENSIS"
  git remote add origin https://github.com/<usuario>/sismo-platform.git
  git push -u origin main
  ```

  `.gitignore` ya excluye `.env`, `var/`, `node_modules/`, `dist/` y los `*.sqlite3`.

- Cuentas en Vercel y Render conectadas a ese repositorio.

## 1. API en Render

El archivo `render.yaml` de la raíz ya declara el servicio web y el worker; con él basta un click.

1. Render → **New +** → **Blueprint** → seleccionar el repositorio.
2. Render detecta `render.yaml` y propone dos servicios:
   - `sismo-api` (web, Docker, `infra/docker/Dockerfile.backend`), health check `/health`.
   - `sismo-ingesta` (worker, mismo Docker, comando `python /app/services/ingestion/sync.py --loop --interval 300`).
3. Completar las variables marcadas con `sync: false` en **sismo-api**:

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | `postgresql+psycopg://postgres.<ref>:<clave>@aws-1-us-west-2.pooler.supabase.com:5432/postgres` |
   | `SEED_ADMIN_PASSWORD` | contraseña del admin (si el usuario ya existe en Supabase no se sobrescribe) |
   | `CORS_ORIGINS` | `["https://<tu-app>.vercel.app"]` |

   `SECRET_KEY` se genera automáticamente. El resto (`ARTIFACTS_DIR=/app/var/artifacts`,
   `REPORTS_DIR=/app/var/reports`, intervalos de ingesta) ya viene en el blueprint.
4. En el worker `sismo-ingesta` basta repetir `DATABASE_URL` (las demás variables ya están).
5. Desplegar y comprobar `https://sismo-api.onrender.com/health` → `{"status":"ok"}`.

Notas:

- El blueprint usa `plan: starter` porque el disco persistente de 1 GB (`/app/var`) solo existe en
  planes pagados. En el plan free hay que quitar el bloque `disk`; los artefactos `.joblib` y los
  reportes generados se pierden en cada reinicio/despliegue.
- El esquema se crea solo: la API llama a `Base.metadata.create_all()` y a `seed_all()` al arrancar.
- Si se despliega sin `render.yaml` (servicio manual), usar **Environment: Docker**,
  **Dockerfile Path** `infra/docker/Dockerfile.backend`, **Docker Context** `.` y **Health Check Path** `/health`.

## 2. Frontend en Vercel

1. Vercel → **Add New…** → **Project** → importar el repositorio.
2. Configuración del proyecto:
   - **Root Directory**: `apps/web`
   - **Framework Preset**: Vite (autodetectado)
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. **Environment Variables** (Production y Preview):

   | Variable | Valor |
   |---|---|
   | `VITE_API_URL` | `https://sismo-api.onrender.com` (sin `/` final) |

   Vite incrusta esta variable **en tiempo de build**: si se cambia, hay que volver a desplegar.
4. Deploy. `apps/web/vercel.json` ya incluye el rewrite de SPA para que rutas como `/eventos` o
   `/estimaciones` funcionen al recargar.

## 3. Cerrar el círculo (CORS)

Cuando Vercel asigne el dominio final:

1. Render → `sismo-api` → Environment → editar `CORS_ORIGINS`, por ejemplo:

   ```json
   ["https://sismo-platform.vercel.app","http://localhost:5173"]
   ```

2. Guardar (Render reinicia el servicio) y recargar la web.

Si se usan dominios de *preview* de Vercel, hay que añadirlos también (no se admiten comodines salvo `"*"`,
que no se recomienda con cookies/tokens).

## 4. Verificación posterior

- `GET https://sismo-api.onrender.com/health` → `{"status":"ok"}`.
- Login en la web desplegada con el usuario de Supabase.
- Dashboard/Eventos muestran el catálogo (881 eventos) y el badge **EN VIVO** se pone verde
  (SSE directo contra Render, sin pasar por Vercel).
- Render → `sismo-ingesta` → Logs: `Sincronizacion ok: vistos=... insertados=...`.
- Auditoría registra los `auth.login` nuevos.

## 5. Limitaciones a tener en cuenta

- **Artefactos ML**: `ml_experiments.artifact_uri` guarda rutas del equipo local
  (`/home/luis/.../var/artifacts/*.joblib`). En Render esos archivos no existen, así que tras el
  primer despliegue hay que **reentrenar los experimentos** desde *Modelos ML → Entrenar*: el
  entrenamiento corre en el contenedor y deja el `.joblib` en el disco `/app/var/artifacts`.
  Sin reentrenar, publicar estimaciones desde esos modelos fallará.
- **Plan free de Render**: el servicio web se suspende a los ~15 minutos sin tráfico (primer acceso
  lento y reconexión del SSE) y no hay disco persistente. Para un uso real: plan Starter.
- **Pooler de Supabase**: usar el puerto `5432` (modo sesión). El puerto `6543` (transaction mode)
  rompe conexiones persistentes de SQLAlchemy.
- **Secretos**: `DATABASE_URL` y `SECRET_KEY` solo en los paneles de Render/Vercel; `.env` está en
  `.gitignore`. Rotar la contraseña de Postgres si estuvo en texto plano en algún archivo compartido.
- **Reportes**: se generan en `REPORTS_DIR` (disco de Render). Para conservarlos entre despliegues
  hace falta el disco persistente del plan Starter.
