# Nexus POS - Sistema Multi-Tenant Completo

## 🚀 Sistema Profesional de Punto de Venta

**Nexus POS** es un sistema completo de punto de venta (POS) multi-tenant diseñado para comercios de retail. Soporta múltiples tiendas independientes con aislamiento total de datos.

### ✨ Características Principales

#### 🏪 **Multi-Tenant Robusto**
- Aislamiento completo de datos por tienda
- Cada tienda opera independientemente
- Escalable para miles de tiendas

#### 📦 **Gestión de Inventario Avanzada**
- Productos polimórficos (general, ropa con variantes, productos pesables)
- Cálculo automático de stock para productos con variantes
- Alertas de stock bajo
- Ajustes manuales con auditoría completa
- Estadísticas de inventario en tiempo real

#### 💰 **Motor de Ventas Transaccional**
- Transacciones ACID con protección contra race conditions
- SELECT FOR UPDATE para bloqueo de productos durante checkout
- Validaciones exhaustivas de stock y consistencia
- Soporte para múltiples métodos de pago
- Descuentos y promociones

#### 💳 **Pagos Integrados**
- **Mercado Pago**: QR, Links de pago, Webhooks
- **AFIP**: Facturación electrónica (preparado)
- Gestión de estados de pago
- Reconciliación automática

#### 📊 **Reportes y Analytics**
- Productos más vendidos
- Análisis de rentabilidad por producto
- Tendencias de venta diarias
- Resumen ejecutivo de ventas
- Métricas de ticket promedio

#### 🔐 **Seguridad Enterprise**
- Autenticación JWT
- Rate limiting por IP
- Logging estructurado con rotación
- Auditoría de operaciones críticas
- Manejo global de excepciones

#### 📈 **Monitoreo y Observabilidad**
- Health checks avanzados (liveness/readiness)
- Métricas de sistema
- Logs estructurados en JSON
- Request ID para trazabilidad

---

## 📚 API Endpoints

### Autenticación
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/register` - Registro
- `GET /api/v1/auth/me` - Usuario actual

### Productos
- `GET /api/v1/productos/` - Listar productos
- `POST /api/v1/productos/` - Crear producto
- `GET /api/v1/productos/{id}` - Ver producto
- `PUT /api/v1/productos/{id}` - Actualizar producto
- `DELETE /api/v1/productos/{id}` - Eliminar producto

### Ventas
- `GET /api/v1/ventas/scan/{codigo}` - Escanear producto (POS)
- `POST /api/v1/ventas/checkout` - Procesar venta
- `GET /api/v1/ventas/` - Listar ventas
- `GET /api/v1/ventas/{id}` - Ver detalle venta

### Pagos
- `POST /api/v1/payments/generate/{venta_id}` - Generar link de pago
- `POST /api/v1/payments/webhook` - Webhook Mercado Pago

### Reportes ⭐
- `GET /api/v1/reportes/ventas/resumen` - Resumen de ventas
- `GET /api/v1/reportes/productos/mas-vendidos` - Top productos
- `GET /api/v1/reportes/productos/rentabilidad` - Análisis rentabilidad
- `GET /api/v1/reportes/ventas/tendencia-diaria` - Tendencia ventas

### Inventario ⭐
- `GET /api/v1/inventario/alertas-stock-bajo` - Alertas stock
- `GET /api/v1/inventario/sin-stock` - Productos sin stock
- `GET /api/v1/inventario/estadisticas` - Stats inventario
- `POST /api/v1/inventario/ajustar-stock` - Ajuste manual

### Health ⭐
- `GET /api/v1/health/` - Liveness probe
- `GET /api/v1/health/ready` - Readiness probe
- `GET /api/v1/health/metrics` - Métricas sistema

---

## 🛠️ Instalación con Docker

```bash
# 1. Clonar y configurar
git clone <repo-url>
cd POS
cp .env.example .env

# 2. Levantar servicios
docker-compose up -d

# 3. Ver logs
docker-compose logs -f backend

# 4. Acceder
# API: http://localhost:8000
# Docs: http://localhost:8000/api/v1/docs
# DB Admin: http://localhost:8080
```

---

## 🔐 Seguridad

✅ **Implementado:**
- JWT Authentication
- Rate Limiting
- SQL Injection Protection
- CORS configurado
- Bcrypt password hashing
- Logging de auditoría
- Manejo global de excepciones
- Request ID tracking

---

## 📊 Arquitectura

```
Backend (FastAPI) → PostgreSQL
     ↓
MercadoPago API
     ↓
AFIP Webservice
```

**Stack:**
- Python 3.11+ / FastAPI
- PostgreSQL / SQLModel / asyncpg
- Docker / Docker Compose
- JWT / bcrypt
- Mercado Pago SDK

---

## 📈 Próximos Pasos

- [ ] Integración AFIP completa
- [ ] Generación PDFs facturas
- [ ] Sistema de descuentos
- [ ] App móvil
- [ ] ML para predicción demanda

---

**Desarrollado con ❤️ usando FastAPI**
