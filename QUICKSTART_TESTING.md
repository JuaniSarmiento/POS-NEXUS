# 🚀 Quick Start - Testing en 5 Minutos

## ⚡ Inicio Rápido

### 1️⃣ Instalar Dependencias

```bash
# Instalar uv (si no lo tienes)
pip install uv

# Instalar dependencias del proyecto
uv pip install -e ".[dev]"
```

### 2️⃣ Crear Base de Datos de Test

```bash
# PostgreSQL
psql -U postgres -c "CREATE DATABASE nexus_pos_test;"

# O con Docker
docker run -d \
  --name postgres-test \
  -e POSTGRES_USER=nexuspos \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_DB=nexus_pos_test \
  -p 5432:5432 \
  postgres:17-alpine
```

### 3️⃣ Configurar Variables de Entorno

Asegúrate de tener `.env` configurado:

```bash
# .env
POSTGRES_SERVER=localhost
POSTGRES_USER=nexuspos
POSTGRES_PASSWORD=tu_password
POSTGRES_DB=nexus_pos

SECRET_KEY=tu_secret_key  # Generar con: openssl rand -hex 32
```

### 4️⃣ Ejecutar Tests

#### **Opción A: Script Maestro (Recomendado)**

```bash
# Linux/Mac
bash run_all_tests.sh

# Windows PowerShell
.\run_all_tests.ps1

# Windows CMD
run_all_tests.bat
```

#### **Opción B: Makefile**

```bash
make test           # Tests básicos
make test-cov       # Con coverage
```

#### **Opción C: Pytest Directo**

```bash
pytest              # Todos los tests
pytest -v           # Verbose
pytest --cov=app    # Con coverage
```

### 5️⃣ Ver Resultados

```bash
# Abrir reporte de cobertura en navegador
open htmlcov/index.html        # Mac
xdg-open htmlcov/index.html    # Linux
start htmlcov/index.html       # Windows
```

---

## 🎯 Comandos Esenciales

### Tests Específicos

```bash
# Un módulo completo
pytest tests/api/routes/test_productos.py

# Un test específico
pytest tests/api/routes/test_ventas.py::test_checkout_venta_simple

# Por palabra clave
pytest -k "stock"

# Solo los que fallaron la última vez
pytest --lf

# Detener en el primer error
pytest -x
```

### Debugging

```bash
# Verbose máximo
pytest -vv

# Mostrar print statements
pytest -s

# Traceback completo
pytest --tb=long

# Debug interactivo (con pdb)
pytest --pdb
```

### Coverage

```bash
# Coverage básico
pytest --cov=app

# Coverage con líneas faltantes
pytest --cov=app --cov-report=term-missing

# Coverage HTML
pytest --cov=app --cov-report=html

# Coverage con threshold
pytest --cov=app --cov-fail-under=80
```

---

## 📊 Estructura de Tests

```
tests/
├── conftest.py                    # Fixtures globales
├── api/
│   └── routes/
│       ├── test_productos.py      # 10 tests
│       ├── test_ventas.py         # 11 tests
│       ├── test_payments.py       # 7 tests
│       └── test_insights.py       # 8 tests
└── services/
    └── (futuro)
```

**Total: 36+ tests**

---

## ✅ Checklist de Validación

Antes de hacer commit/push, verifica:

- [ ] Todos los tests pasan: `pytest`
- [ ] Coverage >= 80%: `pytest --cov=app --cov-fail-under=80`
- [ ] Sin errores de linting: `ruff check .`
- [ ] Código formateado: `ruff format .`

---

## 🐛 Troubleshooting Común

### Error: "ModuleNotFoundError: No module named 'pytest'"
```bash
uv pip install -e ".[dev]"
```

### Error: "Database nexus_pos_test does not exist"
```bash
psql -U postgres -c "CREATE DATABASE nexus_pos_test;"
```

### Error: "Port 5432 already in use"
```bash
# Detener PostgreSQL local
sudo service postgresql stop

# O cambiar puerto en .env
POSTGRES_PORT=5433
```

### Tests lentos
```bash
# Usar fixtures con scope="module"
# Reducir número de commits en tests
# Usar transacciones en lugar de crear/borrar datos
```

---

## 📚 Más Información

- **Guía Completa**: [`docs/TESTING.md`](docs/TESTING.md)
- **Resumen de Tests**: [`docs/TEST_SUMMARY.md`](docs/TEST_SUMMARY.md)
- **Deployment**: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

---

## 🎓 Mejores Prácticas

1. **Ejecuta tests antes de cada commit**
2. **Mantén la cobertura >= 80%**
3. **Usa fixtures para evitar duplicación**
4. **Nombra tests descriptivamente**
5. **No testees implementaciones, testea comportamiento**
6. **Mockea servicios externos (MercadoPago, AFIP)**
7. **Un assert por concepto**

---

## 🏆 Objetivo de Calidad

```
✅ Coverage >= 80%
✅ Todos los tests verdes
✅ Multi-tenancy validado
✅ Servicios externos mockeados
✅ 0 errores de linting
```

---

**¡Listo para testear! 🧪🚀**

*Última actualización: 2025-11-19*
