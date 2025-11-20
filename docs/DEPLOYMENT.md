# Nexus POS - Deployment Guide

## 🚀 Guía Rápida de Despliegue

### Prerrequisitos

- Docker 24+ y Docker Compose v2
- Python 3.11+ (para desarrollo local)
- `uv` instalado: `pip install uv`

---

## 📦 Instalación Local (Desarrollo)

### 1. Clonar y configurar entorno

```bash
# Clonar repositorio
git clone <repo-url>
cd POS

# Copiar variables de entorno
cp .env.example .env

# Editar .env con tus credenciales
nano .env
```

### 2. Instalar dependencias con uv

```bash
# Instalar uv si no lo tienes
pip install uv

# Instalar dependencias del proyecto
uv pip install -e ".[dev]"
```

### 3. Levantar base de datos

```bash
# Opción A: Solo PostgreSQL con Docker
docker-compose up -d db

# Opción B: Levantar todo el stack
docker-compose up -d
```

### 4. Ejecutar migraciones

```bash
# Auto-crear tablas con SQLModel
make migrate

# O manualmente:
uv run python -c "from app.core.db import init_db; import asyncio; asyncio.run(init_db())"
```

### 5. Ejecutar servidor de desarrollo

```bash
# Con Makefile
make dev

# O directamente:
uv run uvicorn app.main:app --reload
```

**API disponible en:** http://localhost:8000  
**Documentación:** http://localhost:8000/api/v1/docs

---

## 🐳 Despliegue con Docker Compose

### Modo Básico (Solo API + DB)

```bash
# Construir y levantar
docker-compose up -d --build

# Ver logs
docker-compose logs -f backend

# Verificar salud
curl http://localhost:8000/health
```

### Modo Completo (Con Celery para tareas de fondo)

```bash
# Levantar con profile celery
docker-compose --profile celery up -d --build

# Servicios incluidos:
# - backend (FastAPI)
# - db (PostgreSQL 17)
# - redis (Broker para Celery)
# - celery_worker (Procesamiento de tareas)
# - celery_beat (Scheduler)
# - flower (Monitoreo Celery)
# - adminer (Gestión DB)
```

**Servicios disponibles:**
- API: http://localhost:8000
- Adminer: http://localhost:8080
- Flower: http://localhost:5555 (solo con profile celery)

---

## 🔧 Configuración de Variables de Entorno

### Variables Críticas (OBLIGATORIAS)

```bash
# Generar SECRET_KEY segura
openssl rand -hex 32

# En .env:
SECRET_KEY=<resultado del comando anterior>
POSTGRES_PASSWORD=<password_seguro>
```

### Variables Opcionales

```bash
# Mercado Pago (para pagos)
MERCADOPAGO_ACCESS_TOKEN=TEST-xxx  # Desde panel de desarrolladores

# Sentry (monitoreo de errores)
SENTRY_DSN=https://xxx@sentry.io/xxx

# AFIP (facturación - mock por ahora)
AFIP_CUIT=20123456789
```

---

## 🔄 Comandos Útiles

### Gestión de Servicios

```bash
# Detener todos los servicios
docker-compose down

# Reiniciar solo el backend
docker-compose restart backend

# Ver logs en tiempo real
docker-compose logs -f

# Eliminar volúmenes (CUIDADO: borra la BD)
docker-compose down -v
```

### Base de Datos

```bash
# Conectar al shell de PostgreSQL
make db-shell
# O:
docker-compose exec db psql -U nexuspos -d nexus_pos

# Backup de la base de datos
docker-compose exec db pg_dump -U nexuspos nexus_pos > backup.sql

# Restaurar backup
docker-compose exec -T db psql -U nexuspos nexus_pos < backup.sql
```

### Desarrollo

```bash
# Verificar código con Ruff
make lint

# Auto-corregir errores
make lint-fix

# Formatear código
make format

# Ejecutar tests
make test
```

---

## 🌐 Despliegue en Producción

### Opción 1: VPS/Cloud con Docker

**1. Preparar servidor**

```bash
# En el servidor (Ubuntu/Debian)
sudo apt update
sudo apt install docker.io docker-compose-v2

# Clonar proyecto
git clone <repo-url>
cd POS
```

**2. Configurar entorno**

```bash
# Copiar y editar .env
cp .env.example .env
nano .env

# Cambiar:
ENVIRONMENT=production
POSTGRES_PASSWORD=<password_super_seguro>
SECRET_KEY=<usar openssl rand -hex 32>
```

**3. Levantar con SSL (Traefik)**

El `docker-compose.yml` ya incluye labels de Traefik. Si usas Traefik como reverse proxy:

```yaml
# Traefik automáticamente obtiene certificados SSL
# Solo configurar el dominio en labels:
- "traefik.http.routers.nexus-backend.rule=Host(`api.tudominio.com`)"
```

**4. Desplegar**

```bash
# Producción sin Celery
make prod

# Producción con Celery (recomendado)
make prod-celery
```

### Opción 2: Railway/Render/Fly.io

Estos servicios automatizan el deploy desde Git. Configurar:

1. **Variables de entorno** en el dashboard
2. **Puerto**: 8000
3. **Comando de inicio**: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`

---

## 📊 Monitoreo

### Health Check

```bash
# Verificar salud del API
curl http://localhost:8000/health

# Respuesta esperada:
{"status": "healthy"}
```

### Celery Flower (si está habilitado)

Acceder a http://localhost:5555 para ver:
- Tareas en ejecución
- Workers activos
- Historial de tareas
- Métricas

### Sentry (Errores)

Configurar `SENTRY_DSN` en `.env` para recibir alertas de errores en producción.

---

## 🔐 Seguridad en Producción

### Checklist de Seguridad

- [ ] Cambiar `POSTGRES_PASSWORD` a valor seguro
- [ ] Generar nuevo `SECRET_KEY` con `openssl rand -hex 32`
- [ ] Configurar `BACKEND_CORS_ORIGINS` solo con dominios permitidos
- [ ] No exponer puerto de PostgreSQL (5432) públicamente
- [ ] Activar HTTPS con certificado SSL
- [ ] Configurar firewall para limitar acceso a puertos
- [ ] Activar Sentry para monitoreo de errores
- [ ] Implementar rate limiting (nginx/Traefik)
- [ ] Backups automáticos de PostgreSQL

---

## 🐛 Troubleshooting

### El backend no inicia

```bash
# Ver logs detallados
docker-compose logs backend

# Verificar que la DB está lista
docker-compose ps db
```

### Error de conexión a base de datos

```bash
# Verificar que db está healthy
docker-compose ps

# Reintentar conexión (tenacity reintenta automáticamente)
docker-compose restart backend
```

### Celery no procesa tareas

```bash
# Verificar que Redis está corriendo
docker-compose ps redis

# Ver logs del worker
docker-compose logs celery_worker
```

---

## 📚 Recursos Adicionales

- **Documentación API:** http://localhost:8000/api/v1/docs (Swagger)
- **ReDoc:** http://localhost:8000/api/v1/redoc
- **Adminer:** http://localhost:8080 (Gestor de BD)

---

**¡Listo para producción! 🚀**
