"""
Reportes y Analytics - Nexus POS
Endpoints para generación de reportes de negocio
"""
import logging
from typing import Annotated, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from app.core.db import get_session
from app.models import Venta, DetalleVenta, Producto
from app.api.deps import CurrentTienda
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reportes", tags=["Reportes"])


# === SCHEMAS ===

class ProductoMasVendido(BaseModel):
    """Schema para productos más vendidos"""
    producto_id: UUID
    sku: str
    nombre: str
    cantidad_vendida: float
    total_recaudado: float
    veces_vendido: int
    
class VentasPorPeriodo(BaseModel):
    """Schema para ventas por período"""
    fecha: str
    cantidad_ventas: int
    total_vendido: float
    ticket_promedio: float
    
class ResumenVentas(BaseModel):
    """Schema para resumen de ventas"""
    periodo_inicio: datetime
    periodo_fin: datetime
    total_ventas: int
    monto_total: float
    ticket_promedio: float
    metodo_pago_mas_usado: Optional[str] = None
    producto_mas_vendido: Optional[str] = None
    
class RentabilidadProducto(BaseModel):
    """Schema para análisis de rentabilidad"""
    producto_id: UUID
    nombre: str
    sku: str
    cantidad_vendida: float
    costo_total: float
    ingreso_total: float
    utilidad_bruta: float
    margen_porcentaje: float


# === ENDPOINTS ===

@router.get("/ventas/resumen", response_model=ResumenVentas)
async def obtener_resumen_ventas(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    fecha_desde: Optional[datetime] = Query(None, description="Fecha inicial (default: hace 30 días)"),
    fecha_hasta: Optional[datetime] = Query(None, description="Fecha final (default: hoy)")
) -> ResumenVentas:
    """
    Obtiene un resumen general de ventas para un período
    
    Incluye:
    - Total de ventas realizadas
    - Monto total vendido
    - Ticket promedio
    - Método de pago más usado
    - Producto más vendido
    """
    # Defaults de fechas
    if fecha_hasta is None:
        fecha_hasta = datetime.utcnow()
    if fecha_desde is None:
        fecha_desde = fecha_hasta - timedelta(days=30)
    
    logger.info(f"Generando resumen de ventas para tienda {current_tienda.id} desde {fecha_desde} hasta {fecha_hasta}")
    
    # Query principal de ventas
    stmt = select(
        func.count(Venta.id).label('total_ventas'),
        func.sum(Venta.total).label('monto_total'),
        func.avg(Venta.total).label('ticket_promedio')
    ).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= fecha_desde,
            Venta.fecha <= fecha_hasta,
            Venta.status_pago == 'pagado'
        )
    )
    
    result = await session.execute(stmt)
    row = result.one()
    
    # Método de pago más usado
    stmt_metodo = select(
        Venta.metodo_pago,
        func.count(Venta.id).label('count')
    ).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= fecha_desde,
            Venta.fecha <= fecha_hasta,
            Venta.status_pago == 'pagado'
        )
    ).group_by(Venta.metodo_pago).order_by(desc('count')).limit(1)
    
    result_metodo = await session.execute(stmt_metodo)
    metodo_row = result_metodo.first()
    metodo_mas_usado = metodo_row[0] if metodo_row else None
    
    # Producto más vendido
    stmt_producto = select(
        Producto.nombre,
        func.sum(DetalleVenta.cantidad).label('total')
    ).join(
        DetalleVenta, Producto.id == DetalleVenta.producto_id
    ).join(
        Venta, DetalleVenta.venta_id == Venta.id
    ).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= fecha_desde,
            Venta.fecha <= fecha_hasta,
            Venta.status_pago == 'pagado'
        )
    ).group_by(Producto.nombre).order_by(desc('total')).limit(1)
    
    result_producto = await session.execute(stmt_producto)
    producto_row = result_producto.first()
    producto_mas_vendido = producto_row[0] if producto_row else None
    
    return ResumenVentas(
        periodo_inicio=fecha_desde,
        periodo_fin=fecha_hasta,
        total_ventas=row.total_ventas or 0,
        monto_total=float(row.monto_total or 0),
        ticket_promedio=float(row.ticket_promedio or 0),
        metodo_pago_mas_usado=metodo_mas_usado,
        producto_mas_vendido=producto_mas_vendido
    )


@router.get("/productos/mas-vendidos", response_model=List[ProductoMasVendido])
async def obtener_productos_mas_vendidos(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    limite: int = Query(10, ge=1, le=100, description="Cantidad de productos a retornar"),
    fecha_desde: Optional[datetime] = Query(None),
    fecha_hasta: Optional[datetime] = Query(None)
) -> List[ProductoMasVendido]:
    """
    Retorna los productos más vendidos ordenados por cantidad
    
    Útil para:
    - Identificar productos estrella
    - Optimizar inventario
    - Planificar promociones
    """
    # Defaults de fechas
    if fecha_hasta is None:
        fecha_hasta = datetime.utcnow()
    if fecha_desde is None:
        fecha_desde = fecha_hasta - timedelta(days=30)
    
    stmt = select(
        Producto.id.label('producto_id'),
        Producto.sku,
        Producto.nombre,
        func.sum(DetalleVenta.cantidad).label('cantidad_vendida'),
        func.sum(DetalleVenta.subtotal).label('total_recaudado'),
        func.count(DetalleVenta.id).label('veces_vendido')
    ).join(
        DetalleVenta, Producto.id == DetalleVenta.producto_id
    ).join(
        Venta, DetalleVenta.venta_id == Venta.id
    ).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= fecha_desde,
            Venta.fecha <= fecha_hasta,
            Venta.status_pago == 'pagado'
        )
    ).group_by(
        Producto.id, Producto.sku, Producto.nombre
    ).order_by(
        desc('cantidad_vendida')
    ).limit(limite)
    
    result = await session.execute(stmt)
    rows = result.all()
    
    return [
        ProductoMasVendido(
            producto_id=row.producto_id,
            sku=row.sku,
            nombre=row.nombre,
            cantidad_vendida=float(row.cantidad_vendida),
            total_recaudado=float(row.total_recaudado),
            veces_vendido=row.veces_vendido
        )
        for row in rows
    ]


@router.get("/productos/rentabilidad", response_model=List[RentabilidadProducto])
async def analizar_rentabilidad_productos(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    limite: int = Query(20, ge=1, le=100),
    orden: str = Query("utilidad", regex="^(utilidad|margen|cantidad)$")
) -> List[RentabilidadProducto]:
    """
    Analiza la rentabilidad de productos vendidos
    
    Calcula:
    - Costo total (precio_costo × cantidad)
    - Ingreso total (precio_venta × cantidad)
    - Utilidad bruta (ingreso - costo)
    - Margen de ganancia (%)
    
    Permite ordenar por:
    - utilidad: Mayor ganancia absoluta
    - margen: Mayor porcentaje de ganancia
    - cantidad: Más vendidos
    """
    stmt = select(
        Producto.id.label('producto_id'),
        Producto.nombre,
        Producto.sku,
        Producto.precio_costo,
        Producto.precio_venta,
        func.sum(DetalleVenta.cantidad).label('cantidad_vendida'),
        func.sum(DetalleVenta.subtotal).label('ingreso_total')
    ).join(
        DetalleVenta, Producto.id == DetalleVenta.producto_id
    ).join(
        Venta, DetalleVenta.venta_id == Venta.id
    ).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.status_pago == 'pagado'
        )
    ).group_by(
        Producto.id, Producto.nombre, Producto.sku,
        Producto.precio_costo, Producto.precio_venta
    )
    
    result = await session.execute(stmt)
    rows = result.all()
    
    # Calcular rentabilidad
    productos_rentabilidad = []
    for row in rows:
        cantidad_vendida = float(row.cantidad_vendida)
        costo_total = row.precio_costo * cantidad_vendida
        ingreso_total = float(row.ingreso_total)
        utilidad_bruta = ingreso_total - costo_total
        margen_porcentaje = (utilidad_bruta / ingreso_total * 100) if ingreso_total > 0 else 0
        
        productos_rentabilidad.append(
            RentabilidadProducto(
                producto_id=row.producto_id,
                nombre=row.nombre,
                sku=row.sku,
                cantidad_vendida=cantidad_vendida,
                costo_total=costo_total,
                ingreso_total=ingreso_total,
                utilidad_bruta=utilidad_bruta,
                margen_porcentaje=margen_porcentaje
            )
        )
    
    # Ordenar según parámetro
    if orden == "utilidad":
        productos_rentabilidad.sort(key=lambda x: x.utilidad_bruta, reverse=True)
    elif orden == "margen":
        productos_rentabilidad.sort(key=lambda x: x.margen_porcentaje, reverse=True)
    elif orden == "cantidad":
        productos_rentabilidad.sort(key=lambda x: x.cantidad_vendida, reverse=True)
    
    return productos_rentabilidad[:limite]


@router.get("/ventas/tendencia-diaria", response_model=List[VentasPorPeriodo])
async def obtener_tendencia_ventas_diaria(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    dias: int = Query(30, ge=7, le=365, description="Cantidad de días a analizar")
) -> List[VentasPorPeriodo]:
    """
    Retorna la tendencia de ventas día por día
    
    Útil para:
    - Gráficos de tendencia
    - Identificar patrones de venta
    - Proyecciones de demanda
    """
    fecha_desde = datetime.utcnow() - timedelta(days=dias)
    
    stmt = select(
        func.date(Venta.fecha).label('fecha'),
        func.count(Venta.id).label('cantidad_ventas'),
        func.sum(Venta.total).label('total_vendido'),
        func.avg(Venta.total).label('ticket_promedio')
    ).where(
        and_(
            Venta.tienda_id == current_tienda.id,
            Venta.fecha >= fecha_desde,
            Venta.status_pago == 'pagado'
        )
    ).group_by(
        func.date(Venta.fecha)
    ).order_by(
        func.date(Venta.fecha)
    )
    
    result = await session.execute(stmt)
    rows = result.all()
    
    return [
        VentasPorPeriodo(
            fecha=row.fecha.isoformat() if row.fecha else "",
            cantidad_ventas=row.cantidad_ventas or 0,
            total_vendido=float(row.total_vendido or 0),
            ticket_promedio=float(row.ticket_promedio or 0)
        )
        for row in rows
    ]
