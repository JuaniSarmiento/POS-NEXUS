"""
Alembic Environment - Nexus POS
Configuración para migraciones asíncronas con SQLModel y Supabase
"""
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path para importar los modelos
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.models import SQLModel

# Configuración de Alembic
config = context.config

# Interpretar el archivo de configuración para logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata de SQLModel (incluye todos los modelos importados)
target_metadata = SQLModel.metadata

# Sobrescribir la URL de conexión con la del .env
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Ejecutar migraciones en modo 'offline'.
    
    Configura el contexto con solo una URL y no un Engine,
    aunque un Engine también es aceptable aquí. Al omitir
    la creación del Engine, no necesitamos DBAPI disponible.
    
    Se emiten llamadas a context.execute() aquí para emitir
    la cadena DDL dada al archivo de script.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Función auxiliar para ejecutar las migraciones"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Ejecutar migraciones asíncronas en modo 'online'.
    
    En este escenario necesitamos crear un Engine y asociar
    una conexión con el contexto.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Ejecutar migraciones en modo 'online' con asyncio.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
