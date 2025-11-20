# ⚡ QUICK START - Migración a Supabase

## 🎯 Comandos Rápidos (Copiar y Pegar)

### Opción 1: Script Automatizado (RECOMENDADO)
```powershell
# Ejecutar script automatizado
.\migrate_to_supabase.ps1
```

### Opción 2: Paso a Paso Manual
```powershell
# 1. Instalar Alembic
pip install alembic

# 2. Generar migración
alembic revision --autogenerate -m "add_rubro_field_to_tienda"

# 3. Aplicar a Supabase
alembic upgrade head

# 4. Verificar
python verificar_supabase.py
```

---

## 📋 Checklist de 3 Pasos

### ✅ Paso 1: Verificar .env
Abre `.env` y verifica que contenga:
```env
POSTGRES_SERVER=aws-1-us-east-2.pooler.supabase.com
POSTGRES_USER=postgres.kdqfohbtxlmykjubxqok
POSTGRES_PASSWORD=Juani2006
POSTGRES_DB=postgres
POSTGRES_PORT=5432
```

### ✅ Paso 2: Ejecutar Migración
```powershell
.\migrate_to_supabase.ps1
```

### ✅ Paso 3: Verificar
```powershell
python verificar_supabase.py
```

---

## 🔍 Verificación en Supabase SQL Editor

Ve a: https://supabase.com/dashboard → Tu Proyecto → SQL Editor

```sql
-- Verificar campo rubro
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'tiendas' AND column_name = 'rubro';

-- Ver tiendas
SELECT id, nombre, rubro, is_active, created_at
FROM tiendas;

-- Insertar tienda de prueba
INSERT INTO tiendas (id, nombre, rubro, is_active)
VALUES (gen_random_uuid(), 'Mi Tienda', 'ropa', true);
```

---

## 🐛 Solución de Problemas

### "ModuleNotFoundError: No module named 'alembic'"
```powershell
pip install alembic
```

### "Connection refused" o "Timeout"
1. Verifica credenciales en `.env`
2. Verifica que Supabase esté activo
3. Prueba: `python verificar_supabase.py`

### "No changes detected"
- Verifica que `app/models.py` tenga el campo `rubro`
- Ejecuta: `alembic revision --autogenerate -m "test" --verbose`

### "Target database is not up to date"
```powershell
alembic stamp head
alembic revision --autogenerate -m "sync"
```

---

## 📞 Resumen de Archivos

| Archivo | Descripción |
|---------|-------------|
| `.env` | ✅ Configurado para Supabase |
| `app/models.py` | ✅ Campo `rubro` agregado |
| `app/api/routes/productos.py` | ✅ Errores corregidos |
| `alembic.ini` | ✅ Configuración de Alembic |
| `alembic/env.py` | ✅ Soporte async |
| `migrate_to_supabase.ps1` | ✅ Script automatizado |
| `verificar_supabase.py` | ✅ Script de verificación |

---

## 🚀 ¡Listo para Producción!

**Todo está configurado.** Solo ejecuta:

```powershell
.\migrate_to_supabase.ps1
```

Y luego verifica con:

```powershell
python verificar_supabase.py
```

---

**¿Problemas?** Revisa `DEPLOYMENT_SUPABASE.md` para la guía completa.

**¿Todo funciona?** ¡Felicidades! 🎉 Nexus POS está listo para producción.
