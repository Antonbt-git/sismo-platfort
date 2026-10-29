# Seeds (datos iniciales)

El sembrado inicial es automatico: al arrancar la API (`app/main.py` → `app/seed.py`) se crean:

- Los 5 roles del sistema: `admin`, `analyst`, `alert_operator`, `auditor`, `viewer`.
- El usuario administrador desde `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` del `.env`
  (cambie la contrasena tras el primer acceso; se registra un warning en los logs).
- La fuente por defecto **IGP / CENSIS (Centro Sismológico Nacional)**, el servicio oficial del
  Instituto Geofísico del Perú (API JSON `censis.igp.gob.pe`, frecuencia 5 min). Los simulacros
  (`tipo_evento` S) se excluyen de la ingesta.

También se depuran las fuentes legadas de USGS: la plataforma opera únicamente con IGP/CENSIS.

Para entornos controlados donde el arranque automatico no es deseable, ejecute la API con la
base ya migrada (`alembic upgrade head`) y despliegue estos datos mediante el panel de
administracion (Usuarios) y `PATCH /api/v1/sources/{id}/status` (fuentes).
