"""
Dashboard Endpoints - Nexus POS
Endpoints consolidados para vista de dashboard con métricas clave
"""
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from pydantic import BaseModel

from app.core.db import get_session
import logging
from app.core.cache import cached
from app.models import Producto, Venta, DetalleVenta
from app.api.deps import CurrentTienda

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# === SCHEMAS ===

class MetricaVentas(BaseModel):
    """Métrica de ventas"""
    hoy: float
    ayer: float
    semana: float
    mes: float
    cambio_diario_porcentaje: float
    cambio_semanal_porcentaje: float


class MetricaInventario(BaseModel):
    """Métrica de inventario"""
    total_productos: int
    productos_activos: int
    productos_bajo_stock: int
    valor_total_inventario: float


class ProductoDestacado(BaseModel):
    """Producto destacado del dashboard"""
    id: str
    nombre: str
    sku: str
    stock: float
    ventas_hoy: int


class DashboardResumen(BaseModel):
    """Resumen completo del dashboard"""
    ventas: MetricaVentas
    inventario: MetricaInventario
    productos_destacados: list[ProductoDestacado]
    alertas_criticas: int
    ultima_actualizacion: datetime


# === ENDPOINTS ===

@router.get("/resumen", response_model=DashboardResumen)
@cached(ttl_seconds=60, key_prefix="dashboard")  # Cache de 1 minuto
async def obtener_dashboard_resumen(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> DashboardResumen:
    """
    Endpoint principal del dashboard con todas las métricas consolidadas
    
    Incluye:
    - Ventas (hoy, ayer, semana, mes con % de cambio)
    - Inventario (totales, bajo stock, valor)
    - Productos destacados
    - Alertas críticas
    
    **Cacheado por 60 segundos para mejor performance**
    """
    logger.info(f"Generando dashboard para tienda {current_tienda.id}")
    
    # Rangos de fechas
    ahora = datetime.utcnow()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    ayer_inicio = hoy_inicio - timedelta(days=1)
    semana_inicio = hoy_inicio - timedelta(days=7)
    mes_inicio = hoy_inicio - timedelta(days=30)
    
    # === VENTAS ===
    # Ventas de hoy
    stmt_hoy = select(func.coalesce(func.sum(Venta.total), 0)).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= hoy_inicio,
            Venta.status_pago == 'pagado'
        )
    )
    ventas_hoy = (await session.execute(stmt_hoy)).scalar()
    
    # Ventas de ayer
    stmt_ayer = select(func.coalesce(func.sum(Venta.total), 0)).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= ayer_inicio,
            Venta.fecha < hoy_inicio,
            Venta.status_pago == 'pagado'
        )
    )
    ventas_ayer = (await session.execute(stmt_ayer)).scalar()
    
    # Ventas de la semana
    stmt_semana = select(func.coalesce(func.sum(Venta.total), 0)).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= semana_inicio,
            Venta.status_pago == 'pagado'
        )
    )
    ventas_semana = (await session.execute(stmt_semana)).scalar()
    
    # Ventas del mes
    stmt_mes = select(func.coalesce(func.sum(Venta.total), 0)).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= mes_inicio,
            Venta.status_pago == 'pagado'
        )
    )
    ventas_mes = (await session.execute(stmt_mes)).scalar()
    
    # Calcular cambios porcentuales
    cambio_diario = ((ventas_hoy - ventas_ayer) / ventas_ayer * 100) if ventas_ayer > 0 else 0
    semana_pasada = ventas_semana - ventas_hoy  # Aproximación
    cambio_semanal = ((ventas_hoy - (semana_pasada / 7)) / (semana_pasada / 7) * 100) if semana_pasada > 0 else 0
    
    # === INVENTARIO ===
    # Contar productos totales
    stmt_total = select(func.count(Producto.id)).where(Producto.tienda_id == current_tienda.id)
    total_productos = (await session.execute(stmt_total)).scalar()
    
    # Contar productos activos
    stmt_activos = select(func.count(Producto.id)).where(
        and_(Producto.tienda_id == current_tienda.id, Producto.is_active == True)
    )
    productos_activos = (await session.execute(stmt_activos)).scalar()
    
    # Contar productos bajo stock
    stmt_bajo_stock = select(func.count(Producto.id)).where(
        and_(Producto.tienda_id == current_tienda.id, Producto.stock_actual <= 10)
    )
    productos_bajo_stock = (await session.execute(stmt_bajo_stock)).scalar()
    
    # Valor total del inventario
    stmt_valor = select(func.coalesce(func.sum(Producto.stock_actual * Producto.precio_venta), 0)).where(
        Producto.tienda_id == current_tienda.id
    )
    valor_inventario = (await session.execute(stmt_valor)).scalar()
    
    # === PRODUCTOS DESTACADOS (más vendidos hoy) ===
    stmt_destacados = select(
        Producto.id,
        Producto.nombre,
        Producto.sku,
        Producto.stock_actual,
        func.count(DetalleVenta.id).label('ventas_count')
    ).join(
        DetalleVenta, Producto.id == DetalleVenta.producto_id
    ).join(
        Venta, DetalleVenta.venta_id == Venta.id
    ).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= hoy_inicio,
            Venta.status_pago == 'pagado'
        )
    ).group_by(
        Producto.id, Producto.nombre, Producto.sku, Producto.stock_actual
    ).order_by(desc('ventas_count')).limit(5)
    
    destacados_result = await session.execute(stmt_destacados)
    destacados = [
        ProductoDestacado(
            id=str(row[0]),
            nombre=row[1],
            sku=row[2],
            stock=row[3],
            ventas_hoy=row[4]
        )
        for row in destacados_result.all()
    ]
    
    # === ALERTAS CRÍTICAS ===
    # Productos sin stock + bajo stock crítico (< 5)
    stmt_alertas = select(func.count(Producto.id)).where(
        and_(
            Producto.tienda_id == current_tienda.id,
            Producto.stock_actual < 5,
            Producto.is_active == True
        )
    )
    alertas = (await session.execute(stmt_alertas)).scalar()
    
    return DashboardResumen(
        ventas=MetricaVentas(
            hoy=float(ventas_hoy),
            ayer=float(ventas_ayer),
            semana=float(ventas_semana),
            mes=float(ventas_mes),
            cambio_diario_porcentaje=round(cambio_diario, 2),
            cambio_semanal_porcentaje=round(cambio_semanal, 2)
        ),
        inventario=MetricaInventario(
            total_productos=total_productos or 0,
            productos_activos=productos_activos or 0,
            productos_bajo_stock=productos_bajo_stock or 0,
            valor_total_inventario=float(valor_inventario or 0)
        ),
        productos_destacados=destacados,
        alertas_criticas=alertas,
        ultima_actualizacion=datetime.utcnow()
    )


@router.get("/ventas-tiempo-real")
async def obtener_ventas_tiempo_real(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    """
    Ventas de las últimas 24 horas agrupadas por hora (para gráfico en tiempo real)
    
    **Sin caché para datos en tiempo real**
    """
    hace_24h = datetime.utcnow() - timedelta(hours=24)
    
    stmt = select(
        func.date_trunc('hour', Venta.fecha).label('hora'),
        func.count(Venta.id).label('cantidad'),
        func.sum(Venta.total).label('total')
    ).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= hace_24h,
            Venta.status_pago == 'pagado'
        )
    ).group_by('hora').order_by('hora')
    
    result = await session.execute(stmt)
    
    return {
        "periodo": "ultimas_24h",
        "datos": [
            {
                "hora": row[0].isoformat() if row[0] else None,
                "cantidad_ventas": row[1],
                "total": float(row[2] or 0)
            }
            for row in result.all()
        ]
    }
