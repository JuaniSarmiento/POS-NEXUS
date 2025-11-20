"""
Exportación de Reportes - Nexus POS
Endpoints para exportar reportes en formatos CSV y PDF
"""
from datetime import datetime, timedelta
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
import io
import csv

from app.core.db import get_session
from app.models import Producto, Venta, DetalleVenta
from app.api.deps import CurrentTienda

router = APIRouter(prefix="/exportar", tags=["Exportación"])


@router.get("/productos/csv")
async def exportar_productos_csv(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    solo_activos: bool = Query(True)
) -> StreamingResponse:
    """
    Exporta listado de productos a formato CSV
    
    Columnas: SKU, Nombre, Tipo, Precio Venta, Precio Costo, Stock, Estado
    """
    # Consultar productos
    stmt = select(Producto).where(Producto.tienda_id == current_tienda.id)
    if solo_activos:
        stmt = stmt.where(Producto.is_active == True)
    
    result = await session.execute(stmt)
    productos = result.scalars().all()
    
    # Crear CSV en memoria
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow(['SKU', 'Nombre', 'Tipo', 'Precio Venta', 'Precio Costo', 'Stock Actual', 'Margen %', 'Estado'])
    
    # Datos
    for p in productos:
        margen = ((p.precio_venta - p.precio_costo) / p.precio_venta * 100) if p.precio_venta > 0 else 0
        writer.writerow([
            p.sku,
            p.nombre,
            p.tipo,
            f"${p.precio_venta:.2f}",
            f"${p.precio_costo:.2f}",
            p.stock_actual,
            f"{margen:.1f}%",
            'Activo' if p.is_active else 'Inactivo'
        ])
    
    # Preparar respuesta
    output.seek(0)
    fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"productos_{current_tienda.nombre.replace(' ', '_')}_{fecha}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/ventas/csv")
async def exportar_ventas_csv(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None
) -> StreamingResponse:
    """
    Exporta ventas a formato CSV con filtros de fecha
    
    Columnas: Fecha, ID Venta, Total, Método Pago, Status, Cantidad Items
    """
    # Defaults
    if fecha_hasta is None:
        fecha_hasta = datetime.utcnow()
    if fecha_desde is None:
        fecha_desde = fecha_hasta - timedelta(days=30)
    
    # Consultar ventas
    stmt = (
        select(
            Venta,
            func.count(DetalleVenta.id).label('cantidad_items')
        )
        .outerjoin(DetalleVenta, Venta.id == DetalleVenta.venta_id)
        .where(
            and_(
                Venta.tienda_id == current_tienda.id,
                Venta.fecha >= fecha_desde,
                Venta.fecha <= fecha_hasta
            )
        )
        .group_by(Venta.id)
        .order_by(Venta.fecha.desc())
    )
    
    result = await session.execute(stmt)
    rows = result.all()
    
    # Crear CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow(['Fecha', 'ID Venta', 'Total', 'Método Pago', 'Status Pago', 'Cantidad Items', 'Payment ID', 'CAE AFIP'])
    
    # Datos
    for venta, cantidad_items in rows:
        writer.writerow([
            venta.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            str(venta.id),
            f"${venta.total:.2f}",
            venta.metodo_pago,
            venta.status_pago,
            cantidad_items or 0,
            venta.payment_id or '-',
            venta.afip_cae or '-'
        ])
    
    # Preparar respuesta
    output.seek(0)
    fecha_archivo = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"ventas_{current_tienda.nombre.replace(' ', '_')}_{fecha_archivo}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/reportes/rentabilidad/csv")
async def exportar_rentabilidad_csv(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None
) -> StreamingResponse:
    """
    Exporta análisis de rentabilidad de productos a CSV
    
    Columnas: Producto, SKU, Cantidad Vendida, Costo Total, Ingreso Total, Utilidad, Margen %
    """
    # Defaults
    if fecha_hasta is None:
        fecha_hasta = datetime.utcnow()
    if fecha_desde is None:
        fecha_desde = fecha_hasta - timedelta(days=30)
    
    # Query de rentabilidad
    stmt = select(
        Producto.nombre,
        Producto.sku,
        func.sum(DetalleVenta.cantidad).label('cantidad_vendida'),
        func.sum(DetalleVenta.cantidad * Producto.precio_costo).label('costo_total'),
        func.sum(DetalleVenta.subtotal).label('ingreso_total')
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
        Producto.id, Producto.nombre, Producto.sku
    ).order_by(desc('ingreso_total'))
    
    result = await session.execute(stmt)
    rows = result.all()
    
    # Crear CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow(['Producto', 'SKU', 'Cantidad Vendida', 'Costo Total', 'Ingreso Total', 'Utilidad Bruta', 'Margen %'])
    
    # Datos
    for nombre, sku, cantidad, costo, ingreso in rows:
        cantidad = float(cantidad or 0)
        costo_total = float(costo or 0)
        ingreso_total = float(ingreso or 0)
        utilidad = ingreso_total - costo_total
        margen = (utilidad / ingreso_total * 100) if ingreso_total > 0 else 0
        
        writer.writerow([
            nombre,
            sku,
            f"{cantidad:.2f}",
            f"${costo_total:.2f}",
            f"${ingreso_total:.2f}",
            f"${utilidad:.2f}",
            f"{margen:.1f}%"
        ])
    
    # Preparar respuesta
    output.seek(0)
    fecha_archivo = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"rentabilidad_{current_tienda.nombre.replace(' ', '_')}_{fecha_archivo}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
