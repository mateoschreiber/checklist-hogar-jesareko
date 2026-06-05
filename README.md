# Checklist Hogar Server

Dashboard web para controlar quehaceres del hogar, cerrar rutinas, generar comprobantes, guardar historial por usuario y exportar registros.

## Objetivo

Convertir el checklist HTML en una aplicación liviana para servidor local o homelab, optimizada para equipos con pocos recursos.

Diseño técnico aplicado:

- Backend: FastAPI.
- Base de datos: SQLite en archivo persistente.
- Frontend: HTML, CSS y JavaScript sin framework pesado.
- Despliegue: Docker Compose.
- Persistencia: volumen local `./data`.
- Backups: carpeta `./backups`.
- Móvil: interfaz responsive con barra inferior y modal full screen.

## Requisitos del servidor

Recomendado para el caso indicado:

- Ubuntu Server 24.04.
- 2 GB RAM.
- CPU 4 núcleos.
- 5 GB libres mínimos para sistema + backups.
- Docker Engine + Docker Compose plugin.

El sistema evita Postgres, Redis, Node, compilaciones frontend y workers múltiples para reducir consumo de RAM.

## Estructura del repositorio

```text
checklist-hogar-server/
├── app/
│   ├── main.py
│   ├── db.py
│   ├── auth.py
│   ├── checklist_seed.py
│   └── static/
│       ├── index.html
│       ├── styles.css
│       ├── app.js
│       ├── manifest.json
│       └── service-worker.js
├── data/
│   └── .gitkeep
├── backups/
│   └── .gitkeep
├── scripts/
│   ├── backup.sh
│   ├── restore.sh
│   └── init_server_ubuntu24.sh
├── compose.yaml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Funcionalidades

### Dashboard

- Rutinas por frecuencia: diario, cada 3 días, semanal, quincenal, mensual, cada 3 meses, cada 6 meses, anual y por habitación.
- Checks persistentes en el navegador para trabajo en curso.
- Notas por tarea.
- Búsqueda por tarea, zona o rutina.
- Responsive mobile.

### Cierre de rutina

Al presionar **Cerrar rutina**:

- Autocompleta fecha.
- Autocompleta hora.
- Permite elegir responsable.
- Permite elegir rutina o todas las tareas marcadas.
- Guarda tareas realizadas.
- Opcionalmente guarda pendientes.
- Genera comprobante imprimible/PDF.
- Exporta CSV y JSON.

### Historial

- Cada cierre se guarda en SQLite.
- El historial queda asociado al usuario autenticado.
- Los administradores pueden ver todos los cierres.
- Usuarios normales ven sus propios cierres.

### Usuarios

- Login con correo y contraseña.
- Usuario administrador inicial por variables de entorno.
- Alta de usuarios desde el panel administrador.
- Hash de contraseña PBKDF2-HMAC-SHA256.
- Sesiones con cookie `HttpOnly`.

## Instalación rápida con Docker

### 1. Descomprimir el repositorio

```bash
unzip checklist-hogar-server.zip
cd checklist-hogar-server
```

### 2. Crear archivo `.env`

```bash
cp .env.example .env
nano .env
```

Cambiar como mínimo:

```env
APP_SECRET=generar-un-secreto-real
ADMIN_EMAIL=admin@hogar.local
ADMIN_PASSWORD=una-clave-segura
```

Para generar un secreto:

```bash
openssl rand -hex 32
```

### 3. Levantar el servicio

```bash
docker compose up -d --build
```

### 4. Verificar estado

```bash
docker compose ps
curl http://localhost:8080/api/health
```

### 5. Abrir en navegador

```text
http://IP_DEL_SERVIDOR:8080
```

Ingresar con el correo y contraseña definidos en `.env`.

## Instalación de Docker en Ubuntu 24.04

El repositorio incluye un script auxiliar:

```bash
chmod +x scripts/init_server_ubuntu24.sh
./scripts/init_server_ubuntu24.sh
```

Después de ejecutar el script, cerrar sesión y volver a entrar para usar Docker sin `sudo`.

## Comandos útiles

### Ver logs

```bash
docker compose logs -f
```

### Reiniciar

```bash
docker compose restart
```

### Apagar

```bash
docker compose down
```

### Actualizar después de cambios

```bash
docker compose up -d --build
```

## Backups

### Crear backup manual

```bash
docker compose exec checklist-hogar ./scripts/backup.sh
```

El archivo se guarda en:

```text
./backups/
```

### Restaurar backup

Primero detener el servicio:

```bash
docker compose down
```

Restaurar desde el contenedor o copiando manualmente el archivo a `./data/checklist.db`.

Con script dentro del contenedor:

```bash
docker compose run --rm checklist-hogar ./scripts/restore.sh /backups/checklist_backup_YYYYMMDD_HHMMSS.db.gz
```

Luego levantar:

```bash
docker compose up -d
```

## Optimización para servidor de 2 GB RAM

Decisiones aplicadas:

- Un solo contenedor.
- Un solo worker Uvicorn.
- SQLite en archivo local.
- Sin PostgreSQL ni Redis.
- Sin framework frontend pesado.
- Sin proceso de build frontend.
- GZip activado en FastAPI.
- `mem_limit: 512m` en Compose.
- `pids_limit: 256`.

Consumo esperado en reposo: bajo, normalmente muy inferior a 512 MB.

## Seguridad recomendada

Para uso solo en LAN:

- Cambiar `ADMIN_PASSWORD` antes del primer arranque.
- Cambiar `APP_SECRET`.
- Mantener `ALLOW_REGISTRATION=false`.
- Abrir solo el puerto necesario en firewall.
- Hacer backups periódicos de `./data/checklist.db`.

Para exponer fuera de la red local:

- Usar reverse proxy con HTTPS.
- Configurar `COOKIE_SECURE=true`.
- Usar dominio o VPN.
- No publicar directamente sin TLS.

## Variables de entorno

| Variable | Descripción | Valor recomendado |
|---|---|---|
| `APP_PORT` | Puerto local publicado | `8080` |
| `TZ` | Zona horaria del contenedor | `America/Asuncion` |
| `APP_SECRET` | Secreto de aplicación | valor aleatorio largo |
| `ADMIN_NAME` | Nombre del admin inicial | `Administrador` |
| `ADMIN_EMAIL` | Correo del admin inicial | correo real/local |
| `ADMIN_PASSWORD` | Contraseña inicial | clave segura |
| `ALLOW_REGISTRATION` | Registro público | `false` |
| `COOKIE_SECURE` | Cookie solo HTTPS | `false` en LAN, `true` con HTTPS |
| `SESSION_DAYS` | Duración de sesión | `30` |
| `DATABASE_PATH` | Ruta interna de SQLite | `/data/checklist.db` |

## Endpoints principales

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/health` | Estado del servicio |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/logout` | Cerrar sesión |
| `GET` | `/api/users/me` | Usuario actual |
| `GET` | `/api/checklist` | Rutinas y tareas |
| `POST` | `/api/runs` | Guardar cierre de rutina |
| `GET` | `/api/runs` | Historial |
| `GET` | `/api/runs/{id}/receipt` | Comprobante imprimible |
| `GET` | `/api/runs/{id}/export.csv` | Exportar cierre CSV |
| `GET` | `/api/runs/{id}/export.json` | Exportar cierre JSON |
| `GET` | `/api/export/runs.csv` | Exportar historial CSV |
| `GET` | `/api/users` | Usuarios, solo admin |
| `POST` | `/api/users` | Crear usuario, solo admin |

## Fuentes oficiales

- Docker Compose: https://docs.docker.com/compose/
- Compose file reference: https://docs.docker.com/reference/compose-file/
- FastAPI en contenedores Docker: https://fastapi.tiangolo.com/deployment/docker/
- SQLite documentación oficial: https://sqlite.org/docs.html
- Python `sqlite3`: https://docs.python.org/3/library/sqlite3.html
