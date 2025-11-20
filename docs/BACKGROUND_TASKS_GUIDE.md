# Guía de Implementación: Tareas de Fondo para Insights

## Nexus POS - Motor de Insights Periódico

Esta guía documenta cómo implementar la generación automática de insights en segundo plano usando diferentes estrategias.

---

## 📋 Opciones de Implementación

### Opción 1: FastAPI BackgroundTasks (Incluido - Básico)

**✅ Ya implementado en el código**

**Ventajas:**
- No requiere dependencias adicionales
- Fácil de usar
- Ideal para tareas ligeras

**Limitaciones:**
- Las tareas mueren si el servidor se reinicia
- No hay persistencia de tareas
- No hay reintentos automáticos
- Ejecuta en el mismo proceso que la API

**Uso:**
```python
# Ya disponible en /api/v1/insights/background-refresh
# Solo agrega la tarea al pool de background tasks de FastAPI
```

---

### Opción 2: Celery + Redis (Recomendado para Producción)

**Ideal para:**
- Tareas pesadas o de larga duración
- Necesidad de reintentos automáticos
- Ejecución periódica (cron)
- Escalabilidad horizontal

**Instalación:**
```bash
pip install celery[redis]
pip install redis
```

**Estructura de archivos:**
```
app/
├── celery_app.py          # Configuración de Celery
├── tasks/
│   ├── __init__.py
│   └── insights_tasks.py  # Tareas de insights
└── ...
```

**1. Crear `app/celery_app.py`:**
```python
"""
Configuración de Celery para Nexus POS
"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Crear instancia de Celery
celery_app = Celery(
    "nexus_pos",
    broker=f"redis://localhost:6379/0",
    backend=f"redis://localhost:6379/0"
)

# Configuración
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Argentina/Buenos_Aires',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos máximo por tarea
)

# Configurar tareas periódicas (Beat Schedule)
celery_app.conf.beat_schedule = {
    'generar-insights-cada-hora': {
        'task': 'app.tasks.insights_tasks.generate_all_insights_task',
        'schedule': crontab(minute=0),  # Cada hora en punto
    },
    'generar-insights-stock-cada-30min': {
        'task': 'app.tasks.insights_tasks.generate_stock_alerts_task',
        'schedule': crontab(minute='*/30'),  # Cada 30 minutos
    },
    'generar-insights-ventas-diarias': {
        'task': 'app.tasks.insights_tasks.generate_sales_summary_task',
        'schedule': crontab(hour=20, minute=0),  # Todos los días a las 20:00
    },
}
```

**2. Crear `app/tasks/insights_tasks.py`:**
```python
"""
Tareas de Celery para generación de insights
"""
import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.celery_app import celery_app
from app.services.insight_service import insight_service
from app.core.config import settings
from app.models import Tienda
from sqlmodel import select

logger = logging.getLogger(__name__)

# Crear engine para tareas async
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@celery_app.task(name="app.tasks.insights_tasks.generate_all_insights_task")
def generate_all_insights_task():
    """
    Tarea que genera insights para TODAS las tiendas activas
    Se ejecuta cada hora
    """
    import asyncio
    
    async def _run():
        async with AsyncSessionLocal() as session:
            # Obtener todas las tiendas activas
            statement = select(Tienda).where(Tienda.is_active == True)
            result = await session.execute(statement)
            tiendas = result.scalars().all()
            
            logger.info(f"Generando insights para {len(tiendas)} tiendas")
            
            for tienda in tiendas:
                try:
                    resultado = await insight_service.generate_all_insights(
                        tienda_id=tienda.id,
                        session=session
                    )
                    logger.info(f"Tienda {tienda.nombre}: {resultado}")
                except Exception as e:
                    logger.error(f"Error generando insights para {tienda.nombre}: {str(e)}")
    
    asyncio.run(_run())
    return {"status": "completed"}


@celery_app.task(name="app.tasks.insights_tasks.generate_stock_alerts_task")
def generate_stock_alerts_task():
    """
    Genera solo alertas de stock para todas las tiendas
    Se ejecuta cada 30 minutos
    """
    import asyncio
    
    async def _run():
        async with AsyncSessionLocal() as session:
            statement = select(Tienda).where(Tienda.is_active == True)
            result = await session.execute(statement)
            tiendas = result.scalars().all()
            
            for tienda in tiendas:
                try:
                    alerts = await insight_service.generate_stock_alerts(
                        tienda_id=tienda.id,
                        session=session
                    )
                    logger.info(f"Tienda {tienda.nombre}: {len(alerts)} alertas de stock")
                except Exception as e:
                    logger.error(f"Error: {str(e)}")
    
    asyncio.run(_run())


@celery_app.task(name="app.tasks.insights_tasks.generate_sales_summary_task")
def generate_sales_summary_task():
    """
    Genera resumen de ventas diario
    Se ejecuta todos los días a las 20:00
    """
    import asyncio
    
    async def _run():
        async with AsyncSessionLocal() as session:
            statement = select(Tienda).where(Tienda.is_active == True)
            result = await session.execute(statement)
            tiendas = result.scalars().all()
            
            for tienda in tiendas:
                try:
                    summary = await insight_service.generate_sales_summary(
                        tienda_id=tienda.id,
                        session=session,
                        horas=24
                    )
                    if summary:
                        logger.info(f"Resumen generado para {tienda.nombre}")
                except Exception as e:
                    logger.error(f"Error: {str(e)}")
    
    asyncio.run(_run())
```

**3. Crear `app/tasks/__init__.py`:**
```python
"""Tasks package"""
from app.tasks.insights_tasks import (
    generate_all_insights_task,
    generate_stock_alerts_task,
    generate_sales_summary_task
)
```

**4. Ejecutar Celery:**

**Terminal 1 - Worker (procesa tareas):**
```bash
celery -A app.celery_app worker --loglevel=info
```

**Terminal 2 - Beat (scheduler):**
```bash
celery -A app.celery_app beat --loglevel=info
```

**Terminal 3 - FastAPI:**
```bash
uvicorn app.main:app --reload
```

**5. Monitoreo con Flower (opcional):**
```bash
pip install flower
celery -A app.celery_app flower --port=5555
```
Abrir: http://localhost:5555

---

### Opción 3: APScheduler (Alternativa sin Redis)

**Ventajas:**
- No requiere Redis
- Más simple que Celery
- Corre en el mismo proceso

**Limitaciones:**
- No distribuido
- Menos robusto que Celery

**Instalación:**
```bash
pip install apscheduler
```

**Implementación en `app/main.py`:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.insight_service import insight_service
from app.core.db import AsyncSessionLocal
from app.models import Tienda
from sqlmodel import select

scheduler = AsyncIOScheduler()

async def job_generar_insights():
    """Job que corre cada hora"""
    async with AsyncSessionLocal() as session:
        statement = select(Tienda).where(Tienda.is_active == True)
        result = await session.execute(statement)
        tiendas = result.scalars().all()
        
        for tienda in tiendas:
            await insight_service.generate_all_insights(
                tienda_id=tienda.id,
                session=session
            )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    
    # Configurar scheduler
    scheduler.add_job(
        job_generar_insights,
        CronTrigger(minute=0),  # Cada hora
        id="insights_hourly",
        replace_existing=True
    )
    scheduler.start()
    
    yield
    
    # Shutdown
    scheduler.shutdown()
```

---

## 🚀 Recomendación por Escenario

### Desarrollo/Testing
- **FastAPI BackgroundTasks** (ya implementado)
- Trigger manual: `POST /insights/refresh`

### Staging/Pequeña Escala
- **APScheduler**
- Fácil de configurar
- Sin dependencias externas

### Producción/Gran Escala
- **Celery + Redis**
- Escalable horizontalmente
- Reintentos automáticos
- Monitoreo con Flower

---

## 📊 Configuración de Horarios Recomendada

```python
# Stock bajo: Cada 30 minutos
crontab(minute='*/30')

# Productos sin stock: Cada 15 minutos (más urgente)
crontab(minute='*/15')

# Ventas diarias: Al final del día
crontab(hour=20, minute=0)

# Ventas semanales: Lunes 9 AM
crontab(day_of_week=1, hour=9, minute=0)
```

---

## 🛠️ Actualización de `requirements.txt`

```txt
# Tareas de Fondo (opcional - descomentar según opción elegida)

# Opción Celery:
# celery[redis]==5.3.4
# redis==5.0.1
# flower==2.0.1  # Monitoreo

# Opción APScheduler:
# apscheduler==3.10.4
```

---

## ✅ Testing

**Test manual con endpoint:**
```bash
curl -X POST "http://localhost:8000/api/v1/insights/refresh" \
  -H "Authorization: Bearer <token>"
```

**Verificar Celery:**
```bash
celery -A app.celery_app inspect active
celery -A app.celery_app inspect scheduled
```

---

Esta guía te permite elegir la estrategia que mejor se adapte a tu caso de uso.
