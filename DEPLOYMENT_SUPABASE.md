# 🚀 Nexus POS - Deployment Guide para Supabase

## 📋 Resumen de Cambios Implementados

### 1. ✅ Modelo Tienda Actualizado
Se agregó el campo `rubro` al modelo `Tienda` en `app/models.py`:
```python
rubro: str = Field(
    default="general",
    max_length=50,
    nullable=False,
    description="Categoría del negocio: ropa, carniceria, ferreteria, etc."
)
```

### 2. ✅ Conexión a Supabase Configurada
El archivo `.env` ahora está configurado para conectarse a Supabase:
```env
POSTGRES_SERVER=aws-1-us-east-2.pooler.supabase.com
POSTGRES_USER=postgres.kdqfohbtxlmykjubxqok
POSTGRES_PASSWORD=Juani2006
POSTGRES_DB=postgres
POSTGRES_PORT=5432
```

**URL de conexión generada automáticamente:**
```
postgresql+asyncpg://postgres.kdqfohbtxlmykjubxqok:Juani2006@aws-1-us-east-2.pooler.supabase.com:5432/postgres
```

### 3. ✅ Errores de Tipo Corregidos
Se agregaron validaciones explícitas en `app/api/routes/productos.py`:
- Validación de `None` antes de acceder a atributos
- Manejo explícito de resultados de queries
- Uso de `is not None` en lugar de truthy checks

### 4. ✅ Build de Docker Configurado
`pyproject.toml` ya incluye:
```toml
[tool.hatch.build.targets.wheel]
packages = ["app"]
```

### 5. ✅ Alembic Configurado para Supabase
Se creó la estructura completa de Alembic con soporte asíncrono.

---

## 🔧 Comandos de Migración

### Paso 1: Instalar Alembic
```powershell
pip install alembic
```

### Paso 2: Generar la Migración Inicial
Este comando detectará automáticamente el nuevo campo `rubro` y todas las tablas:
```powershell
alembic revision --autogenerate -m "add_rubro_field_to_tienda"
```

### Paso 3: Revisar la Migración
Abre el archivo generado en `alembic/versions/` y verifica que contenga:
```python
# Debería incluir algo como:
op.add_column('tiendas', sa.Column('rubro', sa.String(length=50), nullable=False, server_default='general'))
```

### Paso 4: Aplicar la Migración a Supabase
```powershell
alembic upgrade head
```

### Comandos Adicionales Útiles

**Ver el estado actual:**
```powershell
alembic current
```

**Ver el historial de migraciones:**
```powershell
alembic history
```

**Revertir una migración:**
```powershell
alembic downgrade -1
```

**Revertir todas las migraciones:**
```powershell
alembic downgrade base
```

---

## 📝 Verificación de la Migración

### 1. Conectarse a Supabase SQL Editor
Ve a tu proyecto en Supabase → SQL Editor y ejecuta:

```sql
-- Verificar que la tabla tiendas tiene el campo rubro
SELECT column_name, data_type, character_maximum_length, column_default
FROM information_schema.columns
WHERE table_name = 'tiendas' AND column_name = 'rubro';
```

### 2. Verificar las Tiendas Existentes
```sql
-- Ver todas las tiendas con su rubro
SELECT id, nombre, rubro, is_active, created_at
FROM tiendas;
```

### 3. Insertar una Tienda de Prueba
```sql
-- Crear una tienda de prueba
INSERT INTO tiendas (id, nombre, rubro, is_active)
VALUES (
    gen_random_uuid(),
    'Boutique Fashion',
    'ropa',
    true
);
```

---

## 🧪 Testing Local Antes de Migrar

Para probar las migraciones localmente antes de aplicarlas a Supabase:

### 1. Usar Docker Local
```powershell
docker-compose up -d
```

### 2. Aplicar Migración Local
```powershell
# Asegúrate de que .env apunte a localhost temporalmente
alembic upgrade head
```

### 3. Cambiar de nuevo a Supabase
Restaura las variables en `.env` y ejecuta:
```powershell
alembic upgrade head
```

---

## 🔒 Seguridad - IMPORTANTE

### ⚠️ Cambiar SECRET_KEY en Producción
El `.env` actual tiene una clave de ejemplo. Para producción real:

```powershell
# Generar una nueva SECRET_KEY segura
python -c "import secrets; print(secrets.token_hex(32))"
```

Reemplaza el valor en `.env`:
```env
SECRET_KEY=<nueva_clave_generada>
```

---

## 📦 Estructura de Archivos Creada

```
POS/
├── alembic/
│   ├── versions/          # Migraciones generadas
│   ├── env.py            # Configuración async de Alembic
│   └── script.py.mako    # Template para migraciones
├── alembic.ini           # Configuración de Alembic
├── .env                  # Variables de entorno (Supabase configurado)
└── app/
    ├── models.py         # Modelo Tienda con campo rubro
    └── api/routes/
        └── productos.py  # Errores de tipo corregidos
```

---

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'alembic'"
```powershell
pip install alembic
```

### Error: "Target database is not up to date"
```powershell
alembic stamp head
alembic revision --autogenerate -m "sync_database"
```

### Error: "Connection refused"
- Verifica que las credenciales en `.env` sean correctas
- Verifica que Supabase esté accesible
- Prueba la conexión:
```powershell
python -c "from app.core.config import settings; print(settings.DATABASE_URL)"
```

### Error: "SSL connection required"
Si Supabase requiere SSL, agrega a `app/core/db.py`:
```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    connect_args={"ssl": "require"}
)
```

---

## ✅ Checklist Final

- [x] Modelo `Tienda` actualizado con campo `rubro`
- [x] `.env` configurado con credenciales de Supabase
- [x] Errores de tipo corregidos en `productos.py`
- [x] `pyproject.toml` con configuración de build
- [x] Alembic configurado y listo
- [ ] Ejecutar: `pip install alembic`
- [ ] Ejecutar: `alembic revision --autogenerate -m "add_rubro_field_to_tienda"`
- [ ] Revisar archivo de migración generado
- [ ] Ejecutar: `alembic upgrade head`
- [ ] Verificar en Supabase SQL Editor
- [ ] (CRÍTICO) Cambiar SECRET_KEY en producción

---

## 📞 Contacto y Soporte

Si encuentras algún problema durante el deployment:
1. Revisa los logs de Alembic
2. Verifica la conexión a Supabase
3. Consulta la documentación de Supabase: https://supabase.com/docs

---

**¡Deployment exitoso! 🎉**
