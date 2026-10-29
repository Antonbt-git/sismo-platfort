# Despliegue gratuito: Vercel (web) + Render (API) + Supabase (datos)

Arquitectura, todo en planes gratuitos:

```
Navegador
  └─ Vercel  ── apps/web (React + Vite, sitio estatico, plan Hobby)
       └─ VITE_API_URL ──► Render ── sismo-api (FastAPI, Docker, plan free)
                                └─ Supabase (PostgreSQL)
GitHub Actions (cron cada hora) ── ingestion/sync.py ──► Supabase
```

El plan free de Render no incluye disco persistente ni workers, por eso:

- Los artefactos `.joblib` se guardan **tambien en la base de datos**
  (`ml_experiments.artifact_blob`), así los modelos siguen funcionando tras cada reinicio.
- La ingesta IGP/CENSIS corre con un **workflow programado de GitHub Actions** en lugar de un worker.

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

- Cuentas gratuitas en Vercel, Render y GitHub.

## 1. API en Render (free)

1. Render → **New +** → **Web Service** → conectar el repositorio (no hace falta Blueprint).
2. Configuración:
   - **Language / Runtime**: Docker
   - **Dockerfile Path**: `infra/docker/Dockerfile.backend`
   - **Docker Build Context Directory**: `.` (raíz del repo)
   - **Instance Type**: Free
   - **Health Check Path**: `/health`
3. **Environment Variables**:

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | `postgresql+psycopg://postgres.<ref>:<clave>@aws-1-us-west-2.pooler.supabase.com:5432/postgres` |
   | `SEED_ADMIN_PASSWORD` | contraseña del admin (si el usuario ya existe en Supabase no se sobrescribe) |
   | `CORS_ORIGINS` | `["https://<tu-app>.vercel.app"]` |
   | `SECRET_KEY` | cualquier cadena larga aleatoria (`openssl rand -hex 32`) |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `600` |
   | `ARTIFACTS_DIR` | `/app/var/artifacts` |
   | `REPORTS_DIR` | `/app/var/reports` |

4. Deploy y comprobar `https://sismo-api.onrender.com/health` → `{"status":"ok"}`.

> El archivo `render.yaml` de la raíz describe esta misma configuración gratuita por si prefieres
> **New + → Blueprint**; también funciona sin coste (no declara disco ni worker).

## 2. Ingesta automática sin worker (GitHub Actions)

El cron vive en `.github/workflows/ingest.yml` (cada hora, y también manual desde *Actions →
Ingesta IGP/CENSIS → Run workflow*).

1. GitHub → **Settings → Secrets and variables → Actions → New repository secret**:
   - `SUPABASE_DATABASE_URL` = la misma cadena `postgresql+psycopg://...` de Supabase.
   - (opcional) `SECRET_KEY` = la misma de Render.
2. Verificar en *Actions* que la primera ejecución termina en verde y que en la web aparecen
   eventos nuevos / registros en Auditoría.

Frecuencia: cada hora (`0 * * * *`). Con repositorio público se puede usar `*/30 * * * *` sin
consumir minutos; en repositorio privado, cada hora mantiene el consumo dentro del plan gratuito.

## 3. Frontend en Vercel (Hobby)

1. Vercel → **Add New…** → **Project** → importar el repositorio.
2. Configuración:
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

## 4. Cerrar el círculo (CORS)

Con el dominio final de Vercel:

1. Render → `sismo-api` → Environment → `CORS_ORIGINS`:

   ```json
   ["https://sismo-platform.vercel.app","http://localhost:5173"]
   ```

2. Guardar (Render reinicia) y recargar la web.

Los dominios de *preview* de Vercel cambian en cada push; si los necesitas, agrégalos a mano (no se
admiten comodines salvo `"*"`, que no se recomienda cuando se envían tokens).

## 5. Verificación posterior

- `GET https://sismo-api.onrender.com/health` → `{"status":"ok"}` (el primer acceso tras inactividad
  tarda ~30-60 s porque Render free suspende la instancia).
- Login en la web con el usuario de Supabase.
- Dashboard/Eventos muestran el catálogo y el badge **EN VIVO** se pone verde (SSE directo a Render).
- Publicar una estimación: el modelo se carga desde `artifact_blob` aunque no exista el archivo.
- GitHub Actions → última ejecución de *Ingesta IGP/CENSIS* en verde.

## 6. Limitaciones del plan gratuito

- **Suspensión por inactividad**: Render free duerme la API a los ~15 minutos sin tráfico; la primera
  petición tarda en despertar y el SSE se reconecta solo.
- **Sin disco persistente**: `ARTIFACTS_DIR` y `REPORTS_DIR` viven en el contenedor y se borran en
  cada despliegue. Los modelos no se pierden (van en `artifact_blob`); los reportes sí, pero se
  generan y descargan al momento.
- **Reentrenar**: si entrenas un experimento y el contenedor se reinicia antes de que termine, el
  experimento queda `running`; basta relanzarlo desde *Modelos ML*.
- **Supabase free**: 500 MB de base de datos y pausa del proyecto tras 7 días sin consultas.
  Cada modelo ocupa ~4 MB en `artifact_blob`.
- **Pooler de Supabase**: usar el puerto `5432` (modo sesión). El `6543` (transaction mode) rompe las
  conexiones persistentes de SQLAlchemy.
- **Secretos**: `DATABASE_URL`, `SECRET_KEY` y `SEED_ADMIN_PASSWORD` solo en Render/GitHub; el `.env`
  local está en `.gitignore`. Rota la contraseña de Postgres si estuvo en texto plano en algún chat
  o archivo compartido.

## 7. Cuando puedas pagar (opcional)

Con el plan Starter de Render (~7 USD/mes) se puede volver al esquema “clásico”:

- Añadir disco persistente montado en `/app/var` (1 GB) al servicio web.
- Crear un **Background Worker** con el mismo Dockerfile y comando
  `python /app/services/ingestion/sync.py --loop --interval 300`, y desactivar el workflow de GitHub.
- Eliminar la copia en BD (`artifact_blob`) si prefieres no duplicar los `.joblib`.
