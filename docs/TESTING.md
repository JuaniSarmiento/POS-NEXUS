# 🧪 Guía de Testing - Nexus POS

## 📋 Tabla de Contenidos

- [Introducción](#introducción)
- [Configuración](#configuración)
- [Ejecutar Tests](#ejecutar-tests)
- [Estructura de Tests](#estructura-de-tests)
- [Fixtures Disponibles](#fixtures-disponibles)
- [Ejemplos de Tests](#ejemplos-de-tests)
- [Coverage](#coverage)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Introducción

Esta suite de tests automatizados cubre **todos los módulos del backend** de Nexus POS:

- ✅ **Productos**: CRUD, polimorfismo (ropa, pesable, general)
- ✅ **Ventas**: Checkout, scan, descuento de stock, race conditions
- ✅ **Pagos**: Integración con MercadoPago (mockeada)
- ✅ **Insights**: Alertas de stock bajo, analytics
- ✅ **Multi-Tenancy**: Aislamiento estricto entre tiendas

### Tecnologías

- **pytest**: Framework de testing
- **pytest-asyncio**: Soporte para tests asíncronos
- **httpx**: Cliente HTTP para FastAPI
- **pytest-cov**: Reporte de cobertura de código
- **unittest.mock**: Mocks de servicios externos (MercadoPago, AFIP)

---

## ⚙️ Configuración

### 1. Instalar Dependencias

```bash
# Con uv (recomendado)
uv pip install -e ".[dev]"

# O con pip tradicional
pip install -e ".[dev]"
```

### 2. Crear Base de Datos de Test

Los tests usan una base de datos separada llamada `nexus_pos_test`.

**PostgreSQL:**
```bash
# Conectarse a PostgreSQL
psql -U postgres

# Crear base de datos de test
CREATE DATABASE nexus_pos_test;
```

**Nota:** Los tests crean y destruyen las tablas automáticamente en cada ejecución.

### 3. Configurar Variables de Entorno

El archivo `.env` se usa tanto para desarrollo como para tests. Asegúrate de tener configurado:

```bash
# .env
POSTGRES_SERVER=localhost
POSTGRES_USER=nexuspos
POSTGRES_PASSWORD=tu_password
POSTGRES_DB=nexus_pos

# SECRET_KEY (generar con: openssl rand -hex 32)
SECRET_KEY=tu_secret_key_super_segura
```

---

## 🚀 Ejecutar Tests

### Métodos Disponibles

#### **1. Script Maestro (Recomendado)**

**Linux/Mac:**
```bash
bash run_all_tests.sh
```

**Windows:**
```cmd
run_all_tests.bat
```

Este script:
- ✨ Limpia caché de pytest
- 🧪 Ejecuta todos los tests
- 📊 Genera reporte de cobertura HTML
- ✅ Valida cobertura mínima (80%)
- 🎨 Output con colores

#### **2. Con Makefile**

```bash
# Tests básicos
make test

# Tests con coverage
make test-cov

# Suite completa (Linux/Mac)
make test-all

# Suite completa (Windows)
make test-all-win
```

#### **3. Directamente con pytest**

```bash
# Todos los tests
pytest

# Tests con coverage
pytest --cov=app --cov-report=html

# Tests específicos
pytest tests/api/routes/test_productos.py

# Un solo test
pytest tests/api/routes/test_ventas.py::test_checkout_venta_simple

# Tests con verbose
pytest -v

# Detener en el primer error
pytest -x

# Re-ejecutar solo los fallidos
pytest --lf
```

---

## 📁 Estructura de Tests

```
tests/
├── __init__.py
├── conftest.py                    # Fixtures globales
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       ├── test_productos.py      # Tests de CRUD de productos
│       ├── test_ventas.py         # Tests de motor de ventas
│       ├── test_payments.py       # Tests de pagos (MercadoPago)
│       └── test_insights.py       # Tests de analytics
└── services/
    └── __init__.py
```

---

## 🔧 Fixtures Disponibles

### Base de Datos

#### `db`
Sesión de base de datos con rollback automático.

```python
async def test_ejemplo(db: AsyncSession):
    producto = Producto(...)
    db.add(producto)
    await db.commit()
```

### Clientes HTTP

#### `client`
Cliente sin autenticación.

```python
def test_ejemplo(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
```

#### `authenticated_client`
Cliente autenticado con usuario owner de la tienda principal.

```python
def test_ejemplo(authenticated_client: TestClient):
    response = authenticated_client.get("/api/v1/productos/")
    assert response.status_code == 200
```

#### `authenticated_client_2`
Cliente autenticado de una segunda tienda (para tests de aislamiento multi-tenant).

```python
def test_aislamiento(
    authenticated_client: TestClient,
    authenticated_client_2: TestClient
):
    # Cliente 1 no puede ver datos de Cliente 2
    ...
```

### Datos de Prueba

#### `tienda`
Tienda de prueba principal.

```python
def test_ejemplo(tienda: Tienda):
    assert tienda.nombre == "Tienda Test"
```

#### `tienda_2`
Segunda tienda para tests de aislamiento.

#### `user`
Usuario owner de la tienda principal.

#### `user_2`
Usuario owner de la segunda tienda.

#### `producto_ropa`
Producto tipo "ropa" con variantes.

```python
def test_ejemplo(producto_ropa: Producto):
    assert producto_ropa.tipo == "ropa"
    assert len(producto_ropa.datos_especificos["variantes"]) == 3
```

#### `producto_pesable`
Producto tipo "pesable" (carnicería).

```python
def test_ejemplo(producto_pesable: Producto):
    assert producto_pesable.tipo == "pesable"
```

### Factory Fixtures

#### `create_producto`
Factory para crear productos dinámicamente.

```python
@pytest.mark.asyncio
async def test_ejemplo(db: AsyncSession, tienda: Tienda, create_producto):
    producto = await create_producto(
        db=db,
        tienda_id=tienda.id,
        sku="TEST-001",
        nombre="Producto Test",
        precio=1500.00,
        stock=100.0
    )
```

---

## 📝 Ejemplos de Tests

### Test Básico de CRUD

```python
def test_crear_producto(authenticated_client: TestClient):
    payload = {
        "sku": "PROD-001",
        "nombre": "Producto de Prueba",
        "tipo": "general",
        "precio": 1000.00,
        "stock_actual": 50.0
    }
    
    response = authenticated_client.post("/api/v1/productos/", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "PROD-001"
```

### Test con Mock de MercadoPago

```python
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_generar_qr(authenticated_client: TestClient, venta):
    with patch('app.services.payment_service.mercadopago.SDK') as mock_sdk:
        mock_preference = MagicMock()
        mock_preference.create.return_value = {
            "status": 201,
            "response": {
                "id": "123456",
                "init_point": "https://mercadopago.com/..."
            }
        }
        mock_sdk.return_value.preference.return_value = mock_preference
        
        response = authenticated_client.post(f"/api/v1/payments/generate/{venta.id}")
        assert response.status_code == 200
```

### Test de Aislamiento Multi-Tenant

```python
@pytest.mark.asyncio
async def test_aislamiento(
    authenticated_client: TestClient,
    authenticated_client_2: TestClient,
    producto_ropa: Producto
):
    # Cliente 1 puede ver sus productos
    response_1 = authenticated_client.get("/api/v1/productos/")
    productos_1 = response_1.json()
    assert len(productos_1) > 0
    
    # Cliente 2 NO puede ver productos de Cliente 1
    response_2 = authenticated_client_2.get("/api/v1/productos/")
    productos_2 = response_2.json()
    
    skus_1 = [p["sku"] for p in productos_1]
    skus_2 = [p["sku"] for p in productos_2]
    
    assert producto_ropa.sku in skus_1
    assert producto_ropa.sku not in skus_2
```

---

## 📊 Coverage

### Ver Reporte

Después de ejecutar los tests con coverage:

```bash
# Linux/Mac
open htmlcov/index.html

# Windows
start htmlcov/index.html
```

### Umbral de Cobertura

El proyecto requiere **mínimo 80% de cobertura** de código.

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=app --cov-fail-under=80"
```

### Excluir Archivos del Coverage

Si necesitas excluir archivos específicos, modifica `pyproject.toml`:

```toml
[tool.coverage.run]
omit = [
    "*/tests/*",
    "*/migrations/*",
]
```

---

## 🐛 Troubleshooting

### Error: "Database nexus_pos_test does not exist"

**Solución:**
```bash
psql -U postgres -c "CREATE DATABASE nexus_pos_test;"
```

### Error: "ModuleNotFoundError: No module named 'pytest'"

**Solución:**
```bash
uv pip install -e ".[dev]"
```

### Tests pasan localmente pero fallan en CI

**Posibles causas:**
1. Diferencias en variables de entorno
2. Base de datos no configurada en CI
3. Dependencias faltantes

**Solución:**
- Asegúrate de que `.env.example` esté completo
- Configura secrets en tu plataforma de CI
- Verifica que las dependencias estén en `pyproject.toml`

### Los tests están lentos

**Optimizaciones:**
1. Usar `scope="module"` en fixtures pesadas
2. Reducir el número de commits en tests
3. Usar transacciones en lugar de crear/borrar datos

```python
@pytest.fixture(scope="module")
async def tienda_modulo():
    # Se crea una vez por módulo, no por test
    ...
```

### Error: "Port 5432 already in use"

**Solución:**
```bash
# Detener PostgreSQL local
sudo service postgresql stop

# O cambiar el puerto en docker-compose.yml
ports:
  - "5433:5432"  # Puerto externo 5433
```

---

## 🎯 Mejores Prácticas

1. **Un assert por concepto**: No mezclar múltiples validaciones sin relación
2. **Nombres descriptivos**: `test_no_puedo_ver_productos_de_otra_tienda` mejor que `test_productos_2`
3. **AAA Pattern**: Arrange (setup), Act (acción), Assert (verificación)
4. **Usar fixtures**: Evitar duplicar código de setup
5. **Mocks para servicios externos**: NUNCA llamar APIs reales en tests
6. **Tests aislados**: Cada test debe poder correr independientemente

---

## 📚 Referencias

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [pytest-cov](https://pytest-cov.readthedocs.io/)

---

**¡Happy Testing! 🚀**
