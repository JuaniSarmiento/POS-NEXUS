"""
Script de Verificación - Nexus POS
Verifica la conexión a Supabase y la estructura de la base de datos
"""
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def verificar_conexion():
    """Verifica la conexión a Supabase"""
    print("=" * 60)
    print("  NEXUS POS - Verificación de Conexión a Supabase")
    print("=" * 60)
    print()
    
    # Mostrar configuración (sin password)
    print("[1/4] Configuración de conexión:")
    print(f"  Servidor: {settings.POSTGRES_SERVER}")
    print(f"  Usuario: {settings.POSTGRES_USER}")
    print(f"  Base de datos: {settings.POSTGRES_DB}")
    print(f"  Puerto: {settings.POSTGRES_PORT}")
    print()
    
    # Crear engine
    print("[2/4] Creando conexión a la base de datos...")
    try:
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        print("  ✓ Engine creado correctamente")
    except Exception as e:
        print(f"  ✗ Error al crear engine: {e}")
        return False
    
    # Verificar conexión
    print()
    print("[3/4] Probando conexión...")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"  ✓ Conexión exitosa!")
            print(f"  PostgreSQL version: {version[:50]}...")
    except Exception as e:
        print(f"  ✗ Error de conexión: {e}")
        await engine.dispose()
        return False
    
    # Verificar tabla tiendas
    print()
    print("[4/4] Verificando estructura de la tabla 'tiendas'...")
    try:
        async with engine.connect() as conn:
            # Obtener columnas de la tabla tiendas
            query = text("""
                SELECT column_name, data_type, character_maximum_length, column_default, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'tiendas'
                ORDER BY ordinal_position;
            """)
            result = await conn.execute(query)
            columns = result.fetchall()
            
            if not columns:
                print("  ⚠ La tabla 'tiendas' no existe todavía")
                print("  Ejecuta: alembic upgrade head")
                await engine.dispose()
                return False
            
            print("  ✓ Tabla 'tiendas' encontrada")
            print()
            print("  Estructura de la tabla:")
            print("  " + "-" * 90)
            print(f"  {'COLUMNA':<20} {'TIPO':<20} {'MAX':<8} {'NULLABLE':<10} {'DEFAULT':<20}")
            print("  " + "-" * 90)
            
            has_rubro = False
            for col in columns:
                col_name, data_type, max_length, default, nullable = col
                max_len_str = str(max_length) if max_length else "N/A"
                default_str = str(default)[:20] if default else "N/A"
                print(f"  {col_name:<20} {data_type:<20} {max_len_str:<8} {nullable:<10} {default_str:<20}")
                
                if col_name == 'rubro':
                    has_rubro = True
            
            print("  " + "-" * 90)
            print()
            
            # Verificar campo rubro
            if has_rubro:
                print("  ✓ Campo 'rubro' encontrado - Migración aplicada correctamente!")
            else:
                print("  ✗ Campo 'rubro' NO encontrado")
                print("  Ejecuta la migración: alembic upgrade head")
                await engine.dispose()
                return False
            
            # Contar registros
            print()
            count_query = text("SELECT COUNT(*) FROM tiendas")
            result = await conn.execute(count_query)
            count = result.scalar()
            print(f"  Registros en 'tiendas': {count}")
            
            # Mostrar muestra de datos
            if count > 0:
                sample_query = text("""
                    SELECT id, nombre, rubro, is_active, created_at 
                    FROM tiendas 
                    LIMIT 5
                """)
                result = await conn.execute(sample_query)
                tiendas = result.fetchall()
                
                print()
                print("  Muestra de datos:")
                print("  " + "-" * 90)
                for tienda in tiendas:
                    tid, nombre, rubro, is_active, created = tienda
                    print(f"  {nombre:<30} | Rubro: {rubro:<15} | Activa: {is_active}")
                print("  " + "-" * 90)
    
    except Exception as e:
        print(f"  ✗ Error al verificar tabla: {e}")
        await engine.dispose()
        return False
    
    await engine.dispose()
    
    print()
    print("=" * 60)
    print("  ✓ VERIFICACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 60)
    print()
    print("Estado: ✓ Sistema listo para usar")
    print()
    
    return True


async def probar_insercion():
    """Prueba insertar una tienda de ejemplo"""
    print()
    respuesta = input("¿Deseas insertar una tienda de prueba? (s/n): ")
    
    if respuesta.lower() != 's':
        print("Operación cancelada.")
        return
    
    print()
    nombre = input("Nombre de la tienda: ")
    rubro = input("Rubro (ropa/carniceria/ferreteria/general): ")
    
    print()
    print(f"Insertando tienda '{nombre}' con rubro '{rubro}'...")
    
    try:
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async with engine.connect() as conn:
            query = text("""
                INSERT INTO tiendas (id, nombre, rubro, is_active)
                VALUES (gen_random_uuid(), :nombre, :rubro, true)
                RETURNING id, nombre, rubro
            """)
            result = await conn.execute(query, {"nombre": nombre, "rubro": rubro})
            await conn.commit()
            
            tienda = result.fetchone()
            tid, tnombre, trubro = tienda
            
            print(f"  ✓ Tienda creada exitosamente!")
            print(f"  ID: {tid}")
            print(f"  Nombre: {tnombre}")
            print(f"  Rubro: {trubro}")
        
        await engine.dispose()
    except Exception as e:
        print(f"  ✗ Error al insertar tienda: {e}")


if __name__ == "__main__":
    try:
        # Ejecutar verificación
        success = asyncio.run(verificar_conexion())
        
        if success:
            # Ofrecer prueba de inserción
            asyncio.run(probar_insercion())
        else:
            print()
            print("⚠ Verifica los errores arriba y vuelve a intentar.")
            print()
            print("Comandos útiles:")
            print("  alembic current         - Ver estado de migraciones")
            print("  alembic upgrade head    - Aplicar migraciones pendientes")
            print("  alembic history         - Ver historial de migraciones")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print()
        print("Operación cancelada por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
