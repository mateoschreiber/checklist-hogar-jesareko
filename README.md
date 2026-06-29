# Checklist Hogar

Aplicación web liviana para checklist del hogar en entorno local/LAN. Usa FastAPI, SQLite, HTML/CSS/JS simple y Docker Compose sin dependencias pesadas.

## Alcance

- Login local por `username` y contraseña.
- Credenciales iniciales compatibles para modo controlado local: `admin:admin`.
- Roles simples: `admin`, `usuario`, `solo_lectura`.
- Fechas locales explícitas para cierres, historial y calendario.
- Backup y restore local sobre SQLite.
- PWA mínima con caché simple de estáticos.

## Advertencia

Modo local/LAN. No exponer a internet sin hardening adicional, HTTPS, reverse proxy y credenciales fuertes.

## Variables `.env`

Partí de [`.env.example`](/opt/checklist-hogar-jesareko/.env.example).

```env
LOCAL_ONLY=true
ADMIN_USER=admin
ADMIN_PASSWORD=admin
APP_PORT=8080
TZ=America/Asuncion
APP_SECRET=change-me-with-openssl-rand-hex-32
COOKIE_SECURE=false
SESSION_DAYS=30
DATABASE_PATH=/data/checklist.db
BACKUP_DIR=/backups
BACKUP_KEEP=10
ALLOW_REGISTRATION=false
```

## Instalación LAN con Docker Compose

1. Crear `.env`:

```bash
cp .env.example .env
```

2. Cambiar al menos `APP_SECRET` y la contraseña del admin si no vas a dejar el modo controlado `admin:admin`.

3. Levantar:

```bash
docker compose up -d --build
```

4. Verificar:

```bash
docker compose ps
curl http://localhost:8080/api/health
```

5. Abrir desde la misma red:

```text
http://IP_DEL_SERVIDOR:8080
```

Desde celular en la misma red usa la IP LAN del servidor en el mismo puerto.

## Credenciales locales por defecto

Si la base está vacía al primer arranque:

- Usuario: `admin`
- Contraseña: `admin`

Cambiá la contraseña del admin desde el panel de administración después del primer acceso o ajustando `ADMIN_PASSWORD` antes del primer arranque.

## Flujo básico

- `admin` puede crear usuarios, cambiar rol, activar/desactivar, cambiar contraseña, administrar ítems, ver historial completo, desactivar cierres y gestionar backups.
- `usuario` puede marcar checklist, generar cierres y ver su historial/calendario.
- `solo_lectura` puede ver checklist, calendario, historial y comprobantes, pero no modifica nada.

## Backup y restore

### Desde la interfaz

En Administración:

- `Crear backup manual`
- `Descargar`
- `Restaurar`

### Desde scripts

Crear backup:

```bash
docker compose exec checklist-hogar ./scripts/backup.sh
```

Restaurar backup existente:

```bash
docker compose exec checklist-hogar ./scripts/restore.sh /backups/checklist_backup_YYYYMMDD_HHMMSS.db.gz
```

Los backups antiguos se limpian de forma simple manteniendo `BACKUP_KEEP` archivos.

## Actualización

```bash
git pull
docker compose up -d --build
```

## Acceso desde celular en la misma red

1. Conocer la IP LAN del servidor.
2. Confirmar que el puerto `APP_PORT` esté abierto en la red local.
3. Abrir `http://IP_DEL_SERVIDOR:APP_PORT` desde el navegador del celular.
4. Instalar como app desde el navegador si el dispositivo ofrece la opción.

## Comandos útiles

```bash
docker compose logs -f
docker compose restart
docker compose down
docker compose up -d --build
```

## Stack y consumo

- 1 contenedor
- 1 worker Uvicorn
- SQLite local
- Sin Postgres, Redis, React, Vue ni build frontend
- Límites simples en Compose: `mem_limit: 512m`, `pids_limit: 256`
- Rotación básica de logs del contenedor
