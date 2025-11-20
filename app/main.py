"""
Aplicación Principal - Nexus POS
FastAPI App con configuración Multi-Tenant
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.db import init_db
from app.core.logging_config import setup_logging
from app.core.middleware import RequestIDMiddleware, RequestLoggingMiddleware
from app.core.exceptions import (
    NexusPOSException,
    nexus_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    generic_exception_handler
)
from app.api.routes import auth, productos, ventas, payments, insights, reportes, health, inventario, dashboard, exportar


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ciclo de vida de la aplicación
    Ejecuta inicialización y limpieza
    """
    # Inicializar sistema de logging
    setup_logging(
        log_level="INFO",
        enable_console=True,
        enable_file=True,
        enable_json=False  # True para producción
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info(f"Iniciando {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info("=" * 50)
    
    # Startup: Crear tablas en desarrollo
    # En producción usar Alembic para migraciones
    await init_db()
    logger.info("Base de datos inicializada correctamente")
    
    yield
    
    # Shutdown: Limpiar recursos si es necesario
    logger.info("Cerrando aplicación...")


# Instancia de FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de Request ID y Logging
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestLoggingMiddleware, log_body=False)

# Registrar handlers de excepciones
app.add_exception_handler(NexusPOSException, nexus_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Registro de rutas
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(productos.router, prefix=settings.API_V1_STR)
app.include_router(ventas.router, prefix=settings.API_V1_STR)
app.include_router(payments.router, prefix=settings.API_V1_STR)
app.include_router(insights.router, prefix=settings.API_V1_STR)
app.include_router(reportes.router, prefix=settings.API_V1_STR)
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(inventario.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(exportar.router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Nexus POS API",
        "version": settings.VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Endpoint de salud para monitoreo"""
    return {"status": "healthy"}
